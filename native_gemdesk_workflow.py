"""GEMDESK's keyboard workflow, shared by the VICE test
(tests/ci_native_gemdesk_vice.py, the oracle) and the hardware check
(hw_native_gem_check.py), so both run the identical key sequence against the
identical oracles: the desktop, drive 9 (a 1581 with a D81, detected from its
DOS identity), drive 8, Calculator and back, a SEQ document in the Editor and
back, a USHT workbook in Sheet and back, a UPNT picture in Paint.

The machine object is the one native_aes_workflow describes. usb=True when
the Ultimate's DOS answers GEMDESK's identify query (the real C128): every
desktop oracle then includes the USB icon.
"""
import binascii
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT/'tests')]
import native_gemdesk_scene as scene  # noqa: E402
from launcher_scene import pointer_shape  # noqa: E402
from native_editor_scene import surface as editor_surface  # noqa: E402
from paint_scene import surface as paint_surface, MESSAGES as PAINT_MESSAGES  # noqa: E402
from native_paint_format import encode as paint_encode  # noqa: E402
from hwlib import lst_symbol  # noqa: E402
from native_aes_workflow import expect_surface, ready  # noqa: E402

IMAGES = ROOT/'target/native-desktop'
NOTE = b'GEMDESK opened this SEQ file.\rIt is an Editor document.\r'
PICTURE = (bytes((i*7+i//320) & 255 for i in range(8000))+bytes(192)
           + b'\x61'*1000+b'\x10'*24)     # UPNT keeps 1,000 attributes; Paint's page pads with $10
EDITOR_FIELDS = ('eg_bitmap', 'eg_started', 'ed_status', 'ed_mode', 'ed_module_kind', 'vd_phase', 'vd_live',
                 'vd_fault', 'bk_state', 'dm_mode', 'dm_lease', 'dm_fault', 'eh_available', 'eg_vdc_attempted')


def ledger():
    """A Sheet workbook: A1 7, B1 =a1*6 (docs/NATIVE-SHEET.md)."""
    records = bytearray(8192)
    records[0:1], records[32:37] = b'7', b'=a1*6'
    return (b'USHT\1\10\40\40\0\40'+binascii.crc_hqx(records, 0xffff).to_bytes(2, 'little')
            + bytes(4)+records)


def d81_entries(image):
    """Live directory records of a D81 image, as N_DIRPAGE normalizes them."""
    def sector(t, s):
        at = ((t-1)*40+s)*256
        return image[at:at+256]
    out, t, s, seen = [], 40, 3, set()
    while t and (t, s) not in seen:
        seen.add((t, s))
        data = sector(t, s)
        for i in range(8):
            e = data[i*32:i*32+32]
            kind = e[2] & 7
            if e[2] and kind:
                out.append(dict(name=bytes(e[5:21]).rstrip(b'\xa0'), type=kind,
                                blocks=e[30] | e[31] << 8))
        t, s = data[0], data[1]
    return out


def prepare_disks(work, image=None):
    """The boot disk (a copy of gem.d81, or image, plus the NOTE, LEDGER and
    PICTURE documents) and drive 9's D81 (two files), both built with c1541."""
    work = Path(work)
    disk = work/'gem.d81'
    shutil.copy2(image or IMAGES/'gem.d81', disk)
    for name, data in (('note,s', NOTE), ('picture,s', paint_encode(PICTURE)), ('ledger,s', ledger())):
        (work/'document.seq').write_bytes(data)
        subprocess.run(['c1541', '-attach', str(disk), '-write', str(work/'document.seq'), name],
                       check=True, capture_output=True)
    disk9 = work/'data9.d81'
    subprocess.run(['c1541', '-format', 'data nine,09', 'd81', str(disk9)], check=True, capture_output=True)
    for name, data in (('alpha,s', b'A'*300), ('bravo,p', b'\x01\x08'+bytes(600))):
        (work/'nine.bin').write_bytes(data)
        subprocess.run(['c1541', '-attach', str(disk9), '-write', str(work/'nine.bin'), name],
                       check=True, capture_output=True)
    return dict(disk=disk, disk9=disk9, entries=d81_entries(disk.read_bytes()),
                entries9=d81_entries(disk9.read_bytes()))


def gemdesk_workflow(m, disks, check, report, *, usb=False, diagnose=None):
    """Cold-booted gem.d81 at GEMDESK's input wait. diagnose(name), when
    given, records extra state at 'editor' (no effect on the verdict)."""
    entries, entries9 = disks['entries'], disks['entries9']

    def expect(want, label, seconds=120):
        want = bytearray(want)
        want[8000:8128] = pointer_shape(); want[9208:9210] = b'\x7d\x7e'
        return expect_surface(m, bytes(want), label, seconds)

    def running(image):
        header = (IMAGES/image).read_bytes()[2:34]
        return lambda: m.read(0x3d60, 32) == header and ready(m)

    gemdesk = running('gemdesk.prg')
    m.wait(lambda: m.read(0x1c13, 6) == b'KES128' and ready(m), 'native boot', 300)
    m.wait(gemdesk, 'GEMDESK is the running app', 300)
    check('cold boot of gem.d81: GEMDESK loads AESVC.PRG; the desktop matches the CPU oracle exactly',
          **expect(scene.desktop(usb=usb), 'desktop'))

    w9 = dict(id=1, x=1, y=2, w=28, h=16, title=b'Drive 9', top=0)
    m.key(ord('9'), io='scan')
    drive9 = expect(scene.picture([w9], {1: scene.ordered(entries9, 0)}, selected_icon=1, usb=usb), 'drive-9')
    detected = m.value(lst_symbol('native-desktop/gemdesk', 'gm_dev_format'))[0]
    assert detected == 2, ('the 1581 ROM answered UI; D81 expected', detected)
    m.key(23)                                   # Ctrl-W: File:Close
    closed = expect(scene.desktop(selected=1, usb=usb), 'drive-9-closed')
    check('drive 9, a 1581 with a D81, is detected from its DOS identity (UI) and listed as a D81',
          entries=len(entries9), listing=drive9, closed=closed)

    ordered = scene.ordered(entries, 0)
    names = [e['name'] for e in ordered]
    window = dict(id=1, x=1, y=2, w=28, h=16, title=b'Drive 8', top=0)
    m.key(ord('8'), io='scan')
    check('the 8 key opens the boot drive; the listing matches the D81 directory, sorted by name',
          entries=len(entries), **expect(scene.picture([window], {1: ordered}, selected_icon=0, usb=usb), 'drive-8'))
    g = scene.scene.geometry(dict(kind=scene.KIND, x=1, y=2, w=28, h=16))

    def select(name, label, selected_icon=None):
        target, current = names.index(name), window.get('selected', -1)
        for _ in range(abs(target-current)):
            m.key(0x11 if target > current else 0x91)
        window['selected'] = target
        window['top'] = min(window['top'], target)             # the selection scrolls into view
        window['top'] = max(window['top'], target-g['wh']+1)
        return expect(scene.picture([window], {1: ordered}, selected_icon=selected_icon, usb=usb), label)

    def back(label):
        m.key(27, io='leave')
        m.wait(gemdesk, f'GEMDESK back from {label}', 300)
        return expect(scene.picture([window], {1: ordered}, usb=usb), f'back-from-{label}')

    selected = select(b'CALC', 'calc-selected', selected_icon=0)
    m.key(13, io='launch')
    m.wait(lambda: m.read(0x3d20) == b'\x20' and m.read(0x3d40, 4) == b'CALC' and ready(m), 'Calculator running', 300)
    check('Return launches the selected CALC through the dispatcher', selected=selected)
    check('leaving Calculator returns to GEMDESK, which reopens the window with its selection', **back('calc'))

    selected = select(b'NOTE', 'note-selected')
    m.key(13, io='launch')
    m.wait(running('editor.prg'), 'Editor running', 300)
    assert m.read(0x3d9a) == b'\0', 'the Editor claimed the document request'
    report['editor_state'] = {n: m.value(lst_symbol('native-desktop/editor', n))[0] for n in EDITOR_FIELDS}
    if diagnose:
        diagnose('editor')
    want = editor_surface(NOTE, 0, name='NOTE', device=8, dirty=False, field='NOTE', fmt=2,
                          view=0, horizontal=0, selection=None)
    check('Return on a SEQ file opens it in the Editor as a document: the surface matches the Editor oracle',
          selected=selected, **expect_surface(m, want, 'editor', 60))
    check('leaving the Editor returns to GEMDESK with the document still selected', **back('editor'))

    selected = select(b'LEDGER', 'ledger-selected')
    m.key(13, io='launch')
    m.wait(running('sheet.prg'), 'Sheet running', 300)
    assert m.read(0x3d9a) == b'\0', 'Sheet claimed the document request'
    labels = {name: int(at, 16) for at, name in
              re.findall(r'^al ([0-9A-F]+) \.(\S+)$', (IMAGES/'sheet.lbl').read_text(), re.M)}
    values = m.value(labels['_sh_values'], 8)
    cells = [int.from_bytes(values[i:i+4], 'little', signed=True) for i in (0, 4)]
    assert cells == [7, 42] and m.value(labels['_wb_error']) == b'\0', cells
    assert m.value(labels['_wb_path'], 7) == b'LEDGER\0'
    check('Return on a USHT workbook (SEQ) opens it in Sheet: A1 7 and B1 =a1*6 read 7 and 42',
          cells=cells, selected=selected)
    check('leaving Sheet returns to GEMDESK with the workbook still selected', **back('sheet'))

    selected = select(b'PICTURE', 'picture-selected')
    m.key(13, io='launch')
    m.wait(running('paint.prg'), 'Paint running', 300)
    assert m.read(0x3d9a) == b'\0', 'Paint claimed the document request'

    def value(name, n=1): return m.value(lst_symbol('native-desktop/paint', name), n)
    # Paint's state is read only once it waits for input with the file service idle.
    m.wait(lambda: ready(m) and m.read(0x3d91) == b'\0' and value('pa_status')[0] == 2,
           'Paint opened the picture', 300)
    tag = value('pd_handles')[0]
    allocation = m.read(0x3c00+(tag-1)*8, 8)
    assert allocation[:2] == bytes([32, 1]) and allocation[3] == 36, allocation
    document = m.value(allocation[2]*256, 9216, bank=1)
    if document != PICTURE:
        (m.work/'paint-document.bin').write_bytes(document)
        raise AssertionError(('the picture in Paint\'s document allocation',
                              [(i, a, b) for i, (a, b) in enumerate(zip(document, PICTURE)) if a != b][:12]))
    name = value('pf_name', value('pf_length')[0])
    assert name == b'PICTURE' and value('pd_dirty')[0] == 0, name
    want = paint_surface(PICTURE, message=PAINT_MESSAGES[2], view_x=value('pa_view_x')[0], view_y=value('pa_view_y')[0],
                         focus=value('ui_selected')[0], x=int.from_bytes(value('pd_x', 2), 'little'), y=value('pd_y')[0],
                         pen=value('pd_pen')[0], color=value('pd_color')[0], dirty=False, mode=value('pa_mode')[0],
                         action=value('pa_action')[0], name=name, caret=value('pa_field_caret')[0],
                         field_view=value('pa_field_view')[0], device=value('pf_device')[0], fmt=value('pf_format')[0])
    check('Return on a UPNT picture (SEQ) opens it in Paint: the document bytes and the surface match',
          selected=selected, **expect_surface(m, want, 'paint'))
