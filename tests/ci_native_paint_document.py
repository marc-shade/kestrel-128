#!/usr/bin/env python3
"""Assembled banked Paint document, cell colors, stroke undo and ownership."""
import argparse
import hashlib
import json
from pathlib import Path
import random

from ci_native_calc import Calculator
from ci_native_pointer import Pointer
from py65.devices.mpu6502 import MPU


class Paint(Calculator):
    instruction_limit=18000000
    allow_busy_poll=True
    position=Pointer.position
    frame=Pointer.frame
    poll=Pointer.poll
    move=Pointer.move
    restored=Pointer.restored

    def __init__(self,**kwargs):
        super().__init__('paint',image_prefix='native-desktop',**kwargs)
        self.bus=self.m.bus;self.frames=0

    def key(self,key,exited=False):
        self.observation_target=None
        self.keys.append(key);self.loop(exited);self.events+=1
        assert int.from_bytes(self.ram[0x3d13:0x3d15],'little')==self.events
        if not exited:assert self.cpu.pc==0xffe4 and self.ram[0x3d12]==1

    def close(self):
        if self.value('pd_dirty'):
            self.key(27);assert self.value('pa_mode')==1
            self.key(ord('D'),exited=True)
        else:self.key(27,exited=True)

    def call(self,name,*,expected=0):
        stack=bytes(self.ram[0x100:0x200])
        try:
            cpu=MPU(memory=self.m.bus,pc=self.symbol(name));cpu.sp=0xe0;cpu.p=0x20
            cpu.stPushWord(0xaff)
            for steps in range(8000000):
                if cpu.pc==0xb00 and cpu.sp==0xe0:break
                cpu.step()
            else:raise AssertionError((name,'document call did not finish',hex(cpu.pc)))
            assert self.m.bus.config==0x0e and cpu.p&0x0c==0
            assert (cpu.a,bool(cpu.p&1))==(expected,bool(expected)),(name,cpu.a,cpu.p)
        finally:self.ram[0x100:0x200]=stack

    def set(self,name,value,size=1):
        at=self.symbol(name);self.ram[at:at+size]=value.to_bytes(size,'little')

    def document(self,slot=0):
        tag=self.ram[self.symbol('pd_handles')+slot*4]
        record=0x3c00+(tag-1)*8
        owner,bank,page,pages=self.ram[record:record+4]
        assert owner==32 and bank==1 and pages==36
        return bytes(self.m.bus.ram[bank][page*256:(page+pages)*256])

    def point(self,x,y,pen=1,color=1,expected=0):
        self.set('pd_x',x,2);self.set('pd_y',y);self.set('pd_pen',pen);self.set('pd_color',color)
        self.call('pd_point',expected=expected)

    def line(self,start,end,pen=1,color=1,expected=0):
        self.set('pd_x',start[0],2);self.set('pd_y',start[1])
        self.set('pd_end_x',end[0],2);self.set('pd_end_y',end[1])
        self.set('pd_pen',pen);self.set('pd_color',color)
        self.call('pd_line',expected=expected)


