#!/usr/bin/env python3
"""Execute the REU module cache: boot probe, cold/warm loads and fallbacks.

Runs the assembled kernel with the IEC/UCI file fixtures of ci_native_modules
and the REC model of native_reu_bus (pinned VICE reu.c behaviour). Software
only: no VICE run, no physical REU.
"""
import argparse
import hashlib
import json
from pathlib import Path

from py65.devices.mpu6502 import MPU
import ci_native_heap as heap
from ci_native_heap import symbol
from native_reu_bus import REUBusMixin
import ci_native_modules as mods

RCACHE = 0x3d9f
BASE, END = mods.BASE, mods.END


def bus_class(kib, present=True):
    class CacheBus(REUBusMixin, heap.Bus):
        reu_kib = kib
        reu_present = present
        def __init__(self):
            super().__init__()
            self.reu_hosts = [(0x3a00, 0x3c00), (BASE, END)]
    return CacheBus


def run_cpu(bus, entry, limit=2000000):
    cpu = MPU(memory=bus, pc=entry); cpu.sp = 0xe0; cpu.p = 0x24; cpu.stPushWord(0xaff)
    for _ in range(limit):
        if cpu.pc == 0xb00 and cpu.sp == 0xe0:
            return cpu
        cpu.step()
    raise AssertionError(('did not return', hex(cpu.pc)))


class Cache(mods.Modules):
    def __init__(self, kib=512, present=True, fmt=0, probe=True):
        saved = heap.Bus
        heap.Bus = bus_class(kib, present)
        try:
            super().__init__(fmt=fmt)
        finally:
            heap.Bus = saved
        self.bus = self.c.m.bus.native if hasattr(self.c.m.bus, 'native') else self.c.m.bus
        self.opens = 0
        if probe:
            self.reu_before = bytes(self.bus.reu_ram)
            run_cpu(self.c.m.bus, symbol('rc_probe'))

    def bank(self):
        return self.ram[symbol('rc_bank')]

    def directory(self):
        base = self.bank()*65536
        return bytes(self.bus.reu_ram[base:base+256])

    def call(self, entry, *args, **kwargs):
        opened = symbol('fs_open')
        stub = self.c.io.stub
        def counting(cpu):
            if cpu.pc == opened:
                self.opens += 1
            return stub(cpu)
        self.c.io.stub = counting
        try:
            return super().call(entry, *args, **kwargs)
        finally:
            self.c.io.stub = stub

    def load(self, expected=0, name=mods.NAME):
        self.ram[BASE:END] = b'\xcc'*(END-BASE)
        self.name(name)
        before = self.opens
        self.call(mods.LOAD, expected)
        return self.opens-before


