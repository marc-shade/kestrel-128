"""The persistent AES demo (40-column alert, menu and window tests) on the
reference C128.

Invoked by hw_ultimate_check.py --native-aes. The demo is built from
examples/native-aes/build.py into the evidence directory, twice, and the two
builds must be identical byte for byte; the boot disk is
target/native/kestrel.d64 with CALC replaced by AESDEMO and AESVC.PRG
added, as tests/ci_native_aes_vice.py builds it. Its sha256 is recorded.

Drive A is recorded, the private disk is mounted on it read-only in 1541
mode, the machine is reset and left 60 seconds without RAM DMA while it
boots (hw_native_check.quiet_boot). Then native_aes_workflow.py, the same
workflow the VICE test runs, injects the same keys and compares the VIC
surface after each step with native_aes_scene exactly. App RAM, bank 1 and
the surface are read through the held CPU capture (the AES passes its event
packets through N_BUFFER, the page the capture borrows). The C key, which
loads AESDEMO and AESVC.PRG, is followed by 90 seconds without DMA.

Afterwards drive A gets its original image and mode back, the upload is
retrieved over FTP and must be unchanged, then deleted and confirmed absent,
and the C128 is reset (hw_session.py).
"""
import hashlib
import json
from pathlib import Path
import tempfile

from hw_session import HardwareSession
from hw_dos_context import DosContexts
from hw_storage_check import HardwareMonitor
from hw_native_check import hashes, quiet_boot
from hw_native_gem_check import HeldMachine
from native_aes_workflow import build_demo, aes_workflow

BOOT_QUIET = 60


def run(ult, *, dos_contexts=False):
    work = Path(tempfile.mkdtemp(prefix='kestrel-hardware-aes-'))
    print(f'AES hardware evidence: {work}', flush=True)
    demo = build_demo(work/'demo')
    build_demo(work/'rebuild')
    disk = demo['disk'].read_bytes()
    built = {name: hashlib.sha256((work/'demo'/name).read_bytes()).hexdigest()
             for name in ('AESDEMO.PRG', 'AESVC.PRG', 'aes.d64')}
    rebuilt = {name: hashlib.sha256((work/'rebuild'/name).read_bytes()).hexdigest() for name in built}
    assert built == rebuilt, ('the demo build is not reproducible', built, rebuilt)
    report = dict(passed=False, physical_hardware_io=True, build=hashes(), host=ult.host, work=str(work),
                  demo_build=demo['images'], demo_sha256=built, demo_disk_sha256=built['aes.d64'],
                  demo_rebuild_identical=True, checks=[], events=[], boot_quiet_seconds=BOOT_QUIET,
                  host_request_timeout_seconds=ult.timeout, uncertain_host_writes=ult.uncertain_writes,
                  host_connect_attempts=ult.connect_attempts, host_connect_failures=ult.connect_failures,
                  host_control_requests=ult.control_requests, host_upload_checks=ult.upload_checks)

    def save(): (work/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    ult.record_event = save
    save()
    mon = HardwareMonitor(ult)
    session = HardwareSession(ult, work, report, save, drives=('a',),
                              dos_contexts=DosContexts(ult, work) if dos_contexts else None)
    before = session.snapshot()
    (work/'ultimate-version.json').write_text(ult.version())
    if not (before['a']['enabled'] and before['a']['bus_id'] == 8):
        report['error'] = 'precondition: drive A must be enabled on IEC 8'; save()
        raise SystemExit(f'FAIL: {report["error"]}')

    def body():
        try:
            report['upload_path'] = session.upload(disk, 'a', 'd64', 'readonly', retrieve=True); save()
            mounted = report['drives_native'] = session.drives('native'); save()
            assert mounted['a']['type'] == '1541' and ult.mounted_path('a') == report['upload_path']
            ult.reset(); quiet_boot('AES demo boot', BOOT_QUIET)
            held_workflow(mon, work, demo, report, save)
        except BaseException as error:
            report['error'] = f'{type(error).__name__}: {error}'; save()
            try:
                (work/'failure-mailbox.bin').write_bytes(bytes(mon.read_mem(0x3d00, 0x3dff)))
            except Exception as diagnostic:
                report['diagnostic_error'] = str(diagnostic); save()
            raise
    try:
        session.run(body)
    finally:
        report['images_unchanged'] = report['build'] == hashes(); save()
    assert report['images_unchanged'] and not report['uncertain_host_writes']
    report['passed'] = True; save()
    print(f'HW-NATIVE-AES PASS; 40-column AES surfaces exact; drives restored, upload unchanged and deleted; {work}',
          flush=True)


def held_workflow(mon, work, demo, report, save, **timing):
    """The shared AES workflow through HeldMachine; also run under VICE by
    tests/ci_native_aes_vice.py --hardware-sequence (short quiet periods)."""
    machine = HeldMachine(mon, work, report, save, **timing)

    def check(name, **extra):
        report['checks'].append(dict(name=name, **extra)); save()
        print('PASS:', name, flush=True)
    aes_workflow(machine, demo, check, report)
    assert all(item.get('restored') for item in machine.capture.records), 'every capture restored its borrowed RAM'
    report['native_checks_passed'] = True; save()
