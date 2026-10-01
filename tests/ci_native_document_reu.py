#!/usr/bin/env python3
"""Execute the shipped Editor document code against independent REU byte arrays."""
import argparse
import hashlib
import json
from pathlib import Path
import random

from ci_native_banked import Banked, ROOT
from ci_native_document import Document
from hwlib import lst_symbol
from native_app_pack import decode
from native_document_reu import physical_bytes


class Symbols(dict):
    def __init__(self, image):
        super().__init__()
        self.image = image

    def __missing__(self, name):
        result = self[name] = lst_symbol('native-desktop/'+self.image, name)
        return result


class Parent(Banked):
    def symbol(self, name):
        return self.ps[name]

    def value(self, name):
        return self.ram[self.symbol(name)]


class SharedDocument(Document):
    span_count_bytes = 3
    def __init__(self, kib=2048):
        packed = (ROOT/'target/native-desktop/editor.prg').read_bytes()
        core = decode(packed)
        provider = (ROOT/'target/native-desktop/vdsvc.prg').read_bytes()
        ps, bs = Symbols('editor'), Symbols('vdsvc')
        # Reserve the complete shipped app allocation, including its module
        # window. Execute the original core and search module bytes unchanged.
        parent = core+bytes(core[12]*256+2-len(core))
        b = self.parent = Parent(parent, provider, ps, bs, kib=kib)
        self.m, self.ram, self.symbols = b.m, b.ram, ps
        module = (ROOT/'target/native-desktop/edfind.prg').read_bytes()
        at = int.from_bytes(module[:2], 'little')
        assert at == ps['editor_module'] and at+len(module)-2 <= 0xc000
        self.ram[at:at+len(module)-2] = module[2:]
        self.workspace = self.m.alloc(16, 0, owner=32, page=0x50)
        self.ram[0x5000:0x6000] = bytes(4096)
        self.protected = []
        foreign = self.m.alloc(2, 1, owner=16, page=4)
        pattern = bytes((i*73+19) & 255 for i in range(512))
        self.m.bus.ram[1][0x400:0x600] = pattern
        self.protected.append((1, 4, pattern, foreign))
        b.load()
        b.call('call', operation=7)
        self.ram[ps['dm_mode']] = 2
        self.ram[ps['dm_lease']] = 1
        self.baseline = self.m.stats()
        self.calls = self.instructions = self.irq_attempts = 0
        self.call('init')
        self.original = bytes(self.m.bus.reu_ram)

    def bytes(self, slot=0):
        state = self.state(slot)
        assert not state['fault']
        assert 0 <= state['gap'] <= state['end'] <= state['capacity']
        assert state['length'] == state['capacity']-(state['end']-state['gap'])
        if not state['capacity']:
            assert state['chunks'] == state['backing'] == 0
            return b''
        data = physical_bytes(self.parent, state)
        return data[:state['gap']]+data[state['end']:]

    def dispose(self):
        for slot in (0, 128):
            self.call('dispose', slot=slot)
        assert self.m.stats() == self.baseline
        b = self.parent
        b.call('call', operation=13)
        b.call('call', operation=0)
        b.call('close')
        for token, owner in ((self.workspace, 32), (b.app, 32), (self.protected[0][3], 16)):
            self.m.select(token, owner)
            self.m.invoke('free')
        assert self.m.stats() == (175, 251, 32)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    report = dict(passed=False, physical_hardware_io=False, cases=[], images={
        name: hashlib.sha256((ROOT/'target/native-desktop'/name).read_bytes()).hexdigest()
        for name in ('editor.prg', 'edfind.prg', 'vdsvc.prg')})

    def done(name, d):
        report['cases'].append(dict(name=name, calls=d.calls, instructions=d.instructions,
            irq_attempts=d.irq_attempts, dmas=len(d.m.bus.reu_transactions)))
        print('PASS:', name, flush=True)

    try:
        d = SharedDocument()
        want = bytearray((i*17+(i>>8)*31) & 255 for i in range(0x100021))
        d.append(want)
        d.check(want)
        assert d.state()['capacity'] == 257*4096 and d.m.stats() == d.baseline
        for offset in (0xfffd, 0x17fff, 0x1fffd, 0xffffd, 0x100001):
            assert d.call('read', pos=offset, count=512) == want[offset:offset+512]
        d.call('insert', pos=0x100001, data=b'EXTENDED', interrupt=True)
        want[0x100001:0x100001] = b'EXTENDED'
        d.check(want)
        d.call('replace', pos=0xffffd, count=13, data=bytes(range(256))*2, interrupt=True)
        want[0xffffd:0xffffd+13] = bytes(range(256))*2
        d.check(want)
        d.call('delete', pos=0x100001, count=511)
        del want[0x100001:0x100001+511]
        d.check(want)
        state = d.state()
        context_at = d.symbols['d_states']
        original_context = bytes(d.ram[context_at:context_at+128])
        for field, value in ((15, 2), (13, 2)):
            d.ram[context_at+field] = value
            transactions = len(d.m.bus.reu_transactions)
            d.call('read', pos=0, count=1, expected=9)
            assert len(d.m.bus.reu_transactions) == transactions
            d.ram[context_at:context_at+128] = original_context
        assert d.state() == state
        d.call('replace', pos=0xffff, count=0x20003, data=b'\0BIG\xff', interrupt=True)
        want[0xffff:0xffff+0x20003] = b'\0BIG\xff'
        d.check(want)
        d.call('replace', pos=len(want), count=0, data=b'TAIL')
        want.extend(b'TAIL')
        d.check(want)
        state = d.state()
        d.call('replace', pos=0, count=len(want)+1, data=b'NO', expected=6)
        assert d.state() == state and d.bytes() == want
        d.call('replace', pos=0, count=len(want), data=b'')
        d.check(b'')
        d.dispose()
        done('document beyond 1 MiB: 24-bit removal, zero-length insertion and range refusal; 24-bit reads/edits, 16-bit page count, IRQs, metadata refusal and exact bytes', d)

        d = SharedDocument(kib=512)
        first = bytearray(bytes(range(256))*16)
        second = bytearray(b'OTHER DOCUMENT\0\xff'*300)
        d.append(first)
        old_token = d.state()['handles'][:8]
        d.append(second, slot=128)
        second_token = d.state(128)['handles'][:8]
        d.call('insert', pos=2047, data=b'GROW\0\xff'*73, interrupt=True)
        first[2047:2047] = b'GROW\0\xff'*73
        assert d.state()['handles'][:8] != old_token
        assert d.state(128)['handles'][:8] == second_token
        d.check(first)
        d.check(second, slot=128)
        rng = random.Random(12878214)
        for _ in range(32):
            slot = rng.choice((0, 128))
            wanted = first if slot == 0 else second
            at = rng.randrange(len(wanted))
            count = rng.randrange(1, min(512, len(wanted)-at)+1)
            data = rng.randbytes(rng.randrange(513))
            d.call('replace', pos=at, count=count, data=data, slot=slot)
            wanted[at:at+count] = data
            assert d.bytes() == first and d.bytes(128) == second
            assert d.m.stats() == d.baseline
        d.check(first)
        d.check(second, slot=128)
        d.dispose()
        done('two contexts, relocated growth and 32 random replacements retain the other document and main RAM', d)
        report['passed'] = True
    finally:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
