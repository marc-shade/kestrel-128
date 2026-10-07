#!/usr/bin/env python3
"""Run the loaded native Claude client through real NMI stubs and modeled chips."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ci_native_calc as calc
from ci_native_heap import Machine
from native_vdc_chip import VDC
from native_claude_check import landing_screen
from native_clipboard_check import released_stats


class LogicalVideo:
    """Observe logical addresses through the independent physical VDC model."""
    def __init__(self,chip):self.chip=chip
    def __len__(self):return 65536
    def __getitem__(self,key):
        if isinstance(key,slice):return bytes(self.chip.vread(i) for i in range(*key.indices(65536)))
        if key>=65536:raise IndexError(key)
        return self.chip.vread(key)


class TerminalBus(VDC):
    def __init__(self, parent, present=True, busy=False, tx=True, floating=False):
        self.parent = parent
        # No ACIA on a real bus: I/O1 reads return whatever the VIC last
        # fetched. This sequence starts with the pair VICE returned when the
        # Claude app wrongly reported a busy port (control $e0, command $ff).
        self.floating = [0xe0, 0xff, 0x01, 0x16, 0x20, 0x7e] if floating else None
        self.video = bytearray((i*31+i//256+19)&255 for i in range(65536))
        self.reg = bytearray(64)
        self.reg[1], self.reg[6], self.reg[9], self.reg[28] = 80, 25, 7, 32
        self.reg[10], self.reg[11], self.reg[20], self.reg[25] = 0x20, 7, 8, 0x47
        self.selected, self.busy, self.ready, self.present = 0, 0, False, True
        self.command, self.control = (9 if busy else 2), 0x1e
        self.serial_present, self.tx = present, tx
        self.input = None
        self.sent, self.serial_writes = bytearray(), []
        self.sid = bytearray(25)
        self.last_data = 0
        self.port = {0xd020: 6, 0xdd0d: 0}
        self.colors = bytearray(1024)  # Color RAM is separate from bitmap RAM.
        self.physical_vdc=parent if hasattr(parent,'video_ram') else None
        if self.physical_vdc is not None:
            self.video=LogicalVideo(parent)
            self.reg=parent.reg
        self.saved_video, self.saved_regs = bytes(self.video), bytes(self.reg)

    @property
    def config(self): return self.parent.config

    def __getattr__(self, name): return getattr(self.parent, name)

    def __getitem__(self, address):
        if self.config&1: return self.parent[address]
        if address in (0xd600, 0xd601):
            if self.physical_vdc is not None:return self.parent[address]
            return super().__getitem__(address)
        if 0xd800 <= address < 0xdc00:return self.colors[address-0xd800]&15
        if address in self.port: return self.port[address]
        if 0xde00 <= address <= 0xde03:
            if not self.serial_present:
                if self.floating:
                    self.floating.append(self.floating.pop(0))
                    return self.floating[-1]
                return 255
            if address == 0xde00:
                result, self.input = self.input, None
                return 0 if result is None else result
            if address == 0xde01:
                return (0x10 if self.tx else 0) | (0x88 if self.input is not None else 0)
            if address == 0xde02: return self.command
            return self.control
        return self.parent[address]

    def __setitem__(self, address, value):
        if self.config&1: return self.parent.__setitem__(address, value)
        if address in (0xd600,0xd601) and self.physical_vdc is not None:
            return self.parent.__setitem__(address,value)
        if address == 0xd600: return super().__setitem__(address, value)
        if address == 0xd601:
            if self.selected == 31: self.last_data = value
            if self.selected == 30:
                assert self.ready, 'block command before ready'
                dest = self.reg[18]<<8 | self.reg[19]
                source = self.reg[32]<<8 | self.reg[33]
                count = value or 256
                for i in range(count):
                    self.video[(dest+i)&65535] = self.video[(source+i)&65535] if self.reg[24]&128 else self.last_data
                self.advance((dest+count-1)&65535)
                if self.reg[24]&128:
                    source = (source+count)&65535
                    self.reg[32], self.reg[33] = source>>8, source&255
            return super().__setitem__(address, value)
        if address in self.port: self.port[address] = value; return
        if 0xd800 <= address < 0xdc00:
            self.colors[address-0xd800] = value&15; return
        if 0xd400 <= address <= 0xd418:        # SID: write-only registers
            self.sid[address-0xd400] = value; return
        if 0xde00 <= address <= 0xde03:
            self.serial_writes.append((address, value))
            if not self.serial_present: return
            if address == 0xde00: self.sent.append(value)
            elif address == 0xde02: self.command = value
            elif address == 0xde03: self.control = value
            else: raise AssertionError('unexpected ACIA reset')
            return
        return self.parent.__setitem__(address, value)


class TerminalMachine(Machine):
    options = {}

    def __init__(self):
        super().__init__()
        self.bus = TerminalBus(self.bus, **self.options)


class Client(calc.Calculator):
    instruction_limit = 5000000

    def __init__(self, **options):
        provider=options.pop('vdc_component',False)
        TerminalMachine.options = options
        calc.Machine = TerminalMachine
        self.labels = {m[2]: int(m[1],16) for m in re.finditer(r'^al ([0-9A-Fa-f]+) \.(\S+)',
                       (ROOT/'target/native-desktop/claude.lbl').read_text(), re.M)}
        self.borrowed = None
        super().__init__('claude', loader_name=b'CLAUDE', image_prefix='native-desktop',vdc_component=provider)
        self.chip = self.m.bus

    def symbol(self, name): return self.labels[name]

    def loop(self, exited=False):
        cpu = self.cpu
        # Loading, checking, unpacking and drawing the larger graphical app
        # exceed the former five-million-instruction startup allowance.
        limit=max(10000000,self.instruction_limit) if self.borrowed is None else self.instruction_limit
        for steps in range(limit):
            if cpu.pc == self.symbol('native_entry') and self.borrowed is None:
                self.borrowed = dict(zp=bytes(self.ram[2:28]), vector=bytes(self.ram[0x318:0x31a]),
                                     gate=bytes(self.ram[0x3d3e:0x3d40]), screen=self.ram[0xd7],
                                     keys=bytes(self.ram[0x1000:0x1100]))
            if cpu.pc == 0xb00 and cpu.sp == 0xe0:
                assert exited, 'unexpected app exit'
                assert self.m.stats() == released_stats(self.m) and not self.io.handles
                assert self.ram[0x3d20] == 0 and self.ram[0x3d23] == 0
                self.check_restored()
                self.instructions+=steps
                return
            if cpu.pc == 0xffe4 and not self.keys and not exited:
                assert self.ram[0x3d12] == 1
                assert self.ram[0x1000:0x1014] == bytes([1]*10+[0x85,0x89,0x86,0x8a,0x87,0x8b,0x88,0x8c,0x83,0x84])
                self.instructions+=steps
                return
            if self.io.stub(cpu): continue
            if cpu.pc == 0xffe4:
                cpu.a = self.keys.pop(0) if self.keys else 0; cpu.FlagsNZ(cpu.a)
                cpu.pc = (cpu.stPopWord()+1)&65535
            elif cpu.pc == 0xff5f:
                self.ram[0xd7] ^= 128; cpu.pc = (cpu.stPopWord()+1)&65535
            elif cpu.pc == 0xffd2:
                assert cpu.a == 0x93
                self.ram[0x400:0x7e8] = b' '*1000
                cpu.pc = (cpu.stPopWord()+1)&65535
            else:
                assert not (self.m.bus.config == 0 and 0x6000 <= cpu.pc < 0xc000), 'NMI entered app with BASIC mapped'
                cpu.step()
        raise AssertionError(f'client stalled at {cpu.pc:04x}')

    def key(self, value, exited=False):
        self.keys.append(value); self.loop(exited)
        self.events += 1
        assert int.from_bytes(self.ram[0x3d13:0x3d15], 'little') == self.events

    def nmi(self, value=None, mapping=None):
        cpu = self.cpu
        if mapping is not None: self.m.bus[0xff00] = mapping
        self.m.bus.input = value
        saved = (cpu.pc, cpu.sp, cpu.a, cpu.x, cpu.y, cpu.p, self.m.bus.config)
        cpu.nmi()
        for _ in range(200):
            assert not (self.m.bus.config == 0 and 0x6000 <= cpu.pc < 0xc000), 'missing bank mapping bridge'
            cpu.step()
            if (cpu.pc, cpu.sp) == saved[:2]: break
        else: raise AssertionError('NMI did not restore interrupted foreground')
        assert (cpu.pc, cpu.sp, cpu.a, cpu.x, cpu.y, cpu.p, self.m.bus.config) == saved
        if mapping is not None: self.m.bus[0xff00] = 0x0e

    def feed(self, data, exited=False):
        for start in range(0, len(data), 64):
            for value in data[start:start+64]: self.nmi(value)
            # Complete the zero-key GETIN where the harness paused, then let
            # the foreground drain the interrupt ring through the real parser.
            self.cpu.a = 0; self.cpu.FlagsNZ(0)
            self.cpu.pc = (self.cpu.stPopWord()+1)&65535
            self.loop(exited and start+64 >= len(data))

    def close(self):
        self.key(0x8c)
        assert self.chip.command == 9 and self.ram[self.symbol('_closeOutcome')] == 1
        self.feed(bytes([9, 0x5a]), exited=True)
        assert self.ram[self.symbol('_closeOutcome')] == 2

    def check_restored(self):
        assert bytes(self.ram[0x1000:0x1100]) == self.borrowed['keys'], 'ROM programmable keys leaked'
        assert bytes(self.ram[2:28]) == self.borrowed['zp'], 'cc65 zero page leaked'
        assert bytes(self.ram[0x318:0x31a]) == self.borrowed['vector'], 'dangling NMI vector'
        assert bytes(self.ram[0x3d3e:0x3d40]) == self.borrowed['gate'], 'NMI mapping pointer leaked'
        assert self.ram[0xd7] == self.borrowed['screen']
        b = self.m.bus
        assert b.video[0x3000:0x4000] == b.saved_video[0x3000:0x4000], 'font leaked'
        for reg in (10,11,12,13,14,15,20,21,24,25,26,27,28,29,32,33,18,19):
            assert b.reg[reg] == b.saved_regs[reg], ('VDC mode leaked', reg)
        assert b.port[0xd020] == 6


def run():
    cases = []
    for key in (27, 0x8c):
        c = Client(); assert not c.chip.serial_writes
        assert c.ram[0x400:0x7e8] == landing_screen(40) and c.chip.video[:2000] == landing_screen(80)
        c.key(key, exited=True)
    cases.append('landing and cancel avoid serial writes and restore all borrowed state')
    for opts in ({'present':False}, {'busy':True}, {'present':False,'floating':True}):
        c = Client(**opts); c.key(13)
        assert not c.chip.serial_writes
        c.key(0x8c, exited=True)
    cases.append('absent, floating and already active serial ports remain untouched')
    c = Client(); c.key(13)
    assert c.chip.sent == b'\0\1' and c.ram[0x318:0x31a] == b'\xf0\x1b'
    for mapping in (0, 0x0e, 0x3f, 0x7f): c.nmi(5, mapping)
    c.key(27); assert c.chip.sent[-1] == 27
    c.key(0x84); assert c.chip.sent[-2:] == b'\0\1'
    c.close()
    assert c.chip.sent[-2:] == b'\0\2' and (c.chip.command,c.chip.control) == (2,0x1e)
    cases.append('ROM NMI entry restores four MMU maps and all CPU registers; native keys and local exit')
    c = Client(); c.key(13)
    c.feed(bytes([1,14, 2,2,3,0x4f,4, 1,2,3,4, 3,4,77,2,10,65, 5]))
    chars = bytearray(b' '*2000); attrs = bytearray([0x8e]*2000)
    chars[163:167] = bytes([1,2,3,4]); attrs[163:167] = bytes([0xcf]*4)
    chars[397:400] = b'A'*3; attrs[397:400] = bytes([0x82]*3)
    assert c.chip.video[:2000] == chars and c.chip.video[0x800:0xfd0] == attrs
    snapshot = bytes(c.chip.video)
    for row,col in ((25,0),(255,255),(0,80)):
        c.feed(bytes([2,row,col,14,3,1,2,3, 3,row,col,14,255,32, 5]))
    assert c.chip.video == snapshot
    c.feed(bytes([10,0xff])+bytes(range(8))+bytes([4,24,79,5]))
    assert c.chip.video[0x3ff0:0x4000] == bytes(range(8))+bytes(8)
    assert c.chip.reg[14:16] == b'\x07\xcf' and c.chip.reg[10] == 0x60
    c.feed(bytes([4,255,255,5])); assert c.chip.reg[10] == 0x20
    c.feed(bytes([6,5])); assert c.value('_bellCount') == 1
    c.close()
    cases.append('complete render planes, clipped and rejected spans, glyphs, cursor and visual bell restoration')
    c = Client(); c.key(13); c.feed(bytes([1,14,5]))
    for row in range(25): c.feed(bytes([3,row,0,row&15,80,row+32,5]))
    for top,bot,n in ((0,24,1),(3,20,0x82),(0,24,24),(4,7,0x81)):
        before = bytes(c.chip.video)
        c.feed(bytes([11,top,bot,n,5]))
        shift = n&127
        for plane in (0,0x800):
            expected = bytearray(before[plane:plane+2000])
            for row in range(top,bot+1):
                source = row-shift if n&128 else row+shift
                if top<=source<=bot: expected[row*80:(row+1)*80] = before[plane+source*80:plane+(source+1)*80]
            assert c.chip.video[plane:plane+2000] == expected
    c.feed(bytes([9,0x5a]), exited=True)
    cases.append('bidirectional scroll regions match whole planes and host BYE closes cleanly')
    c = Client(); c.key(13)
    c.feed(bytes([2,0,0,14,80])+b'A'*10)
    c.key(0x8c)
    assert c.chip.command == 9 and c.ram[c.symbol('_closeOutcome')] == 1
    # A BYE-shaped pair inside a pending RUN is screen content, not an ack.
    c.feed(bytes([9,0x5a])+b'B'*68)
    assert c.chip.command == 9 and c.ram[c.symbol('_closeOutcome')] == 1
    assert c.chip.sent[-2:] == b'\0\3', 'closing client stopped returning credits'
    c.feed(bytes([9,0x5a]), exited=True)
    assert c.ram[c.symbol('_closeOutcome')] == 2
    cases.append('F8 retains the port, parses pending payload and returns credits until an in-stream BYE ack')
    c = Client(); c.key(13); c.key(0x8c)
    for i in range(6):
        c.ram[0xa2] = (c.ram[0xa2]+200)&255
        c.feed(b'\5', exited=i==5)
    assert c.ram[c.symbol('_closeOutcome')] == 3
    cases.append('missing host acknowledgement times out across jiffy wrap and restores the app')
    c = Client(); c.key(13); c.key(0x8c)
    c.instruction_limit = 15000000
    c.loop(exited=True)
    assert c.ram[c.symbol('_closeOutcome')] == 3
    cases.append('a stopped KERNAL clock reaches the finite polling fallback and restores the app')
    c = Client(); c.key(13); c.key(0x8c); c.key(0x8c, exited=True)
    assert c.ram[c.symbol('_closeOutcome')] == 4
    cases.append('a second F8 exits immediately while awaiting shutdown acknowledgement')
    c = Client(); c.key(13); c.nmi()
    c.cpu.a = 0; c.cpu.FlagsNZ(0); c.cpu.pc = (c.cpu.stPopWord()+1)&65535
    c.loop(exited=True)
    cases.append('RESTORE/non-serial NMI takes foreground teardown')
    c = Client(tx=False); c.key(13, exited=True)
    assert not c.chip.sent and (c.chip.command,c.chip.control) == (2,0x1e)
    cases.append('transmitter timeout is bounded and restores ownership')
    return cases


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--report', type=Path, required=True); a = p.parse_args()
    result = dict(passed=False, physical_hardware_io=False,
        claude_sha256=hashlib.sha256((ROOT/'target/native-desktop/claude.prg').read_bytes()).hexdigest())
    try:
        result['cases'] = run(); result['passed'] = True
        print('PASS:',len(result['cases']),'native Claude workflows')
    except BaseException as exc:
        result['error'] = repr(exc); raise
    finally: a.report.write_text(json.dumps(result,indent=2)+'\n')
