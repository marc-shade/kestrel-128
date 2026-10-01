#!/usr/bin/env python3
"""Files keeps REU display backing across copies, pickers and recovery."""
import argparse
import json
from pathlib import Path
from ci_native_vdc_files import Files,gui
from ci_native_reu_calc import CalculatorBus,component,COMPONENT_PAGES


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--recovery-only',action='store_true')
    args=parser.parse_args();original=gui.PointerBus
    report=dict(passed=False,physical_hardware_io=False,cases=[])
    raw=bytes(range(256))*6+b'END'
    def start(**options):
        gui.PointerBus=type('FilesREU',(CalculatorBus,),options)
        return Files({(9,b'SOURCE',b'S'):raw})
    def done(name,p,**extra):
        report['cases'].append(dict(name=name,passed=True,instructions=p.instructions,keys=p.events,
                                   dmas=len(p.bus.reu_transactions),**extra))
        args.report.write_text(json.dumps(report,indent=2)+'\n');print('PASS:',name,flush=True)
    try:
        for size,kib in ((16,128),(64,16384)):
            if args.recovery_only:continue
            p=start(size=size,reu_kib=kib);p.browser()
            assert p.value('vs_reu')==p.value('ru_active')==1
            base,pages=p.value('vd_base')*256,p.value('vd_pages')
            assert p.bus.reu_ram[:pages*256]==p.bus.original[0][base:base+pages*256]
            assert p.bus.reu_ram[pages*256:]==p.bus.reu_original[pages*256:]
            token=p.data('vs_token',8);assert component(p,'vs_token',8)==token
            free=sum(p.m.stats()[:2]);assert free==426-p.image[12]-36-COMPONENT_PAGES-16-37
            p.key(ord('C'));p.rename('COPY');p.copy(b'SOURCE',b'COPY')
            p.key(0x88);p.mirror();p.key(27);p.copy(b'SOURCE',b'COPY')
            assert component(p,'vs_token',8)==token and sum(p.m.stats()[:2])==free
            p.key(13);p.copy(b'SOURCE',b'COPY',copied=len(raw),verified=len(raw),status=1)
            assert bytes(p.io.files[9,b'COPY',b'S'])==raw
            assert bytes(p.io.files[9,b'SOURCE',b'S'])==raw
            assert component(p,'vs_token',8)==token
            p.key(27);p.browser();p.key(27,exited=True);p.restored()
            assert p.bus.reu_ram[pages*256:]==p.bus.reu_original[pages*256:]
            done(f'{size} KiB VDC / {kib} KiB REU: retained snapshot, verified copy, picker and exact restore',
                 p,free_pages=free,file_bytes=len(raw))
        p=start(size=64);p.browser()
        p.bus.reu_fault_from=len(p.bus.reu_transactions)+1;p.key(27)
        assert p.value('vd_phase')==2 and p.value('vd_fault')==17
        owned=p.m.stats();p.poll()
        assert p.m.stats()==owned and p.value('fg_vdc_warned')
        stack=p.cpu.sp
        for key in (ord('C'),ord('I'),13,27,27):
            p.key(key);assert p.m.stats()==owned and p.cpu.sp==stack
            assert not p.value('fc_active') and bytes(p.io.files[9,b'SOURCE',b'S'])==raw
        p.bus.reu_fault_from=None;p.key(27,exited=True);p.restored()
        done('failed REU snapshot reads retain Files, input and every owner until Escape restores',p)
        p=start(size=16,fault_start=2)
        assert p.value('vd_phase')==1 and p.value('ru_probe_live')
        owned=p.m.stats();p.key(ord('C'));p.key(27)
        assert p.m.stats()==owned and not p.value('fc_active') and p.value('ru_probe_live')
        p.bus.reu_fault_from=None;p.key(27,exited=True);p.restored()
        assert p.bus.reu_ram==p.bus.reu_original and not p.value('ru_probe_live')
        done('failed REU capacity-probe restoration retains all bytes until Escape recovery',p)
        report['passed']=True
    finally:
        gui.PointerBus=original;args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
