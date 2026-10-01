#!/usr/bin/env python3
"""Execute the assembled native allocator with real C128 ROM bank gateways.

The small bus model implements the configurations used by this ABI, common
bottom RAM and ROM/I/O visibility. It is not a full C128 emulator; ci_native
separately cold-boots the actual disk in x128. No KERNAL transfer is mocked.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import re
import sys

from py65.devices.mpu6502 import MPU

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from hwlib import lst_symbol
IMAGE = ROOT/'target/native/kestrel.prg'
ROM = Path('/usr/share/vice/C128/kernal-318020-05.bin')
API = dict(alloc=0x1c20, free=0x1c23, read=0x1c26, write=0x1c29,
           fill=0x1c2c, stats=0x1c2f, release=0x1c32, reserve=0x1c35)
OWNER, PAGES, BANK, PAGE, HANDLE = 0x3d00, 0x3d01, 0x3d02, 0x3d03, 0x3d04
OFFSET, COUNT, VALUE, ERROR, FREE, BUSY = 0x3d08, 0x3d0a, 0x3d0c, 0x3d0d, 0x3d0e, 0x3d11
BUFFER, TABLES, RECORDS = 0x3a00, 0x3800, 0x3c00


def symbol(name):
    return lst_symbol(IMAGE.relative_to(ROOT/'target').with_suffix('').as_posix(),name)


class Bus:
    def __init__(self):
        self.ram = [bytearray((i*37+bank*83+0x51)&255 for i in range(65536))
                    for bank in (0, 1)]
        self.rom = ROM.read_bytes()
        assert len(self.rom) == 0x4000
        self.config = 0x0e
        self.mmu = bytearray.fromhex('0e3f7f0141b70400f001f020')
        self.io_reads, self.io_writes, self.far_writes, self.maps = [], [], [], []
        image = IMAGE.read_bytes(); origin = int.from_bytes(image[:2], 'little')
        self.ram[0][origin:origin+len(image)-2] = image[2:]
        # Native KERNAL initialization copies these exact ROM routines to
        # common RAM and installs the $ff05..$ff45 stubs in both banks.
        # The matching bytes are also captured after ci_native's cold boot.
        self.ram[0][0x2a2:0x2fc] = self.rom[0x3800:0x385a]
        self.ram[0][0x2aa], self.ram[0][0x2b9] = 0xbb, 0xae
        self.ram[0][0xfb:0xfd] = b'\x53\xa9'
        for bank in self.ram:
            bank[0xff05:0xff46] = self.rom[0x3f05:0x3f46]
            bank[0xfffa:0x10000] = self.rom[0x3ffa:0x4000]
        # A bounded foreground-independent interrupt handler: count then use
        # the real native restore gateway (including the extra saved MMU).
        self.ram[0][0xb00:0xb06] = b'\xee\x10\x0b\x4c\x33\xff'
        self.ram[0][0xb10] = 0
        for vector in (0x314, 0x316, 0x318):
            self.ram[0][vector:vector+2] = b'\0\x0b'

    def __getitem__(self, address):
        address &= 0xffff
        if address == 0xff00:
            return self.config
        if not self.config & 1 and 0xd000 <= address <= 0xdfff:
            if 0xd500 <= address <= 0xd50b:
                return self.config if address == 0xd500 else self.mmu[address-0xd500]
            self.io_reads.append(address)
            raise AssertionError(f'unexpected native heap I/O read ${address:04x}')
        if self.config in (0, 0x0e) and address >= 0xc000:
            return self.rom[address-0xc000]
        bank = 0 if address < 0x400 else (self.config >> 6) & 1
        return self.ram[bank][address]

    def __setitem__(self, address, value):
        address &= 0xffff
        if address == 0xff00:
            assert value in (0, 0x0e, 0x3f, 0x7f), hex(value)
            self.maps.append(value); self.config = value
            return
        if not self.config & 1 and 0xd000 <= address <= 0xdfff:
            self.io_writes.append((address, value))
            raise AssertionError(f'unexpected native heap I/O write ${address:04x}')
        bank = 0 if address < 0x400 else (self.config >> 6) & 1
        if bank or address >= 0x4000:
            self.far_writes.append((bank, address, value))
        self.ram[bank][address] = value


class Machine:
    calls = 0
    longest = 0

    def __init__(self):
        self.bus = Bus()
        self.ram = self.bus.ram[0]
        self.invoke(symbol('native_relocate'), check=False)
        self.invoke(symbol('heap_init'), check=False)
        assert self.stats() == (175, 251, 32)

    def invoke(self, entry, *, flags=0, expected=0, check=True, interrupt=None):
        cpu = MPU(memory=self.bus, pc=API.get(entry, entry))
        cpu.sp, cpu.p = 0xe0, flags | cpu.UNUSED
        cpu.stPushWord(0xaff)      # sentinel $0b00; not executed on return
        saved = bytes(self.ram[0xfb:0xfd]), self.ram[0x2aa], self.ram[0x2b9]
        initial_config = self.bus.config
        for steps in range(500000):
            if cpu.pc == 0xb00 and cpu.sp == 0xe0:
                break
            if interrupt:
                interrupt(cpu, self.bus)
            cpu.step()
        else:
            raise AssertionError(f'{entry} did not return: PC=${cpu.pc:04x}, MMU=${self.bus.config:02x}')
        Machine.calls += 1; Machine.longest = max(Machine.longest, steps)
        assert cpu.sp == 0xe0
        assert cpu.p & 0x0c == flags & 0x0c, (entry, 'D/I changed')
        assert self.bus.config == initial_config, (entry, 'MMU changed')
        assert saved == (bytes(self.ram[0xfb:0xfd]), self.ram[0x2aa], self.ram[0x2b9])
        assert not self.bus.io_reads and not self.bus.io_writes
        if check:
            assert (cpu.a, cpu.p & 1) == (expected, int(bool(expected))), (entry, cpu.a, cpu.p, expected)
            if expected != 7:
                assert self.ram[ERROR] == expected and self.ram[BUSY] == 0
        return cpu

    def set(self, address, value, length=1):
        self.ram[address:address+length] = value.to_bytes(length, 'little')

    def stats(self):
        self.invoke('stats')
        return tuple(self.ram[FREE:FREE+3])

    def alloc(self, pages, bank=0xff, owner=16, page=None, expected=0, flags=0):
        self.set(OWNER, owner); self.set(PAGES, pages); self.set(BANK, bank)
        if page is not None:
            self.set(PAGE, page)
        self.invoke('reserve' if page is not None else 'alloc', expected=expected, flags=flags)
        return bytes(self.ram[HANDLE:HANDLE+4])

    def select(self, handle, owner=16):
        self.ram[HANDLE:HANDLE+4] = handle
        self.set(OWNER, owner)

    def transfer(self, op, offset, count, expected=0, **kwargs):
        self.set(OFFSET, offset, 2); self.set(COUNT, count, 2)
        self.invoke(op, expected=expected, **kwargs)

    def metadata(self):
        return bytes(self.ram[TABLES:TABLES+512])+bytes(self.ram[RECORDS:RECORDS+256])


def capacity_and_slots():
    m = Machine()
    one = m.alloc(251)
    assert (m.ram[BANK], m.ram[PAGE]) == (1, 4)
    zero = m.alloc(175)
    assert (m.ram[BANK], m.ram[PAGE]) == (0, 0x50)
    assert m.stats() == (0, 0, 30)
    before = m.metadata(); m.alloc(1, expected=2); assert m.metadata() == before
    m.select(one); m.invoke('free')
    m.select(zero); m.invoke('free'); assert m.stats() == (175, 251, 32)
    handles = [m.alloc(1) for _ in range(32)]
    before = m.metadata(); m.alloc(1, expected=3); assert m.metadata() == before
    m.select(handles[17]); m.invoke('free'); old = handles[17]
    new = m.alloc(1); assert new[0] == old[0] and new[1:] != old[1:]
    m.select(old); m.invoke('free', expected=4)
    m.select(new, owner=17); m.invoke('free', expected=5)
    m.set(OWNER, 16); m.invoke('release'); assert m.stats() == (175, 251, 32)
    # Fixed graphics/DMA reservations and fragmentation must affect first fit.
    a = m.alloc(1, 0, page=0x51)
    m.alloc(173, 0, page=0x52)
    assert m.stats() == (1, 251, 30)
    m.alloc(2, 0, expected=2)
    m.select(a); m.invoke('free')
    m.alloc(2, 0); assert m.ram[PAGE] == 0x50
    m.set(OWNER, 16); m.invoke('release')
    # Handles never wrap back to an earlier generation, including carry.
    m.ram[RECORDS+4:RECORDS+7] = b'\xff\xff\xfe'
    near = m.alloc(1); assert near == b'\1\0\0\xff'
    m.invoke('free')
    m.ram[RECORDS+4:RECORDS+7] = b'\xfe\xff\xff'
    final = m.alloc(1); assert final == b'\1\xff\xff\xff'
    m.invoke('free'); assert m.stats() == (175, 251, 31)
    later = m.alloc(1); assert later[0] == 2 and m.ram[RECORDS] == 255
    m.select(final); m.invoke('free', expected=4)
    assert not m.bus.far_writes, 'allocator modified user data'


def transfer_boundaries():
    rng = random.Random(128)
    count = 0
    # Identical physical addresses in both banks, including RAM under I/O/ROM
    # and the very last available byte. Model expectations are host-generated.
    for page in (0x50, 0xbf, 0xcf, 0xdf, 0xfd):
        m = Machine(); handles = [m.alloc(2, bank, page=page) for bank in (0, 1)]
        expected = [bytearray(m.bus.ram[b][page*256:(page+2)*256]) for b in (0, 1)]
        for bank in (0, 1):
            m.select(handles[bank])
            for offset, size in ((0,512),(255,257),(511,1),(1,256),(254,3)):
                data = rng.randbytes(size)
                m.ram[BUFFER:BUFFER+size] = data
                m.transfer('write', offset, size, flags=0x0c)
                expected[bank][offset:offset+size] = data
                m.ram[BUFFER:BUFFER+512] = b'\xcc'*512
                m.transfer('read', offset, size)
                assert m.ram[BUFFER:BUFFER+size] == data
                assert m.ram[BUFFER+size:BUFFER+512] == b'\xcc'*(512-size)
                for b in (0, 1):
                    assert m.bus.ram[b][page*256:(page+2)*256] == expected[b]
                count += 1
            m.set(VALUE, 0x56+bank); m.transfer('fill', 255, 257)
            expected[bank][255:512] = bytes([0x56+bank])*257
            assert m.bus.ram[bank][page*256:(page+2)*256] == expected[bank]
        assert all(page*256 <= address < (page+2)*256 for _, address, _ in m.bus.far_writes)
        assert set(m.bus.maps) == {0x0e,0x3f,0x7f}
    # Every possible count near the legal maximum, offset overflow and the
    # caller's decimal/interrupt states: reject before any data/table write.
    m = Machine(); m.alloc(2,1)
    cases = [(0,0),(0,513),(0,768),(0,65535),(1,512),(256,257),
             (512,1),(65535,1),(65535,512),(65024,512)]
    for op in ('read','write','fill'):
        for flags in (0,4,8,12):
            for offset, size in cases:
                metadata, buffer = m.metadata(), bytes(m.ram[BUFFER:BUFFER+512])
                far = len(m.bus.far_writes)
                m.transfer(op,offset,size,expected=6,flags=flags)
                assert m.metadata() == metadata and bytes(m.ram[BUFFER:BUFFER+512]) == buffer
                assert len(m.bus.far_writes) == far
    return count


def rejected_arguments_and_corruption():
    m = Machine()
    for owner, pages, bank in ((0,1,0),(255,1,0),(16,0,0),(16,1,2),(16,1,254)):
        before=m.metadata(); m.alloc(pages,bank,owner,expected=1); assert m.metadata()==before
    for bank,page,pages in ((0,0x4f,1),(0,0x40,16),(1,3,1),(0,0xff,1),(1,0xfe,2),(0,0x80,0x80)):
        before=m.metadata(); m.alloc(pages,bank,page=page,expected=6); assert m.metadata()==before
    a = m.alloc(2,0,owner=16); b = m.alloc(2,1,owner=16); foreign = m.alloc(2,1,owner=17)
    record = RECORDS+(b[0]-1)*8
    for delta,value in ((1,2),(2,3),(2,0xff),(3,0),(3,255)):
        previous=m.ram[record+delta]; m.ram[record+delta]=value
        before=m.metadata(); m.select(b)
        for op in ('free','read','write','fill','release'):
            m.set(COUNT,1,2); m.invoke(op,expected=9)
            assert m.metadata()==before, (delta,op,'partial mutation')
        m.ram[record+delta]=previous
    tag_address = 0x3900+m.ram[record+2]
    saved=m.ram[tag_address]; m.ram[tag_address]=0
    before=m.metadata(); m.invoke('release',expected=9); assert m.metadata()==before
    m.ram[tag_address]=saved
    m.set(OWNER,16); m.invoke('release'); assert m.stats() == (175,249,31)
    m.select(foreign,17); m.invoke('free'); assert m.stats()==(175,251,32)
    for handle in (b'\0\0\0\0',b'\x21\1\0\0',a,b):
        m.select(handle); m.invoke('free',expected=4)
    # A busy call must not overwrite the active result, lock or parameters.
    m.set(BUSY,1); m.set(ERROR,0xa7)
    before=bytes(m.ram[0x3800:0x3d20])
    for op in API:
        m.invoke(op,expected=7,flags=12)
        assert bytes(m.ram[0x3800:0x3d20])==before
    m.set(BUSY,0)
    for offset,value in ((5,0xf7),(6,5),(7,2),(8,0xf1),(9,2),(10,0xf1)):
        saved=m.bus.mmu[offset]; m.bus.mmu[offset]=value
        before=m.metadata(); m.invoke('stats',expected=8); assert m.metadata()==before
        m.bus.mmu[offset]=saved
    m.bus.config=0x3f; m.invoke('stats',expected=8); m.bus.config=0x0e
    assert m.stats()==(175,251,32)
    assert not m.bus.far_writes


def interrupt_boundaries():
    injected = 0
    for op in ('read','write','fill'):
        # Collect every instruction in the actual first-byte bank gateway.
        # Interrupt at each boundary independently, including when RAM1 is
        # mapped and kernel code/ROM is temporarily absent.
        m = Machine(); m.alloc(1,1,page=0xe0)
        m.ram[BUFFER] = 0xa9; m.ram[VALUE] = 0x73
        trace=[]
        def trace_gateway(cpu,bus):
            if 0x2a2 <= cpu.pc < 0x2c2 or 0xf7d0 <= cpu.pc < 0xf7e4:
                trace.append((cpu.pc,bus.config))
        m.transfer(op,0,1,interrupt=trace_gateway)
        points=list(dict.fromkeys(trace))
        assert any(config==0x7f for _,config in points)
        for kind in ('nmi','irq'):
            for pc,config in points:
                m = Machine(); m.alloc(1,1,page=0xe0)
                original=m.bus.ram[1][0xe000]
                m.ram[BUFFER]=0xa9; m.ram[VALUE]=0x73
                fired=[]
                def inject(cpu,bus):
                    if not fired and (cpu.pc,bus.config)==(pc,config):
                        fired.append(True)
                        if kind=='nmi': cpu.nmi()
                        else: cpu.irq()    # SEI must defer IRQ while banked
                m.transfer(op,0,1,interrupt=inject)
                assert fired
                assert m.ram[0xb10]==int(kind=='nmi'), (kind,pc,config)
                if op=='read': assert m.ram[BUFFER]==original
                else: assert m.bus.ram[1][0xe000]==(0xa9 if op=='write' else 0x73)
                injected+=1
        # IRQ delivery between bytes remains enabled for normal callers.
        m=Machine(); m.alloc(2,1,page=0xe0); m.ram[BUFFER:BUFFER+512]=bytes(range(256))*2
        point=symbol('heap_transfer_loop'); remaining=symbol('hremaining'); delivered=set()
        def between(cpu,bus):
            current=bytes(m.ram[remaining:remaining+2])
            if cpu.pc==point and current not in delivered:
                assert not cpu.p & cpu.INTERRUPT
                delivered.add(current); cpu.irq()
        m.transfer(op,0,512,interrupt=between)
        assert len(delivered)==512 and m.ram[0xb10]==0
        injected+=512
    return injected


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--report',type=Path); args=parser.parse_args()
    report=dict(image_sha256=hashlib.sha256(IMAGE.read_bytes()).hexdigest(),
                rom_path=str(ROM),rom_sha256=hashlib.sha256(ROM.read_bytes()).hexdigest(),passed=False)
    try:
        capacity_and_slots(); print('PASS: full native capacity, slots, reservations, fragmentation and generation retirement',flush=True)
        report['bank_boundary_transfers']=transfer_boundaries()
        print('PASS: both-bank ROM/I/O overlap, transfer edges and rejected bounds',flush=True)
        rejected_arguments_and_corruption(); print('PASS: ownership, stale handles, corrupt records, atomic release and busy/platform errors',flush=True)
        report['interrupt_attempts']=interrupt_boundaries()
        print('PASS: native ROM gateways, NMI bank restoration and IRQ deferral/delivery',flush=True)
        report.update(passed=True,calls=Machine.calls,longest_instructions=Machine.longest,
                      managed_pages=426,managed_bytes=109056)
    finally:
        if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')
    return 0


if __name__=='__main__':raise SystemExit(main())
