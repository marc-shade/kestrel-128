"""Paint, the Claude landing page, Ultimate controls and a Sheet save on the
reference C128, after the shared native desktop workflow.

Drives A and B are recorded. B must be enabled as a 1541 on IEC 9 with no
image. A private copy of the native desktop disk is mounted read-only on A
and a private blank data D64 read-write on B. The shared desktop workflow
(hw_native_desktop_check.run_native_workflow) runs with these additional apps,
keyboard only (the 1351 is never moved):

  Paint     the new canvas (bitmap, banked picture, VDC mirror), three
            keyboard edits checked against a model of the picture, then the
            discard prompt and D back to the desktop
  Claude    the landing page (VIC bitmap, retained 80-column terminal model,
            VDC mirror) without opening the modem, F8 back to the desktop;
            VDC font, NMI vector and NMI gate as before the launch
  Controls  the panel's Drives page against an inventory built from the
            Ultimate's REST drive list (not the app's own UCI replies); the
            Info page has no independent hardware reference and is only
            checked where the caller supplies one (VICE: no cartridge)
  Sheet     12, 30, =A1+B1, Save As BUDGET on device 9; after the session the
            retrieved drive-B image must hold exactly that workbook file

Afterwards both drives get their original image and mode back, both uploads
are retrieved and deleted, and the C128 is reset (hw_session.py).
tests/ci_native_apps_iec.py runs the same app workflow in VICE.
"""
import binascii
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from hw_native_desktop_check import run_native_workflow, idle_admission, sheet_symbol
from native_capture import ROOT, NativeCapture
from native_mode_capture import NativeModeCapture
from native_vdc_check import capture_frame as vdc_frame
from native_claude_check import landing_screen, capture_frame as claude_frame
from native_controls_check import panel_screen
from native_controls_scene import surface as controls_surface, drive_body as graphical_drives
from native_suite_workflow import info_body, drive_body
from native_files_check import exact_disk_files
from paint_scene import surface as paint_surface, MESSAGES as PAINT_MESSAGES
from launcher_scene import pointer_shape
from src.native.graphics.font import font
from hwlib import lst_symbol

BLANK_PICTURE = bytes(8192)+b'\x10'*1024
# The UCI drive type codes (Ultimate firmware c1541.h; NATIVE-ULTIMATE-CONTROLS.md).
UCI_DRIVE_TYPES = {'1541': 0, '1571': 1, '1581': 2}


def expected_workbook():
    """The BUDGET file tests/ci_native_sheet_iec.py expects for 12, 30, =A1+B1."""
    records = bytearray(8192)
    for index, text in {0: b'12', 1: b'30', 2: b'=a1+b1'}.items():
        records[index*32:index*32+len(text)] = text
    header = b'USHT\1\10\40\40\0\40'+binascii.crc_hqx(records, 65535).to_bytes(2, 'little')+bytes(4)
    return bytes(records), header+bytes(records)


def paint_edits():
    """Keyboard-only Paint edits (tests/ci_native_paint_gui.py, keyboard case)
    and the picture and cursor state each must leave."""
    first = bytearray(BLANK_PICTURE); first[0] = 128           # pen at (0,0), ink 1
    second = bytearray(first); second[0] |= 64; second[8192] = 0x20   # right, ink 2, pen at (1,0)
    return [('paint-pen-origin', b' ', dict(x=0, y=0, color=1), bytes(first)),
            ('paint-ink2-right', bytes([0x1d, ord('+'), 32]), dict(x=1, y=0, color=2), bytes(second)),
            ('paint-undo', b'U', dict(x=1, y=0, color=2), bytes(first))]


def rest_drive_reference(drives):
    """Drive inventory replies predicted from the Ultimate's REST drive list.

    The reference machine answers the UCI inventory in the documented short
    form: a count of every listed drive (4) with only the A and B records
    (NATIVE-ULTIMATE-CONTROLS.md, 'observed count=4, length=7'); the app then
    needs both power replies to agree. Each record (type, IEC, power) comes
    from REST: type from the drive mode, IEC from bus_id, power from enabled.
    """
    names = list(drives)
    if names[:2] != ['a', 'b']:
        raise RuntimeError(f'REST does not list drives A and B first: {names}')
    records = b''
    reference = {}
    for slot, name in enumerate(('a', 'b')):
        record = drives[name]
        if record.get('type') not in UCI_DRIVE_TYPES:
            raise RuntimeError(f'drive {name} mode {record.get("type")!r} has no independent UCI type code')
        records += bytes([UCI_DRIVE_TYPES[record['type']], record['bus_id'], int(bool(record['enabled']))])
        reference[f'power-{slot}'] = dict(ok=True, data_hex=(b'on' if record['enabled'] else b'off').hex(),
                                         dos=0, status='')
    reference['drives'] = dict(ok=True, data_hex=(bytes([len(names)])+records).hex(), dos=0, status='')
    return reference


