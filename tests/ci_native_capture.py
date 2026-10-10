#!/usr/bin/env python3
"""Check the native observer through a complete native ROM IRQ frame."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from py65.devices.mpu6502 import MPU
from ci_native_heap import Bus, ROOT
from native_vdc_chip import CaptureBus
from native_capture import NativeCapture, ObservationChanged
from native_vdc_check import capture_frame
from native_vdc_scene import bitmap, attributes, pointer_bitmap


class NativeCaptureBus(Bus):
    def __init__(self, fault=None, present=True):
        super().__init__()
        self.vdc = CaptureBus(fault,present)

    def __getitem__(self,address):
        if address in (0xd600,0xd601) and not self.config & 1:
            return self.vdc[address]
        return super().__getitem__(address)

    def __setitem__(self,address,value):
        if address in (0xd600,0xd601) and not self.config & 1:
            self.vdc[address]=value
        else:
            super().__setitem__(address,value)


def check(prg,mode,bank,start,count,fault=None,present=True,interrupted_mmu=0x0e):
    bus=NativeCaptureBus(fault,present); ram=bus.ram[0]
    ram[0x3e00:0x3e00+len(prg)-2]=prg[2:]
    ram[0x3fee:0x3ffb]=b'\0\0\0\x0b\0'+bytes([mode,bank])+start.to_bytes(2,'little')+count.to_bytes(2,'little')+b'\0\0'
    ram[0x3ffe:0x4000]=b'\0\0'
    ram[0x3d12]=1
    ram[0x314:0x316]=b'\0\x3e'
    ram[0xfb:0xff]=b'\x63\x98\x15\xa7'
    bus.vdc.video[:2000]=bytes((i*73+i//251)&255 for i in range(2000))
    bus.vdc.reg[18:20]=b'\x23\x47'
    expected=bytes(bus.vdc.video[:2000] if mode else bus.ram[bank][start:start+count]) if bank<2 else b''
    before=bytes(ram[0x1300:0x3a00]),bytes(ram[0x3c00:0x3e00]),bytes(ram[0x3a00:0x3c00])
    bus.config=interrupted_mmu
    cpu=MPU(memory=bus,pc=0x2500); cpu.sp=0xc0
    cpu.a,cpu.x,cpu.y,cpu.p=0x5a,0x6d,0x90,0x28
    cpu.irq()
    held=None
    for steps in range(2000000):
        if cpu.pc==0x2500:break
        if ram[0x3ff2] and held is None:
            held=steps                       # status written: the probe now holds
            for _ in range(5000):cpu.step()
            assert 0x3e00<=cpu.pc<0x3fee and ram[0x314:0x316]==b'\0\x3e','held until released'
            ram[0x3ffe]=1
        cpu.step()
    else:raise AssertionError('Native IRQ capture failed to return')
    assert held is not None and ram[0x3fff]==0 and ram[0x3fee]==0
    assert (cpu.a,cpu.x,cpu.y,cpu.sp,cpu.p&0xcf)==(0x5a,0x6d,0x90,0xc0,8)
    assert bus.config==interrupted_mmu and ram[0x314:0x316]==b'\0\x0b'
    assert ram[0x3ffb:0x3ffe]==bytes([0xb7,4,interrupted_mmu])
    assert ram[0xfb:0xff]==b'\x63\x98\x15\xa7' and ram[0x2aa]==0xbb
    assert bytes(ram[0x1300:0x3a00])==before[0] and bytes(ram[0x3c00:0x3e00])==before[1]
    result=ram[0x3ff2]; resyncs=int.from_bytes(ram[0x3ff9:0x3ffb],'little')
    if mode>1 or bank>1 or not 1<=count<=512:
        assert result==4 and bytes(ram[0x3a00:0x3c00])==before[2]
    elif mode and not present:assert result==2
    elif mode and fault=='always':assert result==3 and resyncs==3
    else:
        assert result==1 and ram[0x3a00:0x3a00+count]==expected[:count]
        assert ram[0x3a00+count:0x3c00]==before[2][count:]
    if mode==1 and present and 1<=count<=512:
        assert bus.vdc.reg[18:20]==b'\x23\x47'
    assert not bus.far_writes and ram[0xb10]==1
    return dict(code=result,address_resyncs=resyncs,instructions=steps)


def busy(prg,why):
    """An IRQ that finds the foreground away from its input wait, in another
    map or with another common RAM setting passes through untouched."""
    bus=NativeCaptureBus(); ram=bus.ram[0]
    ram[0x3e00:0x3e00+len(prg)-2]=prg[2:]
    ram[0x3fee:0x3ffb]=b'\0\0\0\x0b\0\0\0\0\x40\0\2\0\0'
    ram[0x3ffe:0x4000]=b'\0\0'
    ram[0x3d12]=0 if why=='not-ready' else 1
    if why=='common':bus.mmu[6]=7
    if why=='mode':bus.mmu[5]|=0x40
    interrupted={'bank-1-map':0x7f,'all-ram-map':0x3f}.get(why,0x0e)
    ram[0x314:0x316]=b'\0\x3e'
    ram[0xfb:0xff]=b'\x63\x98\x15\xa7'
    before=bytes(ram[0x1300:0x3fee])
    bus.config=interrupted
    cpu=MPU(memory=bus,pc=0x2500); cpu.sp=0xc0
    cpu.a,cpu.x,cpu.y,cpu.p=0x5a,0x6d,0x90,0x28
    cpu.irq()
    for steps in range(200000):
        if cpu.pc==0x2500:break
        cpu.step()
    else:raise AssertionError('busy IRQ did not return')
    assert (cpu.a,cpu.x,cpu.y,cpu.sp,cpu.p&0xcf)==(0x5a,0x6d,0x90,0xc0,8)
    assert bus.config==interrupted and ram[0xb10]==1 and ram[0xfb:0xff]==b'\x63\x98\x15\xa7'
    assert ram[0x314:0x316]==b'\0\x3e','the hook stays armed'
    assert ram[0x3fee]==1 and ram[0x3ff2]==0 and ram[0x3fff]==0
    assert bytes(ram[0x1300:0x3fee])==before and not bus.far_writes
    return dict(skipped=True,instructions=steps)


def unreleased(prg):
    """A host that never releases: the hold gives up, flags it and returns."""
    bus=NativeCaptureBus(); ram=bus.ram[0]
    ram[0x3e00:0x3e00+len(prg)-2]=prg[2:]
    ram[0x3fee:0x3ffb]=b'\0\0\0\x0b\0\0\0\0\x40\x10\0\0\0'
    ram[0x3ffe:0x4000]=b'\0\0'
    ram[0x3d12]=1
    ram[0x314:0x316]=b'\0\x3e'
    cpu=MPU(memory=bus,pc=0x2500); cpu.sp=0xc0; cpu.p=0x20
    cpu.irq()
    for steps in range(2000000):
        if cpu.pc==0x2500:break
        cpu.step()
    else:raise AssertionError('an unreleased hold did not give up')
    assert ram[0x3ff2]==1 and ram[0x3fff]==1 and ram[0x314:0x316]==b'\0\x0b'
    assert bytes(ram[0x3a00:0x3a10])==bytes(bus.ram[0][0x4000:0x4010])
    return dict(gave_up=True,instructions=steps)


class CaptureMonitor:
    """Run the actual IRQ probe when the host installs its vector."""
    def __init__(self,fail_chunk=None):
        self.bus=NativeCaptureBus();self.ram=self.bus.ram[0]
        self.ram[0x3d11:0x3d13]=b'\0\1';self.ram[0xd0]=0
        self.bus.vdc.video[:2000]=bytes((i*73+i//251)&255 for i in range(2000))
        self.chunks=0;self.fail_chunk=fail_chunk;self.cpu=None

    def read_mem(self,start,end):return bytes(self.ram[start:end+1])
    def write_mem(self,start,data):self.ram[start:start+len(data)]=data
    def resume(self):
        # One IRQ per resume; a probe that holds keeps the CPU here until the
        # host has written its release and resumes again.
        if self.cpu is None:
            if self.ram[0x314:0x316]!=b'\0\x3e':return
            self.chunks+=1
            if self.chunks==self.fail_chunk:self.bus.vdc.fault='always'
            self.cpu=MPU(memory=self.bus,pc=0x2500);self.cpu.sp=0xc0;self.cpu.p=0x20
            self.cpu.irq()
        cpu=self.cpu
        for _ in range(200000):
            if cpu.pc==0x2500:
                self.cpu=None;return
            if self.ram[0x3ff2] and not self.ram[0x3ffe] and 0x3e00<=cpu.pc<0x3fee:
                return
            cpu.step()
        raise AssertionError('host capture IRQ did not return')


def host_cases(folder):
    cases={}
    for mode,bank,start in ((0,0,0x1300),(0,0,0xcf80),(0,1,0x3800),(1,0,0)):
        mon=CaptureMonitor();capture=NativeCapture(mon,folder,quiet=0)
        expected=bytes(mon.bus.vdc.video[:2000] if mode else mon.bus.ram[bank][start:start+2000])
        before=bytes(mon.ram[0x1300:0x1c00]),bytes(mon.ram[0x3800:0x4000])
        label=f'host-{mode}-{bank}-{start:04x}'
        assert capture.capture(label,mode=mode,bank=bank,address=start)==expected
        assert before==(bytes(mon.ram[0x1300:0x1c00]),bytes(mon.ram[0x3800:0x4000]))
        assert mon.chunks==4 and [c['count'] for c in capture.records[0]['chunks']]==[512,512,512,464]
        assert capture.records[0]['restored'];cases[label]=capture.records[0]
    mon=CaptureMonitor(fail_chunk=3);capture=NativeCapture(mon,folder,quiet=0)
    before=bytes(mon.ram[0x1300:0x1c00]),bytes(mon.ram[0x3800:0x4000])
    try:capture.capture('failed-third-chunk',mode=1)
    except AssertionError:pass
    else:raise AssertionError('persistent VDC fault was accepted')
    assert before==(bytes(mon.ram[0x1300:0x1c00]),bytes(mon.ram[0x3800:0x4000]))
    assert mon.chunks==3 and capture.records[0]['restored'] and capture.records[0]['code']==3
    cases['host-fault-restores-all']=capture.records[0]
    for start,count in ((0x3900,512),(0x3a00,1),(0x3df0,32),(0x3fff,1),(0xffff,2)):
        mon=CaptureMonitor();capture=NativeCapture(mon,folder,quiet=0)
        before=bytes(mon.ram)
        try:capture.capture('bad-source',address=start,count=count)
        except AssertionError:pass
        else:raise AssertionError('overlapping/wrapped capture source accepted')
        assert before==bytes(mon.ram) and mon.chunks==0
        cases[f'host-guard-{start:04x}']=dict(no_writes=True)
    mon=CaptureMonitor();mon.ram[0x3d91]=1;capture=NativeCapture(mon,folder,quiet=0)
    before=bytes(mon.ram)
    try:capture.capture('active-file-operation',mode=1)
    except AssertionError:pass
    else:raise AssertionError('borrowed the active file-service buffer')
    assert before==bytes(mon.ram) and mon.chunks==0
    cases['host-active-file-buffer']=dict(no_writes=True)
    # An app redraw while the observer borrows N_BUFFER is reported with the
    # changed addresses, after the borrowed bytes are restored.
    mon=CaptureMonitor();capture=NativeCapture(mon,folder,quiet=0)
    write=capture.write
    def restore(start,data):
        write(start,data)
        if start==0x3e00 and len(data)==512:mon.ram[0x3a1a]^=1  # scratch restored: app runs
    capture.write=restore
    try:capture.capture('pointer-redraw',mode=1)
    except ObservationChanged as changed:assert set(changed.changes)=={0x3a1a},changed.changes
    else:raise AssertionError('a change during observation was accepted')
    assert capture.records[0]['restored'] is not True
    cases['host-redraw-reported']=dict(changes=[0x3a1a])
    cases.update(frame_cases(folder))
    return cases


class FrameCapture:
    """Observer stand-in for capture_frame: one 64 KiB VDC desktop frame."""
    def __init__(self,failures):
        self.failures=dict(failures);self.point=bytes([1,80,0,100])
        self.bitmap=pointer_bitmap(bitmap(0),160,100,True)
    def capture(self,label,mode=0,bank=0,address=0,count=2000):
        if label.endswith('-vdc-state'):return bytes([2,1,1,0,0,0x40,72])
        if label in self.failures:raise ObservationChanged(label,self.failures.pop(label))
        if label.endswith(('-pointer-before','-pointer-after')):return self.point
        if address>=0x8000:return attributes(0)[address-0x8000:address-0x8000+count]
        return self.bitmap[address-0x4000:address-0x4000+count]


def frame_cases(folder):
    cases={}
    # A pointer redraw during a frame (argument or status pointer bytes only)
    # retakes that attempt; any other change still fails the frame.
    for name,changes in (('status',[0x3a1a]),('arguments',[0x3a07,0x3a0a,0x3a1c])):
        fake=FrameCapture({'redraw-pointer-after':changes})
        result=capture_frame(fake,None,None,folder,'redraw',0)
        assert result['pointer_moves']==[dict(attempt=0,redraw_during_capture=sorted(changes))],result
        cases[f'frame-retakes-pointer-redraw-{name}']=result['pointer_moves']
    for changes in ([0x3d2f],[0x3a1a,0x3a00],[]):
        fake=FrameCapture({'other-vdc-bitmap-07d0':changes})
        try:capture_frame(fake,None,None,folder,'other',0)
        except ObservationChanged:pass
        else:raise AssertionError(('change outside the pointer bytes was retaken',changes))
    cases['frame-other-changes-fail']=dict(rejected=3)
    return cases


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path);args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='kestrel-native-capture-') as folder:
        output=Path(folder)/'probe.prg'
        subprocess.run(['64tass','-a',str(ROOT/'probes/native-read.asm'),'-o',str(output)],check=True,capture_output=True)
        prg=output.read_bytes()
    assert prg[:2]==b'\0\x3e' and len(prg)-2<=0x1f0
    with tempfile.TemporaryDirectory(prefix='kestrel-native-capture-hold-') as folder:
        short=Path(folder)/'probe-short-hold.prg'
        subprocess.run(['64tass','-a','-D','HOLD_PAGES=1',str(ROOT/'probes/native-read.asm'),'-o',str(short)],
                       check=True,capture_output=True)
        short=short.read_bytes()
    cases={}
    for why in ('not-ready','bank-1-map','all-ram-map','common','mode'):
        cases['busy-'+why]=busy(prg,why)
    cases['hold-gives-up']=unreleased(short)
    for bank in (0,1):
        for start,count in ((0x1300,512),(0x4000,512),(0xcf80,512),(0xe000,512),(0xfef0,16)):
            cases[f'ram-{bank}-{start:04x}']=check(prg,0,bank,start,count)
    for label,fault,present in [('normal',None,True),('first',0,True),('page-boundary',255,True),
                                ('last',511,True),('persistent','always',True),('absent',None,False)]:
        cases['vdc-'+label]=check(prg,1,0,0,512,fault,present)
    for mode,bank,count in ((2,0,1),(0,2,1),(0,0,0),(0,0,513),(0,0,65535)):
        cases[f'bad-{mode}-{bank}-{count}']=check(prg,mode,bank,0x4000,count)
    for bank in (0,1):
        for start,count in ((0x1300,512),(0x4000,512),(0xcf80,512),(0xe000,512),(0xfef0,16)):
            cases[f'rom-mapping-ram-{bank}-{start:04x}']=check(prg,0,bank,start,count,interrupted_mmu=0)
    for label,fault,present in [('normal',None,True),('first',0,True),('page-boundary',255,True),
                               ('last',511,True),('persistent','always',True),('absent',None,False)]:
        cases['rom-mapping-vdc-'+label]=check(prg,1,0,0,512,fault,present,interrupted_mmu=0)
    with tempfile.TemporaryDirectory(prefix='kestrel-native-capture-host-') as folder:
        cases.update(host_cases(Path(folder)))
    report=dict(passed=True,probe_sha256=hashlib.sha256(prg).hexdigest(),cases=cases)
    if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(f'PASS: {len(cases)} native IRQ bank/VDC captures, faults, guards and complete frame restoration',flush=True)


if __name__=='__main__':main()
