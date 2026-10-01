import ci_native_heap as heap
from native_banked_bus import BankedMemoryBus
BaseBus=BankedMemoryBus
class DisplayBus(BaseBus):
    def __init__(self):
        super().__init__()
        self.video={0xd011:0x1b,0xd012:255,0xd015:0,0xd016:0xc8,0xd018:0x15,
                    0xd01a:0xf1,0xdd00:0xc7,0xdd02:0x3f}
        self.video.update({address:0 for address in (0xd000,0xd001,0xd002,0xd003,
            0xd010,0xd017,0xd01b,0xd01c,0xd01d,0xd027,0xd028)})
        self.ram[0][0:2]=bytes([0x2f,0x73]);self.ram[0][0xd8]=0
        self.writes=[];self.raster_high=0x80;self.compare=255
    def __getitem__(self,address):
        assert self.config != 0x4e or self.ram[0][0x3d12] == 0, "app component executed while input/capture readiness was published"
        if not self.config&1 and address==0xd600:
            return 0            # This VIC-only model has no ready VDC.
        if not self.config&1 and (0xdf00<=address<=0xdf0a or 0xdf1c<=address<=0xdf1f):
            return 255          # No REU and no Ultimate command interface; fixtures override these ports.
        if not self.config&1 and address in self.video:
            return self.video[address]|self.raster_high if address==0xd011 else self.video[address]
        return super().__getitem__(address)
    def __setitem__(self,address,value):
        if not self.config&1 and address==0xd600:
            self.writes.append((address,value));return
        if not self.config&1 and address in self.video:
            self.writes.append((address,value))
            if address==0xd011:
                self.compare=(self.compare&255)|((value&128)<<1);value&=127
            elif address==0xd012:self.compare=(self.compare&256)|value
            self.video[address]=value;return
        return super().__setitem__(address,value)
