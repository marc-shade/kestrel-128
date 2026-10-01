#!/usr/bin/env python3
"""Paint's copied ROM-visible filter (input/key-filter.inc). Since 11d64e2 it
rechecks every decoded key against the matrix: a key passes only when its row
is low with its own column selected and not with no columns selected, so
fire aliases on row 4 and phantom keys from nested ROM scans are rejected."""
import argparse
import hashlib
import json
from pathlib import Path

import ci_native_heap as heap
from ci_native_pointer import PointerBus
from ci_native_paint_document import Paint
from py65.devices.mpu6502 import MPU


class MatrixBus(PointerBus):
    keys=set()
    def __getitem__(self,address):
        if address==0xdc01 and not self.config&1:
            value=0xef if self.down else 255
            for index in self.keys:
                column,row=divmod(index,8)
                selected=self.video[0xdc00] if column<8 else self.video[0xd02f]
                if not selected&(1<<(column%8)):value&=255^(1<<row)
            return value
        return super().__getitem__(address)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True);args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    report=dict(passed=False,physical_hardware_io=False,cases=[],images={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (root/'target/native-desktop/paint.prg',root/'target/native/kestrel.prg')})
    prior=heap.Bus
    try:
        heap.Bus=MatrixBus;p=Paint();entry=p.symbol('pk_entry');end=p.symbol('pk_end')
        template=p.symbol('pa_key_filter_image')
        assert entry==0x1014 and end<=0x1100
        original_callback=bytes(p.ram[p.symbol('pa_keys_callback'):p.symbol('pa_keys_callback')+2])
        next_at=p.symbol('pk_next');p.ram[next_at:next_at+2]=(0xb10).to_bytes(2,'little')
        accepted=rejected=0;stack=bytes(p.ram[0x100:0x200])
        for mapping in (0,0x0e):
            for index in range(96):
                for down,pressed in ((False,False),(False,True),(True,False),(True,True)):
                    p.bus.keys={index} if pressed else set();p.bus.down=down
                    p.bus.video[0xdc00]=255;p.bus.video[0xd02f]=0xfb
                    p.bus[0xff00]=mapping
                    cpu=MPU(memory=p.bus,pc=entry);cpu.sp=0xe0;cpu.p=0x21;cpu.a=0x4d;cpu.x=2;cpu.y=index;cpu.stPushWord(0xaff)
                    for _ in range(250):
                        if cpu.pc in (0xb00,0xb10):break
                        cpu.step()
                    else:raise AssertionError(('filter did not return',hex(cpu.pc)))
                    blocked=index<88 and (not pressed or (down and index%8==4))
                    assert cpu.pc==(0xb00 if blocked else 0xb10),(mapping,index,down,pressed,hex(cpu.pc))
                    assert p.bus.config==mapping and cpu.x==2 and cpu.y==index and cpu.p&0x0d==1
                    assert p.bus.video[0xd02f]==0xfb
                    assert p.bus.video[0xdc00]==(0x7f if blocked else 255)
                    if blocked:rejected+=1
                    else:accepted+=1;assert cpu.a==0x4d and cpu.sp==0xde
        p.ram[0x100:0x200]=stack;p.bus[0xff00]=0x0e;p.bus.keys=set();p.bus.down=False
        p.bus.video[0xdc00]=0x7f;p.bus.video[0xd02f]=p.bus.initial[0xd02f]
        p.ram[next_at:next_at+2]=original_callback
        counter=p.symbol('pk_rejects');assert int.from_bytes(p.ram[counter:counter+2],'little')==rejected
        saved=bytes(p.ram[p.symbol('pa_saved_keys'):p.symbol('pa_saved_keys')+256])
        p.close();p.restored()
        assert bytes(p.ram[0x1000:0x1100])==saved and bytes(p.ram[0x33c:0x33e])==original_callback
        report.update(passed=True,accepted=accepted,rejected=rejected,
            cases=['all 96 scan ordinals, fire and key combinations under ROM and app mappings',
                   'genuine keys chain unchanged; unpressed keys and held-fire row-4 aliases rejected',
                   'registers, MMU, CIA columns, stack, whole function table and prior callback preserved/restored'])
        print('PASS:',accepted,'accepted and',rejected,'rejected callback cases; complete restoration',flush=True)
    except BaseException as error:report['error']=repr(error);raise
    finally:heap.Bus=prior;args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
