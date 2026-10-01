#!/usr/bin/env python3
"""GEMDESK Print Screen in a real emulated C128 (VICE x128, 1581 true drive
emulation, VICE's printer on IEC device 4 with the raw driver writing every
byte it receives to a file): boot gem.d81, check the Printer icon, open drive
8, press HELP, and compare what the printer received with the dump decoded
from the emulated machine's own surface RAM (docs/GEM-DESKTOP.md)."""
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
from launcher_scene import pointer_shape
from native_capture_transport import PausedViceMonitor
from ci_native_gemdesk_vice import d81_entries
from ci_native_gemdesk_prtscr import screen_dump, decode, pixels

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix='kestrel-gemdesk-prtscr-'))
    disk = work/'gem.d81'
    shutil.copy2(ROOT/'target/native-desktop/gem.d81', disk)
    printed_file = work/'printer.bin'
    entries = d81_entries(disk.read_bytes())
    report = dict(passed=False, physical_hardware_io=False, work=str(work), checks=[])
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
    xv = ci.cbm.Xvfb(); log = (work/'vice.log').open('w'); mon = None
    command = ['x128', '-default', '-8', str(disk), '-drive8true', '-drive8type', '1581',
               '-devicebackend4', '1', '-busdevice4', '-pr4drv', 'raw', '-pr4output', 'text',
               '-pr4txtdev', '0', '-prtxtdev1', str(printed_file),
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

    bitmap = None
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

        def key(value, seconds=300):
            wait(ready, 'input ready')
            before = int.from_bytes(read(0x3d13, 2), 'little')
            with paused.paused('key'):
                paused.write_mem(0x3d12, b'\0'); paused.write_mem(0x34a, bytes([value])); paused.write_mem(0xd0, b'\1')
            wait(lambda: int.from_bytes(read(0x3d13, 2), 'little') == before+1 and ready(), f'key {value:#x}', seconds)

        def expect(want, label, seconds=120):
            want = bytearray(want)
            want[8000:8128] = pointer_shape(); want[9208:9210] = b'\x7d\x7e'
            want = bytes(want)
            deadline = time.monotonic()+seconds
            while True:
                wait(ready, label)
                got = read(0xc000, 0x2400)
                if got == want: return got
                if time.monotonic() > deadline:
                    (work/(label+'-actual.bin')).write_bytes(got); (work/(label+'-expected.bin')).write_bytes(want)
                    raise AssertionError((label, [(i, a, b) for i, (a, b) in enumerate(zip(got, want)) if a != b][:12]))
                time.sleep(.2)

        wait(lambda: read(0x1c13, 6) == b'KES128' and ready(), 'native boot', 600)
        expect(scene.desktop(printer=True), 'desktop')
        check('cold boot with a printer on device 4: the desktop shows the Printer icon')

        window = dict(id=1, x=1, y=2, w=28, h=16, title=b'Drive 8', top=0)
        shown = scene.picture([window], {1: scene.ordered(entries, 0)}, selected_icon=0, printer=True)
        key(ord('8'))
        expect(shown, 'drive-8')
        key(0x84, 600)                                  # HELP
        bitmap = expect(shown, 'after-help')[:8000]
        check('HELP runs Print Screen and leaves the desktop exactly as it was')
    finally:
        if mon: mon.quit_emulator()                     # a clean exit flushes the printer file
        else: emu.terminate()
        emu.wait(timeout=30); xv.stop(); log.close()
    printed = printed_file.read_bytes() if printed_file.exists() else b''
    report['printed_bytes'] = len(printed)
    assert printed == screen_dump(bitmap), (len(printed), printed[:8], printed[-8:])
    assert decode(printed) == pixels(bitmap)
    check('the printer received 29 bit-image bands whose dots are exactly the emulated surface\'s set '
          'pixels, then CHR$(15)', bytes=len(printed), dots=len(pixels(bitmap)))
    report['passed'] = True
    args.report.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
