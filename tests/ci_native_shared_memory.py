#!/usr/bin/env python3
"""Shared VDC/document arena through the real checked bank-1 call gate."""
import argparse
import json
from pathlib import Path
import tempfile

from ci_native_banked import assemble, seal
from ci_native_vdc_service import Service
from native_banked_bus import BankedBus
from ci_native_vdc_desktop import VDCBus
from launcher_scene import surface


class Memory(Service):
    def memory(self, operation, expected=0, *, token=0, pages=0, offset=0, count=0, interrupt=None):
        self.ram[0x3d00:0x3d11] = (token.to_bytes(8, 'little') +
            offset.to_bytes(3, 'little') + count.to_bytes(2, 'little') +
            pages.to_bytes(2, 'little') + bytes(2))
        self.call('call', expected, operation=operation, flags=8, interrupt=interrupt)
        return dict(token=int.from_bytes(self.ram[0x3d00:0x3d08], 'little'),
                    actual=int.from_bytes(self.ram[0x3d0b:0x3d0d], 'little'),
                    pages=int.from_bytes(self.ram[0x3d0d:0x3d0f], 'little'),
                    page=int.from_bytes(self.ram[0x3d0f:0x3d11], 'little'))

    def info(self):
        self.call('call', operation=6)
        return bytes(self.ram[0x3d00:0x3d08])

    def value(self, name, count=1):
        at = self.bs[name]
        return int.from_bytes(self.bus.ram[1][at:at+count], 'little')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix='kestrel-shared-memory-'))
    parent, ps = assemble(work, 'parent', 'tests/fixtures/native-banked.asm')
    raw, bs = assemble(work, 'provider', 'src/native/vdc-service.asm')
    provider = seal(raw)
    report = dict(passed=False, physical_hardware_io=False, cases=[], work=str(work))

    def new(kib=1024, size=64, present=True):
        Memory.bus_type = type('MemoryBus', (BankedBus, VDCBus),
                               dict(size=size, reu_present=present))
        p = Memory(parent, provider, ps, bs, kib=kib)
        p.load()
        return p

    def done(name, p, **extra):
        report['cases'].append(dict(name=name, calls=p.calls,
                                   instructions=p.instructions, **extra))
        print('PASS:', name, flush=True)

    try:
        p = new()
        original = bytes(p.bus.reu_ram)
        payload = bytes((i*19+(i>>8)*73+11) & 255 for i in range(512))
        p.ram[0x3a00:0x3c00] = payload
        assert p.info() == bytes([1, 0, 0, 0, 0, 0, 0, 0])
        p.memory(13)
        p.memory(7)
        p.memory(7)
        assert p.info()[:5] == bytes([1, 1, 1, 0, 0])
        old = p.memory(8, pages=2)
        blocker = p.memory(8, pages=1)
        assert (old['page'], blocker['page']) == (0, 2)
        assert p.ram[0x3a00:0x3c00] == payload
        p.memory(13, 1)
        p.call('call', 1, operation=0)
        grown = p.memory(12, token=old['token'], pages=33)
        assert grown['page'] == 3 and grown['token'] != old['token']
        wanted = bytearray(original)
        wanted[3*4096:5*4096] = original[:8192]
        assert p.bus.reu_ram == wanted
        transactions = len(p.bus.reu_transactions)
        p.memory(9, 4, token=old['token'], count=1)
        assert len(p.bus.reu_transactions) == transactions
        p.memory(11, token=blocker['token'])
        extended = p.memory(12, token=grown['token'], pages=129)
        assert extended['token'] == grown['token'] and extended['page'] == 3
        assert p.bus.reu_ram == wanted
        for offset, count in ((0, 512), (0xfff1, 512), (0x1ffff, 512), (129*4096-512, 512)):
            p.ram[0x3a00:0x3c00] = payload
            reply = p.memory(10, token=grown['token'], offset=offset, count=count)
            assert reply['actual'] == count
            wanted[3*4096+offset:3*4096+offset+count] = payload[:count]
            assert p.bus.reu_ram == wanted
            p.ram[0x3a00:0x3c00] = bytes(512)
            reply = p.memory(9, token=grown['token'], offset=offset, count=count)
            assert reply['actual'] == count and p.ram[0x3a00:0x3c00] == payload
        for offset, count in ((0, 0), (0, 513), (129*4096-1, 2), (0xffffff, 512)):
            transactions = len(p.bus.reu_transactions)
            reply = p.memory(10, 6, token=grown['token'], offset=offset, count=count)
            assert reply['actual'] == 0 and len(p.bus.reu_transactions) == transactions
            assert p.bus.reu_ram == wanted
        p.memory(11, token=grown['token'])
        p.memory(13)
        assert p.info()[:5] == bytes([1, 0, 0, 0, 0])
        p.call('call', operation=0)
        p.call('close')
        assert p.m.stats()[1:] == (251, 31)
        done('512-byte payloads, relocation, growth past 96 KiB, full-byte integrity and lifetime', p)

        for fault in (1, 2, 3, 16, 32):
            p = new()
            p.memory(7)
            old = p.memory(8, pages=2)
            blocker = p.memory(8, pages=1)
            original = bytes(p.bus.reu_ram)
            p.bus.reu_fault_prefix = 128
            p.bus.reu_faults.add(len(p.bus.reu_transactions)+fault)
            failed = p.memory(12, 17, token=old['token'], pages=3)
            assert failed['token'] == old['token']
            assert p.info()[:5] == bytes([1, 1, 1, 0, 0])
            assert p.bus.reu_ram[:3*4096] == original[:3*4096]
            assert p.bus.reu_ram[6*4096:] == original[6*4096:]
            stats = p.memory(14)
            assert (stats['page'], stats['token'] & 255) == (253, 30)
            p.bus.reu_faults.clear()
            grown = p.memory(12, token=old['token'], pages=3)
            assert p.bus.reu_ram[grown['page']*4096:grown['page']*4096+8192] == original[:8192]
            p.memory(11, token=grown['token'])
            p.memory(11, token=blocker['token'])
            p.memory(13)
            p.call('close')
            done(f'partial relocation DMA {fault}: original allocation survives, temporary frees, retry succeeds', p)

        for size in (16, 64):
            for first in ('memory', 'display'):
                p = new(size=size)
                p.surface = p.m.alloc(36, 0, owner=32, page=0xc0)
                p.ram[0xc000:0xe400] = surface(2)
                original_vdc = bytes(p.bus.video_ram)
                if first == 'memory':
                    p.memory(7)
                    document = p.memory(8, pages=25)
                p.arguments(selected=2)
                p.call('call', operation=1)
                if first == 'display':
                    p.memory(7)
                    document = p.memory(8, pages=25)
                assert p.state()[29] == 1
                document_bytes = bytes(p.bus.reu_ram[document['page']*4096:(document['page']+25)*4096])
                snapshot = p.value('vs_token', 8)
                # A document API call cannot free a display-owned token.
                p.memory(11, 5, token=snapshot)
                p.memory(13, 1)
                p.call('call', operation=4)
                assert p.bus.video_ram == original_vdc
                assert p.info()[:5] == bytes([1, 1, 1, 0, 0])
                assert p.bus.reu_ram[document['page']*4096:(document['page']+25)*4096] == document_bytes
                p.arguments(selected=2)
                p.call('call', operation=1)
                assert p.state()[29] == 1
                p.memory(11, token=document['token'])
                p.memory(13)  # The display alone now retains the arena.
                assert p.info()[:5] == bytes([1, 0, 1, 0, 0])
                p.call('call', operation=4)
                assert p.bus.video_ram == original_vdc
                assert p.info()[:5] == bytes([1, 0, 0, 0, 0])
                p.call('close')
                p.m.select(p.surface, 32)
                p.m.invoke('free')
                assert p.m.stats()[1:] == (251, 31)
                done(f'{size} KiB VDC, {first} first: documents survive screen close/reopen and independent lease release', p)

        p = new(present=False)
        original = bytes(p.bus.reu_ram), bytes(p.bus.reu_reg)
        p.memory(7, 21)
        assert p.info()[:5] == bytes([1, 0, 0, 0, 0])
        assert original == (bytes(p.bus.reu_ram), bytes(p.bus.reu_reg))
        p.call('close')
        done('absent REU refuses cleanly without writes or a retained memory lease', p)
        report['passed'] = True
    finally:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
