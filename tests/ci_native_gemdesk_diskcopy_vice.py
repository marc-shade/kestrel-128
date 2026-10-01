#!/usr/bin/env python3
"""GEMDESK disk copy in a real emulated C128 (VICE x128, two 1581s with true
drive emulation, a 1351 mouse on control port 1 moved by host pointer events
through XTEST): boot gem.d81 in drive 8 with a blank D81 in drive 9, drag the
Boot icon onto the Drive 9 icon with the mouse, choose Copy, and after the
emulator exits compare the two disk images byte for byte (docs/GEM-DESKTOP.md)."""
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

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT)]
from hwlib import lst_symbol  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix='kestrel-gemdesk-diskcopy-'))
    disk8, disk9 = work/'gem.d81', work/'blank.d81'
    shutil.copy2(ROOT/'target/native-desktop/gem.d81', disk8)
    subprocess.run(['c1541', '-format', 'blank,b9', 'd81', str(disk9)], check=True, capture_output=True)
    source = disk8.read_bytes()
    assert disk9.read_bytes() != source
    report = dict(passed=False, physical_hardware_io=False, work=str(work), checks=[])
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
    xv = ci.cbm.Xvfb(); log = (work/'vice.log').open('w'); mon = None
    env = dict(os.environ, DISPLAY=xv.display, __EGL_VENDOR_LIBRARY_FILENAMES=ci.cbm.MESA_EGL)
    command = ['x128', '-default', '-8', str(disk8), '-drive8true', '-drive8type', '1581',
               '-9', str(disk9), '-drive9true', '-drive9type', '1581',
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
        expect(scene.desktop(), 'desktop')
        host('at 400 300')                               # over the emulator's window
        point_at(35, 3)
        check('the 1351 in control port 1 moves GEMDESK\'s pointer onto the Boot icon', pointer=where())

        host('down')
        time.sleep(1)
        point_at(35, 7)
        time.sleep(.5)
        host('up')
        ask = b'[3][Copy the disk in drive 8|onto drive 9? Everything|on drive 9 is replaced.][Copy|Cancel]'
        expect(scene.scene.draw(scene.desktop(selected=0), ask, 2, 2)[0], 'asked')
        check('Boot dragged onto Drive 9 with the mouse asks to copy the disk (Cancel is the default)')

        started = time.monotonic()
        key(9); key(13, 3600)                                   # Copy
        done_alert = b'[1][Disk copied and compared.][OK]'
        expect(scene.scene.draw(scene.desktop(selected=0), done_alert, 1, 1)[0], 'copied', 3600)
        report['copy_seconds_host'] = round(time.monotonic()-started, 1)
        check('Copy reads, writes and compares every sector and says so', seconds=report['copy_seconds_host'])
        key(13)
        expect(scene.desktop(selected=0), 'closed')
    finally:
        try: pointer.stdin.close(); pointer.wait(5)
        except Exception: pointer.kill()
        if mon: mon.quit_emulator()
        else: emu.terminate()
        emu.wait(timeout=60); xv.stop(); log.close()
    copied = disk9.read_bytes()
    assert len(copied) == len(source) == 819200, (len(copied), len(source))
    differing = [i//256 for i in range(0, len(source), 256) if copied[i:i+256] != source[i:i+256]]
    assert not differing, ('sectors differ', differing[:10], len(differing))
    check('after the emulator exits, the drive 9 D81 is byte-identical to the drive 8 D81 (3,200 sectors)')
    report['passed'] = True
    args.report.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
