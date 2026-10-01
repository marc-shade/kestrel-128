#!/usr/bin/env python3
"""GEM desktop drag-and-drop copy and move (GDCPY.PRG, docs/GEM-DESKTOP.md) in
the Py65 model: a listing row dropped on another window or a drive icon is
copied there between IEC drives and USB storage, verified by reopening both
files, and Move deletes the source only after that. Refusals, an existing
name, Esc during the copy and a changed destination are reported with alerts;
complete surfaces are compared with tests/native_gemdesk_scene.py."""
import argparse
import json
from pathlib import Path
import random
import sys

sys.dont_write_bytecode = True
from ci_native_gemdesk import ROOT, Gem, AESVC, entries_for, scene

GDCPY = {}                          # (Gem supplies GDCPY.PRG with the other modules)
RNG = random.Random(128)


def data(n):
    return bytes(RNG.randrange(256) for _ in range(n))


def drag(p, cx, cy, tx, ty):
    """Press on a row, hold past the double-click window, release elsewhere."""
    p.cell(cx, cy); p.frame(down=True)
    for _ in range(24):
        p.frame()
    p.cell(tx, ty); p.frame(down=False)
    for _ in range(4):
        p.frame()


def outline(before, rect):
    """before with the AES's one-pixel XOR outline of a cell rectangle."""
    x, y, w, h = rect
    data = bytearray(before)

    def xor(x0, y0, x1, y1):
        for py in range(y0, y1):
            for px in range(x0, x1):
                data[py//8*320+px//8*8+py % 8] ^= 128 >> (px % 8)
    X0, Y0, X1, Y1 = x*8, y*8, (x+w)*8, (y+h)*8
    xor(X0, Y0, X1, Y0+1); xor(X0, Y1-1, X1, Y1)
    xor(X0, Y0+1, X0+1, Y1-1); xor(X1-1, Y0+1, X1, Y1-1)
    return bytes(data)


def draw(before, text, default, focus=None):
    return scene.scene.draw(before, text, default, default if focus is None else focus)[0]


progress = scene.progress


def as_read(want):
    """want as Gem.surface() returns it: the 1351 sprite in the surface tail."""
    from launcher_scene import pointer_shape
    want = bytearray(want)
    want[8000:8128] = pointer_shape(); want[9208:9210] = b'\x7d\x7e'
    return bytes(want)


def opens_seen(p, names):
    """Record the surface at every KERNAL OPEN of a file named in names (the
    copy's own opens, not the listings read after it) until stop() is called."""
    stub, seen = p.io.stub, []

    def watch(cpu):
        if cpu.pc == 0xffc0:
            at, n = p.ram[0xbb] | p.ram[0xbc] << 8, p.ram[0xb7]
            name = bytes(p.ram[at:at+n])
            if any(x in name for x in names):
                seen.append(p.surface())
        return stub(cpu)
    p.io.stub = watch

    def stop():
        p.io.stub = stub
        return seen
    return stop


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
        # Two IEC drives: a window on each, drive 9's on top.
        big, check = data(1300), data(1100)
        # Three 16-character names on both drives: Keep both must shorten them.
        longs = [b'SIXTEEN CHARS 16', b'REPORT.TEXTFILE1', b'A.BCDEFGHIJKLMNO']
        files = {**GDCPY, (8, b'AESVC.PRG', b'P'): AESVC, (8, b'TWIN', b'S'): data(10),
                 (9, b'NINE', b'S'): data(300), (9, b'TWIN', b'S'): data(20), (9, b'MOVER', b'U'): data(600),
                 (9, b'BIG', b'S'): big, (9, b'CHECK', b'S'): check, (9, b'QUICK', b'S'): data(200),
                 **{(8, name, b'S'): data(30+i) for i, name in enumerate(longs)},
                 **{(9, name, b'S'): data(40+i) for i, name in enumerate(longs)}}
        original = dict(files)
        p = Gem(files)
        w8 = dict(id=1, x=1, y=2, w=28, h=16, title=b'Drive 8', top=0)
        w9 = dict(id=2, x=2, y=3, w=28, h=16, title=b'Drive 9', top=0)
        g9 = scene.scene.geometry(dict(kind=scene.KIND, x=2, y=3, w=28, h=16))

        def listed(device):
            return scene.ordered(entries_for(p.io.files, device), 0)

        def shown(selected8=None, selected9=None, icon=1):
            w8['selected'], w9['selected'] = selected8, selected9
            return scene.picture([w8, w9], {1: listed(8), 2: listed(9)}, selected_icon=icon)

        def row9(name):
            return [e['name'] for e in listed(9)].index(name)

        p.cell(35, 3); p.click(double=True)
        p.cell(35, 7); p.click(double=True)
        p.expect(shown(), 'two drives')

        # Copy: drive 9's NINE dropped on drive 8's window (its visible left edge).
        at = row9(b'NINE')
        mark = len(p.io.events)
        p.cell(3, g9['wy']+at); p.frame(down=True)
        for _ in range(24):
            p.frame()
        before = shown(selected9=at)
        p.expect(outline(before, (3, g9['wy']+at, 10, 1)), 'outline at the press')
        p.cell(33, 20); p.frame(down=True); p.frame(down=True)
        p.expect(outline(before, (30, 20, 10, 1)), 'outline follows (kept on screen)')
        p.cell(1, 12); p.frame(down=False)
        for _ in range(4):
            p.frame()
        ask = b'[2][Copy NINE|to Drive 8?][Copy|Move|Cancel]'
        p.expect(draw(before, ask, 1), 'copy asked')
        stop = opens_seen(p, [b'NINE'])
        p.key(13)
        seen = stop()
        assert len(seen) == 4 and set(seen) == {as_read(progress(before, b'Copying 1/1', w9))}, len(seen)
        assert p.io.files[8, b'NINE', b'S'] == original[9, b'NINE', b'S']
        assert p.io.files[9, b'NINE', b'S'] == original[9, b'NINE', b'S']
        assert not [e for e in p.io.events[mark:] if e[0] == 'dos'], 'a copy scratches nothing'
        p.expect(shown(selected9=row9(b'NINE')), 'drive 8 listed again with NINE')
        done('a dragged row shows an XOR outline that follows the pointer; dropped on another drive\'s window it '
             'is copied there after Copy is chosen under a "Copying 1/1" window, and the target lists it', p)

        # Move: MOVER (USR) dropped on the Boot icon; Tab to Move.
        at = row9(b'MOVER')
        mark = len(p.io.events)
        drag(p, 3, g9['wy']+at, 35, 3)
        before = shown(selected9=at)
        ask = b'[2][Copy MOVER|to Drive 8?][Copy|Move|Cancel]'
        p.expect(draw(before, ask, 1), 'move asked')
        p.key(9); p.expect(draw(before, ask, 1, 2), 'move focused')
        p.key(13)
        assert p.io.files[8, b'MOVER', b'U'] == original[9, b'MOVER', b'U']
        assert (9, b'MOVER', b'U') not in p.io.files
        assert [e for e in p.io.events[mark:] if e[0] == 'dos'] == [('dos', 9, b'S0:MOVER')]
        p.expect(shown(), 'both drives listed again')
        done('Move on a drive icon: the verified copy keeps the type (USR), then the source is scratched without a second question', p)

        # An existing name on the target: the drive's refusal, nothing changed.
        at = row9(b'TWIN')
        drag(p, 3, g9['wy']+at, 35, 3)
        before = shown(selected9=at)
        p.expect(draw(before, b'[2][Copy TWIN|to Drive 8?][Copy|Move|Cancel]', 1), 'twin asked')
        p.key(13)
        conflict = b'[2][TWIN already|exists on Drive 8.][Replace|Keep both|Skip]'
        p.expect(draw(progress(before, b'Copying 1/1', w9), conflict, 3), 'exists')
        p.key(13); p.expect(before, 'exists closed')                  # Skip, the default
        assert p.io.files[8, b'TWIN', b'S'] == original[8, b'TWIN', b'S']
        assert p.io.files[9, b'TWIN', b'S'] == original[9, b'TWIN', b'S']
        done('a name that exists on the target (the drive answers 63) asks Replace, Keep both or Skip over the '
             'progress window; Skip, the default, leaves both files unchanged', p)

        mark = len(p.io.events)
        drag(p, 3, g9['wy']+at, 35, 3)
        p.key(13)                                                     # Copy
        p.expect(draw(progress(before, b'Copying 1/1', w9), conflict, 3), 'exists again')
        p.key(ord('1'))                                               # Replace
        assert p.io.files[8, b'TWIN', b'S'] == original[9, b'TWIN', b'S'], 'the target holds the source now'
        assert p.io.files[9, b'TWIN', b'S'] == original[9, b'TWIN', b'S']
        assert [e for e in p.io.events[mark:] if e[0] == 'dos'] == [('dos', 8, b'S0:TWIN')]
        p.expect(shown(selected9=at), 'replaced')
        done('Replace scratches the target (S0:NAME, one file scratched) and copies again, compared as any copy', p)

        # Keep both: the copy takes the source's name with "-2"; a second time "-2" is taken, so "-3".
        for suffix in (b'-2', b'-3'):
            mark = len(p.io.events)
            drag(p, 3, g9['wy']+at, 35, 3)
            before = shown(selected9=at)
            p.key(13)                                                 # Copy
            p.expect(draw(progress(before, b'Copying 1/1', w9), conflict, 3), 'keep both offered '+suffix.decode())
            p.key(ord('2'))                                           # Keep both
            assert p.io.files[8, b'TWIN'+suffix, b'S'] == original[9, b'TWIN', b'S'], suffix
            assert p.io.files[8, b'TWIN', b'S'] == original[9, b'TWIN', b'S']   # untouched (replaced above)
            assert not [e for e in p.io.events[mark:] if e[0] == 'dos'], 'Keep both scratches nothing'
            p.expect(shown(selected9=at), 'kept both '+suffix.decode())
        done('Keep both copies under the source\'s name with "-2" and scratches nothing; when that name is taken '
             'too the next number is used without asking again ("-3")', p)

        # Esc in the conflict alert is Stop: nothing more is copied.
        mark = len(p.io.events)
        drag(p, 3, g9['wy']+at, 35, 3)
        before = shown(selected9=at)
        p.key(13)
        p.expect(draw(progress(before, b'Copying 1/1', w9), conflict, 3), 'exists, then Esc')
        p.key(27)
        p.expect(shown(selected9=at), 'stopped at the conflict')
        assert (8, b'TWIN-4', b'S') not in p.io.files
        assert not [e for e in p.io.events[mark:] if e[0] == 'dos']
        done('Esc in the name-conflict alert stops the copy and changes nothing', p)

        # A drive keeps 16 characters: the part before the suffix is shortened (before the
        # extension when there is room for it, else the suffix ends the name).
        for name, kept in zip(longs, [b'SIXTEEN CHARS -2', b'REPO-2.TEXTFILE1', b'A.BCDEFGHIJKLM-2']):
            row = row9(name)
            drag(p, 3, g9['wy']+row, 35, 3)
            before = shown(selected9=row)
            p.key(13)
            ask = b'[2]['+name+b' already|exists on Drive 8.][Replace|Keep both|Skip]'
            p.expect(draw(progress(before, b'Copying 1/1', w9), ask, 3), 'long conflict '+name.decode())
            p.key(ord('2'))
            assert p.io.files[8, kept, b'S'] == original[9, name, b'S'], (name, kept)
            assert p.io.files[8, name, b'S'] == original[8, name, b'S']
            p.expect(shown(selected9=row), 'long kept '+kept.decode())
        done('Keep both on a drive stays within 16 characters: SIXTEEN CHARS -2, REPO-2.TEXTFILE1 (the extension '
             'kept), A.BCDEFGHIJKLM-2 (an extension too long to keep)', p)

        # Cancel in the question: nothing is opened.
        mark = len(p.io.events)
        drag(p, 3, g9['wy']+at, 1, 12)
        before = shown(selected9=at)
        p.key(9); p.key(9)
        p.expect(draw(before, b'[2][Copy TWIN|to Drive 8?][Copy|Move|Cancel]', 1, 3), 'cancel focused')
        p.key(13); p.expect(before, 'cancelled')
        assert not [e for e in p.io.events[mark:] if e[0] in ('open', 'dos')]
        done('Cancel in the question opens and changes nothing', p)

        # Esc during the copy stops it between chunks; the partial file stays and is listed.
        at = row9(b'BIG')
        drag(p, 3, g9['wy']+at, 1, 12)
        before = shown(selected9=at)         # the alert opens before drive 8 is listed again
        p.keys += [13, 27]                   # Copy, then Esc read by the copy's first cancel check
        p.loop(); p.events += 2
        assert p.io.files[8, b'BIG', b'S'] == big[:512], len(p.io.files[8, b'BIG', b'S'])
        assert p.io.files[9, b'BIG', b'S'] == big
        stopped = b'[1][Copy stopped.|Drive 8 may hold|part of BIG.][OK]'
        p.expect(draw(progress(before, b'Copying 1/1', w9), stopped, 1), 'stopped')
        p.key(13)
        p.expect(shown(selected9=at), 'partial file listed')
        done('Esc during a copy stops it after the chunk in hand; the partial target stays, is said to, and is listed', p)

        # A destination that changes before the comparison is detected.
        at = row9(b'CHECK')
        drag(p, 3, g9['wy']+at, 1, 12)
        before = shown(selected9=at)
        stub, changed = p.io.stub, []

        def corrupt(cpu):
            key = (8, b'CHECK', b'S')
            if not changed and cpu.pc == 0xffc0 and len(p.io.files.get(key, b'')) == len(check):
                p.io.files[key][-1] ^= 1
                changed.append(True)
            return stub(cpu)
        p.io.stub = corrupt
        p.key(13)
        p.io.stub = stub
        assert changed and p.io.files[9, b'CHECK', b'S'] == check
        mismatch = b'[3][The copy does not match.|The original is kept.][OK]'
        p.expect(draw(progress(before, b'Copying 1/1', w9), mismatch, 1), 'mismatch')
        p.key(13)
        p.expect(shown(selected9=at), 'changed copy listed')
        done('a target that changes after writing fails the reopened comparison; the source is kept', p)

        # Preferences: Confirm copies off; a drop then copies without the question.
        before = shown(selected9=at)
        p.key(0x85); p.key(0x1d); p.key(0x1d); p.key(0x1d); p.key(13)   # Options:Preferences...
        p.expect(scene.prefs_dialog(before, True, 0), 'preferences')
        p.key(9); p.key(32)
        p.expect(scene.prefs_dialog(before, True, 0, focus=2, copies=False), 'copies unticked')
        p.key(13)
        assert p.ram[p.symbol('gm_confirm')] == 3, p.ram[p.symbol('gm_confirm')]   # deletes asked, copies not
        p.expect(before, 'preferences closed')
        at = row9(b'QUICK')
        drag(p, 3, g9['wy']+at, 1, 12)
        assert p.io.files[8, b'QUICK', b'S'] == original[9, b'QUICK', b'S']
        p.expect(shown(selected9=row9(b'QUICK')), 'copied without asking')
        done('with Confirm copies off in Preferences (gm_confirm bit 1), a dropped row is copied without the question', p)

        # Preferences: Confirm overwrites off; a name on the target is replaced without the question.
        before = shown(selected9=row9(b'QUICK'))
        p.key(0x85); p.key(0x1d); p.key(0x1d); p.key(0x1d); p.key(13)
        p.expect(scene.prefs_dialog(before, True, 0, copies=False), 'preferences show copies off')
        p.key(9); p.key(9); p.key(32)
        p.expect(scene.prefs_dialog(before, True, 0, focus=3, copies=False, overwrites=False), 'overwrites unticked')
        p.key(13)
        assert p.ram[p.symbol('gm_confirm')] == 11, p.ram[p.symbol('gm_confirm')]   # bits 0, 1 and 3
        p.expect(before, 'preferences closed again')
        quick2 = data(200)                                            # new bytes, same size: drive 9's listing stays
        p.io.files[9, b'QUICK', b'S'] = bytearray(quick2)
        mark = len(p.io.events)
        drag(p, 3, g9['wy']+row9(b'QUICK'), 1, 12)
        assert p.io.files[8, b'QUICK', b'S'] == quick2, 'the target holds the new source'
        assert [e for e in p.io.events[mark:] if e[0] == 'dos'] == [('dos', 8, b'S0:QUICK')]
        p.expect(shown(selected9=row9(b'QUICK')), 'replaced without asking')
        done('with Confirm overwrites off (gm_confirm bit 3), a name on the target is scratched and copied again '
             'without the Replace question', p)

        # USB storage: IEC to USB, USB to IEC (with Move), USB to USB, refusals.
        long = b'a name longer than sixteen.txt'
        tree = {b'/': [b'\x10Usb0'],
                b'/Usb0': [b'\x10Docs', b'\x20GAME.PRG', b'\x20notes.txt', b'\x20'+long],
                b'/Usb0/Docs': [], b'/shell': [], b'/browser': []}
        game, notes = data(900), data(700)
        u = Gem({**GDCPY, (8, b'AESVC.PRG', b'P'): AESVC, (8, b'LETTER', b'S'): data(400)},
                usb=dict(dirs=tree, files={b'/Usb0/GAME.PRG': game, b'/Usb0/notes.txt': notes, b'/Usb0/'+long: data(5)}))
        dos = u.ultimate
        letter = u.io.files[8, b'LETTER', b'S']
        wu = dict(id=1, x=1, y=2, w=28, h=16, title=b'USB /Usb0', top=0)
        wb = dict(id=2, x=2, y=3, w=28, h=16, title=b'Drive 8', top=0)
        gb = scene.scene.geometry(dict(kind=scene.KIND, x=2, y=3, w=28, h=16))

        def usb_listed(path=b'/Usb0'):
            return scene.ordered(scene.usb_entries(dos.directories[path]), 0)

        def ushown(windows, icon=0):
            of = {1: usb_listed(), 2: scene.ordered(entries_for(u.io.files, 8), 0)}
            return scene.picture(windows, of, selected_icon=icon, usb=True)

        u.cell(35, 11); u.click(double=True)
        u.cell(3, 3); u.click(double=True)                         # /Usb0
        u.cell(35, 3); u.click(double=True)                        # drive 8 over it
        wu['selected'] = wb['selected'] = None
        u.expect(ushown([wu, wb]), 'usb and drive 8')
        at = [e['name'] for e in scene.ordered(entries_for(u.io.files, 8), 0)].index(b'LETTER')
        drag(u, 3, gb['wy']+at, 1, 12)
        wb['selected'] = at
        before = ushown([wu, wb])
        u.expect(draw(before, b'[2][Copy LETTER|to USB?][Copy|Move|Cancel]', 1), 'to usb asked')
        u.key(13)
        assert dos.files[b'/Usb0/LETTER'] == letter and (8, b'LETTER', b'S') in u.io.files
        assert b'\x20LETTER' in dos.directories[b'/Usb0']
        u.expect(ushown([wu, wb]), 'usb listed again')
        done('an IEC file dropped on a USB window is copied into that folder (context 1) and listed there', u)

        letter2 = data(420)                                           # the drive's LETTER changes, then again
        u.io.files[8, b'LETTER', b'S'] = bytearray(letter2)
        mark = len(dos.commands)
        drag(u, 3, gb['wy']+at, 1, 12)
        wb['selected'] = at
        before = ushown([wu, wb])
        u.key(13)                                                     # Copy
        conflict = b'[2][LETTER already|exists on USB.][Replace|Keep both|Skip]'
        u.expect(draw(progress(before, b'Copying 1/1', wb), conflict, 3), 'usb exists')
        assert dos.files[b'/Usb0/LETTER'] == letter
        u.key(ord('1'))                                               # Replace
        assert dos.files[b'/Usb0/LETTER'] == letter2
        sent = [bytes(c) for c in dos.commands[mark:]]
        assert [c[2:] for c in sent if c[1] == 0x09] == [b'/Usb0/LETTER'], sent
        u.expect(ushown([wu, wb]), 'usb replaced')
        done('onto USB, FILE_STAT finds the name first; Replace deletes it (DELETE_FILE) and copies the new bytes', u)

        u.cell(1, 12); u.click()                                   # top the USB window
        wu['selected'] = None
        u.expect(ushown([wb, wu]), 'usb topped')
        at = [e['name'] for e in usb_listed()].index(b'GAME.PRG')
        drag(u, 3, 3+at, 35, 3)
        wu['selected'] = at
        before = ushown([wb, wu])
        u.expect(draw(before, b'[2][Copy GAME.PRG|to Drive 8?][Copy|Move|Cancel]', 1), 'from usb asked')
        u.key(9); u.key(13)                                        # Move
        assert u.io.files[8, b'GAME.PRG', b'P'] == game, 'from USB, .PRG is a PRG file'
        assert b'/Usb0/GAME.PRG' not in dos.files and b'\x20GAME.PRG' not in dos.directories[b'/Usb0']
        wu['selected'] = wb['selected'] = None
        u.expect(ushown([wb, wu]), 'moved from usb')
        done('Move from USB to a drive: ".PRG" becomes a PRG file; DELETE_FILE then removes the source', u)

        at = [e['name'] for e in usb_listed()].index(b'notes.txt')
        drag(u, 3, 3+at, 35, 3); u.key(13)
        assert u.io.files[8, b'notes.txt', b'S'] == notes and dos.files[b'/Usb0/notes.txt'] == notes
        done('any other USB file becomes a SEQ file under its own name', u)

        at = [e['name'] for e in usb_listed()].index(long[:16])
        drag(u, 3, 3+at, 35, 3)
        wu['selected'] = at
        before = ushown([wb, wu])
        u.key(13)
        badname = b'[1][This name does not fit|a drive: 16 characters,|no * ? , = : @ or quote.][OK]'
        u.expect(draw(before, badname, 1), 'long name')
        u.key(13)
        assert not [k for k in u.io.files if k[1].startswith(b'a name')]
        at = [e['name'] for e in usb_listed()].index(b'Docs')
        drag(u, 3, 3+at, 35, 3)
        wu['selected'] = at
        refused = b'[1][Folders onto a drive,|REL and unclosed files|cannot be copied.][OK]'
        u.expect(draw(ushown([wb, wu]), refused, 1), 'folder refused')
        u.key(13)
        done('a USB name that does not fit a drive, and a folder dropped on a drive, are refused before anything is opened', u)

        u.cell(35, 11); u.click(double=True)                       # a second USB window: /Usb0/Docs
        u.cell(4, 5); u.click(double=True)
        u.cell(4, 5); u.click(double=True)
        wd = dict(id=3, x=3, y=4, w=28, h=16, title=b'USB /Usb0/Docs', top=0, selected=None)
        u.cell(1, 12); u.click()                                   # /Usb0 on top again
        at = [e['name'] for e in usb_listed()].index(b'notes.txt')
        drag(u, 3, 3+at, 30, 12)                                   # the Docs window's right edge
        u.key(13)
        assert dos.files[b'/Usb0/Docs/notes.txt'] == notes and dos.files[b'/Usb0/notes.txt'] == notes
        assert b'\x20notes.txt' in dos.directories[b'/Usb0/Docs']
        of = {1: usb_listed(), 2: scene.ordered(entries_for(u.io.files, 8), 0), 3: usb_listed(b'/Usb0/Docs')}
        wu['selected'] = None                                     # every USB window is listed again
        u.expect(scene.picture([wb, wd, wu], of, selected_icon=3, usb=True), 'usb to usb')
        done('USB to USB: the target is opened on the other DOS context and listed in its window', u)
        report['passed'] = True
    finally:
        args.report.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
