#!/usr/bin/env python3
"""The persistent AES in a real emulated C128 (VICE x128): cold boot, load
AESVC.PRG into bank 1, then drive the alert, menu and window demos from the
keyboard and compare the complete VIC surface with the CPU-test oracles.
The key sequence and oracles live in native_aes_workflow.py, which
hw_native_aes_check.py runs on the real C128."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import vice_harness as ci  # noqa: E402
from native_capture_transport import PausedViceMonitor  # noqa: E402
from vice_workflow_machine import ViceMachine, ViceDma  # noqa: E402
# The workflow (keys and oracles) is shared with hw_native_aes_check.py.
from native_aes_workflow import build_demo, aes_workflow  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--hardware-sequence', action='store_true',
                        help='run hw_native_aes_check.py\'s own workflow code (HeldMachine, held CPU captures) '
                             'with short quiet periods instead of direct monitor reads')
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix='kestrel-aes-vice-'))
    demo = build_demo(work)
    disk = demo['disk']
    report = dict(passed=False, physical_hardware_io=False, work=str(work), images=demo['images'], checks=[],
                  disk_sha256=hashlib.sha256(disk.read_bytes()).hexdigest())
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
        if args.hardware_sequence:
            from hw_native_aes_check import held_workflow
            report['hardware_sequence'] = True
            held_workflow(ViceDma(mon, banks['ram00']), work, demo, report,
                          lambda: args.report.write_text(json.dumps(report, indent=2)+'\n'), quiet=.1, pause=.2)
        else:
            aes_workflow(ViceMachine(paused, banks, emu, work), demo, check, report)
        report['passed'] = True
    finally:
        args.report.write_text(json.dumps(report, indent=2)+'\n')
        if mon: mon.quit_emulator()
        else: emu.terminate()
        emu.wait(timeout=15); xv.stop(); log.close()


if __name__ == '__main__':
    main()
