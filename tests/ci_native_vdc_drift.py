#!/usr/bin/env python3
"""A physical 8563 once landed a bitmap write without advancing its update
address, so the rest of that run sat one byte early (and, in another run, one
byte late). The shared VDC service reads R18/R19 back after every 80-byte run
and writes a run again when the address drifted; this makes the VDC model
drift once, at a chosen data write, and requires an exact surface anyway."""
import argparse
import hashlib
import json
from pathlib import Path

from ci_native_vdc_desktop import VDCBus,heap,ROOT
from ci_native_vdc_calc import Calculator
from hwlib import lst_symbol


class DriftingVDC(VDCBus):
    threshold = None
    drift = 0              # -1: the write lands without advancing; +1: it advances twice
    fired = False

    def advance(self, address):
        if (self.threshold is not None and not self.fired and self.selected == 31
                and self.data_writes+1 == self.threshold):
            self.fired = True
            address += self.drift
        super().advance(address)


def rewrites(machine):
    at = lst_symbol('native-desktop/vdsvc','vm_rewrites')
    return machine.bus.ram[1][at] | machine.bus.ram[1][at+1]<<8


def run():
    previous = heap.Bus
    cases = []
    try:
        for size in (16,64):
            # Write 300 is inside a bitmap run; on 64 KiB, write 700 is inside
            # the first attribute run (each text row is 640 bitmap + 80 attribute
            # writes after the snapshot setup).
            for threshold in ((300,) if size == 16 else (300,700)):
                for drift,name in ((-1,'landed without advancing'),(1,'advanced twice')):
                    heap.Bus = type('DriftingSetup',(DriftingVDC,),dict(size=size,addressing=16,threshold=threshold,drift=drift))
                    calc = Calculator()
                    assert calc.bus.fired, ('drift never injected', size, threshold)
                    count = rewrites(calc)
                    assert count == 1, ('expected one rewritten run', count)
                    calc.check()
                    calc.key(27, exited=True)
                    calc.restored()
                    label = f'{size} KiB, data write {threshold} {name}'
                    cases.append(dict(name=label,physical_kib=size,threshold=threshold,drift=drift,
                                      rewritten_runs=count,instructions=calc.instructions))
                    print('PASS:',label,'is written again and the surface is exact',flush=True)
    finally:
        heap.Bus = previous
    return cases


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True);args=parser.parse_args()
    report=dict(passed=False,physical_hardware_io=False,cases=[],images={
        str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (ROOT/'target/native/kestrel.prg',ROOT/'target/native-desktop/vdsvc.prg',ROOT/'target/native-desktop/calc.prg')})
    try:
        report['cases']=run();report['passed']=True
    finally:
        args.report.write_text(json.dumps(report,indent=2)+'\n')
