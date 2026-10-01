#!/usr/bin/env python3
"""Loaded Calculator on both physical VDC RAM sizes, including recovery."""
import argparse
import hashlib
import json
from pathlib import Path

from ci_native_calc_gui import GraphicalCalculator, heap, calc
from ci_native_vdc_desktop import VDCBus
from native_vdc_mirror import bitmap, attributes

ROOT = Path(__file__).resolve().parents[1]


class Calculator(GraphicalCalculator):
    # Full startup includes the loader, VIC scene and owned VDC snapshot/upload.
    instruction_limit = 16000000

    def output(self, value):
        assert not self.value('vd_phase'), 'ROM text output during VDC ownership'
        chip = self.m.bus
        if chip.original is not None and not getattr(self, 'rollback_checked', False):
            assert chip.video_ram == chip.original[0], 'probe restored before text fallback'
            for register in (10,12,13,18,19,20,21,24,25,26,27,28,32,33):
                assert chip.reg[register] == chip.original[1][register], register
            self.rollback_checked = True
        screen = self.ram[0xd7]>>7
        row, col = self.row[screen], self.col[screen]
        calc.Calculator.output(self, value)
        if screen:
            if value == 0x93:
                for i in range(2000):
                    chip.vwrite(i, 32); chip.vwrite(0x800+i, 15)
            elif 32 <= value < 128:
                chip.vwrite(row*80+col, self.screens[1][row*80+col])
                chip.vwrite(0x800+row*80+col, 15)

    def check(self):
        super().check()
        assert self.value('vd_live') == 1 and self.value('vd_phase') == 2
        assert self.value('vd_fault') == 0
        source = bytes(self.ram[0xc000:0xe400])
        x, y = self.position
        expected = bitmap(source, self.bus.size == 64, x=x, y=y,
                          pointer=bool(self.value('vd_pointer_visible')))
        base = self.value('vd_base')*256
        assert self.bus.bytes(base, 16000) == expected, 'complete VDC bitmap'
        if self.bus.size == 64:
            assert self.bus.bytes(0x8000, 2000) == attributes(source)
            assert self.bus.reg[25] == 0xc7
            assert self.bus.video_ram[:0x4000] == self.bus.original[0][:0x4000]
            assert self.bus.video_ram[0x8800:] == self.bus.original[0][0x8800:]
        else:
            assert self.bus.reg[25] == 0x87
            assert self.bus.video_ram[0x4000:] == self.bus.original[0][0x4000:]
        assert self.bus.reg[26] == 0xf2
        assert self.value('vm_pending') == 0

    def restored(self):
        super().restored()
        assert self.value('vd_phase') == self.value('vd_live') == self.value('vd_handle') == 0
        if self.bus.original is not None:
            assert self.bus.video_ram == self.bus.original[0], 'all physical VDC RAM restored'
            for register in (1,6,8,9,10,12,13,14,15,18,19,20,21,22,23,24,25,26,27,28,32,33):
                assert self.bus.reg[register] == self.bus.original[1][register], register


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--group', choices=('all','core','fault'), default='all')
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    original, machine = heap.Bus, calc.Machine
    report = dict(passed=False, physical_hardware_io=False, cases=[], images={
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (ROOT/'target/native-desktop/calc.prg', heap.IMAGE)})

    def start(size=64, addressing=16, **options):
        heap.Bus = type('ConfiguredVDC', (VDCBus,), dict(size=size, addressing=addressing, **options))
        return Calculator()

    def done(name, p, **extra):
        report['cases'].append(dict(name=name, frames=p.frames, keys=p.events,
                                    instructions=p.instructions, **extra))
        print('PASS:', name, flush=True)

    try:
        if args.group in ('all', 'core'):
            for size in (16, 64):
                for addressing in (16, 64):
                    p = start(size, addressing); p.check()
                    before = p.bus.data_writes
                    p.key(ord('1')); p.check()
                    digit_writes = p.bus.data_writes-before
                    assert 0 < digit_writes < 10000, digit_writes
                    p.type('2+30='); p.check(); assert p.history() == ['42']
                    p.frame(); p.check()
                    for x,y in ((0,0),(319,199),(319,0),(0,199),(72,80),(288,168)):
                        p.move(x,y); p.check()
                    # Stationary mouse leaves keyboard focus alone; pointer-only
                    # moves must not upload a complete app scene.
                    p.move(250,185); p.check()
                    before = p.bus.data_writes
                    p.frame(dx=1); p.check()
                    assert p.bus.data_writes-before <= 96
                    p.key(9); p.check()
                    p.type('SRESULT'); p.check(); p.key(9); p.check(); p.key(9)
                    p.key(13); p.check()
                    assert bytes(p.io.files[8,b'RESULT',b'S']) == b'42\r'
                    assert not p.io.handles
                    p.type('SRESULT'); p.key(13); p.check(); assert p.value('save_status') == 3
                    p.type('SCANCEL'); p.key(27); p.check()
                    p.key(27, exited=True); p.restored()
                    done(f'{size} KiB / {addressing} KiB addressing: arithmetic, dirty rows, pointer, save, collision, cancel and restore', p,
                         digit_vdc_writes=digit_writes)
        if args.group in ('all', 'fault'):
            p = start(); p.check()
            p.bus.stall = True
            p.key(ord('7'))
            assert p.value('vd_fault') == 0x11 and p.value('vd_phase') == 2
            assert p.value('vm_pending') and p.value('vd_handle')
            owned = p.m.stats()
            p.key(27)
            assert p.ram[0x3d20] == 32 and p.m.stats() == owned
            p.bus.stall = False
            p.key(27, exited=True); p.restored()
            done('stalled row upload and exit retain the snapshot and all owners; Escape retries exact restoration', p)

            p = start(); p.frame(); p.check()
            p.bus.stall_register = (28, p.bus.original[1][28])
            p.key(27)
            assert p.value('vd_phase') == 2 and p.bus.stall
            p.bus.stall_register = None; p.bus.stall = False
            p.key(27, exited=True); p.restored()
            done('retry after partial register restoration restores original addressing and every VRAM byte', p)

            p = start(); p.type('12'); p.check()
            normal_stub = p.io.stub
            history = p.value('history_handle')
            injected = []
            def fail_history(cpu):
                if not injected and cpu.pc == 0x1c29 and p.ram[0x3d04] == history:
                    injected.append(True); p.bus.stall = True
                    cpu.a = 0x11; cpu.p |= cpu.CARRY
                    cpu.pc = cpu.stPopWord()+1
                    return True
                return normal_stub(cpu)
            p.io.stub = fail_history
            p.key(ord('='))
            assert injected and p.value('cg_exit_error') == 0x11
            owned = p.m.stats(); stack = p.cpu.sp
            for key in (ord('7'),ord('S'),27,27):
                p.key(key)
                assert p.m.stats() == owned and p.cpu.sp == stack
            p.bus.stall = False
            p.expected_exit_code = 0x11
            p.key(27, exited=True); p.restored()
            done('fatal history failure retains VDC recovery and original exit error without accumulating stack frames', p)

            for options in (dict(present=False), dict(columns=79)):
                p = start(**options)
                assert not p.value('vd_phase') and not p.value('vd_handle')
                assert p.value('bk_state') == p.value('bp_started') == 0
                p.type('12+30='); GraphicalCalculator.check(p)
                assert not p.bus.data_writes
                p.key(27, exited=True); p.restored()
                done('absent or unsupported VDC keeps VIC controls and text fallback', p)

            class ShortCharacters(VDCBus):
                def __init__(self):
                    super().__init__(); self.reg[23] = 6
            heap.Bus = ShortCharacters
            p = Calculator()
            assert not p.value('vd_phase') and p.bus.original is None
            p.type('7*8='); GraphicalCalculator.check(p)
            p.key(27, exited=True); p.restored()
            done('foreign character height is refused before any VDC mutation', p)

            class Occupied(machine):
                def __init__(self):
                    super().__init__()
                    end=0x60+(ROOT/'target/native-desktop/vdsvc.prg').read_bytes()[12]
                    self.foreign = [self.alloc(0x60-6,1,77,page=6),
                                    self.alloc(0xff-end,1,77,page=end)]
            calc.Machine = Occupied
            p = start()
            calc.Machine = machine
            assert not p.value('vd_phase') and not p.value('vd_handle')
            assert p.value('bk_state') == p.value('bp_started') == 0
            p.type('7*8='); GraphicalCalculator.check(p)
            assert p.rollback_checked
            stack = bytes(p.ram[0x100:0x200])
            for handle in p.m.foreign:
                p.m.select(handle,77); p.m.invoke('free')
            p.ram[0x100:0x200] = stack
            p.key(27, exited=True)
            GraphicalCalculator.restored(p)
            done('snapshot allocation refusal leaves both app views and foreign allocation usable', p)
        report['passed'] = True
    except BaseException as error:
        report['error'] = repr(error)
        raise
    finally:
        heap.Bus, calc.Machine = original, machine
        args.report.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
