#!/usr/bin/env python3
"""Paint's REU display backing stays separate from picture, undo and file I/O."""
import argparse
import json
from pathlib import Path
from ci_native_vdc_paint import Paint,GraphicalPaint,heap
from ci_native_reu_calc import CalculatorBus,component,COMPONENT_PAGES
from ci_native_paint_files import pattern
from native_paint_format import encode


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args();original=heap.Bus
    report=dict(passed=False,physical_hardware_io=False,cases=[])
    def start(**options):
        heap.Bus=type('PaintREU',(CalculatorBus,),options)
        return Paint(files={(9,b'PICTURE',b'S'):encode(pattern(61))},device=9)
    def done(name,p,**extra):
        report['cases'].append(dict(name=name,passed=True,instructions=p.instructions,keys=p.events,
                                   dmas=len(p.bus.reu_transactions),**extra))
        args.report.write_text(json.dumps(report,indent=2)+'\n');print('PASS:',name,flush=True)
    try:
        for size,kib in ((16,128),(64,16384)):
            p=start(size=size,reu_kib=kib);p.check()
            assert p.value('vs_reu')==p.value('ru_active')==1
            base,pages=p.value('vd_base')*256,p.value('vd_pages')
            assert p.bus.reu_ram[:pages*256]==p.bus.original[0][base:base+pages*256]
            assert p.bus.reu_ram[pages*256:]==p.bus.reu_original[pages*256:]
            token=bytes(p.ram[p.symbol('vs_token'):p.symbol('vs_token')+8])
            assert component(p,'vs_token',8)==token
            free=sum(p.m.stats()[:2]);assert free==426-p.image[12]-72-36-COMPONENT_PAGES-10
            p.key(ord('O'));p.mirror();p.key(13);p.check();p.clean()
            assert p.document()==pattern(61) and component(p,'vs_token',8)==token
            assert sum(p.m.stats()[:2])==free
            p.name(b'NEW',device=9);p.key(ord('S'));p.key(13);p.check();p.clean()
            assert bytes(p.io.files[9,b'NEW',b'S'])==encode(pattern(61))
            p.close();p.restored()
            assert p.bus.reu_ram[pages*256:]==p.bus.reu_original[pages*256:]
            done(f'{size} KiB VDC / {kib} KiB REU: retained snapshot, complete picture open/save and exact restore',p,free_pages=free)
        p=start(size=64);p.key(32);p.check();document,undo=p.document(),p.document(1)
        p.bus.reu_fault_from=len(p.bus.reu_transactions)+1
        p.key(27);p.key(ord('D'))
        assert p.value('vd_phase')==2 and p.value('vd_fault')==17
        owned,stack=p.m.stats(),p.cpu.sp
        for key in (32,ord('S'),27):
            p.key(key);assert p.m.stats()==owned and p.cpu.sp==stack
            assert p.document()==document and p.document(1)==undo and p.value('pd_dirty')
        p.bus.reu_fault_from=None;p.key(27);GraphicalPaint.check(p)
        assert p.document()==document and p.value('pd_dirty')
        p.bus.original=None;p.key(ord('R'));p.check();p.close();p.restored()
        done('failed REU snapshot read retains unsaved picture and every owner until restoration succeeds',p)
        p=start(size=16,fault_start=2)
        assert p.value('vd_phase')==1 and p.value('ru_probe_live') and p.value('pa_status')==14
        GraphicalPaint.check(p);owned=p.m.stats();document=p.document()
        p.key(32);p.key(27);assert p.m.stats()==owned and p.document()==document
        p.bus.reu_fault_from=None;p.key(27,exited=True);p.restored()
        assert p.bus.reu_ram==p.bus.reu_original and not p.value('ru_probe_live')
        done('failed REU capacity-probe restoration retains all data for Escape recovery',p)
        report['passed']=True
    finally:
        heap.Bus=original;args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
