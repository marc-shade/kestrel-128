#!/usr/bin/env python3
"""Execute owned module loading/calls against IEC and UCI fault fixtures."""
import argparse
import hashlib
import json
from pathlib import Path

from py65.devices.mpu6502 import MPU
from ci_native_apps import fixture
from ci_native_heap import ROOT, IMAGE, symbol
from ci_native_ultimate import Client
from native_image import seal, validate as validate_app
from native_module import seal as seal_module, validate as validate_module

LOAD,CALL,CLOSE=0x1c5f,0x1c62,0x1c65
TOKEN,ERROR,STATE=0x3d17,0x3d1a,0x3d1b
BASE,END=0x6183,0x6400
NAME=b'SERVICE.PRG'


def parent_image():
    image=bytearray(fixture(b'\x4c\x20\x60'+bytes(221),pages=4))
    image[8]=7;image[9]=BASE&255;image[13]=(BASE-0x6000)>>8
    return seal(image)


def module_image(parent,code=b'\xa9\x2a\x18\x60'):
    header=b'NMOD'+bytes([1,1,7,0])+(16+len(code)).to_bytes(2,'little')+bytes(2)+b'\x10\0'+bytes(2)
    return seal_module(BASE.to_bytes(2,'little')+header+code,parent)


class Modules:
    def __init__(self,fmt=0,context=1,path=b'/Usb0/Apps/CORE.PRG'):
        self.parent=parent_image();self.module=module_image(self.parent)
        self.fmt=fmt;self.path=path.rsplit(b'/',1)[0]+b'/'+NAME
        self.c=Client({path:self.parent,self.path:self.module},iec={(8,b'CORE',b'P'):self.parent,(8,NAME,b'P'):self.module})
        self.ram=self.c.ram;self.c.io.formats[8]=fmt if fmt<3 else 0
        r=self.ram
        r[0x3d21]=context if fmt==3 else 8;r[0x3d2c]=fmt
        r[0x3d22]=len(path) if fmt==3 else 4;r[0x3d40:0x3d44]=b'CORE'
        r[0x4e00:0x4e00+len(path)]=path
        self.protected=[]
        for bank,page in ((0,0xc0),(1,4)):
            handle=self.c.m.alloc(32,bank,owner=16,page=page)
            data=bytes((i*73+bank*51+17)&255 for i in range(8192))
            self.c.m.bus.ram[bank][page*256:page*256+8192]=data
            self.protected.append((bank,page,handle,data))
        cpu=MPU(memory=self.c.m.bus,pc=0x1c38);cpu.sp=0xe0;cpu.p=0x20;cpu.stPushWord(0xaff)
        for steps in range(1000000):
            if cpu.pc==0x6020:break
            if not self.c.io.stub(cpu):cpu.step()
        else:raise AssertionError(('app did not enter',hex(cpu.pc),r[0x3d27]))
        assert r[0x3d23]==2 and not self.c.io.handles
        assert self.c.ultimate.handles=={1:None,2:None}
        assert int.from_bytes(r[symbol('m_base'):symbol('m_base')+2],'little')==BASE
        self.core=bytes(r[0x6000:BASE]);self.instructions=0;self.irqs=0;self.close_calls=0
        self.name();self.ram[BASE:END]=b'\xcc'*(END-BASE)

    def name(self,name=NAME):
        self.ram[0x3d86]=len(name);self.ram[0x3da0:0x3da0+len(name)]=name

    def install(self,image):
        self.c.io.files[8,NAME,b'P']=image
        self.c.ultimate.files[self.path]=image
        self.name()

    def token(self):return bytes(self.ram[TOKEN:TOKEN+3])

    def call(self,entry,expected=0,carry=None,*,flags=0,irq=False,caller=0x60f0,exited=False):
        cpu=MPU(memory=self.c.m.bus,pc=entry);cpu.sp=0xd0;cpu.p=0x20|flags
        cpu.stPushWord(caller-1)
        target,stack=(0xb00,0xe0) if exited else (caller,0xd0)
        close_entry=symbol('fs_close')
        for steps in range(3000000):
            if cpu.pc==target and cpu.sp==stack:break
            if cpu.pc==close_entry:self.close_calls+=1
            if irq and steps%101==0 and not cpu.p&4:cpu.irq();self.irqs+=1
            if not self.c.io.stub(cpu):cpu.step()
        else:raise AssertionError(('module gate did not return',hex(cpu.pc),cpu.sp,self.ram[STATE]))
        self.instructions+=steps
        assert (cpu.a,cpu.p&1)==(expected,int(bool(expected)) if carry is None else carry),(entry,cpu.a,cpu.p&1,expected)
        assert self.c.m.bus.config==0x0e
        if not exited:assert cpu.p&12==flags&12 and bytes(self.ram[0x6000:BASE])==self.core
        for bank,page,handle,data in self.protected:
            assert bytes(self.c.m.bus.ram[bank][page*256:page*256+8192])==data
            at=0x3c00+(handle[0]-1)*8
            assert self.ram[at]==16 and bytes(self.ram[at+4:at+7])==handle[1:]
        return cpu

    def check_load(self,image=None,expected=0,retained=False):
        if image is not None:self.install(image)
        self.call(LOAD,expected)
        assert self.ram[ERROR]==expected
        if expected:
            assert self.ram[STATE]==(4 if retained else 0) and self.token()==bytes(3)
        else:
            assert self.ram[STATE]==2 and self.token()!=bytes(3)
            image=self.module if image is None else image
            assert self.ram[BASE:BASE+len(image)-2]==image[2:]
        if not retained:
            assert not self.c.io.handles and self.c.ultimate.handles=={1:None,2:None}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path);args=parser.parse_args()
    report=dict(passed=False,kernel_sha256=hashlib.sha256(IMAGE.read_bytes()).hexdigest(),cases={})
    def done(name,m):
        report['cases'][name]=dict(instructions=m.instructions,irqs=m.irqs,close_calls=m.close_calls,state=m.ram[STATE])
        print('PASS: native module '+name,flush=True)
    try:
        for fmt in (0,1,2,3):
            m=Modules(fmt);m.check_load();m.call(CALL,42,0,flags=8,irq=True)
            assert m.ram[ERROR]==0 and m.irqs
            token=m.token();m.call(CLOSE);assert m.ram[STATE]==0 and m.token()==bytes(3)
            m.ram[TOKEN:TOKEN+3]=token;m.call(CALL,4)
            m.name();m.check_load();assert m.token()!=token
            m.call(CALL,42,0);done('load-call-close-format-'+str(fmt),m)
        m=Modules(3,context=2)
        m.ram[0x3d21]=8;m.ram[0x3d2c]=0;m.ram[0x4e00:0x4f00]=b'X'*256
        m.check_load();m.call(CALL,42,0)
        assert m.c.ultimate.commands[-1][0]==2
        done('original-context-and-folder-survive-public-source-changes',m)

        for fmt in (0,3):
            m=Modules(fmt)
            abi8=bytearray(module_image(m.parent,b'\x20\x6b\x1c\xa9\x2a\x18\x60'))
            abi8[8]=8
            m.check_load(seal_module(abi8,m.parent));m.call(CALL,42,0,flags=8,irq=True)
            done(f'{fmt}-abi-1.8-calls-display-close',m)
            m=Modules(fmt)
            abi9=bytearray(module_image(m.parent,b'\xad\x2f\x3d\x18\x60'));abi9[8]=9
            m.ram[0x3d2f]=2
            m.check_load(seal_module(abi9,m.parent));m.call(CALL,2,0,flags=8,irq=True)
            done(f'{fmt}-abi-1.9-reads-desktop-selection',m)
            m=Modules(fmt)
            abi12=bytearray(module_image(m.parent,b'\xad\xe4\x3d\x18\x60'));abi12[8]=12
            m.ram[0x3de4]=2
            m.check_load(seal_module(abi12,m.parent));m.call(CALL,2,0,flags=8,irq=True)
            done(f'{fmt}-abi-1.12-reads-system-format',m)
            m=Modules(fmt)
            abi13=bytearray(module_image(m.parent,b'\xad\xe5\x3d\x18\x60'));abi13[8]=13
            m.check_load(seal_module(abi13,m.parent));m.call(CALL,0,0,flags=8,irq=True)
            done(f'{fmt}-abi-1.13-reads-empty-clipboard-session',m)
            for size in (17,127,128,255,510,511,512,513,END-BASE):
                m=Modules(fmt)
                code=(b'\x60' if size==17 else b'\xa9\x2a\x18\x60')+bytes(max(0,size-20))
                full=module_image(m.parent,code)
                m.check_load(full);m.call(CALL,0 if size==17 else 42,0,irq=True)
                assert m.ram[BASE+size:END]==b'\xcc'*(END-BASE-size)
                done(f'{fmt}-extent-{size}',m)
            for label,offset,value in [('origin',0,0),('magic',2,0),('format',6,2),('abi',7,2),('minor',8,15),
                    ('minor-too-old',8,6),('flags',9,1),('parent',12,0),('entry-header',14,15),('entry-past-end',14,20),('extent-high',11,3)]:
                m=Modules(fmt);bad=bytearray(m.module);bad[offset]=value
                if label=='parent':bad[offset]^=m.module[offset]^0xff
                m.check_load(bytes(bad),0x10);done(f'{fmt}-reject-{label}',m)
            for size in (0,1,2,7,17,18,19,20,21):
                m=Modules(fmt);m.check_load(m.module[:size],0x12);done(f'{fmt}-short-{size}',m)
            m=Modules(fmt);m.check_load(m.module+b'X',0x13);done(f'{fmt}-long',m)
            m=Modules(fmt);bad=bytearray(m.module);bad[-1]^=1;m.check_load(bytes(bad),0x14);done(f'{fmt}-crc',m)
            m=Modules(fmt)
            if fmt==3:del m.c.ultimate.files[m.path]
            else:del m.c.io.files[8,NAME,b'P']
            m.check_load(expected=0x11);m.install(m.module);m.check_load();m.call(CALL,42,0)
            done(f'{fmt}-missing-then-retry',m)
            m=Modules(fmt);m.check_load();old=m.token()
            replacement=module_image(m.parent,b'\xa9\x63\x38\x60')
            m.check_load(replacement);new=m.token();assert new!=old
            m.ram[TOKEN:TOKEN+3]=old;m.call(CALL,4)
            m.ram[TOKEN:TOKEN+3]=new;m.call(CALL,99,1);assert m.ram[ERROR]==0
            m.install(replacement[:-1]);m.check_load(replacement[:-1],0x12)
            m.ram[TOKEN:TOKEN+3]=new;m.call(CALL,4)
            done(f'{fmt}-replacement-stale-token-and-partial-load',m)
            m=Modules(fmt)
            large=module_image(m.parent,b'\xa9\x2a\x18\x60'+bytes(500))
            m.install(large)
            if fmt==0:m.c.io.fail_read=21
            else:m.c.ultimate.read_limit=20
            m.check_load(large,0x11)
            done(f'{fmt}-read-failure-invalidates-entry',m)
            m=Modules(fmt)
            if fmt==0:
                m.c.io.files[8,b'DATA',b'S']=bytearray(b'KEPT STREAM')
                other=m.c.open(b'DATA')
            else:
                m.c.ultimate.files[b'/Data/KEEP']=bytearray(b'KEPT STREAM')
                other=m.c.open_u(b'/Data/KEEP',device=2)
            descriptor=0x3dc0+(other[0]-1)*16
            before=bytes(m.ram[descriptor:descriptor+16])
            m.name();m.call(LOAD)
            assert bytes(m.ram[descriptor:descriptor+16])==before
            m.call(CALL,42,0)
            m.c.select(other)
            assert (m.c.read() if fmt==0 else m.c.read_u())==b'KEPT STREAM'
            m.c.call(0x1c4a)
            done(f'{fmt}-caller-owned-stream-retained',m)

        for entry in (LOAD,CALL,CLOSE):
            m=Modules();m.check_load(module_image(m.parent,b'\x20'+entry.to_bytes(2,'little')+b'\x60'))
            m.call(CALL,7,1);assert m.ram[ERROR]==0 and m.ram[STATE]==2
            done('nested-gate-'+hex(entry),m)
        for caller in (0x5fff,0x601f,BASE,BASE+1,END,0xffff):
            m=Modules();before=bytes(m.ram[BASE:END]);m.call(LOAD,1,caller=caller)
            assert bytes(m.ram[BASE:END])==before and not m.token().strip(b'\0')
            done('outside-core-caller-'+hex(caller),m)
        for page in range(0x60,0x64):
            m=Modules();m.ram[0x3800+page]^=1;m.call(LOAD,4)
            done('corrupt-page-'+hex(page),m)
        for offset in (0,1,2,3,4,5,6):
            m=Modules();handle=m.ram[symbol('l_app_handle')];at=0x3c00+(handle-1)*8
            m.ram[at+offset]^=1;m.call(LOAD,4);done('changed-allocation-'+str(offset),m)
        for flags in (4,12):
            m=Modules();m.call(LOAD,8,flags=flags);done('masked-'+str(flags),m)
        for entry in (0,BASE,BASE+15,BASE+20,END,0xffff):
            m=Modules();m.check_load();at=symbol('m_entry');m.ram[at:at+2]=entry.to_bytes(2,'little')
            m.call(CALL,4);done('changed-entry-'+hex(entry),m)
        for limit in (BASE,BASE+16,END+1,0xffff):
            m=Modules();m.check_load();at=symbol('m_limit');m.ram[at:at+2]=limit.to_bytes(2,'little')
            m.call(CALL,4);done('changed-image-end-'+hex(limit),m)
        m=Modules();at=symbol('m_generation');m.ram[at:at+3]=b'\xfe\xff\xff'
        m.check_load();assert m.token()==b'\xff'*3
        m.name();m.call(LOAD,0x16);assert m.token()==b'\xff'*3 and m.ram[STATE]==2
        m.call(CALL,42,0);m.call(CLOSE);m.name();m.call(LOAD,0x16)
        done('nonwrapping-generation-exhaustion',m)

        for fmt in (0,3):
            m=Modules(fmt)
            if fmt==3:m.c.ultimate.inject[3]=lambda command,reply:[(b'',b'71,CLOSE ERROR')]
            else:m.c.io.fail_close=122
            m.check_load(expected=0x11,retained=True)
            assert m.close_calls==1,'uncertain CLOSE was replayed within the same load'
            m.name();m.call(LOAD,7);m.call(CALL,4);assert m.close_calls==1
            if fmt==3:m.c.ultimate.inject.clear()
            else:m.c.io.fail_close=None
            if fmt==0:
                events=list(m.c.io.events)
                m.call(CLOSE,0x11)
                assert m.ram[STATE]==4 and m.c.io.events==events
                m.name();m.call(LOAD,7)
                done('0-retained-close-keeps-existing-IEC-quarantine',m)
                continue
            m.call(CLOSE);assert m.ram[STATE]==0 and m.close_calls==2
            m.name();m.check_load();m.call(CALL,42,0)
            done(f'{fmt}-retained-close-explicit-recovery',m)
        m=Modules();m.check_load(module_image(m.parent,b'\x48\x48\xa9\x39\x4c\x3e\x1c'))
        m.call(CALL,0,0,exited=True)
        assert m.ram[0x3d24]==57 and m.ram[0x3d23]==0 and m.ram[STATE]==0
        done('module-exit-restores-original-app-stack',m)

        parent=parent_image();module=module_image(parent)
        assert validate_app(parent)['window']==BASE and validate_module(module,parent)['entry']==BASE+16
        for offset in (0,2,6,7,8,9,10,11,12,13,14,15,16,17,18):
            bad=bytearray(module);bad[offset]^=1
            try:validate_module(bytes(bad),parent)
            except ValueError:pass
            else:raise AssertionError(('host module accepted corruption',offset))
        report['passed']=True
        print(f"PASS: {len(report['cases'])} native module cases; core and workspaces preserved",flush=True)
    except BaseException as error:report['error']=str(error);raise
    finally:
        if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
