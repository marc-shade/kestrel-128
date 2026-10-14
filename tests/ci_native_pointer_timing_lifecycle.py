#!/usr/bin/env python3
"""hw_native_pointer_timing.run against the simulated Ultimate and FTP server
of ci_hardware_uploads (no hardware I/O).

The C128 side is a stand-in: after the start key it serves a finished run's
header and counters (synthetic numbers) to the native capture. Checked here:
the measurement build is made outside target/, drive A is restored, the
read-only upload comes back unchanged and is deleted, the report carries
passed/restore/images_unchanged/host_connect_failures/uncertain_host_writes
and the statistics, and a run that was still going at the first contact,
or whose calibration is not exact, fails after the same restoration."""
import argparse
from contextlib import nullcontext
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'tests')]
import hw_native_pointer_timing as lifecycle
import hw_session
import native_pointer_timing as timing
from ci_hardware_uploads import Machine, FTP


def header(phase, count, calibration=(19, 1020, 2021), service=19, arrays=0):
    data = bytearray(timing.HEADER_BYTES)
    data[:5] = b'PTIM\1'; data[5] = phase
    for at, value in ((6, count), (8, timing.COUNT), (10, count), (16, calibration[0]), (18, calibration[1]),
                      (20, calibration[2]), (22, service), (31, count+57 if phase else 0), (33, arrays)):
        data[at:at+2] = value.to_bytes(2, 'little')
    data[13], data[14], data[15] = 8, 0, 0x19
    return bytes(data)


def arrays():
    columns = {name: bytearray(timing.COUNT) for name in timing.ARRAYS}
    for i in range(timing.COUNT):
        for name, value in (('pre', 1550+i % 3), ('svc', 16000+(i*37) % 1300), ('post', 1450+i % 5)):
            columns[name+'_lo'][i], columns[name+'_hi'][i] = value & 255, value >> 8
        columns['jif'][i] = (75+2*i) & 255; columns['irq'][i] = 1
    return b''.join(bytes(columns[name]) for name in timing.ARRAYS)


class C128(Machine):
    """Boots the measurement desktop on reset; the start key runs it."""
    def __init__(self, work, fault, **kwargs):
        super().__init__(**kwargs)
        self.work, self.fault, self.started, self.headers = work, fault, False, 0

    def on_reset(self):
        super().on_reset()
        build = self.work/'build/desktop.prg'
        if build.exists(): self.ram[0x3d60:0x3d80] = build.read_bytes()[2:34]

    def write_mem(self, address, data):
        super().write_mem(address, data)
        if address == 0xd0 and data == b'\1' and self.ram[0x34a] == timing.KEY:
            self.ram[0xd0] = 0; self.ram[0x3d12] = 1
            self.ram[0x3d13] = (self.ram[0x3d13]+1) & 255
            self.started = True


def capture_class(m):
    class Capture:
        def __init__(self, *args, **kwargs):
            self.records = []; self.batch = kwargs.get('batch') or (lambda label: nullcontext())

        def capture(self, label, *, mode=0, bank=0, address=0, count=2000):
            manifest = json.loads((m.work/'build/manifest.json').read_text())
            self.records.append(dict(label=label, address=address, count=count))
            if address == manifest['header']:
                if not m.started: return header(0, 0)
                m.headers += 1
                calibration = (19, 1021, 2021) if m.fault == 'calibration' else (19, 1020, 2021)
                if m.fault == 'contact' and m.headers == 1: return header(2, 300, calibration, arrays=manifest['arrays'])
                return header(3, timing.COUNT, calibration, arrays=manifest['arrays'])
            offset = address-manifest['arrays']
            assert m.started and 0 <= offset and offset+count <= timing.COUNT*len(timing.ARRAYS), (label, address)
            return arrays()[offset:offset+count]
    return Capture


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args(); result = dict(passed=False, physical_hardware_io=False, cases=[])
    original = bytes((i*7) & 255 for i in range(174848))
    for fault in (None, 'contact', 'calibration'):
        with tempfile.TemporaryDirectory(prefix='kestrel-pointer-timing-lifecycle-') as temporary:
            work = Path(temporary)
            m = C128(work, fault, a=('/Temp/temp0098', ''), files={'/Temp/temp0098': original})
            ftp = FTP(m)
            def session(ult, work, report, save, drives, dos_contexts=None):
                return hw_session.HardwareSession(ult, work, report, save, drives=drives, ftp=ftp, dos_contexts=dos_contexts)
            message = None
            with patch.object(lifecycle, 'tempfile', SimpleNamespace(mkdtemp=lambda **_: str(work))), \
                 patch.object(lifecycle, 'NativeCapture', capture_class(m)), \
                 patch.object(lifecycle, 'HardwareSession', session), \
                 patch.object(lifecycle, 'quiet_boot', lambda *_: None), \
                 patch.object(lifecycle.time, 'sleep', lambda *_: None):
                try: lifecycle.run(m)
                except AssertionError as error: message = str(error)
            report = json.loads((work/'report.json').read_text())
            assert report['passed'] == (fault is None), (fault, message)
            restore = report['restore']
            uploads = [p for p in m.files if p.startswith('/Temp/') and p != '/Temp/temp0098']
            assert restore['passed'] and restore['cleanup_complete'] and not uploads, restore
            assert m.state['a']['image_file'] == '/Temp/temp0098' and m.events[-1] == 'reset'
            assert m.events[:2] == ['upload-a', 'reset'] and m.ram[0x34a] == timing.KEY
            assert report['upload_unchanged'] and report['images_unchanged']
            disk = (work/'build/pointer-timing.d64').read_bytes()
            assert restore['retrieved'][report['upload_path']]['sha256'] == hashlib.sha256(disk).hexdigest()
            assert not report['uncertain_host_writes'] and report['host_connect_failures'] == []
            summary = report['summary']
            assert summary['updates'] == timing.COUNT and summary['service']['count'] == timing.COUNT
            assert summary['jiffies_between_updates'] == {'2': timing.COUNT-1}
            if fault is None:
                assert summary['calibration']['exact'] and not report['host_contact_before_done']
                assert summary['service']['min'] == 16000-19 and summary['call']['under_frame'] == 0
            elif fault == 'contact':
                assert 'still being timed' in message and report['first_contact_count'] == 300
                assert report['summary_before_contact']['updates'] == 300
            else:
                assert 'timer calibration' in message and not summary['calibration']['exact']
            result['cases'].append(dict(fault=fault, error=message, events=m.events, passed=True))
            print('PASS:', fault or 'complete run', flush=True)
    result['passed'] = True; args.report.write_text(json.dumps(result, indent=2)+'\n')
    print(f'PASS: {len(result["cases"])} pointer timing lifecycle cases; drives restored, upload read back and '
          'deleted in each; no hardware I/O')


if __name__ == '__main__':
    main()
