#!/usr/bin/env python3
"""GEMDESK Show Info's Read-only in a real emulated C128 (VICE x128, two 1581s
with true drive emulation): boot gem.d81 in drive 8 with a D81 holding two
files in drive 9, open drive 9, select a file from the keyboard, tick
Read-only in Show Info and choose OK; Show Info then reads the file back as
locked, and after the emulator exits the D81's directory entry has the lock
bit and c1541 lists the file as locked (docs/GEM-DESKTOP.md)."""
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
    work = Path(tempfile.mkdtemp(prefix='kestrel-gemdesk-lock-'))
    disk8, disk9 = work/'gem.d81', work/'data9.d81'
    shutil.copy2(ROOT/'target/native-desktop/gem.d81', disk8)
    subprocess.run(['c1541', '-format', 'data nine,09', 'd81', str(disk9)], check=True, capture_output=True)
    (work/'notes.seq').write_bytes(bytes(range(256))*3)
    (work/'game.prg').write_bytes(b'\x01\x08'+bytes(400))
    subprocess.run(['c1541', '-attach', str(disk9), '-write', str(work/'notes.seq'), 'notes,s',
                    '-write', str(work/'game.prg'), 'game'], check=True, capture_output=True)
    entries9 = d81_entries(disk9.read_bytes())
    assert len(entries9) == 2, entries9
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
        listed = scene.ordered(entries9, 0)
        key(ord('9'))
        expect(scene.picture([w9], {1: listed}, selected_icon=1), 'drive-9')
        at = [e['name'] for e in listed].index(entries9[0]['name'])
        entry = listed[at]
        for _ in range(at+1):
            key(0x11)
        w9['selected'] = at
        before = scene.picture([w9], {1: listed}, selected_icon=1)
        expect(before, 'selected')
        key(9)                                                         # Ctrl-I: Show Info
        expect(scene.info_dialog(before, entry), 'info')
        key(9)                                                         # Tab to Read-only
        key(32)
        expect(scene.info_dialog(before, entry, locked=True, focus=4), 'ticked')
        check('Show Info from the keyboard: Tab to Read-only, Space ticks it')
        key(13, 600)                                                   # OK: the lock on the drive
        w9['selected'] = None
        expect(scene.picture([w9], {1: listed}, selected_icon=1), 'listed-again', 600)
        for _ in range(at+1):
            key(0x11)
        w9['selected'] = at
        key(9)
        expect(scene.info_dialog(before, entry, locked=True), 'read-back')
        check('after OK the drive is listed again and Show Info reads the file back as read-only')
        key(27)
        expect(before, 'closed')
    finally:
        if mon: mon.quit_emulator()
        else: emu.terminate()
        emu.wait(timeout=60); xv.stop(); log.close()
    image = disk9.read_bytes()
    directory = image[((40-1)*40+3)*256:((40-1)*40+4)*256]
    kinds = {bytes(directory[i+5:i+21]).rstrip(b'\xa0'): directory[i+2] for i in range(0, 256, 32) if directory[i+2]}
    assert kinds == {entries9[0]['name']: 0xc1, entries9[1]['name']: 0x82}, kinds
    listing = subprocess.run(['c1541', '-attach', str(disk9), '-list'], check=True, capture_output=True,
                             text=True, errors='replace').stdout
    report['listing'] = listing
    rows = [line for line in listing.splitlines() if '"' in line and not line.startswith('0 "')]
    assert len(rows) == 2 and rows[0].rstrip().endswith('seq<') and rows[1].rstrip().endswith('prg'), rows
    check('after the emulator exits, the D81 entry reads $C1 (SEQ, locked; the other file unchanged) and c1541 '
          'lists it as locked', rows=rows)
    report['passed'] = True
    args.report.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
