#!/usr/bin/env python3
"""Execute packed NAPP startup through the real native loader and heap gates."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import sys

from py65.devices.mpu6502 import MPU
from ci_native_heap import Machine, Bus, ROOT
from ci_native_apps import RUN
from ci_native_files import StreamIEC
sys.path.insert(0,str(ROOT))
from native_image import seal, validate
from native_app_pack import build, decode


class OwnedBus(Bus):
    def __setitem__(self, address, value):
        address &= 65535
        bank = 0 if address < 0x400 else (self.config >> 6) & 1
        if getattr(self,'guard',False) and ((bank == 0 and 0x5000 <= address < 0xff00)
                                           or (bank == 1 and 0x400 <= address < 0xff00)):
            slot = self.ram[0][0x3800+bank*256+address//256]
            assert 1 <= slot <= 32, ('write without allocation',bank,hex(address),slot)
            at = 0x3c00+(slot-1)*8
            assert self.ram[0][at] == 32, ('write into foreign allocation',bank,hex(address))
        super().__setitem__(address,value)


def run(image, original, *, fault=None, expected_exit=0, expected_loader=0, execute=False, interrupts=False, flags=0):
    m=Machine();m.bus.__class__=OwnedBus;ram=m.ram
    if fault=='code-full': m.alloc(1,0,owner=16,page=0x50)
    elif fault in ('bank-one-full','input-full'):
        m.alloc(251,1,owner=16,page=4)
        if fault=='input-full':
            m.alloc(12,0,owner=16,page=0x54)
            m.alloc(127,0,owner=16,page=0x80)
    else: m.alloc(2,1,owner=16,page=0x80)
    foreign=[]
    for slot in range(32):
        at=0x3c00+slot*8;record=bytes(ram[at:at+8])
        if record[0]==16:
            bank,page,pages=record[1:4]
            foreign.append((at,record,bank,page*256,bytes(m.bus.ram[bank][page*256:(page+pages)*256])))
    initial_stats=m.stats()
    m.bus.guard=True
    io=StreamIEC(m,{(8,b'PACKED',b'P'):image});io.add(6,9,2)
    ram[0x3d21:0x3d23]=bytes([8,6]);ram[0x3d40:0x3d46]=b'PACKED'
    parameters=bytes(ram[0xb7:0xbd])+bytes(ram[0xc6:0xc8])+bytes([ram[0x9d]])
    borrower=(bytes(ram[0xfb:0xfd]),ram[0x2aa],ram[0x2b9])
    entry=validate(original)['entry'];outer_entry=validate(image)['entry'] if not expected_loader else -1
    cpu=MPU(memory=m.bus,pc=RUN);cpu.sp=0xe0;cpu.p=0x20|flags;cpu.stPushWord(0xaff)
    entered=False;wrapper=False;temporary_fetches=0;delivered=0;injected=False
    for steps in range(16000000):
        if cpu.pc==0xb00 and cpu.sp==0xe0:break
        if cpu.pc==outer_entry:
            wrapper=True;assert set(io.handles)=={6}
        if wrapper and not injected and fault in ('read-handle','write-handle','free-handle'):
            if cpu.pc=={'read-handle':0x1c26,'write-handle':0x1c29,'free-handle':0x1c23}[fault]:
                ram[0x3d05]^=128;injected=True
        if 0x5000<=cpu.pc<0x6000:
            slot=ram[0x3800+cpu.pc//256]
            assert 1<=slot<=32 and ram[0x3c00+(slot-1)*8]==32, 'executed released startup code'
            assert ram[0x3d12]==0
            temporary_fetches+=1
        if cpu.pc==entry and wrapper:
            assert not expected_exit and not expected_loader
            assert ram[0x6000:0x6020]==image[2:34]
            assert ram[0x6020:0x6000+len(original)-2]==original[34:]
            owned=[bytes(ram[at:at+8]) for at in range(0x3c00,0x3d00,8) if ram[at]==32]
            assert len(owned)==1 and owned[0][1:4]==bytes([0,0x60,original[12]])
            assert not any(ram[0x3850:0x3860])
            assert set(io.handles)=={6}
            assert m.bus.config==0x0e and not cpu.p&12 and cpu.a==0
            entered=True
            if not execute: break
        if interrupts and 0x5000<=cpu.pc<0x6000 and temporary_fetches%8192==0 and not cpu.p&4:
            if delivered&1:cpu.nmi()
            else:cpu.irq()
            delivered+=1
        if not io.stub(cpu): cpu.step()
    else:raise AssertionError(f'packed startup did not finish: {cpu.pc:04x}')
    if not expected_exit and not expected_loader:assert entered and temporary_fetches
    else:assert not entered
    if execute or expected_exit or expected_loader:
        assert cpu.pc==0xb00 and cpu.sp==0xe0
        assert cpu.p&12==flags&12
        assert ram[0x3d27]==expected_loader and ram[0x3d24]==expected_exit
        assert m.stats()==initial_stats
        assert not any(ram[at]==32 for at in range(0x3c00,0x3d00,8))
    assert set(io.handles)=={6} and io.handles[6]['device']==9
    assert borrower==(bytes(ram[0xfb:0xfd]),ram[0x2aa],ram[0x2b9])
    assert parameters==bytes(ram[0xb7:0xbd])+bytes(ram[0xc6:0xc8])+bytes([ram[0x9d]])
    assert not m.bus.io_writes
    assert ram[0xb10]==delivered&255
    if interrupts:assert delivered>10
    if fault in ('read-handle','write-handle','free-handle'):assert injected
    for at,record,bank,address,data in foreign:
        assert bytes(ram[at:at+8])==record and m.bus.ram[bank][address:address+len(data)]==data
    return dict(passed=True,instructions=steps,temporary_fetches=temporary_fetches,
                wrapper_entered=wrapper,original_entered=entered,loader_error=expected_loader,exit_code=expected_exit,
                interrupts=delivered)


def fixture():
    random_bytes=random.Random(791).randbytes(1500)
    body=(b'\xa9\0\x60'+random_bytes*6)[:8096]
    h=b'NAPP'+bytes([1,1,0,0])+(len(body)+32).to_bytes(2,'little')+bytes([32,0,32,0,0,0])+b'PACK FIXTURE'.ljust(16,b'\0')
    return seal(b'\0\x60'+h+body)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--apps',action='store_true');args=parser.parse_args()
    report=dict(passed=False,physical_hardware_io=False,cases=[])
    def save():args.report.write_text(json.dumps(report,indent=2)+'\n')
    def case(name,*values,**options):
        result=run(*values,**options);result['name']=name;report['cases'].append(result);save()
        print('PASS',name,result['instructions'],flush=True)
    try:
        raw=fixture();packed=build(raw);assert decode(packed)==raw
        case('fixture-complete',packed,raw,execute=True)
        case('fixture-interrupts-decimal-caller',packed,raw,execute=True,interrupts=True,flags=8)
        case('temporary-code-unavailable',packed,raw,fault='code-full',expected_exit=2)
        case('temporary-input-bank-zero-fallback',packed,raw,fault='bank-one-full',execute=True)
        case('temporary-input-unavailable',packed,raw,fault='input-full',expected_exit=2)
        for operation in ('read','write','free'):
            case('temporary-'+operation+'-failure',packed,raw,fault=operation+'-handle',expected_exit=4)
        corrupt=bytearray(packed);corrupt[-1]^=1
        case('outer-checksum-rejects',bytes(corrupt),raw,expected_loader=20)
        case('outer-truncation-rejects',packed[:-1],raw,expected_loader=18)
        case('outer-extension-rejects',packed+b'\0',raw,expected_loader=19)
        malformed=seal(corrupt)
        case('decoded-length-rejects',malformed,raw,expected_exit=16)
        altered=bytearray(packed)
        payload=int.from_bytes(altered[74:76],'little')-0x6000+2
        literal=altered.find(b'\xa9\0\x60',payload)
        assert literal>=payload
        altered[literal+1]=1
        case('decoded-checksum-rejects',seal(altered),raw,expected_exit=20)
        altered=bytearray(packed);altered[12]=16
        case('smaller-declared-allocation-rejects',seal(altered),raw,expected_exit=16)
        if args.apps:
            report['sizes']={}
            for name in ('desktop','calc','editor','files','controls','claude','paint','sheet'):
                original=(ROOT/'target/native-desktop'/f'{name}.prg').read_bytes()
                if original[34:38]==b'NPZ2':
                    image=original;original=decode(image)
                else:
                    runtime_end=json.loads((ROOT/'target/native-desktop'/f'{name}.json').read_text())['runtime_end'] if name in ('claude','sheet') else None
                    image=build(original,runtime_end=runtime_end)
                report['sizes'][name]=dict(raw=len(original),packed=len(image),sha256=hashlib.sha256(image).hexdigest())
                case(name+'-body-and-cleanup',image,original)
        report['passed']=True
    finally:save()


if __name__=='__main__':main()
