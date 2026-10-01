#!/usr/bin/env python3
"""Exercise the actual bank-1 VDC component through the checked native loader."""
import argparse
import json
from pathlib import Path
import tempfile

from ci_native_banked import Banked,assemble,seal
from native_banked_bus import BankedBus
from ci_native_vdc_desktop import VDCBus
from launcher_scene import surface
from native_vdc_scene import bitmap as desktop_bitmap,attributes as desktop_attributes
from native_vdc_mirror import bitmap as mirror_bitmap,attributes as mirror_attributes


class Service(Banked):
    bus_type = type('ServiceBus',(BankedBus,VDCBus),{})

    def arguments(self,mode=0,selected=0,error=0,x=0,y=0,seen=0,dirty=True):
        data=(bytes([mode])+self.surface+bytes([selected,error,seen,x&255,x>>8,y])+
              bytes([int(dirty)])*25)
        self.ram[0x3a00:0x3a00+len(data)]=data

    def state(self):
        self.call('call',operation=5)
        return bytes(self.ram[0x3a00:0x3a29])


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    work=Path(tempfile.mkdtemp(prefix='kestrel-vdc-service-cpu-'))
    parent,ps=assemble(work,'parent','tests/fixtures/native-banked.asm')
    raw,bs=assemble(work,'provider','src/native/vdc-service.asm');provider=seal(raw)
    report=dict(passed=False,physical_hardware_io=False,cases=[],work=str(work))
    try:
        for size in (16,64):
            for mode in (0,1):
                Service.bus_type=type('ServiceBus',(BankedBus,VDCBus),dict(size=size))
                p=Service(parent,provider,ps,bs)
                p.surface=p.m.alloc(36,0,owner=32,page=0xc0)
                original_reu=bytes(p.bus.reu_ram)
                original_vdc=bytes(p.bus.video_ram)
                p.ram[0xc000:0xe400]=source=surface(2)
                p.load();p.arguments(mode=mode,selected=2);p.call('call',operation=1)
                state=p.state();assert state[:4]==bytes([2,1,size==64,0]),state[:4]
                base=0x4000 if size==64 else 0
                bitmap=desktop_bitmap(2) if mode else mirror_bitmap(source,size==64)
                assert p.bus.bytes(base,16000)==bitmap
                if size==64:assert p.bus.bytes(0x8000,2000)==(desktop_attributes(2) if mode else mirror_attributes(source))
                assert state[29]==state[38]==1
                for error in (1,17,255):
                    p.ram[0xc000:0xe400]=updated=surface(2,error)
                    p.arguments(mode=mode,selected=2,error=error)
                    p.call('call',operation=2)
                    expected=desktop_bitmap(2,error) if mode else mirror_bitmap(updated,size==64)
                    assert p.bus.bytes(base,16000)==expected,('error status',mode,error)
                p.ram[0xc000:0xe400]=source
                p.arguments(mode=mode,selected=2,x=319,y=199,seen=1,dirty=False)
                p.call('call',operation=3);assert p.state()[25:29]==bytes([1,63,1,199])
                p.bus.stall=True;p.arguments(mode=mode,selected=3)
                p.call('call',17,operation=2);assert p.state()[3]==17
                p.call('call',17,operation=4)
                p.bus.stall=False;p.call('call',operation=4)
                state=p.state();assert state[0]==state[1]==state[7]==state[29]==state[38]==0
                assert p.bus.video_ram==original_vdc
                # Only the snapshot allocation's exact VDC bytes change in REU.
                count=(72 if size==64 else 64)*256
                assert p.bus.reu_ram[:count]==original_vdc[base:base+count]
                assert p.bus.reu_ram[count:]==original_reu[count:]
                p.call('close');p.m.select(p.surface,32);p.m.invoke('free')
                assert p.m.stats()[1:]==(251,31)
                report['cases'].append(dict(vdc_kib=size,mode=mode,calls=p.calls,instructions=p.instructions))
                print('PASS: banked VDC',size,mode,flush=True)
        report['passed']=True
    finally:
        args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
