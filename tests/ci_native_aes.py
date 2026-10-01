#!/usr/bin/env python3
"""Persistent AES component (GEM layer step 1): load, survive app exit,
re-attach from a new app, refuse bad images or ranges, and unload fully."""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import tempfile

from py65.devices.mpu6502 import MPU
import ci_native_heap as heap
import ci_native_calc
from ci_native_calc import Calculator
from ci_native_files import StreamIEC
from native_banked_bus import BankedBus
import native_aes_scene as scene

ROOT = Path(__file__).resolve().parents[1]
APP = b'AESDEMO.PRG'
AESVC = b'AESVC.PRG'
AE_BASE = int(re.search(r'^AE_BASE = \$([0-9a-f]{4})', (Path(__file__).resolve().parents[1]/'src/native/aes-api.inc').read_text(), re.M).group(1), 16)
AES_OWNER = 30

_released = ci_native_calc.released_stats


AE_DATA, AE_DATA_PAGES = 0x5000, 16


def owner30(machine):
    ram = machine.ram
    return [(i, bytes(ram[0x3c00+i*8:0x3c08+i*8])) for i in range(32)
            if ram[0x3c00+i*8] == AES_OWNER]


ACC_OWNER = 29                     # N_ACCOWNER: the desk accessory image


def resident_aes(machine):
    """The AES image record (bank 1 at AE_BASE), or None; page tags checked.
    Besides it, only the RAM-table segment at AE_DATA may stay resident."""
    ram = machine.ram
    image = [(i, r) for i, r in owner30(machine) if r[2] == AE_BASE >> 8]
    others = [r for i, r in owner30(machine) if r[2] not in (AE_BASE >> 8, AE_DATA >> 8)]
    assert not others, others
    if not image:
        assert not data_segment(machine), 'a data segment without its image'
        return None
    slot, record = image[0]
    assert len(image) == 1 and record[1] == 1, image
    pages = record[3]
    assert bytes(ram[0x3900+record[2]:0x3900+record[2]+pages]) == bytes([slot+1])*pages
    return record


def data_segment(machine):
    found = [r for i, r in owner30(machine) if r[2] == AE_DATA >> 8]
    if found:
        assert found[0][1] == 1 and found[0][3] == AE_DATA_PAGES, found
        return found[0]
    return None


def released_with_aes(machine):
    record = resident_aes(machine)
    live = [bytes(machine.ram[0x3c00+i*8:0x3c08+i*8]) for i in range(32)]
    live = [r for r in live if r[0]]
    if record is None:
        return _released(machine)
    # Only the AES (owner 30) and a desk accessory image (owner 29, bank-1
    # AC_BASE) outlive an app.
    accessory = [r for r in live if r[0] == ACC_OWNER]
    assert all(r[0] == AES_OWNER for r in live if r[0] != ACC_OWNER), live
    assert all(r[1] == 1 and r[2] == 0x40 for r in accessory) and len(accessory) <= 1, live
    data = data_segment(machine)
    pages = record[3]+(data[3] if data else 0)+sum(r[3] for r in accessory)
    return 175, 251-pages, 32-len(live)


ci_native_calc.released_stats = released_with_aes


