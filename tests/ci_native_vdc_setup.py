#!/usr/bin/env python3
"""Stall the physical alias probe and the first bitmap write, then retry exit."""
import argparse
import hashlib
import json
from pathlib import Path

from ci_native_vdc_desktop import Desktop,VDCBus,heap,ROOT
from ci_native_vdc_calc import Calculator


class InterruptedVDC(VDCBus):
    threshold = 1

    def __setitem__(self,address,value):
        data_write = not self.config&1 and address == 0xd601 and self.selected == 31
        super().__setitem__(address,value)
        if data_write and self.data_writes == self.threshold:
            self.stall = True


def run():
    previous = heap.Bus
    cases = []
    try:
        for app,fixture,bitmap,key in [('Desktop',Desktop,'gd_bitmap',ord('C')),
                                        ('Calculator',Calculator,'cg_bitmap',27)]:
            for size in (16,64):
                for threshold,phase in ((1,1),(5,2)):
                    heap.Bus = type('InterruptedSetup',(InterruptedVDC,),dict(size=size,threshold=threshold))
                    desktop = fixture()
                    assert desktop.value('vd_fault') == 0x11 and desktop.value('vd_phase') == phase
                    assert bool(desktop.value('vd_handle')) == (phase == 2)
                    assert not desktop.value('vd_live') and desktop.value(bitmap) == 1
                    assert desktop.ram[0x3d20] == 32
                    desktop.key(key)
                    assert desktop.value('vd_phase') == phase and desktop.value('vd_fault') == 0x11
                    desktop.bus.threshold = None
                    desktop.bus.stall = False
                    desktop.key(key,exited=True)
                    desktop.restored()
                    name=f'{app}, {size} KiB setup stall during '+('alias probe' if phase == 1 else 'first bitmap write')
                    cases.append(dict(name=name,interrupted_phase=phase,physical_kib=size,restored=True,instructions=desktop.instructions))
                    print('PASS:',name,'retains recovery state and restores every byte',flush=True)
    finally:
        heap.Bus = previous
    return cases


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True);args=parser.parse_args()
    report=dict(passed=False,physical_hardware_io=False,cases=[],images={
        str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (ROOT/'target/native/kestrel.prg',ROOT/'target/native-desktop/desktop.prg',ROOT/'target/native-desktop/calc.prg')})
    try:
        report['cases']=run();report['passed']=True
    finally:
        args.report.write_text(json.dumps(report,indent=2)+'\n')
