#!/usr/bin/env python3
"""Display failures preserve Paint's unsaved picture and exact resource owners."""
import argparse
import json
from pathlib import Path
from ci_native_vdc_paint import Paint, heap, VDCBus, GraphicalPaint


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--group',choices=('all','display','surface'),default='all')
    args=parser.parse_args();original=heap.Bus
    report=dict(passed=False,physical_hardware_io=False,cases=[])
    def done(name,p):
        report['cases'].append(dict(name=name,passed=True,instructions=p.instructions,keys=p.events))
        args.report.write_text(json.dumps(report,indent=2)+'\n');print('PASS:',name,flush=True)
    try:
        heap.Bus=VDCBus
        if args.group in ('all','display'):
            p=Paint();p.key(32);p.check();document,undo=p.document(),p.document(1)
            p.bus.stall=True;p.key(ord('R'))
            assert p.value('vd_phase') and p.value('vd_fault') and p.value('pa_status')==14
            GraphicalPaint.check(p);owned=p.m.stats();stack=p.cpu.sp
            for key in (32,ord('U'),ord('S'),ord('O'),27,27):
                p.key(key)
                assert p.document()==document and p.document(1)==undo and p.value('pd_dirty')
                assert p.m.stats()==owned and p.cpu.sp==stack and not p.value('pa_picker_active')
            p.bus.stall=False;p.key(27)
            assert not p.value('vd_phase') and p.value('pa_mode')==1
            GraphicalPaint.check(p);p.key(13);GraphicalPaint.check(p)
            assert p.document()==document and p.value('pd_dirty')
            p.bus.original=None;p.key(ord('R'));p.check();p.close();p.restored()
            done('stalled display freezes edits and retains unsaved image; Escape restores and Refresh resumes graphics',p)
        if args.group in ('all','surface'):
            p=Paint();p.check();document=p.document();active=p.symbol('pa_picker_active')
            original_stub=p.io.stub;injected=[];restored=[];output=p.output
            def bad_fill(cpu):
                if p.ram[active] and cpu.pc==0x1c2c and not injected:
                    p.ram[0x3d05]^=128;injected.append(True)
                return original_stub(cpu)
            def observe(value):
                if injected and not restored and p.ram[0xd7]&128:
                    assert p.bus.video_ram==p.bus.original[0], 'VDC restored before picker text'
                    restored.append(True)
                output(value)
            p.io.stub=bad_fill;p.output=observe;p.key(ord('O'))
            assert injected and restored and p.value('pa_picker_active') and not p.value('vd_phase')
            assert p.document()==document
            p.io.stub=original_stub;p.key(27);GraphicalPaint.check(p);p.output=output
            p.bus.original=None;p.key(ord('R'));p.check();p.close();p.restored()
            done('failed picker surface restores VDC before text fallback and keeps the picture',p)
        report['passed']=True
    finally:
        heap.Bus=original;args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
