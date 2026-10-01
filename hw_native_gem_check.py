#!/usr/bin/env python3
"""Boot the GEM profile (gem.d81) on the reference C128 through the Ultimate
II+ and compare GEMDESK's screens with the CPU-test oracles.

The Ultimate's DOS answers GEMDESK's identify query here, so every desktop
oracle includes the USB icon (VICE has no Ultimate and shows none).

A private copy of gem.d81 (plus the NOTE and PICTURE documents the VICE suite
uses) is mounted read-only on drive A in 1581 mode and the machine is reset.
The run follows tests/ci_native_gemdesk_vice.py: the desktop, drive 8's
window, Calculator and back, a SEQ document in the Editor and back, a UPNT
picture in Paint. Screens are read by the CPU capture probe (NativeCapture);
no video signal is captured.

Afterwards drive A gets its original mode and image back (it is unmounted if
it had none), the upload is deleted over FTP and its absence confirmed, and
the C128 is reset (hw_session.py). Nothing on the machine's own disks is
written.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT/'tests')]
from hw_session import HardwareSession  # noqa: E402
from hw_dos_context import DosContexts  # noqa: E402
from hw_storage_check import HardwareMonitor  # noqa: E402
from hw_ultimate_check import VerifiedUltimate, resolve_host  # noqa: E402
from hwlib import lst_symbol  # noqa: E402
from native_capture import wait  # noqa: E402
import native_gemdesk_scene as scene  # noqa: E402
from launcher_scene import pointer_shape  # noqa: E402
from native_editor_scene import surface as editor_surface  # noqa: E402
from paint_scene import surface as paint_surface, MESSAGES as PAINT_MESSAGES  # noqa: E402
from native_paint_format import encode as paint_encode  # noqa: E402
from ci_native_gemdesk_vice import d81_entries, NOTE, PICTURE  # noqa: E402

IMAGES = ROOT/'target/native-desktop'


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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', help='the Ultimate II+ address (default: $KESTREL_ULTIMATE_HOST)')
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--mouse', action='store_true',
                        help='interactive: a person moves and clicks the 1351 while this observes')
    parser.add_argument('--mirror', action='store_true',
                        help='check the 80-column mirror byte for byte (desktop, window, menu, alert)')
    parser.add_argument('--show', type=int, metavar='SECONDS',
                        help='boot and leave GEMDESK running this long for a person to look, then restore')
    parser.add_argument('--image', type=Path, help='gem.d81 to boot instead of the committed target (hash recorded)')
    parser.add_argument('--screens', type=Path, metavar='DIR',
                        help='README screenshots of GEMDESK and the Ultimate app into DIR, then restore')
    parser.add_argument('--sample-ready', type=int, metavar='N',
                        help='diagnostic: after boot, sample N_READY ($3d12) N times over DMA and record its duty cycle')
    args = parser.parse_args()
    args.host = resolve_host(args.host)
    work = Path(tempfile.mkdtemp(prefix='kestrel-hardware-gem-'))
    print('GEM hardware evidence:', work, flush=True)
    disk = work/'gem.d81'
    shutil.copyfile(args.image or IMAGES/'gem.d81', disk)
    images = json.loads((IMAGES/'images.json').read_text())
    if args.image is None:
        assert hashlib.sha256(disk.read_bytes()).hexdigest() == images['gem.d81']['sha256'], 'gem.d81 differs from images.json'
    else:
        images['gem.d81']['sha256'] = hashlib.sha256(disk.read_bytes()).hexdigest()
    for name, data in (('note,s', NOTE), ('picture,s', paint_encode(PICTURE))):
        (work/'doc.bin').write_bytes(data)
        subprocess.run(['c1541', '-attach', str(disk), '-write', str(work/'doc.bin'), name], check=True, capture_output=True)
    entries = d81_entries(disk.read_bytes())

    ult = VerifiedUltimate(args.host)
    report = dict(passed=False, physical_hardware_io=True, host=args.host, work=str(work),
                  gem_d81_sha256=images['gem.d81']['sha256'], private_disk_sha256=hashlib.sha256(disk.read_bytes()).hexdigest(),
                  checks=[], events=[], control_requests=ult.control_requests, upload_checks=ult.upload_checks,
                  uncertain_writes=ult.uncertain_writes)

    def save(): args.report.write_text(json.dumps(report, indent=2)+'\n')
    ult.record_event = save

    mon = HardwareMonitor(ult)
    session = HardwareSession(ult, work, report, save, drives=('a',), dos_contexts=DosContexts(ult, work))
    before = session.snapshot(); report['drive_a_before'] = before['a']; save()
    assert before['a']['enabled'] and before['a']['bus_id'] == 8
    report['ultimate_version'] = json.loads(ult.version())

    def body():
        try:
            uploaded = session.upload(disk.read_bytes(), 'a', 'd81', 'readonly')
            report['upload_path'] = uploaded; save()
            mounted = session.drives('native')['a']; report['drive_a_native'] = mounted; save()
            assert mounted['type'] == '1581' and ult.mounted_path('a') == uploaded
            ult.reset()
            print('Boot: 150 seconds without RAM DMA while the kernel and GEMDESK load', flush=True)
            time.sleep(150)
            if args.sample_ready:
                def peek(address, count=1): return bytes(mon.read_mem(address, address+count-1))
                gemdesk = (IMAGES/'gemdesk.prg').read_bytes()[2:34]
                started, polls = time.monotonic(), 0
                while not (peek(0x1c13, 6) == b'KES128' and peek(0x3d60, 32) == gemdesk and peek(0x3d12) == b'\1'):
                    polls += 1
                    assert time.monotonic()-started < 300, 'GEMDESK never published N_READY within 300 s'
                    time.sleep(0.1)
                first_ready = round(time.monotonic()-started+60, 1)
                samples = []
                sampling = time.monotonic()
                for _ in range(args.sample_ready):
                    samples.append(peek(0x3d12)[0])
                    time.sleep(0.02)
                report['ready_samples'] = dict(count=len(samples), ready=samples.count(1),
                                               values=sorted(set(samples)), sequence=bytes(samples).hex(),
                                               first_ready_after_reset_s=first_ready, polls_before_ready=polls,
                                               sampling_seconds=round(time.monotonic()-sampling, 1))
                print('N_READY duty:', samples.count(1), '/', len(samples), flush=True)
            elif args.show:
                show_workflow(mon, args.show, report, save)
            elif args.screens:
                args.screens.mkdir(parents=True, exist_ok=True)
                screens_workflow(mon, work, entries, report, save, args.screens)
            elif args.mirror:
                mirror_workflow(mon, work, entries, report, save)
            else:
                (mouse_workflow if args.mouse else run_workflow)(mon, work, entries, report, save)
            report['workflow_passed'] = True; save()
        except BaseException as caught:
            report['error'] = f'{type(caught).__name__}: {caught}'; save()
            raise
    session.run(body)
    assert not ult.uncertain_writes
    report['passed'] = True; save()
    print('HW-GEM PASS:', work, flush=True)


def run_workflow(mon, work, entries, report, save):
    def watch(predicate, label, seconds):
        started, last = time.monotonic(), None
        while time.monotonic()-started < seconds:
            state = (read(0x3d60, 32).hex(), read(0x3d20)[0], read(0x3d12)[0], read(0x3d91)[0], read(0xd0)[0])
            if state != last:
                entry = dict(label=label, t=round(time.monotonic()-started, 1), header=state[0], current=state[1],
                             ready=state[2], file_service=state[3], keys_pending=state[4])
                report.setdefault('switch_log', []).append(entry); save(); last = state
                print('  ', label, entry['t'], bytes.fromhex(state[0])[12:32], state[1:], flush=True)
            if predicate():
                return
            time.sleep(0.5)
        raise AssertionError(label)
    capture = HeldCapture(mon, work)
    report['captures'] = capture.records

    def read(address, count=1):
        return bytes(mon.read_mem(address, address+count-1))

    def ready(): return read(0x3d12) == b'\1' and read(0xd0, 2) == bytes(2)

    def check(name, **extra):
        report['checks'].append(dict(name=name, **extra)); save()
        print('PASS:', name, flush=True)

    def key(value, quiet=4):
        wait(ready, 'native input ready', 300)
        previous = int.from_bytes(read(0x3d13, 2), 'little')
        mon.write_mem(0x3d12, b'\0'); mon.write_mem(0x34a, bytes([value])); mon.write_mem(0xd0, b'\1')
        start = time.monotonic()
        time.sleep(quiet)                     # no DMA while a key may start a load
        wait(lambda: ready() and int.from_bytes(read(0x3d13, 2), 'little') == (previous+1) & 65535,
             f'key {value:#x}', 600)
        report['events'].append(dict(key=value, seconds=round(time.monotonic()-start, 1))); save()

    def surface(label):
        got = b''.join(capture.capture(f'{label}-{offset:04x}', address=0xc000+offset, count=min(2000, 9216-offset))
                       for offset in range(0, 9216, 2000))
        (work/f'{label}.surface').write_bytes(got)
        return got

    def settled(want, label, attempts=4):
        """Capture until the surface equals the oracle (redraws can trail the key)."""
        for attempt in range(attempts):
            got = surface(f'{label}-{attempt}')
            if got == want:
                return hashlib.sha256(got).hexdigest()
            time.sleep(5)
        (work/f'{label}-expected.bin').write_bytes(want)
        raise AssertionError((label, [(i, a, b) for i, (a, b) in enumerate(zip(got, want)) if a != b][:12]))

    def expect(want, label):
        want = bytearray(want)
        want[8000:8128] = pointer_shape(); want[9208:9210] = b'\x7d\x7e'
        return settled(bytes(want), label)

    wait(lambda: read(0x1c13, 6) == b'KES128' and ready(), 'native boot', 300)
    browse = (IMAGES/'gemdesk.prg').read_bytes()[2:34]
    assert read(0x3d60, 32) == browse, 'GEMDESK is the running app'
    check('boot from gem.d81 on the 1581-mode drive: Kestrel runs GEMDESK',
          surface_sha256=expect(scene.desktop(usb=True), 'desktop'))

    ordered = scene.ordered(entries, 0)
    window = dict(id=1, x=1, y=2, w=28, h=16, title=b'Drive 8', top=0)
    key(ord('8'), quiet=10)
    check('the 8 key lists the D81, sorted by name',
          surface_sha256=expect(scene.picture([window], {1: ordered}, selected_icon=0, usb=True), 'drive-8'), entries=len(entries))

    g = scene.scene.geometry(dict(kind=scene.KIND, x=1, y=2, w=28, h=16))
    names = [e['name'] for e in ordered]

    def select(target, label):
        current = window.get('selected', -1)
        for _ in range(abs(target-current)):
            key(0x11 if target > current else 0x91)
        window['selected'] = target
        window['top'] = min(window['top'], target)
        window['top'] = max(window['top'], target-g['wh']+1)
        expect(scene.picture([window], {1: ordered}, selected_icon=0 if label == 'calc' else None, usb=True), f'{label}-selected')

    select(names.index(b'CALC'), 'calc')
    key(13, quiet=90)
    watch(lambda: read(0x3d60, 32) == (IMAGES/'calc.prg').read_bytes()[2:34], 'Calculator running', 300)
    check('Return launches Calculator through the dispatcher')
    key(27, quiet=60)
    watch(lambda: read(0x3d60, 32) == browse, 'GEMDESK back from Calculator', 300)
    check('leaving Calculator reloads GEMDESK, which reopens its window with the selection',
          surface_sha256=expect(scene.picture([window], {1: ordered}, usb=True), 'back-from-calc'))

    select(names.index(b'NOTE'), 'note')
    key(13, quiet=90)
    editor = (IMAGES/'editor.prg').read_bytes()[2:34]
    watch(lambda: read(0x3d60, 32) == editor and ready(), 'Editor running', 300)
    assert read(0x3d9a) == b'\0', 'the Editor claimed the request'
    editor_fields = ('eg_bitmap', 'eg_started', 'ed_status', 'ed_mode', 'ed_module_kind', 'vd_phase', 'vd_live',
                     'vd_fault', 'bk_state', 'dm_mode', 'dm_lease', 'dm_fault', 'eh_available', 'eg_vdc_attempted')
    editor_state = {n: capture.capture(f'ed-{n}', address=lst_symbol('native-desktop/editor', n), count=1)[0]
                    for n in editor_fields}
    text80 = capture.capture('ed-vdc-text', mode=1, address=0, count=2000)
    report['editor_state'] = editor_state
    report['editor_vdc_text'] = [bytes(c if 32 <= c < 127 else 46 for c in text80[r*80:r*80+80]).decode() for r in range(25)]
    save(); print('  Editor state:', editor_state, flush=True)
    want = editor_surface(NOTE, 0, name='NOTE', device=8, dirty=False, field='NOTE', fmt=2,
                          view=0, horizontal=0, selection=None)
    check('Return on a SEQ file opens it in the Editor: the surface matches the Editor oracle',
          surface_sha256=settled(want, 'editor'))
    key(27, quiet=60)
    watch(lambda: read(0x3d60, 32) == browse, 'GEMDESK back', 300)
    check('leaving the Editor returns to GEMDESK with the document selected',
          surface_sha256=expect(scene.picture([window], {1: ordered}, usb=True), 'back-from-editor'))

    select(names.index(b'PICTURE'), 'picture')
    key(13, quiet=25)
    paint = (IMAGES/'paint.prg').read_bytes()[2:34]
    wait(lambda: read(0x3d60, 32) == paint and ready(), 'Paint running', 180)

    def value(name, n=1):
        # Through the held CPU capture: a direct DMA read of app RAM can land while
        # the AES has bank 1 mapped and return other bytes (seen as x=5616 readings).
        return capture.capture(f'paint-{name}', address=lst_symbol('native-desktop/paint', name), count=n)
    wait(lambda: ready() and read(0x3d91) == b'\0' and value('pa_status')[0] == 2, 'Paint opened the picture', 180)
    assert read(0x3d9a) == b'\0', 'Paint claimed the request'
    tag = value('pd_handles')[0]
    allocation = read(0x3c00+(tag-1)*8, 8)
    assert allocation[:2] == bytes([32, 1]) and allocation[3] == 36, allocation
    document = b''.join(capture.capture(f'paint-document-{offset:04x}', bank=1, address=allocation[2]*256+offset,
                                        count=min(2000, 9216-offset)) for offset in range(0, 9216, 2000))
    (work/'paint-document.bin').write_bytes(document)
    assert document == PICTURE, 'the picture in Paint\'s document allocation'
    name = value('pf_name', value('pf_length')[0])
    assert name == b'PICTURE' and value('pd_dirty')[0] == 0, name
    want = paint_surface(PICTURE, message=PAINT_MESSAGES[2], view_x=value('pa_view_x')[0], view_y=value('pa_view_y')[0],
                         focus=value('ui_selected')[0], x=int.from_bytes(value('pd_x', 2), 'little'), y=value('pd_y')[0],
                         pen=value('pd_pen')[0], color=value('pd_color')[0], dirty=False, mode=value('pa_mode')[0],
                         action=value('pa_action')[0], name=name, caret=value('pa_field_caret')[0],
                         field_view=value('pa_field_view')[0], device=value('pf_device')[0], fmt=value('pf_format')[0])
    check('Return on a UPNT picture opens it in Paint: the banked document and the surface match',
          surface_sha256=settled(want, 'paint'))
    assert all(item.get('restored') for item in capture.records), 'every capture restored its borrowed RAM'



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
