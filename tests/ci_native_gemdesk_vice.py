#!/usr/bin/env python3
"""GEMDESK in a real emulated C128 (VICE x128, 1581 true drive emulation):
boot gem.d81, compare the desktop with the CPU-test oracle, open drive 8 from
the keyboard, launch Calculator, leave it, and check the AES session brings
the window and its selection back, then open a SEQ file in the Editor as a
document and return to the desktop, open a USHT workbook (a SEQ file, as
Sheet saves it) in Sheet and return, then open a UPNT picture (a SEQ file, as
Paint saves it) in Paint. The key sequence, documents and oracles live in
native_gemdesk_workflow.py, which hw_native_gem_check.py runs on the real
C128."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT)]
import vice_harness as ci  # noqa: E402
from native_capture_transport import PausedViceMonitor  # noqa: E402
from vice_workflow_machine import ViceMachine, ViceDma  # noqa: E402
# The workflow (keys, documents and oracles) is shared with hw_native_gem_check.py;
# other GEMDESK suites import d81_entries from here.
from native_gemdesk_workflow import d81_entries, prepare_disks, gemdesk_workflow  # noqa: E402,F401


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--hardware-sequence', action='store_true',
                        help='run hw_native_gem_check.py\'s own workflow code (HeldMachine, held CPU captures) '
                             'with short quiet periods instead of direct monitor reads')
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix='kestrel-gemdesk-vice-'))
    disks = prepare_disks(work)
    disk, disk9 = disks['disk'], disks['disk9']
    report = dict(passed=False, physical_hardware_io=False, work=str(work), checks=[],
                  entries=[e['name'].decode('latin-1') for e in disks['entries']])
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
    xv = ci.cbm.Xvfb(); log = (work/'vice.log').open('w'); mon = None
    command = ['x128', '-default', '-8', str(disk), '-drive8true', '-drive8type', '1581',
               '-9', str(disk9), '-drive9true', '-drive9type', '1581',
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
            from hw_native_gem_check import keyboard_workflow
            report['hardware_sequence'] = True
            keyboard_workflow(ViceDma(mon, banks['ram00']), work, disks, report,
                              lambda: args.report.write_text(json.dumps(report, indent=2)+'\n'),
                              usb=False, quiet=.1, pause=.2)
        else:
            gemdesk_workflow(ViceMachine(paused, banks, emu, work), disks, check, report)
        report['passed'] = True
    finally:
        args.report.write_text(json.dumps(report, indent=2)+'\n')
        if mon: mon.quit_emulator()
        else: emu.terminate()
        emu.wait(timeout=15); xv.stop(); log.close()


if __name__ == '__main__':
    main()
