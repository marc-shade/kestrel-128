#!/usr/bin/env python3
"""GEM desktop folder copy and move (GDCPY.PRG, docs/GEM-DESKTOP.md) in the
Py65 model: a USB folder dropped on another USB window is copied as a tree
(CREATE_DIR proven by FILE_STAT, each file copied and compared, subfolders
descended into), under the progress window; an existing name, a copy into
itself and a folder dropped on a drive are refused; Esc stops between entries; Move copies the tree, then
deletes the source's contents deepest first and the emptied folder last.
Complete surfaces are compared with tests/native_gemdesk_scene.py."""
import argparse
import json
from pathlib import Path
import random
import sys

sys.dont_write_bytecode = True
from ci_native_gemdesk import Gem, AESVC, scene
from ci_native_gemdesk_copy import drag, draw, progress

RNG = random.Random(4096)


def data(n):
    return bytes(RNG.randrange(256) for _ in range(n))


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
        a, b, c = data(700), data(1300), data(10)
        tree = {b'/': [b'\x10Usb0'],
                b'/Usb0': [b'\x10Clash', b'\x10Dest', b'\x10Esc', b'\x10Out', b'\x10Proj', b'\x20top.txt'],
                b'/Usb0/Clash': [b'\x20Proj'],
                b'/Usb0/Proj': [b'\x10Sub', b'\x20a.txt', b'\x20b.prg'],
                b'/Usb0/Proj/Sub': [b'\x20c.bin'],
                b'/Usb0/Dest': [], b'/Usb0/Esc': [], b'/Usb0/Out': [], b'/shell': [], b'/browser': []}
        files = {b'/Usb0/Proj/a.txt': a, b'/Usb0/Proj/b.prg': b, b'/Usb0/Proj/Sub/c.bin': c, b'/Usb0/top.txt': data(5),
                 b'/Usb0/Clash/Proj': data(3)}
        u = Gem({(8, b'AESVC.PRG', b'P'): AESVC}, usb=dict(dirs=tree, files=files))
        dos = u.ultimate
        wu = dict(id=1, x=1, y=2, w=28, h=16, title=b'USB /Usb0', top=0, selected=None)
        wt = dict(id=2, x=2, y=3, w=28, h=16, title=b'USB /Usb0/Dest', top=0, selected=None)

        def listed(path):
            return scene.ordered(scene.usb_entries(dos.directories[path]), 0)

        def row(path, name):
            return [e['name'] for e in listed(path)].index(name)

        def shown(target=b'/Usb0/Dest'):
            wt['title'] = b'USB '+target
            return scene.picture([wt, wu], {1: listed(b'/Usb0'), 2: listed(target)}, selected_icon=3, usb=True)

        def open_target(name):
            """The second window, from the root to /Usb0/name; then /Usb0 on top."""
            u.cell(35, 11); u.click(double=True)                   # a second USB window: the root
            u.cell(4, 4); u.click(double=True)                     # Usb0
            u.cell(4, 4+row(b'/Usb0', name)); u.click(double=True)
            u.cell(1, 12); u.click()                               # /Usb0 on top again

        u.cell(35, 11); u.click(double=True)
        u.cell(3, 3); u.click(double=True)                         # /Usb0
        open_target(b'Dest')
        u.expect(shown(), 'two usb windows')

        # Copy: Proj dropped on Dest (its right edge, column 29).
        at = row(b'/Usb0', b'Proj')
        mark = len(dos.commands)
        drag(u, 3, 3+at, 29, 12)
        wu['selected'] = at
        before = shown()
        u.expect(draw(before, b'[2][Copy Proj|to USB?][Copy|Move|Cancel]', 1), 'asked')
        u.key(13)
        assert sorted(dos.directories[b'/Usb0/Dest/Proj']) == sorted(tree[b'/Usb0/Proj']), dos.directories[b'/Usb0/Dest/Proj']
        assert dos.directories[b'/Usb0/Dest/Proj/Sub'] == [b'\x20c.bin']
        for leaf, want in ((b'Proj/a.txt', a), (b'Proj/b.prg', b), (b'Proj/Sub/c.bin', c)):
            assert dos.files[b'/Usb0/Dest/'+leaf] == want, leaf
            assert dos.files[b'/Usb0/'+leaf] == want, leaf
        sent = [bytes(x) for x in dos.commands[mark:]]
        made = [x[2:] for x in sent if x[1] == 0x16]
        assert made == [b'/Usb0/Dest/Proj', b'/Usb0/Dest/Proj/Sub'], made
        assert not [x for x in sent if x[1] == 0x09], 'a copy deletes nothing'
        wu['selected'] = None
        u.expect(shown(), 'copied, listed')
        done('a USB folder dropped on another USB window is copied as a tree: CREATE_DIR for it and its subfolder, '
             'every file copied and compared, the source unchanged, and both windows listed again', u,
             folders=[m.decode() for m in made])

        # The same folder again: merged into the one on the target, each name on both asked about.
        a2 = data(700)
        dos.files[b'/Usb0/Dest/Proj/a.txt'] = a2                   # the target's a.txt differs now
        mark = len(dos.commands)
        drag(u, 3, 3+at, 29, 12)
        wu['selected'] = at
        before = shown()
        u.key(13)                                                   # Copy
        copying = progress(before, b'Copying 1/1', wu)

        def conflict(leaf):
            return draw(copying, b'[2]['+leaf+b' already|exists on USB.][Replace|Skip|Stop]', 2)
        u.expect(conflict(b'c.bin'), 'c.bin conflict')              # Sub first, as the folder lists it
        u.key(13)                                                   # Skip
        u.expect(conflict(b'a.txt'), 'a.txt conflict')
        u.key(ord('1'))                                             # Replace
        u.expect(conflict(b'b.prg'), 'b.prg conflict')
        u.key(13)
        sent = [bytes(x) for x in dos.commands[mark:]]
        assert not [x for x in sent if x[1] == 0x16], 'nothing made: both folders were there'
        assert [x[2:] for x in sent if x[1] == 0x09] == [b'/Usb0/Dest/Proj/a.txt'], 'only the replaced file deleted'
        assert dos.files[b'/Usb0/Dest/Proj/a.txt'] == a and dos.files[b'/Usb0/Proj/a.txt'] == a
        assert dos.files[b'/Usb0/Dest/Proj/b.prg'] == b and dos.files[b'/Usb0/Dest/Proj/Sub/c.bin'] == c
        wu['selected'] = None
        u.expect(shown(), 'merged, listed')
        done('a folder whose name is a folder on the target is merged into it (no CREATE_DIR): each file on both '
             'asks Replace, Skip or Stop by its own name, in the source folder\'s order', u)

        mark = len(dos.commands)
        drag(u, 3, 3+at, 29, 12)
        u.key(9); u.key(13)                                         # Move
        for _ in range(3):
            u.key(13)                                               # Skip each of the three
        assert not [x for x in dos.commands[mark:] if bytes(x)[1] == 0x09], 'a skipped Move deletes nothing'
        for leaf, want in ((b'Proj/a.txt', a), (b'Proj/b.prg', b), (b'Proj/Sub/c.bin', c)):
            assert dos.files[b'/Usb0/'+leaf] == want, leaf
        u.expect(shown(), 'skipped move, listed')
        done('a Move in which a name was skipped keeps the whole source folder', u)

        # A file on the target with the folder's name: refused.
        u.cell(10, 18); u.click()                                   # the target window on top (its bottom row)
        u.cell(2, 3); u.click()                                     # its close box goes up a level, to /Usb0
        u.cell(4, 4+row(b'/Usb0', b'Clash')); u.click(double=True)
        u.cell(1, 12); u.click()
        u.expect(shown(b'/Usb0/Clash'), 'target is clash')
        mark = len(dos.commands)
        drag(u, 3, 3+at, 29, 12)
        wu['selected'] = at
        before = shown(b'/Usb0/Clash')
        u.key(13)
        exists = b'[1][Proj already|exists on USB.][OK]'
        u.expect(draw(progress(before, b'Copying 1/1', wu), exists, 1), 'exists')
        u.key(13)
        assert not [x for x in dos.commands[mark:] if bytes(x)[1] in (0x16, 0x09)], 'nothing made or deleted'
        u.expect(before, 'exists closed')
        done('a folder whose name is a file on the target is refused (FILE_STAT finds a file) over the progress '
             'window; nothing is made', u)

        # Into itself: the target window shows Proj itself.
        u.cell(10, 18); u.click()                                   # the target window on top (its bottom row)
        u.cell(2, 3); u.click()                                     # its close box goes up a level, to /Usb0
        u.cell(4, 4+row(b'/Usb0', b'Proj')); u.click(double=True)   # into Proj
        u.cell(1, 12); u.click()                                   # (a refusal lists nothing: Proj stays selected)
        u.expect(shown(b'/Usb0/Proj'), 'target is proj')
        mark = len(dos.commands)
        drag(u, 3, 3+at, 29, 12)
        wu['selected'] = at
        before = shown(b'/Usb0/Proj')
        u.key(13)
        itself = b'[1][A folder cannot be|copied into itself.][OK]'
        u.expect(draw(progress(before, b'Copying 1/1', wu), itself, 1), 'itself')
        u.key(13)
        assert not [x for x in dos.commands[mark:] if bytes(x)[1] in (0x16, 0x09)]
        assert b'/Usb0/Proj/Proj' not in dos.directories
        done('a folder dropped on a window showing that folder is refused: it cannot be copied into itself', u)

        # Esc during a folder copy: it stops before the first entry; the new folder stays and is listed.
        u.cell(10, 18); u.click()
        u.cell(2, 3); u.click()
        u.cell(4, 4+row(b'/Usb0', b'Esc')); u.click(double=True)
        u.cell(1, 12); u.click()
        u.expect(shown(b'/Usb0/Esc'), 'target is esc')
        mark = len(dos.commands)
        drag(u, 3, 3+at, 29, 12)
        before = shown(b'/Usb0/Esc')
        u.keys += [13, 27]                                          # Copy, then Esc read by the tree's first check
        u.loop(); u.events += 2
        stopped = b'[1][Copy stopped.|USB may hold|part of Proj.][OK]'
        u.expect(draw(progress(before, b'Copying 1/1', wu), stopped, 1), 'stopped')
        u.key(13)
        made = [bytes(x)[2:] for x in dos.commands[mark:] if bytes(x)[1] == 0x16]
        assert made == [b'/Usb0/Esc/Proj'] and dos.directories[b'/Usb0/Esc/Proj'] == [], made
        assert not [x for x in dos.commands[mark:] if bytes(x)[1] == 0x09]
        wu['selected'] = None                                       # the target made something: USB listed again
        u.expect(shown(b'/Usb0/Esc'), 'stopped, listed')
        done('Esc during a folder copy stops it before the next entry; the folder made so far stays, is said to, '
             'and is listed', u)

        # Move: Proj onto Out; the source tree is deleted after the copy.
        u.cell(10, 18); u.click()
        u.cell(2, 3); u.click()                                     # the target window back to /Usb0
        u.cell(4, 4+row(b'/Usb0', b'Out')); u.click(double=True)
        u.cell(1, 12); u.click()
        u.expect(shown(b'/Usb0/Out'), 'target is out')
        mark = len(dos.commands)
        drag(u, 3, 3+at, 29, 12)
        u.key(9); u.key(13)                                         # Move
        for leaf, want in ((b'Proj/a.txt', a), (b'Proj/b.prg', b), (b'Proj/Sub/c.bin', c)):
            assert dos.files[b'/Usb0/Out/'+leaf] == want, leaf
            assert b'/Usb0/'+leaf not in dos.files, leaf
        assert b'/Usb0/Proj' not in dos.directories and b'/Usb0/Proj/Sub' not in dos.directories
        assert b'\x10Proj' not in dos.directories[b'/Usb0']
        deleted = [bytes(x)[2:] for x in dos.commands[mark:] if bytes(x)[1] == 0x09]
        assert deleted == [b'/Usb0/Proj/Sub/c.bin', b'/Usb0/Proj/Sub', b'/Usb0/Proj/a.txt', b'/Usb0/Proj/b.prg',
                           b'/Usb0/Proj'], deleted
        wu['selected'] = None                                       # listed again after the Move
        u.expect(shown(b'/Usb0/Out'), 'moved')
        done('Move of a folder: the tree is copied and compared, then the source\'s files and subfolders are deleted '
             'deepest first and the emptied folder last', u, deleted=[d.decode() for d in deleted])

        # A folder dropped on a drive icon is refused before anything is sent.
        mark = len(dos.commands)
        at = row(b'/Usb0', b'Dest')
        drag(u, 3, 3+at, 35, 3)
        wu['selected'] = at
        refused = b'[1][Folders onto a drive,|REL and unclosed files|cannot be copied.][OK]'
        u.expect(draw(shown(b'/Usb0/Out'), refused, 1), 'onto a drive')
        u.key(13)
        assert not [x for x in dos.commands[mark:] if bytes(x)[1] in (0x16, 0x09)]
        done('a folder dropped on a drive icon is refused before anything is opened or made', u)
        report['passed'] = True
    finally:
        args.report.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
