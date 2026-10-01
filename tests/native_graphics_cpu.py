#!/usr/bin/env python3
"""Execute clipped graphics against real native heap transfers and byte oracles."""
import hashlib
import json
from pathlib import Path
import random
import re
from py65.devices.mpu6502 import MPU
from ci_native_heap import Machine,OWNER,HANDLE,BUFFER,BUSY,RECORDS

ROOT=Path(__file__).resolve().parents[1]
LIB=(ROOT/'target/native-graphics/graphics.prg').read_bytes()
SYMBOLS={name:int(value,16) for name,value in re.findall(r'^(\w+)\s*=\s*\$([0-9a-f]+)',
    (ROOT/'target/native-graphics/graphics.sym').read_text(),re.M)}
report=dict(passed=False,hardware_io=False,kernel_sha256=hashlib.sha256((ROOT/'target/native/kestrel.prg').read_bytes()).hexdigest(),
    library_sha256=hashlib.sha256(LIB).hexdigest(),library_bytes=len(LIB)-2,cases=[],interrupts=0,max_instructions=0)


class Drawing:
    def __init__(self,bank=0,pages=36):
        self.m=Machine();self.ram=self.m.ram
        self.code_pages=(len(LIB)-2+255)//256
        self.code=self.m.alloc(self.code_pages,0,32,page=0x60)
        self.ram[0x6000:0x6000+len(LIB)-2]=LIB[2:]
        self.handle=self.m.alloc(pages,bank,32,page=0xc0 if bank==0 else 0x90)
        self.bank=bank;self.start=(0xc0 if bank==0 else 0x90)*256;self.size=pages*256
        self.clip=(0,0,320,200)
        self.expected=bytearray((i*73+i//251)&255 for i in range(self.size))
        self.m.bus.ram[bank][self.start:self.start+self.size]=self.expected
        self.original_other=bytes(self.m.bus.ram[1-bank]) if bank==0 else None
        self.m.select(self.handle,32)
        self.call('gfx_bind',expected=0 if pages>=36 else 6)
    def call(self,name,expected=0,flags=0,irq=False):
        cpu=MPU(memory=self.m.bus,pc=SYMBOLS[name]);cpu.sp=0xe0;cpu.p=cpu.UNUSED|flags
        cpu.stPushWord(0xaff);before=bytes(self.ram[:256]);mapping=self.m.bus.config
        writes=len(self.m.bus.far_writes);interrupts=0
        for steps in range(30000000):
            if cpu.pc==0xb00 and cpu.sp==0xe0:break
            if irq and steps%1009==0 and not cpu.p&4:cpu.irq();interrupts+=1
            cpu.step()
        else:raise AssertionError((name,'did not return',hex(cpu.pc)))
        assert (cpu.a,cpu.p&1)==(expected,int(bool(expected))),(name,cpu.a,cpu.p,expected)
        assert cpu.p&12==flags&12 and self.m.bus.config==mapping and bytes(self.ram[:256])==before
        assert self.ram[SYMBOLS['gfx_error']]==expected
        assert all((bank==self.bank and self.start<=at<self.start+self.size) or (bank==0 and 0x6000<=at<0x6000+self.code_pages*256)
                   for bank,at,value in self.m.bus.far_writes[writes:])
        assert not self.m.bus.io_reads and not self.m.bus.io_writes
        report['interrupts']+=interrupts;report['max_instructions']=max(report['max_instructions'],steps)
        return steps
    def draw(self,coords,pen=1,color=None,flags=0,irq=False,expected=0):
        for index,value in enumerate(coords):self.ram[SYMBOLS['gfx_x0']+index*2:SYMBOLS['gfx_x0']+index*2+2]=(value&65535).to_bytes(2,'little')
        self.ram[SYMBOLS['gfx_pen']]=pen
        if color is not None:self.ram[SYMBOLS['gfx_color']]=color
        steps=self.call('gfx_rect' if color is None else 'gfx_colors',expected,flags,irq)
        if not expected:
            x0,y0,x1,y1=coords;w,h=(320,200) if color is None else (40,25)
            clip=self.clip if color is None else ((self.clip[0]+7)//8,(self.clip[1]+7)//8,self.clip[2]//8,self.clip[3]//8)
            for y in range(max(0,y0,clip[1]),min(h,y1,clip[3])):
                for x in range(max(0,x0,clip[0]),min(w,x1,clip[2])):
                    if color is not None:self.expected[8192+y*40+x]=color
                    else:
                        at=(y//8)*320+(x//8)*8+y%8;mask=128>>(x%8)
                        if pen==0:self.expected[at]&=mask^255
                        elif pen==1:self.expected[at]|=mask
                        else:self.expected[at]^=mask
        actual=bytes(self.m.bus.ram[self.bank][self.start:self.start+self.size])
        if actual!=self.expected:
            bad=[i for i,(a,b) in enumerate(zip(actual,self.expected)) if a!=b]
            raise AssertionError((coords,pen,color,'surface differs',bad[:20]))
        if self.original_other is not None:assert bytes(self.m.bus.ram[1-self.bank])==self.original_other
        report['cases'].append(dict(bank=self.bank,coords=coords,pen=pen,color=color,error=expected,
                                    flags=flags,interrupts=irq,instructions=steps))