class Demo(Calculator):
    instruction_limit = 12000000

    def __init__(self, output, machine=None, *, corrupt=False, missing=False):
        if machine is None:
            heap.Bus = BankedBus
            machine = heap.Machine()
        self.m = machine
        self.ram = self.m.ram
        self.image_name = 'aes-demo'
        self.image = (output/APP.decode()).read_bytes()
        component = bytearray((output/AESVC.decode()).read_bytes())
        if corrupt:
            component[-1] ^= 1
        self.symbols = {n: int(v, 16) for n, v in re.findall(
            r'^([\w.]+)\s*=\s*\$([\da-fA-F]+)', (output/'parent.sym').read_text(), re.M)}
        self.aes_symbols = {n: int(v, 16) for n, v in re.findall(
            r'^([\w.]+)\s*=\s*\$([\da-fA-F]+)', (output/'aesvc.sym').read_text(), re.M)}
        files = {(8, APP, b'P'): self.image, (8, AESVC, b'P'): bytes(component)}
        if missing:
            del files[8, AESVC, b'P']
        self.io = StreamIEC(self.m, files)
        self.io.formats[8] = 0
        self.ram[0x3d21:0x3d23] = bytes([8, len(APP)])
        self.ram[0x3d40:0x3d40+len(APP)] = APP
        self.ram[0x3d2c:0x3d2e] = bytes([0, 8])
        self.cpu = MPU(memory=self.m.bus, pc=0x1c38)
        self.cpu.sp, self.cpu.p = 0xe0, 0x20
        self.cpu.stPushWord(0xaff)
        self.screens = [bytearray(b' '*1000), bytearray(b' '*2000)]
        self.reverse = [False, False]; self.row = [0, 0]; self.col = [0, 0]; self.keys = []
        # N_KEYS is kernel state and keeps counting across launches.
        self.events = int.from_bytes(self.ram[0x3d13:0x3d15], 'little')
        self.instructions = 0
        self.observation_target = None; self.observation_done = False
        self.loop()

    def symbol(self, name):
        if name == 'cloop':  # the next wait point: alert or event loop, else input
            name = ('demo_alert_loop' if self.alert_open() else
                    'ae_event_wait' if self.ram[self.symbols['demo_waiting']] else 'input_loop')
        return self.symbols[name]

    def alert_open(self):
        return self.m.bus.ram[1][self.aes_symbols['al_active']] == 1

    def surface(self):
        return bytes(self.ram[0xc000:0xe400])

    def data(self, name, length):
        at = self.symbol(name)
        return bytes(self.ram[at:at+length])

    def check(self, *, attaches, apps, loaded, error=0, version=0x0107, choice=0):
        status = self.data('demo_status', 13)
        assert self.value('demo_error') == error, (self.value('demo_error'), error)
        assert self.value('demo_loaded') == loaded
        if error == 0:
            assert status[0:2] == bytes([version >> 8, version & 255])
            assert int.from_bytes(status[4:6], 'little') == attaches
            assert int.from_bytes(status[6:8], 'little') == apps
        lines = ['AES DEMO', f'VERSION (HEX): ${status[0]:02X}{status[1]:02X}',
                 f'ATTACHES (HEX): ${status[5]:02X}{status[4]:02X}',
                 f'APPS (HEX): ${status[7]:02X}{status[6]:02X}',
                 f'LOADED HERE (HEX): ${loaded:02X}', f'ALERT CHOICE (HEX): ${choice:02X}',
                 'EVENT (HEX): '+self.data('ae_ev_result', 7).hex().upper(),
                 'MESSAGE (HEX): '+self.data('ae_ev_result', 15)[7:].hex().upper(),
                 f'LAST ERROR (HEX): ${error:02X}', '',
                 'RETURN: AES STATUS', 'ESC: EXIT, AES STAYS RESIDENT', 'U: UNLOAD AES AND EXIT',
                 'A: AES ALERT OVER THE VIC SURFACE', 'E: WAIT FOR EVENTS  P: POST A MESSAGE',
                 'M: MENU BAR OVER THE VIC SURFACE', 'W: THREE AES WINDOWS']
        for screen, columns in zip(self.screens, (40, 80)):
            expected = bytearray(b' '*(columns*25))
            for row, line in enumerate(lines):
                expected[row*columns:row*columns+len(line)] = bytes(
                    v-64 if 64 <= v < 96 else v for v in line.encode())
            assert screen == expected, (columns, bytes(screen[:columns*10]))

    def bank1(self, offset, length):
        return bytes(self.m.bus.ram[1][AE_BASE+offset:AE_BASE+offset+length])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix='kestrel-aes-'))
    spec = importlib.util.spec_from_file_location('aes_build', ROOT/'examples/native-aes/build.py')
    build = importlib.util.module_from_spec(spec); spec.loader.exec_module(build)
    images = build.build(work)
    component = (work/AESVC.decode()).read_bytes()
    report = dict(passed=False, physical_hardware_io=False, work=str(work), images=images, cases=[])

    def done(name, demo, **extra):
        report['cases'].append(dict(name=name, events=demo.events, instructions=demo.instructions, **extra))
        args.report.write_text(json.dumps(report, indent=2)+'\n')
        print('PASS:', name, flush=True)

    try:
        first = Demo(work)
        first.check(attaches=1, apps=1, loaded=1)
        record = resident_aes(first.m)
        assert record is not None and record[3] == images['images']['AESVC.PRG']['pages']
        assert data_segment(first.m) is not None, 'attach reserved the RAM-table segment'
        # The loaded bytes equal the file image after the executor patches the
        # callback import; the counters live inside the resident image.
        resident = first.bank1(0, len(component)-2)
        expected = bytearray(component[2:])
        callback = first.symbol('ae_callback')
        expected[22:24] = callback.to_bytes(2, 'little')
        assert resident[:22] == bytes(expected[:22]) and resident[22:24] == bytes(expected[22:24])
        first.key(13); first.check(attaches=1, apps=1, loaded=1)
        first.key(27, exited=True)
        assert resident_aes(first.m) is not None, 'AES must survive the app exit'
        done(f'first app loads AESVC at bank-1 ${AE_BASE:04x} as owner 30; it survives exit', first,
             pages=record[3])

        second = Demo(work, first.m)
        second.check(attaches=2, apps=2, loaded=0)
        assert second.bank1(22, 2) == callback.to_bytes(2, 'little')
        second.key(13); second.check(attaches=2, apps=2, loaded=0)
        second.key(ord('U'), exited=True)
        assert resident_aes(second.m) is None
        assert second.m.stats() == _released(second.m), 'unload returns every page'
        done('second app attaches without loading, sees persisted counters, unloads fully', second)

        third = Demo(work, second.m)
        third.check(attaches=1, apps=1, loaded=1)
        third.key(27, exited=True)
        machine = third.m
        identity = AE_BASE+32
        machine.bus.ram[1][identity] ^= 0x40          # 'N' -> 0x0e: not an AES
        refused = Demo(work, machine)
        refused.check(attaches=0, apps=0, loaded=0, error=0x10)
        refused.key(27, exited=True)
        assert resident_aes(machine) is not None, 'a refused attach leaves the image alone'
        machine.bus.ram[1][identity] ^= 0x40
        callback_bytes = machine.bus.ram[1][AE_BASE+22:AE_BASE+24]
        machine.bus.ram[1][AE_BASE+22:AE_BASE+24] = bytes(2)  # as a partial load leaves it
        partial = Demo(work, machine)
        partial.check(attaches=0, apps=0, loaded=0, error=0x10)
        partial.key(27, exited=True)
        machine.bus.ram[1][AE_BASE+22:AE_BASE+24] = callback_bytes
        again = Demo(work, machine)
        again.check(attaches=2, apps=2, loaded=0)  # the refused apps never registered
        again.key(ord('U'), exited=True)
        assert resident_aes(machine) is None
        done('wrong identity or zero callback import (partial load) refused with BADIMAGE; restored image re-attaches', again)

        heap.Bus = BankedBus
        blocked_machine = heap.Machine()
        blocked_machine.alloc(1, bank=1, owner=29, page=AE_BASE >> 8)  # real heap reserve
        occupied = Demo(work, blocked_machine)
        occupied.check(attaches=0, apps=0, loaded=0, error=occupied.value('demo_error'))
        assert occupied.value('demo_error') not in (0, 4), occupied.value('demo_error')
        assert resident_aes(blocked_machine) is None
        assert blocked_machine.ram[0x3900+(AE_BASE >> 8)] != 0, 'the other owner keeps its page'
        done(f'occupied ${AE_BASE:04x} by another owner: clean allocation refusal, nothing adopted', occupied,
             error=occupied.value('demo_error'))

        for kind, error in (('corrupt', 0x14), ('missing', None)):
            demo = Demo(work, corrupt=kind == 'corrupt', missing=kind == 'missing')
            code = demo.value('demo_error')
            if error is not None:
                assert code == error, code
            else:
                assert code not in (0, 4), code
            demo.check(attaches=0, apps=0, loaded=0, error=code)
            assert resident_aes(demo.m) is None
            demo.key(27, exited=True)
            done(f'{kind} AESVC.PRG refused; no resident image', demo, error=code)
        alert_cases(work, report, done)
        event_cases(work, report, done)
        menu_cases(work, report, done)
        window_cases(work, report, done)
        gadget_cases(work, report, done)
        report['passed'] = True
    finally:
        args.report.write_text(json.dumps(report, indent=2)+'\n')


