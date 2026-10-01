#!/usr/bin/env python3
"""Assembled 1351 counter protocol, desktop gestures and exact input teardown."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ci_native_heap as heap
from native_display_bus import DisplayBus
from native_clipboard_check import released_stats


class PointerBus(DisplayBus):
    def __init__(self):
        super().__init__()
        self.raster_high = 0
        self.raster = 100
        self.video.update({0xdc00:0x7f,0xdc02:255,0xdc03:0,0xd02f:0xf8})
        for address in (0xd000,0xd001,0xd002,0xd003,0xd010,0xd017,0xd01b,0xd01c,0xd01d,0xd027,0xd028):
            self.video[address] = (address*17+23)&255
        self.initial = dict(self.video)
        self.init_status = self.ram[0][0xa04]
        self.pots = [64,64]
        self.down = False
        self.samples = 0

    def __getitem__(self, address):
        if not self.config&1:
            if address==0xd012:return self.raster
            if address in (0xd419,0xd41a):
                self.samples += 1
                assert self.video[0xdc00]==0x7f
                return self.pots[address-0xd419]
            if address==0xdc01:
                assert self.video[0xdc00]==255 and self.video[0xd02f]&7==7, 'keyboard columns can masquerade as mouse button'
                return 0xef if self.down else 255
        return super().__getitem__(address)


heap.Bus = PointerBus
import ci_native_calc as calc
from py65.devices.mpu6502 import MPU
from launcher_scene import surface, console, CARDS


class Pointer(calc.Calculator):
    instruction_limit = 12000000

    def __init__(self, **kwargs):
        super().__init__('desktop', loader_name=b'BROWSE', image_prefix='native-desktop', **kwargs)
        self.bus = self.m.bus
        self.frames = 0
        assert self.ram[0xa04]==self.bus.init_status&0xfe

    @property
    def position(self):
        start = self.symbol('pm_x')
        return int.from_bytes(self.ram[start:start+2], 'little'), self.value('pm_y')

    def frame(self, dx=0, dy=0, down=None, *, exited=False):
        assert -31<=dx<=31 and -31<=dy<=31
        if dx:self.bus.pots[0]=64+((self.bus.pots[0]-64+dx*2)&127)
        if dy:self.bus.pots[1]=64+((self.bus.pots[1]-64-dy*2)&127)
        if down is not None:self.bus.down=down
        jiffies=int.from_bytes(self.ram[0xa0:0xa3],'big')+1   # the KERNAL's UDTIM: carry, reset at 24 h
        self.ram[0xa0:0xa3]=(0 if jiffies>=0x4f1a01 else jiffies).to_bytes(3,'big')
        self.poll()
        line=self.bus.raster
        self.bus.raster=min(255,line+32)
        self.poll(exited)
        self.bus.raster=line
        self.frames += 1
        if not exited:
            assert self.bus.video[0xdc00]==0x7f and self.bus.video[0xd02f]==self.bus.initial[0xd02f]
            assert self.bus.video[0xdc02]==255 and self.bus.video[0xdc03]==0
            x,y=self.position
            assert (self.bus.video[0xd000]|((self.bus.video[0xd010]&1)<<8),self.bus.video[0xd001])==(x+24,y+50)
            assert self.bus.video[0xd000]==self.bus.video[0xd002] and self.bus.video[0xd001]==self.bus.video[0xd003]

    def poll(self,exited=False):
        assert self.cpu.pc==0xffe4
        self.cpu.a=0;self.cpu.FlagsNZ(0);self.cpu.pc=self.cpu.stPopWord()+1
        self.loop(exited)

    def move(self,x,y):
        while self.position!=(x,y):
            px,py=self.position
            self.frame(max(-20,min(20,x-px)),max(-20,min(20,y-py)))

    def check(self,selected):
        assert self.value('gd_selected')==selected and self.ram[0x3d2f]==selected
        assert bytes(self.ram[0xc000:0xe400])==surface(selected)
        assert self.screens[1]==console(80,selected)

    def restored(self):
        for address in (0xd000,0xd001,0xd002,0xd003,0xd010,0xd015,0xd017,0xd01b,0xd01c,0xd01d,0xd027,0xd028,0xdc00,0xdc02,0xdc03,0xd02f):
            assert self.bus.video[address]==self.bus.initial[address], hex(address)
        assert self.ram[0xa04]==self.bus.init_status
        assert not self.value('pm_active') and not self.ram[heap.symbol('v_tag')]
        assert not self.value('nk_active')
        at=self.symbol('nk_saved_callback')
        if bytes(self.ram[at:at+2])!=bytes(2):
            assert bytes(self.ram[0x033c:0x033e])==bytes(self.ram[at:at+2])
            at=self.symbol('nk_saved_keys');assert bytes(self.ram[0x1000:0x1100])==bytes(self.ram[at:at+256])
        assert self.m.stats()==released_stats(self.m)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True);args=parser.parse_args()
    report=dict(passed=False,physical_hardware_io=False,cases=[],images={
        'target/native/kestrel.prg':hashlib.sha256(heap.IMAGE.read_bytes()).hexdigest(),
        'target/native-desktop/desktop.prg':hashlib.sha256((ROOT/'target/native-desktop/desktop.prg').read_bytes()).hexdigest()})
    def done(name,p,**extra):
        report['cases'].append(dict(name=name,frames=p.frames,instructions=p.instructions,**extra));print('PASS:',name,flush=True)
    try:
        p=Pointer();p.check(0)
        # Exhaust all counter pairs, executing the assembled displacement routine.
        cpu=MPU(memory=p.bus);entry=p.symbol('pm_delta');pairs=0
        stack=bytes(p.ram[0x100:0x200])
        for old in range(64,192):
            for new in range(64,192):
                cpu.pc=entry;cpu.sp=0xe0;cpu.p=0x20;cpu.a=new;cpu.y=old;cpu.stPushWord(0xaff)
                for _ in range(50):
                    if cpu.pc==0xb00:break
                    cpu.step()
                assert cpu.pc==0xb00
                raw=(new-old+64)%128-64
                want=raw//2 if abs(raw)>1 else 0
                observed=cpu.a if cpu.x==0 else cpu.a-256
                assert (observed,bool(cpu.p&1),cpu.y)==(want,bool(want),new if want else old),(old,new,observed,want)
                pairs+=1
        p.ram[0x100:0x200]=stack
        p.frame();assert p.position==(160,160) and p.value('pm_seen')==1 and p.bus.video[0xd015]==3
        p.key(27,exited=True);p.restored();done('all 16384 circular counter pairs and stationary attach',p,counter_pairs=pairs)

        for index,name in enumerate((b'CALC',b'EDITOR',b'FILES',b'ULTIMATE',b'CLAUDE',b'PAINT',b'SHEET')):
            p=Pointer();p.frame();p.move(100,CARDS[index]+8);p.check(index)
            p.frame(down=True);p.check(index);assert p.value('pm_arm')==index
            for _ in range(3):p.frame(down=True)
            assert p.ram[0x3d20]==32
            p.frame(down=False,exited=True);p.restored()
            assert p.ram[0x3d28]==1 and bytes(p.ram[0x3d40:0x3d40+len(name)])==name
            done('hover, press, hold, release opens '+name.decode(),p)

        p=Pointer();p.bus.down=True;p.frame();p.move(100,40);p.frame(down=False);p.check(0)
        assert p.value('pm_arm')==255
        p.frame(down=True);p.move(10,40);p.frame(down=False);assert p.ram[0x3d20]==32
        p.move(100,40);p.frame(down=True);p.move(100,64);p.frame(down=False);p.check(1)
        p.move(100,30);p.frame(down=True);p.move(100,40);p.frame(down=False);assert p.ram[0x3d20]==32
        p.key(27,exited=True);p.restored();done('held on attach, drag outside, drag to another card and press outside cancel launch',p)

        p=Pointer();p.frame();p.move(100,40);p.key(9);p.check(1)
        for _ in range(4):p.frame();p.check(1)
        p.frame(dx=1);p.check(0)
        p.key(ord('E'),exited=True);p.restored();done('stationary pointer preserves keyboard selection; renewed movement resumes hover',p)

        p=Pointer();p.frame()
        for target in ((0,0),(319,199),(0,199),(319,0)):
            p.move(*target);p.frame(dx=-31 if target[0]==0 else 31,dy=-31 if target[1]==0 else 31)
            assert p.position==target
        for x,y,want in ((15,48,255),(16,40,0),(303,55,0),(304,48,255),(100,39,255),(100,56,1),
                         (100,135,5),(100,136,6),(303,151,6),(100,152,255)):
            p.move(x,y);assert p.value('pm_hit')==want,(x,y,p.value('pm_hit'))
        p.key(27,exited=True);p.restored();done('four edges saturate and card hit bounds exclude gaps and borders outside',p)

        p=Pointer();p.frame();p.move(100,40);p.frame(down=True)
        p.bus.pots=[255,255]
        # Poll an open port without converting its values into proportional data.
        p.frame()
        assert not p.value('pm_seen') and p.value('pm_arm')==255 and p.bus.video[0xd015]==0
        p.bus.pots=[64,64];p.frame(down=True);p.frame(down=False);assert p.ram[0x3d20]==32
        p.key(27,exited=True);p.restored();done('disconnect cancels armed click; reconnect baselines counters and held button',p)

        p=Pointer();p.frame();samples=p.bus.samples
        for high,line in ((128,100),(0,79),(0,160),(0,255)):
            p.bus.raster_high=high;p.bus.raster=line;p.ram[0xa2]=(p.ram[0xa2]+1)&255;p.poll()
            assert p.bus.samples==samples
        p.bus.raster_high=0;p.bus.raster=100;p.frame();assert p.bus.samples==samples+2
        for address,value in ((0xdc02,0xc0),(0xdc03,1),(0xdc00,0xff)):
            before=p.bus.video[address];p.bus.video[address]=value
            p.ram[0xa2]=(p.ram[0xa2]+1)&255;p.poll();p.bus.raster=132;p.poll();p.bus.raster=100
            assert p.bus.video[address]==value and p.bus.video[0xd015]==0 and not p.value('pm_seen')
            p.bus.video[address]=before
        p.key(27,exited=True);p.restored();done('raster settling guard and foreign CIA configurations are respected',p)
        p=Pointer();p.frame();samples=p.bus.samples
        p.bus.raster=100;p.ram[0xa2]=(p.ram[0xa2]+1)&255;p.poll()
        assert p.bus.samples==samples
        p.bus.raster=131;p.poll();assert p.bus.samples==samples
        # A late ROM IRQ changes the jiffy while a read is pending: restart
        # the settling interval, even though the raster is in the usual band.
        p.bus.raster=132;p.ram[0xa2]=(p.ram[0xa2]+1)&255;p.poll()
        assert p.bus.samples==samples
        p.bus.raster=159;p.poll();assert p.bus.samples==samples
        p.bus.raster=164;p.poll();assert p.bus.samples==samples
        p.bus.raster=100;p.frame();assert p.bus.samples==samples+2
        p.key(27,exited=True);p.restored();done('late ROM IRQ restarts full conversion delay; late frames are skipped',p)
        report['passed']=True
    except BaseException as error:report['error']=repr(error);raise
    finally:args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
