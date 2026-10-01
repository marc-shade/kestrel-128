#!/usr/bin/env python3
"""Paint remains usable when its VDC hardware or component cannot be opened."""
import argparse
import json
from pathlib import Path
from ci_native_vdc_paint import Paint,GraphicalPaint,heap,VDCBus


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args();original=heap.Bus
    report=dict(passed=False,physical_hardware_io=False,cases=[])
    try:
        for case in ('hardware','component','corrupt'):
            heap.Bus=type('PaintFallback',(VDCBus,),dict(present=case!='hardware'))
            component=True
            if case=='component':component=False
            elif case=='corrupt':
                component=bytearray((Path(__file__).resolve().parents[1]/'target/native-desktop/vdsvc.prg').read_bytes())
                component[-1]^=1
            p=Paint(vdc_component=component)
            assert p.value('vd_phase')==p.value('bk_state')==0 and p.value('pa_bitmap')==1
            GraphicalPaint.check(p);p.key(32);GraphicalPaint.check(p)
            assert p.document()[0]==128 and p.value('pd_dirty')
            p.key(ord('U'));GraphicalPaint.check(p);assert not p.value('pd_dirty')
            p.key(ord('S'));GraphicalPaint.check(p);p.key(27);GraphicalPaint.check(p)
            p.close();p.restored()
            report['cases'].append(dict(name=case+' refusal preserves VIC drawing, undo, text controls and cleanup',
                passed=True,instructions=p.instructions,keys=p.events))
            print('PASS:',report['cases'][-1]['name'],flush=True)
        report['passed']=True
    finally:
        heap.Bus=original;args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
