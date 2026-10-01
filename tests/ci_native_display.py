#!/usr/bin/env python3
"""Execute native VIC lifetime gates against owned heap records and port latches."""
import hashlib
import argparse
import json
from pathlib import Path
import sys
import ci_native_heap as heap

SHOW,CLOSE=0x1c68,0x1c6b
BaseBus=heap.Bus
class DisplayBus(BaseBus):
    def __init__(self):
        super().__init__()
        self.video={0xd011:0x1b,0xd012:255,0xd015:0,0xd016:0xc8,0xd018:0x15,
                    0xd01a:0xf1,0xdd00:0xc7,0xdd02:0x3f}
        self.ram[0][0:2]=bytes([0x2f,0x73]);self.ram[0][0xd8]=0
        self.writes=[];self.raster_high=0x80;self.compare=255
    def __getitem__(self,address):
        if not self.config&1 and address in self.video:
            return self.video[address]|self.raster_high if address==0xd011 else self.video[address]
        return super().__getitem__(address)
    def __setitem__(self,address,value):
        if not self.config&1 and address in self.video:
            self.writes.append((address,value))
            if address==0xd011:
                self.compare=(self.compare&255)|((value&128)<<1);value&=127
            elif address==0xd012:self.compare=(self.compare&256)|value
            self.video[address]=value;return
        return super().__setitem__(address,value)
heap.Bus=DisplayBus

class Client:
    def __init__(self,*,bank=0,page=0xc0,pages=36):
        self.m=heap.Machine();self.ram=self.m.ram;self.bus=self.m.bus
        app=self.m.alloc(4,0,32,page=0x60)
        at=heap.symbol('l_app_handle');self.ram[at:at+4]=app
        self.ram[0x3d6a]=4;self.ram[0x3d20]=32;self.ram[0x3d23]=2
        self.ram[0x3d3b]=0;self.surface=self.m.alloc(pages,bank,32,page=page)
        self.original=dict(self.bus.video),self.ram[1],self.ram[0xd8],self.bus.compare
    def show(self,**kwargs):self.m.select(self.surface,32);return self.m.invoke(SHOW,**kwargs)
    def close(self,**kwargs):return self.m.invoke(CLOSE,**kwargs)
    def active(self):
        assert self.ram[heap.symbol('v_tag')]==self.surface[0]
        assert self.ram[0xd8]==255 and self.ram[1]&6==4 and self.bus.compare==255
        assert self.bus.video[0xd011]==0x3b and self.bus.video[0xd018]==0x80
        assert self.bus.video[0xd016]&0x3f==8
        assert self.bus.video[0xdd00]&3==0
    def restored(self):
        assert not self.ram[heap.symbol('v_tag')]
        assert (self.bus.video,self.ram[1],self.ram[0xd8],self.bus.compare)==self.original
    def cleanup(self,expected=0,interrupt=None):
        self.ram[0xb20:0xb24]=b'\x08\x4c'+heap.symbol('app_cleanup').to_bytes(2,'little')
        self.ram[heap.symbol('l_result')]=0
        cpu=self.m.invoke(0xb20,expected=expected,check=False,interrupt=interrupt)
        assert (cpu.a,cpu.p&1)==(expected,bool(expected))
        assert self.ram[0x3d27]==expected
        return cpu

cases={}
for show_flags in (0,8):
    for close_flags in (0,4,8,12):
        c=Client();metadata=c.m.metadata();c.show(flags=show_flags);c.active()
        assert c.m.metadata()==metadata
        c.close(flags=close_flags);c.restored();assert c.m.metadata()==metadata
        writes=len(c.bus.writes);c.close();assert len(c.bus.writes)==writes
cases['show-close-preserve-status-and-allocation']=8

for bank,page,pages in ((1,0xc0,36),(0,0xbf,36),(0,0xc0,35),(0,0xc0,37)):
    c=Client(bank=bank,page=page,pages=pages);before=c.m.metadata()
    c.show(expected=6);c.restored();assert not c.bus.writes and c.m.metadata()==before
cases['wrong-bank-origin-or-extent']=4

