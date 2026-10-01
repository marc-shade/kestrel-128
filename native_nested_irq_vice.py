"""Force real ROM IRQ nesting in VICE and check complete desktop return."""
from contextlib import contextmanager
import hashlib
import json
import struct
import time

from hwlib import lst_symbol
from launcher_scene import surface
from native_vdc_scene import bitmap as vdc_bitmap,pointer_bitmap
from native_capture import NativeCapture
from native_capture_transport import PausedViceMonitor


class NestedMonitor(PausedViceMonitor):
    def __init__(self,monitor,work):
        super().__init__(monitor);self.work=work;self.forced=False;self.frames=[];self.checkpoints={}
        raw=self.command(0x83,b'\0');count=int.from_bytes(raw[:2],'little');pos=2
        self.register_names={}
        for _ in range(count):
            size=raw[pos];item=raw[pos+1:pos+size+1];pos+=size+1
            self.register_names[item[0]]=item[3:3+item[2]].decode()

    def command(self,code,body=b''):
        error,raw=self.monitor._recv(self.monitor._send(code,body));assert not error,(code,error)
        return raw

    def registers(self):
        raw=self.command(0x31,b'\0');count=int.from_bytes(raw[:2],'little');pos=2;result={}
        for _ in range(count):
            size=raw[pos];item=raw[pos+1:pos+size+1];pos+=size+1
            result[self.register_names[item[0]]]=int.from_bytes(item[1:],'little')
        return result

    def breakpoint(self,address):
        raw=self.command(0x12,struct.pack('<HHBBBBB',address,address,1,1,4,0,0))
        self.checkpoints[address]=int.from_bytes(raw[:4],'little')
        (self.work/f'checkpoint-{address:04x}.bin').write_bytes(raw)

    def await_pc(self,address):
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            registers=self.registers()
            if registers['PC']==address:
                self.command(0x13,struct.pack('<I',self.checkpoints.pop(address)))
                return registers
            self.monitor.resume();time.sleep(.15)
        diagnostic=dict(registers=registers,irq=bytes(self.monitor.read_mem(0x314,0x315)).hex(),
            mmu=bytes(self.monitor.read_mem(0xff00,0xff00)).hex(),
            vic=bytes(self.monitor.read_mem(0xd011,0xd01a)).hex())
        diagnostic['checkpoint_hex']=self.command(0x11,struct.pack('<I',self.checkpoints[address])).hex()
        (self.work/'breakpoint-timeout.json').write_text(json.dumps(diagnostic,indent=2)+'\n')
        raise AssertionError(('did not hit breakpoint',hex(address),diagnostic))

    def reach(self,address):
        self.breakpoint(address);self.monitor.resume();time.sleep(.15)
        return self.await_pc(address)

    def enter_rom_irq(self):
        # This one-shot entry occupies the probe's unused tail. It restores
        # the real vector before entering the unmodified ROM IRQ handler.
        assert bytes(self.monitor.read_mem(0x314,0x315))==b'\x65\xfa'
        self.monitor.write_mem(0x3fd0,bytes.fromhex('a9658d1403a9fa8d15034c65fa'))
        self.monitor.write_mem(0x314,b'\xd0\x3f')
        self.reach(0x3fd0)
        trace=[]
        for _ in range(80):
            registers=self.registers();pc=registers['PC']
            trace.append(dict(registers=registers,opcode=bytes(self.monitor.read_mem(pc,pc+2)).hex(),
                              mmu=bytes(self.monitor.read_mem(0xff00,0xff00)).hex()))
            if pc==0xc22a:
                (self.work/'actual-irq-trace.json').write_text(json.dumps(trace,indent=2)+'\n')
                return registers
            self.command(0x71,b'\0\1\0');time.sleep(.005)
        (self.work/'actual-irq-trace.json').write_text(json.dumps(trace,indent=2)+'\n')
        raise AssertionError('stepped ROM IRQ did not reach its CLI return')

    @contextmanager
    def paused(self,label):
        force=not self.forced and label.endswith('-command-0000')
        if force:
            self.forced=True
            outer=self.enter_rom_irq()
            assert bytes(self.monitor.read_mem(0xff00,0xff00))==b'\0'
            outer_stack=bytes(self.monitor.read_mem(0x100,0x1ff))
            assert outer_stack[outer['SP']+3]==0x0e
        with super().paused(label):
            yield
            if force:
                # Keep the display mode; schedule a raster IRQ one line ahead
                # while the outer ROM handler has already executed its CLI.
                self.breakpoint(0x3e00)
                d011=self.monitor.read_mem(0xd011,0xd011)[0]
                raster=self.monitor.read_mem(0xd012,0xd012)[0]+((d011&128)<<1)
                assert raster<310
                next_line=raster+1
                self.monitor.write_mem(0xd011,bytes([(d011&127)|((next_line>>1)&128)]))
                self.monitor.write_mem(0xd012,bytes([next_line&255]))
        if force:
            nested=self.await_pc(0x3e00)
            stack=bytes(self.monitor.read_mem(0x100,0x1ff));sp=nested['SP']
            interrupted_pc=int.from_bytes(stack[sp+6:sp+8],'little')
            row=dict(label=label,outer=outer,nested=nested,saved_mmu=stack[sp+1],
                     interrupted_pc=interrupted_pc,outer_saved_mmu=outer_stack[outer['SP']+3])
            self.frames.append(row)
            (self.work/(label+'-outer-stack.bin')).write_bytes(outer_stack)
            (self.work/(label+'-nested-stack.bin')).write_bytes(stack)
            assert row['saved_mmu']==0 and 0xc000<=interrupted_pc<0xff05,row
            self.monitor.resume()


