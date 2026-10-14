#!/usr/bin/env python3
"""Boot the GEM profile (gem.d81) on the reference C128 through the Ultimate
II+ and compare GEMDESK's screens with the CPU-test oracles.

hw_ultimate_check.py --native-gem runs the keyboard workflow; this script's
own command line also offers the interactive and diagnostic modes below.

The Ultimate's DOS answers GEMDESK's identify query here, so every desktop
oracle includes the USB icon (VICE has no Ultimate and shows none). The
check refuses to start when the Ultimate's printer emulation is enabled on
IEC 4 or 5, where GEMDESK would show a Printer icon the oracles leave out.

The keyboard workflow is native_gemdesk_workflow.py, the one the VICE test
tests/ci_native_gemdesk_vice.py runs: the desktop, drive 9's window (a 1581
with a D81, detected from its DOS identity) and File:Close, drive 8's
window, Calculator and back, a SEQ document in the Editor and back, a USHT
workbook in Sheet and back, a UPNT picture in Paint. A private copy of
gem.d81 (plus the NOTE, LEDGER and PICTURE documents the VICE test adds) is
mounted read-only on drive A in 1581 mode, and drive 9's two-file D81
read-only on drive B (IEC 9) in 1581 mode; the machine is reset and left
150 seconds without RAM DMA while the kernel and GEMDESK load. Screens and
app RAM are read by the held CPU capture (HeldCapture); no video signal is
captured. The other modes use drive A only.

Afterwards each drive gets its original image and mode back (or is
unmounted if it had none), each upload is retrieved over FTP and must be
unchanged, then deleted and its absence confirmed, and the C128 is reset
(hw_session.py). Nothing on the machine's own disks is written. The report
is report.json in the evidence directory (and --report, when given).
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT/'tests')]
from hw_session import HardwareSession  # noqa: E402
from hw_dos_context import DosContexts  # noqa: E402
from hw_storage_check import HardwareMonitor  # noqa: E402
from hw_native_check import hashes, quiet_boot  # noqa: E402
from hw_ultimate_check import VerifiedUltimate, resolve_host  # noqa: E402
from hwlib import lst_symbol  # noqa: E402
from native_capture import wait  # noqa: E402
import native_gemdesk_scene as scene  # noqa: E402
from launcher_scene import pointer_shape  # noqa: E402
from native_aes_workflow import ready  # noqa: E402
from native_gemdesk_workflow import prepare_disks, gemdesk_workflow  # noqa: E402

IMAGES = ROOT/'target/native-desktop'
BOOT_QUIET = 150             # seconds after reset without RAM DMA (about 111 s to GEMDESK's input wait)


class HeldCapture:
    """Read native RAM through probes/native-read-held.asm. GEMDESK's idle loop
    passes every AES event packet through N_BUFFER, the page the probe writes,
    so the probe holds the IRQ while the host saves N_BUFFER, lets the copy
    run, reads it and writes N_BUFFER back; only then does the foreground run."""

    def __init__(self, mon, work):
        self.mon, self.work = mon, work
        output = work/'native-read-held.prg'
        subprocess.run(['64tass', '-a', str(ROOT/'probes/native-read-held.asm'), '-o', str(output)],
                       check=True, capture_output=True)
        self.prg = output.read_bytes()
        assert self.prg[:2] == b'\0\x3e' and len(self.prg)-2 <= 0x1f0
        self.records = []

    def read(self, address, count=1):
        return bytes(self.mon.read_mem(address, address+count-1))

    def until(self, predicate, label, seconds=5):
        deadline = time.monotonic()+seconds
        while not predicate():
            assert time.monotonic() < deadline, label

    def capture(self, label, *, bank=0, address=0, count=2000, mode=0):
        """mode 0: RAM of bank 0/1; mode 1: VDC memory (retried until the
        foreground is idle at its input wait)."""
        assert bank in (0, 1) and mode in (0, 1) and 1 <= count and address+count <= 65536
        if bank == 0 and mode == 0:
            assert address+count <= 0x3a00 or address >= 0x4000, 'source overlaps the borrowed pages'
        record = dict(label=label, bank=bank, mode=mode, address=address, count=count, chunks=[], restored=False, busy=0,
                      probe_sha256=hashlib.sha256(self.prg).hexdigest())
        self.records.append(record)
        result = bytearray()
        for offset in range(0, count, 512):
            size = min(512, count-offset)
            assert self.read(0x1c13, 6) == b'KES128' and self.read(0x3d91) == b'\0' and self.read(0xd0) == b'\0', \
                'native kernel running, file service idle, no keys pending'
            source = address+offset
            for attempt in range(200):
                scratch = self.read(0x3e00, 512)
                oldirq = self.read(0x314, 2); assert oldirq != b'\0\x3e'
                self.mon.write_mem(0x3e00, self.prg[2:])
                self.mon.write_mem(0x3ff0, oldirq+bytes([0, mode, bank])+source.to_bytes(2, 'little')
                                   + size.to_bytes(2, 'little')+bytes(7))
                self.mon.write_mem(0x314, b'\0\x3e')
                self.until(lambda: self.read(0x3ffe) == b'\1' or self.read(0x3ff2) == b'\5', f'{label}: probe held')
                if self.read(0x3ffe) == b'\1':
                    break
                record['busy'] += 1          # VDC: the foreground was not idle; nothing was touched
                self.until(lambda: self.read(0x314, 2) == oldirq, f'{label}: busy probe returned')
                time.sleep(0.05)
                self.mon.write_mem(0x3e00, scratch)
                assert self.read(0x3e00, 512) == scratch
            else:
                raise AssertionError((label, 'the foreground was never idle for a VDC capture'))
            saved = self.read(0x3a00, size)
            self.mon.write_mem(0x3ffe, b'\2')
            self.until(lambda: self.read(0x3ff2) != b'\0', f'{label}: copy')
            status = self.read(0x3ff2, 12)
            payload = self.read(0x3a00, size)
            self.mon.write_mem(0x3a00, saved)
            buffer_back = self.read(0x3a00, size) == saved
            self.mon.write_mem(0x3ffe, b'\3')
            self.until(lambda: self.read(0x314, 2) == oldirq, f'{label}: released')
            time.sleep(0.1)
            self.mon.write_mem(0x3e00, scratch)
            scratch_back = self.read(0x3e00, 512) == scratch
            record['chunks'].append(dict(address=source, count=size, code=status[0], mmu=status[9:12].hex(),
                                         n_buffer_restored=buffer_back, scratch_restored=scratch_back,
                                         sha256=hashlib.sha256(payload).hexdigest()))
            assert status[0] == 1, (label, 'probe status', status[0])
            assert buffer_back and scratch_back, (label, 'borrowed RAM not restored')
            result += payload
        record['restored'] = True
        (self.work/f'{label}.bin').write_bytes(result)
        return bytes(result)


class HeldMachine:
    """The workflow machine (see native_aes_workflow) on the real C128.
    Common RAM below $4000 is read directly over DMA; app RAM, bank 1 and
    the VIC surface only through the held capture (a direct DMA read can land
    while the AES has bank 1 mapped). A key goes through the keyboard buffer,
    then nothing touches the machine for the key's quiet period, as long as
    the key may start IEC traffic, before its consumption is polled."""
    scale = 2                 # workflow timeouts and settle budgets, doubled
    min_attempts = 4          # surface reads before a mismatch fails
    QUIET = {None: 4, 'scan': 10, 'launch': 90, 'leave': 60}

    def __init__(self, mon, work, report, save, *, quiet=None, pause=5):
        """quiet and pause replace the hardware timings (the VICE rehearsal)."""
        self.mon, self.work, self.report, self.save = mon, Path(work), report, save
        self.capture = HeldCapture(mon, self.work)
        self.quiet = dict(self.QUIET) if quiet is None else dict.fromkeys(self.QUIET, quiet)
        self.pause_seconds = pause
        report['captures'] = self.capture.records
        report['key_quiet_seconds'] = {str(k): v for k, v in self.quiet.items()}
        report.setdefault('events', [])
        self.values = 0

    def read(self, at, n=1):
        assert at+n <= 0x4000, 'common RAM only'
        return bytes(self.mon.read_mem(at, at+n-1))

    def value(self, at, n=1, bank=0):
        self.values += 1
        return self.capture.capture(f'value-{self.values:04d}-b{bank}-{at:04x}', bank=bank, address=at, count=n)

    def surface(self, label):
        return b''.join(self.capture.capture(f'{label}-{offset:04x}', address=0xc000+offset,
                                             count=min(2000, 9216-offset)) for offset in range(0, 9216, 2000))

    def pause(self):
        time.sleep(self.pause_seconds)

    def wait(self, predicate, label, seconds=300):
        """Poll predicate; log every app switch (header, N_CURRENT, N_READY,
        file service, pending keys) to report['switch_log']."""
        started, last = time.monotonic(), None
        while time.monotonic()-started < seconds*self.scale:
            state = (self.read(0x3d60, 32).hex(), self.read(0x3d20)[0], self.read(0x3d12)[0],
                     self.read(0x3d91)[0], self.read(0xd0)[0])
            if state != last:
                entry = dict(label=label, t=round(time.monotonic()-started, 1), header=state[0], current=state[1],
                             ready=state[2], file_service=state[3], keys_pending=state[4])
                self.report.setdefault('switch_log', []).append(entry); self.save(); last = state
            if predicate():
                return
            time.sleep(0.5)
        raise AssertionError(label)

    def key(self, value, io=None):
        quiet = self.quiet[io]
        self.wait(lambda: ready(self), 'native input ready', 300)
        previous = int.from_bytes(self.read(0x3d13, 2), 'little')
        self.mon.write_mem(0x3d12, b'\0'); self.mon.write_mem(0x34a, bytes([value])); self.mon.write_mem(0xd0, b'\1')
        start = time.monotonic()
        time.sleep(quiet)                     # no DMA while the key may start a load
        self.wait(lambda: int.from_bytes(self.read(0x3d13, 2), 'little') == (previous+1) & 65535 and ready(self),
                  f'key {value:#x}', 300)
        self.report['events'].append(dict(key=value, io=io, quiet=quiet, seconds=round(time.monotonic()-start, 1)))
        self.save()


def gem_hashes():
    """hw_native_check.hashes() plus the GEM image and its pins."""
    build = hashes()
    for path in (IMAGES/'gem.d81', IMAGES/'images.json'):
        build[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return build


def run(ult, *, dos_contexts=False, report_path=None, image=None, mode='keyboard', seconds=None, screens=None,
        samples=None):
    """mode: keyboard (the shared workflow), mouse, mirror, show (seconds),
    screens (directory) or sample-ready (samples)."""
    assert mode in ('keyboard', 'mouse', 'mirror', 'show', 'screens', 'sample-ready')
    work = Path(tempfile.mkdtemp(prefix='kestrel-hardware-gem-'))
    print('GEM hardware evidence:', work, flush=True)
    keyboard = mode == 'keyboard'
    disks = prepare_disks(work, image)
    disk = disks['disk']
    pins = json.loads((IMAGES/'images.json').read_text())
    gem_sha256 = hashlib.sha256((image or IMAGES/'gem.d81').read_bytes()).hexdigest()
    if image is None:
        assert gem_sha256 == pins['gem.d81']['sha256'], 'gem.d81 differs from images.json'
    report = dict(passed=False, physical_hardware_io=True, host=ult.host, work=str(work), mode=mode,
                  build=gem_hashes(), image=str(image) if image else None, gem_d81_sha256=gem_sha256,
                  private_disk_sha256=hashlib.sha256(disk.read_bytes()).hexdigest(),
                  drive9_disk_sha256=hashlib.sha256(disks['disk9'].read_bytes()).hexdigest() if keyboard else None,
                  entries=[e['name'].decode('latin-1') for e in disks['entries']], checks=[], events=[],
                  boot_quiet_seconds=BOOT_QUIET, host_request_timeout_seconds=ult.timeout,
                  uncertain_host_writes=ult.uncertain_writes, host_connect_attempts=ult.connect_attempts,
                  host_connect_failures=ult.connect_failures, host_control_requests=ult.control_requests,
                  host_upload_checks=ult.upload_checks)

    def save():
        text = json.dumps(report, indent=2)+'\n'
        (work/'report.json').write_text(text)
        if report_path:
            Path(report_path).write_text(text)
    ult.record_event = save
    save()

    mon = HardwareMonitor(ult)
    session = HardwareSession(ult, work, report, save, drives=('a', 'b') if keyboard else ('a',),
                              dos_contexts=DosContexts(ult, work) if dos_contexts else None)
    before = session.snapshot()
    (work/'ultimate-version.json').write_text(ult.version())
    try:
        assert before['a']['enabled'] and before['a']['bus_id'] == 8, 'drive A must be enabled on IEC 8'
        if keyboard:
            assert before['b']['enabled'] and before['b']['bus_id'] == 9, \
                'the drive-9 step needs drive B enabled on IEC 9'
        printer = before.get('Printer Emulation')
        assert printer is not None, 'the Ultimate does not list its printer emulation; the desktop oracle needs it off'
        assert not (printer.get('enabled') and printer.get('bus_id') in (4, 5)), \
            f'printer emulation answers on IEC {printer.get("bus_id")}: GEMDESK would show a Printer icon'
    except AssertionError as error:
        report['error'] = f'precondition: {error}'; save()
        raise

    def body():
        try:
            report['upload_path'] = session.upload(disk.read_bytes(), 'a', 'd81', 'readonly', retrieve=True); save()
            if keyboard:
                report['drive9_upload_path'] = session.upload(disks['disk9'].read_bytes(), 'b', 'd81', 'readonly',
                                                              retrieve=True); save()
            mounted = report['drives_native'] = session.drives('native'); save()
            assert mounted['a']['type'] == '1581' and ult.mounted_path('a') == report['upload_path']
            if keyboard:
                assert mounted['b']['type'] == '1581' and ult.mounted_path('b') == report['drive9_upload_path']
            ult.reset()
            quiet_boot('GEMDESK boot', BOOT_QUIET)
            entries = disks['entries']
            if mode == 'sample-ready':
                sample_ready(mon, samples, report)
            elif mode == 'show':
                show_workflow(mon, seconds, report, save)
            elif mode == 'screens':
                screens.mkdir(parents=True, exist_ok=True)
                screens_workflow(mon, work, entries, report, save, screens)
            elif mode == 'mirror':
                mirror_workflow(mon, work, entries, report, save)
            elif mode == 'mouse':
                mouse_workflow(mon, work, entries, report, save)
            else:
                keyboard_workflow(mon, work, disks, report, save)
            report['workflow_passed'] = True; save()
        except BaseException as caught:
            report['error'] = f'{type(caught).__name__}: {caught}'; save()
            raise
    try:
        session.run(body)
    finally:
        report['images_unchanged'] = report['build'] == gem_hashes(); save()
    assert report['images_unchanged'] and not report['uncertain_host_writes']
    report['passed'] = True; save()
    print(f'HW-GEM PASS ({mode}); drives restored, uploads unchanged and deleted; evidence {work}', flush=True)
    return report


def keyboard_workflow(mon, work, disks, report, save, *, usb=True, **timing):
    """The shared GEMDESK workflow through HeldMachine; also run under VICE
    by tests/ci_native_gemdesk_vice.py --hardware-sequence (usb=False, short
    quiet periods)."""
    machine = HeldMachine(mon, work, report, save, **timing)

    def check(name, **extra):
        report['checks'].append(dict(name=name, **extra)); save()
        print('PASS:', name, flush=True)

    def diagnose(stage):
        # The Editor's 80-column text (the VDC mirror's state is in editor_state).
        text80 = machine.capture.capture(f'{stage}-vdc-text', mode=1, address=0, count=2000)
        report[f'{stage}_vdc_text'] = [bytes(c if 32 <= c < 127 else 46 for c in text80[r*80:r*80+80]).decode()
                                       for r in range(25)]
        save()
    gemdesk_workflow(machine, disks, check, report, usb=usb, diagnose=diagnose)
    assert all(item.get('restored') for item in machine.capture.records), 'every capture restored its borrowed RAM'


def sample_ready(mon, count, report):
    """Diagnostic: sample N_READY ($3d12) count times over DMA once GEMDESK is up."""
    def peek(address, n=1): return bytes(mon.read_mem(address, address+n-1))
    gemdesk = (IMAGES/'gemdesk.prg').read_bytes()[2:34]
    started, polls = time.monotonic(), 0
    while not (peek(0x1c13, 6) == b'KES128' and peek(0x3d60, 32) == gemdesk and peek(0x3d12) == b'\1'):
        polls += 1
        assert time.monotonic()-started < 300, 'GEMDESK never published N_READY within 300 s'
        time.sleep(0.1)
    first_ready = round(time.monotonic()-started+BOOT_QUIET, 1)
    samples = []
    sampling = time.monotonic()
    for _ in range(count):
        samples.append(peek(0x3d12)[0])
        time.sleep(0.02)
    report['ready_samples'] = dict(count=len(samples), ready=samples.count(1),
                                   values=sorted(set(samples)), sequence=bytes(samples).hex(),
                                   first_ready_after_reset_s=first_ready, polls_before_ready=polls,
                                   sampling_seconds=round(time.monotonic()-sampling, 1))
    print('N_READY duty:', samples.count(1), '/', len(samples), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--host', help='the Ultimate II+ address (default: $KESTREL_ULTIMATE_HOST)')
    parser.add_argument('--report', type=Path, help='also write the report here')
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--mouse', action='store_true',
                       help='interactive: a person moves and clicks the 1351 while this observes')
    modes.add_argument('--mirror', action='store_true',
                       help='check the 80-column mirror byte for byte (desktop, window, menu, alert)')
    modes.add_argument('--show', type=int, metavar='SECONDS',
                       help='boot and leave GEMDESK running this long for a person to look, then restore')
    modes.add_argument('--screens', type=Path, metavar='DIR',
                       help='README screenshots of GEMDESK and the Ultimate app into DIR, then restore')
    modes.add_argument('--sample-ready', type=int, metavar='N',
                       help='diagnostic: after boot, sample N_READY ($3d12) N times over DMA and record its duty cycle')
    parser.add_argument('--image', type=Path, help='gem.d81 to boot instead of the committed target (hash recorded)')
    args = parser.parse_args()
    mode = ('mouse' if args.mouse else 'mirror' if args.mirror else 'show' if args.show else
            'screens' if args.screens else 'sample-ready' if args.sample_ready else 'keyboard')
    run(VerifiedUltimate(resolve_host(args.host), timeout=60), dos_contexts=True, report_path=args.report,
        image=args.image, mode=mode, seconds=args.show, screens=args.screens, samples=args.sample_ready)

def screens_workflow(mon, work, entries, report, save, out):
    """README screenshots on the real machine: GEMDESK, a drive window and the
    Ultimate app's Info and Drives pages, each rendered from its VIC surface
    captured through the held IRQ observer (bitmap + colour cells; no sprites)."""
    sys.path.insert(0, str(ROOT/'tools'))
    from readme_screenshots import surface_png
    capture = HeldCapture(mon, work)
    report['captures'] = capture.records
    shots = report.setdefault('screenshots', [])

    def read(address, count=1):
        return bytes(mon.read_mem(address, address+count-1))

    def ready(): return read(0x3d12) == b'\1' and read(0xd0, 2) == bytes(2)

    def key(value, quiet=4):
        wait(ready, 'native input ready', 300)
        previous = int.from_bytes(read(0x3d13, 2), 'little')
        mon.write_mem(0x3d12, b'\0'); mon.write_mem(0x34a, bytes([value])); mon.write_mem(0xd0, b'\1')
        time.sleep(quiet)                     # no DMA while a key may start a load
        wait(lambda: ready() and int.from_bytes(read(0x3d13, 2), 'little') == (previous+1) & 65535,
             f'key {value:#x}', 600)
        report['events'].append(dict(key=value)); save()

    def running(image, label):
        header = (IMAGES/image).read_bytes()[2:34]
        wait(lambda: read(0x3d60, 32) == header and ready(), label, 300)

    def shot(name, label):
        """Capture until two consecutive surfaces agree, then render it."""
        previous = None
        for attempt in range(6):
            got = b''.join(capture.capture(f'{label}-{attempt}-{offset:04x}', address=0xc000+offset,
                                           count=min(2000, 9216-offset)) for offset in range(0, 9216, 2000))
            if got == previous:
                (work/f'{label}.surface').write_bytes(got)
                surface_png(got, out/f'{name}.png', work)
                shots.append(dict(name=name, sha256=hashlib.sha256(got).hexdigest(), attempts=attempt+1)); save()
                print('saved', out/f'{name}.png', flush=True)
                return
            previous = got
            time.sleep(5)
        raise AssertionError((label, 'surface did not settle'))

    wait(lambda: read(0x1c13, 6) == b'KES128' and ready(), 'native boot', 300)
    running('gemdesk.prg', 'GEMDESK running')
    shot('gemdesk-c128', 'desktop')
    key(ord('8'), quiet=10)
    shot('gemdesk-window-c128', 'drive-8')
    names = [e['name'] for e in scene.ordered(entries, 0)]
    for _ in range(names.index(b'ULTIMATE')+1):
        key(0x11)
    key(13, quiet=90)
    running('controls.prg', 'Ultimate running')
    time.sleep(10)
    shot('ultimate-c128', 'ultimate-info')
    key(ord('D'), quiet=20)
    shot('ultimate-drives-c128', 'ultimate-drives')
    key(27, quiet=60)
    running('gemdesk.prg', 'GEMDESK back from Ultimate')
    assert all(item.get('restored') for item in capture.records), 'every capture restored its borrowed RAM'


def mirror_workflow(mon, work, entries, report, save):
    """The VDC must hold the VIC surface as native_vdc_mirror renders it: the
    VIC surface and the whole VDC bitmap (and colours on a 64 KiB VDC) are read
    through the held capture and compared."""
    from native_vdc_mirror import bitmap, attributes
    capture = HeldCapture(mon, work)
    report['captures'] = capture.records

    def read(address, count=1):
        return bytes(mon.read_mem(address, address+count-1))

    def ready(): return read(0x3d12) == b'\1' and read(0xd0, 2) == bytes(2)

    def value(name, n=1):
        return capture.capture(f'gd-{name}', address=lst_symbol('native-desktop/gemdesk', name), count=n)

    def check(name, **extra):
        report['checks'].append(dict(name=name, **extra)); save()
        print('PASS:', name, flush=True)

    def key(value, quiet=4):
        wait(ready, 'native input ready', 300)
        previous = int.from_bytes(read(0x3d13, 2), 'little')
        mon.write_mem(0x3d12, b'\0'); mon.write_mem(0x34a, bytes([value])); mon.write_mem(0xd0, b'\1')
        time.sleep(quiet)
        wait(lambda: ready() and int.from_bytes(read(0x3d13, 2), 'little') == (previous+1) & 65535,
             f'key {value:#x}', 600)

    def mirrored(label, oracle=None):
        for attempt in range(4):
            wait(ready, label, 120)
            state = {n: value(n)[0] for n in ('vd_phase', 'vd_live', 'vd_fault', 'vm_pending', 'vd_color',
                                              'vd_base', 'vd_pointer_visible', 'pm_y')}
            x = int.from_bytes(value('pm_x', 2), 'little')
            surface = b''.join(capture.capture(f'{label}-{attempt}-vic-{o:04x}', address=0xc000+o,
                                               count=min(2000, 9216-o)) for o in range(0, 9216, 2000))
            assert (state['vd_phase'], state['vd_live'], state['vd_fault']) == (2, 1, 0), (label, state)
            if oracle is not None:
                want = bytearray(oracle); want[8000:8128] = pointer_shape(); want[9208:9210] = b'\x7d\x7e'
                assert surface == bytes(want), (label, 'VIC surface')
            vdc = capture.capture(f'{label}-{attempt}-vdc', mode=1, address=state['vd_base']*256, count=16000)
            # A second read tells a transport glitch (the reads disagree) from a
            # mirror mismatch (they agree but differ from the VIC surface).
            again = capture.capture(f'{label}-{attempt}-vdc-again', mode=1, address=state['vd_base']*256, count=16000)
            chunks = sorted({i//512 for i in range(16000) if vdc[i] != again[i]})
            report.setdefault('vdc_rereads', []).append(dict(label=label, attempt=attempt, reads_agree=not chunks,
                                                             differing_chunks=chunks)); save()
            want = bitmap(surface, bool(state['vd_color']), x=x, y=state['pm_y'], pointer=bool(state['vd_pointer_visible']))
            colours = True
            if state['vd_color']:
                colours = capture.capture(f'{label}-{attempt}-attr', mode=1, address=0x8000, count=2000) == attributes(surface)
            if vdc == want and colours and state['vm_pending'] == 0:
                (work/f'{label}.vdc').write_bytes(vdc)
                return dict(vdc_64k=bool(state['vd_color']), pointer=(x, state['pm_y']),
                            vdc_sha256=hashlib.sha256(vdc).hexdigest(), attempts=attempt+1)
            (work/f'{label}-{attempt}-vdc-expected.bin').write_bytes(want)
            time.sleep(3)
        raise AssertionError((label, 'VDC differs from the mirrored VIC surface',
                              [i for i in range(16000) if vdc[i] != want[i]][:12], colours))

    wait(lambda: read(0x1c13, 6) == b'KES128' and ready(), 'native boot', 300)
    check('startup: the VDC holds the mirrored desktop', **mirrored('desktop', scene.desktop(usb=True)))
    window = dict(id=1, x=1, y=2, w=28, h=16, title=b'Drive 8', top=0)
    key(ord('8'), quiet=10)
    check('a drive window, mirrored', **mirrored('window', scene.picture([window], {1: scene.ordered(entries, 0)},
                                                                     selected_icon=0, usb=True)))
    key(0x85)
    check('an open drop-down menu (drawn in the AES event loop), mirrored', **mirrored('menu'))
    key(27)
    check('the menu closed, mirrored', **mirrored('menu-closed'))
    key(0x85); key(13)
    check('an alert (Desk:About), mirrored', **mirrored('alert'))
    key(13)
    check('the alert closed, mirrored', **mirrored('alert-closed'))


def show_workflow(mon, seconds, report, save):
    """No checks beyond GEMDESK running: a person looks at the screens."""
    def read(address, count=1):
        return bytes(mon.read_mem(address, address+count-1))
    gemdesk = (IMAGES/'gemdesk.prg').read_bytes()[2:34]
    wait(lambda: read(0x1c13, 6) == b'KES128' and read(0x3d60, 32) == gemdesk and read(0x3d12) == b'\1',
         'GEMDESK running', 300)
    print(f'SHOW: GEMDESK is running; look for {seconds} seconds', flush=True)
    report['shown_seconds'] = seconds; save()
    time.sleep(seconds)
    print('SHOW: done; restoring', flush=True)


def mouse_workflow(mon, work, entries, report, save):
    """A person uses the 1351; each step waits (5 minutes at most) for what the
    pointer module, GEMDESK and the screen must show, and says what to do next."""
    capture = HeldCapture(mon, work)
    report['captures'] = capture.records

    def read(address, count=1):
        return bytes(mon.read_mem(address, address+count-1))

    def sym(name): return lst_symbol('native-desktop/gemdesk', name)

    def ready(): return read(0x3d12) == b'\1' and read(0xd0, 2) == bytes(2)

    def pointer():
        return int.from_bytes(read(sym('pm_x'), 2), 'little'), read(sym('pm_y'))[0], read(sym('pm_buttons'))[0]

    def step(text):
        print('MOUSE:', text, flush=True)
        report.setdefault('prompts', []).append(text); save()

    def check(name, **extra):
        report['checks'].append(dict(name=name, **extra)); save()
        print('PASS:', name, flush=True)

    def until(predicate, label, seconds=300, every=0.5):
        deadline = time.monotonic()+seconds
        while not predicate():
            assert time.monotonic() < deadline, label
            time.sleep(every)

    def screen(label):
        got = b''.join(capture.capture(f'{label}-{offset:04x}', address=0xc000+offset, count=min(2000, 9216-offset))
                       for offset in range(0, 9216, 2000))
        (work/f'{label}.surface').write_bytes(got)
        return got

    def oracle(picture):
        want = bytearray(picture)
        want[8000:8128] = pointer_shape(); want[9208:9210] = b'\x7d\x7e'
        return bytes(want)

    def settled(want, label, attempts=4):
        for attempt in range(attempts):
            got = screen(f'{label}-{attempt}')
            if got == want:
                return hashlib.sha256(got).hexdigest()
            time.sleep(3)
        raise AssertionError((label, [(i, a, b) for i, (a, b) in enumerate(zip(got, want)) if a != b][:12]))

    wait(lambda: read(0x1c13, 6) == b'KES128' and ready(), 'native boot', 300)
    check('GEMDESK is up', surface_sha256=settled(oracle(scene.desktop(usb=True)), 'desktop'))
    start = pointer(); report['pointer_start'] = start; save()

    samples = report.setdefault('pointer_samples', [])
    shown = [None]

    def sprite():
        """Where the VIC draws the arrow: sprite 0, minus the pointer module's offsets."""
        v = read(0xd000, 17)
        return v[0] | (v[16] & 1) << 8, v[1]

    def reach(test, label):
        def seen():
            x, y, b = pointer(); sx, sy = sprite()
            samples.append((round(time.monotonic(), 2), x, y, b, sx, sy))
            if shown[0] is None or abs(x-shown[0][0]) + abs(y-shown[0][1]) >= 12:
                print(f'MOUSE-POS pm=({x},{y}) sprite=({sx-24},{sy-50}) buttons={b}', flush=True)
                shown[0] = (x, y)
            return test(x, y)
        until(seen, label, seconds=600)
        save()
        return samples[-1]

    step('move the pointer to the TOP-LEFT corner of the screen')
    corner = reach(lambda x, y: x <= 8 and y <= 8, 'top-left corner')
    step('now the BOTTOM-RIGHT corner')
    far = reach(lambda x, y: x >= 311 and y >= 191, 'bottom-right corner')
    assert far[1] <= 319 and far[2] <= 199, 'the pointer is clamped to the screen'
    check('the 1351 moves the pointer across the whole screen',
          top_left=corner[1:3], bottom_right=far[1:3], samples=len(samples))

    step('DOUBLE-CLICK the Boot drive icon (top right)')
    until(lambda: read(sym('gm_win_handle')) != b'\0' and ready(), 'a window opened')
    ordered = scene.ordered(entries, 0)
    window = dict(id=1, x=1, y=2, w=28, h=16, title=b'Drive 8', top=0)
    check('a double-click on the Boot icon opens drive 8',
          surface_sha256=settled(oracle(scene.picture([window], {1: ordered}, selected_icon=0, usb=True)), 'opened'))

    step('DRAG the window by its title bar to another place, then let go')
    candidates = [(x, y) for y in range(1, 25-16+1) for x in range(0, 40-28+1) if (x, y) != (1, 2)]

    def moved():
        until(lambda: pointer()[2] != 0, 'button pressed on the title bar', every=0.05)
        until(lambda: pointer()[2] == 0 and ready(), 'button released', every=0.1)
        got = screen('drag')
        for x, y in candidates:
            if got == oracle(scene.picture([dict(window, x=x, y=y)], {1: ordered}, selected_icon=0, usb=True)):
                return x, y
        step('the window has not moved yet: drag it by the title bar')
        return None
    place = None
    deadline = time.monotonic()+300
    while place is None:
        assert time.monotonic() < deadline, 'window moved'
        place = moved()
    window.update(x=place[0], y=place[1])
    check('dragging the title bar moves the window; the screen matches the oracle at its new place',
          x=place[0], y=place[1])

    step('CLICK the close box (top-left corner of the window)')
    until(lambda: read(sym('gm_win_handle')) == b'\0' and ready(), 'the window closed')
    got = screen('closed')
    shown = [label for label, selected in (('icon selected', 0), ('nothing selected', None))
             if got == oracle(scene.desktop(selected=selected, usb=True))]
    assert shown, 'the desktop after closing matches neither oracle'
    check('the close box closes the window; the desktop matches the oracle', state=shown[0])
    step('done: thank you. The machine is being put back now.')


if __name__ == '__main__':
    main()
