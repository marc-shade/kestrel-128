#!/usr/bin/env python3
"""Real NAPP calculator logic behind bitmap controls, with owned input/display."""
import argparse
import hashlib
import json
from pathlib import Path

from ci_native_pointer import Pointer, calc, heap, PointerBus
from native_calc_scene import BUTTONS, surface
from native_capture import calculator_screen
from py65.devices.mpu6502 import MPU

ROOT=Path(__file__).resolve().parents[1]


class GraphicalCalculator(Pointer):
    def __init__(self, **kwargs):
        calc.Calculator.__init__(self,'calc',image_prefix='native-desktop',**kwargs)
        self.bus=self.m.bus;self.frames=0

    def click(self,index,*,exited=False):
        (x0,y0,x1,y1),_,_=BUTTONS[index]
        self.move((x0+x1)//2,(y0+y1)//2)
        self.frame(down=True);self.frame(down=False,exited=exited)

    def check(self):
        dialog=bool(self.value('save_mode'));status=self.value('save_status')
        name=bytes(self.ram[self.symbol('save_name'):self.symbol('save_name')+self.value('save_length')]).decode()
        history=self.history();view=self.value('history_view')
        bitmap=bool(self.value('cg_bitmap'))
        if bitmap:
            want=surface(self.display(),history,view,self.value('ui_selected'),dialog=dialog,
                         name=name,cursor=self.value('save_cursor'),status=status)
            actual=bytes(self.ram[0xc000:0xe400])
            assert actual==want,('bitmap mismatch',next((i for i,(a,b) in enumerate(zip(actual,want)) if a!=b),None),self.display(),dialog)
            assert self.ram[heap.symbol('v_tag')]==self.value('cg_handle')
        messages=[None,'HISTORY SAVED AND VERIFIED','DISK ERROR; FILE MAY BE PARTIAL',
                  'FILE EXISTS - CHOOSE ANOTHER NAME','NO RESULTS TO SAVE',
                  'PATH TOO LONG; SHORTEN NAME','INPUT UNAVAILABLE; ESC RETURNS']
        for bank in ((1,) if bitmap else (0,1)):
            if bank == 1 and self.value('vd_phase'):
                continue
            cols=(40,80)[bank]
            want=calculator_screen(cols,self.display(),history,view,name if dialog else None,
                None if dialog else messages[status],usb=self.ram[0x3d2c]==3,
                save_caret=self.value('save_cursor'),save_view=self.ram[self.symbol('save_views')+bank])
            assert self.screens[bank]==want,('text mismatch',bank,dialog,status)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True);args=parser.parse_args()
    report=dict(passed=False,physical_hardware_io=False,cases=[],images={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (ROOT/'target/native-desktop/calc.prg',heap.IMAGE)})
    def done(name,p,**extra):
        report['cases'].append(dict(name=name,frames=p.frames,keys=p.events,instructions=p.instructions,**extra))
        print('PASS:',name,flush=True)
    original=calc.Machine
    try:
        p=GraphicalCalculator();p.check();assert p.value('cg_bitmap')==1
        for text,want in [('12+30=','42'),('65535/255=','257'),('65535/32768=','1'),('65535*1=','65535'),
                          ('300*300=','OVF'),('65535+1=','OVF'),('0-1=','OVF'),('37/0=','DIV/0'),
                          ('9=+1=','10'),('5+6*7=','77'),('12345\x14=','1234')]:
            p.type('C'+text);assert p.display()==want;p.check()
        p.key(27,exited=True);p.restored();done('all arithmetic and errors retain exact bitmap, VDC and cleanup',p,arithmetic_cases=11)

        p=GraphicalCalculator();p.frame()
        for index in (8,9,15,10,13,14):p.click(index);p.check()
        assert p.display()=='42' and p.history()==['42'] and p.events==0
        p.click(12);p.click(0);p.click(1);p.click(2);p.click(16);assert p.display()=='78'
        p.click(3);p.click(1);p.click(14);assert p.display()=='9'
        p.click(7);p.click(5);p.click(14);assert p.display()=='45'
        p.click(11);p.click(4);p.click(14);assert p.display()=='41'
        p.check();p.click(20,exited=True);p.restored();done('all digit/operator/delete buttons use arithmetic engine; mouse close restores resources',p)

        p=GraphicalCalculator();p.frame();p.move(32,80);p.frame(down=True);p.move(72,80);p.frame(down=False)
        assert p.display()=='0'
        p.key(9);selected=p.value('ui_selected')
        for _ in range(3):p.frame();assert p.value('ui_selected')==selected
        p.key(32);assert p.display()=='9';p.key(13);assert p.history()==['9']
        p.key(0x9d);p.check();p.key(27,exited=True);p.restored()
        done('drag cancellation, stationary mouse with keyboard focus, Space activation and Enter equals',p)

        p=GraphicalCalculator()
        for number in range(1,41):p.type('C'+str(number)+'=')
        assert p.history()==list(map(str,range(40,8,-1)));p.check();p.frame()
        for view in (8,16,24,24):p.click(18);assert p.value('history_view')==view;p.check()
        for view in (16,8,0,0):p.click(19);assert p.value('history_view')==view;p.check()
        p.click(17);p.type('HISTORY');p.check();p.click(21)
        assert bytes(p.io.files[8,b'HISTORY',b'S'])==b''.join(str(n).encode()+b'\r' for n in range(9,41))
        assert not p.io.handles;p.check();p.click(17);p.type('HISTORY');p.click(21);assert p.value('save_status')==3;p.check()
        p.click(17);p.type('CANCEL');p.key(9);p.check();p.key(13);assert not p.value('save_mode')
        assert (8,b'CANCEL',b'S') not in p.io.files;p.check()
        p.click(17);p.type('MOUSECANCEL');p.click(22);assert not p.value('save_mode');p.check()
        p.click(17);p.type('PARTIAL');p.io.fail_flush=True;p.click(21);assert p.value('save_status')==2;p.check()
        p.io.fail_flush=False;p.key(27,exited=True);p.restored()
        done('32-result ring, mouse history paging, verified save, exclusive collision, both cancel controls and write fault',p)

        p=GraphicalCalculator();p.type('S');assert p.value('save_status')==4;p.check()
        p.type('12=SA123456789012345');p.check();assert p.value('save_cursor')==16
        p.key(0x9d);p.key(20);p.check();p.key(27);p.check();p.key(27,exited=True);p.restored()
        done('empty-history status and full-length filename caret/edit/cancel',p)

        class Fragmented(original):
            def __init__(self):
                super().__init__();self.obstacle=self.alloc(1,0,77,page=0xd0)
        calc.Machine=Fragmented
        p=GraphicalCalculator();assert p.value('cg_bitmap')==0 and p.value('cg_error')==2
        p.type('12+30=');p.check();assert p.bus.video[0xd015]==0
        p.m.select(p.m.obstacle,77)
        stack=bytes(p.ram[0x100:0x200]);p.m.invoke('free');p.ram[0x100:0x200]=stack
        p.key(27,exited=True);p.restored();done('occupied surface keeps both text consoles and unrelated allocation usable',p)
        class Unsupported(original):
            def __init__(self):super().__init__();self.bus.video[0xd015]=1
        calc.Machine=Unsupported
        p=GraphicalCalculator();assert p.value('cg_bitmap')==0 and p.value('cg_error')==8
        p.type('7*8=');p.check();assert p.bus.video[0xd015]==1 and not p.value('cg_handle')
        p.key(27,exited=True);assert p.m.stats()==(175,251,32) and p.bus.video[0xd015]==1
        done('unsupported sprite owner receives text fallback without register theft or leaked surface',p)
        report['passed']=True
    except BaseException as error:report['error']=repr(error);raise
    finally:
        calc.Machine=original
        args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
