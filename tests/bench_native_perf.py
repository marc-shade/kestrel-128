#!/usr/bin/env python3
"""Py65 cycles of one frame or input step for the 80-column hover, focus and
pointer cases of docs/validation/2026-10-10-desktop-hover (64 KiB VDC, 16 KiB
initial addressing), with the VDC accesses each made. Uses the target/ images.

The VDC reports ready on the first status read after every access, so the
cycles are the code's own cost, a lower bound for a real 8563. --handshake
keeps the test buses' model instead, which holds the chip busy for a fixed
number of status reads after each access to prove the code polls; its wait
loops are an artifact of that model, not 8563 timing."""
import argparse
import importlib.util
import json
from pathlib import Path
import tempfile
import time

from ci_native_vdc_desktop import VDCBus, Desktop
from ci_native_pointer import heap, calc

ROOT = Path(__file__).resolve().parents[1]
COUNTS = ('select', 'write', 'read', 'block')      # $d600 writes, $d601 writes, $d601 reads, R30 bytes


class Counted:
    handshake = False

    def __init__(self):
        super().__init__()
        self.vdc = dict.fromkeys(COUNTS, 0)

    def ready_now(self):
        if not self.handshake: self.busy = 0

    def __getitem__(self, address):
        if not self.config&1 and address == 0xd601:
            self.vdc['read'] += 1
            value = super().__getitem__(address); self.ready_now()
            return value
        return super().__getitem__(address)

    def __setitem__(self, address, value):
        if not self.config&1 and address == 0xd600: self.vdc['select'] += 1
        elif not self.config&1 and address == 0xd601:
            self.vdc['write'] += 1
            if self.selected == 30: self.vdc['block'] += value or 256
        super().__setitem__(address, value)
        if not self.config&1 and address in (0xd600, 0xd601): self.ready_now()


def vdc(base=VDCBus):
    return type('BenchVDC', (Counted, base), dict(size=64, addressing=16))


def measure(p, step):
    counts = getattr(getattr(p, 'bus', None), 'vdc', None)
    before, cycles = dict(counts or {}), p.cpu.processorCycles
    step()
    return p.cpu.processorCycles-cycles, counts and {k: counts[k]-before[k] for k in COUNTS}


def cross(p, start, d, target, old, new, key='ui_selected'):
    """Step d from start; measure the frame that reaches target and moves focus old -> new."""
    p.move(*start); assert p.value(key) == old, (start, p.value(key))
    while p.position != (target[0]-d[0], target[1]-d[1]):
        p.frame(*d); assert p.value(key) == old, (p.position, p.value(key))
    result = measure(p, lambda: p.frame(*d))
    assert p.position == target and p.value(key) == new, (p.position, p.value(key), new)
    return result


def wiggle(p, frames, settled=lambda: True):
    """Mean of frames alternating dx +5/-5 with dy 3: both axes move, no jump is held."""
    total, counts = 0, dict.fromkeys(COUNTS, 0)
    for i in range(frames):
        at = p.position; dx = 5 if i%2 == 0 else -5
        cycles, step = measure(p, lambda: p.frame(dx, 3))
        assert p.position == (at[0]+dx, at[1]+3) and settled(), (at, p.position)
        total += cycles
        for k in COUNTS: counts[k] += step[k]
    return round(total/frames), {k: round(v/frames) for k, v in counts.items()}


def desktop(results):
    heap.Bus = vdc(); p = Desktop(); p.frame()
    p.move(308, 20); selected = p.value('gd_selected')
    results['Desktop: pointer-only over empty space (mean of 30)'] = wiggle(p, 30, lambda: p.value('gd_selected') == selected)
    p.move(100, 76); assert p.value('gd_selected') == 2
    results['Desktop: within the selected card, same byte column'] = cross(p, (100, 76), (0, 2), (100, 80), 2, 2, 'gd_selected')
    results['Desktop: within the selected card, next byte column'] = cross(p, (100, 80), (4, 0), (108, 80), 2, 2, 'gd_selected')
    results['Desktop: onto the next card'] = cross(p, (100, 76), (0, 2), (100, 88), 2, 3, 'gd_selected')


def calculator(results):
    from ci_native_vdc_calc import Calculator
    heap.Bus = vdc(); p = Calculator(); p.frame()
    results['Calculator: onto the next button across'] = cross(p, (40, 80), (2, 0), (56, 80), 0, 1)
    results['Calculator: onto the next button down'] = cross(p, (32, 80), (0, 2), (32, 96), 0, 4)


def controls(results):
    from ci_native_vdc_controls import Panel
    heap.Bus = vdc(); p = Panel(); p.frame()
    results['Controls: Info tab onto Drives tab (across)'] = cross(p, (70, 40), (2, 0), (88, 40), 0, 1)
    results['Controls: Info tab onto Prev (down)'] = cross(p, (40, 40), (0, 2), (40, 160), 0, 5)


def files(results):
    import ci_native_files_gui as gui
    from ci_native_vdc_files import Files
    gui.PointerBus = vdc()
    p = Files({(9, b'FILE%d' % i, b'S'): bytes(50) for i in range(5)}); p.frame()
    results['Files: Device onto Format'] = cross(p, (40, 32), (2, 0), (72, 32), 1, 2)
    results['Files: first file row onto the second'] = cross(p, (100, 66), (0, 2), (100, 72), 11, 12)


