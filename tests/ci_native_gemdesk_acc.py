#!/usr/bin/env python3
"""The Calculator desk accessory (docs/GEM-LAYER-DESIGN.md#desk-accessories) in
the Py65 model: GEMDESK loads DESK1.ACC into bank-1 AC_BASE (owner 29) and
installs it in the AES; the Desk menu lists it; its window opens, computes from
pointer clicks and from keys while it is on top (the app never sees them),
closes with its close box, and it survives a relaunch of the desktop. Surfaces
are compared with a painter built from tests/native_gemdesk_scene.py."""
import argparse
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
from ci_native_gemdesk import Gem, Relaunch, AESVC, scene, entries_for

AES = scene.scene
KIND = AES.WK['NAME'] | AES.WK['CLOSER'] | AES.WK['MOVER']
LABELS = b'789/456*123-0C=+'
MENU_ACC = scene.MENU.replace(b'Control Panel...;', b'Control Panel...|-|Calculator;')


def key_cell(label):
    """The middle cell of a keypad button (the window's work area starts at 22, 4)."""
    i = LABELS.index(label)
    return 22+[1, 5, 9, 13][i % 4]+1, 4+[3, 5, 7, 9][i // 4]


def calculator(display, base):
    win = dict(id=1, kind=KIND, x=22, y=3, w=16, h=12, title=b'Calculator')

    def content(s, w, g):
        wx, wy = g['wx'], g['wy']
        for i, label in enumerate(LABELS):
            kx, ky = wx+[1, 5, 9, 13][i % 4], wy+[3, 5, 7, 9][i // 4]
            s.rect(kx*8, ky*8, (kx+3)*8, ky*8+8, 0)
            s.colors(kx, ky, kx+3, ky+1, 0x0f)
            s.text((kx+1)*8, ky*8, bytes([label]))
        s.rect((wx+1)*8, (wy+1)*8, (wx+15)*8, (wy+2)*8, 0)
        s.colors(wx+1, wy+1, wx+15, wy+2, 0x61)
        s.text((wx+15-len(display))*8, (wy+1)*8, display)
    return AES.windows_draw([win], {1: (0, 0x61)}, base=base, content=content, markers=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    report = dict(passed=False, physical_hardware_io=False, cases=[])

    def done(name, p, **extra):
        report['cases'].append(dict(name=name, frames=p.frames, instructions=p.instructions, **extra))
        args.report.write_text(json.dumps(report, indent=2)+'\n')
        print('PASS:', name, flush=True)

    try:
        files = {(8, b'AESVC.PRG', b'P'): AESVC}
        p = Gem(files, acc=True)
        desk = scene.desktop()
        p.expect(desk, 'desktop')
        records = [bytes(p.ram[0x3c00+i*8:0x3c08+i*8]) for i in range(32)]
        acc = [r for r in records if r[0] == 29]
        assert len(acc) == 1 and acc[0][1] == 1 and acc[0][2] == 0x40, records
        p.key(0x85)                                             # F1: the Desk menu
        p.expect(AES.menu_draw(desk, MENU_ACC, open_title=0, hover=0)[0], 'desk menu')
        done('with DESK1.ACC beside GEMDESK, the accessory is loaded at bank-1 $4000 (owner 29) and the Desk '
             'menu lists Calculator after a separator', p)

        p.key(0x11); p.key(0x11); p.key(13)                     # Control Panel, Calculator
        p.expect(calculator(b'0', desk), 'opened')
        done('choosing Calculator opens its window: title, close box, display and keypad', p)

        for label in b'12+3=':
            p.cell(*key_cell(label)); p.click()
        p.expect(calculator(b'15', desk), 'clicked')
        done('clicks on the keypad compute 12 + 3 = 15 (the desktop never sees them)', p)

        for key in b'8*6=':                                     # 8 would open drive 8 in GEMDESK
            p.key(key)
        p.expect(calculator(b'48', desk), 'typed')
        done('keys go to the calculator while its window is on top: 8 * 6 = 48, and no drive window opens', p)

        for key in b'7/0=':
            p.key(key)
        p.expect(calculator(b'Error', desk), 'error')
        p.key(ord('c'))
        p.expect(calculator(b'0', desk), 'cleared')
        for key in b'2147483647+1=':
            p.key(key)
        p.expect(calculator(b'Error', desk), 'overflow')
        p.key(ord('c'))
        for key in b'0-5*3=':
            p.key(key)
        p.expect(calculator(b'-15', desk), 'negative')
        done('division by zero and overflow show Error until C; negative results print with a sign', p)

        p.cell(22, 3); p.click()                                # the close box
        p.expect(desk, 'closed')
        p.key(ord('8'))                                         # the desktop has its keys back
        w8 = dict(id=1, x=1, y=2, w=28, h=16, title=b'Drive 8', top=0)
        opened = scene.picture([w8], {1: scene.ordered(entries_for(p.io.files, 8), 0)}, selected_icon=0)
        p.expect(opened, 'drive 8')
        done('the close box closes it and restores the desktop; keys reach GEMDESK again', p)

        p.key(12, exited=True)                                  # Ctrl-L: to the launcher; GEMDESK exits
        back = Relaunch(p)
        opened = scene.picture([w8], {1: scene.ordered(entries_for(p.io.files, 8), 0)})   # (no icon selection kept)
        back.expect(opened, 'relaunched')
        events = [e for e in back.io.events if e[0] == 'open' and b'DESK1'.hex() in e[4]]
        assert not events, 'a resident accessory is adopted, not loaded again'
        back.key(0x85)
        back.expect(AES.menu_draw(opened, MENU_ACC, open_title=0, hover=0)[0], 'menu after relaunch')
        done('after the desktop is started again the resident accessory is adopted and listed', back)
        report['passed'] = True
    finally:
        args.report.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
