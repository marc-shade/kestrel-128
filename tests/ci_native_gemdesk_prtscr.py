#!/usr/bin/env python3
"""GEM desktop Print Screen (docs/GEM-DESKTOP.md) in the Py65 model: HELP or
Options:Print Screen sends the desktop's bitmap to the printer on IEC device 4
in the Commodore bit-image mode; the printed bytes are decoded independently
from the model's surface RAM. Esc stops between bands (the printer is returned
to text mode), and a missing printer is reported. Surfaces are compared with
tests/native_gemdesk_scene.py."""
import argparse
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
from ci_native_gemdesk import Gem, AESVC, scene
from ci_native_gemdesk_print import with_printer
import ci_native_files


def band_dump(bitmap, y0):
    """One band: CHR$(8), 320 columns (bit 7 set, bit r = pixel row y0+r), CR."""
    out = bytearray([8])
    rows = min(7, 200-y0)
    for x in range(320):
        dots = 0
        for r in range(rows):
            y = y0+r
            if bitmap[(y//8)*320+(x//8)*8+y % 8] & (0x80 >> (x % 8)):
                dots |= 1 << r
        out.append(dots | 0x80)
    out.append(13)
    return bytes(out)


def screen_dump(bitmap):
    return b''.join(band_dump(bitmap, y0) for y0 in range(0, 200, 7))+b'\x0f'


def decode(printed):
    """Printed bytes back to a 320x200 set of dots (independent of band_dump)."""
    assert printed[-1] == 15, 'ends in text mode'
    lines = printed[:-1].split(b'\r')
    assert lines[-1] == b'' and len(lines) == 30, len(lines)
    dots = set()
    for band, line in enumerate(lines[:-1]):
        assert line[0] == 8 and len(line) == 321, (band, line[:4], len(line))
        for x, byte in enumerate(line[1:]):
            assert byte & 0x80
            for r in range(7):
                if byte & (1 << r):
                    dots.add((x, band*7+r))
    return dots


def pixels(bitmap):
    return {(x, y) for y in range(200) for x in range(320)
            if bitmap[(y//8)*320+(x//8)*8+y % 8] & (0x80 >> (x % 8))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    report = dict(passed=False, physical_hardware_io=False, cases=[])

    def done(name, p, **extra):
        report['cases'].append(dict(name=name, frames=p.frames, instructions=p.instructions, **extra))
        args.report.write_text(json.dumps(report, indent=2)+'\n')
        print('PASS:', name, flush=True)

    try:
        files = {(8, b'AESVC.PRG', b'P'): AESVC, (8, b'NOTE', b'S'): b'NOTE\r'}
        p = with_printer(lambda: Gem(files))
        p.cell(35, 3); p.click(double=True)             # a window, so the dump has text in it
        w8 = dict(id=1, x=1, y=2, w=28, h=16, title=b'Drive 8', top=0)
        from ci_native_gemdesk import entries_for
        shown = scene.picture([w8], {1: scene.ordered(entries_for(p.io.files, 8), 0)}, selected_icon=0, printer=True)
        p.expect(shown, 'drive 8 open')
        p.io.printers[4].clear()
        p.key(0x84)                                     # HELP
        printed = bytes(p.io.printers[4])
        p.expect(shown, 'unchanged after HELP')
        bitmap = p.surface()[:8000]
        assert printed == screen_dump(bitmap), (len(printed), printed[:8])
        assert decode(printed) == pixels(bitmap)
        assert not p.io.handles
        done('HELP prints the desktop: 29 bit-image bands whose dots are exactly the set bitmap pixels, '
             'then CHR$(15)', p, bytes=len(printed), dots=len(pixels(bitmap)))

        p.io.printers[4].clear()
        p.key(0x85)                                     # F1, right x3: the Options menu
        for _ in range(3):
            p.key(0x1d)
        p.key(0x11); p.key(0x11)                        # Preferences, Save Desktop, Print Screen
        p.key(13)
        p.expect(shown, 'menu closed')
        assert bytes(p.io.printers[4]) == printed, 'the menu is gone before the dump'
        done('Options:Print Screen closes the menu, then prints the same dump', p)

        p.io.printers[4].clear()
        p.keys.extend([0x84, 27])                       # Esc waits in the buffer: read after band 1
        p.loop()
        stopped = b'[1][Print Screen|stopped.][OK]'
        p.expect(scene.scene.draw(shown, stopped, 1, 1)[0], 'stopped')
        assert bytes(p.io.printers[4]) == band_dump(bitmap, 0)+b'\x0f', bytes(p.io.printers[4])[-4:]
        p.key(13); p.expect(shown, 'alert closed')
        assert not p.io.handles
        done('Esc stops after the band being printed and returns the printer to text mode', p)

        del p.io.printers[4]                            # switched off
        p.key(0x84)
        gone = b'[1][No printer answers|on device 4.][OK]'
        p.expect(scene.scene.draw(shown, gone, 1, 1)[0], 'no printer')
        p.key(13); p.expect(shown, 'closed')
        assert not p.io.handles
        done('without a printer, HELP reports that none answers on device 4', p)

        # The Control Panel's printer (TOS's Install Printer): device 5, upper case only.
        p.io.printers[5] = bytearray()
        repeat = p.ram[0x0a22]
        p.key(0x85); p.key(0x11); p.key(13)             # Desk:Control Panel
        p.expect(scene.control_dialog(shown, repeat, 2), 'control panel')
        p.cell(5+16+1, 6+8); p.click()                  # printer 5
        p.cell(5+2+1, 6+9); p.click()                   # Lowercase off
        p.expect(scene.control_dialog(shown, repeat, 2, focus=16, printer=5, lower=False), 'printer 5 chosen')
        p.key(13)
        assert (p.ram[p.symbol('gm_prt_dev')], p.ram[p.symbol('gm_prt_sa')]) == (5, 0)
        p.expect(shown, 'device 5 answers: the Printer icon stays')
        mark = len(p.io.events)
        p.key(0x84)
        assert bytes(p.io.printers[5]) == screen_dump(p.surface()[:8000])
        opens = [e for e in p.io.events[mark:] if e[0] == 'open' and e[1] == 121]
        assert opens and all(e[2:4] == (5, 0) for e in opens), opens
        done('Control Panel: printer 5 with Lowercase off; Print Screen goes to device 5, secondary address 0', p)

        listed8 = scene.ordered(entries_for(p.io.files, 8), 0)      # (Save Desktop does not list drive 8 again)
        p.key(0x85); p.key(0x1d); p.key(0x1d); p.key(0x1d); p.key(0x11); p.key(13)   # Options:Save Desktop
        saved = bytes(p.io.files[8, b'DESKTOP.INF', b'S'])
        assert saved[60:62] == b'\x05\x00', saved[60:62]
        original = ci_native_files.StreamIEC.__init__

        def only_five(self, *a, **k):                    # a cold start where only device 5 answers
            original(self, *a, **k)
            self.printers[5] = bytearray()
        ci_native_files.StreamIEC.__init__ = only_five
        try:
            cold = Gem({k: bytes(v) for k, v in p.io.files.items() if k != (8, b'GEMDESK', b'P')})
        finally:
            ci_native_files.StreamIEC.__init__ = original
        assert (cold.ram[cold.symbol('gm_prt_dev')], cold.ram[cold.symbol('gm_prt_sa')]) == (5, 0)
        cold.expect(scene.picture([dict(w8, selected=None)], {1: scene.ordered(entries_for(cold.io.files, 8), 0)},
                                  selected_icon=None, printer=True), 'cold start with printer 5')
        done('the printer is saved with the desktop (record bytes 60, 61); a cold start restores it and probes '
             'device 5 for the Printer icon', cold)

        del p.io.printers[5]
        p.key(0x84)
        p.expect(scene.scene.draw(shown, b'[1][No printer answers|on device 5.][OK]', 1, 1)[0], 'none on 5')
        p.key(13)
        p.key(0x85); p.key(0x11); p.key(13)
        p.expect(scene.control_dialog(shown, repeat, 2, printer=5, lower=False), 'control panel again')
        p.cell(5+11+1, 6+8); p.click(); p.key(13)       # back to 4, where nothing answers
        bare = scene.picture([w8], {1: listed8}, selected_icon=0)
        p.expect(bare, 'no printer on device 4: the icon goes')
        done('a missing printer is named by its device; choosing a device that does not answer removes the '
             'Printer icon', p)
        report['passed'] = True
    finally:
        args.report.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