def native_apps(mon, capture, work, report, save, *, kernel_prefix='native-desktop',
                controls_reference, info_reference=False):
    """The additional_apps callable for run_native_workflow.

    controls_reference: the UCI replies drive_body/info_body expect (VICE:
    native_suite_workflow.absent_reference(); hardware: rest_drive_reference).
    info_reference=True also checks the Info page against it."""
    modes = NativeModeCapture(mon, work, quiet=capture.quiet, kernel_prefix=kernel_prefix, batch=capture.batch)
    report['apps_mode_captures'] = modes.records
    rows = report.setdefault('apps', dict(paint=[], claude=[], controls=[], sheet=[]))
    names = iter(range(1 << 30))

    def app_read(read, address, count=1):
        # App RAM at $4000 and above lies under ROM in the IRQ/KERNAL map; a
        # host read there can return ROM, so read it on the C128.
        if address+count <= 0x4000:
            return read(address, count)
        return capture.capture(f'app-read-{next(names)}', address=address, count=count)

    def symbol(app, name):
        return lst_symbol(f'{kernel_prefix}/{app}', name)

    def value(read, app, name, size=1):
        return int.from_bytes(app_read(read, symbol(app, name), size), 'little')

    def span(label, address, count, mode=0, bank=0):
        data = b''.join(capture.capture(f'{label}-{offset:04x}', mode=mode, bank=bank, address=address+offset,
                        count=min(2000, count-offset)) for offset in range(0, count, 2000))
        (work/(label+'.bin')).write_bytes(data)
        return data

    def display(label, app, read, *, sprites=None):
        registers = modes.snapshot(label+'-mode')
        assert registers['vic_d011'] & 0x7f == 0x3b, (label, 'bitmap mode', registers)
        if sprites is None:
            sprites = 3 if value(read, app, 'pm_seen') else 0
        assert registers['vic_sprites'] == sprites, (label, 'pointer sprites', registers['vic_sprites'], sprites)
        return registers

    def paint_frame(read, label, picture, *, x=0, y=0, color=1, dirty=False, mode=0, focus=23):
        app = 'paint'
        state = {name: value(read, app, name) for name in
                 ('pa_bitmap', 'pa_picker_active', 'pa_labels_stale', 'pd_dirty', 'pa_mode', 'pa_status',
                  'pd_y', 'pd_pen', 'pd_color', 'ui_selected', 'pa_view_x', 'pa_view_y', 'pf_length')}
        state['pd_x'] = value(read, app, 'pd_x', 2)
        wanted_state = dict(pa_bitmap=1, pa_picker_active=0, pa_labels_stale=0, pd_dirty=int(dirty), pa_mode=mode,
                            pa_status=0, pd_x=x, pd_y=y, pd_pen=1, pd_color=color, ui_selected=focus,
                            pa_view_x=0, pa_view_y=0, pf_length=0)
        if mode == 1:   # the prompt's action: 1 close (0 until a prompt is first opened)
            state['pa_action'] = value(read, app, 'pa_action'); wanted_state['pa_action'] = 1
        assert state == wanted_state, (label, 'Paint state', state, wanted_state)
        tag = value(read, app, 'pd_handles')
        allocation = read(0x3c00+(tag-1)*8, 8)
        assert allocation[:2] == bytes([32, 1]) and allocation[3] == 36, (label, 'picture allocation', allocation.hex())
        document = span(label+'-picture', allocation[2]*256, 9216, bank=1)
        assert document == picture, (label, 'banked picture',
                                     [(i, a, b) for i, (a, b) in enumerate(zip(document, picture)) if a != b][:16])
        wanted = paint_surface(picture, focus=focus, x=x, y=y, pen=1, color=color, dirty=dirty,
                               message=PAINT_MESSAGES[0], mode=mode, action=1)
        actual = span(label+'-surface', 0xc000, 9216)
        assert actual == wanted, (label, 'Paint bitmap', [(i, a, b) for i, (a, b) in enumerate(zip(actual, wanted)) if a != b][:16])
        mirror = vdc_frame(capture, read, None, work, label, 0, surface_data=actual, image_prefix=f'{kernel_prefix}/paint')
        # Paint shows its cursor sprite on the canvas page even with no mouse
        # (paint/input.inc pa_cursor); the discard prompt shows it only with one.
        seen = value(read, app, 'pm_seen')
        registers = display(label, app, read, sprites=3 if seen or mode == 0 else 0)
        rows['paint'].append(dict(label=label, state=state, picture_sha256=hashlib.sha256(document).hexdigest(),
                                  surface_sha256=hashlib.sha256(actual).hexdigest(), registers=registers, vdc=mirror))
        save(); print('Verified Paint picture, bitmap and VDC:', label, flush=True)

    def sheet_frame(read, label, values):
        # Sheet draws its 40x25 cell grid as character cells on the bitmap.
        assert capture.capture(label+'-bitmap-active', address=sheet_symbol('sg_bitmap'), count=1) == b'\1'
        cells = capture.capture(label+'-values', address=sheet_symbol('sh_values'), count=4*len(values))
        assert cells == b''.join(n.to_bytes(4, 'little') for n in values), (label, 'Sheet values', cells.hex())
        chars = capture.capture(label+'-chars', address=sheet_symbol('sg_chars'), count=1000)
        colors = capture.capture(label+'-colors', address=sheet_symbol('sg_colors'), count=1000)
        actual = span(label+'-surface', 0xc000, 9216)
        glyphs = font(); wanted = bytearray(9216)
        for cell, code in enumerate(chars):
            wanted[cell*8:cell*8+8] = glyphs[(code-32)*8:(code-31)*8]
        wanted[8192:9192] = colors; wanted[8000:8128] = pointer_shape(); wanted[9208:9210] = b'\x7d\x7e'
        assert actual == bytes(wanted), (label, 'Sheet bitmap')
        mirror = vdc_frame(capture, read, None, work, label, 0, surface_data=actual, image_prefix=f'{kernel_prefix}/sheet-gui')
        registers = display(label, 'sheet-gui', read)
        rows['sheet'].append(dict(label=label, values=list(values), registers=registers,
                                  surface_sha256=hashlib.sha256(actual).hexdigest(), vdc=mirror))
        save(); print('Verified Sheet values, bitmap and VDC:', label, flush=True)

    def workbook_sources(read, label):
        token = capture.capture(label+'-handle', address=sheet_symbol('wb_handle'), count=4)
        record = read(0x3c00+(token[0]-1)*8, 8)
        assert record[:2] == bytes([32, 1]) and record[3] == 32 and record[4:7] == token[1:], (label, record.hex())
        return span(label+'-sources', record[2]*256, 8192, bank=1)

    def controls_panel(read, label, body, page):
        assert value(read, 'controls', 'ug_bitmap') == 1, (label, 'Ultimate controls are not graphical')
        graphical, count = body, 0
        if page == 0:
            graphical = info_body(controls_reference, 4, model_limit=33)
        elif page == 1:
            graphical, count = graphical_drives(body)
        expected = controls_surface(graphical, page=page, focus=page, count=count)
        actual = span(label+'-surface', 0xc000, 9216)
        assert actual == expected, (label, 'Ultimate controls bitmap')
        mirror = vdc_frame(capture, read, None, work, label, page, surface_data=actual, image_prefix=f'{kernel_prefix}/controls')
        registers = display(label, 'controls', read)
        held = dict(ud_count=value(read, 'controls', 'ud_count'), ud_partial=value(read, 'controls', 'ud_partial'),
                    ud_verified=value(read, 'controls', 'ud_verified'),
                    ud_records=app_read(read, symbol('controls', 'ud_records'), 12).hex())
        rows['controls'].append(dict(label=label, page=page, body=body, graphical_body=graphical, drive_count=count,
                                     console_oracle_sha256=hashlib.sha256(panel_screen(40, body, page=page, focus=page)).hexdigest(),
                                     app_held_inventory=held, surface_sha256=hashlib.sha256(actual).hexdigest(),
                                     registers=registers, vdc=mirror))
        save(); print('Verified Ultimate controls bitmap and VDC:', label, flush=True)

    def extra(*, key, screens, desktop, read):
        # Paint (desktop card P): new canvas, keyboard edits, discard prompt.
        key(ord('P'), io=True)
        picture = BLANK_PICTURE
        paint_frame(read, 'paint-new', picture)
        for label, keys, state, picture in paint_edits():
            for code in keys:
                key(code)
            paint_frame(read, label, picture, dirty=True, **state)
        key(27)
        paint_frame(read, 'paint-discard-prompt', picture, dirty=True, mode=1, focus=25, **state)
        key(ord('D'), io=True)
        desktop('desktop-after-paint', 5)

        # Claude (desktop card A): the landing page, never the modem.
        labels = {m[2]: int(m[1], 16) for m in re.finditer(r'^al ([0-9A-Fa-f]+) \.(\S+)',
                  (ROOT/f'target/{kernel_prefix}/claude.lbl').read_text(), re.M)}
        original = dict(font=span('claude-font-before', 0x3000, 4096, 1), nmi=span('claude-nmi-before', 0x318, 2),
                        gate=span('claude-gate-before', 0x3d3e, 2))
        key(ord('A'), io=True)
        actual, landing = claude_frame(capture, lambda address, count=1: app_read(read, address, count), labels, work,
                                       'claude-landing', panel=landing_screen(40), terminal_chars=landing_screen(80))
        assert app_read(read, labels['cg_vdc_owned']) == b'\1'
        assert app_read(read, labels['serialOwned']) == b'\0', 'Claude opened the serial port without Return'
        landing['vdc'] = vdc_frame(capture, read, None, work, 'claude-landing', 0, surface_data=actual,
                                   image_prefix=f'{kernel_prefix}/claude-gui')
        rows['claude'].append(landing); save()
        key(0x8c, io=True)   # F8: desktop
        desktop('desktop-after-claude', 4)
        for name, (address, count, mode) in dict(font=(0x3000, 4096, 1), nmi=(0x318, 2, 0), gate=(0x3d3e, 2, 0)).items():
            assert span(f'claude-{name}-after', address, count, mode) == original[name], ('Claude left', name, 'changed')
        rows['claude'][-1]['restored'] = sorted(original); save()
        print('Verified Claude landing page and clean return', flush=True)

        # Ultimate controls (desktop card U): Drives page.
        key(ord('U'), io=True)
        if info_reference:
            controls_panel(read, 'controls-info', info_body(controls_reference), 0)
        else:
            assert value(read, 'controls', 'ug_bitmap') == 1
            rows['controls'].append(dict(label='controls-info', verified=False,
                reason='the Info page shows UCI identity replies with no independent hardware reference')); save()
        key(ord('D'))
        controls_panel(read, 'controls-drives', drive_body(controls_reference), 1)
        key(27, io=True)
        desktop('desktop-after-controls', 3)

        # Sheet (desktop card S): workbook saved to device 9 and verified.
        records, _ = expected_workbook()
        key(ord('S'), io=True)
        sheet_frame(read, 'sheet-save-new', (0, 0, 0))
        for code in b'12\r\x1d30\r\x1d=A1+B1\r':
            key(code)
        sheet_frame(read, 'sheet-save-calculated', (12, 30, 42))
        assert workbook_sources(read, 'sheet-save-calculated') == records
        key(0x87); key(0x86)   # Save As; data drive 8 -> 9 (tests/ci_native_sheet_iec.py)
        assert capture.capture('sheet-save-device', address=sheet_symbol('wb_device'), count=1) == b'\x09'
        for code in b'BUDGET':
            key(code)
        key(13, io=True)
        flags = capture.capture('sheet-save-dirty', address=sheet_symbol('wb_dirty'), count=1)
        flags += capture.capture('sheet-save-error', address=sheet_symbol('wb_error'), count=1)
        assert flags == bytes(2), ('Sheet save', 'wb_dirty/wb_error', flags.hex())
        sheet_frame(read, 'sheet-saved', (12, 30, 42))
        assert workbook_sources(read, 'sheet-saved') == records
        key(27, io=True)
        desktop('desktop-after-sheet-save', 6)
        assert all(item['restored'] for item in modes.records)
        report['apps_passed'] = True; save()
    return extra


