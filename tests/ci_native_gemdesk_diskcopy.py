#!/usr/bin/env python3
"""GEM desktop disk copy (docs/GEM-DESKTOP.md) in the Py65 model: the Boot
icon dragged onto the Drive 9 icon copies every sector of the disk through
"#" buffer channels (U1 on the source; B-P, the bytes and U2 on the target;
U1 on the target to compare), after a question whose default is Cancel. The
model's DOS answers U1/U2/B-P on whole-disk sector maps (D64 and D81 here);
Esc between tracks, a write-protected target, a sector that reads back
different and drives of different kinds are each reported. Surfaces are
compared with tests/native_gemdesk_scene.py."""
import argparse
import json
from pathlib import Path
import random
import sys

sys.dont_write_bytecode = True
from ci_native_gemdesk import Gem, AESVC, scene
from ci_native_pointer import heap
from ci_native_vdc_desktop import VDCBus
from launcher_scene import pointer_shape

GEOMETRY = {0: [(t, 21 if t < 18 else 19 if t < 25 else 18 if t < 31 else 17) for t in range(1, 36)],
            2: [(t, 40) for t in range(1, 81)]}


def disk(fmt, seed):
    rng = random.Random(seed)
    return {(t, s): bytearray(rng.randbytes(256)) for t, n in GEOMETRY[fmt] for s in range(n)}


