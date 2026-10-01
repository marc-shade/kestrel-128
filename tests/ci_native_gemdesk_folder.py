#!/usr/bin/env python3
"""GEM desktop File:New Folder (docs/GEM-DESKTOP.md) in the Py65 model: in a USB
window a dialog takes the name, Ultimate DOS CREATE_DIR makes the folder,
FILE_STAT confirms it is a directory, and the window lists it; bad names,
Cancel and IEC windows are refused without a command. Surfaces are compared
with tests/native_gemdesk_scene.py."""
import argparse
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
from ci_native_gemdesk import Gem, AESVC, scene


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
        tree = {b'/': [b'\x10Usb0'], b'/Usb0': [b'\x20notes.txt'], b'/shell': [], b'/browser': []}
        u = Gem({(8, b'AESVC.PRG', b'P'): AESVC}, usb=dict(dirs=tree, files={b'/Usb0/notes.txt': b'hi'}))
        dos = u.ultimate
        wu = dict(id=1, x=1, y=2, w=28, h=16, title=b'USB /Usb0', top=0)

        def shown():
            return scene.picture([wu], {1: scene.ordered(scene.usb_entries(dos.directories[b'/Usb0']), 0)},
                                 selected_icon=3, usb=True)

        def new_folder():
            u.key(0x85); u.key(0x1d)                           # F1, right: the File menu
            for _ in range(4):                                  # Show Info, Delete, Format, New Folder
                u.key(0x11)
            u.key(13)

        u.cell(35, 11); u.click(double=True)
        u.cell(3, 3); u.click(double=True)
        before = shown()
        u.expect(before, 'usb0')
        new_folder()
        u.expect(scene.newfolder_dialog(before), 'dialog')
        for c in b'Photos':
            u.key(c)
        u.expect(scene.newfolder_dialog(before, name=b'Photos'), 'named')
        mark = len(dos.commands)
        u.key(13)                                               # Create (the default)
        sent = [bytes(c) for c in dos.commands[mark:]]
        assert sent[0] == bytes([1, 0x16])+b'/Usb0/Photos', sent
        assert sent[1] == bytes([1, 0x08])+b'/Usb0/Photos\0', sent
        assert b'\x10Photos' in dos.directories[b'/Usb0'] and b'/Usb0/Photos' in dos.directories
        u.expect(shown(), 'listed with the folder')
        done('New Folder in a USB window: CREATE_DIR with the full path, FILE_STAT confirms a directory, '
             'and the window lists it', u, commands=[c.hex() for c in sent])

        for bad in (b'a/b', b'dot.', b'what?'):
            new_folder()
            for c in bad:
                u.key(c)
            mark = len(dos.commands)
            u.key(13)
            alert = b'[1][That name cannot be|used for a folder.][OK]'
            u.expect(scene.scene.draw(shown(), alert, 1, 1)[0], 'bad name '+bad.decode())
            u.key(13)
            assert len(dos.commands) == mark, 'nothing sent for a refused name'
        new_folder(); u.key(ord('x')); u.key(9); u.key(9); u.key(13)   # Tab to Cancel
        u.expect(shown(), 'cancelled')
        done('names with / or ?, or ending in a period, and Cancel, send nothing', u)

        # Rename through Show Info: RENAME_FILE "old NUL new", then FILE_STAT of the new name.
        listed = scene.ordered(scene.usb_entries(dos.directories[b'/Usb0']), 0)
        at = [e['name'] for e in listed].index(b'notes.txt')
        u.cell(3, 3+at); u.click(); u.key(9)
        wu['selected'] = at
        before = scene.picture([wu], {1: listed}, selected_icon=3, usb=True)
        u.expect(scene.usb_info_dialog(before, b'notes.txt', b'File, 2 bytes'), 'info')
        u.key(21)                                               # Ctrl-U clears the field
        for c in b'memo.txt':
            u.key(c)
        mark = len(dos.commands)
        u.key(13)
        sent = [bytes(c) for c in dos.commands[mark:]]
        at = next(i for i, c in enumerate(sent) if c[1] == 0x0a)
        assert all(c[1] in (0x07, 0x11, 0x12, 0x13, 0x14) for c in sent[:at]), \
            ('before the rename only the directory is read again, for the full name', sent)
        assert sent[at] == bytes([1, 0x0a])+b'/Usb0/notes.txt\0/Usb0/memo.txt', sent
        assert sent[at+1] == bytes([1, 0x08])+b'/Usb0/memo.txt\0', sent
        assert dos.files.get(b'/Usb0/memo.txt') == b'hi' and b'/Usb0/notes.txt' not in dos.files
        wu['selected'] = None
        u.expect(shown(), 'renamed and listed')
        done('USB Show Info renames: RENAME_FILE with both full paths, FILE_STAT finds the new name, the window '
             'lists it', u, commands=[c.hex() for c in sent])

        g = Gem({(8, b'AESVC.PRG', b'P'): AESVC, (8, b'NOTE', b'S'): b'x'})
        g.cell(35, 3); g.click(double=True)
        w8 = dict(id=1, x=1, y=2, w=28, h=16, title=b'Drive 8', top=0)
        from ci_native_gemdesk import entries_for
        before = scene.picture([w8], {1: scene.ordered(entries_for(g.io.files), 0)}, selected_icon=0)
        g.key(0x85); g.key(0x1d)
        for _ in range(4):
            g.key(0x11)
        g.key(13)
        refused = b'[1][New folders are made|in USB windows.][OK]'
        g.expect(scene.scene.draw(before, refused, 1, 1)[0], 'iec refused')
        g.key(13); g.expect(before, 'closed')
        done('New Folder in a drive window is refused with an alert (IEC disks have no folders)', g)
        report['passed'] = True
    finally:
        args.report.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
