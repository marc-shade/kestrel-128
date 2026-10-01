#!/usr/bin/env python3
"""Execute the shipped banked history against an independent byte-edit model."""
import argparse
import hashlib
import json
from pathlib import Path
import traceback

from ci_native_document_reu import SharedDocument, ROOT


class History:
    def __init__(self, reu=False):
        self.document = SharedDocument(kib=512)
        self.b = self.document.parent
        self.ram = self.b.ram
        if not reu:
            self.b.call('call', operation=13)
            self.ram[self.b.ps['dm_lease']] = 0
        self.before = self.b.m.stats()

    def call(self, op, data=None, count=None, expected=0, **options):
        if data is not None:
            self.ram[0x3a00:0x3a00+len(data)] = data
        if count is not None:
            self.ram[0x3d0a:0x3d0c] = count.to_bytes(2, 'little')
        self.b.call('call', operation=op, expected=expected, **options)
        return bytes(self.ram[0x3a00:0x3c00])

    def info(self):
        answer = self.call(15)[:4]
        assert answer[3] == 1
        return tuple(answer[:3])

    def begin(self, position, removed, inserted, **kw):
        return self.call(16, b''.join(v.to_bytes(3, 'little')
                                    for v in (position, removed, inserted)), **kw)

    def append(self, data):
        for offset in range(0, len(data), 511):
            chunk = data[offset:offset+511]
            self.call(17, chunk, len(chunk))

    def edit(self, text, position, remove, insert):
        self.begin(position, remove, len(insert))
        self.append(text[position:position+remove])
        self.append(insert)
        self.call(18)
        return text[:position]+insert+text[position+remove:]

    def replay(self, text, redo=False):
        header = self.call(21 if redo else 20)
        position, remove, length = (int.from_bytes(header[n:n+3], 'little')
                                    for n in (0, 3, 6))
        assert 0 <= position <= position+remove <= len(text)
        value = bytearray()
        while len(value) < length:
            size = min(512, length-len(value))
            value.extend(self.call(22, count=size)[:size])
        self.call(23)
        return text[:position]+value+text[position+remove:]

    def close(self):
        self.call(26, b'\0')
        assert self.info() == (0, 0, 0)
        assert self.b.m.stats() == self.before
        self.document.dispose()


def fail_once(address, error):
    fired = []
    def hook(cpu, bus, steps):
        if not fired and cpu.pc == address and bus.config == 0x0e:
            fired.append(steps)
            cpu.a = error
            cpu.p |= 1
            cpu.pc = (cpu.stPopWord()+1) & 65535
    return hook, fired


def sequence(reu):
    h = History(reu)
    assert h.info() == (0, 0, 0)
    text = b''
    states = [text]
    for n in range(21):
        text = h.edit(text, len(text), 0, bytes([65+n]))
        states.append(text)
        if n == 9:
            h.call(25)
            assert h.info()[0] == 0
    assert h.info() == (1, 16, 0)
    for n in range(20, 4, -1):
        text = h.replay(text)
        assert text == states[n]
        assert h.info()[0] == int(n != 10)
    h.call(20, expected=6)
    for n in range(6, 22):
        text = h.replay(text, True)
        assert text == states[n]
        assert h.info()[0] == int(n != 10)
    h.call(21, expected=6)
    text = h.replay(h.replay(text))
    original = text
    text = h.edit(text, 2, 7, b'NEW')
    h.call(21, expected=6)
    assert h.replay(text) == original
    h.call(24, b'\1')
    assert h.info() == (1, 0, 0)
    h.close()
    return dict(name='REU' if reu else 'RAM', calls=h.b.calls, instructions=h.b.instructions,
                retained_steps=16, result_sha256=hashlib.sha256(text).hexdigest())


def transaction_faults():
    h = History()
    text = h.edit(b'ABCD', 1, 2, b'xyz')
    h.begin(0, 0, 3)
    h.append(b'A')
    h.call(18, expected=1)
    assert h.info() == (1, 1, 0)
    h.call(17, b'OVER', count=4, expected=6)
    h.call(19)
    assert h.replay(text) == b'ABCD'
    h.replay(b'ABCD', True)
    hook, fired = fail_once(0x1c20, 2)
    h.begin(1, 0, 1, interrupt=hook, expected=2)
    assert fired and h.info() == (1, 1, 0)
    h.begin(0, 0, 1)
    hook, fired = fail_once(0x1c29, 9)
    h.call(17, b'Q', count=1, interrupt=hook, expected=9)
    assert fired
    h.call(18, expected=1)
    h.call(19)
    assert h.replay(text) == b'ABCD'
    # Cancel a prepared replay after a caller-side reservation failure.
    h.call(21)
    h.call(19)
    assert h.info() == (0, 0, 1)
    assert h.replay(b'ABCD', True) == text
    hook, fired = fail_once(0x1c23, 9)
    h.call(26, b'\1', interrupt=hook, expected=9)
    assert fired and h.info() == (1, 0, 0)
    h.call(0, expected=1)
    h.close()
    return dict(name='unpublished records, refusal, transfer fault and retained free retry',
                calls=h.b.calls, instructions=h.b.instructions)


def large_span():
    h = History(True)
    original = bytes((n*73+19) & 255 for n in range(196673))
    changed = h.edit(original, 65530, 131119, b'\0RESTORED\xff')
    assert h.replay(changed) == original
    assert h.replay(original, True) == changed
    h.close()
    return dict(name='24-bit position and 131119-byte removed span', calls=h.b.calls,
                instructions=h.b.instructions, original_sha256=hashlib.sha256(original).hexdigest(),
                result_sha256=hashlib.sha256(changed).hexdigest())


def reu_faults():
    h = History(True)
    text = h.edit(b'ABCD', 1, 1, b'EF')
    h.begin(0, 0, 512)
    bus = h.b.m.bus
    bus.reu_fault_prefix = 128
    bus.reu_faults.add(len(bus.reu_transactions)+1)
    h.call(17, bytes(range(256))*2, count=512, expected=17)
    h.call(18, expected=1)
    bus.reu_faults.clear()
    h.call(19)
    assert h.info() == (1, 1, 0)
    h.call(20)
    bus.reu_fault_prefix = 0
    bus.reu_faults.add(len(bus.reu_transactions)+1)
    h.call(22, count=1, expected=17)
    h.call(23, expected=1)
    bus.reu_faults.clear()
    assert h.call(22, count=1)[:1] == b'B'
    h.call(23)
    assert h.replay(b'ABCD', True) == text
    h.begin(0xffffff, 0xffffff, 1, expected=2)
    assert h.info() == (1, 1, 0)
    h.close()
    return dict(name='partial REU write, replay read retry and overflowing record refusal',
                calls=h.b.calls, instructions=h.b.instructions)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    report = dict(passed=False, physical_hardware_io=False, cases=[], images={
        name: hashlib.sha256((ROOT/'target/native-desktop'/name).read_bytes()).hexdigest()
        for name in ('editor.prg', 'edfind.prg', 'vdsvc.prg')})
    try:
        for run in (lambda: sequence(False), lambda: sequence(True), transaction_faults, large_span, reu_faults):
            result = run()
            report['cases'].append(result)
            print('PASS', result, flush=True)
        report['passed'] = True
    except BaseException:
        report['error'] = traceback.format_exc()
        raise
    finally:
        args.report.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
