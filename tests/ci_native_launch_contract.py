#!/usr/bin/env python3
"""Run assembled request consumers, every compact glyph and workspace patterns."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from py65.devices.mpu6502 import MPU
from ci_native_heap import Machine,ROOT,symbol
from hwlib import lst_symbol
from native_app_pack import decode
from native_module import validate as validate_module
from src.native.graphics.font import font


def loaded(app,part=None):
    image=(ROOT/f'target/native-desktop/{app}.prg').read_bytes()
    raw=decode(image) if part is None else (ROOT/f'target/native-desktop/{part}.prg').read_bytes()
    if part:validate_module(raw,image)
    ram=bytearray(65536);start=int.from_bytes(raw[:2],'little');ram[start:start+len(raw)-2]=raw[2:]
    cache={}
    def address(name):
        if name not in cache:cache[name]=lst_symbol('native-desktop/'+app,name)
        return cache[name]
    return ram,address


def call(ram,pc,a=0):
    cpu=MPU(memory=ram,pc=pc);cpu.a=a;cpu.p=0x20;cpu.sp=0xe0;cpu.stPushWord(0xaff)
    for steps in range(20000):
        if cpu.pc==0xb00 and cpu.sp==0xe0:return cpu,steps
        cpu.step()
    raise AssertionError(('consumer did not return',hex(cpu.pc)))


def glyphs():
    wanted=font();results=[]
    for app,part in [('editor','edfind'),('files','fsview'),('paint',None)]:
        ram,at=loaded(app,part);entry=at('gfx_load_glyph');bits=at('gfx_bits');steps=0
        for code in range(32,127):
            _,count=call(ram,entry,code);steps+=count
            assert ram[bits:bits+8]==wanted[(code-32)*8:][:8],(app,code)
        results.append(dict(name=app+' every printable glyph matches original 8x8 rows',glyphs=95,instructions=steps))
    return results


def claims():
    results=[]
    cases=[dict(label='SEQ',name=b'EXACT',kind=0),dict(label='PRG',name=b'EXACT',kind=1),
           dict(label='USR',name=b'EXACT',kind=2),dict(label='sixteen bytes',name=b'X'*16),
           dict(label='IEC slash remains literal',name=b'A/B'),
           dict(label='Ultimate root',name=b'A.TXT',fmt=3,device=1,parent=b'/'),
           dict(label='Ultimate 255 bytes',name=b'DOC.TXT',fmt=3,device=2,parent=b'/'+b'D'*246),
           dict(label='Ultimate trailing separator',name=b'UPPER',fmt=3,device=2,parent=b'/Usb0/'),
           dict(label='absent',request=0,error=0),dict(label='expired phase',request=2,error=1),
           dict(label='unlaunched staged phase',request=128,error=1),
           dict(label='wrong app',consumer=7,error=1),dict(label='bad file type',kind=3,error=1),
           dict(label='empty name',name=b'',error=1),dict(label='IEC long name',name=b'A'*17,error=1),
           dict(label='IEC low device',device=7,error=1),dict(label='IEC high device',device=31,error=1),
           dict(label='bad format',fmt=4,error=1),dict(label='Ultimate low device',fmt=3,device=0,error=1),
           dict(label='Ultimate high device',fmt=3,device=3,error=1),
           dict(label='Ultimate nonzero file type',fmt=3,device=1,kind=1,error=1),
           dict(label='Ultimate empty parent',fmt=3,device=1,parent=b'',error=1),
           dict(label='Ultimate relative parent',fmt=3,device=1,parent=b'Usb0',error=1),
           dict(label='Ultimate path overflow',fmt=3,device=1,parent=b'/'+b'D'*254,error=1),
           dict(label='Ultimate embedded separator',fmt=3,device=1,name=b'DIR/FILE',error=1),
           dict(label='embedded terminator',name=b'A\0B',error=1)]
    for app,part,expected_kind in [('editor','edclip',1),('paint',None,2)]:
        template,at=loaded(app,part);entry=at('dl_claim')
        for case in cases:
            ram=bytearray(template);name=case.get('name',b'EXACT');parent=case.get('parent',b'/')
            fmt=case.get('fmt',0);device=case.get('device',9);kind=case.get('kind',0)
            ram[0x3d9a:0x3d9f]=bytes([case.get('request',1),case.get('consumer',expected_kind),kind,1,0])
            ram[0x3d29:0x3d2b]=bytes([device,fmt]);ram[0x3d2e]=len(parent);ram[0x3d34]=len(name)
            ram[0x4a00:0x4a00+len(parent)]=parent;ram[0x3e00:0x3e00+len(name)]=name
            identity=bytes(ram[0x3d29:0x3d35]+ram[0x3e00:0x3f00]+ram[0x4a00:0x4b00])
            cpu,steps=call(ram,entry);assert ram[0x3d9a]==0 and ram[0x3d9d]==1
            if 'error' in case:assert (cpu.a,cpu.p&1)==(case['error'],1),(app,case,cpu.a,cpu.p)
            else:
                assert (cpu.a,cpu.p&1)==(0,0),(app,case,cpu.a,cpu.p)
                target=parent.rstrip(b'/')+b'/'+name if fmt==3 else name
                assert bytes(ram[at('DL_NAME'):at('DL_NAME')+len(target)+1])==target+b'\0'
                assert [ram[at(key)] for key in ('DL_LENGTH','DL_DEVICE','DL_FORMAT','DL_TYPE')]==[len(target),device,fmt,kind]
            assert identity==bytes(ram[0x3d29:0x3d35]+ram[0x3e00:0x3f00]+ram[0x4a00:0x4b00])
            results.append(dict(name=app+' '+case['label'],instructions=steps))
    return results


def workspace():
    results=[]
    def run(m):
        cpu=MPU(memory=m.bus,pc=symbol('ui_pattern_test'));cpu.sp=0xe0;cpu.p=0x20
        cpu.stPushWord(0xaff)
        for steps in range(4000000):
            if cpu.pc==0xb00 and cpu.sp==0xe0:
                assert m.bus.config==0x0e and not cpu.p&12
                return cpu.a
            cpu.step()
        raise AssertionError(('workspace did not return',hex(cpu.pc)))
    for bank in (0,1):
        m=Machine();token=m.alloc(32,bank,16)
        m.ram[symbol('ui_handles')+bank*4:symbol('ui_handles')+bank*4+4]=bytes(token)
        m.ram[symbol('ui_bank')]=bank;m.ram[symbol('ui_test_operation')]=1
        assert run(m)==0
        descriptor=0x3c00+(token[0]-1)*8;start=m.ram[descriptor+2]*256
        expected=bytes((index&255)^((index>>8)&255)^(0xa5 if bank else 0) for index in range(8192))
        assert bytes(m.bus.ram[bank][start:start+8192])==expected
        m.ram[symbol('ui_test_operation')]=0
        assert run(m)==0
        for offset in (0,255,256,511,512,4095,8191):
            m.bus.ram[bank][start+offset]^=1
            assert run(m)==10,(bank,offset)
            m.bus.ram[bank][start+offset]^=1
        results.append(dict(name='workspace bank '+str(bank)+' complete 8 KiB pattern and seven mismatches',
                            sha256=hashlib.sha256(expected).hexdigest()))
    return results


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True);args=parser.parse_args()
    result=dict(passed=False,physical_hardware_io=False,cases=[])
    try:
        result['cases']=glyphs()+claims()+workspace();result['passed']=True
        print('PASS',len(result['cases']),'contract, font and workspace groups')
    finally:args.report.write_text(json.dumps(result,indent=2)+'\n')
