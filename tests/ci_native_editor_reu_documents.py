#!/usr/bin/env python3
"""Actual Editor REU documents: large files, transactional limits and faults."""
import argparse
import json
from pathlib import Path

from ci_native_vdc_editor_recovery import RecoveryEditor
from ci_native_vdc_editor import gui
from ci_native_reu_calc import CalculatorBus, component, COMPONENT_PAGES
from native_document_reu import extent
from native_picker_fixture import Picker
from ci_native_browser import expected

H_STEPS = 16                  # src/native/history-api.inc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=('large', 'capacity', 'transfer', 'no_vdc', 'probe', 'file_close'), required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    original_bus = gui.PointerBus
    report = dict(passed=False, physical_hardware_io=False, cases=[])
    raw = (b'0123456789ABCDEF\r\n'*8000)[:131113]
    files = {(9, b'LARGE', b'S'): raw, (9, b'MEDIUM', b'S'): raw[:107019]}
    options = dict(size=64, reu_kib=128 if args.case == 'capacity' else 512)
    if args.case in ('no_vdc', 'probe'):
        options['present'] = False
    if args.case == 'probe':
        options['fault_start'] = 2

    def checked(p, want, **kw):
        p.check(want, **kw)
        if want:
            assert p.state()['backing'] == 1 and p.banks == {'reu'}
            assert sum(p.m.stats()[:2]) == 426-96-16-36-COMPONENT_PAGES

    def history_extents(p):
        """REU span-history records (docs/NATIVE-HISTORY.md: owner 33, like the
        document), from the history service's table checked against the arena."""
        table = component(p, 'bh_records', (H_STEPS+1)*9)
        records = component(p, 'ru_records', 256)
        found = {}
        for at in range(0, len(table), 9):
            if table[at] != 2:
                continue
            token = table[at+1:at+9]
            assert 1 <= token[0] <= 32 and token[4:] == component(p, 'ru_cookie', 4)
            record = records[(token[0]-1)*8:token[0]*8]
            assert record[0] == 33 and record[5:8] == token[1:4]
            start, units = int.from_bytes(record[1:3], 'little'), int.from_bytes(record[3:5], 'little')
            assert units > 0
            found[token[0]] = (start*4096, units*4096)
        return found

    try:
        gui.PointerBus = type('DocumentREU', (CalculatorBus,), options)
        p = RecoveryEditor(files, device=9, fmt=2)
        print('Started Editor:', args.case, p.instructions, 'instructions', flush=True)
        if args.case == 'large':
            checked(p, b'')
            p.type('KEEP')
            kept = history_extents(p)
            assert len(kept) == 4                               # one span per typed key
            history = list(kept.values())
            old_start, old_count = extent(p, p.state())
            snapshot_bytes = p.value('vd_pages')*256
            tokens = p.data('vs_token', 8)+p.data('bk_handle', 4)
            p.prompt(0x85, 'LARGE', confirm='Y')
            checked(p, raw, cursor=0, dirty=False, name='LARGE')
            assert p.state()['capacity'] > 96*1024
            first_start, first_count = extent(p, p.state())
            want = raw
            for offset, inserted in ((65537, b'C128'), (98305, b'REU96')):
                p.prompt(0x88, f'{offset:06X}')
                at = offset+(want[offset-1:offset+1] == b'\r\n')
                checked(p, want, cursor=at)
                p.type(inserted.decode())
                history += history_extents(p).values()
                want = want[:at]+inserted+want[at:]
                checked(p, want, cursor=at+len(inserted), dirty=True)
            p.key(0x86)
            p.type('COPY')
            contexts = p.data('d_states', 256)
            p.key(0x88)
            rows = expected(p.io.files, 9)
            for row in rows:
                row['app'] = False
            Picker(p).check(rows, mode=2, device=9, fmt=2)
            p.mirror()
            assert p.contents() == want and p.data('d_states', 256) == contexts
            p.key(27)
            p.key(13)
            checked(p, want, dirty=False, status=1, name='COPY')
            assert bytes(p.io.files[9, b'COPY', b'S']) == want
            assert bytes(p.io.files[9, b'LARGE', b'S']) == raw
            p.key(0x87)
            checked(p, b'', cursor=0, dirty=False)
            p.prompt(0x85, 'COPY')
            checked(p, want, cursor=0, dirty=False, name='COPY')
            last_start, last_count = extent(p, p.state())
            assert p.data('vs_token', 8)+p.data('bk_handle', 4) == tokens
            p.exit()
            p.restored()
            low = min(old_start, first_start, last_start)
            high = max(old_start+old_count, first_start+first_count, last_start+last_count)
            # Outside the display snapshot, the documents and the history spans
            # (released at exit, contents retained), every REU byte is unchanged.
            ram, original = p.bus.reu_ram, p.bus.reu_original
            assert any(ram[s:s+c] != original[s:s+c] for s, c in kept.values()), 'history spans reached the REU'
            edge = 0
            for start, end in sorted((s, s+c) for s, c in [(0, snapshot_bytes), (low, high-low)]+history):
                if start > edge:
                    assert ram[edge:start] == original[edge:start], ('REU changed', hex(edge), hex(start))
                edge = max(edge, end)
            assert ram[edge:] == original[edge:], ('REU changed', hex(edge))
            records = component(p, 'ru_records', 256, released=True)
            assert all(records[at] == 0 for at in range(0, 256, 8))
            description = '128 KiB file: edits across 64/96 KiB, retained picker, exact verified Save As and reopen'
        elif args.case == 'capacity':
            p.type('KEEP')
            checked(p, b'KEEP', cursor=4, dirty=True)
            token = p.state()['handles'][:8]
            p.prompt(0x85, 'LARGE', confirm='Y')
            checked(p, b'KEEP', cursor=4, dirty=True, status=3)
            assert p.state()['handles'][:8] == token
            pending = p.state(p.value('ed_active') ^ 128)
            assert pending['capacity'] == pending['chunks'] == pending['backing'] == 0
            records = component(p, 'ru_records', 256)
            # The staged document was returned: owner 33 is the kept document and
            # its four history spans (a failed Open retains history, NATIVE-HISTORY.md).
            spans = history_extents(p)
            assert len(spans) == 4 and token[0] not in spans
            assert {at//8+1 for at in range(0, 256, 8) if records[at] == 33} == {token[0], *spans}
            p.prompt(0x86, 'KEPT')
            assert bytes(p.io.files[9, b'KEPT', b'S']) == b'KEEP'
            p.key(0x87)
            p.prompt(0x85, 'MEDIUM')
            checked(p, raw[:107019], cursor=0, dirty=False)
            assert p.state()['capacity'] == 27*4096
            p.exit()
            p.restored()
            description = '128 KiB REU: failed staged Open retains dirty original; freed capacity accepts a >96 KiB document'
        elif args.case == 'transfer':
            p.type('KEPT')
            checked(p, b'KEPT', cursor=4, dirty=True)
            old = p.state()
            step, injected = p.cpu.step, []
            def fail_write():
                if p.cpu.pc == p.symbol('dm_write') and not injected:
                    injected.append(len(p.bus.reu_transactions)+1)
                    p.bus.reu_faults.add(injected[0])
                return step()
            p.cpu.step = fail_write
            try:
                p.type('X')
            finally:
                p.cpu.step = step
            assert injected and p.state()['fault'] == 17
            assert p.state()['length'] == old['length'] and p.state()['handles'] == old['handles']
            assert p.value('ed_status') == 5 and p.value('vd_fault') == 0
            opened = len(p.io.events)
            p.prompt(0x86, 'INVALID')
            assert (9, b'INVALID', b'S') not in p.io.files and len(p.io.events) == opened
            p.key(0x87)
            p.type('Y')
            checked(p, b'', cursor=0, dirty=False)
            p.type('GOOD')
            p.prompt(0x86, 'RECOVERED')
            checked(p, b'GOOD', dirty=False, status=1)
            assert bytes(p.io.files[9, b'RECOVERED', b'S']) == b'GOOD'
            p.exit()
            p.restored()
            description = 'failed document DMA retains and poisons its allocation, refuses Save As, and permits New/recovery'
        elif args.case == 'file_close':
            p.type('KEPT')
            p.io.fail_close = 122
            p.prompt(0x86, 'UNCERTAIN')
            p.check(b'KEPT', 4, True, status=9, released=False)
            contexts = p.data('d_states', 256)
            p.key(27)
            p.check(b'KEPT', mode=5, released=False)
            heap, step, count = p.m.stats(), p.cpu.step, [0]
            class Quarantined(Exception):
                pass
            def stop_at_return():
                count[0] += 1
                result = step()
                if p.cpu.pc == 0xb00 and p.cpu.sp == 0xe0:
                    raise Quarantined
                return result
            p.cpu.step = stop_at_return
            try:
                p.key(ord('Y'), exited=True)
            except Quarantined:
                p.events += 1
                p.instructions += count[0]
            else:
                raise AssertionError('uncertain file owner was not quarantined')
            finally:
                p.cpu.step = step
            assert p.ram[0x3d20] == 32 and p.ram[0x3d23] == 4 and p.ram[0x3d27] == 17
            assert p.data('d_states', 256) == contexts and p.contents() == b'KEPT'
            assert p.m.stats() == heap and p.value('dm_lease') == p.value('bk_state')-1 == 1
            assert p.value('vd_phase') == 0 and p.bus.video_ram == p.bus.original[0]
            assert p.ram[0x1000:0x1100] == p.original_keys
            assert int.from_bytes(p.ram[0x3d13:0x3d15], 'little') == p.events
            description = 'uncertain file CLOSE restores the display and keys while quarantining both document and provider'
        elif args.case == 'no_vdc':
            assert p.value('vd_phase') == 0 and p.value('dm_mode') == 2
            p.type('REU WITHOUT VDC')
            checked(p, b'REU WITHOUT VDC', dirty=True)
            p.prompt(0x86, 'TEXT')
            checked(p, b'REU WITHOUT VDC', dirty=False, status=1)
            assert bytes(p.io.files[9, b'TEXT', b'S']) == b'REU WITHOUT VDC'
            p.exit()
            p.restored()
            description = 'REU documents work when the VDC is unavailable'
        else:
            assert p.value('vd_phase') == 0 and p.value('dm_fault') == 17
            assert p.value('dm_lease') == 1 and component(p, 'ru_probe_live') == b'\1'
            contexts = p.data('d_states', 256)
            for key in (ord('A'), 13, 0x86, 27):
                p.key(key)
                assert p.data('d_states', 256) == contexts and p.value('dm_lease')
            p.bus.reu_fault_from = None
            p.key(27, exited=True)
            p.restored()
            assert p.bus.reu_ram == p.bus.reu_original
            assert p.value('dm_lease') == p.value('dm_fault') == 0
            description = 'memory-only probe restoration retains the provider and blocks edits/exit until exact recovery'
        report['cases'].append(dict(name=description, passed=True, instructions=p.instructions,
            keys=p.events, checked=p.checked, dmas=len(p.bus.reu_transactions),
            main_ram_pages=426-96-16-36-COMPONENT_PAGES))
        report['passed'] = True
        print('PASS:', description, flush=True)
    finally:
        gui.PointerBus = original_bus
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
