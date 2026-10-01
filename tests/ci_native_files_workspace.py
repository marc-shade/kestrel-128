#!/usr/bin/env python3
"""Packed Files startup reserves every scratch page without touching other owners."""
import argparse
import json
from pathlib import Path
from py65.devices.mpu6502 import MPU
from ci_native_heap import Machine,ROOT
from ci_native_apps import RUN
from ci_native_files import StreamIEC
from ci_native_app_pack import OwnedBus
from native_app_pack import decode
from native_image import validate
from hwlib import lst_symbol


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args();report=dict(passed=False,physical_hardware_io=False,cases=[])
    image=(ROOT/'target/native-desktop/files.prg').read_bytes();entry=validate(decode(image))['entry']
    initialized=lst_symbol('native-desktop/files','nk_install');exit_entry=lst_symbol('native-desktop/files','N_EXIT')
    try:
        for bank,page,expected in ((0,0x54,2),(0,0x5f,2),(1,0x54,0)):
            m=Machine();m.bus.__class__=OwnedBus;ram=m.ram
            token=m.alloc(1,bank,owner=16,page=page)
            foreign=bytes((i*73+29)&255 for i in range(256));m.bus.ram[bank][page*256:(page+1)*256]=foreign
            record_at=0x3c00+(token[0]-1)*8;record=bytes(ram[record_at:record_at+8]);stats=m.stats()
            keys=bytes(ram[0x1000:0x1100]);callback=bytes(ram[0x033c:0x033e])
            io=StreamIEC(m,{(8,b'FILES',b'P'):image});io.add(6,9,2)
            ram[0x3d21:0x3d23]=bytes([8,5]);ram[0x3d40:0x3d45]=b'FILES';m.bus.guard=True
            cpu=MPU(memory=m.bus,pc=RUN);cpu.sp=0xe0;cpu.p=0x20;cpu.stPushWord(0xaff)
            entered=ready=False
            for steps in range(16000000):
                if cpu.pc==0xb00 and cpu.sp==0xe0:break
                if cpu.pc==entry:entered=True
                if entered and cpu.pc==initialized:
                    assert not expected and entered and not ready
                    table=bytes(ram[0x3850:0x3860]);assert len(set(table))==1 and 1<=table[0]<=32
                    own=bytes(ram[0x3c00+(table[0]-1)*8:0x3c08+(table[0]-1)*8])
                    assert own[:4]==bytes([32,0,0x50,16])
                    assert ram[0x5000:0x6000]==bytes(4096)
                    ready=True;cpu.a=0;cpu.pc=exit_entry
                if not io.stub(cpu):cpu.step()
            else:raise AssertionError(('Files startup did not finish',hex(cpu.pc)))
            assert entered and ready==(not bool(expected))
            assert ram[0x3d24]==expected and ram[0x3d27]==0 and not ram[0x3d20]
            assert m.stats()==stats and set(io.handles)=={6} and io.handles[6]['device']==9
            assert bytes(ram[record_at:record_at+8])==record and bytes(m.bus.ram[bank][page*256:(page+1)*256])==foreign
            assert bytes(ram[0x1000:0x1100])==keys and bytes(ram[0x033c:0x033e])==callback
            assert not any(ram[at]==32 for at in range(0x3c00,0x3d00,8))
            report['cases'].append(dict(name='conflicting scratch page refuses before input ownership' if expected else
                'same address in the other bank permits sixteen initialized scratch pages and complete cleanup',
                passed=True,instructions=steps,foreign_bank=bank,foreign_page=page,exit_code=expected))
            print('PASS:',report['cases'][-1]['name'],flush=True)
        report['passed']=True
    finally:args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