def editor(results):
    import ci_native_editor_gui as gui
    from ci_native_vdc_editor import Editor
    gui.PointerBus = vdc(); p = Editor({}, device=9, fmt=0); p.frame()
    results['Editor: Open onto Save As'] = cross(p, (40, 32), (2, 0), (64, 32), 1, 2)


def paint(results):
    from ci_native_vdc_paint import Paint
    heap.Bus = vdc(); p = Paint(); p.frame()
    results['Paint: Pen onto Eraser'] = cross(p, (292, 40), (0, 2), (292, 56), 0, 1)
    results['Paint: canvas onto Pen'] = cross(p, (240, 40), (2, 0), (272, 40), 23, 0)
    results['Paint: swatch onto the next swatch'] = cross(p, (16, 192), (2, 0), (24, 192), 7, 8)
    p.move(100, 60); p.settle(); assert p.value('ui_selected') == 23
    results['Paint: moving over the canvas (mean of 10)'] = wiggle(p, 10, lambda: p.value('pa_labels_stale'))
    results['Paint: first still frame after moving (status)'] = measure(p, p.frame)
    assert not p.value('pa_labels_stale')


def claude(results):
    from ci_native_claude_vdc import Claude, TerminalVDC
    heap.Bus = vdc(TerminalVDC); p = Claude(); p.frame()
    results['Claude: Connect onto Desktop (over disabled Repaint)'] = cross(p, (60, 20), (2, 0), (216, 20), 0, 2, 'cg_focus')
    results['Claude: Next onto Panel'] = cross(p, (232, 180), (-2, 0), (222, 180), 4, 5, 'cg_focus')


def gemdesk(results):
    import native_gemdesk_scene as scene
    from ci_native_gemdesk import Gem, AESVC
    heap.Bus = vdc(); p = Gem({(8, b'AESVC.PRG', b'P'): AESVC, (8, b'A0', b'S'): b'x'}, vdc=True)
    p.expect(scene.desktop(), 'startup')
    def menu(hover):
        p.expect(scene.scene.menu_draw(scene.desktop(), scene.MENU, open_title=2, hover=hover, flags={(2, 0): 1})[0], hover)
    p.key(0x85); p.key(0x1d); p.key(0x1d); menu(0)                  # F1, right, right: View
    results['GEMDESK View menu: cursor key onto Type'] = measure(p, lambda: p.key(0x11))
    menu(1); p.key(27)
    p.key(0x85); p.key(0x1d); p.key(0x1d)
    p.move(120, 18); menu(0)
    while p.position != (120, 22): p.frame(0, 2)
    menu(0)
    results['GEMDESK View menu: pointer onto Type'] = measure(p, lambda: p.frame(0, 2))
    assert p.position == (120, 24); menu(1)


def aes(results):
    from native_display_bus import DisplayBus
    import native_aes_scene as scene
    from ci_native_aes import Demo, MENU, BLANK
    spec = importlib.util.spec_from_file_location('aes_build', ROOT/'examples/native-aes/build.py')
    build = importlib.util.module_from_spec(spec); spec.loader.exec_module(build)
    with tempfile.TemporaryDirectory(prefix='kestrel-bench-aes-') as work:
        build.build(work)
        heap.Bus = DisplayBus; demo = Demo(Path(work), heap.Machine())
    flags = {(1, 1): 2}
    demo.key(ord('M')); demo.key(0x85); demo.key(0x1d)
    assert demo.surface() == scene.menu_draw(BLANK, MENU, flags=flags, open_title=1, hover=0)[0]
    results['AES menu test: cursor key onto Quit (40 columns)'] = measure(demo, lambda: demo.key(0x11))
    assert demo.surface() == scene.menu_draw(BLANK, MENU, flags=flags, open_title=1, hover=3)[0]


APPS = dict(desktop=desktop, calculator=calculator, controls=controls, files=files, editor=editor,
            paint=paint, claude=claude, gemdesk=gemdesk, aes=aes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', choices=APPS, action='append')
    parser.add_argument('--json', type=Path)
    parser.add_argument('--handshake', action='store_true', help="the test buses' fixed poll-count busy model")
    args = parser.parse_args()
    Counted.handshake = args.handshake
    started, results = time.time(), {}
    for name in args.app or APPS:
        bus, machine = heap.Bus, calc.Machine          # harnesses swap these module factories
        try: APPS[name](results)
        finally: heap.Bus, calc.Machine = bus, machine
    width = max(map(len, results))
    print(f'{"case":<{width}} {"cycles":>10} {"select":>7} {"write":>7} {"read":>6} {"block":>6}')
    for case, (cycles, counts) in results.items():
        counts = counts or dict.fromkeys(COUNTS, '-')
        print(f'{case:<{width}} {cycles:>10,} ' + ' '.join(f'{counts[k]:>{w}}' for k, w in zip(COUNTS, (7, 7, 6, 6))))
    print(f'{len(results)} cases, {time.time()-started:.1f} s')
    if args.json:
        args.json.write_text(json.dumps({case: cycles for case, (cycles, _) in results.items()}, indent=2)+'\n')


if __name__ == '__main__':
    main()
