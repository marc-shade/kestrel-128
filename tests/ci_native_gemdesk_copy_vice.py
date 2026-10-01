#!/usr/bin/env python3
"""GEMDESK file copy in a real emulated C128 (VICE x128, two 1581s with true
drive emulation, a 1351 mouse on control port 1 moved by host pointer events
through XTEST): boot gem.d81 in drive 8 with a D81 holding a 3,000-byte SEQ
file in drive 9, open drive 9, drag the file's row onto the Boot icon with the
mouse, choose Copy, open drive 8 to see it listed, and after the emulator
exits read both files back with c1541 and compare them (docs/GEM-DESKTOP.md)."""
import argparse
import json
import os
from pathlib import Path
import random
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
sys.path[:0] = [str(ROOT)]
from hwlib import lst_symbol  # noqa: E402

DATA = bytes(random.Random(1581).randrange(256) for _ in range(3000))   # six 512-byte chunks


def c1541_read(disk, name, out):
    subprocess.run(['c1541', '-attach', str(disk), '-read', name, str(out)], check=True, capture_output=True)
    return out.read_bytes()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix='kestrel-gemdesk-copy-'))
    disk8, disk9 = work/'gem.d81', work/'data9.d81'
    shutil.copy2(ROOT/'target/native-desktop/gem.d81', disk8)
    subprocess.run(['c1541', '-format', 'data nine,09', 'd81', str(disk9)], check=True, capture_output=True)
    (work/'notes.seq').write_bytes(DATA)
    subprocess.run(['c1541', '-attach', str(disk9), '-write', str(work/'notes.seq'), 'notes,s'],
                   check=True, capture_output=True)
    entries8, entries9 = d81_entries(disk8.read_bytes()), d81_entries(disk9.read_bytes())
    name = entries9[0]['name']
    assert [e['name'] for e in entries9] == [name] and entries9[0]['type'] == 1, entries9
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
        expect(scene.desktop(), 'desktop')
        w9 = dict(id=1, x=1, y=2, w=28, h=16, title=b'Drive 9', top=0)
        key(ord('9'))
        expect(scene.picture([w9], {1: scene.ordered(entries9, 0)}, selected_icon=1), 'drive-9')
        check('drive 9 opens with the SEQ file listed', entries=len(entries9))

        host('at 400 300')                               # over the emulator's window
        point_at(3, 3)                                   # the file's row
        host('down')
        time.sleep(1)                                    # past the double-click time: a drag
        point_at(35, 3)                                  # the Boot icon
        time.sleep(.5)
        host('up')
        w9['selected'] = 0
        before = scene.picture([w9], {1: scene.ordered(entries9, 0)}, selected_icon=1)
        ask = b'[2][Copy '+name+b'|to Drive 8?][Copy|Move|Cancel]'
        expect(scene.scene.draw(before, ask, 1, 1)[0], 'asked')
        check('the row dragged onto the Boot icon with the mouse asks Copy, Move or Cancel (Copy is the default)')

        started = time.monotonic()
        item_no = lst_symbol('native-desktop/gdcpy', 'item_no')      # GDCPY's row counter
        gm_batch = lst_symbol('native-desktop/gemdesk', 'gm_batch')    # set while its rows are copied
        key(13, 3600)                                    # Copy
        wait(lambda: read(item_no) == b'\1' and read(gm_batch) == b'\0' and ready(), 'copied', 3600)
        key(ord('8'))                                    # (a key during the copy would be read as not-Esc)
        w8 = dict(id=2, x=2, y=3, w=28, h=16, title=b'Drive 8', top=0)
        copied = dict(name=name, type=1, blocks=-(-len(DATA)//254))
        listed8 = scene.ordered(entries8+[copied], 0)
        expect(scene.picture([w9, w8], {1: scene.ordered(entries9, 0), 2: listed8}, selected_icon=0),
               'drive-8', 3600)
        report['copy_seconds_host'] = round(time.monotonic()-started, 1)
        check('after Copy, drive 8 lists the file with its type (SEQ) and block count',
              blocks=copied['blocks'], seconds=report['copy_seconds_host'])
    finally:
        try: pointer.stdin.close(); pointer.wait(5)
        except Exception: pointer.kill()
        if mon: mon.quit_emulator()
        else: emu.terminate()
        emu.wait(timeout=60); xv.stop(); log.close()
    target = c1541_read(disk8, 'notes,s', work/'copied.seq')
    source = c1541_read(disk9, 'notes,s', work/'source.seq')
    assert source == DATA, 'the source is unchanged'
    assert target == DATA, ('the copy differs', len(target), len(DATA))
    check('after the emulator exits, c1541 reads the copy on drive 8 byte-identical to the 3,000-byte source, '
          'which is unchanged', bytes=len(DATA))
    report['passed'] = True
    args.report.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
