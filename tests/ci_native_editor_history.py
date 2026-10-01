#!/usr/bin/env python3
"""Drive actual Editor undo/redo through keys, file operations and mouse buttons."""
import argparse
import hashlib
import json
from pathlib import Path
import traceback

import ci_native_editor_gui as gui


def hold_free(e, leave=0):
    held = []
    stack = bytes(e.ram[0x100:0x200])
    for bank in (0, 1):
        table = e.ram[0x3800+bank*256:0x3900+bank*256]
        start = 0
        while start < 255:
            if table[start]:
                start += 1
                continue
            end = start+1
            while end < 255 and not table[end]:
                end += 1
            if leave and end-start >= leave:
                start += leave
                leave = 0
            if start == end:
                continue
            token = e.m.alloc(end-start, bank, owner=16, page=start)
            held.append((token, bank, start, end, bytes(e.bus.ram[bank][start*256:end*256])))
            start = end
    e.ram[0x100:0x200] = stack
    assert not leave
    return held


def release(e, held):
    stack = bytes(e.ram[0x100:0x200])
    for token, bank, start, end, original in held:
        assert bytes(e.bus.ram[bank][start*256:end*256]) == original
        e.m.select(token, 16)
        e.m.invoke('free')
    e.ram[0x100:0x200] = stack


def basic(e):
    e.type('ABC')
    e.check(b'ABC', 3, True)
    for want in (b'AB', b'A', b''):
        e.key(26)
        e.check(want, len(want), bool(want), status=27)
    e.key(26)
    e.check(b'', 0, False, status=31)
    e.key(25)
    e.check(b'A', 1, True, status=28)
    e.prompt(0x86, 'SAVED')
    e.check(b'A', 1, False, status=1, name='SAVED')
    e.key(25)
    e.check(b'AB', 2, True, status=28)
    e.key(26)
    e.check(b'A', 1, False, status=27)
    e.type('!')
    e.check(b'A!', 2, True)
    e.key(25)
    e.check(b'A!', 2, True, status=31)
    e.key(26)
    e.check(b'A', 1, False, status=27)
    e.exit()


def mutations(e, raw):
    e.prompt(0x85, 'SOURCE')
    e.key(1)
    e.type('X')
    e.check(b'X', 1, True)
    e.key(26)
    e.check(raw, len(raw), False, status=27)
    e.key(25)
    e.check(b'X', 1, True, status=28)
    e.key(1)
    e.key(24)
    e.check(b'', 0, True, status=20)
    e.key(26)
    e.check(b'X', 1, True, status=27)
    e.key(22)
    e.check(b'XX', 2, True, status=21)
    e.key(18)
    e.type('X')
    e.key(13)
    e.type('YZ')
    e.key(13)
    e.type('A')
    e.check(b'YZYZ', dirty=True, status=17)
    assert e.number('ed_s_count') == 2
    for key, want, cursor in ((26, b'YZX', 3), (26, b'XX', 1),
                              (25, b'YZX', 2), (25, b'YZYZ', 4)):
        e.key(key)
        e.check(want, cursor, True, status=27 if key == 26 else 28)
    e.prompt(0x86, 'REPLACED')
    assert bytes(e.io.files[9, b'REPLACED', b'S']) == b'YZYZ'
    e.key(0x87)
    e.check(b'', 0, False)
    e.key(26)
    e.check(b'', 0, False, status=31)
    e.exit()


def large(e, raw):
    e.prompt(0x85, 'SOURCE')
    assert e.state()['backing'] == 1
    e.key(1)
    e.type('X')
    e.check(b'X', 1, True)
    e.key(26)
    e.check(raw, len(raw), False, status=27)
    e.key(25)
    e.check(b'X', 1, True, status=28)
    e.key(26)
    e.check(raw, len(raw), False, status=27)
    e.prompt(0x86, 'RESTORED')
    assert bytes(e.io.files[9, b'RESTORED', b'S']) == raw
    e.exit()


def memory(e, raw):
    e.prompt(0x85, 'SOURCE')
    e.key(0x8a)
    assert e.value('eh_available')
    vdc = bool(e.value('vd_phase'))
    held = hold_free(e, leave=16 if vdc else 0)
    assert sum(e.m.stats()[:2]) == (16 if vdc else 0)
    e.type('Q')
    e.check(raw+b'Q', len(raw)+1, True, status=30)
    assert bool(e.value('eh_available')) == vdc
    assert bool(e.value('bk_state')) == vdc
    held += hold_free(e)
    assert sum(e.m.stats()[:2]) == 0
    e.type('R')
    e.check(raw+b'QR', len(raw)+2, True, status=30)
    e.key(26)
    e.check(raw+b'QR', len(raw)+2, True, status=31)
    release(e, held)
    e.key(0x87)
    e.type('Y')
    e.check(b'', 0, False)
    assert e.value('eh_available')
    e.type('F')
    e.key(26)
    e.check(b'', 0, False, status=27)
    e.exit()