def drag(p, cx, cy, tx, ty):
    p.cell(cx, cy); p.frame(down=True)
    for _ in range(24):
        p.frame()
    p.cell(tx, ty); p.frame(down=False)
    for _ in range(4):
        p.frame()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    report = dict(passed=False, physical_hardware_io=False, cases=[])

    def done(name, p, **extra):
        report['cases'].append(dict(name=name, frames=p.frames, instructions=p.instructions, **extra))
        args.report.write_text(json.dumps(report, indent=2)+'\n')
        print('PASS:', name, flush=True)

    def machine(fmt, vdc=False):
        prior = heap.Bus
        if vdc:                                                  # a 64 KiB VDC, so the mirror goes live
            heap.Bus = VDCBus
        try:
            p = Gem({(8, b'AESVC.PRG', b'P'): AESVC}, fmt=fmt, vdc=vdc)
        finally:
            heap.Bus = prior
        assert p.value('vd_live') == int(vdc)
        p.io.formats[9] = fmt
        p.io.sectors = {8: disk(fmt, 8), 9: {a: bytearray(256) for a in disk(fmt, 0)}}
        return p

    def ask(p):
        return scene.scene.draw(scene.desktop(selected=0), b'[3][Copy the disk in drive 8|onto drive 9? Everything|'
                                b'on drive 9 is replaced.][Copy|Cancel]', 2, 2)[0]

    def buffer_events(p, mark=0):
        return [e for e in p.io.events[mark:] if e[0] == 'buffer']

    try:
        p = machine(0)
        blank = {a: bytes(v) for a, v in p.io.sectors[9].items()}
        drag(p, 35, 3, 35, 7)
        p.expect(ask(p), 'asked')
        p.key(13)                                               # Cancel, the default
        p.expect(scene.desktop(selected=0), 'cancelled')
        assert not buffer_events(p) and {a: bytes(v) for a, v in p.io.sectors[9].items()} == blank
        done('Boot dropped on Drive 9 asks first (Cancel is the default) and Cancel sends nothing', p)

        snap = {}
        original = p.io.buffer_command

        def watching(device, command):                          # the screen as track 2 begins
            if command == b'U1:2 0 2 0' and not snap:
                snap['surface'] = p.surface()
            original(device, command)
        p.io.buffer_command = watching
        drag(p, 35, 3, 35, 7)
        p.key(9); p.key(13)                                     # Copy
        p.io.buffer_command = original
        progress = bytearray(scene.scene.windows_draw(
            [dict(id=1, kind=1, x=7, y=10, w=26, h=3, title=b'Copy track 2/35')], {1: (0, scene.PAPER)},
            base=scene.desktop(selected=0), markers=False))
        progress[8000:8128] = pointer_shape(); progress[9208:9210] = b'\x7d\x7e'
        got = snap['surface']
        assert got == bytes(progress), [(i, a, b) for i, (a, b) in enumerate(zip(got, progress)) if a != b][:12]
        p.expect(scene.scene.draw(scene.desktop(selected=0), b'[1][Disk copied and compared.][OK]', 1, 1)[0], 'copied')
        assert not p.ram[p.symbol('ae_ev_params')] & 32, 'the alert waits without a timer (it would wake every jiffy)'
        assert p.io.sectors[9] == p.io.sectors[8]
        sent = buffer_events(p)
        assert len(sent) == 4*683, len(sent)
        assert sent[:4] == [('buffer', 8, b'U1:2 0 1 0'), ('buffer', 9, b'B-P:2 0'), ('buffer', 9, b'U2:2 0 1 0'),
                            ('buffer', 9, b'U1:2 0 1 0')], sent[:4]
        assert sent[-1] == ('buffer', 9, b'U1:2 0 35 16')
        p.key(13); p.expect(scene.desktop(selected=0), 'closed')
        assert not p.io.handles
        done('Copy writes all 683 D64 sectors (U1, B-P, U2, then U1 to compare each), shows a "Copy track T/N" '
             'window while it works, closes it, and says the disk was copied and compared', p, commands=len(sent))

        p = machine(0)                                          # the same drag from the keyboard
        p.cell(35, 3)
        p.ram[0xd3] = 9; p.key(13)                              # ALT+Shift+Return: hold the button
        p.ram[0xd3] = 0
        for _ in range(24):                                     # held past the double-click window
            p.frame()
        for _ in range(4):
            p.ram[0xd3] = 8; p.key(0x11)                        # ALT+down: 8 pixels, onto Drive 9
        p.ram[0xd3] = 9; p.key(13); p.ram[0xd3] = 0             # ALT+Shift+Return: release
        for _ in range(4):
            p.frame()
        p.expect(ask(p), 'asked from the keyboard')
        p.key(13)
        assert not buffer_events(p)
        done('the keyboard mouse drags too: ALT+Shift+Return holds the button, ALT+cursor keys move, and the '
             'second ALT+Shift+Return drops Boot on Drive 9', p)

        p = machine(0)
        drag(p, 35, 3, 35, 7)
        p.keys.extend([9, 13, 27])                              # Copy; Esc waits until track 1 is done
        p.loop()
        stopped = b'[1][Disk copy stopped.|Drive 9 holds part|of the copy.][OK]'
        p.expect(scene.scene.draw(scene.desktop(selected=0), stopped, 1, 1)[0], 'stopped')
        assert all(p.io.sectors[9][1, s] == p.io.sectors[8][1, s] for s in range(21))
        assert all(p.io.sectors[9][2, s] == bytes(256) for s in range(21))
        p.key(13)
        assert not p.io.handles
        done('Esc stops between tracks: track 1 is copied, track 2 is not, and the alert says so', p)

        p = machine(0)
        p.io.protected.add(9)
        drag(p, 35, 3, 35, 7); p.key(9); p.key(13)
        failed = b'[3][Disk copy stopped at|track 1, sector 0:|26,WRITE PROTECT ON,01,00][OK]'
        p.expect(scene.scene.draw(scene.desktop(selected=0), failed, 1, 1)[0], 'protected')
        p.key(13)
        assert not p.io.handles
        done('a write-protected target stops the copy with the drive\'s status line', p)

        p = machine(0, vdc=True)                                # the 80-column mirror presents each alert
        p.io.protected.add(9)
        drag(p, 35, 3, 35, 7); p.key(9); p.key(13)
        p.expect(scene.scene.draw(scene.desktop(selected=0), failed, 1, 1)[0], 'protected, with the VDC mirror')
        assert buffer_events(p), 'Copy was taken as Copy'
        p.key(13)
        done('with the VDC mirror presenting the alert (it reuses N_BUFFER), the button chosen still reaches the '
             'caller: Copy runs (regression: GEMDESK read N_BUFFER after the present and saw garbage)', p)

        p = machine(0)
        original = p.io.buffer_command

        def corrupting(device, command):                        # the drive stores sector 1/5 wrongly
            original(device, command)
            if device == 9 and command == b'U2:2 0 1 5':
                p.io.sectors[9][1, 5][100] ^= 0x40
        p.io.buffer_command = corrupting
        drag(p, 35, 3, 35, 7); p.key(9); p.key(13)
        differs = b'[3][Disk copy stopped at|track 1, sector 5:|the copy differs.][OK]'
        p.expect(scene.scene.draw(scene.desktop(selected=0), differs, 1, 1)[0], 'differs')
        p.key(13)
        assert not p.io.handles
        done('a sector that reads back different from the source stops the copy at that sector', p)

        p = machine(0)
        p.io.formats[9] = 2
        drag(p, 35, 3, 35, 7)
        kinds = b'[1][Both drives must hold|the same kind of disk.][OK]'
        p.expect(scene.scene.draw(scene.desktop(selected=0), kinds, 1, 1)[0], 'kinds')
        p.key(13)
        assert not buffer_events(p)
        done('a D64 drive and a D81 drive are refused before anything is sent', p)

        p = machine(2)
        drag(p, 35, 3, 35, 7); p.key(9); p.key(13)
        p.expect(scene.scene.draw(scene.desktop(selected=0), b'[1][Disk copied and compared.][OK]', 1, 1)[0], 'd81')
        assert p.io.sectors[9] == p.io.sectors[8] and len(p.io.sectors[9]) == 3200
        assert buffer_events(p)[-1] == ('buffer', 9, b'U1:2 0 80 39')
        done('a D81 copy writes and compares all 3,200 sectors (80 tracks of 40)', p)
        report['passed'] = True
    finally:
        args.report.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
