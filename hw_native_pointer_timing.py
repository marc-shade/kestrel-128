"""Time the 80-column desktop's pointer-only updates on the reference C128.

Invoked by hw_ultimate_check.py --native-pointer-timing. It builds the
measurement-only desktop (native_pointer_timing.py: never shipped; the
normal images in target/ are hashed before and after and must not change),
records drive A, mounts the measurement disk there read-only, and afterwards
drive A gets its original image and mode back, the upload is read back (it
must be unchanged), deleted and confirmed absent, and the C128 is reset
(hw_session.py).

The C128 moves the pointer itself through the shipped 1351 sampling path
with synthetic counters; the physical 1351 must stay still (its button is
still read). Key T starts the run: an approach to (308,20) over empty space,
then 512 updates with dx +5/-5 and dy 3, each timed with CIA2 timer B.

Host traffic and timed code never overlap: no RAM DMA while the boot loads
over IEC (hw_native_check.quiet_boot, 240 seconds as for the desktop), and
after the start key the host sends nothing for RUN_QUIET seconds, so no DMA
pause can stretch an update. If the run was still going at the first
contact, the check fails (the figures are kept in the report).
"""
import hashlib
import json
from pathlib import Path
import tempfile
import time

from hw_native_check import hashes, quiet_boot
from hw_native_desktop_check import idle_admission
from hw_session import HardwareSession
from hw_dos_context import DosContexts
from hw_storage_check import HardwareMonitor
from native_capture import NativeCapture, wait
import native_pointer_timing as timing

RUN_QUIET = 90                # VICE (NTSC): the 512 timed updates came 2 jiffies apart, 17 s


