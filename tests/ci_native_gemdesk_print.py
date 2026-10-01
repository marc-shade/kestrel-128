#!/usr/bin/env python3
"""GEM desktop printing (docs/GEM-DESKTOP.md) in the Py65 model: a Printer icon
appears when IEC device 4 answers at start; rows dropped on it are printed
through the KERNAL (IEC files as stored, USB text with ASCII letters swapped
for PETSCII and CR/LF/CR LF as CR, Paint pictures in bit-image bands),
several at once after one question; a printer that stops answering is
reported. Surfaces are compared with
tests/native_gemdesk_scene.py; the printed bytes with the files."""
import argparse
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
from ci_native_gemdesk import ROOT, Gem, AESVC, entries_for, scene
import ci_native_files
sys.path.insert(0, str(ROOT))
from native_paint_format import encode as paint_encode  # noqa: E402

PICTURE = (bytes((i*7+i//320) & 255 for i in range(8000))+bytes(192)
           + b'\x61'*1000+b'\x10'*24)                  # a Paint surface: bitmap, pad, attributes

GDCPY = {}                          # (Gem supplies GDCPY.PRG with the other modules)


def with_printer(make):
    """Build a desktop whose IEC bus has a printer on device 4 from power-on."""
    original = ci_native_files.StreamIEC.__init__

    def init(self, *args, **kwargs):
        original(self, *args, **kwargs)
        self.printers[4] = bytearray()
    ci_native_files.StreamIEC.__init__ = init
    try:
        return make()
    finally:
        ci_native_files.StreamIEC.__init__ = original


def drag(p, cx, cy, tx, ty):
    p.cell(cx, cy); p.frame(down=True)
    for _ in range(24):
        p.frame()
    p.cell(tx, ty); p.frame(down=False)
    for _ in range(4):
        p.frame()


def petscii(data):
    out = bytearray()
    for i, c in enumerate(data):
        if c == 10:
            if i and data[i-1] == 13:
                continue
            c = 13
        elif c == 9:
            c = 32
        elif c != 13 and not 32 <= c < 127:
            continue
        elif 0x41 <= c <= 0x5a:
            c |= 0x80
        elif 0x61 <= c <= 0x7a:
            c &= 0xdf
        out.append(c)
    return bytes(out)


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
        note = bytes(range(32, 128))*3+b'\r'+bytes(range(0xc1, 0xdb))*40     # 1,425 bytes of PETSCII
        memo = b'MEMO\rTWO LINES\r'
        picture = paint_encode(PICTURE)
        files = {**GDCPY, (8, b'AESVC.PRG', b'P'): AESVC, (8, b'NOTE', b'S'): note, (8, b'MEMO', b'S'): memo,
                 (8, b'DIR', b'P'): b'\x01\x08'+bytes(20), (8, b'PIC', b'S'): picture,
                 (8, b'SHORT', b'S'): picture[:16+2000]}
        p = with_printer(lambda: Gem(files))
        del p.io.files[8, b'GDDSK.PRG', b'P']                   # printing is GDPRT's: every row stays in view
        p.expect(scene.desktop(printer=True), 'printer icon')
        assert ('open', 121, 4, 7, '') in p.io.events and not p.io.handles
        done('a printer on device 4 at start shows the Printer icon (KERNAL OPEN and CHKOUT on file 121)', p)

        w8 = dict(id=1, x=1, y=2, w=28, h=16, title=b'Drive 8', top=0)
        g = scene.scene.geometry(dict(kind=scene.KIND, x=1, y=2, w=28, h=16))

        def listed():
            return scene.ordered(entries_for(p.io.files, 8), 0)

        def row(name):
            return [e['name'] for e in listed()].index(name)

        def shown(anchor=None, selection=()):
            w8['selected'], w8['selection'] = anchor, set(selection)
            return scene.picture([w8], {1: listed()}, selected_icon=0, printer=True)

        p.cell(35, 3); p.click(double=True)
        p.expect(shown(), 'drive 8 open')
        at = row(b'NOTE')
        drag(p, 3, g['wy']+at, 35, 15)
        before = shown(at, {at})
        ask = b'[2][Print NOTE?][Print|Cancel]'
        p.expect(scene.scene.draw(before, ask, 1, 1)[0], 'print asked')
        p.key(13)
        assert bytes(p.io.printers[4]) == note, len(p.io.printers[4])
        p.expect(before, 'printed')
        assert not p.io.handles
        done('a row dropped on the Printer icon is printed as stored after Print is chosen', p, bytes=len(note))

        p.io.printers[4].clear()
        memo_at = row(b'MEMO')
        p.cell(3, g['wy']+memo_at); p.click()
        p.cell(3, g['wy']+at); p.ram[0xd3] = 1; p.click(); p.ram[0xd3] = 0
        drag(p, 3, g['wy']+memo_at, 35, 15)
        before = shown(at, {at, memo_at})
        p.expect(scene.scene.draw(before, b'[2][Print 2 items?][Print|Cancel]', 1, 1)[0], 'print two asked')
        p.key(9); p.key(13)                                     # Cancel: nothing printed
        assert not p.io.printers[4]
        drag(p, 3, g['wy']+memo_at, 35, 15)
        p.key(13)
        first, second = sorted([(memo_at, memo), (at, note)])
        assert bytes(p.io.printers[4]) == first[1]+second[1]
        done('several rows print in listing order after one question; Cancel prints nothing', p)

        # A Paint picture (the UPNT header): bit-image bands, as Print Screen.
        from ci_native_gemdesk_prtscr import band_dump, screen_dump, decode, pixels
        p.io.printers[4].clear()
        pic_at = row(b'PIC')
        p.cell(3, g['wy']+pic_at); p.click()
        drag(p, 3, g['wy']+pic_at, 35, 15)
        before = shown(pic_at, {pic_at})
        p.expect(scene.scene.draw(before, b'[2][Print PIC?][Print|Cancel]', 1, 1)[0], 'picture asked')
        p.key(13)
        printed = bytes(p.io.printers[4])
        assert printed == screen_dump(PICTURE[:8000]), (len(printed), printed[:8])
        assert decode(printed) == pixels(PICTURE[:8000])
        p.expect(before, 'picture printed')
        assert not p.io.handles
        done('a Paint picture dropped on the Printer icon prints in bit-image bands whose dots are exactly its '
             'bitmap pixels, then CHR$(15)', p, bytes=len(printed), dots=len(pixels(PICTURE[:8000])))

        p.io.printers[4].clear()
        short_at = row(b'SHORT')
        p.cell(3, g['wy']+short_at); p.click()
        drag(p, 3, g['wy']+short_at, 35, 15)
        before = shown(short_at, {short_at})
        p.key(13)
        stopped = b'[1][Printing stopped.|The printer may hold|part of a file.][OK]'
        p.expect(scene.scene.draw(before, stopped, 1, 1)[0], 'short picture')
        want = b''.join(band_dump(PICTURE[:8000], y0) for y0 in range(0, 42, 7))+b'\x0f'
        assert bytes(p.io.printers[4]) == want, len(p.io.printers[4])   # rows 0..5 read: six bands
        p.key(13); p.expect(before, 'short closed')
        assert not p.io.handles
        done('a picture that ends early prints the bands its rows cover, returns the printer to text mode and '
             'says printing stopped', p)

        del p.io.printers[4]                                    # switched off
        drag(p, 3, g['wy']+memo_at, 35, 15)                     # (pressed alone: it alone is selected)
        before = shown(memo_at, {memo_at})
        p.key(13)
        gone = b'[1][No printer answers|on device 4.][OK]'
        p.expect(scene.scene.draw(before, gone, 1, 1)[0], 'printer gone')
        p.key(13); p.expect(before, 'alert closed')
        assert not p.io.handles
        done('a printer that no longer answers is reported and every file is closed', p)

        # USB text: ASCII, so letters are swapped for PETSCII and line ends become CR.
        tree = {b'/': [b'\x10Usb0'], b'/Usb0': [b'\x20readme.txt'], b'/shell': [], b'/browser': []}
        text = b'Hello World\r\nline two\nTab\there\r'
        u = with_printer(lambda: Gem({**GDCPY, (8, b'AESVC.PRG', b'P'): AESVC},
                                     usb=dict(dirs=tree, files={b'/Usb0/readme.txt': text})))
        u.cell(35, 11); u.click(double=True)
        u.cell(3, 3); u.click(double=True)
        drag(u, 3, 3, 35, 15)
        u.key(13)
        assert bytes(u.io.printers[4]) == petscii(text) == b'\xc8ELLO \xd7ORLD\rLINE TWO\r\xd4AB HERE\r', bytes(u.io.printers[4])
        done('a USB text file prints with ASCII letters as PETSCII and CR, LF, CR LF as CR', u)
        report['passed'] = True
    finally:
        args.report.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
