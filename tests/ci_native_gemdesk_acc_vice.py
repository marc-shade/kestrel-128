#!/usr/bin/env python3
"""The Calculator desk accessory in a real emulated C128 (VICE x128, 1581 true
drive emulation, a 1351 mouse on control port 1 moved by host pointer events
through XTEST): boot gem.d81, which carries DESK1.ACC, check the accessory is
resident at bank-1 $4000, open it from the Desk menu, compute from the keyboard
and with the mouse, and close it with its close box; every surface is compared
with the CPU test's painter (docs/GEM-LAYER-DESIGN.md#desk-accessories)."""
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
from ci_native_gemdesk_acc import calculator, key_cell, MENU_ACC

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT)]
from hwlib import lst_symbol  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix='kestrel-gemdesk-acc-'))
    disk = work/'gem.d81'
    shutil.copy2(ROOT/'target/native-desktop/gem.d81', disk)
    image = (ROOT/'target/native-desktop/desk1.acc').read_bytes()
    report = dict(passed=False, physical_hardware_io=False, work=str(work), checks=[])
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
    xv = ci.cbm.Xvfb(); log = (work/'vice.log').open('w'); mon = None
    env = dict(os.environ, DISPLAY=xv.display, __EGL_VENDOR_LIBRARY_FILENAMES=ci.cbm.MESA_EGL)
    command = ['x128', '-default', '-8', str(disk), '-drive8true', '-drive8type', '1581',
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
        pm_x, pm_y = lst_symbol('native-desktop/gemdesk', 'pm_x'), lst_symbol('native-desktop/gemdesk', 'pm_y')

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
            while True:
                wait(ready, label, seconds)
                got = read(0xc000, 0x2400)
                if got == want: return
                if time.monotonic() > deadline:
                    (work/(label+'-actual.bin')).write_bytes(got); (work/(label+'-expected.bin')).write_bytes(want)
                    raise AssertionError((label, [(i, a, b) for i, (a, b) in enumerate(zip(got, want)) if a != b][:12]))
                time.sleep(.3)

        def where():
            return int.from_bytes(read(pm_x, 2), 'little'), read(pm_y)[0]

        def point_at(cx, cy):
            tx, ty = cx*8+4, cy*8+4
            for _ in range(60):
                x, y = where()
                if abs(x-tx) <= 1 and abs(y-ty) <= 1: return
                host(f'move {max(-40, min(40, (tx-x)*2))} {max(-40, min(40, (ty-y)*2))}')
                time.sleep(.15)
            raise AssertionError(('pointer', where(), (tx, ty)))

        def click(cx, cy):
            point_at(cx, cy)
            host('down'); time.sleep(.3); host('up'); time.sleep(1)

        wait(lambda: read(0x1c13, 6) == b'KES128' and ready(), 'native boot', 600)
        desk = scene.desktop()
        expect(desk, 'desktop')
        resident = read(0x4000, 48, 'ram01')     # header, identity and entries (the code patches itself)
        assert resident[:22] == image[2:24] and resident[24:48] == image[26:50], \
            ('DESK1.ACC resident at bank-1 $4000 (bytes 22..23: the loader\'s callback)', resident.hex(), image[2:50].hex())
        check('cold boot: GEMDESK loads DESK1.ACC into bank-1 $4000; the desktop matches the oracle')

        key(0x85)
        expect(scene.scene.menu_draw(desk, MENU_ACC, open_title=0, hover=0)[0], 'desk menu')
        key(0x11); key(0x11); key(13)
        expect(calculator(b'0', desk), 'opened')
        check('the Desk menu lists Calculator; choosing it opens the accessory\'s window')

        for k in b'12+3=':
            key(k)
        expect(calculator(b'15', desk), 'typed')
        check('keys typed while the window is on top reach the accessory: 12 + 3 = 15')

        host('at 400 300')
        click(*key_cell(ord('*')))
        click(*key_cell(ord('4')))
        click(*key_cell(ord('=')))
        expect(calculator(b'60', desk), 'clicked')
        check('1351 clicks on the keypad reach the accessory: * 4 = gives 60')

        click(22, 3)                                            # the close box
        expect(desk, 'closed')
        check('the close box closes the window and the desktop is restored exactly')
        report['passed'] = True
    finally:
        try: pointer.stdin.close(); pointer.wait(5)
        except Exception: pointer.kill()
        if mon: mon.quit_emulator()
        else: emu.terminate()
        emu.wait(timeout=60); xv.stop(); log.close()
        args.report.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
