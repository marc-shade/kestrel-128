#!/usr/bin/env python3
"""Loaded Ultimate panels and picker on both VDC sizes, with retained recovery."""
import argparse
import json
from pathlib import Path

from ci_native_controls_gui import GraphicalPanel, heap
from ci_native_vdc_desktop import VDCBus
from ci_native_calc import Calculator
from native_vdc_mirror import bitmap, attributes


class Panel(GraphicalPanel):
    instruction_limit = 20000000

    def output(self, value):
        screen = self.ram[0xd7] >> 7
        if screen:
            assert not self.value('vd_phase'), 'ROM text during owned VDC graphics'
        row, col = self.row[screen], self.col[screen]
        Calculator.output(self, value)
        if screen:
            chip = self.m.bus.native
            if value == 0x93:
                for i in range(2000):
                    chip.vwrite(i, 32)
                    chip.vwrite(0x800+i, 15)
            elif 32 <= value < 128:
                chip.vwrite(row*80+col, self.screens[1][row*80+col])
                chip.vwrite(0x800+row*80+col, 15)

    def mirror(self):
        assert self.value('vd_phase') == 2 and self.value('vd_live') == 1
        assert self.value('vd_fault') == self.value('vm_pending') == 0
        source = bytes(self.ram[0xc000:0xe400])
        x, y = self.position
        wanted = bitmap(source, self.bus.size == 64, x=x, y=y,
                        pointer=bool(self.value('vd_pointer_visible')))
        base = self.value('vd_base')*256
        assert self.bus.bytes(base, 16000) == wanted, 'complete VDC bitmap'
        if self.bus.size == 64:
            assert self.bus.bytes(0x8000, 2000) == attributes(source), 'complete VDC color cells'
            assert self.bus.video_ram[:0x4000] == self.bus.original[0][:0x4000]
            assert self.bus.video_ram[0x8800:] == self.bus.original[0][0x8800:]
        else:
            assert self.bus.video_ram[0x4000:] == self.bus.original[0][0x4000:]

    def check(self, *args, **kwargs):
        super().check(*args, **kwargs)
        self.mirror()

    def restored(self):
        super().restored()
        assert self.value('vd_phase') == self.value('vd_live') == self.value('bk_state') == 0
        if self.bus.original is not None:
            assert self.bus.video_ram == self.bus.original[0], 'every VDC RAM byte restored'
            for index in (1,6,8,9,10,12,13,14,15,18,19,20,21,22,23,24,25,26,27,28,32,33):
                assert self.bus.reg[index] == self.bus.original[1][index], index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--group', choices=('all', 'core', 'fault'), default='all')
    args = parser.parse_args()
    original_bus = heap.Bus
    report = dict(passed=False, physical_hardware_io=False, cases=[])

    def start(size=64, **options):
        heap.Bus = type('UltimateVDC', (VDCBus,), dict(size=size, **options))
        return Panel()

    def done(name, panel):
        report['cases'].append(dict(name=name, passed=True, instructions=panel.instructions,
                                    frames=panel.frames, keys=panel.events))
        args.report.write_text(json.dumps(report, indent=2)+'\n')
        print('PASS:', name, flush=True)

    try:
        if args.group in ('all', 'core'):
            for size in (16, 64):
                p = start(size); p.check(); p.frame(); p.check()
                p.key(9); p.check(); p.key(13); p.check()
                p.key(0x11); p.check()
                p.key(ord('E')); p.check(); p.key(27); p.check()
                p.key(ord('M')); assert p.value('ug_picker_active'); p.mirror()
                p.key(27); assert not p.value('ug_picker_active'); p.check()
                assert not p.value('ug_scratch_handle')
                p.key(ord('N')); p.check(); p.key(ord('T')); p.check()
                p.key(27, exited=True); p.restored()
                done(f'{size} KiB: panels, focus, cancelled confirmation, picker and exact restore', p)
        if args.group in ('all', 'fault'):
            p = start(); p.check(); p.bus.stall = True
            p.key(ord('D'))
            assert p.value('vd_fault') and p.value('vd_phase') == 2
            owned, stack = p.m.stats(), p.cpu.sp
            for key in (ord('M'), ord('E'), 13, 27, 27):
                p.key(key)
                assert p.m.stats() == owned and p.cpu.sp == stack and not p.device.mutations
            p.bus.stall = False
            p.key(27, exited=True); p.restored()
            done('failed display updates freeze drive actions and retain resources until Escape restores', p)
        report['passed'] = True
    finally:
        heap.Bus = original_bus
        args.report.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
