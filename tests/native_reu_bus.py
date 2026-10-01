"""REC bus behavior from pinned VICE reu.c, including holes and bank wrapping."""


class REUBusMixin:
    reu_kib = 512
    reu_present = True
    reu_configs = (0x0e,)

    def __init__(self):
        super().__init__()
        block = bytes((i*37+(i>>8)*73+19)&255 for i in range(65536))
        self.reu_ram = bytearray().join(block.translate(bytes((i+b*53)&255 for i in range(256)))
                                       for b in range(self.reu_kib//64))
        self.reu_reg = bytearray([16 if self.reu_kib != 128 else 0,
                                 0x10,0x34,0x12,0x78,0x56,0,0x23,0x01,0x1f,0x3f])
        self.reu_float = 0xff
        self.reu_transactions, self.reu_accesses = [], []
        self.reu_faults = set()
        self.reu_fault_from = None
        self.reu_fault_prefix = 0
        self.reu_after_dma = None
        self.reu_hosts = [(0x3a00,0x3c00)]
        self.reu_bank1_hosts = []
        self.reu_speed = 0xa1

    def __getitem__(self, address):
        if not self.config&1:
            if 0xdf00 <= address <= 0xdf0a:
                self.reu_accesses.append(('read',address))
                if not self.reu_present: return 0xff
                register = address-0xdf00
                value = self.reu_reg[register]
                if register == 0: self.reu_reg[0] &= 31
                if register == 6: value |= 0xf8  # upper bank latch is not readable
                return value
            if address == 0xd030: return self.reu_speed
        return super().__getitem__(address)

    def __setitem__(self, address, value):
        if not self.config&1:
            if address == 0xd030:
                self.reu_speed = value
                return
            if address == 0xd506:
                self.mmu[6] = value
                return
            if 0xdf00 <= address <= 0xdf0a:
                self.reu_accesses.append(('write',address,value))
                if not self.reu_present: return
                register = address-0xdf00
                if register:
                    if register == 9: value |= 31
                    if register == 10: value |= 63
                    self.reu_reg[register] = value
                if register == 1 and value&128:
                    assert value in (0x90,0x91), 'only immediate bounded stash/fetch'
                    self.reu_dma()
                return
        return super().__setitem__(address,value)

    def reu_physical(self, address):
        mask = (128 if self.reu_kib == 128 else max(512,self.reu_kib))*1024-1
        address &= mask
        return address if address < len(self.reu_ram) else None

    def reu_get(self, address):
        at = self.reu_physical(address)
        return self.reu_float if at is None else self.reu_ram[at]

    def reu_dma(self):
        r = self.reu_reg
        host = int.from_bytes(r[2:4],'little')
        address = int.from_bytes(r[4:7],'little')
        length = int.from_bytes(r[7:9],'little') or 65536
        assert 1 <= length <= 512, length
        bank = (self.mmu[6] >> 6)&1
        hosts = self.reu_bank1_hosts if bank else self.reu_hosts
        assert any(a <= host < host+length <= b for a,b in hosts), (bank,hex(host),length)
        assert not self.reu_speed&1
        assert r[9] == 31 and r[10] == 63
        assert self.config in self.reu_configs
        row = dict(host=host,address=address,count=length,command=r[1],host_bank=bank)
        self.reu_transactions.append(row)
        fault = (len(self.reu_transactions) in self.reu_faults or
                 self.reu_fault_from is not None and len(self.reu_transactions) >= self.reu_fault_from)
        count = min(length,self.reu_fault_prefix) if fault else length
        for _ in range(count):
            if r[1]&1:
                self.reu_float = self.reu_get(address)
                self.ram[bank][host] = self.reu_float
            else:
                self.reu_float = self.ram[bank][host]
                at = self.reu_physical(address)
                if at is not None: self.reu_ram[at] = self.reu_float
            host = (host+1)&65535
            low = (address&0x7ffff)+1
            if low == (0x20000 if self.reu_kib == 128 else 0x80000): low = 0
            address = (address&0xf80000)|low
        if r[1]&1: self.reu_float = self.reu_get(address)  # prefetched data latch
        r[2:4] = host.to_bytes(2,'little')
        r[4:7] = address.to_bytes(3,'little')
        r[7:9] = (1).to_bytes(2,'little')
        r[0] |= 0 if fault else 64
        r[1] = (r[1]&127)|16
        if self.reu_after_dma: self.reu_after_dma(self,row)