def entries(directory):
    count = directory[0]
    rows = []
    for i in range(count):
        e = directory[2+i*22:2+(i+1)*22]
        rows.append(dict(name=bytes(e[1:1+e[0]]), crc=e[17:19], unit=e[19],
                         extent=int.from_bytes(e[20:22], 'little')))
    return rows


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    report = dict(passed=False, physical_hardware_io=False,
                  kernel_sha256=hashlib.sha256(heap.IMAGE.read_bytes()).hexdigest(), cases=[])
    def done(name, **extra):
        report['cases'].append(dict(name=name, **extra)); print('PASS:', name, flush=True)
    try:
        # Boot probe: sizes, absent and busy REUs; every probed byte restored.
        for kib, present, want_bank in ((128, True, None), (256, True, None), (512, True, 7),
                                        (16384, True, 255), (512, False, None)):
            c = Cache(kib=kib, present=present)
            if want_bank is None:
                assert c.ram[RCACHE] == 0, (kib, present)
                assert bytes(c.bus.reu_ram) == c.reu_before, ('probe changed REU bytes', kib)
            else:
                assert c.ram[RCACHE] == 16 and c.bank() == want_bank, (kib, c.ram[RCACHE], c.bank())
                top = want_bank*65536
                changed = [i for i in range(len(c.reu_before)) if c.bus.reu_ram[i] != c.reu_before[i]]
                assert changed == [i for i in (top, top+1) if c.reu_before[i] != (0, 1)[i-top]], changed[:8]
                assert c.directory()[:2] == b'\0\1'
            done(f'probe {kib} KiB present={present}: cache bank {want_bank}')
        c = Cache(kib=512); c.bus.reu_reg[1] |= 0x80
        c.ram[RCACHE] = 0xee
        run_cpu(c.c.m.bus, symbol('rc_probe'))
        assert c.ram[RCACHE] == 0
        done('probe refuses an REU with an armed transfer')

        for fmt in (0, 3):
            c = Cache(kib=512, fmt=fmt)
            # Cold load reads the disk and stores the verified window.
            assert c.load() == 1 and c.ram[mods.STATE] == 2
            module = c.module[2:]
            assert bytes(c.ram[BASE:BASE+len(module)]) == module
            rows = entries(c.directory())
            assert [(r['name'], r['extent']) for r in rows] == [(mods.NAME, len(module))], rows
            assert rows[0]['crc'] == bytes(c.ram[0x3d6e:0x3d70])
            unit = c.bank()*65536+rows[0]['unit']*256
            assert bytes(c.bus.reu_ram[unit:unit+len(module)]) == module
            first = c.token()
            c.call(mods.CALL, 42, 0)
            # Warm load: no file opened, same bytes, new token, callable.
            assert c.load() == 0 and c.ram[mods.STATE] == 2 and c.token() != first
            assert bytes(c.ram[BASE:BASE+len(module)]) == module
            assert bytes(c.ram[BASE+len(module):END]) == b'\xcc'*(END-BASE-len(module))
            c.call(mods.CALL, 42, 0)
            assert len(entries(c.directory())) == 1
            for irq in (False, True):
                c.ram[BASE:END] = b'\xcc'*(END-BASE); c.name()
                before = c.opens; c.call(mods.LOAD, 0, irq=irq)
                assert c.opens == before and bytes(c.ram[BASE:BASE+len(module)]) == module
            done(f'format {fmt}: cold load stores, warm loads read no file (IRQs too)', opens=c.opens)

            # A damaged cached copy fails its CRC and falls back to the disk.
            c.bus.reu_ram[unit+len(module)-1] ^= 0x40
            assert c.load() == 1 and bytes(c.ram[BASE:BASE+len(module)]) == module
            c.call(mods.CALL, 42, 0)
            assert len(entries(c.directory())) == 2
            assert c.load() == 0
            done(f'format {fmt}: damaged copy falls back to disk and is replaced')

            # A damaged extent past the window never reaches the window.
            d = bytearray(c.directory()); d[2+22+20:2+22+22] = (0xf000).to_bytes(2, 'little')
            top = c.bank()*65536; c.bus.reu_ram[top:top+256] = d
            transfers = len(c.bus.reu_transactions)
            assert c.load() == 1
            assert all(t['host'] < BASE or t['host'] >= END or t['command'] == 0x90
                       for t in c.bus.reu_transactions[transfers:]), 'out-of-window extent fetched'
            done(f'format {fmt}: an out-of-window cached extent is refused before any copy')

            # A busy REU at load time also falls back to the disk.
            c.bus.reu_reg[1] |= 0x80
            assert c.load() == 1
            c.bus.reu_reg[1] &= 0x7f
            done(f'format {fmt}: armed REU transfer: disk load, cache untouched')

        # Twelve distinct names: the directory resets once full and keeps working.
        c = Cache(kib=512)
        names = [b'M%02d.PRG' % i for i in range(12)]
        for name in names:
            c.c.io.files[8, name, b'P'] = c.module
        counts = []
        for name in names:
            assert c.load(name=name) == 1
            counts.append(c.directory()[0])
        assert counts == list(range(1, 12))+[1], counts
        assert c.load(name=names[-1]) == 0 and c.load(name=names[0]) == 1
        done('directory resets after eleven entries and keeps caching', counts=counts)

        # No cache: every load reads the disk and the REU is never touched.
        for kib in (128, 256):
            c = Cache(kib=kib)
            transfers = len(c.bus.reu_transactions)
            assert c.load() == 1 and c.load() == 1
            assert len(c.bus.reu_transactions) == transfers
            done(f'{kib} KiB REU: no cache, disk loads, no REU transfers')
        report['passed'] = True
        print(f"PASS: {len(report['cases'])} REU module cache cases", flush=True)
    finally:
        args.report.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
