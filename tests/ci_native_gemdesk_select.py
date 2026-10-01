#!/usr/bin/env python3
"""GEM desktop multiple selection (docs/GEM-DESKTOP.md) in the Py65 model:
Shift-click adds and removes rows, Ctrl-A selects all, a press below the
entries clears the selection or drags a live band, and Delete, Trash and
drag-and-drop copy and move act on every selected row. Complete surfaces are
compared with tests/native_gemdesk_scene.py."""
import argparse
from itertools import groupby
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
from ci_native_gemdesk import ROOT, Gem, AESVC, entries_for, scene
from ci_native_gemdesk_copy import outline, progress, as_read, opens_seen

GDCPY = {}                          # (Gem supplies GDCPY.PRG with the other modules)


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
        files = {**GDCPY, (8, b'AESVC.PRG', b'P'): AESVC, (9, b'NINE', b'S'): bytes(30)}
        for i in range(1, 7):                               # (with AESVC, GEMDESK and 6 modules: 14 rows of 15)
            files[8, f'A{i}'.encode(), b'S'] = bytes([i])*(40*i)
        p = Gem(files)
        del p.io.files[8, b'GDNEW.PRG', b'P']              # New Folder and Format are not used:
        del p.io.files[8, b'GDFMT.PRG', b'P']              # keep a blank row below
        del p.io.files[8, b'GDPRT.PRG', b'P']
        w8 = dict(id=1, x=1, y=2, w=28, h=16, title=b'Drive 8', top=0)
        g = scene.scene.geometry(dict(kind=scene.KIND, x=1, y=2, w=28, h=16))

        def listed(device=8):
            return scene.ordered(entries_for(p.io.files, device), 0)

        def row(name, device=8):
            return [e['name'] for e in listed(device)].index(name)

        def shown(anchor=None, selection=(), icon=0):
            w8['selected'], w8['selection'] = anchor, set(selection)
            return scene.picture([w8], {1: listed()}, selected_icon=icon)

        def click(name, shift=False):
            p.cell(3, g['wy']+row(name))
            p.ram[0xd3] = 1 if shift else 0                    # KERNAL SHFLAG
            p.click()
            p.ram[0xd3] = 0

        p.cell(35, 3); p.click(double=True)
        assert len(listed()) < g['wh'], 'the window has blank rows below its entries'
        click(b'A1'); click(b'A3', shift=True); click(b'A5', shift=True)
        a1, a3, a5 = row(b'A1'), row(b'A3'), row(b'A5')
        p.expect(shown(a5, {a1, a3, a5}), 'three selected')
        done('Shift-click adds rows to the selection; every selected row is inverted', p)

        click(b'A3', shift=True)
        p.expect(shown(a5, {a1, a5}), 'a3 removed')
        click(b'A5', shift=True)
        p.expect(shown(a1, {a1}), 'anchor removed')
        done('Shift-click on a selected row removes it; removing the anchor moves it to another selected row', p)

        click(b'A3', shift=True); click(b'A5')
        p.expect(shown(a5, {a5}), 'plain click')
        done('a plain click on a row of a multiple selection leaves that row alone selected', p)

        p.key(1)                                                # Ctrl-A
        p.expect(shown(0, range(len(listed()))), 'select all')
        done('Ctrl-A selects every entry of the top window', p)

        blank = g['wy']+len(listed())                          # the first row below the entries
        p.cell(3, blank); p.click()
        p.expect(shown(), 'cleared')
        done('a click below the entries clears the selection', p)

        a2 = row(b'A2')
        p.cell(3, blank); p.frame(down=True)
        for _ in range(24):                                     # held past the double-click window
            p.frame()
        last = len(listed())-1
        p.expect(shown(last, {last}), 'band at the last entry')
        p.cell(3, g['wy']+a2); p.frame(down=True)
        for _ in range(4):
            p.frame(down=True)
        p.expect(shown(a2, range(a2, last+1)), 'band dragged up')
        p.cell(3, g['wy']+a5); p.frame(down=True)
        for _ in range(4):
            p.frame(down=True)
        p.expect(shown(a5, range(a5, last+1)), 'band shrunk')
        p.frame(down=False)
        for _ in range(4):
            p.frame()
        p.expect(shown(a5, range(a5, last+1)), 'band released')
        done('a press below the entries drags a band; the rows it covers are selected live, and stay after the release', p)

        # Delete: every selected row after one question, listed again once.
        click(b'A5'); click(b'A6', shift=True)
        a5, a6 = row(b'A5'), row(b'A6')
        before = shown(a6, {a5, a6})
        p.expect(before, 'two to delete')
        mark = len(p.io.events)
        ask = b'[2][Delete 2 items?|This cannot be undone.][Delete|Cancel]'
        p.key(4); p.expect(scene.scene.draw(before, ask, 2, 2)[0], 'delete two asked')
        p.key(9); p.key(13)
        assert (8, b'A5', b'S') not in p.io.files and (8, b'A6', b'S') not in p.io.files
        assert [e for e in p.io.events[mark:] if e[0] == 'dos'] == [('dos', 8, b'S0:A5'), ('dos', 8, b'S0:A6')]
        p.expect(shown(), 'two deleted')
        done('Delete with two rows selected asks once ("2 items"), scratches both, and lists the drive once', p)

        # Copy and move several rows to another drive.
        w9 = dict(id=2, x=2, y=3, w=28, h=16, title=b'Drive 9', top=0)
        g9 = scene.scene.geometry(dict(kind=scene.KIND, x=2, y=3, w=28, h=16))
        p.cell(35, 7); p.click(double=True)
        p.cell(1, 12); p.click()                                # drive 8 on top
        w9['selected'] = None

        def both(anchor=None, selection=()):
            w8['selected'], w8['selection'] = anchor, set(selection)
            return scene.picture([w9, w8], {1: listed(), 2: listed(9)}, selected_icon=1)
        p.expect(both(), 'drive 8 over drive 9')
        g8 = scene.scene.geometry(dict(kind=scene.KIND, x=1, y=2, w=28, h=16))
        a1, a2 = row(b'A1'), row(b'A2')
        p.cell(3, g8['wy']+a1); p.click(); p.cell(3, g8['wy']+a2)
        p.ram[0xd3] = 1; p.click(); p.ram[0xd3] = 0
        p.cell(3, g8['wy']+a1); p.frame(down=True)             # drag both by the first
        for _ in range(24):
            p.frame()
        p.expect(outline(both(a1, {a1, a2}), (3, g8['wy']+a1, 10, 1)), 'held on a selected row')
        p.cell(29, 10); p.frame(down=False)                     # drive 9's right edge
        for _ in range(4):
            p.frame()
        ask = b'[2][Copy 2 items|to Drive 9?][Copy|Move|Cancel]'
        p.expect(scene.scene.draw(both(a1, {a1, a2}), ask, 1, 1)[0], 'copy two asked')
        stop = opens_seen(p, [b'A1', b'A2'])
        p.key(13)
        seen = stop()
        base = both(a1, {a1, a2})
        steps = [as_read(progress(base, b'Copying %d/2' % n, w8)) for n in (1, 2)]
        assert seen == [steps[0]]*4+[steps[1]]*4, [steps.index(s) if s in steps else None for s in seen]
        for name in (b'A1', b'A2'):
            assert p.io.files[9, name, b'S'] == p.io.files[8, name, b'S']
        p.expect(both(a1, {a1, a2}), 'copied, drive 9 listed')
        done('dragging a multiple selection by one of its rows copies every selected row after one question, '
             'under a window titled "Copying 1/2", then "Copying 2/2", that closes at the end', p)

        a3, a4 = row(b'A3'), row(b'A4')
        data = {n: bytes(p.io.files[8, n, b'S']) for n in (b'A3', b'A4')}
        p.cell(3, g8['wy']+a3); p.click(); p.cell(3, g8['wy']+a4)
        p.ram[0xd3] = 1; p.click(); p.ram[0xd3] = 0
        mark = len(p.io.events)
        p.cell(3, g8['wy']+a4); p.frame(down=True)
        for _ in range(24):
            p.frame()
        p.cell(35, 7); p.frame(down=False)                      # the Drive 9 icon
        for _ in range(4):
            p.frame()
        before = both(a4, {a3, a4})
        p.key(9)
        stop = opens_seen(p, [b'A3', b'A4'])
        p.key(13)                                               # Move
        seen = stop()
        steps = [as_read(progress(before, b'Moving %d/2' % n, w8)) for n in (1, 2)]
        assert [k for k, _ in groupby(seen)] == steps, [steps.index(s) if s in steps else None for s in seen]
        for name in (b'A3', b'A4'):
            assert p.io.files[9, name, b'S'] == data[name] and (8, name, b'S') not in p.io.files
        assert [e for e in p.io.events[mark:] if e[0] == 'dos'] == [('dos', 8, b'S0:A3'), ('dos', 8, b'S0:A4')]
        p.expect(both(), 'moved, both listed')
        done('Move with two rows: both copied and verified, then both scratched, under "Moving 1/2" and "Moving 2/2"; '
             'each drive is listed once', p)
        report['passed'] = True
    finally:
        args.report.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
