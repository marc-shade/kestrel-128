#!/usr/bin/env python3
"""Run checked native application loading through real modeled UCI registers."""
import argparse
import hashlib
import json
from pathlib import Path

from py65.devices.mpu6502 import MPU
from ci_native_apps import fixture,seal
from ci_native_ultimate import Client
from ci_native_files import OWNER,HANDLE,RECORDS,CLOSE,OPEN
from ci_native_heap import ROOT,IMAGE,symbol


def run_case(image=None,*,name=b'/Usb0/Applications/Example.prg',device=1,fmt=3,
             expected=0,retained=False,flags=0,prepare=None,interrupt=False):
    image=fixture() if image is None else image
    c=Client({name:image},iec={(8,b'CHECK',b'P'):image,(8,b'DATA',b'S'):b'KEPT'})
    r=c.ram;protected=[]
    for bank,page in ((0,0xc0),(1,4)):
        handle=c.m.alloc(32,bank,owner=16,page=page)
        data=bytes((i&255)^(i>>8)^(0xa5 if bank else 0) for i in range(8192))
        c.m.bus.ram[bank][page*256:page*256+8192]=data
        protected.append((bank,page,data,handle))
    if prepare:prepare(c)
    r[0x3d21]=device;r[0x3d22]=len(name) if fmt==3 else 5;r[0x3d2c]=fmt;r[0x3d2d]=8
    r[0x3d40:0x3d45]=b'CHECK';r[0x4e00:0x4e00+len(name)]=name
    r[symbol('ui_system_device')]=8
    baseline=c.m.stats()
    parameters=bytes(r[0xb7:0xbd])+bytes(r[0xc6:0xc8])+bytes([r[0x9d]])
    cpu=MPU(memory=c.m.bus,pc=0x1c38);cpu.sp=0xe0;cpu.p=0x20|flags;cpu.stPushWord(0xaff)
    entry=0x6000+int.from_bytes(image[14:16],'little') if len(image)>=16 else -1
    entered=False;irqs=0
    for steps in range(8000000):
        if cpu.pc==0xb00 and cpu.sp==0xe0:break
        if cpu.pc==entry:
            entered=True
            assert all(r[RECORDS+i]!=32 for i in (0,16)),'loader stream remained owned at app entry'
            assert parameters==bytes(r[0xb7:0xbd])+bytes(r[0xc6:0xc8])+bytes([r[0x9d]])
        if interrupt and steps%101==0 and not cpu.p&4:cpu.irq();irqs+=1
        if not c.io.stub(cpu):cpu.step()
    else:raise AssertionError(f'loader did not return, PC={cpu.pc:04x}')
    assert (cpu.a,cpu.p&1)==(expected,int(bool(expected))),(expected,cpu.a,cpu.p&1)
    assert cpu.p&12==flags&12 and cpu.sp==0xe0
    assert parameters==bytes(r[0xb7:0xbd])+bytes(r[0xc6:0xc8])+bytes([r[0x9d]])
    assert c.m.bus.config==0x0e and not c.m.bus.io_writes
    for bank,page,data,handle in protected:
        assert bytes(c.m.bus.ram[bank][page*256:page*256+8192])==data
    if expected:assert not entered,'executed a rejected image'
    if retained:assert (r[0x3d20],r[0x3d23])==(32,4)
    elif expected!=7:
        assert (r[0x3d20],r[0x3d23])==(0,0)
        assert c.m.stats()==baseline
        assert all(r[RECORDS+i]!=32 for i in (0,16))
    assert c.ultimate.paths=={1:b'/shell',2:b'/browser'}
    return c,dict(result=expected,entered=entered,instructions=steps,irq_attempts=irqs,
                  dos=r[0x3d25],io_status=r[0x3d26],app_state=r[0x3d23],
                  commands=[command.hex() for command in c.ultimate.commands])


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path);args=parser.parse_args()
    report=dict(passed=False,kernel_sha256=hashlib.sha256(IMAGE.read_bytes()).hexdigest(),cases={})
    cases=report['cases']
    def case(label,*a,**kw):
        c,result=run_case(*a,**kw);cases[label]=result;return c
    try:
        c=case('ultimate-return');assert c.ram[0x3d24]==42 and not c.io.events
        assert c.ram[0x6023:0x7000]==bytes(0x7000-0x6023)
        c=case('second-context',device=2);assert c.ram[0x3d24]==42
        assert all(command[0]==2 for command in c.ultimate.commands)
        for size,pages in ((510,2),(512,2),(513,3),(24576,96)):
            code=b'\xa9\x2a\x60'+bytes((i*29+17)&255 for i in range(size-35))
            c=case('payload-'+str(size),fixture(code,pages))
            assert c.ram[0x6000+size-1]==code[-1]
        c=case('255-byte-path',name=b'/'+b'A'*126+b'/'+b'B'*127)
        assert len(c.ultimate.commands[1])==258
        c=case('irq-decimal-caller',flags=8,interrupt=True)
        assert cases['irq-decimal-caller']['irq_attempts']>20
        for label,target,action in (('exit',0x1c3e,0),('replace',0x1c53,1),('workspace',0x1c56,2)):
            code=b'\x48\x48\xa9\x39\x4c'+target.to_bytes(2,'little')
            c=case(label,fixture(code));assert c.ram[0x3d28]==action
            assert c.ram[0x3d24]==(0 if action else 57)
        for fmt in (0,1,2):
            c=case('shared-iec-format-'+str(fmt),device=8,fmt=fmt,
                   prepare=lambda c,fmt=fmt:c.io.formats.__setitem__(8,fmt))
            assert not c.ultimate.commands and c.ram[0x3d24]==42

        abi8=bytearray(fixture());abi8[8]=8
        c=case('abi-1.8-accepted',seal(abi8));assert c.ram[0x3d24]==42
        abi9=bytearray(fixture());abi9[8]=9
        c=case('abi-1.9-accepted',seal(abi9));assert c.ram[0x3d24]==42
        abi12=bytearray(fixture());abi12[8]=12
        c=case('abi-1.12-accepted',seal(abi12));assert c.ram[0x3d24]==42
        for minor in (13,14):
            image=bytearray(fixture());image[8]=minor
            c=case(f'abi-1.{minor}-accepted',seal(image));assert c.ram[0x3d24]==42
        mutations=[('origin',0,1),('magic',2,0),('format',6,2),('abi',7,2),('minor',8,15),
                   ('flags',9,1),('pages-zero',12,0),('pages-too-large',12,97),('reserved',13,1),
                   ('entry-header',14,31),('entry-past-end',14,40),('title-control',18,13),('size-small',10,32)]
        for label,offset,value in mutations:
            data=bytearray(fixture());data[offset]=value
            case('reject-'+label,bytes(data),expected=0x10)
        for size in (0,1,2,10,33,34,35,36):case('short-'+str(size),fixture()[:size],expected=0x12)
        case('trailing',fixture()+b'X',expected=0x13)
        data=bytearray(fixture());data[-2]^=1;case('checksum',bytes(data),expected=0x14)
        for label,name in (('empty',b''),('relative',b'app.prg'),('nul',b'/bad\0app')):
            c=case('path-'+label,name=name,expected=1);assert not c.ultimate.commands
        for label,kw in (('masked',dict(flags=4,expected=8)),('bad-context',dict(device=8,expected=1)),
                         ('bad-format',dict(fmt=4,expected=1))):
            c=case(label,**kw);assert not c.ultimate.commands
        c=case('missing',expected=0x11,prepare=lambda c:c.ultimate.files.clear())
        assert c.ultimate.handles=={1:None,2:None} and cases['missing']['dos']
        c=case('absent',expected=0x11,prepare=lambda c:setattr(c.ultimate,'present',False))
        assert c.ram[0x3d26]==0xfe
        image=fixture(b'\xa9\x2a\x60'+b'X'*1100)
        c=case('short-transfer',image,expected=0x11,prepare=lambda c:setattr(c.ultimate,'read_limit',100))
        assert c.ram[0x3d26]==0xe5
        c=case('read-status',expected=0x11,prepare=lambda c:setattr(c.ultimate,'read_status',b'71,READ ERROR'))
        assert c.ram[0x3d25]==71
        c=case('oversized-response',expected=0x11,
               prepare=lambda c:c.ultimate.inject.__setitem__(4,lambda command,reply:[(bytes(513),b'00,OK')]))
        assert c.ram[0x3d26]==0xfc and c.ultimate.aborted==1
        c=case('uncertain-close',expected=0x11,retained=True,
               prepare=lambda c:c.ultimate.inject.__setitem__(3,lambda command,reply:[(b'',b'71,CLOSE ERROR')]))
        assert c.ram[0x3d25]==71 and c.ram[RECORDS]==32

        def foreign_file(c):
            c.ultimate.files[b'/foreign']=b'FOREIGN FILE'
            c.ultimate.handles[1]=dict(name=b'/foreign',mode=1,pos=7)
        c=case('foreign-file',expected=0x15,prepare=foreign_file)
        assert c.ultimate.handles[1]==dict(name=b'/foreign',mode=1,pos=7)
        assert [command[1] for command in c.ultimate.commands]==[7]
        def busy(c):c.ultimate.state=0x10;c.ultimate.stuck=True
        c=case('foreign-command',expected=0x15,prepare=busy)
        assert not c.ultimate.commands and not c.ultimate.aborted
        def other_context(c):
            c.ram[OWNER]=33;c.ultimate.files[b'/kept']=b'OTHER CONTEXT'
            c.other=c.open_u(b'/kept',device=2)
        c=case('other-owned-dos-context',prepare=other_context)
        assert c.ultimate.handles[1] is None and c.ultimate.handles[2]['name']==b'/kept'
        c.select(c.other,33);assert c.read_u()==b'OTHER CONTEXT';c.call(CLOSE)
        def same_iec(c):c.other=c.open(b'DATA',owner=33)
        c=case('shared-iec-command-lease',device=8,fmt=0,prepare=same_iec)
        assert set(c.io.handles)=={122,124}
        c.select(c.other,33);assert c.read()==b'KEPT';c.call(CLOSE)
        def full(c):
            other_context(c);c.ram[OWNER]=34;c.open(b'DATA',owner=34)
        c=case('both-stream-slots-occupied',expected=3,prepare=full)
        assert c.ram[RECORDS]==33 and c.ram[RECORDS+16]==34
        assert c.ultimate.handles[2]['name']==b'/kept'
        report['passed']=True
        print(f'PASS: {len(cases)} shared loader cases; UCI/IEC bytes, IRQs, checked entry and 16 KiB workspace preservation',flush=True)
    except BaseException as error:report['error']=str(error);raise
    finally:
        if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
