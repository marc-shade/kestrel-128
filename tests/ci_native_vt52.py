#!/usr/bin/env python3
"""The native VT52 terminal (docs/NATIVE-VT52.md) through real NMI stubs and
the modeled ACIA and VDC: screen, keyboard, ring buffer and restoration."""
import argparse
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ci_native_calc as calc
import ci_native_claude as claude
from native_clipboard_check import released_stats
from native_vt52_scene import VT52, key_bytes, ROWS, COLS
from src.native.graphics.font import font


class StartupExit(Exception):
    """The terminal returned during startup (no ACIA), after the restore checks."""


class Terminal(calc.Calculator):
    instruction_limit = 5_000_000
    nmi = claude.Client.nmi
    feed = claude.Client.feed
    check_restored = claude.Client.check_restored
    key = claude.Client.key

    def __init__(self, **options):
        claude.TerminalMachine.options = options
        calc.Machine = claude.TerminalMachine
        self.labels = {n: int(v, 16) for n, v in re.findall(r'^(\w+)\s*=\s*\$([0-9a-fA-F]+)',
                       (ROOT/'target/native-desktop/vt52.sym').read_text(), re.M)}
        self.borrowed = None
        self.exit_at_start = not options.get('present', True)   # no ACIA: straight back
        self.exited_at_start = False
        try:
            super().__init__('vt52', loader_name=b'VT52', image_prefix='native-desktop', vdc_component=False)
        except StartupExit:
            self.exited_at_start = True
        self.chip = self.m.bus

    def symbol(self, name): return self.labels[name]

    def loop(self, exited=False):
        cpu = self.cpu
        limit = max(10_000_000, self.instruction_limit) if self.borrowed is None else self.instruction_limit
        for steps in range(limit):
            if cpu.pc == self.symbol('vt_start') and self.borrowed is None:
                self.borrowed = dict(zp=bytes(self.ram[2:28]), vector=bytes(self.ram[0x318:0x31a]),
                                     gate=bytes(self.ram[0x3d3e:0x3d40]), screen=self.ram[0xd7],
                                     keys=bytes(self.ram[0x1000:0x1100]))
            if cpu.pc == 0xb00 and cpu.sp == 0xe0:
                assert exited or self.exit_at_start, 'unexpected app exit'
                assert self.m.stats() == released_stats(self.m) and not self.io.handles
                assert self.ram[0x3d20] == 0 and self.ram[0x3d23] == 0
                self.check_restored()
                self.instructions += steps
                if self.exit_at_start and not exited:
                    raise StartupExit
                return
            if cpu.pc == 0xffe4 and not self.keys and not exited:
                assert self.ram[0x3d12] == 1
                assert self.ram[0x1000:0x1014] == bytes([1]*10+[0x85, 0x89, 0x86, 0x8a, 0x87, 0x8b, 0x88, 0x8c, 0x83, 0x84])
                self.instructions += steps
                return
            if self.io.stub(cpu): continue
            if cpu.pc == 0xffe4:
                cpu.a = self.keys.pop(0) if self.keys else 0; cpu.FlagsNZ(cpu.a)
                cpu.pc = (cpu.stPopWord()+1) & 65535
            elif cpu.pc == 0xff5f:
                self.ram[0xd7] ^= 128; cpu.pc = (cpu.stPopWord()+1) & 65535
            elif cpu.pc == 0xffd2:
                assert cpu.a == 0x93
                cpu.pc = (cpu.stPopWord()+1) & 65535
            else:
                assert not (self.m.bus.config == 0 and 0x6000 <= cpu.pc < 0xc000), 'NMI entered app with BASIC mapped'
                cpu.step()
        raise AssertionError(f'terminal stalled at {cpu.pc:04x}')

    def screen(self):
        v = self.chip.video
        return bytes(v[0:ROWS*COLS]), bytes(v[0x800:0x800+ROWS*COLS])

    def expect(self, model, label):
        chars, attrs = self.screen()
        for name, got, want in (('chars', chars, bytes(model.chars)), ('attrs', attrs, bytes(model.attrs))):
            assert got == want, (label, name, [(i//COLS, i % COLS, a, b) for i, (a, b) in enumerate(zip(got, want)) if a != b][:8])
        v = self.value('vt_row'), self.value('vt_col')
        assert v == (model.row, model.col), (label, 'cursor', v, (model.row, model.col))
        reg = self.chip.reg
        if model.cursor:
            assert reg[10] == 0x60 and (reg[14] << 8 | reg[15]) == model.row*COLS+model.col, (label, 'hardware cursor')
        else:
            assert reg[10] == 0x20, (label, 'cursor hidden')
        assert reg[26] & 15 == model.bg, (label, 'background')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    report = dict(passed=False, physical_hardware_io=False, cases=[])

    def done(name, t, **extra):
        report['cases'].append(dict(name=name, instructions=t.instructions, **extra))
        args.report.write_text(json.dumps(report, indent=2)+'\n')
        print('PASS:', name, flush=True)

    try:
        t = Terminal()
        c = t.chip
        assert c.control == 0x1e and c.command == 9, (c.control, c.command)
        assert t.ram[0x318:0x31a] == bytes([0xf0, 0x1b])
        assert int.from_bytes(t.ram[0x3d3e:0x3d40], 'little') == t.symbol('vt_nmi')
        assert t.ram[0xd7] & 128, '80-column screen'
        assert (c.reg[12], c.reg[13], c.reg[20], c.reg[21]) == (0, 0, 8, 0) and c.reg[25] & 0x40
        glyphs = font()
        base = 0x3000
        for code in range(256):
            cell = bytes(c.video[base+code*16:base+code*16+16])
            want = (glyphs[(code-32)*8:(code-32)*8+8]+bytes(8)) if 32 <= code < 127 else (bytes(16) if code < 32 else None)
            if want is not None:
                assert cell == want, ('font', code)
        model = VT52()
        t.expect(model, 'startup')
        done('startup: 19200 8N1 with the receive NMI, 80 columns, ASCII font, blank screen', t)

        def show(data, label):
            t.feed(data); model.feed(data); t.expect(model, label)

        show(b'Hello, VT52!\r\nSecond line\tTab', 'text, CR LF, tab')
        show(b'\x1bY' + bytes([32+10, 32+30]) + b'at 10,30' + b'\x1bA\x1bA\x1bD\x1bDX\x1bB\x1bCY', 'ESC Y and cursor moves')
        show(b'\x1bH\x1bpREVERSE\x1bq normal \x1bb\x05green\x1bb\x0f', 'home, reverse, colour')
        show(b'\x1bc\x01', 'background')
        done('printable text, CR/LF/Tab, ESC Y, ESC A-D, home, reverse and colours', t)

        show(b'\x1bY' + bytes([32+1, 32+70]) + b'ABCDEFGHIJ', 'text up to the last column')
        show(b'\x1bY' + bytes([32+1, 32+5]) + b'\x1bK', 'erase to end of line')
        show(b'\x1bY' + bytes([32+0, 32+6]) + b'\x1bo', 'erase to start of line')
        show(b'\x1bY' + bytes([32+10, 32+32]) + b'\x1bl', 'erase line')
        show(b'\x1bY' + bytes([32+1, 32+3]) + b'\x1bJ', 'erase to end of screen')
        show(b'\x1bE' + b''.join(b'\x1bY' + bytes([32+r, 32]) + f'row {r}'.encode() for r in range(25)), 'clear and 25 rows')
        show(b'\x1bY' + bytes([32+12, 32+40]) + b'\x1bd', 'erase to start of screen')
        done('erase to end/start of line and screen, erase line, clear screen', t)

        show(b'\x1bE' + b''.join(b'\x1bY' + bytes([32+r, 32+2*r]) + f'line {r}'.encode() for r in range(25)), 'fill')
        show(b'\x1bY' + bytes([32+5, 32+9]) + b'\x1bL', 'insert line')
        show(b'\x1bY' + bytes([32+7, 32+1]) + b'\x1bM', 'delete line')
        show(b'\x1bY' + bytes([32+24, 32]) + b'\x1bM', 'delete the last line')
        show(b'\x1bY' + bytes([32+24, 32+70]) + b'\nscrolled', 'line feed on the last row scrolls')
        show(b'\x1bH\x1bIabove', 'reverse line feed at the top')
        show(b'\x1bj\x1bY' + bytes([32+3, 32+3]) + b'x\x1bky', 'save and restore the cursor')
        done('insert/delete line, scrolling both ways, save/restore cursor', t)

        show(b'\x1bY' + bytes([32+20, 32+75]) + b'wrapping text', 'wrap on')
        show(b'\x1bw\x1bY' + bytes([32+21, 32+75]) + b'no wrap here', 'wrap off')
        show(b'\x1bv\x1bf', 'cursor off')
        show(b'\x1be\x1bZ\x07\x01ok', 'cursor on; unknown escapes and controls ignored; BEL rings')
        sid = [c.sid[a-0xd400] for a in (0xd400, 0xd401, 0xd404, 0xd405, 0xd406)]
        assert (sid[0] | sid[1] << 8) == 14985 and sid[2:] == [0x11, 0x09, 0x00], sid   # the SID bell
        show(b'\x1bY\x10\x7f', 'ESC Y out of range clamps')
        done('wrap on and off, cursor on and off, BEL rings the SID bell, unknown sequences ignored, positions clamped', t)

        sent = len(c.sent)
        keys = [0x41, 0x5a, 0xc1, 0x31, 0x2e, 0x0d, 0x14, 0x1b, 0x91, 0x11, 0x1d, 0x9d, 0x09, 0x03, 0x5e, 0x85, 0xa0]
        for k in keys:
            t.key(k)
        want = b''.join(key_bytes(k) for k in keys if k not in (0x85, 0xa0))
        assert bytes(c.sent[sent:]) == want, (bytes(c.sent[sent:]), want)
        done('keys are sent as ASCII; cursor keys as ESC A-D; Del as backspace', t, sent=want.decode('latin-1'))

        before = t.value('vt_rx_dropped')
        data = bytes(33+(i % 90) for i in range(300))
        for b in data:
            t.nmi(b)
        assert t.value('vt_rx_dropped') - before == 300-255
        t.cpu.a = 0; t.cpu.FlagsNZ(0); t.cpu.pc = (t.cpu.stPopWord()+1) & 65535; t.loop()
        model.feed(data[:255]); t.expect(model, 'ring overflow')
        done('the 256-byte ring keeps the first 255 bytes and counts the rest as dropped', t)

        t.key(0x8c, exited=True)
        assert c.command == 2 and c.control == 0x1e, 'ACIA settings restored'
        done('F8 returns to the desktop: VDC, font, screen mode, NMI vector, keys and ACIA restored', t)

        n = Terminal(present=False)
        assert n.exited_at_start and not n.chip.serial_writes, 'no ACIA register was written'
        done('without an ACIA the terminal restores everything and returns', n)
        report['passed'] = True
    finally:
        args.report.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