def verify_data_disk(image, blank, work, report, save):
    """The only file on the closed data D64 is BUDGET with the expected bytes,
    by an independent host extraction and by c1541."""
    _, wanted = expected_workbook()
    output = work/'data-readback.d64'
    try:
        output.write_bytes(image)
        files = exact_disk_files(image)
        expected = dict(exact_disk_files(blank)); expected[b'BUDGET'] = (1, wanted)
        assert files == expected, ('data disk files', sorted(files))
        exported = work/'budget-readback.usht'
        subprocess.run(['c1541', '-attach', str(output), '-read', 'budget,s', str(exported)], check=True, capture_output=True)
        assert exported.read_bytes() == wanted, 'c1541 BUDGET differs'
        report['independent_readback'] = dict(bytes=len(image), sha256=hashlib.sha256(image).hexdigest(),
            files=[name.decode('latin1') for name in files], budget_bytes=len(wanted),
            budget_sha256=hashlib.sha256(wanted).hexdigest())
    except BaseException as error:
        report['readback_error'] = str(error)
        raise
    finally:
        save()


def blank_data_disk(path):
    subprocess.run(['c1541', '-format', 'kestrel data,01', 'd64', str(path)], check=True, capture_output=True)
    return path.read_bytes()


def run(ult, *, dos_contexts=False, apps_only=False):
    from hw_native_check import hashes, quiet_boot
    from hw_session import HardwareSession
    from hw_dos_context import DosContexts
    from native_capture_transport import PausedHardwareMonitor
    work = Path(tempfile.mkdtemp(prefix='kestrel-hardware-native-apps-'))
    print(f'Native apps hardware evidence: {work}', flush=True)
    disk = work/'native.d64'; shutil.copyfile(ROOT/'target/native-desktop/kestrel.d64', disk)
    data_disk = work/'data.d64'; blank = blank_data_disk(data_disk)
    report = dict(passed=False, physical_hardware_io=True, build=hashes(), events=[], desktops=[], screens=[],
                  native_disk_sha256=hashlib.sha256(disk.read_bytes()).hexdigest(),
                  data_disk_sha256=hashlib.sha256(blank).hexdigest(),
                  uncertain_host_writes=ult.uncertain_writes, host_connect_failures=ult.connect_failures,
                  host_control_requests=ult.control_requests, host_upload_checks=ult.upload_checks,
                  quiet_seconds=dict(boot=240, key=4, io=30, capture=2, poll=2),
                  # apps_only: boot, then straight to the apps below; the Calculator, Editor
                  # and Files steps are --native-desktop's and are skipped (a shorter session).
                  apps_only=apps_only)
    def save(): (work/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    ult.record_event = save; save()
    mon = PausedHardwareMonitor(ult)
    def paused_read(address, count):
        data = bytes(mon.read_mem(address, address+count-1)); mon.resume(); return data
    capture = NativeCapture(mon, work, quiet=2, kernel_prefix='native-desktop',
                            batch=idle_admission(mon.paused, paused_read, report.setdefault('capture_admissions', [])))
    report['paused_capture_batches'] = mon.batches
    report['ram_write_receipts'] = getattr(ult, 'ram_write_receipts', [])
    report['captures'] = capture.records
    session = HardwareSession(ult, work, report, save, drives=('a', 'b'),
                              dos_contexts=DosContexts(ult, work) if dos_contexts else None)
    report['stage'] = 'preflight'; save()
    before = session.snapshot()
    assert before['a']['enabled'] and before['a']['bus_id'] == 8
    assert before['b']['enabled'] and before['b']['bus_id'] == 9 and before['b']['type'] == '1541'
    assert not before['b']['image_file'], 'the native apps check requires an initially empty drive B'
    (work/'ultimate-version.json').write_text(ult.version())
    def body():
        try:
            report['data_disk_path'] = session.upload(blank, 'b', 'd64', 'readwrite', retrieve=True); save()
            report['native_disk_path'] = session.upload(disk.read_bytes(), 'a', 'd64', 'readonly', retrieve=True); save()
            drives = session.drives('controls-reference')
            reference = rest_drive_reference(drives)
            report['controls_reference'] = dict(source='REST /v1/drives after both uploads', drives=drives, replies=reference)
            report['stage'] = 'native-boot'; save()
            ult.reset(); quiet_boot('Native apps boot', 240)
            run_native_workflow(mon, capture, work, disk, report, save, io_quiet=30, prelude=not apps_only,
                additional_apps=native_apps(mon, capture, work, report, save, controls_reference=reference))
        except BaseException as error:
            report['native_error'] = str(error); save()
            raise
    try:
        session.run(body)
    finally:
        report['images_unchanged'] = report['build'] == hashes(); save()
    verify_data_disk(session.retrieved[report['data_disk_path']], blank, work, report, save)
    assert report['images_unchanged'] and not report['uncertain_host_writes']
    report['passed'] = True; save()
    print(f'HW-NATIVE-APPS{"-ONLY" if apps_only else ""} PASS; Paint, Claude landing, controls drives and verified Sheet save; '
          f'drives restored, uploads deleted; {work}', flush=True)
