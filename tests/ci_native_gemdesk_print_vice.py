#!/usr/bin/env python3
"""GEMDESK printing a Paint picture in a real emulated C128 (VICE x128, a 1581
with true drive emulation, VICE's printer on IEC device 4 with the raw driver
writing every byte to a file, a 1351 mouse on control port 1 moved by host
pointer events through XTEST): boot gem.d81 holding a UPNT picture, open drive
8, drag the picture's row onto the Printer icon with the mouse, choose Print,
and compare what the printer received with the bit-image dump of the
picture's bitmap (docs/GEM-DESKTOP.md)."""
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
from ci_native_gemdesk_prtscr import screen_dump, decode, pixels
from launcher_scene import pointer_shape
from native_capture_transport import PausedViceMonitor

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT)]
from hwlib import lst_symbol  # noqa: E402
from native_paint_format import encode as paint_encode  # noqa: E402

PICTURE = (bytes((i*13+i//320*3) & 255 for i in range(8000))+bytes(192)
           + b'\x61'*1000+b'\x10'*24)                  # a Paint surface: bitmap, pad, attributes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix='kestrel-gemdesk-print-'))
    disk8 = work/'gem.d81'
    shutil.copy2(ROOT/'target/native-desktop/gem.d81', disk8)
    (work/'pic.seq').write_bytes(paint_encode(PICTURE))
    subprocess.run(['c1541', '-attach', str(disk8), '-write', str(work/'pic.seq'), 'apic,s'],
                   check=True, capture_output=True)
    printed_file = work/'printer.bin'
    entries = d81_entries(disk8.read_bytes())
    report = dict(passed=False, physical_hardware_io=False, work=str(work), checks=[])
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
    xv = ci.cbm.Xvfb(); log = (work/'vice.log').open('w'); mon = None
    env = dict(os.environ, DISPLAY=xv.display, __EGL_VENDOR_LIBRARY_FILENAMES=ci.cbm.MESA_EGL)
    command = ['x128', '-default', '-8', str(disk8), '-drive8true', '-drive8type', '1581',
               '-devicebackend4', '1', '-busdevice4', '-pr4drv', 'raw', '-pr4output', 'text',
               '-pr4txtdev', '0', '-prtxtdev1', str(printed_file),
               '-controlport1device', '3', '-mouse',
               '-sounddev', 'dummy', '-jamaction', '0', '-warp',
               '-binarymonitor', '-binarymonitoraddress', f'ip4://127.0.0.1:{port}']
    report['command'] = command
    emu = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT)
    pointer = subprocess.Popen(['/usr/bin/python3', str(Path(__file__).with_name('x_pointer.py'))], env=env,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)

    def host(cmd):
        pointer.stdin.write(cmd+'\n'); pointer.stdin.flush()
        assert pointer.stdout.readline().strip() == 'ok', cmd

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
        pm_x, pm_y = lst_symbol('native-desktop/gemdesk', 'pm_x'), lst_symbol('native-desktop/gemdesk', 'pm_y')

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
                wait(ready, label, seconds)
                got = read(0xc000, 0x2400)
                if got == want: return
                if time.monotonic() > deadline:
                    (work/(label+'-actual.bin')).write_bytes(got); (work/(label+'-expected.bin')).write_bytes(want)
                    raise AssertionError((label, [(i, a, b) for i, (a, b) in enumerate(zip(got, want)) if a != b][:12]))
                time.sleep(.5)

        def where():
            return int.from_bytes(read(pm_x, 2), 'little'), read(pm_y)[0]

        def point_at(cx, cy):
            """Move the 1351 until the pointer is in the middle of cell (cx, cy)."""
            tx, ty = cx*8+4, cy*8+4
            for _ in range(60):
                x, y = where()
                if abs(x-tx) <= 1 and abs(y-ty) <= 1: return
                host(f'move {max(-40, min(40, (tx-x)*2))} {max(-40, min(40, (ty-y)*2))}')
                time.sleep(.15)
            raise AssertionError(('pointer', where(), (tx, ty)))

        wait(lambda: read(0x1c13, 6) == b'KES128' and ready(), 'native boot', 600)
        expect(scene.desktop(printer=True), 'desktop')
        window = dict(id=1, x=1, y=2, w=28, h=16, title=b'Drive 8', top=0)
        ordered = scene.ordered(entries, 0)
        key(ord('8'))
        expect(scene.picture([window], {1: ordered}, selected_icon=0, printer=True), 'drive-8')
        name = next(e['name'] for e in entries if e['name'].upper() == b'APIC')
        at = [e['name'] for e in ordered].index(name)
        assert at < 15, ('the row must be visible without scrolling', at)
        check('drive 8 opens with the picture listed', row=at)

        host('at 400 300')                               # over the emulator's window
        point_at(3, 3+at)                                # the picture's row
        host('down')
        time.sleep(1)                                    # past the double-click time: a drag
        point_at(35, 15)                                 # the Printer icon
        time.sleep(.5)
        host('up')
        window['selected'] = at
        before = scene.picture([window], {1: ordered}, selected_icon=0, printer=True)
        ask = b'[2][Print '+name+b'?][Print|Cancel]'
        expect(scene.scene.draw(before, ask, 1, 1)[0], 'asked')
        check('the picture\'s row dragged onto the Printer icon with the mouse asks Print or Cancel')

        ps_y = lst_symbol('native-desktop/gdprt', 'ps_y')       # GDPRT's band counter
        key(13, 3600)                                    # Print
        wait(lambda: read(ps_y)[0] >= 200 and ready(), 'printed', 3600)
        expect(before, 'after-print')
        check('the bands are sent and the desktop is left as it was')
    finally:
        try: pointer.stdin.close(); pointer.wait(5)
        except Exception: pointer.kill()
        if mon: mon.quit_emulator()                     # a clean exit flushes the printer file
        else: emu.terminate()
        emu.wait(timeout=60); xv.stop(); log.close()
    printed = printed_file.read_bytes() if printed_file.exists() else b''
    report['printed_bytes'] = len(printed)
    assert printed == screen_dump(PICTURE[:8000]), (len(printed), printed[:8], printed[-8:])
    assert decode(printed) == pixels(PICTURE[:8000])
    check('the printer received 29 bit-image bands whose dots are exactly the picture\'s bitmap pixels, '
          'then CHR$(15)', bytes=len(printed), dots=len(pixels(PICTURE[:8000])))
    report['passed'] = True
    args.report.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
