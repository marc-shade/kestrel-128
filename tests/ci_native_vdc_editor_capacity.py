#!/usr/bin/env python3
"""Editor preserves its original at the RAM limit and uses REU capacity when present."""
import argparse
import json
from pathlib import Path

from ci_native_vdc_editor import Editor,gui,VDCBus
from ci_native_reu_calc import CalculatorBus,COMPONENT_PAGES


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--size',type=int,choices=(16,64),required=True)
    parser.add_argument('--reu',action='store_true')
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args();original=gui.PointerBus
    report=dict(passed=False,physical_hardware_io=False,cases=[])
    try:
        base=CalculatorBus if args.reu else VDCBus
        gui.PointerBus=type('CapacityVDC',(base,),dict(size=args.size,addressing=64))
        raw=(b'ROW 12345\r'*7000)[:66053]
        p=Editor({(9,b'LARGE',b'S'):raw},device=9);p.check(b'',0,False)
        free=bytes(p.ram[0x3800:0x3a00]).count(0)
        assert free==426-96-16-36-COMPONENT_PAGES-(0 if args.reu else (64 if args.size==16 else 72)),free
        p.type('KEPT');p.check(b'KEPT',4,True)
        before=p.state();heap=p.m.stats()
        p.key(0x85);p.type('LARGE');p.key(13);p.check(b'KEPT',4,True,mode=5)
        step=p.cpu.step;failure=p.symbol('ed_open_no_memory');failed=[]
        def observe():
            if p.cpu.pc==failure:
                pending=p.state(p.value('ed_pending'))
                failed.append(dict(bytes=p.number('ed_io_pos'),chunks=pending['chunks'],capacity=pending['capacity']))
            return step()
        p.cpu.step=observe
        try:p.key(ord('Y'))
        finally:p.cpu.step=step
        if args.reu:
            assert not failed
            p.check(raw,0,False,name='LARGE')
            assert p.state()['backing']==1 and p.m.stats()==heap
            saved,cursor,name=raw,0,'REU bypasses the main-RAM document limit'
        else:
            assert len(failed)==1 and failed[0]['bytes']==failed[0]['capacity']
            assert failed[0]['chunks']>0 and failed[0]['capacity']<len(raw)
            p.check(b'KEPT',4,True,status=3)
            assert p.state()==before and p.m.stats()==heap
            saved,cursor,name=b'KEPT',4,'transactional Open at main-RAM limit'
        assert p.state(p.value('ed_active')^128)['chunks']==0
        p.prompt(0x86,'COPY');p.check(saved,cursor,False,status=1,name='COPY')
        assert bytes(p.io.files[9,b'COPY',b'S'])==saved and bytes(p.io.files[9,b'LARGE',b'S'])==raw
        p.exit();p.restored()
        report['cases'].append(dict(name=name,passed=True,
            vdc_kib=args.size,reu_screen_backing=args.reu,free_pages=free,pending_limit=failed[0] if failed else None,
            retained_bytes=len(saved),instructions=p.instructions,keys=p.events))
        report['passed']=True;print('PASS: capacity rollback',args.size,args.reu,free,failed,flush=True)
    finally:
        gui.PointerBus=original;args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
