#!/usr/bin/env python3
"""Execute owned native field editing and clipping at both display widths."""
import argparse
import hashlib
import json
from pathlib import Path
import random

from py65.devices.mpu6502 import MPU
from ci_native_heap import Machine,ROOT,symbol
from native_field_check import viewport

PTR,KEY,WIDTH,FLAGS,ERROR,BUSY=0x3d35,0x3d37,0x3d38,0x3d39,0x3d3a,0x3d3b
STATE,TEXT=0x60fc,0x67f0


def screen_code(value):return value-64 if 64<=value<96 else value-32 if value>=96 else value


class Fields:
    def __init__(self,data=b'',maximum=255,filter=0):
        self.m=Machine();self.ram=self.m.ram;self.bus=self.m.bus
        self.handle=self.m.alloc(16,0,32,page=0x60)
        self.ram[symbol('l_app_handle'):symbol('l_app_handle')+4]=self.handle
        self.ram[0x3d6a]=16
        self.ram[0x3d20]=32;self.ram[0x3d23]=2;self.ram[BUSY]=0
        self.ram[STATE:STATE+8]=bytes([len(data),len(data),maximum,TEXT&255,TEXT>>8,0,0,filter])
        self.ram[TEXT:TEXT+len(data)+1]=data+b'\0'
        self.ram[PTR:PTR+2]=STATE.to_bytes(2,'little')
        self.screens=[bytearray(b' '*1000),bytearray(b' '*2000)]
        self.row=[6,6];self.col=[7,7];self.reverse=[False,False]
        self.instructions=0;self.outputs=0

    def invoke(self,draw=False,expected=0,flags=0):
        cpu=MPU(memory=self.bus,pc=0x1c5c if draw else 0x1c59)
        cpu.sp=0xe0;cpu.p=flags|cpu.UNUSED;cpu.stPushWord(0xaff)
        old_heap=self.m.metadata();old_config=self.bus.config
        for steps in range(100000):
            if cpu.pc==0xb00 and cpu.sp==0xe0:break
            if cpu.pc in (0xffd2,0xfff0):
                display=self.ram[0xd7]>>7;columns=(40,80)[display]
                if cpu.pc==0xfff0:
                    assert cpu.p&cpu.CARRY
                    cpu.x,cpu.y=self.row[display],self.col[display]
                else:
                    value=cpu.a
                    self.outputs+=1
                    assert not self.ram[0xf4],'ROM quote mode leaked into field drawing'
                    if value in (0x12,0x92):self.reverse[display]=value==0x12
                    else:
                        assert 32<=value<127 and self.col[display]<columns-1
                        at=self.row[display]*columns+self.col[display]
                        self.screens[display][at]=screen_code(value)|(128 if self.reverse[display] else 0)
                        self.col[display]+=1
                        if value==34:self.ram[0xf4]=1
                cpu.pc=cpu.stPopWord()+1
            else:cpu.step()
        else:raise AssertionError(('field did not return',hex(cpu.pc)))
        self.instructions+=steps
        assert (cpu.a,cpu.p&1)==(expected,int(bool(expected))),(cpu.a,cpu.p,expected)
        assert cpu.p&12==flags&12 and self.bus.config==old_config
        assert self.m.metadata()==old_heap
        assert self.ram[ERROR]==expected
        if expected!=7:assert self.ram[BUSY]==0
        return self.ram[FLAGS]

    def key(self,key,**kwargs):self.ram[KEY]=key;return self.invoke(**kwargs)
    def data(self):return bytes(self.ram[TEXT:TEXT+self.ram[STATE]])
    def caret(self):return self.ram[STATE+1]
    def draw(self,width,display=0):
        self.ram[0xd7]=display*128;self.ram[WIDTH]=width
        self.row[display]=6;self.col[display]=7
        self.screens[display][:]=b' '*(1000 if not display else 2000)
        self.invoke(draw=True)
        columns=(40,80)[display]
        return bytes(self.screens[display][6*columns+7:6*columns+7+width])