ALERT = b'[3][Delete NOTES.TXT?|This cannot be undone.][Delete|Cancel]'
BLANK = bytes(8192)+b'\x16'*1024


def alert_cases(work, report, done):
    from native_display_bus import DisplayBus  # VIC/CIA state N_VSHOW requires
    heap.Bus = DisplayBus
    demo = Demo(work, heap.Machine())
    demo.check(attaches=1, apps=1, loaded=1)
    aes = demo.aes_symbols

    def reply():
        return bytes(demo.ram[0x3a00:0x3a06])

    def expect(focus, before=BLANK):
        want, geo = scene.draw(before, ALERT, 2, focus)
        got = demo.surface()
        assert got == want, [(i, a, b) for i, (a, b) in enumerate(zip(got, want)) if a != b][:12]
        return geo

    def saved_pages():
        return [bytes(demo.ram[0x3c00+i*8:0x3c08+i*8]) for i in range(32)
                if demo.ram[0x3c00+i*8] == AES_OWNER and demo.ram[0x3c02+i*8] not in (AE_BASE >> 8, AE_DATA >> 8)]

    demo.key(ord('A'))
    assert demo.alert_open()
    geo = expect(2)
    assert reply()[:2] == bytes([0, 2]) and reply()[2:] == scene.dirty_rows(geo['y'], geo['h'])
    assert len(saved_pages()) == 1, 'one owner-30 save-under allocation while open'
    for key, focus in ((9, 1), (9, 2), (0x9d, 1), (0x9d, 2), (0x1d, 1), (ord('x'), 1)):
        demo.key(key); expect(focus)
        rows = scene.dirty_rows(geo['button_y'], 2) if key != ord('x') else bytes(4)
        assert reply() == bytes([0, focus])+rows, (key, reply())
    demo.key(13)
    assert not demo.alert_open() and demo.surface() == BLANK, 'exact restoration'
    assert reply()[:2] == bytes([1, 1]) and not saved_pages()
    demo.check(attaches=1, apps=1, loaded=1, choice=1)
    done('keyboard alert: exact frame, Tab/cursor focus with row masks, Return, exact restore', demo,
         alert=dict(x=geo['x'], y=geo['y'], w=geo['w'], h=geo['h']))

    for keys, choice in (([ord('2')], 2), ([ord('1')], 1), ([27], 2), ([13], 2)):
        demo.key(ord('A')); expect(2)
        for key in keys:
            demo.key(key)
        assert not demo.alert_open() and demo.surface() == BLANK
        demo.check(attaches=1, apps=1, loaded=1, choice=choice)
    done('digits choose directly, Escape chooses Cancel, Return takes the default', demo)

    def point(x, y, down):
        at = demo.symbol('ae_pointer_x')
        demo.ram[at:at+2] = x.to_bytes(2, 'little')
        demo.ram[demo.symbol('ae_pointer_y')] = y
        demo.ram[demo.symbol('ae_pointer_buttons')] = down
        demo.key(0xff)

    demo.key(ord('A')); expect(2)
    delete_x = geo['button_x'][0]*8+12; bar_y = geo['button_y']*8+8
    point(delete_x, bar_y, 1); expect(1)            # press arms and focuses Delete
    point(20, 20, 0); expect(1)                     # release elsewhere: nothing chosen
    assert demo.alert_open()
    point(delete_x, bar_y, 1); point(delete_x+8, bar_y+4, 0)
    assert not demo.alert_open() and demo.surface() == BLANK
    demo.check(attaches=1, apps=1, loaded=1, choice=1)
    done('1351-style press/release on the same button chooses it; release elsewhere does not', demo)

    # A drawn surface underneath must come back byte for byte.
    pattern = bytes((i*37+11) & 255 for i in range(8192))+bytes((i*7) & 255 for i in range(1024))
    demo.ram[0xc000:0xe400] = pattern
    demo.key(ord('A')); expect(2, pattern)
    demo.key(27)
    assert demo.surface() == pattern
    done('arbitrary pixels and colours under the alert are restored exactly', demo)

    at = demo.symbol('demo_alert')
    original = bytes(demo.ram[at:at+len(ALERT)+1])
    for bad in (b'[3][a|b|c|d|e|f][OK]', b'[4][x][OK]', b'[1][x][]', b'[1][x][A|B|C|D]',
                b'[1]['+b'W'*31+b'][OK]', b'[1][x][OK]junk', b'[1][x][ELEVENCHARS]'):
        assert scene.parse(bad) is None
        demo.ram[at:at+len(bad)+1] = bad+b'\0'
        demo.key(ord('A'))
        assert not demo.alert_open() and not saved_pages() and demo.surface() == pattern
        demo.check(attaches=1, apps=1, loaded=1, choice=2, error=1)
    too_big = b'[1][' + b'|'.join([b'W'*30]*5) + b'][OK]'
    assert scene.parse(too_big) is not None and scene.layout(*scene.parse(too_big)) is None
    demo.ram[at:at+len(too_big)+1] = too_big+b'\0'
    demo.key(ord('A')); assert not demo.alert_open() and not saved_pages()
    demo.ram[at:at+len(original)] = original
    done('malformed strings and alerts over 250 cells are refused before any surface change', demo)
    demo.key(27, exited=True)


