#!/usr/bin/env python3
"""Editor printing in a real emulated C128 (VICE x128, 1581 true drive
emulation, VICE's printer emulation on IEC device 4 writing a text file):
boot kestrel.d81, start the Editor from the blue launcher, type two lines,
press Ctrl-P, and read what the printer printed (docs/NATIVE-EDITOR-GUI.md)."""
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

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT)]
import vice_harness as ci  # noqa: E402
from native_capture_transport import PausedViceMonitor  # noqa: E402
from hwlib import lst_symbol  # noqa: E402

LINES = ['Hello, World!', 'second line: 42', 'END']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix='kestrel-editor-print-'))
    disk = work/'kestrel.d81'
    shutil.copy2(ROOT/'target/native-desktop/kestrel.d81', disk)
    printed = work/'printer.txt'
    report = dict(passed=False, physical_hardware_io=False, work=str(work), checks=[])
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
    xv = ci.cbm.Xvfb(); log = (work/'vice.log').open('w'); mon = None
    command = ['x128', '-default', '-8', str(disk), '-drive8true', '-drive8type', '1581',
               '-devicebackend4', '1', '-busdevice4', '-pr4drv', 'ascii', '-pr4output', 'text',
               '-pr4txtdev', '0', '-prtxtdev1', str(printed),
               '-sounddev', 'dummy', '-jamaction', '0', '-warp',
               '-binarymonitor', '-binarymonitoraddress', f'ip4://127.0.0.1:{port}']
    report['command'] = command
    emu = subprocess.Popen(command, env=dict(os.environ, DISPLAY=xv.display,
                           __EGL_VENDOR_LIBRARY_FILENAMES=ci.cbm.MESA_EGL),
                           stdout=log, stderr=subprocess.STDOUT)
    status_at = lst_symbol('native-desktop/editor', 'ed_status')
    length_at = lst_symbol('native-desktop/editor', 'ed_length')

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

        def read(at, n=1):
            result = bytes(paused.read_mem(at, at+n-1, bank=banks['ram00'])); paused.resume(); return result

        def wait(predicate, label, seconds=300):
            deadline = time.monotonic()+seconds
            while time.monotonic() < deadline:
                if predicate(): return
                assert emu.poll() is None
                time.sleep(.05)
            raise AssertionError(label)

        def key(value, seconds=300):
            """Inject one key at a paused idle instant (the Editor clears
            N_READY while it samples the pointer)."""
            deadline = time.monotonic()+seconds; before = None
            while before is None:
                with paused.paused('key'):
                    if (bytes(paused.read_mem(0x3d12, 0x3d12, bank=banks['ram00'])) == b'\1' and
                            bytes(paused.read_mem(0xd0, 0xd0, bank=banks['ram00'])) == b'\0'):
                        before = int.from_bytes(bytes(paused.read_mem(0x3d13, 0x3d14, bank=banks['ram00'])), 'little')
                        paused.write_mem(0x3d12, b'\0'); paused.write_mem(0x34a, bytes([value]))
                        paused.write_mem(0xd0, b'\1')
                if before is None:
                    assert time.monotonic() < deadline, f'never idle for key {value:#x}'
                    assert emu.poll() is None
                    time.sleep(.02)
            wait(lambda: int.from_bytes(read(0x3d13, 2), 'little') == (before+1) & 0xffff and
                 read(0x3d12) == b'\1', f'key {value:#x} consumed', seconds)

        wait(lambda: read(0x3d12) == b'\1', 'launcher ready', 600)
        key(ord('E'))                                   # the Editor
        try:
            wait(lambda: read(0x3d70, 11) == b'TEXT EDITOR' and read(0x3d12) == b'\1', 'editor ready', 180)
        except AssertionError:
            raise AssertionError(('editor ready', read(0x3d20, 4).hex(), read(0x3d40, 16), read(0x3d60, 32)))
        text = '\r'.join(LINES).encode()
        for c in text:
            key(c)
        assert int.from_bytes(read(length_at, 3), 'little') == len(text)
        check('the Editor started from the launcher and holds the typed document', length=len(text))
        key(16)                                         # Ctrl-P
        status = read(status_at)[0]
        assert status == 32, ('status', status)
        check('Ctrl-P reports "printed"', status=status)
    finally:
        if mon: mon.quit_emulator()             # a clean exit flushes the printer file
        else: emu.terminate()
        emu.wait(timeout=30); xv.stop(); log.close()
    output = printed.read_bytes() if printed.exists() else b''
    report['printer_output'] = output.decode('latin-1')
    lines = [line.rstrip() for line in output.decode('latin-1').splitlines() if line.strip()]
    assert lines == LINES, lines
    check('VICE\'s device-4 printer printed the document line for line', lines=lines)
    report['passed'] = True
    args.report.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
