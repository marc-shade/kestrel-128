"""C128 CPU map used by the banked executor tests, including common-RAM size.

The ROM common routines and heap gates execute their actual machine code.
VICE cold boots independently check MMU, IRQ and DMA behavior.
"""
import ci_native_heap as heap
from native_reu_bus import REUBusMixin


class BankedMemoryBus(heap.Bus):

    def physical_bank(self, address):
        size = (0x400, 0x1000, 0x2000, 0x4000)[self.mmu[6]&3]
        common = (self.mmu[6]&4 and address < size or
                  self.mmu[6]&8 and address >= 0x10000-size)
        return 0 if common else self.config>>6&1

    def __getitem__(self, address):
        address &= 65535
        if address == 0xff00 or not self.config&1 and 0xd000 <= address < 0xe000:
            return super().__getitem__(address)
        if self.config in (0, 0x0e, 0x4e) and address >= 0xc000:
            return self.rom[address-0xc000]
        return self.ram[self.physical_bank(address)][address]

    def __setitem__(self, address, value):
        address &= 65535
        if address == 0xff00:
            assert value in (0, 0x0e, 0x4e, 0x3f, 0x7f), hex(value)
            self.maps.append(value)
            self.config = value
            return
        if not self.config&1 and address == 0xd506:
            self.mmu[6] = value
            return
        if not self.config&1 and 0xd000 <= address < 0xe000:
            return super().__setitem__(address, value)
        bank = self.physical_bank(address)
        if bank or address >= 0x4000:
            self.far_writes.append((bank, address, value))
        self.ram[bank][address] = value


class BankedBus(REUBusMixin, BankedMemoryBus):
    reu_configs = (0x0e, 0x4e)
