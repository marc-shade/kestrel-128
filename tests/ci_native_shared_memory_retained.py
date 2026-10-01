#!/usr/bin/env python3
"""Shared memory retains uncertain temporaries and permits RAM display fallback."""
import argparse
import json
from pathlib import Path
import tempfile

from ci_native_banked import assemble, seal
from ci_native_shared_memory import Memory
from native_banked_bus import BankedBus
from ci_native_vdc_desktop import VDCBus
from launcher_scene import surface


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix='kestrel-shared-memory-retained-'))
    parent, ps = assemble(work, 'parent', 'tests/fixtures/native-banked.asm')
    raw, bs = assemble(work, 'provider', 'src/native/vdc-service.asm')
    provider = seal(raw)
    report = dict(passed=False, physical_hardware_io=False, cases=[])

    def new(kib=512):
        Memory.bus_type = type('MemoryBus', (BankedBus, VDCBus), dict(size=64))
        p = Memory(parent, provider, ps, bs, kib=kib)
        p.load()
        p.memory(7)
        return p

    def done(name, p):
        report['cases'].append(dict(name=name, passed=True, calls=p.calls, instructions=p.instructions))
        print('PASS:', name, flush=True)

    try:
        p = new()
        old = p.memory(8, pages=2)
        blocker = p.memory(8, pages=1)
        original = bytes(p.bus.reu_ram)
        p.bus.reu_faults.add(len(p.bus.reu_transactions)+1)
        injected = []
        def block_disposal(cpu, bus, steps):
            if bus.config == 0x4e and cpu.pc == bs['ru_free'] and not injected:
                injected.append(steps)
                p.ram[0x3d11] = 1
        failed = p.memory(12, 7, token=old['token'], pages=3, interrupt=block_disposal)
        assert injected and failed['token'] == old['token'] and p.value('bm_pending') == 1
        assert p.value('bm_lease') == p.value('ru_active') == 1
        assert p.bus.reu_ram == original
        records_at = bs['ru_records']
        records = bytes(p.bus.ram[1][records_at:records_at+256])
        assert sum(records[at] == 33 for at in range(0, 256, 8)) == 3
        temporary = p.value('bm_temporary', 8)
        p.ram[0x3d11] = 0
        p.bus.reu_faults.clear()
        assert p.info()[:5] == bytes([1, 1, 1, 0, 1])
        reply = p.memory(9, token=old['token'], count=512)
        assert reply['actual'] == 512 and p.ram[0x3a00:0x3c00] == original[:512]
        assert p.value('bm_pending') == 0
        p.memory(11, 4, token=temporary)
        p.memory(13, 1)
        p.memory(11, token=old['token'])
        p.memory(11, token=blocker['token'])
        p.memory(13)
        p.call('close')
        done('failed temporary disposal stays owned; a later read recovers it and preserves the original extent', p)

        p = new(kib=128)
        document = p.memory(8, pages=32)
        original_reu = bytes(p.bus.reu_ram)
        p.surface = p.m.alloc(36, 0, owner=32, page=0xc0)
        p.ram[0xc000:0xe400] = surface(2)
        original_vdc = bytes(p.bus.video_ram)
        p.arguments(selected=2)
        p.call('call', operation=1)
        state = p.state()
        assert state[:4] == bytes([2, 1, 1, 0]) and state[29] == 0 and state[38] == 1
        assert p.bus.reu_ram == original_reu
        p.call('call', operation=4)
        assert p.bus.video_ram == original_vdc and p.bus.reu_ram == original_reu
        assert p.info()[:5] == bytes([1, 1, 1, 0, 0])
        reply = p.memory(9, token=document['token'], offset=len(original_reu)-512, count=512)
        assert reply['actual'] == 512 and p.ram[0x3a00:0x3c00] == original_reu[-512:]
        p.memory(11, token=document['token'])
        p.memory(13)
        p.call('close')
        p.m.select(p.surface, 32)
        p.m.invoke('free')
        assert p.m.stats()[1:] == (251, 31)
        done('a full REU document permits a RAM-backed VDC snapshot and survives its exact restoration', p)
        report['passed'] = True
    finally:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