def event_cases(work, report, done):
    heap.Bus = BankedBus
    demo = Demo(work, heap.Machine())
    demo.check(attaches=1, apps=1, loaded=1)

    def waiting():
        return demo.ram[demo.symbol('demo_waiting')] == 1

    def resume():
        """Run one more pass of the wait loop without a key (time/pointer moved)."""
        demo.observation_target = None
        demo.keys.append(0)
        demo.loop()

    def jiffy(value):
        demo.ram[0xa0:0xa3] = value.to_bytes(3, 'big')

    def pointer(x, y, buttons):
        at = demo.symbol('ae_pointer_x')
        demo.ram[at:at+2] = x.to_bytes(2, 'little')
        demo.ram[demo.symbol('ae_pointer_y')] = y
        demo.ram[demo.symbol('ae_pointer_buttons')] = buttons

    def params(mask, clicks=1, bmask=1, bstate=1, m1=(0, 0, 0, 0, 0), m2=(0, 0, 0, 0, 0), timer=0):
        at = demo.symbol('ae_ev_params')
        demo.ram[at:at+16] = bytes([mask, clicks, bmask, bstate, *m1, *m2]) + timer.to_bytes(2, 'little')

    def result():
        return demo.data('ae_ev_result', 15)

    jiffy(1000); pointer(0, 0, 0)
    demo.key(ord('E')); assert waiting()
    demo.key(ord('Z')); assert not waiting()
    assert result()[:2] == bytes([1, 0x5a]) and result()[6] == 0
    demo.check(attaches=1, apps=1, loaded=1)
    done('keyboard event returns the key', demo)

    jiffy(0x01fff0)                         # crosses a 16-bit carry during the wait
    demo.key(ord('E')); assert waiting()
    jiffy(0x01fff0+59); resume(); assert waiting()
    jiffy(0x01fff0+60); resume(); assert not waiting() and result()[0] == 32
    done('timer fires at exactly 60 jiffies, not 59, across a carry', demo)

    params(2)
    demo.key(ord('E')); assert waiting()
    pointer(40, 30, 1); resume(); assert not waiting()
    assert result()[0] == 2 and result()[6] == 1 and result()[2:6] == bytes([40, 0, 30, 1])
    demo.key(ord('E')); assert not waiting() and result()[0] == 2, 'GEM: state already matches'
    pointer(40, 30, 0)
    done('button press fires one click; an already-matching state fires at once', demo)

    params(2, clicks=2)
    jiffy(5000); demo.key(ord('E'))
    pointer(0, 0, 1); resume(); assert waiting()
    pointer(0, 0, 0); jiffy(5010); resume(); assert waiting()
    pointer(0, 0, 1); jiffy(5019); resume(); assert not waiting()
    assert result()[0] == 2 and result()[6] == 2
    pointer(0, 0, 0)
    jiffy(6000); demo.key(ord('E'))
    pointer(0, 0, 1); resume(); pointer(0, 0, 0); jiffy(6019); resume(); assert waiting()
    jiffy(6020); resume(); assert not waiting() and result()[6] == 1
    pointer(0, 0, 0)
    jiffy(0x4f1a00-5); demo.key(ord('E'))                  # the clock resets at midnight
    pointer(0, 0, 1); resume(); pointer(0, 0, 0); resume(); assert waiting()
    jiffy(3); resume(); assert not waiting() and result()[6] == 1
    done('double-click inside the 20-jiffy window; the window closing reports one click, '
         'also across the midnight clock reset', demo)

    params(4|8, m1=(0, 10, 10, 5, 5), m2=(1, 0, 0, 4, 4))
    pointer(8, 8, 0); demo.key(ord('E')); assert waiting()           # in rect 2, outside rect 1
    pointer(12*8, 14*8+7, 0); resume(); assert not waiting()          # enters 1 and leaves 2
    assert result()[0] == 4|8
    params(4, m1=(0, 10, 10, 5, 5))
    pointer(15*8, 12*8, 0); demo.key(ord('E')); assert waiting()      # x == 10+5 is outside
    pointer(14*8+7, 10*8, 0); resume(); assert not waiting() and result()[0] == 4
    done('rectangle enter/leave with half-open cell bounds', demo)

    params(16|32, timer=1000)
    jiffy(0); demo.key(ord('P')); demo.key(ord('E'))
    assert not waiting() and result()[0] == 16 and result()[7:] == bytes([41, 0, 7, 0, 1, 2, 3, 4])
    demo.key(ord('E')); assert waiting()
    jiffy(1000); resume(); assert not waiting() and result()[0] == 32
    for n in range(16):
        demo.key(ord('P')); assert demo.value('demo_error') == 0, n
    demo.key(ord('P')); assert demo.value('demo_error') == 2, 'N_NOMEM when 16 are queued'
    done('messages queue in order, deliver once, and refuse a 17th', demo)

    demo.key(27, exited=True)
    other = Demo(work, demo.m)
    other.check(attaches=2, apps=2, loaded=0)
    at = other.symbol('ae_ev_params')
    other.ram[at:at+16] = bytes([16|32, 1, 1, 1]+[0]*10) + (5).to_bytes(2, 'little')
    other.ram[0xa0:0xa3] = bytes(3)
    other.key(ord('E'))
    other.ram[0xa0:0xa3] = (5).to_bytes(3, 'big')
    other.observation_target = None; other.keys.append(0); other.loop()
    assert other.data('ae_ev_result', 1)[0] == 32, 'the previous app\'s messages were discarded'
    other.key(ord('U'), exited=True)
    done('a new app attaching finds an empty queue', other)