def edited(data,caret,key,maximum,filter):
    old=data,caret
    if key==0:return data,len(data),0
    if key in (0x13,1):caret=0
    elif key==5:caret=len(data)
    elif key==0x9d:caret=max(0,caret-1)
    elif key==0x1d:caret=min(len(data),caret+1)
    elif key==20 and caret:data=data[:caret-1]+data[caret:];caret-=1
    elif key==4 and caret<len(data):data=data[:caret]+data[caret+1:]
    elif key==21:data=b'';caret=0
    else:
        if key==0x94:key=32
        valid=32<=key<127
        if filter==1:valid=valid and 48<=key<=57
        elif filter==2:
            if 97<=key<=102:key-=32
            valid=valid and (48<=key<=57 or 65<=key<=70)
        elif filter==3:valid=valid and key not in b'*?,:/\\@#$'
        if valid and len(data)<maximum:data=data[:caret]+bytes([key])+data[caret:];caret+=1
    return data,caret,int(data!=old[0])|2*int(caret!=old[1])


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path);args=parser.parse_args()
    report=dict(passed=False,kernel_sha256=hashlib.sha256((ROOT/'target/native/kestrel.prg').read_bytes()).hexdigest(),cases={})
    try:
        rng=random.Random(12816);events=0
        for filter,maximum in ((0,255),(1,2),(2,6),(3,16)):
            field=Fields(maximum=maximum,filter=filter);data=b'';caret=0
            keys=list(range(256))+[rng.choice([0x9d,0x1d,20,4,0x13,5,21,0x94,rng.randrange(32,127)]) for _ in range(800)]
            for key in keys:
                data,caret,result=edited(data,caret,key,maximum,filter)
                assert field.key(key,flags=8)==result,(filter,key,'change flags')
                assert (field.data(),field.caret())==(data,caret),(filter,key,data,field.data())
                assert not field.ram[TEXT+len(data)]
                events+=1
        report['cases']['filters-navigation-and-random-edits']=dict(events=events)

        field=Fields(bytes((i%90)+32 for i in range(255)))
        original=field.data();assert field.key(ord('!'))==0 and field.data()==original
        field.key(0x9d);field.key(20);field.key(ord('!'))
        assert field.data()==original[:253]+b'!'+original[254:] and field.caret()==254
        field.key(0);assert field.caret()==255
        report['cases']['full-255-byte-field-and-insertion']=True

        comparisons=0
        for length in (0,1,2,7,8,31,32,71,72,254,255):
            raw=(b'AB"cd\x00\xffEF'*32)[:length];field=Fields(raw)
            for display in (0,1):
                for width in ((3,9,31) if not display else (3,9,31,71)):
                    for caret in sorted({0,length//2,length}):
                        field.ram[STATE+1]=caret
                        previous=field.ram[STATE+5+display];outputs=field.outputs
                        other=bytes(field.screens[1-display])
                        shown=field.draw(width,display)
                        view=field.ram[STATE+5+display];capacity=width-2
                        assert view==viewport(length,caret,width,previous)
                        assert field.outputs-outputs==width+3
                        assert bytes(field.screens[1-display])==other
                        assert 0<=view<=caret<view+capacity
                        expected=bytearray([ord('<') if view else 32])
                        for at in range(view,view+capacity):
                            value=raw[at] if at<len(raw) else 32
                            value=value if 32<=value<127 else ord('.')
                            expected.append(screen_code(value)|(128 if at==caret else 0))
                        expected.append(ord('>') if length-view>capacity else 32)
                        assert shown==expected,(length,display,width,caret,view,shown,expected)
                        assert field.data()==raw and not any(field.reverse)
                        comparisons+=1
        report['cases']['both-display-widths-quotes-raw-bytes-and-caret']=dict(frames=comparisons)

        for kind,edit in (
                ('foreign-record',lambda f:f.ram.__setitem__(slice(PTR,PTR+2),(0x5000).to_bytes(2,'little'))),
                ('foreign-buffer',lambda f:f.ram.__setitem__(slice(STATE+3,STATE+5),(0x7000).to_bytes(2,'little'))),
                ('wrapped-buffer',lambda f:f.ram.__setitem__(slice(STATE+3,STATE+5),(0xfff0).to_bytes(2,'little'))),
                ('overlapping-buffer',lambda f:f.ram.__setitem__(slice(STATE+3,STATE+5),(STATE-10).to_bytes(2,'little'))),
                ('zero-capacity',lambda f:f.ram.__setitem__(STATE+2,0)),
                ('bad-length',lambda f:f.ram.__setitem__(STATE,255)),
                ('bad-caret',lambda f:f.ram.__setitem__(STATE+1,17)),
                ('bad-filter',lambda f:f.ram.__setitem__(STATE+7,4))):
            field=Fields(b'ABC',maximum=16);edit(field);before=bytes(field.ram[0x5000:0xc000])
            error=6 if kind in ('foreign-record','foreign-buffer','wrapped-buffer') else 1
            field.key(ord('X'),expected=error)
            assert bytes(field.ram[0x5000:0xc000])==before,kind
        report['cases']['bad-state-and-range-are-atomic']=True

        for width,row,col,display in ((0,6,7,0),(2,6,7,0),(80,6,0,1),
                                      (9,25,7,0),(9,6,31,0),(9,6,71,1),(79,6,255,1)):
            field=Fields(b'ABC');field.ram[WIDTH]=width;field.ram[0xd7]=display*128
            field.row[display]=row;field.col[display]=col
            before=bytes(field.ram[STATE:STATE+8]),field.data()
            field.invoke(draw=True,expected=1)
            assert (bytes(field.ram[STATE:STATE+8]),field.data())==before and not field.outputs
        report['cases']['invalid-width-and-screen-boundary-are-atomic']=True

        for page in (STATE>>8,(STATE+7)>>8,TEXT>>8,(TEXT+255)>>8):
            field=Fields(b'ABC');field.ram[0x3800+page]=0
            before=bytes(field.ram[STATE:STATE+8]),field.data()
            field.key(ord('X'),expected=4)
            assert (bytes(field.ram[STATE:STATE+8]),field.data())==before
        report['cases']['every-record-and-buffer-page-is-owned']=True

        field=Fields(b'ABC');before=field.data();field.key(ord('X'),expected=8,flags=4);assert field.data()==before
        field.ram[BUSY]=1;field.key(ord('X'),expected=7);assert field.ram[BUSY]==1 and field.data()==before
        field.ram[BUSY]=0;field.ram[0x3d20]=0;field.key(ord('X'),expected=5);assert field.data()==before
        field.ram[0x3d20]=32;field.ram[symbol('l_app_handle')+1]^=1
        field.key(ord('X'),expected=4);assert field.data()==before
        report['cases']['foreground-reentrancy-and-stale-owner']=True
        report['passed']=True
    finally:
        if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(f'PASS: {len(report["cases"])} native field cases')


if __name__=='__main__':main()
