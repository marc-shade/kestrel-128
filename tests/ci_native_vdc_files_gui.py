#!/usr/bin/env python3
"""Run complete Files mouse/keyboard workflows with independent VDC oracles."""
import argparse
import json
from pathlib import Path
import sys
from ci_native_vdc_files import Files,gui,VDCBus


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--size',type=int,choices=(16,64),required=True)
    parser.add_argument('--case',choices=('keyboard','mouse','picker','fields','ultimate','longfields','gestures','cancel'),required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    original_bus,original_app,argv=gui.PointerBus,gui.GraphicalFiles,sys.argv
    try:
        gui.PointerBus=type('FilesVDC',(VDCBus,),dict(size=args.size))
        gui.GraphicalFiles=type('GraphicalVDCFiles',(Files,),dict(instruction_limit=120000000))
        sys.argv=[argv[0],'--case',args.case,'--report',str(args.report)]
        gui.main()
        report=json.loads(args.report.read_text());report['vdc_kib']=args.size
        report['complete_vic_and_vdc_canvases']=sum(case['views'] for case in report['cases'])
        args.report.write_text(json.dumps(report,indent=2)+'\n')
    finally:
        gui.PointerBus,gui.GraphicalFiles,sys.argv=original_bus,original_app,argv


if __name__=='__main__':main()