for name,change,error in (
    ('interrupts-disabled',lambda c:None,8),
    ('vic-bank1',lambda c:c.bus.mmu.__setitem__(6,0x44),8),
    ('port-direction',lambda c:c.ram.__setitem__(0,0x2b),8),
    ('kernal-graphics-state',lambda c:c.ram.__setitem__(0xd8,1),8),
    ('raster-mask',lambda c:c.bus.video.__setitem__(0xd01a,0xf0),8),
    ('bitmap-already',lambda c:c.bus.video.__setitem__(0xd011,0x3b),8),
    ('extended-color',lambda c:c.bus.video.__setitem__(0xd011,0x5b),8),
    ('multicolor',lambda c:c.bus.video.__setitem__(0xd016,0xd8),8),
    ('active-sprites',lambda c:c.bus.video.__setitem__(0xd015,1),8),
    ('cia-bank-direction',lambda c:c.bus.video.__setitem__(0xdd02,0x3e),8),
    ('no-app',lambda c:c.ram.__setitem__(0x3d20,0),5),
    ('app-not-running',lambda c:c.ram.__setitem__(0x3d23,3),5),
    ('stale-app',lambda c:c.ram.__setitem__(heap.symbol('l_app_handle')+1,255),4),
    ('lost-app-page',lambda c:c.ram.__setitem__(0x3863,0),4),
    ('file-busy',lambda c:c.ram.__setitem__(0x3d91,1),7),
    ('ui-busy',lambda c:c.ram.__setitem__(0x3d3b,1),7),
):
    c=Client();change(c);before=c.m.metadata();registers=dict(c.bus.video),bytes(c.ram[:2]),c.ram[0xd8]
    c.show(expected=error,flags=4 if name=='interrupts-disabled' else 8)
    assert not c.bus.writes and not c.ram[heap.symbol('v_tag')]
    assert c.m.metadata()==before and (c.bus.video,bytes(c.ram[:2]),c.ram[0xd8])==registers
    cases[name]=True

c=Client();c.show();c.active();writes=len(c.bus.writes);c.show(expected=7);c.active()
assert len(c.bus.writes)==writes
for owner,handle,error in ((16,c.surface,5),(32,c.surface[:1]+b'\xff\xff\xff',4)):
    c.m.select(handle,owner);c.m.invoke('free',expected=error);c.active()
    assert len(c.bus.writes)==writes
c.m.select(c.surface,32);c.m.invoke('free');c.restored()
assert c.m.stats()==(171,251,31)
cases['double-presentation-stale-foreign-free-and-owned-free']=True

c=Client();c.show();foreign=c.m.alloc(1,1,16);c.m.set(heap.OWNER,16);c.m.invoke('release');c.active()
c.m.set(heap.OWNER,32);c.m.invoke('release');c.restored();assert c.m.stats()==(175,251,32)
cases['release-is-owner-scoped-and-restores-before-free']=True

c=Client();c.show();c.ram[0x38d0]=0;c.m.select(c.surface,32);c.m.invoke('free',expected=9);c.active()
c.close();c.restored();assert c.ram[0x3c00+(c.surface[0]-1)*8]==32
cases['corrupt-surface-close-restores-without-freeing']=True

c=Client();c.show();c.cleanup();c.restored()
assert c.m.stats()==(175,251,32) and c.ram[0x3d20]==0 and c.ram[0x3d23]==0
cases['app-cleanup-restores-and-releases']=True

c=Client();c.show();c.ram[0x38d0]=0;before=c.m.metadata();c.cleanup(expected=9);c.restored()
assert c.m.metadata()==before and c.ram[0x3d20]==32 and c.ram[0x3d23]==4
cases['app-corrupt-heap-retains-owner-with-text-restored']=True

c=Client();c.show();c.ram[0x3dc0]=32;before=c.m.metadata()
def file_failure(cpu,bus):
    if cpu.pc==heap.symbol('fs_release'):
        cpu.a=0x11;cpu.p|=1;cpu.pc=cpu.stPopWord()+1
c.cleanup(expected=0x11,interrupt=file_failure);c.restored()
assert c.m.metadata()==before and c.ram[0x3d20]==32 and c.ram[0x3d23]==4
cases['app-file-close-error-retains-memory-with-text-restored']=True

c=Client();c.show();c.ram[1]^=0x20;c.bus.video[0xdd00]^=0x10;c.close()
assert c.ram[1]==c.original[1]^0x20 and c.bus.video[0xdd00]==c.original[0][0xdd00]^0x10
cases['unrelated-port-output-changes-survive-close']=True

c=Client();c.bus.video[0xd011]=0x12;c.bus.video[0xd016]=0xc3
c.original=dict(c.bus.video),c.ram[1],c.ram[0xd8],c.bus.compare
c.show();c.active();c.close();c.restored()
cases['bitmap-geometry-normalized-and-original-text-geometry-restored']=True

c=Client();interrupts=[]
def irq(cpu,bus):
    if not cpu.p&4 and cpu.processorCycles%23==0:
        cpu.irq();interrupts.append(cpu.processorCycles)
c.show(flags=8,interrupt=irq);c.active()
c.m.set(heap.VALUE,0x5a);c.m.transfer('fill',0,512,flags=8,interrupt=irq)
assert c.bus.ram[0][0xc000:0xc200]==b'\x5a'*512
c.close(flags=8,interrupt=irq);c.restored();assert interrupts
cases['irqs-during-gates-and-banked-drawing']=len(interrupts)

result=dict(passed=True,hardware_io=False,kernel_sha256=hashlib.sha256(heap.IMAGE.read_bytes()).hexdigest(),
            cases=cases,case_groups=len(cases),heap_pages=426)
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--report',type=Path,default=heap.ROOT/'display-cpu.json')
output=parser.parse_args().report
output.write_text(json.dumps(result,indent=2)+'\n')
print(f'PASS: {len(cases)} native display lifetime groups; {len(interrupts)} IRQs during gate/fill calls')