def run(ult, *, monitor_class=HardwareMonitor, dos_contexts=False, run_quiet=RUN_QUIET):
    work = Path(tempfile.mkdtemp(prefix='kestrel-hardware-pointer-timing-'))
    print(f'Pointer timing hardware evidence: {work}', flush=True)
    report = dict(passed=False, physical_hardware_io=True, build=hashes(),
                  uncertain_host_writes=ult.uncertain_writes, host_connect_failures=ult.connect_failures,
                  host_control_requests=ult.control_requests, host_upload_checks=ult.upload_checks,
                  quiet_seconds=dict(boot=240, after_start_key=run_quiet))
    def save(): (work/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    ult.record_event = save
    manifest = report['measurement_build'] = timing.build(work/'build'); save()
    disk = (work/'build'/'pointer-timing.d64').read_bytes()
    header_bytes = (work/'build'/'desktop.prg').read_bytes()[2:34]
    mon = monitor_class(ult)
    def paused_read(address, count):
        data = bytes(mon.read_mem(address, address+count-1)); mon.resume(); return data
    paused = getattr(mon, 'paused', None)
    capture = NativeCapture(mon, work, quiet=2, kernel_prefix='native-desktop',
                            batch=idle_admission(paused, paused_read, report.setdefault('capture_admissions', []))
                            if paused else None)
    report.update(captures=capture.records, paused_capture_batches=getattr(mon, 'batches', []),
                  ram_write_receipts=getattr(ult, 'ram_write_receipts', []))
    session = HardwareSession(ult, work, report, save, drives=('a',),
                              dos_contexts=DosContexts(ult, work) if dos_contexts else None)
    before = session.snapshot(); assert before['a']['enabled'] and before['a']['bus_id'] == 8
    (work/'ultimate-version.json').write_text(ult.version())

    def read(address, count=1):
        data = bytes(mon.read_mem(address, address+count-1)); mon.resume(); return data
    def ready(): return read(0x3d12) == b'\1' and read(0xd0, 2) == bytes(2)
    def header(label):
        # The desktop image lies under ROM in the IRQ/KERNAL map: read it on the C128.
        return timing.decode_header(capture.capture(label, address=manifest['header'], count=timing.HEADER_BYTES))

    def body():
        report['stage'] = 'boot'; save()
        path = report['upload_path'] = session.upload(disk, 'a', 'd64', 'readonly', retrieve=True); save()
        ult.reset(); quiet_boot('Pointer timing boot', 240)
        wait(lambda: read(0x1c13, 6) == b'KES128' and read(0x3d60, 32) == header_bytes and ready(),
             'measurement desktop boot', 300)
        report['before_start'] = start = header('header-before-start'); save()
        # Nothing is recorded before the start key. A connected 1351 can still
        # cause pointer calls at rest (its pots straddle a count boundary);
        # the run ignores the physical mouse, so those calls are only recorded.
        assert start['phase'] == 0 and start['count'] == 0, start
        report['calls_before_start'] = start['calls']
        report['stage'] = 'start'; save()
        keys = int.from_bytes(read(0x3d13, 2), 'little')
        deadline = time.monotonic()+60; started = None
        while started is None:          # inject only at an idle instant, as the desktop check does
            with capture.batch(f'key-{timing.KEY:02x}'):
                if ready():
                    mon.write_mem(0x3d12, b'\0'); mon.write_mem(0x34a, bytes([timing.KEY])); mon.write_mem(0xd0, b'\1')
                    mon.resume(); started = time.monotonic()
            if started is None:
                assert time.monotonic() < deadline, 'desktop never idle for the start key'
                time.sleep(.01)
        report['stage'] = 'measuring'; save()
        print(f'Pointer timing: started; no host traffic for {run_quiet} seconds', flush=True)
        time.sleep(run_quiet)
        progress = report['progress'] = []
        for attempt in range(6):
            state = header(f'header-{attempt}')
            progress.append(dict(seconds=round(time.monotonic()-started, 1), phase=state['phase'], count=state['count']))
            save()
            if state['phase'] == 3:
                break
            time.sleep(30)
        else:
            raise AssertionError(('measurement did not finish', progress))
        report['host_contact_before_done'] = progress[0]['phase'] != 3
        report['first_contact_count'] = progress[0]['count']
        report['stage'] = 'read'; save()
        total = timing.COUNT*len(timing.ARRAYS)
        arrays = b''.join(capture.capture(f'arrays-{offset:04x}', address=manifest['arrays']+offset,
                                          count=min(2000, total-offset)) for offset in range(0, total, 2000))
        raw = capture.capture('header-final', address=manifest['header'], count=timing.HEADER_BYTES)
        (work/'pointer-timing-header.bin').write_bytes(raw); (work/'pointer-timing-arrays.bin').write_bytes(arrays)
        final, records = timing.decode(raw, arrays)
        report.update(header=final, records=records, summary=timing.summarize(final, records),
                      start_key_consumed=int.from_bytes(read(0x3d13, 2), 'little') == (keys+1) & 65535,
                      video_standard='NTSC' if read(0x0a03) == b'\0' else 'PAL', rs232_nmi_enable=read(0x0a0f)[0])
        if report['host_contact_before_done']:
            report['summary_before_contact'] = timing.summarize(final, records[:report['first_contact_count']])
        save()
        summary = report['summary']
        assert report['start_key_consumed'], 'the start key was not consumed exactly once'
        assert summary['calibration']['exact'], ('timer calibration', summary['calibration'])
        assert (final['count'], final['driven'], final['missing'], summary['overflow']) == (timing.COUNT, timing.COUNT, 0, 0), final
        assert final['crb_halt'] == final['crb_before'] & 0x80 and report['rs232_nmi_enable'] == 0
        report['native_checks_passed'] = True; save()

    try:
        session.run(body)
    finally:
        report['images_unchanged'] = report['build'] == hashes()
        retrieved = session.retrieved.get(report.get('upload_path'))
        report['upload_unchanged'] = retrieved is not None and hashlib.sha256(retrieved).digest() == hashlib.sha256(disk).digest()
        save()
    assert report['images_unchanged'] and not report['uncertain_host_writes'] and report['upload_unchanged']
    assert not report['host_contact_before_done'], 'the host read the C128 while updates were still being timed'
    report['passed'] = True; save()
    summary = report['summary']
    print('Pointer timing (cycles):', json.dumps(dict(service=summary['service'], call=summary['call'])), flush=True)
    print(f'HW-NATIVE-POINTER-TIMING PASS; {summary["updates"]} updates; drives restored, upload deleted; {work}', flush=True)
