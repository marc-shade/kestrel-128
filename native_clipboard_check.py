"""Independent clipboard ownership/bytes checks after native app cleanup."""
def published(machine):
    ram=machine.ram;token=bytes(ram[0x3deb:0x3def])
    assert not ram[0x3de6] and not ram[0x3def], 'clipboard call/draft remained live'
    if not token[0]:
        assert not ram[0x3de7] and ram[0x3de8:0x3deb]==bytes(3)
        return b'',0
    assert ram[0x3de5:0x3de8]==bytes([1,0,1])
    assert 1<=token[0]<=32
    at=0x3c00+(token[0]-1)*8;record=bytes(ram[at:at+8])
    assert record[0:2]==bytes([31,1]) and record[4:7]==token[1:]
    page,pages=record[2:4]
    assert 1<=pages<=60 and (4<=page and page+pages<=0x60 or 0xc0<=page and page+pages<=0xff)
    size=int.from_bytes(ram[0x3de8:0x3deb],'little')
    assert 1<=size<=15360 and pages==(size+255)//256
    assert bytes(ram[0x3900+page:0x3900+page+pages])==bytes([token[0]])*pages
    return bytes(machine.bus.ram[1][page*256:page*256+size]),pages

def released_stats(machine):
    data,pages=published(machine)
    records=[bytes(machine.ram[0x3c00+i*8:0x3c08+i*8]) for i in range(32)]
    live=[record for record in records if record[0]]
    assert len(live)==int(bool(data)) and all(record[0]==31 for record in live),live
    return 175,251-pages,32-int(bool(data))