MENU = b'Desk:About AES...;File:New^N|Open...^O|-|Quit^Q;Options:Grid|Snap'


def menu_cases(work, report, done):
    from native_display_bus import DisplayBus
    heap.Bus = DisplayBus
    demo = Demo(work, heap.Machine())
    flags = {(1, 1): 2}                    # the demo disables File:Open...

    def frame(**kwargs):
        want, _ = scene.menu_draw(BLANK, MENU, flags=flags, **kwargs)
        got = demo.surface()
        assert got == want, [(i, a, b) for i, (a, b) in enumerate(zip(got, want)) if a != b][:12]

    def resume():
        demo.observation_target = None
        demo.keys.append(0)
        demo.loop()

    def point(x, y, buttons):
        at = demo.symbol('ae_pointer_x')
        demo.ram[at:at+2] = x.to_bytes(2, 'little')
        demo.ram[demo.symbol('ae_pointer_y')] = y
        demo.ram[demo.symbol('ae_pointer_buttons')] = buttons
        resume()

    def chosen():
        return (demo.value('demo_menu_title'), demo.value('demo_menu_item'), demo.value('demo_menu_count'))

    def saved_pages():
        return [1 for i in range(32) if demo.ram[0x3c00+i*8] == AES_OWNER and demo.ram[0x3c02+i*8] not in (AE_BASE >> 8, AE_DATA >> 8)]

    demo.key(ord('M')); frame()
    demo.key(0x85); frame(open_title=0, hover=0)
    assert len(saved_pages()) == 1, 'the drop-down owns one save-under allocation'
    demo.key(0x1d); frame(open_title=1, hover=0)
    demo.key(0x11); frame(open_title=1, hover=3)          # skips disabled Open and the separator
    demo.key(0x91); frame(open_title=1, hover=0)
    demo.key(0x91); frame(open_title=1, hover=3)          # wraps upward
    demo.key(13); frame()
    assert chosen() == (1, 3, 1) and not saved_pages()
    done('F1, cursor keys skip disabled rows, Return chooses File:Quit and restores the bar', demo)

    demo.key(14); frame(); assert chosen() == (1, 0, 2)   # Ctrl-N
    demo.key(15); frame(); assert chosen() == (1, 0, 2)   # Ctrl-O is disabled: a plain key
    assert demo.data('ae_ev_result', 2) == bytes([1, 15])
    done('an enabled shortcut chooses without drawing; a disabled one reaches the app as a key', demo)

    point(11*8+4, 3, 1); frame(open_title=2)               # press on Options
    point(11*8+4, 3, 0); frame(open_title=2)               # release on the title keeps it open
    point(12*8, 2*8+3, 0); frame(open_title=2, hover=0)    # hover Grid
    point(12*8, 3*8+3, 0); frame(open_title=2, hover=1)    # hover Snap
    point(12*8, 2*8+3, 1); point(12*8, 2*8+3, 0)           # click Grid
    flags[(2, 0)] = 1
    frame(); assert chosen() == (2, 0, 3) and demo.value('demo_grid') == 1
    demo.key(0x85); demo.key(0x1d); demo.key(0x1d); frame(open_title=2, hover=0)   # check mark shown
    point(300, 150, 1); frame(); point(300, 150, 0)        # a press elsewhere closes
    assert chosen() == (2, 0, 3)
    done('pointer: open on press, hover, release chooses; set draws the check; press outside closes', demo)

    demo.key(0x85); demo.key(27); frame(); assert chosen() == (2, 0, 3)
    demo.key(27)                                            # Escape with the menu closed ends the loop
    assert not demo.ram[demo.symbol('demo_waiting')] and demo.value('demo_error') == 0
    assert not saved_pages()
    done('Escape closes an open drop-down first, then reaches the app', demo)
    demo.key(27, exited=True)


