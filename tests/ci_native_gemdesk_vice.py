#!/usr/bin/env python3
"""GEMDESK in a real emulated C128 (VICE x128, 1581 true drive emulation):
boot gem.d81, compare the desktop with the CPU-test oracle, open drive 8 from
the keyboard, launch Calculator, leave it, and check the AES session brings
the window and its selection back, then open a SEQ file in the Editor as a
document and return to the desktop, open a USHT workbook (a SEQ file, as
Sheet saves it) in Sheet and return, then open a UPNT picture (a SEQ file, as
Paint saves it) in Paint."""
import argparse
import binascii
import json
import os
import re
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time

import vice_harness as ci
import native_gemdesk_scene as scene
from launcher_scene import pointer_shape
from native_capture_transport import PausedViceMonitor

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT)]
from native_editor_scene import surface as editor_surface  # noqa: E402
from paint_scene import surface as paint_surface, MESSAGES as PAINT_MESSAGES  # noqa: E402
from native_paint_format import encode as paint_encode  # noqa: E402
from hwlib import lst_symbol  # noqa: E402
NOTE = b'GEMDESK opened this SEQ file.\rIt is an Editor document.\r'
PICTURE = (bytes((i*7+i//320) & 255 for i in range(8000))+bytes(192)
           + b'\x61'*1000+b'\x10'*24)     # UPNT keeps 1,000 attributes; Paint's page pads with $10


def d81_entries(image):
    """Live directory records of a D81 image, as N_DIRPAGE normalizes them."""
    def sector(t, s):
        at = ((t-1)*40+s)*256
        return image[at:at+256]
    out, t, s, seen = [], 40, 3, set()
    while t and (t, s) not in seen:
        seen.add((t, s))
        data = sector(t, s)
        for i in range(8):
            e = data[i*32:i*32+32]
            kind = e[2] & 7
            if e[2] and kind:
                out.append(dict(name=bytes(e[5:21]).rstrip(b'\xa0'), type=kind,
                                blocks=e[30] | e[31] << 8))
        t, s = data[0], data[1]
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix='kestrel-gemdesk-vice-'))
    disk = work/'gem.d81'
    shutil.copy2(ROOT/'target/native-desktop/gem.d81', disk)
    (work/'note.seq').write_bytes(NOTE)       # a test-local document on the copy
    subprocess.run(['c1541', '-attach', str(disk), '-write', str(work/'note.seq'), 'note,s'],
                   check=True, capture_output=True)
    (work/'picture.seq').write_bytes(paint_encode(PICTURE))
    subprocess.run(['c1541', '-attach', str(disk), '-write', str(work/'picture.seq'), 'picture,s'],
                   check=True, capture_output=True)
    records = bytearray(8192)                 # a Sheet workbook: A1 7, B1 =a1*6 (docs/NATIVE-SHEET.md)
    records[0:1], records[32:37] = b'7', b'=a1*6'
    (work/'ledger.seq').write_bytes(b'USHT\1\10\40\40\0\40'+binascii.crc_hqx(records, 0xffff).to_bytes(2, 'little')
                                    + bytes(4)+records)
    subprocess.run(['c1541', '-attach', str(disk), '-write', str(work/'ledger.seq'), 'ledger,s'],
                   check=True, capture_output=True)
    disk9 = work/'data9.d81'                  # device 9: a 1581 with a D81, to be detected
    subprocess.run(['c1541', '-format', 'data nine,09', 'd81', str(disk9)], check=True, capture_output=True)
    for name, data in (('alpha,s', b'A'*300), ('bravo,p', b'\x01\x08'+bytes(600))):
        (work/'nine.bin').write_bytes(data)
        subprocess.run(['c1541', '-attach', str(disk9), '-write', str(work/'nine.bin'), name],
                       check=True, capture_output=True)
    entries9 = d81_entries(disk9.read_bytes())
    entries = d81_entries(disk.read_bytes())
    report = dict(passed=False, physical_hardware_io=False, work=str(work), checks=[],
                  entries=[e['name'].decode('latin-1') for e in entries])
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
    xv = ci.cbm.Xvfb(); log = (work/'vice.log').open('w'); mon = None
    command = ['x128', '-default', '-8', str(disk), '-drive8true', '-drive8type', '1581',
               '-9', str(disk9), '-drive9true', '-drive9type', '1581',
               '-sounddev', 'dummy', '-jamaction', '0', '-warp',
               '-binarymonitor', '-binarymonitoraddress', f'ip4://127.0.0.1:{port}']
    report['command'] = command
    emu = subprocess.Popen(command, env=dict(os.environ, DISPLAY=xv.display,
                           __EGL_VENDOR_LIBRARY_FILENAMES=ci.cbm.MESA_EGL),
                           stdout=log, stderr=subprocess.STDOUT)

    def check(name, **extra):
        report['checks'].append(dict(name=name, **extra))
        args.report.write_text(json.dumps(report, indent=2)+'\n')
        print('PASS:', name, flush=True)

    try:
        deadline = time.monotonic()+30
        while mon is None:
            assert emu.poll() is None
            try: mon = ci.Monitor(port=port)
            except OSError:
                assert time.monotonic() < deadline
                time.sleep(.1)
        banks = mon.banks(); mon.resume(); paused = PausedViceMonitor(mon)

        def read(at, n=1, bank='ram00'):
            result = bytes(paused.read_mem(at, at+n-1, bank=banks[bank])); paused.resume(); return result

        def wait(predicate, label, seconds=300):
            deadline = time.monotonic()+seconds
            while time.monotonic() < deadline:
                if predicate(): return
                assert emu.poll() is None
                time.sleep(.05)
            raise AssertionError(label)

        def ready(): return read(0x3d12) == b'\1' and read(0xd0) == b'\0'

        def key(value):
            wait(ready, 'input ready')
            before = int.from_bytes(read(0x3d13, 2), 'little')
            with paused.paused('key'):
                paused.write_mem(0x3d12, b'\0'); paused.write_mem(0x34a, bytes([value])); paused.write_mem(0xd0, b'\1')
            wait(lambda: int.from_bytes(read(0x3d13, 2), 'little') == before+1 and ready(), f'key {value:#x}')

        def expect(want, label, seconds=120):
            want = bytearray(want)
            want[8000:8128] = pointer_shape(); want[9208:9210] = b'\x7d\x7e'
            want = bytes(want)
            deadline = time.monotonic()+seconds
            while True:                       # redraws finish after the key is consumed
                wait(ready, label)
                got = read(0xc000, 0x2400)
                if got == want: break
                if time.monotonic() > deadline:
                    (work/(label+'-actual.bin')).write_bytes(got); (work/(label+'-expected.bin')).write_bytes(want)
                    raise AssertionError((label, [(i, a, b) for i, (a, b) in enumerate(zip(got, want)) if a != b][:12]))
                time.sleep(.2)
            (work/(label+'.surface')).write_bytes(got)

        wait(lambda: read(0x1c13, 6) == b'KES128' and ready(), 'native boot')
        expect(scene.desktop(), 'desktop')
        check('cold boot of gem.d81: GEMDESK loads AESVC.PRG; the desktop matches the CPU oracle exactly')

        w9 = dict(id=1, x=1, y=2, w=28, h=16, title=b'Drive 9', top=0)
        key(ord('9'))
        expect(scene.picture([w9], {1: scene.ordered(entries9, 0)}, selected_icon=1), 'drive-9')
        detected = read(lst_symbol('native-desktop/gemdesk', 'gm_dev_format'))[0]
        assert detected == 2, ('the 1581 ROM answered UI; D81 expected', detected)
        key(23)                                   # Ctrl-W: File:Close
        expect(scene.desktop(selected=1), 'drive-9-closed')
        check('drive 9, a 1581 with a D81, is detected from its DOS identity (UI) and listed as a D81',
              entries=len(entries9))

        ordered = scene.ordered(entries, 0)
        window = dict(id=1, x=1, y=2, w=28, h=16, title=b'Drive 8', top=0)
        key(ord('8'))
        expect(scene.picture([window], {1: ordered}, selected_icon=0), 'drive-8')
        check('the 8 key opens the boot drive; the listing matches the D81 directory, sorted by name',
              entries=len(entries))

        at = [e['name'] for e in ordered].index(b'CALC')
        for _ in range(at+1):
            key(0x11)
        window['selected'] = at
        g = scene.scene.geometry(dict(kind=scene.KIND, x=1, y=2, w=28, h=16))
        window['top'] = max(0, at-g['wh']+1)
        expect(scene.picture([window], {1: ordered}, selected_icon=0), 'calc-selected')
        key(13)
        wait(lambda: read(0x3d20) == b'\x20' and read(0x3d40, 4) == b'CALC' and ready(), 'Calculator running')
        check('Return launches the selected CALC through the dispatcher')

        key(27)
        expect(scene.picture([window], {1: ordered}), 'back')
        check('leaving Calculator returns to GEMDESK, which reopens the window with its selection')

        note = [e['name'] for e in ordered].index(b'NOTE')
        for _ in range(abs(note-at)):
            key(0x11 if note > at else 0x91)
        window['selected'] = note
        window['top'] = min(window['top'], note)             # the selection scrolls into view
        window['top'] = max(window['top'], note-g['wh']+1)
        expect(scene.picture([window], {1: ordered}), 'note-selected')
        key(13)
        editor = (ROOT/'target/native-desktop/editor.prg').read_bytes()[2:34]
        wait(lambda: read(0x3d60, 32) == editor and ready(), 'Editor running', 120)
        assert read(0x3d9a) == b'\0', 'the Editor claimed the document request'
        want = editor_surface(NOTE, 0, name='NOTE', device=8, dirty=False, field='NOTE', fmt=2,
                              view=0, horizontal=0, selection=None)
        deadline = time.monotonic()+60
        while (got := read(0xc000, 0x2400)) != want:
            if time.monotonic() > deadline:
                (work/'editor-actual.bin').write_bytes(got); (work/'editor-expected.bin').write_bytes(want)
                raise AssertionError(('editor', [(i, a, b) for i, (a, b) in enumerate(zip(got, want)) if a != b][:12]))
            time.sleep(.2)
        (work/'editor.surface').write_bytes(got)
        check('Return on a SEQ file opens it in the Editor as a document: the surface matches the Editor oracle')

        key(27)
        expect(scene.picture([window], {1: ordered}), 'back-from-editor')
        check('leaving the Editor returns to GEMDESK with the document still selected')

        ledger = [e['name'] for e in ordered].index(b'LEDGER')
        for _ in range(abs(ledger-note)):
            key(0x11 if ledger > note else 0x91)
        window['selected'] = ledger
        window['top'] = min(window['top'], ledger)
        window['top'] = max(window['top'], ledger-g['wh']+1)
        expect(scene.picture([window], {1: ordered}), 'ledger-selected')
        key(13)
        sheet = (ROOT/'target/native-desktop/sheet.prg').read_bytes()[2:34]
        wait(lambda: read(0x3d60, 32) == sheet and ready(), 'Sheet running', 120)
        assert read(0x3d9a) == b'\0', 'Sheet claimed the document request'
        labels = {name: int(at, 16) for at, name in
                  re.findall(r'^al ([0-9A-F]+) \.(\S+)$', (ROOT/'target/native-desktop/sheet.lbl').read_text(), re.M)}
        values = read(labels['_sh_values'], 8)
        cells = [int.from_bytes(values[i:i+4], 'little', signed=True) for i in (0, 4)]
        assert cells == [7, 42] and read(labels['_wb_error']) == b'\0', cells
        assert read(labels['_wb_path'], 7) == b'LEDGER\0'
        check('Return on a USHT workbook (SEQ) opens it in Sheet: A1 7 and B1 =a1*6 read 7 and 42', cells=cells)
        key(27)
        expect(scene.picture([window], {1: ordered}), 'back-from-sheet')
        check('leaving Sheet returns to GEMDESK with the workbook still selected')
        note = ledger

        pic = [e['name'] for e in ordered].index(b'PICTURE')
        for _ in range(abs(pic-note)):
            key(0x11 if pic > note else 0x91)
        window['selected'] = pic
        window['top'] = min(window['top'], pic)
        window['top'] = max(window['top'], pic-g['wh']+1)
        expect(scene.picture([window], {1: ordered}), 'picture-selected')
        key(13)
        paint = (ROOT/'target/native-desktop/paint.prg').read_bytes()[2:34]
        wait(lambda: read(0x3d60, 32) == paint and ready(), 'Paint running', 120)
        assert read(0x3d9a) == b'\0', 'Paint claimed the document request'

        def value(name, n=1): return read(lst_symbol('native-desktop/paint', name), n)
        wait(lambda: value('pa_status')[0] == 2 and ready(), 'Paint opened the picture', 120)
        tag = value('pd_handles')[0]
        allocation = read(0x3c00+(tag-1)*8, 8)
        assert allocation[:2] == bytes([32, 1]) and allocation[3] == 36, allocation
        document = read(allocation[2]*256, 9216, 'ram01')
        if document != PICTURE:
            (work/'paint-document.bin').write_bytes(document)
            raise AssertionError(('the picture in Paint\'s document allocation',
                                  [(i, a, b) for i, (a, b) in enumerate(zip(document, PICTURE)) if a != b][:12]))
        name = value('pf_name', value('pf_length')[0])
        assert name == b'PICTURE' and value('pd_dirty')[0] == 0, name
        want = paint_surface(PICTURE, message=PAINT_MESSAGES[2], view_x=value('pa_view_x')[0], view_y=value('pa_view_y')[0],
                             focus=value('ui_selected')[0], x=int.from_bytes(value('pd_x', 2), 'little'), y=value('pd_y')[0],
                             pen=value('pd_pen')[0], color=value('pd_color')[0], dirty=False, mode=value('pa_mode')[0],
                             action=value('pa_action')[0], name=name, caret=value('pa_field_caret')[0],
                             field_view=value('pa_field_view')[0], device=value('pf_device')[0], fmt=value('pf_format')[0])
        got = read(0xc000, 0x2400)
        if got != want:
            (work/'paint-actual.bin').write_bytes(got); (work/'paint-expected.bin').write_bytes(want)
            raise AssertionError(('paint', [(i, a, b) for i, (a, b) in enumerate(zip(got, want)) if a != b][:12]))
        (work/'paint.surface').write_bytes(got)
        check('Return on a UPNT picture (SEQ) opens it in Paint: the document bytes and the surface match')
        report['passed'] = True
    finally:
        args.report.write_text(json.dumps(report, indent=2)+'\n')
        if mon: mon.quit_emulator()
        else: emu.terminate()
        emu.wait(timeout=15); xv.stop(); log.close()


if __name__ == '__main__':
    main()
