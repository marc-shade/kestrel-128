#!/usr/bin/env python3
"""The persistent AES in a real emulated C128 (VICE x128): cold boot, load
AESVC.PRG into bank 1, then drive the alert, menu and window demos from the
keyboard and compare the complete VIC surface with the CPU-test oracles."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time

import vice_harness as ci
import native_aes_scene as scene
from native_capture_transport import PausedViceMonitor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
AE_BASE = int(re.search(r'^AE_BASE = \$([0-9a-f]{4})', (Path(__file__).resolve().parents[1]/'src/native/aes-api.inc').read_text(), re.M).group(1), 16)
AE_DATA = 0x5000
BLANK = bytes(8192)+b'\x16'*1024
ALERT = b'[3][Delete NOTES.TXT?|This cannot be undone.][Delete|Cancel]'
MENU = b'Desk:About AES...;File:New^N|Open...^O|-|Quit^Q;Options:Grid|Snap'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix='kestrel-aes-vice-'))
    spec = importlib.util.spec_from_file_location('aes_build', ROOT/'examples/native-aes/build.py')
    build = importlib.util.module_from_spec(spec); spec.loader.exec_module(build)
    images = build.build(work)
    ps = {n: int(v, 16) for n, v in re.findall(r'^([\w.]+)\s*=\s*\$([\da-fA-F]+)',
                                                (work/'parent.sym').read_text(), re.M)}
    component = (work/'AESVC.PRG').read_bytes()
    report = dict(passed=False, physical_hardware_io=False, work=str(work), images=images, checks=[])
    disk = work/'aes.d64'
    shutil.copy2(ROOT/'target/native/kestrel.d64', disk)
    subprocess.run(['c1541', '-attach', str(disk), '-delete', 'calc',
                    '-write', str(work/'AESDEMO.PRG'), 'calc',
                    '-write', str(work/'AESVC.PRG'), 'aesvc.prg'], check=True, capture_output=True)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
    xv = ci.cbm.Xvfb(); log = (work/'vice.log').open('w'); mon = None
    command = ['x128', '-default', '-8', str(disk), '-drive8true', '-drive8type', '1541',
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

        def wait(predicate, label, seconds=240):
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

        def surface(): return read(0xc000, 0x2400)

        def expect(want, label):
            got = surface()
            (work/(label+'.surface')).write_bytes(got)   # kept for inspection/rendering
            if got != want:
                (work/(label+'-actual.bin')).write_bytes(got); (work/(label+'-expected.bin')).write_bytes(want)
                raise AssertionError((label, [(i, a, b) for i, (a, b) in enumerate(zip(got, want)) if a != b][:12]))

        def value(name, n=1): return read(ps[name], n)

        wait(lambda: read(0x1c13, 6) == b'KES128' and ready(), 'native boot')
        key(ord('C'))
        wait(ready, 'demo ready')
        status = value('demo_status', 13)
        assert value('demo_error') == b'\0' and value('demo_loaded') == b'\1', (value('demo_error'), status.hex())
        assert status[0:3] == bytes([1, 7, 127]) and int.from_bytes(status[4:6], 'little') == 1
        loaded = bytearray(component[2:]); loaded[22:24] = ps['ae_callback'].to_bytes(2, 'little')
        resident = read(AE_BASE, 64, 'ram01')
        assert resident[:22] == bytes(loaded[:22]) and resident[22:24] == bytes(loaded[22:24])
        whole = read(AE_BASE, len(loaded), 'ram01')
        # The image's own RAM variables have run since loading; the code is fixed.
        report['image_matching_bytes'] = sum(a == b for a, b in zip(whole, loaded))
        check(f'cold boot; AESDEMO loads AESVC.PRG into bank-1 ${AE_BASE:04x} and attaches (version 1.7)',
              status=status.hex())

        key(ord('A')); want, geo = scene.draw(BLANK, ALERT, 2, 2); expect(want, 'alert-open')
        key(9); want, _ = scene.draw(BLANK, ALERT, 2, 1); expect(want, 'alert-tab')
        key(13)
        assert value('demo_choice') == b'\1' and value('demo_error') == b'\0'
        assert read(0xc000, 0x2400) == BLANK, 'exact restoration in the emulator'
        check('alert: exact frames on the VIC surface, Tab, Return, exact restore')

        key(ord('M'))
        flags = {(1, 1): 2}
        want, _ = scene.menu_draw(BLANK, MENU, flags=flags); expect(want, 'menu-bar')
        key(0x85); want, _ = scene.menu_draw(BLANK, MENU, open_title=0, hover=0, flags=flags); expect(want, 'menu-desk')
        key(0x1d); key(0x11); want, _ = scene.menu_draw(BLANK, MENU, open_title=1, hover=3, flags=flags)
        expect(want, 'menu-file-quit')
        key(13)
        assert value('demo_menu_title') == b'\1' and value('demo_menu_item') == b'\3'
        want, _ = scene.menu_draw(BLANK, MENU, flags=flags); expect(want, 'menu-closed')
        key(27)
        assert value('demo_error') == b'\0' and value('demo_waiting') == b'\0'
        check('menu bar: F1, cursor keys past a disabled item, Return queues MN_SELECTED')

        K = scene.WK
        wins = {
            1: dict(id=1, kind=K['NAME'] | K['CLOSER'] | K['FULLER'] | K['MOVER'], x=1, y=2, w=20, h=10, title=b'Alpha'),
            2: dict(id=2, kind=K['NAME'] | K['CLOSER'] | K['INFO'] | K['SIZER'] | K['UP'] | K['DN'] | K['VSLIDE'],
                    x=10, y=6, w=18, h=12, title=b'Beta', vpos=64, vsize=128),
            3: dict(id=3, kind=K['NAME'] | K['SIZER'] | K['LF'] | K['RT'] | K['HSLIDE'],
                    x=5, y=14, w=24, h=8, title=b'Gamma', hpos=200, hsize=64),
        }
        fills = {1: (0, 0x15), 2: (1, 0xb0), 3: (0, 0x3e)}
        order = [1, 2, 3]
        base = read(0xc000, 0x2400)
        base_desktop = scene.windows_draw([], fills)
        def windows(label):
            want = bytearray(scene.windows_draw([wins[h] for h in order], fills))
            # Row 0 keeps whatever the menu demo left there (windows never touch it).
            want[0:320] = base[0:320]; want[8192:8232] = base[8192:8232]
            expect(bytes(want), label)
        key(ord('W')); windows('windows-open')
        key(ord('1')); order[:] = [2, 3, 1]; windows('windows-top-1')
        key(ord('L')); wins[1].update(x=0, y=1); windows('windows-left')
        key(ord('M')); wins[1].update(x=1, y=2); windows('windows-move')
        key(ord('C')); order.remove(1); windows('windows-close')
        key(27)
        assert value('demo_error') == b'\0'
        check('windows: open three, top, move, close — frames, fills and markers match the painter')

        key(ord('U'))
        wait(lambda: read(0x3d20) == b'\0', 'demo exit')
        records = [read(0x3c00+i*8, 8) for i in range(32)]
        assert not any(r[0] == 30 for r in records), 'unload freed the image and the data segment'
        assert read(0x3d0e, 3) == bytes([175, 251, 32])
        check('U unloads: every owner-30 page returns (175/251/32 free)')
        report['passed'] = True
    finally:
        args.report.write_text(json.dumps(report, indent=2)+'\n')
        if mon: mon.quit_emulator()
        else: emu.terminate()
        emu.wait(timeout=15); xv.stop(); log.close()


if __name__ == '__main__':
    main()
