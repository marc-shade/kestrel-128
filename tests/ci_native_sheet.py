#!/usr/bin/env python3
"""Loaded native Sheet: complete pixels, workbook bytes, errors and ownership."""
import argparse
import binascii
import hashlib
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
from ci_native_pointer import Pointer, calc, heap
from ci_native_vdc_desktop import VDCBus
from native_vdc_mirror import bitmap, attributes
from src.native.graphics.font import font
from launcher_scene import pointer_shape

ROOT = Path(__file__).resolve().parents[1]


def workbook(cells, formats=bytes(4)):
    records = bytearray(8192)
    for index, text in cells.items():
        text = text.encode() if isinstance(text, str) else bytes(text)
        assert len(text) <= 31
        records[index*32:index*32+len(text)] = text
    header = b'USHT\1\10\40\40\0\40' + binascii.crc_hqx(records, 65535).to_bytes(2, 'little') + bytes(formats)
    return header + records


class Sheet(Pointer):
    instruction_limit = 30000000
    allow_busy_poll = True

    def __init__(self, document=None, **kwargs):
        self.document = document                # {address: bytes}, written before the first instruction
        self.labels = {name: int(value, 16) for value, name in re.findall(
            r'^al ([0-9a-fA-F]+) \.(\S+)', (ROOT/'target/native-desktop/sheet.lbl').read_text(), re.M)}
        self.initial_zp = None
        calc.Calculator.__init__(self, 'sheet', loader_name=b'SHEET', image_prefix='native-desktop', **kwargs)
        self.bus = self.m.bus; self.frames = 0
        print('Sheet ready:', self.image[12], 'app pages,', self.m.stats(), 'free', flush=True)

    def symbol(self, name):
        return self.labels[name] if name in self.labels else self.labels['_'+name]

    def loop(self, exited=False):
        if self.document:                       # as a desktop leaves it for the dispatcher
            staged, self.document = self.document, None
            for at, value in staged.items():
                self.ram[at:at+len(value)] = value
        if self.initial_zp is None and self.cpu.pc == self.symbol('native_entry'):
            self.initial_zp = bytes(self.ram[2:28])
        return calc.Calculator.loop(self, exited)

    def key(self, key, exited=False):
        self.keys.append(key); self.loop(exited); self.events += 1
        assert int.from_bytes(self.ram[0x3d13:0x3d15], 'little') == self.events

    def output(self, value):
        assert not self.value('vd_phase'), 'ROM text output while VDC is retained'
        if 0xc1 <= value <= 0xda: value -= 0x80
        calc.Calculator.output(self, value)

    def bytes(self, name, count):
        at = self.symbol(name)
        return bytes(self.ram[at:at+count])

    def sources(self):
        handle = self.bytes('wb_handle', 4)
        at = 0x3c00+(handle[0]-1)*8
        desc = bytes(self.ram[at:at+8])
        assert desc[:2] == bytes([32,1]) and desc[3] == 32 and desc[4:7] == handle[1:]
        return bytes(self.bus.ram[1][desc[2]*256:(desc[2]+32)*256])

    def values(self):
        raw = self.bytes('sh_values', 1024)
        return [int.from_bytes(raw[i:i+4], 'little', signed=True) for i in range(0,1024,4)]

    def text(self, row):
        return self.bytes('sg_chars', 1000)[row*40:row*40+40].decode()

    def check(self):
        chars, colors = self.bytes('sg_chars', 1000), self.bytes('sg_colors', 1000)
        glyphs = font()
        expected = bytearray(9216)
        for cell, code in enumerate(chars):
            expected[cell*8:cell*8+8] = glyphs[(code-32)*8:(code-31)*8]
        expected[8192:9192] = colors
        expected[8000:8128] = pointer_shape()
        expected[9208:9210] = b'\x7d\x7e'
        actual = bytes(self.ram[0xc000:0xe400])
        assert actual == expected, ('VIC pixels', next((i for i,(a,b) in enumerate(zip(actual,expected)) if a!=b), None))
        if self.value('vd_live'):
            assert not self.value('vd_fault')
            x, y = self.position
            want = bitmap(actual, self.bus.size == 64, x=x, y=y, pointer=bool(self.value('vd_pointer_visible')))
            assert self.bus.bytes(self.value('vd_base')*256, 16000) == want, 'VDC pixels'
            if self.bus.size == 64: assert self.bus.bytes(0x8000, 2000) == attributes(actual)
        assert not self.value('vm_pending') or not self.value('vd_live')

    def edit(self, text):
        self.type(text); self.key(13); self.check()

    def save(self, path):
        self.key(0x87); self.key(21); self.type(path); self.key(13); self.check()

    def open(self, path):
        self.key(0x86)
        if self.value('mode') == 3: self.key(13)
        self.key(21); self.type(path); self.key(13); self.check()

    def exit(self):
        if self.value('mode') or self.value('edit_active'): self.key(27)
        dirty = self.value('wb_dirty') or self.value('wb_poisoned')
        self.key(27, exited=not dirty)
        if dirty: self.key(13, exited=True)
        self.restored()
        if self.bus.original is not None:
            assert self.bus.video_ram == self.bus.original[0], 'VDC restored byte for byte'
            for register in (1,6,8,9,10,12,13,14,15,18,19,20,21,22,23,24,25,26,27,28,32,33):
                assert self.bus.reg[register] == self.bus.original[1][register], register


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=('core', 'files', 'document', 'faults', 'mouse', 'ultimate', 'recovery', 'undo', 'undo-faults', 'aggregates', 'clipboard', 'clipboard-handoff', 'modules', 'formats'), default='core')
    parser.add_argument('--size', type=int, choices=(16,64), default=64)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    original = heap.Bus
    heap.Bus = type('SheetBus', (VDCBus,), dict(size=args.size))
    report = dict(passed=False, physical_hardware_io=False, cases=[], images={
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (ROOT/'target/native-desktop/sheet.prg', ROOT/'target/native-desktop/vdsvc.prg',
                  ROOT/'target/native-desktop/shfont.prg', ROOT/'target/native-desktop/shcalc.prg',
                  ROOT/'target/native-desktop/shclip.prg', heap.IMAGE)})
    def done(name, p):
        report['cases'].append(dict(name=name, instructions=p.instructions, keys=p.events, frames=p.frames))
        print('PASS:', name, flush=True)
    try:
        if args.case == 'core':
            p = Sheet(); p.check(); assert p.sources() == bytes(8192)
            p.edit('12'); p.key(0x1d); p.edit('30'); p.key(0x1d); p.edit('=A1+B1')
            print('Core: arithmetic entered', flush=True)
            assert p.values()[:3] == [12,30,42]
            assert p.sources() == workbook({0:'12',1:'30',2:'=a1+b1'})[16:]
            p.key(0x9d); p.key(13); p.key(21); p.type('8'); p.key(27)
            assert p.values()[1:3] == [30,42], 'cancelled draft changed workbook'
            p.key(13); p.key(21); p.type('8'); p.key(13); assert p.values()[1:3] == [8,20]
            p.key(0x1d); p.key(0x1d); p.edit('=SUM(A1:C1)'); assert p.values()[3] == 40
            print('Core: editing and SUM checked', flush=True)
            # Decimals: mantissa and decimals (the high nibble of the type); the
            # grid cell keeps the decimals that fit 8 characters, rounded once.
            p.key(0x1d); p.edit('1.5'); p.key(0x1d); p.edit('=E1/4'); p.key(0x1d); p.edit('=-1/3')
            p.key(0x1d); p.edit('12345.6789')
            types = p.bytes('sh_types', 256)
            assert [(p.values()[i], types[i]) for i in range(4, 8)] == [(15, 0x11), (375, 0x31), (-333333, 0x61),
                                                                         (123456789, 0x41)]
            assert p.value('left_column') == 4
            row = p.text(6)
            assert [row[3+x*9:11+x*9].strip() for x in range(4)] == ['1.5', '0.375', '-0.33333', '12345.68'], row
            assert p.text(19).startswith('Value: 12345.6789'), p.text(19)
            p.check()
            print('Core: decimals checked', flush=True)
            for _ in range(4): p.key(0x1d)
            for _ in range(31): p.key(0x11)
            assert p.value('selected') == 255 and p.value('top_row') == 20 and p.value('left_column') == 4
            p.edit('-2147483648'); assert p.values()[255] == -2147483648
            assert '-2147483648' in p.text(19) and '########' in p.text(17)
            p.key(0x13); p.edit('=A1'); assert p.bytes('sh_types',256)[0] == 8
            p.key(0x14); assert p.bytes('sh_types',256)[0] == 0
            p.edit("'Hello"); assert p.sources()[:7] == b"'hello\0"
            p.key(27); assert p.value('mode') == 3
            p.key(27); assert not p.value('mode') and p.value('wb_dirty')
            p.check(); p.exit(); done('editing, references, SUM, cycles, full grid navigation, source retention and discard protection', p)
        elif args.case == 'clipboard':
            from native_clipboard_check import published
            p=Sheet();p.key(22);assert p.value('wb_error') and not p.value('wb_dirty')
            p.edit('42');p.key(3);assert published(p.m)[0]==b'42'
            token=p.bytes('sh_clip_text',2)  # payload remains ASCII after Copy
            assert token==b'42'
            handle=p.ram[0x3deb];page=p.ram[0x3c00+(handle-1)*8+2]
            # The shared provider permits opaque byte text. Inject an item
            # another client could publish; Sheet must reject its control byte.
            p.bus.ram[1][page*256]=10;before=p.sources();p.key(22)
            assert p.value('wb_error') and p.sources()==before and published(p.m)[0]==b'\n2'
            p.bus.ram[1][page*256]=ord('4')
            p.key(0x1d);p.key(22);assert p.values()[:2]==[42,42]
            p.key(24);assert p.values()[1]==0 and published(p.m)[0]==b'42'
            p.key(26);assert p.values()[1]==42
            before=p.sources();clip=p.io.files.pop((8,b'SHCLIP.PRG',b'P'))
            p.key(24);assert p.value('wb_error') and p.sources()==before and published(p.m)[0]==b'42'
            p.io.files[8,b'SHCLIP.PRG',b'P']=clip;p.key(24);assert p.values()[1]==0
            p.key(3);assert p.value('wb_error') and published(p.m)[0]==b'42'
            p.key(22);assert not p.value('wb_error') and p.values()[1]==42
            p.check();p.exit();done('Copy/Paste/Cut, undo, empty clipboard and missing module retain workbook and clipboard',p)
        elif args.case == 'clipboard-handoff':
            from ci_native_editor_gui import GraphicalEditor
            from native_clipboard_check import published
            raw=b'=MAX(B1:C1)'
            e=GraphicalEditor({(9,b'INPUT',b'S'):raw},device=9,existing_machine=calc.Machine())
            e.prompt(0x85,'INPUT');e.key(1);e.key(3);e.key(7);e.exit();e.restored()
            machine=calc.Machine;calc.Machine=lambda:e.m
            try:p=Sheet()
            finally:calc.Machine=machine
            p.events=int.from_bytes(p.ram[0x3d13:0x3d15],'little')
            p.key(22);assert p.sources()[:len(raw)]==raw
            p.key(0x1d);p.edit('42');assert p.values()[0]==42
            p.key(0x13);p.key(3);p.check();p.exit();assert published(p.m)[0]==raw
            e2=GraphicalEditor(device=9,existing_machine=p.m)
            e2.events=int.from_bytes(e2.ram[0x3d13:0x3d15],'little')
            e2.key(22);e2.check(raw,len(raw),True,status=21)
            e2.key(1);e2.type('X'*32);e2.key(1);e2.key(3);e2.key(7);e2.exit(dirty=True);e2.restored()
            machine=calc.Machine;calc.Machine=lambda:e2.m
            try:q=Sheet()
            finally:calc.Machine=machine
            q.events=int.from_bytes(q.ram[0x3d13:0x3d15],'little')
            q.key(22);assert q.value('wb_error') and q.sources()==bytes(8192)
            assert published(q.m)[0]==b'X'*32
            q.check();q.exit();done('Editor -> Sheet formula -> Editor and oversized paste refusal on one kernel',q)
        elif args.case == 'modules':
            p=Sheet();p.edit('7');module=p.io.files.pop((8,b'SHCALC.PRG',b'P'))
            p.type('8');p.key(13)
            assert p.value('wb_error') and p.sources()[:2]==b'8\0'
            assert p.bytes('sh_types',256)==bytes([10])*256 and p.values()==[0]*256
            p.io.files[8,b'SHCALC.PRG',b'P']=module
            p.key(13);assert not p.value('wb_error') and p.values()[0]==8
            broken=bytearray(module);broken[-1]^=1;p.io.files[8,b'SHCALC.PRG',b'P']=bytes(broken)
            p.type('9');p.key(13);assert p.value('wb_error') and p.values()==[0]*256
            p.io.files[8,b'SHCALC.PRG',b'P']=module;p.key(13);assert p.values()[0]==9
            font_module=p.io.files.pop((8,b'SHFONT.PRG',b'P'))
            p.type('10');p.key(13);assert p.values()[0]==10 and p.value('wb_dirty')
            assert p.value('sm_display_fault')
            io_events=list(p.io.events);p.key(ord('9'));assert p.io.events==io_events
            before=p.sources();owners=p.m.stats();p.key(27)
            assert p.sources()==before and p.m.stats()==owners
            p.io.files[8,b'SHFONT.PRG',b'P']=font_module;p.key(12)
            p.check();p.exit();done('missing and corrupt calculation modules invalidate results and retry unchanged source safely',p)
        elif args.case == 'aggregates':
            p=Sheet();p.edit('13');p.key(0x1d);p.edit('-7');p.key(0x1d)
            p.edit('=MIN(A1:B1)');p.key(0x1d);p.edit('=MAX(A1:B1)')
            p.key(0x1d);p.edit('=COUNT(A1:B1)')
            assert p.values()[:5]==[13,-7,-7,13,2]
            expected=workbook({0:'13',1:'-7',2:'=min(a1:b1)',3:'=max(a1:b1)',4:'=count(a1:b1)'})
            p.save('RANGES');assert bytes(p.io.files[8,b'RANGES',b'S'])==expected
            p.key(0x13);p.edit('99');assert p.values()[3]==99
            p.key(26);assert p.values()[:5]==[13,-7,-7,13,2]
            p.open('RANGES');assert p.sources()==expected[16:] and p.values()[:5]==[13,-7,-7,13,2]
            p.check();p.exit();done('MIN/MAX/COUNT entry, dependency recalculation, undo and byte-exact save/reopen',p)
        elif args.case == 'undo':
            p=Sheet();p.key(26);assert not p.value('wb_dirty')
            p.edit('21');p.key(0x1d);p.edit('=A1*2')
            p.key(0x13);p.key(26)
            assert p.value('selected')==1 and p.values()[:2]==[21,0]
            assert p.sources()==workbook({0:'21'})[16:]
            p.key(26);assert p.values()[:2]==[21,0]  # one step only
            p.key(18);assert p.values()[:2]==[21,42]
            p.key(0x14);p.key(26);assert p.values()[1]==42  # undo Clear
            p.key(13);p.key(13);assert p.value('wb_history')==2  # no-op edit
            p.key(18);assert p.values()[1]==0
            p.edit('7');p.key(18);assert p.values()[1]==7  # new edit drops redo
            before=p.sources();p.save('HISTORY');assert not p.value('wb_dirty')
            p.key(26);assert p.value('wb_dirty') and p.values()[1]==0
            p.key(18);assert p.sources()==before
            p.open('HISTORY');assert not p.value('wb_history') and not p.value('wb_dirty')
            p.key(26);assert p.sources()==before and not p.value('wb_dirty')
            p.edit('8');p.key(0x85);p.key(27);assert p.value('wb_history')==1
            p.key(0x85);p.key(13);assert not p.value('wb_history') and p.sources()==bytes(8192)
            p.check();p.exit();done('one-step cell undo/redo, Clear, no-op edits, save retention and New/Open reset',p)
        elif args.case == 'undo-faults':
            p=Sheet();p.edit('7');before=p.sources();stub=p.io.stub
            injected=[];operation=0x1c26
            def fail_once(cpu):
                if not injected and cpu.pc==operation and bytes(p.ram[0x3d04:0x3d08])==p.bytes('wb_handle',4):
                    injected.append(True);cpu.a=4;cpu.p|=1;cpu.pc=cpu.stPopWord()+1;return True
                return stub(cpu)
            p.io.stub=fail_once;p.key(26)
            assert injected and p.value('wb_error') and p.value('wb_history')==1
            assert p.sources()==before and not p.value('wb_poisoned')
            p.io.stub=stub;p.key(26);assert p.sources()==bytes(8192)
            p.key(18);assert p.sources()==before
            operation=0x1c29;injected.clear();p.io.stub=fail_once;p.key(26)
            assert injected and p.value('wb_poisoned') and p.sources()==before
            p.io.stub=stub;p.key(26);assert p.value('wb_error') and p.sources()==before
            p.check();p.exit();done('failed undo read retains retry history; failed undo write poisons storage and blocks further mutation',p)
        elif args.case == 'formats':
            # Column display formats (Ctrl-F): every decimal, then 0-6 decimals.
            p = Sheet()
            for text in ('1.5', '2', '-0.004', '9.995', '123456.789'):
                p.edit(text); p.key(0x11)
            p.key(0x13)
            def column_a():
                return [p.text(6+y)[3:11].strip() for y in range(5)]
            shown = {None: ['1.5', '2', '-0.004', '9.995', '123456.8'],
                     0: ['2', '2', '0', '10', '123457'],
                     1: ['1.5', '2.0', '0.0', '10.0', '123456.8'],
                     2: ['1.50', '2.00', '0.00', '10.00', '123456.8'],
                     3: ['1.500', '2.000', '-0.004', '9.995', '123456.8'],
                     6: ['1.500000', '2.000000', '-0.00400', '9.995000', '123456.8']}
            assert column_a() == shown[None], column_a()
            for decimals in range(7):
                p.key(6)
                assert p.text(23).startswith('Column A decimals: %d' % decimals), p.text(23)
                if decimals in shown:
                    assert column_a() == shown[decimals], (decimals, column_a())
            assert p.value('wb_dirty') and p.bytes('wb_formats', 4) == bytes([7, 0, 0, 0])
            assert p.values()[0:40:8] == [15, 2, -4, 9995, 123456789], 'a format changes only what is shown'
            p.key(0x1d); p.key(6); p.key(6); p.key(6)          # column B: 2 decimals
            assert p.text(23).startswith('Column B decimals: 2') and p.bytes('wb_formats', 4) == bytes([0x37, 0, 0, 0])
            p.key(0x9d); p.key(6); assert p.text(23).startswith('Column A decimals: all')
            assert p.bytes('wb_formats', 4) == bytes([0x30, 0, 0, 0]) and column_a() == shown[None]
            p.key(6); p.key(6)                                 # column A: 1 decimal
            p.save('FORMATS')
            saved = bytes(p.io.files[8, b'FORMATS', b'S'])
            assert saved[12:16] == bytes([0x32, 0, 0, 0]), saved[12:16].hex()
            assert saved == workbook({0:'1.5', 8:'2', 16:'-0.004', 24:'9.995', 32:'123456.789'}, bytes([0x32, 0, 0, 0]))
            p.key(0x85)                                        # New (saved: no question): every decimal again
            assert p.bytes('wb_formats', 4) == bytes(4)
            p.open('FORMATS'); assert not p.value('wb_error') and p.bytes('wb_formats', 4) == bytes([0x32, 0, 0, 0])
            assert column_a() == shown[1], column_a()
            done('Ctrl-F cycles a column\'s display format (every decimal, then 0-6 decimals, rounded once, padded '
                 'within the cell, "-0.00" shown as 0.00); values are unchanged; formats are saved in header bytes '
                 '12-15, reopened and cleared by New', p)
            # A workbook from before formats (zeros) opens unchanged; a format nibble above 7 is refused.
            p.io.files[8, b'OLD', b'S'] = bytearray(workbook({0:'2.25'}))
            p.open('OLD'); assert not p.value('wb_error') and p.bytes('wb_formats', 4) == bytes(4)
            assert p.text(6)[3:11].strip() == '2.25'
            p.io.files[8, b'ODD', b'S'] = bytearray(workbook({0:'7'}, bytes([0, 0, 0x80, 0])))
            before = p.sources(); p.open('ODD')
            assert p.value('wb_error') and p.sources() == before and p.bytes('wb_formats', 4) == bytes(4)
            p.exit(); done('a workbook without formats opens as before; a format above 6 decimals is an invalid workbook', p)
        elif args.case == 'files':
            p = Sheet(); p.edit('123'); p.key(0x1d); p.edit('=A1*2'); p.save('BUDGET')
            data = workbook({0:'123',1:'=a1*2'})
            assert bytes(p.io.files[8,b'BUDGET',b'S']) == data
            assert not p.value('wb_dirty') and not p.value('wb_error')
            p.key(0x13); p.edit('999'); before=p.sources(); p.save('BUDGET')
            assert p.value('wb_error') and p.value('wb_dirty') and p.sources()==before
            assert bytes(p.io.files[8,b'BUDGET',b'S']) == data
            p.key(27); p.open('BUDGET'); assert not p.value('wb_error') and p.values()[:2] == [123,246]
            p.exit(); done('exclusive SEQ save, complete byte readback, collision retention and Open/recalculate', p)
        elif args.case == 'document':
            data = workbook({0:'7', 1:'=a1*6'})

            def request(kind, device, fmt, name, path=b''):
                return {0x3d9a: b'\x80', 0x3d9b: bytes([kind]), 0x3d9c: b'\0', 0x3d9d: b'\0',
                        0x3d29: bytes([device, fmt]), 0x3d2e: bytes([len(path)]), 0x4a00: path,
                        0x3d34: bytes([len(name)]), 0x3e00: name}
            p = Sheet(files={(8, b'LEDGER', b'S'): data}, document=request(3, 8, 0, b'LEDGER'))
            p.check()
            assert p.ram[0x3d9a] == 0, 'the request is claimed'
            assert not p.value('wb_error') and p.values()[:2] == [7, 42], p.values()[:2]
            assert p.sources() == data[16:] and p.bytes('wb_path', 7) == b'LEDGER\0'
            p.exit(); done('a workbook handed over by a desktop (document kind 3, IEC) opens at start and recalculates', p)
            u = Sheet(ultimate_files={b'/Usb0/Books/ledger.sht': data},
                      document=request(3, 1, 3, b'ledger.sht', b'/Usb0/Books'))
            u.check()
            assert not u.value('wb_error') and u.values()[:2] == [7, 42], u.values()[:2]
            assert u.bytes('wb_path', 23) == b'/Usb0/Books/ledger.sht\0' and u.value('wb_format') == 3
            u.exit(); done('the same from USB: the folder and the name joined into the full path', u)
            q = Sheet(files={(8, b'LEDGER', b'S'): data}, document=request(1, 8, 0, b'LEDGER'))
            q.check()
            assert q.ram[0x3d9a] == 0 and q.sources() == bytes(8192) and not q.value('wb_error')
            q.exit(); done('a request for another kind is cleared and leaves a blank workbook', q)
        elif args.case == 'mouse':
            p=Sheet();p.frame();p.move(3*8+4,6*8+4);p.frame(down=True);p.frame(down=False)
            assert p.value('selected')==0
            p.edit('42');p.move(12*8+4,7*8+4);p.frame(down=True);p.frame(down=False)
            assert p.value('selected')==9
            p.move(20*8,2*8+4);p.frame(down=True);p.frame(down=False);assert p.value('edit_active')
            p.type('=A1');p.key(13);assert p.values()[9]==42
            p.check();p.exit();done('shared 1351 selects cells and activates toolbar editing',p)
        elif args.case == 'ultimate':
            data=workbook({0:'21',1:'=A1*2',255:'-99'})
            p=Sheet(source_path=b'/APPS/SHEET',source_context=2,
                    ultimate_files={b'/DATA/INPUT.USHT':data})
            p.key(0x86)
            for _ in range(3):p.key(0x85)
            p.key(0x86)  # DOS context 2, independent of the retained app source.
            p.type('/DATA/INPUT.USHT');p.key(13);p.check()
            assert not p.value('wb_error') and p.sources()==data[16:] and p.values()[1]==42
            p.edit('22');p.save('/DATA/COPY.USHT')
            assert not p.value('wb_error') and not p.value('wb_dirty')
            expected=workbook({0:'22',1:'=A1*2',255:'-99'})
            assert bytes(p.ultimate.files[b'/DATA/COPY.USHT'])==expected
            p.open('/DATA/COPY.USHT');assert p.values()[1]==44 and p.sources()==expected[16:]
            p.exit();done('Ultimate-loaded app, both DOS contexts, absolute paths, full save/readback and Open',p)
        elif args.case == 'recovery':
            p=Sheet(files={(8,b'GOOD',b'S'):workbook({0:'42'})});p.edit('777');before=p.sources()
            stub=p.io.stub;injected=[]
            def no_stage(cpu):
                if cpu.pc==0x1c20 and p.ram[0x3d01]==32:
                    injected.append(True);cpu.a=2;cpu.p|=1;cpu.pc=cpu.stPopWord()+1;return True
                return stub(cpu)
            p.io.stub=no_stage;p.open('GOOD')
            assert injected and p.value('wb_error')==2 and p.sources()==before and p.value('wb_dirty')
            p.io.stub=stub;p.key(27)
            # Make a read fail partway through a fully allocated staging workbook.
            p.io.fail_read=144;p.open('GOOD')
            assert p.value('wb_error') and p.sources()==before and not p.value('wb_stage')
            p.io.fail_read=None;p.key(27)
            p.io.fail_write=100;p.save('PARTIAL')
            assert p.value('wb_error') and p.value('wb_dirty') and p.sources()==before
            assert len(p.io.files[8,b'PARTIAL',b'S'])==100
            p.io.fail_write=None;p.key(27)
            p.bus.stall=True;p.key(0x1d)
            assert p.value('vd_fault') and p.sources()==before
            owned=p.m.stats();sp=p.cpu.sp
            for key in (ord('9'),0x85,0x87,27):
                p.key(key);assert p.sources()==before and p.m.stats()==owned and p.cpu.sp==sp
            p.bus.stall=False;p.key(12);p.check();assert not p.value('vd_fault')
            p.exit();done('staging allocation/read failures, partial output and retained display failure preserve workbook and owners',p)
        else:
            good=workbook({0:'42',1:'=A1*2'})
            malformed=[good[:10], good[:-1], good+b'x', good[:10]+b'\0\0'+good[12:],
                       good[:12]+b'\x08'+good[13:]]          # a column format beyond 6 decimals
            p=Sheet(files={(8,b'BAD'+str(i).encode(),b'S'):data for i,data in enumerate(malformed)})
            p.edit('777');source=p.sources()
            for i in range(len(malformed)):
                p.open('BAD'+str(i));assert p.value('wb_error') and p.sources()==source and p.value('wb_dirty')
                assert not p.io.handles and not p.value('wb_stage');p.key(27)
            p.exit();done('short, long, corrupt-CRC and unsupported files preserve the dirty workbook and release staging',p)
        report['passed']=True
    except BaseException as error:
        report['error']=repr(error)
        raise
    finally:
        heap.Bus=original
        args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__ == '__main__': main()