def window_cases(work, report, done):
    from native_display_bus import DisplayBus
    heap.Bus = DisplayBus
    demo = Demo(work, heap.Machine())
    K = scene.WK
    wins = {
        1: dict(id=1, kind=K['NAME'] | K['CLOSER'] | K['FULLER'] | K['MOVER'],
                x=1, y=2, w=20, h=10, title=b'Alpha'),
        2: dict(id=2, kind=K['NAME'] | K['CLOSER'] | K['INFO'] | K['SIZER'] | K['UP'] | K['DN'] | K['VSLIDE'],
                x=10, y=6, w=18, h=12, title=b'Beta', vpos=64, vsize=128),
        3: dict(id=3, kind=K['NAME'] | K['SIZER'] | K['LF'] | K['RT'] | K['HSLIDE'],
                x=5, y=14, w=24, h=8, title=b'Gamma', hpos=200, hsize=64),
    }
    fills = {1: (0, 0x15), 2: (1, 0xb0), 3: (0, 0x3e)}
    order = [1, 2, 3]

    def expect():
        want = scene.windows_draw([wins[h] for h in order], fills)
        got = demo.surface()
        assert got == want, [(i, a, b) for i, (a, b) in enumerate(zip(got, want)) if a != b][:12]

    def rects_of(h):
        owner = scene.cell_map([wins[i] for i in order])
        g = scene.geometry(wins[h])
        return scene.rectangles(owner, h, (g['wx'], g['wy'], g['ww'], g['wh']))

    def recorded():
        n = demo.value('demo_rect_count')
        raw = demo.data('demo_rects', n*4)
        return [tuple(raw[i:i+4]) for i in range(0, len(raw), 4)]

    demo.key(ord('W')); expect()
    assert demo.data('demo_handles', 3) == bytes([1, 2, 3])
    done('three windows open with every gadget kind; frames and fills match the painter', demo,
         redraws=demo.value('demo_redraws'))

    demo.key(ord('R')); assert recorded() == rects_of(3)
    for key, h in ((ord('1'), 1), (ord('2'), 2), (ord('3'), 3), (ord('1'), 1)):
        demo.key(key); order.remove(h); order.append(h); expect()
    demo.key(ord('R')); assert recorded() == rects_of(1) and len(recorded()) >= 1
    done('topping windows repaints exactly what changed; visible rectangles match', demo,
         rects=len(recorded()))

    demo.key(ord('M')); wins[1].update(x=2, y=3); expect()
    demo.key(ord('S')); wins[1].update(w=22, h=11); expect()
    demo.key(ord('L')); wins[1].update(x=1, y=2); expect()   # changed cells: new left column only
    demo.key(ord('M')); wins[1].update(x=2, y=3); expect()
    demo.key(ord('2')); order.remove(2); order.append(2); expect()
    demo.key(ord('R')); assert recorded() == rects_of(2)
    done('move and size uncover desktop and lower windows exactly', demo)

    demo.key(ord('C')); order.remove(2); expect()
    demo.key(ord('C')); order.remove(order[-1]); expect()
    demo.key(ord('R')); assert recorded() == rects_of(order[-1])
    done('closing the top window uncovers the rest and highlights the new top', demo)

    demo.key(27)
    assert demo.surface() == scene.windows_draw([], fills)
    assert demo.value('demo_error') == 0
    demo.key(ord('W')); order[:] = [1, 2, 3]
    wins[1].update(x=1, y=2, w=20, h=10); expect()      # every slot was deleted and is reusable
    demo.key(27)
    done('Escape closes and deletes all windows; slots are reusable', demo)
    demo.key(27, exited=True)


