#!/usr/bin/env python3
"""Ultimate VDC backing in REU, bounded fallback and retained recovery."""
import argparse
import json
from pathlib import Path
from ci_native_vdc_controls import Panel, GraphicalPanel, heap
from ci_native_reu_calc import CalculatorBus, component, COMPONENT_PAGES


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args();original=heap.Bus
    report=dict(passed=False,physical_hardware_io=False,cases=[])

    def start(**options):
        heap.Bus=type('UltimateREU',(CalculatorBus,),options)
        return Panel()

    def done(name,p,**extra):
        report['cases'].append(dict(name=name,passed=True,instructions=p.instructions,
            keys=p.events,dmas=len(p.bus.reu_transactions),**extra))
        args.report.write_text(json.dumps(report,indent=2)+'\n')
        print('PASS:',name,flush=True)

    try:
        for size,kib in ((16,128),(64,16384)):
            p=start(size=size,reu_kib=kib);p.check()
            assert p.value('vs_reu')==p.value('ru_active')==1
            base,pages=p.value('vd_base')*256,p.value('vd_pages')
            assert p.bus.reu_ram[:pages*256]==p.bus.original[0][base:base+pages*256]
            assert p.bus.reu_ram[pages*256:]==p.bus.reu_original[pages*256:]
            token=bytes(p.ram[p.symbol('vs_token'):p.symbol('vs_token')+8])
            assert component(p,'vs_token',8)==token and component(p,'ru_cookie',4)==token[4:]
            free=sum(p.m.stats()[:2]);assert free==426-p.image[12]-11-36-COMPONENT_PAGES
            p.key(ord('D'));p.check();p.key(0x11);p.check()
            p.key(ord('M'));p.mirror();p.key(27);p.check()
            assert sum(p.m.stats()[:2])==free
            assert component(p,'vs_token',8)==token
            p.key(27,exited=True);p.restored()
            assert p.value('ru_active')==p.value('vs_reu')==0
            assert p.bus.reu_ram[pages*256:]==p.bus.reu_original[pages*256:]
            done(f'{size} KiB VDC / {kib} KiB REU: picker retains one backup, exact restore',p,free_pages=free)

        p=start(size=64);p.check()
        p.bus.reu_fault_from=len(p.bus.reu_transactions)+1
        owned,stack=p.m.stats(),p.cpu.sp
        for _ in range(2):
            p.key(27)
            assert p.value('vd_phase')==2 and p.value('vd_fault')==17
            assert p.m.stats()==owned and p.cpu.sp==stack and not p.device.mutations
        p.bus.reu_fault_from=None
        p.key(27,exited=True);p.restored()
        done('failed snapshot reads keep all owners until Escape restores',p)

        p=start(size=16,fault_start=2)
        assert p.value('vd_phase')==1 and p.value('ru_probe_live') and p.value('ug_notice')==11
        GraphicalPanel.check(p)
        owned=p.m.stats();p.key(ord('D'));p.key(27)
        assert p.m.stats()==owned and p.value('ru_probe_live') and not p.device.mutations
        p.bus.reu_fault_from=None
        p.key(27,exited=True);p.restored()
        assert p.bus.reu_ram==p.bus.reu_original and not p.value('ru_probe_live')
        done('failed capacity-probe restoration retains the component and every REU byte for retry',p)
        report['passed']=True
    finally:
        heap.Bus=original
        args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