def segment(start,end):
    """Integer nearest-pixel oracle, resolving exact halves toward the start."""
    x,y=start;xx,yy=end;dx=abs(xx-x);dy=abs(yy-y)
    sx=1 if xx>=x else -1;sy=1 if yy>=y else -1
    if dx==dy==0:return [start]
    if dx>=dy:return [(x+sx*i,y+sy*((2*i*dy+dx-1)//(2*dx))) for i in range(dx+1)]
    return [(x+sx*((2*i*dx+dy-1)//(2*dy)),y+sy*i) for i in range(dy+1)]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True);args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    report=dict(passed=False,scope='document engine; application interface is still being implemented',cases=[],
        images={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
                (root/'target/native-desktop/paint.prg',root/'target/native/kestrel.prg')})
    def done(name):report['cases'].append(name);print('PASS:',name,flush=True)
    try:
        p=Paint();blank=bytes(8192)+b'\x10'*1024
        assert p.document()==blank and not p.value('pd_dirty') and not p.value('pd_undo_valid')
        p.call('pd_undo');assert p.document()==blank;done('blank full-resolution image, separate owned blocks and empty undo')
        wanted=bytearray(blank);previous=blank;dirty=0
        rng=random.Random(128)
        for stroke in range(6):
            p.set('pd_stroke',0);before=bytes(wanted);before_dirty=dirty
            points=[(0,0),(319,199),(255,7),(256,8),(7,192),(8,199)]
            points += [(rng.randrange(320),rng.randrange(200)) for _ in range(16)]
            for index,(x,y) in enumerate(points):
                color=(stroke+index)%16;pen=int(stroke%3!=2)
                old=bytes(wanted);at=y//8*320+x//8*8+y%8;mask=128>>(x%8)
                if pen:
                    wanted[at]|=mask;wanted[8192+y//8*40+x//8]=color*16+(wanted[8192+y//8*40+x//8]&15)
                else:wanted[at]&=255^mask
                p.point(x,y,pen,color)
                assert p.document()==wanted,(stroke,index,x,y)
                assert p.value('pd_changed')==int(old!=wanted)
                dirty|=int(old!=wanted)
                assert p.value('pd_dirty')==dirty
            if before!=wanted:
                assert p.document(1)==before
                current=bytes(wanted);p.call('pd_undo');assert p.document()==before and p.value('pd_dirty')==before_dirty
                p.call('pd_undo');assert p.document()==current and p.value('pd_dirty')==dirty
            done('pixel/cell boundaries, stroke snapshot and undo/redo '+str(stroke))
        before=p.document();undo=p.document(1);p.set('pd_stroke',0)
        p.point(319,199,0);baseline=p.document();saved=p.document(1)
        p.set('pd_stroke',0);p.point(319,199,0)
        assert not p.value('pd_changed') and p.document()==baseline and p.document(1)==saved
        done('no-op erasing preserves the preceding undo record')
        before=p.document();p.call('pd_clear');assert p.document()==blank and p.value('pd_dirty')
        p.call('pd_undo');assert p.document()==before;done('clear is undoable')
        before=p.document();undo=p.document(1)
        for x,y,pen,color in [(320,0,1,1),(65535,0,1,1),(0,200,1,1),(0,255,1,1),(0,0,2,1),(0,0,1,16)]:
            p.point(x,y,pen,color,expected=1);assert p.document()==before and p.document(1)==undo
        done('out-of-range point and tool inputs cannot mutate document or undo')
        for index,(start,end) in enumerate([((0,0),(319,199)),((319,199),(0,0)),
                ((0,199),(319,0)),((319,0),(0,199)),((0,0),(319,0)),((319,199),(0,199)),
                ((0,0),(0,199)),((319,199),(319,0)),((7,7),(9,8)),((9,8),(7,7)),
                ((255,100),(256,102)),((256,102),(255,100)),((319,199),(319,199))]):
            before=p.document();p.set('pd_stroke',0);wanted=bytearray(before);color=(index+2)%16
            for x,y in segment(start,end):
                wanted[y//8*320+x//8*8+y%8]|=128>>(x%8)
                at=8192+y//8*40+x//8;wanted[at]=color*16+(wanted[at]&15)
            p.line(start,end,color=color)
            assert p.document()==wanted,(index,start,end)
            at=p.symbol('pd_x');assert int.from_bytes(p.ram[at:at+2],'little')==end[0]
            assert p.value('pd_y')==end[1]
            assert p.document(1)==before
            p.call('pd_undo');assert p.document()==before
            p.call('pd_undo');assert p.document()==wanted
        done('connected segments in all octants, full edges, ties, byte boundaries and one-stroke undo')
        before=p.document();undo=p.document(1)
        for end in ((320,0),(0,200),(65535,255)):
            p.line((0,0),end,expected=1);assert p.document()==before and p.document(1)==undo
        done('invalid segment endpoint cannot draw its otherwise valid starting point')
        p.close();done('app exit releases all document and image allocations')
        report['passed']=True
    except BaseException as error:report['error']=repr(error);raise
    finally:args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