def gadget_cases(work, report, done):
    from native_display_bus import DisplayBus
    heap.Bus = DisplayBus
    demo = Demo(work, heap.Machine())
    K = scene.WK
    wins = {
        1: dict(id=1, kind=K['NAME'] | K['CLOSER'] | K['FULLER'] | K['MOVER'],
                x=1, y=2, w=20, h=10, title=b'Alpha'),
        2: dict(id=2, kind=K['NAME'] | K['CLOSER'] | K['INFO'] | K['SIZER'] | K['UP'] | K['DN'] | K['VSLIDE'],
                x=10, y=6, w=18, h=12, title=b'Beta', vpos=64, vsize=128),
        3: dict(id=3, kind=K['NAME'] | K['SIZER'] | K['LF'] | K['RT'] | K['HSLIDE'],
                x=5, y=14, w=24, h=8, title=b'Gamma', hpos=200, hsize=64),
    }
    fills = {1: (0, 0x15), 2: (1, 0xb0), 3: (0, 0x3e)}
    order = [1, 2, 3]

    def picture():
        return scene.windows_draw([wins[h] for h in order], fills)

    def expect(want=None):
        want = want or picture()
        got = demo.surface()
        assert got == want, [(i, a, b) for i, (a, b) in enumerate(zip(got, want)) if a != b][:12]

    def point(cx, cy, down):
        """Pointer at the centre of cell (cx, cy)."""
        at = demo.symbol('ae_pointer_x')
        demo.ram[at:at+2] = (cx*8+4).to_bytes(2, 'little')
        demo.ram[demo.symbol('ae_pointer_y')] = cy*8+4
        demo.ram[demo.symbol('ae_pointer_buttons')] = down
        demo.observation_target = None
        demo.keys.append(0)
        demo.loop()

    def click(cx, cy):
        point(cx, cy, 1); point(cx, cy, 0)

    def top(h):
        order.remove(h); order.append(h)

    def outline(rect):
        x, y, w, h = rect
        data = bytearray(picture())
        def xor(x0, y0, x1, y1):
            for py in range(y0, y1):
                for px in range(x0, x1):
                    data[py//8*320+px//8*8+py % 8] ^= 128 >> (px % 8)
        X0, Y0, X1, Y1 = x*8, y*8, (x+w)*8, (y+h)*8
        xor(X0, Y0, X1, Y0+1); xor(X0, Y1-1, X1, Y1)
        xor(X0, Y0+1, X0+1, Y1-1); xor(X1-1, Y0+1, X1, Y1-1)
        return bytes(data)

    def vtrack(win):
        g = scene.geometry(win); k = win['kind']
        track, ty = g['wh'], g['wy']
        if not g['hbar'] and k & K['SIZER']:
            track -= 1
        up = down = None
        if k & K['UP']:
            up = ty; ty += 1; track -= 1
        if k & K['DN']:
            down = ty+track-1; track -= 1
        at, length = scene.thumb(track, win.get('vsize', 255), win.get('vpos', 0))
        return dict(col=win['x']+win['w']-1, up=up, down=down, start=ty, track=track, at=at, len=length)

    def htrack(win):
        g = scene.geometry(win); k = win['kind']
        track, tx = g['ww'], g['wx']
        if not g['vbar'] and k & K['SIZER']:
            track -= 1
        left = right = None
        if k & K['LF']:
            left = tx; tx += 1; track -= 1
        if k & K['RT']:
            right = tx+track-1; track -= 1
        at, length = scene.thumb(track, win.get('hsize', 255), win.get('hpos', 0))
        return dict(row=win['y']+win['h']-1, left=left, right=right, start=tx, track=track, at=at, len=length)

    demo.key(ord('W')); expect()
    gadgets = lambda: demo.value('demo_gadgets')

    click(3, 2); top(1); expect()                          # WM_TOPPED from a lower window's title
    assert gadgets() == 1
    point(5, 2, 1); expect(outline((1, 2, 20, 10)))        # press on the title: outline at the start
    point(8, 4, 1); expect(outline((4, 4, 20, 10)))        # drag: the outline follows
    point(8, 4, 0); wins[1].update(x=4, y=4); expect()     # release: WM_MOVED, the app moves it
    click(23, 4); wins[1].update(x=1, y=2); expect()       # WM_FULLED: back to the full rectangle
    assert gadgets() == 3
    done('topping, dragging the title with an XOR outline, and the full box', demo)

    click(24, 6); top(2); expect()                          # Beta's visible title cells
    point(27, 17, 1); point(25, 15, 1); expect(outline((10, 6, 16, 10)))
    point(25, 15, 0); wins[2].update(w=16, h=10); expect()  # WM_SIZED
    v = vtrack(wins[2])
    click(v['col'], v['up']); wins[2]['vpos'] = 48; expect()
    click(v['col'], v['down']); wins[2]['vpos'] = 64; expect()
    v = vtrack(wins[2])
    click(v['col'], v['start']+v['at']+v['len']); wins[2]['vpos'] = 128; expect()   # page down
    v = vtrack(wins[2])
    click(v['col'], v['start']+v['at']-1 if v['at'] else v['start']); wins[2]['vpos'] = 64; expect()
    v = vtrack(wins[2])
    point(v['col'], v['start']+v['at'], 1); expect()        # the thumb: no outline for sliders
    point(v['col'], v['start']+v['track']-1, 1); point(v['col'], v['start']+v['track']-1, 0)
    wins[2]['vpos'] = 255; expect()                         # WM_VSLID at the end of the track
    done('size box drag, arrows, paging and the vertical thumb drag', demo, gadgets=gadgets())

    click(6, 14); top(3); expect()
    hbar = htrack(wins[3])
    click(hbar['left'], hbar['row']); wins[3]['hpos'] = 184; expect()
    click(hbar['right'], hbar['row']); wins[3]['hpos'] = 200; expect()
    hbar = htrack(wins[3])
    point(hbar['start']+hbar['at'], hbar['row'], 1); point(hbar['start'], hbar['row'], 1)
    point(hbar['start'], hbar['row'], 0); wins[3]['hpos'] = 0; expect()   # WM_HSLID 0
    before = gadgets()
    g = scene.geometry(wins[3])
    click(g['wx']+2, g['wy']+1); expect()                    # the work area belongs to the app
    click(0, 23); expect()                                   # and so does the desktop
    assert gadgets() == before
    done('horizontal arrows and thumb; work-area and desktop presses reach the app', demo)

    # The text sub-op: a string in Alpha's work area, drawn only where Alpha is visible.
    demo.key(ord('2')); order.remove(2); order.append(2); expect()   # Beta above Alpha
    demo.key(ord('T'))
    want = scene.Surface(scene.windows_draw([wins[h] for h in order], fills))
    owner = scene.cell_map([wins[h] for h in order])
    g = scene.geometry(wins[1])
    shown = 0
    for i, c in enumerate(b'Text in Alpha'):
        cx, cy = g['wx']+1+i, g['wy']+5
        if cx < g['wx']+g['ww'] and owner[cy][cx] == 1:
            want.text(cx*8, cy*8, bytes([c])); shown += 1
    got = demo.surface()
    assert 0 < shown < 13, ('the test needs Alpha partly covered', shown)
    assert got == bytes(want.data), [(i, a, b) for i, (a, b) in enumerate(zip(got, want.data)) if a != b][:12]
    demo.key(ord('U')); expect()                            # the same text in pen 0: gone again
    done('the text sub-op draws a string in a window\'s work area, clipped to its visible cells', demo,
         shown=shown)

    click(24, 6); top(2); expect()
    click(10, 6); order.remove(2); expect()                  # Beta's close box
    demo.key(27)
    demo.key(27, exited=True)
    done('the close box closes the window through the app', demo)


if __name__ == '__main__':
    main()
