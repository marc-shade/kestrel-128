#!/usr/bin/env python3
"""Execute the assembled REU arena and independent ownership/range oracles."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import re
import subprocess
import tempfile

import ci_native_heap as heap
from native_reu_bus import REUBusMixin

ROOT = Path(__file__).resolve().parents[1]
BaseBus = heap.Bus


class REUBus(REUBusMixin, BaseBus):
    pass


class Arena:
    def __init__(self, image, symbols, kib=512, present=True):
        heap.Bus = type('Bus',(REUBus,),dict(reu_kib=kib,reu_present=present))
        self.m = heap.Machine()
        self.bus, self.ram, self.symbols = self.m.bus, self.m.ram, symbols
        self.app = self.m.alloc(32,0,owner=32,page=0x60)
        self.ram[0x6000:0x6000+len(image)-2] = image[2:]
        self.ram[0x3d20], self.ram[0x3d23] = 32,2
        for at in (0x3d3b,0x3d91): self.ram[at] = 0
        self.bus.reu_hosts.append((symbols['ru_probe_data'],symbols['ru_probe_data']+2))
        self.set('owner',32)
        self.calls = 0

    def set(self, name, value, size=1):
        if isinstance(value,int): value = value.to_bytes(size,'little')
        start = self.symbols['ru_'+name]
        self.ram[start:start+len(value)] = value

    def get(self, name, size=1):
        start = self.symbols['ru_'+name]
        return int.from_bytes(self.ram[start:start+size],'little')

    def call(self, name, expected=0, flags=0):
        before = bytes(self.bus.mmu),self.bus.reu_speed
        cpu = self.m.invoke(self.symbols['ru_'+name],check=False,flags=flags)
        assert (cpu.a,cpu.p&1) == (expected,int(bool(expected))), (name,cpu.a,cpu.p&1,expected)
        assert before == (bytes(self.bus.mmu),self.bus.reu_speed)
        if expected != 7: assert self.get('error') == expected and self.get('busy') == 0
        self.calls += 1

    def alloc(self, pages, owner=32, page=None, expected=0):
        self.set('owner',owner); self.set('pages',pages,2)
        if page is not None: self.set('page',page,2)
        self.call('alloc' if page is None else 'reserve',expected)
        return self.get('handle',8),self.get('page',2)

    def free(self, token, owner=32, expected=0):
        self.set('owner',owner); self.set('handle',token,8); self.call('free',expected)

    def transfer(self, direction, token, offset, count, expected=0, flags=0):
        self.set('owner',32); self.set('handle',token,8)
        self.set('offset',offset,3); self.set('count',count,2)
        self.call(direction,expected,flags)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report',type=Path,required=True)
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix='kestrel-reu-cpu-'))
    subprocess.run(['64tass','-a','-B',str(ROOT/'tests/fixtures/native-reu.asm'),
                    '-o',str(work/'reu.prg'),'-l',str(work/'reu.sym')],check=True,capture_output=True)
    image = (work/'reu.prg').read_bytes()
    symbols = {m[1]:int(m[2],16) for m in re.finditer(r'^(\w+)\s*=\s*\$([a-fA-F0-9]+)$',
                                                    (work/'reu.sym').read_text(),re.M)}
    report = dict(passed=False,physical_hardware_io=False,cases=[],
                  image_sha256=hashlib.sha256(image).hexdigest(),library_bytes=len(image)-34)
    def done(name,a,**extra):
        report['cases'].append(dict(name=name,calls=a.calls,dmas=len(a.bus.reu_transactions),**extra))
        print('PASS:',name,flush=True)
    try:
        # With the kernel module cache (N_RCACHE=16 at $3d9f, set at boot for
        # 512 KiB or more) the arena stops below the REU's top 64 KiB bank.
        for kib in (512,1024,16384):
            a = Arena(image,symbols,kib); a.ram[0x3d9f] = 16
            top = len(a.bus.reu_ram)-65536; reserved = bytes(a.bus.reu_ram[top:])
            a.call('open',flags=8)
            assert a.get('total',2) == kib//4-16
            token,at = a.alloc(kib//4-16); a.alloc(1,expected=2)
            a.alloc(1,page=kib//4-16,expected=2)
            assert at == 0; a.set('handle',token,8); a.set('offset',(kib//4-16)*4096-512,3); a.set('count',512,2)
            a.ram[0x3a00:0x3c00] = bytes(range(256))*2; a.call('write')
            assert bytes(a.bus.reu_ram[top:]) == reserved
            done(f'{kib} KiB with the module cache: arena {kib//4-16} pages, top bank untouched',a)
        for kib in (128,256,512,1024,2048,4096,8192,16384):
            a = Arena(image,symbols,kib)
            original = bytes(a.bus.reu_ram)
            host1, buffer = bytes(a.bus.ram[1]),bytes(a.ram[0x3a00:0x3c00])
            a.call('open',flags=8)
            assert a.get('total',2) == kib//4 and a.get('active') == 1
            assert a.bus.reu_ram == original and a.bus.ram[1] == host1
            assert bytes(a.ram[0x3a00:0x3c00]) == buffer
            a.call('stats'); assert a.get('available',2) == kib//4 and a.get('slots') == 32
            token,_ = a.alloc(kib//4)
            a.alloc(1,expected=2)
            for offset,count in ((0,1),(0xff23,512),(0x1fffd,3),(len(original)-512,512)):
                payload = bytes((i*17+(i>>4)*29+offset)&255 for i in range(count))
                a.ram[0x3a00:0x3a00+count] = payload
                for direction in ('write','read'):
                    if direction == 'read': a.ram[0x3a00:0x3a00+count] = bytes(count)
                    a.transfer(direction,token,offset,count,flags=12)
                    assert a.get('actual',2) == count
                    assert a.bus.reu_ram[offset:offset+count] == payload
                    assert a.ram[0x3a00:0x3a00+count] == payload
            for offset,count in ((0,0),(0,513),(len(original)-1,2),(0xffffff,512)):
                transactions = len(a.bus.reu_transactions)
                a.transfer('write',token,offset,count,expected=6)
                assert a.get('actual',2) == 0 and len(a.bus.reu_transactions) == transactions
            a.free(token); a.call('close'); a.call('open')
            new,_ = a.alloc(1)
            a.free(token,expected=4); a.free(new); a.call('close')
            assert not a.get('probe_live')
            done(f'{kib} KiB: preserved probe, full allocation, edge transfers, range checks, reopen generations',a)

        a = Arena(image,symbols,16384); a.call('open')
        original = bytes(a.bus.reu_ram)
        token,page = a.alloc(3,page=127)
        assert page == 127
        payload = bytes((i*51+31)&255 for i in range(512))
        a.ram[0x3a00:0x3c00] = payload
        before = len(a.bus.reu_transactions)
        a.transfer('write',token,0xf80,512)
        assert [(r['address'],r['count']) for r in a.bus.reu_transactions[before:]] == [(0x7ff80,128),(0x80000,384)]
        expected = bytearray(original); expected[0x7ff80:0x80180] = payload
        assert a.bus.reu_ram == expected
        a.ram[0x3a00:0x3c00] = bytes(512)
        a.transfer('read',token,0xf80,512)
        assert a.ram[0x3a00:0x3c00] == payload
        a.free(token)
        # Final bank and 24-bit offset carry, with distinct high-bank bytes.
        token,page = a.alloc(1,page=4095)
        a.ram[0x3a00:0x3c00] = payload[::-1]
        a.transfer('write',token,3584,512)
        expected[-512:] = payload[::-1]
        assert a.bus.reu_ram == expected
        done('512 KiB REC boundary and final 16 MiB byte preserve every unrelated REU byte',a)

        a = Arena(image,symbols); a.call('open')
        rng = random.Random(78191); live = {}
        for _ in range(250):
            if live and rng.randrange(3) == 0:
                token = rng.choice(list(live)); a.free(token); del live[token]
                a.free(token,expected=4)
            else:
                pages = rng.randrange(1,16)
                fit = next((i for i in range(129-pages) if all(i+n <= s or s+c <= i for s,c in live.values() for n in [pages])),None)
                error = 3 if len(live) == 32 else (2 if fit is None else 0)
                token,at = a.alloc(pages,expected=error)
                if not error: assert at == fit; live[token] = (at,pages)
            a.call('stats')
            assert a.get('available',2) == 128-sum(n for _,n in live.values())
            assert a.get('slots') == 32-len(live)
        for token in live: a.free(token,owner=33,expected=5)
        a.set('owner',32); a.call('release'); a.call('close')
        done('250 independent first-fit/fragmentation steps, stale tokens and owner isolation',a)

        for present,command,mask in ((False,0x10,31),(True,0x80,31),(True,0x10,0xdf)):
            a = Arena(image,symbols,present=present)
            a.bus.reu_reg[1],a.bus.reu_reg[9] = command,mask
            original = bytes(a.bus.reu_ram),bytes(a.bus.reu_reg)
            a.call('open',expected=0x15)
            assert not a.bus.reu_transactions and not any(r[0] == 'write' for r in a.bus.reu_accesses)
            assert original == (bytes(a.bus.reu_ram),bytes(a.bus.reu_reg))
            done('absent / armed / interrupt-owned REU refused before writes or status acknowledgement',a)

        a = Arena(image,symbols); a.call('open')
        token,_ = a.alloc(1)
        for name in ('busy',):
            a.set(name,1); a.call('read',expected=7); a.set(name,0)
        cookie = a.get('cookie',4)
        record = 0x3c00+((cookie&255)-1)*8
        a.ram[record+4] += 1
        a.free(token,expected=4)
        done('reentry and app-allocation generation changes refuse stale arena access',a)

        a = Arena(image,symbols); a.call('open')
        records = symbols['ru_records']
        a.ram[records+5:records+8] = bytes([255])*3
        a.call('stats'); assert a.get('slots') == 31
        handles = [a.alloc(1)[0] for _ in range(31)]
        assert all(h&255 != 1 for h in handles)
        a.alloc(1,expected=3)
        a.set('owner',32); a.call('release')
        a.alloc(0,expected=1); a.alloc(65535,expected=2)
        token,_ = a.alloc(1,page=127)
        a.alloc(1,page=127,expected=2); a.alloc(1,page=128,expected=2)
        a.call('close',expected=1)
        a.free(token); a.call('close')
        done('retired generation slots never wrap; 31 live slots, reserve conflicts and close ownership',a)

        a = Arena(image,symbols,1024); a.call('open')
        token,_ = a.alloc(2,page=127)
        expected = bytearray(a.bus.reu_ram)
        payload = bytes((i*53+21)&255 for i in range(512))
        a.ram[0x3a00:0x3c00] = payload
        a.bus.reu_faults.add(len(a.bus.reu_transactions)+2)
        a.transfer('write',token,0xf80,512,expected=17)
        expected[0x7ff80:0x80000] = payload[:128]
        assert a.get('actual',2) == 128 and a.bus.reu_ram == expected
        a.bus.reu_faults.clear()
        a.transfer('write',token,0xf80,512)
        expected[0x7ff80:0x80180] = payload
        assert a.bus.reu_ram == expected
        a.set('owner',33); a.set('handle',token,8); a.call('read',5)
        assert a.get('actual',2) == 0
        a.ram[0x3d20] = 0; a.set('actual',512,2); a.call('read',8)
        assert a.get('actual',2) == 0
        done('failed second DMA exposes only completed prefix; retry and every owner/platform refusal are bounded',a)

        for fault in (2,5,6,8,9,10,11):
            a = Arena(image,symbols)
            original = bytes(a.bus.reu_ram)
            a.bus.reu_faults.add(fault); a.bus.reu_fault_prefix = 1
            a.call('open',expected=0x11)
            a.bus.reu_faults.clear()
            a.call('close')
            assert a.bus.reu_ram == original and a.get('probe_live') == 0
            done(f'partial probe/restore DMA {fault}: exact memory recovery',a)
        report['passed'] = True
    finally:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__ == '__main__': main()
