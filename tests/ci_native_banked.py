#!/usr/bin/env python3
"""Execute the owned bank-1 loader, callbacks and REU provider with fault cases."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

from py65.devices.mpu6502 import MPU
import ci_native_heap as heap
from ci_native_files import StreamIEC
from native_banked_bus import BankedBus
from native_banked import seal, validate
from ci_native_ultimate import DOSFiles, UltimateBus
from ci_native_query import QueryDOS

ROOT = Path(__file__).resolve().parents[1]


def assemble(work, name, source):
    subprocess.run(['64tass', '-a', '-B', '-I', str(ROOT/'src/native'), str(ROOT/source),
                    '-o', str(work/(name+'.prg')), '-l', str(work/(name+'.sym'))],
                   check=True, capture_output=True)
    symbols = {n:int(v,16) for n,v in re.findall(r'^(\w+)\s*=\s*\$([\da-fA-F]+)',
                                                (work/(name+'.sym')).read_text(),re.M)}
    return (work/(name+'.prg')).read_bytes(),symbols


class Banked:
    bus_type = BankedBus
    def __init__(self, parent, provider, ps, bs, *, kib=512, image=None, fmt=0):
        heap.Bus = type('Bus',(self.bus_type,),dict(reu_kib=kib))
        self.m = heap.Machine()
        self.bus, self.ram = self.m.bus, self.m.ram
        self.ps, self.bs, self.provider = ps, bs, provider
        self.app = self.m.alloc((len(parent)-2+255)//256,0,owner=32,page=0x60)
        self.ram[0x6000:0x6000+len(parent)-2] = parent[2:]
        self.ram[0x3d20],self.ram[0x3d23] = 32,2
        for at in (0x3d3b,0x3d91): self.ram[at] = 0
        self.bus.reu_bank1_hosts.append((bs['ru_probe_data'],bs['ru_probe_data']+2))
        self.io = StreamIEC(self.m, {(8,b'BKREU.PRG',b'P'): provider if image is None else image})
        self.fmt = fmt
        self.io.formats[8] = min(fmt,2)
        if fmt == 3:
            self.ultimate = DOSFiles({b'/Usb0/BKREU.PRG': provider if image is None else image})
            self.ultimate.fragment = 7
            self.ultimate.direct_write_corruption = True
            self.bus = self.m.bus = UltimateBus(self.bus,self.ultimate)
        self.calls = self.instructions = 0

    def get(self,name,n=1):
        at = self.ps['bk_'+name]
        return int.from_bytes(self.ram[at:at+n],'little')

    def set(self,name,value,n=1):
        at = self.ps['bk_'+name]
        self.ram[at:at+n] = value.to_bytes(n,'little')

    def call(self,name,expected=0,*,operation=0,carry=None,flags=0,interrupt=None):
        entry = self.ps['bk_'+name] if isinstance(name,str) else name
        cpu = MPU(memory=self.bus,pc=entry)
        cpu.a,cpu.p,cpu.sp = operation,0x20|flags,0xe0
        cpu.stPushWord(0xaff)
        before = bytes(self.bus.mmu),self.bus.config,bytes(self.ram[6:9])
        for steps in range(12000000):
            if cpu.pc == 0xb00 and cpu.sp == 0xe0: break
            if interrupt: interrupt(cpu,self.bus,steps)
            if not self.io.stub(cpu): cpu.step()
        else: raise AssertionError((name,hex(cpu.pc),hex(self.bus.config),cpu.sp))
        assert (cpu.a,cpu.p&1) == (expected,int(bool(expected)) if carry is None else carry), (name,cpu.a,cpu.p,expected)
        assert cpu.sp == 0xe0 and cpu.p&12 == flags&12
        assert before[:2] == (bytes(self.bus.mmu),self.bus.config), (name,'mapping')
        if name == 'call' and not self.get('error'): assert bytes(self.ram[6:9]) == before[2]
        assert not self.bus.io_reads and not self.bus.io_writes
        if isinstance(name,str) and expected != 7: assert self.get('busy') == 0
        self.calls += 1; self.instructions += steps
        return cpu

    def open(self,via_callback=False):
        self.ram[0x3d80] = 32
        self.ram[0x3d85:0x3d89] = bytes([8,9,0,1])
        self.ram[0x3d96] = self.io.formats[8]
        self.ram[0x3da0:0x3da9] = b'BKREU.PRG'
        if self.fmt == 3:
            path = b'/Usb0/BKREU.PRG'
            self.ram[0x3d85:0x3d87] = bytes([1,len(path)])
            self.ram[0x3d96] = 3
            self.ram[0x4e00:0x4e00+len(path)] = path
        if via_callback:
            self.ram[0x3a00] = 11
            self.call('call',operation=11)
        else: self.call(0x1c41)

    def load(self,expected=0):
        self.open(); self.call('load',expected)

    def config(self,owner=32,pages=0,page=0,token=0,offset=0,count=0):
        data = (bytes([owner])+pages.to_bytes(2,'little')+page.to_bytes(2,'little')+
                token.to_bytes(8,'little')+offset.to_bytes(3,'little')+count.to_bytes(2,'little'))
        self.ram[0x3a00:0x3a12] = data
        self.call('call',operation=9)

    def status(self):
        self.call('call',operation=10)
        b = self.ram[0x3a00:0x3a1d]
        return dict(token=int.from_bytes(b[5:13],'little'),page=int.from_bytes(b[3:5],'little'),
                    actual=int.from_bytes(b[18:20],'little'),error=b[20],total=int.from_bytes(b[21:23],'little'),
                    available=int.from_bytes(b[23:25],'little'),slots=b[25],active=b[26],probe_live=b[28])


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--report',type=Path,required=True)
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix='kestrel-banked-cpu-'))
    parent,ps = assemble(work,'parent','tests/fixtures/native-banked.asm')
    raw,bs = assemble(work,'provider','examples/native-banked/provider.asm')
    provider = seal(raw)
    report = dict(passed=False,physical_hardware_io=False,work=str(work),cases=[],
                  parent_sha256=hashlib.sha256(parent).hexdigest(),provider_sha256=hashlib.sha256(provider).hexdigest())
    def new(**kw): return Banked(parent,provider,ps,bs,**kw)
    def done(name,b,**extra):
        report['cases'].append(dict(name=name,calls=b.calls,instructions=b.instructions,**extra))
        print('PASS:',name,flush=True)
    try:
        b = new(); original = bytes(b.bus.ram[1])
        b.load(); assert b.get('state') == 2 and not b.io.handles
        loaded = bytearray(provider[2:]); loaded[22:24] = ps['bk_callback'].to_bytes(2,'little')
        assert b.bus.ram[1][0x6000:0x6000+len(loaded)] == loaded
        assert b.bus.ram[1][:0x6000] == original[:0x6000] and b.bus.ram[1][0x6000+len(loaded):] == original[0x6000+len(loaded):]
        b.config(); b.call('call',operation=0,flags=8)
        assert b.status()['total'] == 128
        b.config(pages=1); b.call('call',operation=2); token = b.status()['token']
        data = bytes((i*71+3)&255 for i in range(512))
        b.config(token=token,offset=31,count=512)
        b.ram[0x3a00:0x3c00] = data
        b.call('call',operation=6)
        b.ram[0x3a00:0x3c00] = bytes(512)
        b.call('call',operation=5)
        assert b.ram[0x3a00:0x3c00] == data
        assert b.status()['actual'] == 512
        b.call('call',operation=4); b.call('call',operation=1)
        b.call('close'); assert b.get('state') == 0 and b.m.stats()[1:] == (251,31)
        done('checked stream load, bank-1 REU open/allocate/roundtrip/free/close',b)

        for fmt in (1,2,3):
            b = new(fmt=fmt); b.load()
            b.ram[0x3a00] = 5
            b.call('call',operation=11)
            assert b.m.stats()[1] == 251-validate(provider)['pages']
            if fmt == 3: assert b.ultimate.handles == {1:None,2:None}
            b.call('close')
            done(f'geometry/backend {fmt}: real native stream, checked load and returning STATS callback',b)

        b = new(); b.load()
        # Callback writes and reads must reach physical low bank-1 RAM even
        # though it is hidden by the temporary 16-KiB common area during calls.
        h = b.m.alloc(2,1,owner=32,page=4)
        baseline = bytes(b.bus.ram[1][0x400:0x4000])
        b.m.select(h,32); b.m.set(heap.OFFSET,0,2); b.m.set(heap.COUNT,512,2)
        data = bytes([3])+bytes((i*11+17)&255 for i in range(511))
        b.ram[0x3a00:0x3c00] = data
        b.call('call',operation=11,flags=8) # N_WRITE index is the first data byte
        assert b.bus.ram[1][0x400:0x600] == data
        assert b.bus.ram[1][0x600:0x4000] == baseline[512:]
        b.ram[0x3a00:0x3c00] = bytes([2])+bytes(511)
        b.call('call',operation=11)
        assert b.ram[0x3a00:0x3c00] == data
        b.ram[0x3a00] = 1; b.call('call',operation=11)
        metadata = b.m.metadata()
        for index in (6,8,9,10,17,18,21,22,23,28,255):
            b.ram[0x3a00] = index; b.call('call',1,operation=11)
            assert b.m.metadata() == metadata
        for token in (b.app,b.get('handle',4).to_bytes(4,'little')):
            b.m.select(token,32)
            for index in (1,3,4):
                b.ram[0x3a00] = index; b.call('call',1,operation=11)
                assert b.m.metadata() == metadata
        b.call('close')
        done('callbacks preserve low bank-1 documents and reject exit/module/release and active-code mutations',b)

        for fmt in (0,3):
            b = new(fmt=fmt); b.load(); b.open(via_callback=True)
            b.ram[0x3d89:0x3d8b] = (512).to_bytes(2,'little')
            b.ram[0x3a00] = 12; b.call('call',operation=11)
            assert b.ram[0x3a00:0x3c00] == provider[:512]
            b.ram[0x3a00] = 14; b.call('call',operation=11)
            assert not b.io.handles
            if fmt == 3: assert b.ultimate.handles == {1:None,2:None}
            b.call('close')
            done(f'backend {fmt}: banked native OPEN/READ/CLOSE callbacks preserve mapping and exact source bytes',b)

        b = new(fmt=3); b.load()
        b.ultimate = QueryDOS(); b.bus.dos = b.ultimate
        reply = b'BANKED ULTIMATE QUERY\x00\xff'
        b.ultimate.replies[b'\x04\x01'] = [(reply[:7],b''),(reply[7:],b'00,OK')]
        b.ram[0x3d80] = 32; b.ram[0x3d3c:0x3d3e] = bytes([0,4]); b.ram[0x3a00] = 26
        fired = []
        def query_irq(c,m,s):
            if s%101 == 0 and not c.p&4:
                fired.append(s);c.irq()
        b.call('call',operation=11,flags=8,interrupt=query_irq)
        assert b.ram[0x3a00:0x3a00+len(reply)] == reply
        assert int.from_bytes(b.ram[0x3d8b:0x3d8d],'little') == len(reply)
        assert b.ultimate.commands == [b'\x04\x01'] and fired
        b.call('close')
        done('banked Ultimate query callback: multipart binary reply, service RAM mapping and delivered IRQs',b)

        # Inject interrupts at every unique instruction/map boundary in the
        # complete round trip, including both common tails and native callback.
        # Both code-check paths: a cold cache walks the page map, a warm one
        # reuses the passed check.
        b = new(); b.load()
        def cache(warm):
            epoch = int.from_bytes(b.ram[0x1bf8:0x1bfa],'little')
            b.set('checked',(epoch if warm else epoch^0xffff)|b.get('handle')<<16,3)
        paths = []
        for warm in (False,True):
            b.ram[0x3a00] = 5; cache(warm); trace = []
            b.call('call',operation=11,interrupt=lambda c,m,s:trace.append((c.pc,m.config,m.mmu[6])))
            paths += [(warm,point) for point in dict.fromkeys(trace)]
        assert any(config == 0x4e for _,(_,config,_) in paths)
        assert len({point for _,point in paths}) > len({point for warm,point in paths if warm})
        injected = 0
        for kind in ('nmi','irq'):
            for warm,point in paths:
                b.ram[0x3a00] = 5; fired = []; cache(warm)
                counted = b.ram[0xb10]
                def inject(c,m,s):
                    if not fired and (c.pc,m.config,m.mmu[6]) == point:
                        fired.append(kind == 'nmi' or not c.p&4)
                        getattr(c,kind)()
                b.call('call',operation=11,interrupt=inject)
                assert fired
                assert (b.ram[0xb10]-counted)&255 == int(fired[0]), (kind,point)
                injected += 1
        b.call('close')
        done('IRQ/NMI attempts at every executor/client/callback instruction and MMU boundary',b,interrupt_attempts=injected)

        for kib in (128,256,512,1024,2048,4096,8192,16384):
            b = new(kib=kib); b.load()
            original = bytes(b.bus.reu_ram)
            low = bytes(b.bus.ram[1][:0x6000])
            # Existing VIC/DMA-bank and speed bits are borrowed and restored.
            b.bus.mmu[6] |= 64; b.bus.reu_speed |= 1
            b.config(); b.call('call',operation=0,flags=8)
            assert b.status()['total'] == kib//4 and b.bus.reu_ram == original
            b.config(pages=kib//4); b.call('call',operation=2); token = b.status()['token']
            expected = bytearray(original)
            for offset in (0xff80,kib*1024-512,0x7ff80 if kib>=1024 else 0):
                data = bytes((i*57+(offset>>16)*3)&255 for i in range(512))
                b.config(token=token,offset=offset,count=512)
                b.ram[0x3a00:0x3c00] = data; b.call('call',operation=6)
                expected[offset:offset+512] = data
                b.ram[0x3a00:0x3c00] = bytes(512); b.call('call',operation=5)
                assert b.ram[0x3a00:0x3c00] == data and b.status()['actual'] == 512
            assert b.bus.reu_ram == expected and b.bus.ram[1][:0x6000] == low
            assert {r['host_bank'] for r in b.bus.reu_transactions} == {0,1}
            b.call('call',operation=4); b.call('call',operation=1); b.call('close')
            done(f'{kib} KiB banked REU: preserved probe, physical host bank and REC-boundary transfers',b,
                 independently_compared_reu_bytes=len(original)*2)

        # A partial failed probe keeps its bank-1 arena allocated and recovers
        # both physical REU bytes when close is explicitly retried.
        b = new(); b.load(); original = bytes(b.bus.reu_ram)
        b.config(); b.bus.reu_fault_from = 5; b.bus.reu_fault_prefix = 1
        b.call('call',17,operation=0)
        assert b.status()['probe_live'] and b.get('state') == 2
        b.call('call',17,operation=1)
        b.bus.reu_fault_from = None
        b.call('call',operation=1)
        assert b.status()['probe_live'] == 0 and b.bus.reu_ram == original
        b.call('close')
        done('failed probe restoration retains banked REU context until explicit successful close',b)

        for mutation,error in (('crc',20),('short',18),('long',19),('magic',16),('stub',16),
                               ('callback',16),('reserved',16),('pages',16),('entry',16)):
            image = bytearray(provider)
            if mutation == 'crc': image[-1] ^= 1
            elif mutation == 'short': image = image[:-1]
            elif mutation == 'long': image += b'X'
            elif mutation == 'magic': image[2] ^= 1
            elif mutation == 'stub': image[18] ^= 1
            elif mutation == 'callback': image[24] = 1
            elif mutation == 'reserved': image[33] = 1
            elif mutation == 'pages': image[12] += 1
            elif mutation == 'entry': image[14:16] = b'\x1f\0'
            b = new(image=bytes(image)); b.load(error)
            assert b.get('state') == 1
            b.call('call',4); b.call('load',1)
            b.call('close'); assert not b.io.handles and b.m.stats()[1:] == (251,31)
            done(f'{mutation} image rejected without execution; retained resources close cleanly',b)

        b = new(); b.open(); b.io.fail_read = 111
        b.call('load',17); assert b.get('state') == 1
        b.io.fail_read = None; b.call('close')
        b.load(); old = b.get('handle',4)
        b.call('close'); b.load(); assert b.get('handle',4) != old
        current = b.get('handle',4); b.set('handle',old,4)
        b.call('call',4); b.set('handle',current,4); b.call('close')
        done('partial transport error cleanup and stale banked-code generation refusal',b)

        b = new(fmt=3); b.open()
        b.ultimate.inject[3] = lambda command,reply: [(b'',b'71,CLOSE ERROR')]
        b.call('load',17); assert b.get('state') == 1 and b.get('file')
        b.call('call',4); b.call('close',17)
        del b.ultimate.inject[3]
        b.call('close'); assert b.get('state') == 0 and b.ultimate.handles == {1:None,2:None}
        done('uncertain Ultimate source close retains file/code ownership and disables execution',b)

        b = new(); b.load()
        for flags in (4,12): b.call('call',8,flags=flags)
        for name in ('busy',):
            b.set(name,1); before = bytes(b.ram[0x6000:0x6800])
            b.call('call',7); assert b.ram[0x6000:0x6800] == before
            b.set(name,0)
        for at in (0x2ab,0x2f2):
            b.ram[at] ^= 1; b.call('call',8); b.ram[at] ^= 1
        for offset,value in ((6,5),(7,2),(8,0xf1),(9,2),(10,0xf1)):
            old = b.bus.mmu[offset]; b.bus.mmu[offset] = value
            b.call('call',8); b.bus.mmu[offset] = old
        for name,n,values in (('entry',2,(0x5fff,0x6000,0xc000)),('length',2,(0,32,0xffff)),
                              ('pages',1,(0,97))):
            old = b.get(name,n)
            for value in values:
                b.set(name,value,n);b.call('call',4)
            b.set(name,old,n)
        b.set('checked',0,3)  # the page-tag walk runs again only after a heap change
        tag = b.ram[0x3960]; b.ram[0x3960] = 0
        b.call('call',4); b.ram[0x3960] = tag
        at = 0x3c00+(b.app[0]-1)*8+4
        b.ram[at] += 1; b.call('call',4); b.ram[at] -= 1
        b.call('close')
        done('busy, disabled IRQs, altered common tails/MMU, page tags and parent generations refused',b)

        b = new(); b.load()
        counts = []
        for _ in range(2):
            before = b.instructions; b.call('call',operation=0,flags=8); counts.append(b.instructions-before)
        assert counts[0]-counts[1] >= 5*b.get('pages'), counts
        epoch = int.from_bytes(b.ram[0x1bf8:0x1bfa],'little')
        tag = b.ram[0x3960]; b.ram[0x3960] = 0
        b.call('call',operation=0,flags=8)
        spare = b.m.alloc(1,0,owner=32); b.m.select(spare,32); b.m.invoke('free')
        assert int.from_bytes(b.ram[0x1bf8:0x1bfa],'little') == epoch+2
        b.call('call',4)
        b.ram[0x3960] = tag; b.call('call',operation=0,flags=8)
        b.call('close')
        done('a passed page-tag walk is reused until a heap page owner changes, then repeated',b,
             walked=counts[0],cached=counts[1])

        b = new(); b.load()
        # The provider's callback helper refuses an IRQ-disabled caller
        # before changing borrowed common registers or entering bank 0.
        entry = bs['provider_entry']
        original = bytes(b.bus.ram[1][entry:entry+7])
        b.bus.ram[1][entry:entry+7] = bytes([0x78,0xa9,5,0x4c])+bs['bk_native'].to_bytes(2,'little')+b'\x60'
        regs = bytes(b.ram[6:9]); b.call('call',8)
        assert b.ram[6:9] == regs
        b.bus.ram[1][entry:entry+7] = original
        b.call('close')
        done('banked callback with disabled IRQs refuses before entering native services',b)

        for size,entry in ((33,32),(0x6000,0x5fff)):
            image = bytearray(provider[:34])+bytearray([0x60])*(size-32)
            image[10:12] = size.to_bytes(2,'little'); image[12] = (size+255)//256
            image[14:16] = entry.to_bytes(2,'little')
            image = seal(image)
            b = new(image=image); b.load()
            b.call('call',47,operation=47,carry=0,flags=8)
            b.call('close')
            done(f'{size}-byte image and final executable-byte entry: exact load bounds and callee A/carry',b)
        report['passed'] = True
    finally:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__ == '__main__': main()