def run_nested_irq(mon,work,report,desktop_loop):
    monitor=NestedMonitor(mon,work)
    report['nested_frames']=monitor.frames
    report['paused_capture_batches']=monitor.batches
    report['register_names']=monitor.register_names
    capture=NativeCapture(monitor,work,quiet=.1,kernel_prefix='native-desktop',batch=monitor.paused)
    report['captures']=capture.records
    # Since 5d04173 the desktop's VDC holds its bitmap scene at the owned base,
    # not 80-column text; derive base and pointer from the desktop's VDC state.
    symbol=lambda name:lst_symbol('native-desktop/desktop',name)
    state=bytes(mon.read_mem(symbol('vd_phase'),symbol('vd_phase')+6))
    point=bytes(mon.read_mem(symbol('vd_pointer_visible'),symbol('vd_pointer_visible')+3));mon.resume()
    assert state[:2]==b'\2\1' and state[3]==0,state.hex()
    scene=pointer_bitmap(vdc_bitmap(0),int.from_bytes(point[1:3],'little')*2,point[3],bool(point[0]))
    for label,mode,address,expected in (
        ('nested-ram',0,0xc7d0,surface()[0x7d0:0x9d0]),
        ('nested-vdc',1,state[5]*256,scene[:512]),
    ):
        before=monitor.reach(desktop_loop)
        assert mon.read_mem(0xff00,0xff00)==b'\x0e';mon.resume()
        monitor.forced=False
        actual=capture.capture(label,mode=mode,address=address,count=512)
        assert actual==expected and capture.records[-1]['foreground_mmu']==0
        assert capture.records[-1]['restored']
        after=monitor.reach(desktop_loop)
        assert after['SP']==before['SP'] and mon.read_mem(0xff00,0xff00)==b'\x0e'
        monitor.frames[-1].update(foreground_returned=True,foreground_before=before,
                                  foreground_after=after,exact_payload_sha256=hashlib.sha256(actual).hexdigest())
        # Restore the desktop's ordinary raster IRQ position before the next case.
        d011=mon.read_mem(0xd011,0xd011)[0]
        mon.write_mem(0xd011,bytes([d011&127]));mon.write_mem(0xd012,b'\xff');mon.resume()
        print(f'PASS: {label}; saved MMU 00, exact payload, both IRQ frames return to MMU 0e desktop',flush=True)
    report['nested_checks_passed']=True
