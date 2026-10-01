#!/usr/bin/env python3
"""Search startup and partial Replace All retain exact document state on VDC faults."""
import argparse
import json
from pathlib import Path

from ci_native_vdc_editor_recovery import RecoveryEditor,paused,ignored,restore,reopen_and_exit
from ci_native_vdc_editor import gui,VDCBus


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=('initial','replace'),required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args();original=gui.PointerBus
    report=dict(passed=False,physical_hardware_io=False,cases=[])
    try:
        gui.PointerBus=type('SearchVDC',(VDCBus,),dict(size=16,addressing=64))
        raw=(b'ROW 12345\r'*1100)[:10240]
        p=RecoveryEditor({(9,b'SOURCE',b'S'):raw},device=9);p.prompt(0x85,'SOURCE')
        document_view=dict(data=raw,cursor=0,name='SOURCE',dirty=False,
            view=p.number('ed_view'),horizontal=p.number('ed_horizontal'))
        if args.case=='initial':
            p.key(6);p.type('ZZZ');trigger=13;position=0
        else:
            p.key(18);p.type('ROW');p.key(13);p.type('NEW');p.key(13)
            assert p.value('ed_mode')==9
            trigger=ord('A');position=256
        step=p.cpu.step;field=p.symbol('ed_paint_fields');injected=[]
        def stall():
            if p.cpu.pc==field and p.value('ed_status')==16 and p.number('ed_probe')==position and not injected:
                p.bus.stall=True;injected.append(position)
            return step()
        p.cpu.step=stall
        try:p.key(trigger)
        finally:p.cpu.step=step
        assert injected==[position] and p.value('ed_s_running') and p.number('ed_probe')==position
        want=raw[:position].replace(b'ROW',b'NEW')+raw[position:]
        count=raw[:position].count(b'ROW')
        assert p.contents()==want and p.number('ed_s_count')==count
        paused(p,busy=2,document_view=document_view);ignored(p)
        assert restore(p,lambda:p.key(27))
        p.check(want,dirty=bool(count),status=18 if count else 8)
        assert not p.value('ed_s_running') and p.number('ed_s_count')==count
        p.prompt(0x86,'COPY');p.check(want,dirty=False,status=1,name='COPY')
        assert bytes(p.io.files[9,b'COPY',b'S'])==want and bytes(p.io.files[9,b'SOURCE',b'S'])==raw
        reopen_and_exit(p)
        report['cases'].append(dict(name=args.case,passed=True,position=position,replacements=count,
            instructions=p.instructions,keys=p.events,vdc_kib=16,initial_addressing=64))
        report['passed']=True;print('PASS: search recovery',args.case,position,count,flush=True)
    finally:
        gui.PointerBus=original;args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