def mouse(e):
    e.type('AB')
    e.frame()
    for _ in range(4):
        e.click(5)
    assert e.value('eg_more') == 4
    e.click(27)
    e.check(b'A', 1, True, status=27)
    e.click(28)
    e.check(b'AB', 2, True, status=28)
    e.click(29)
    e.check(b'AB', 2, True, status=29)
    e.key(26)
    e.check(b'AB', 2, True, status=31)
    e.exit(dirty=True)


def recovery(e):
    assert not e.value('eh_available')
    e.type('W')
    e.check(b'W', 1, True, status=30)
    e.io.files[8, b'VDSVC.PRG', b'P'] = (gui.ROOT/'target/native-desktop/vdsvc.prg').read_bytes()
    e.key(12)
    assert e.value('eh_available')
    e.type('R')
    e.key(26)
    e.check(b'W', 1, True, status=27)
    e.prompt(0x86, 'RECOVERED')
    e.key(25)
    e.check(b'WR', 2, True, status=28)
    e.key(26)
    e.check(b'W', 1, False, status=27)
    e.exit()


def transfer_fault(e):
    from ci_native_reu_calc import component
    e.type('AB')
    e.key(20)
    e.check(b'A', 1, True)
    record = component(e, 'bh_records', 27)[18:27]
    assert record[0] == 1
    original_step = e.cpu.step
    reads = []
    def step():
        if e.cpu.pc == 0x1c26 and bytes(e.ram[0x3d04:0x3d08]) == record[1:5]:
            reads.append(e.instructions)
            if len(reads) == 2:
                e.cpu.a = 9
                e.cpu.p |= 1
                e.cpu.pc = (e.cpu.stPopWord()+1) & 65535
                return
        return original_step()
    e.cpu.step = step
    try:
        e.key(26)
    finally:
        e.cpu.step = original_step
    assert len(reads) == 2 and e.state()['fault'] == 9
    assert e.value('ed_status') == 5
    assert component(e, 'bh_replay') == b'\0'
    e.prompt(0x86, 'REFUSED')
    assert (9, b'REFUSED', b'S') not in e.io.files
    if e.value('ed_mode'):
        e.key(27)
    e.key(0x87)
    e.type('Y')
    e.check(b'', 0, False)
    e.type('Z')
    e.key(26)
    e.check(b'', 0, False, status=27)
    e.exit()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=('basic', 'mutations', 'large', 'memory', 'mouse', 'recovery', 'transfer_fault'), required=True)
    parser.add_argument('--vdc-kib', type=int, choices=(16, 64))
    parser.add_argument('--reu-kib', type=int, choices=(128, 512, 16384))
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    factory = gui.GraphicalEditor
    if args.vdc_kib:
        from ci_native_vdc_editor import Editor
        from ci_native_vdc_desktop import VDCBus
        base = VDCBus
        options = dict(size=args.vdc_kib, addressing=16)
        if args.reu_kib:
            from ci_native_reu_calc import CalculatorBus
            base = CalculatorBus
            options['reu_kib'] = args.reu_kib
        gui.PointerBus = type('HistoryDisplay', (base,), options)
        factory = Editor
    report = dict(passed=False, physical_hardware_io=False, vdc_kib=args.vdc_kib,
                  reu_kib=args.reu_kib, cases=[], images={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in (gui.ROOT/'target/native-desktop').glob('*.prg')})
    try:
        raw = b'ONE\r\nTwo words\nLAST\0\xff'
        if args.case == 'memory':
            raw = (b'0123456789 ABCDEFGHIJ\r\n'*300)[:4096]
        if args.case == 'large':
            assert args.reu_kib
            raw = (b'0123456789 ABCDEFGHIJ\r\n'*6300)[:131118]
        options = {'vdc_component': False} if args.case == 'recovery' else {}
        e = factory({(9, b'SOURCE', b'S'): raw}, device=9, fmt=2, **options)
        print('READY', args.case, e.m.stats(), flush=True)
        if args.case in ('mutations', 'memory', 'large'):
            globals()[args.case](e, raw)
        else:
            globals()[args.case](e)
        e.restored()
        report['cases'].append(dict(name=args.case, instructions=e.instructions, checked=e.checked,
                                   frames=e.frames, module_calls=e.module_calls))
        report['passed'] = True
        print('PASS', report['cases'], flush=True)
    except BaseException:
        report['error'] = traceback.format_exc()
        raise
    finally:
        args.report.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
