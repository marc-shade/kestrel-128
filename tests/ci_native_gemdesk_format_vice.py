#!/usr/bin/env python3
"""GEMDESK File:Format in a real emulated C128 (VICE x128, two 1581s with true
drive emulation): boot gem.d81 in drive 8 with a D81 holding a file in drive 9,
open drive 9, choose File:Format from the keyboard (drive 9, a name and an ID,
then Format in the confirmation), see the "Formatting disk" window while the
drive works and the drive's own free-block count afterwards, and after the
emulator exits read drive 9 back with c1541: the new name and ID, no files
(docs/GEM-DESKTOP.md)."""
import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time

import vice_harness as ci
import native_gemdesk_scene as scene
from ci_native_gemdesk_vice import d81_entries
from launcher_scene import pointer_shape
from native_capture_transport import PausedViceMonitor

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix='kestrel-gemdesk-format-'))
    disk8, disk9 = work/'gem.d81', work/'data9.d81'
    shutil.copy2(ROOT/'target/native-desktop/gem.d81', disk8)
    subprocess.run(['c1541', '-format', 'old nine,o9', 'd81', str(disk9)], check=True, capture_output=True)
    (work/'old.seq').write_bytes(bytes(range(256))*4)
    subprocess.run(['c1541', '-attach', str(disk9), '-write', str(work/'old.seq'), 'old,s'],
                   check=True, capture_output=True)
    entries9 = d81_entries(disk9.read_bytes())
    assert len(entries9) == 1, entries9
    report = dict(passed=False, physical_hardware_io=False, work=str(work), checks=[])
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
    xv = ci.cbm.Xvfb(); log = (work/'vice.log').open('w'); mon = None
    env = dict(os.environ, DISPLAY=xv.display, __EGL_VENDOR_LIBRARY_FILENAMES=ci.cbm.MESA_EGL)
    command = ['x128', '-default', '-8', str(disk8), '-drive8true', '-drive8type', '1581',
               '-9', str(disk9), '-drive9true', '-drive9type', '1581',
               '-sounddev', 'dummy', '-jamaction', '0', '-warp',
               '-binarymonitor', '-binarymonitoraddress', f'ip4://127.0.0.1:{port}']
    report['command'] = command
    emu = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT)

    def check(label, **extra):
        report['checks'].append(dict(name=label, **extra))
        args.report.write_text(json.dumps(report, indent=2)+'\n')
        print('PASS:', label, flush=True)

    try:
        deadline = time.monotonic()+30
        while mon is None:
            assert emu.poll() is None
            try: mon = ci.Monitor(port=port)
            except OSError:
                assert time.monotonic() < deadline
                time.sleep(.1)
        banks = mon.banks(); mon.resume(); paused = PausedViceMonitor(mon)

        def read(at, n=1):
            result = bytes(paused.read_mem(at, at+n-1, bank=banks['ram00'])); paused.resume(); return result

        def wait(predicate, label, seconds=300):
            deadline = time.monotonic()+seconds
            while time.monotonic() < deadline:
                if predicate(): return
                assert emu.poll() is None
                time.sleep(.05)
            raise AssertionError(label)

        def ready(): return read(0x3d12) == b'\1' and read(0xd0) == b'\0'

        def press(value):
            """Put one key in the KERNAL buffer once GEMDESK waits for input."""
            wait(ready, 'input ready')
            before = int.from_bytes(read(0x3d13, 2), 'little')
            with paused.paused('key'):
                paused.write_mem(0x3d12, b'\0'); paused.write_mem(0x34a, bytes([value])); paused.write_mem(0xd0, b'\1')
            return before

        def key(value, seconds=300):
            before = press(value)
            wait(lambda: int.from_bytes(read(0x3d13, 2), 'little') == before+1 and ready(), f'key {value:#x}', seconds)

        def shown(want):
            want = bytearray(want)
            want[8000:8128] = pointer_shape(); want[9208:9210] = b'\x7d\x7e'
            return bytes(want)

        def expect(want, label, seconds=120):
            want = shown(want)
            deadline = time.monotonic()+seconds
            while True:
                wait(ready, label, seconds)
                got = read(0xc000, 0x2400)
                if got == want: return
                if time.monotonic() > deadline:
                    (work/(label+'-actual.bin')).write_bytes(got); (work/(label+'-expected.bin')).write_bytes(want)
                    raise AssertionError((label, [(i, a, b) for i, (a, b) in enumerate(zip(got, want)) if a != b][:12]))
                time.sleep(.5)

        wait(lambda: read(0x1c13, 6) == b'KES128' and ready(), 'native boot', 600)
        expect(scene.desktop(), 'desktop')
        w9 = dict(id=1, x=1, y=2, w=28, h=16, title=b'Drive 9', top=0)
        key(ord('9'))
        before = scene.picture([w9], {1: scene.ordered(entries9, 0)}, selected_icon=1)
        expect(before, 'drive-9')
        for k in (0x85, 0x1d, 0x11, 0x11, 0x11, 13):                  # File:Format...
            key(k)
        expect(scene.format_dialog(before, 2), 'format-dialog')
        key(0x11); key(32); key(9)                                     # drive 9, then the name
        for c in b'BLANK':
            key(c)
        key(9)
        for c in b'B1':
            key(c)
        expect(scene.format_dialog(before, 7, drive8=False, name=b'BLANK', ident=b'B1'), 'name-and-id')
        key(13)
        ask = b'[3][Format drive 9?|Every file on it|will be erased.][Format|Cancel]'
        expect(scene.scene.draw(before, ask, 2, 2)[0], 'confirm')
        check('File:Format from the keyboard: drive 9, name BLANK, ID B1, and the confirmation (Cancel the default)')

        key(9)                                                         # Format
        started = time.monotonic()
        press(13)
        formatting = shown(scene.progress(before, b'Formatting disk', w9))
        wait(lambda: read(0xc000, 0x2400) == formatting, 'the Formatting disk window', 600)
        check('while the 1581 formats, a "Formatting disk" window is on the desktop')
        empty = scene.picture([w9], {1: []}, selected_icon=1)
        done = b'[1][Drive 9 is formatted:|3160 blocks free.][OK]'
        expect(scene.scene.draw(empty, done, 1, 1)[0], 'formatted', 1800)
        report['format_seconds_host'] = round(time.monotonic()-started, 1)
        check('afterwards drive 9 is listed again (empty) and the drive\'s own listing reports 3160 blocks free',
              seconds=report['format_seconds_host'])
        key(13)
        expect(empty, 'closed')
    finally:
        if mon: mon.quit_emulator()
        else: emu.terminate()
        emu.wait(timeout=60); xv.stop(); log.close()
    listing = subprocess.run(['c1541', '-attach', str(disk9), '-list'], check=True, capture_output=True,
                             text=True, errors='replace').stdout
    report['listing'] = listing
    lines = [line for line in listing.splitlines() if line.strip()]
    header = [line for line in lines if line.startswith('0 "')]     # (c1541 notes its libraries and the image first)
    assert len(header) == 1 and header[0].lower().startswith('0 "blank ') and header[0].lower().endswith(' b1 3d'), lines
    assert not d81_entries(disk9.read_bytes()), 'no files after the format'
    assert any(line.lower().startswith('3160 blocks free') for line in lines), lines
    check('after the emulator exits, c1541 reads drive 9 as BLANK,B1 with no files and 3160 blocks free',
          header=header[0])
    report['passed'] = True
    args.report.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
