#!/usr/bin/env python3
"""Refuse an unavailable Ultimate workspace before touching input or displays."""
import argparse
import json
from pathlib import Path

from py65.devices.mpu6502 import MPU
from ci_native_heap import Machine, ROOT
from ci_native_app_pack import OwnedBus
from ci_native_files import StreamIEC
from hwlib import lst_symbol


def run(fault):
    m=Machine();m.bus.__class__=OwnedBus;m.bus.guard=True;ram=m.ram
    image=(ROOT/'target/native-desktop/controls.prg').read_bytes()
    io=StreamIEC(m,{(8,b'ULTIMATE',b'P'):image})
    ram[0x3d21:0x3d23]=bytes([8,8]);ram[0x3d40:0x3d48]=b'ULTIMATE'
    keys=bytes(ram[0x1000:0x1100]);callback=bytes(ram[0x033c:0x033e])
    cpu=MPU(memory=m.bus,pc=0x1c38);cpu.sp=0xe0;cpu.p=0x20;cpu.stPushWord(0xaff)
    workspace=lst_symbol('native-desktop/controls','ug_workspace')
    entered=False;injected=False;foreign=[]
    for steps in range(16000000):
        if cpu.pc==0xb00 and cpu.sp==0xe0:break
        if cpu.pc==workspace:
            entered=True;assert not io.handles
            stack=bytes(ram[0x100:0x200])
            if fault=='occupied':m.alloc(1,0,owner=77,page=0x50)
            if fault=='slots':
                for _ in range(31):m.alloc(1,1,owner=77)
            ram[0x100:0x200]=stack
            for at in range(0x3c00,0x3d00,8):
                record=bytes(ram[at:at+8])
                if record[0]==77:
                    bank,page,pages=record[1:4]
                    foreign.append((at,record,bank,page*256,bytes(m.bus.ram[bank][page*256:(page+pages)*256])))
        if entered and fault=='fill' and not injected and cpu.pc==0x1c2c:
            ram[0x3d05]^=128;injected=True
        if io.stub(cpu):continue
        assert cpu.pc not in (0xffe4,0xffd2,0xff5f),('input or presentation before successful workspace setup',hex(cpu.pc),entered,steps)
        cpu.step()
    else:raise AssertionError(('startup did not return',hex(cpu.pc)))
    assert entered and (fault!='fill' or injected)
    assert ram[0x3d24]=={'occupied':2,'slots':3,'fill':4}[fault]
    assert not ram[0x3d20] and not ram[0x3d23] and not io.handles
    assert not any(ram[at]==32 for at in range(0x3c00,0x3d00,8))
    assert bytes(ram[0x1000:0x1100])==keys and bytes(ram[0x033c:0x033e])==callback
    for at,record,bank,start,data in foreign:
        assert bytes(ram[at:at+8])==record
        assert bytes(m.bus.ram[bank][start:start+len(data)])==data
    assert m.bus.config==0x0e and not cpu.p&12
    return dict(name=fault,passed=True,instructions=steps,foreign_allocations=len(foreign),exit_code=ram[0x3d24])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args();report=dict(passed=False,physical_hardware_io=False,cases=[])
    try:
        for fault in ('occupied','slots','fill'):
            report['cases'].append(run(fault));print('PASS:',fault,flush=True)
        report['passed']=True
    finally:args.report.write_text(json.dumps(report,indent=2)+'\n')
