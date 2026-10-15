#!/usr/bin/env python3
"""A physical 8563 once landed a bitmap write without advancing its update
address, so the rest of that run sat one byte early (and, in another run, one
byte late). The shared VDC service reads R18/R19 back after every run (each
80-byte mirror run and each snapshot or restore block) and repeats a run when
the address drifted; this makes the VDC model drift once, at a chosen data
write or read, and requires an exact surface and an exact restore anyway."""
import argparse
import hashlib
import json
from pathlib import Path

from ci_native_vdc_desktop import VDCBus,heap,ROOT
from ci_native_vdc_calc import Calculator
from hwlib import lst_symbol


class DriftingVDC(VDCBus):
    """Drift once: at data write `threshold`, or data read `read_threshold`."""
    threshold = None
    read_threshold = None
    drift = 0              # -1: the access lands without advancing; +1: it advances twice
    fired = False

    def __getitem__(self, address):
        if (not self.config&1 and address == 0xd601 and self.selected == 31 and not self.fired
                and self.read_threshold is not None and self.data_reads+1 == self.read_threshold):
            self.fired = 'read'
            value = super().__getitem__(address)
            at = self.reg[18]*256+self.reg[19]
            super().advance(at+self.drift)
            return value
        return super().__getitem__(address)

    def __setitem__(self, address, value):
        if (not self.config&1 and address == 0xd601 and self.selected == 31 and not self.fired
                and self.threshold is not None and self.data_writes+1 == self.threshold):
            self.fired = 'write'
            super().__setitem__(address, value)
            at = self.reg[18]*256+self.reg[19]
            super().advance(at+self.drift)
            return
        super().__setitem__(address, value)


def rewrites(machine):
    at = lst_symbol('native-desktop/vdsvc','vd_rewrites')
    return machine.bus.ram[1][at] | machine.bus.ram[1][at+1]<<8


DRIFTS = ((-1,'landed without advancing'),(1,'advanced twice'))


def run():
    previous = heap.Bus
    cases = []
    def configure(size, **options):
        heap.Bus = type('DriftingSetup',(DriftingVDC,),dict(size=size,addressing=16,**options))
    def record(label, calc, count, **extra):
        cases.append(dict(name=label,repeated_runs=count,instructions=calc.instructions,**extra))
        print('PASS:',label,flush=True)
    try:
        for size in (16,64):
            # Write 300 is inside a bitmap run; on 64 KiB, write 700 is inside
            # the first attribute run (each text row is 640 bitmap + 80 attribute
            # writes after the snapshot setup).
            for threshold in ((300,) if size == 16 else (300,700)):
                for drift,name in DRIFTS:
                    configure(size, threshold=threshold, drift=drift)
                    calc = Calculator()
                    assert calc.bus.fired == 'write', ('drift never injected', size, threshold)
                    count = rewrites(calc)
                    assert count == 1, ('expected one repeated run', count)
                    calc.check()
                    calc.key(27, exited=True)
                    calc.restored()
                    record(f'{size} KiB, data write {threshold} {name}: the run is written again and the surface is exact',
                           calc, count, physical_kib=size, threshold=threshold, drift=drift)
            for drift,name in DRIFTS:
                # The open-time snapshot reads every page the bitmap will
                # cover; a drifted read there would put wrong bytes back at close.
                configure(size, read_threshold=300, drift=drift)
                calc = Calculator()
                assert calc.bus.fired == 'read', ('read drift never injected', size)
                assert rewrites(calc) == 1, rewrites(calc)
                calc.check()
                calc.key(27, exited=True)
                calc.restored()
                record(f'{size} KiB, snapshot read 300 {name}: the page is read again and close restores every byte',
                       calc, 1, physical_kib=size, read_threshold=300, drift=drift)
                # The close-time restore writes the saved pages back, and they
                # are the last data writes of a close: drift 1,000 before the end.
                configure(size)
                clean = Calculator(); clean.check()
                before = clean.bus.data_writes
                clean.key(27, exited=True)
                close_writes = clean.bus.data_writes-before
                assert close_writes >= 64*256, close_writes   # at least the 64 or 72 saved pages
                configure(size, drift=drift)
                calc = Calculator(); calc.check()
                before = rewrites(calc)
                calc.bus.threshold = calc.bus.data_writes+close_writes-1000
                calc.key(27, exited=True)
                assert calc.bus.fired == 'write', ('restore drift never injected', size)
                calc.restored()
                assert rewrites(calc) == before+1, (before, rewrites(calc))
                record(f'{size} KiB, restore write 1,000 before the end {name}: the page is written again and close restores every byte',
                       calc, 1, physical_kib=size, close_writes=close_writes, drift=drift)
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
