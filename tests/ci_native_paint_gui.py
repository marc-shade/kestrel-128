#!/usr/bin/env python3
"""Paint controls execute through the native ABI; compare both complete views."""
import argparse
import hashlib
import json
from pathlib import Path

from ci_native_paint_document import Paint,segment
from ci_native_paint_files import FilePaint,pattern
from ci_native_pointer import calc
from paint_scene import surface,console,RECTS,MESSAGES
from native_paint_format import encode


class GraphicalPaint(FilePaint):
    def number(self,name,size=2):
        at=self.symbol(name);return int.from_bytes(self.ram[at:at+size],'little')

    def check(self):
        assert not self.value('pa_picker_active')
        state=dict(x=self.number('pd_x'),y=self.value('pd_y'),pen=self.value('pd_pen'),
                   color=self.value('pd_color'),dirty=bool(self.value('pd_dirty')),focus=self.value('ui_selected'),
                   mode=self.value('pa_mode'),action=self.value('pa_action'),device=self.value('pf_device'),fmt=self.value('pf_format'),
                   name=bytes(self.ram[self.symbol('pf_name'):self.symbol('pf_name')+self.value('pf_length')]),
                   caret=self.value('pa_field_caret'))
        bitmap=bool(self.value('pa_bitmap'));message=self.value('pa_status')
        if bitmap:
            wanted=surface(self.document(),view_x=self.value('pa_view_x'),view_y=self.value('pa_view_y'),
                field_view=self.value('pa_field_view'),message=MESSAGES[message],**state)
            actual=bytes(self.ram[0xc000:0xe400])
            assert actual==wanted,('bitmap',state,message,[(i,a,b) for i,(a,b) in enumerate(zip(actual,wanted)) if a!=b][:24])
        for bank in ((1,) if bitmap else (0,1)):
            if bank and self.value('vd_phase'):continue
            wanted=console((40,80)[bank],bitmap=bitmap,message=message,view=self.ram[self.symbol('pa_field')+5+bank],**state)
            assert self.screens[bank]==wanted,('console',bank,state,message,
                [(i,a,b) for i,(a,b) in enumerate(zip(self.screens[bank],wanted)) if a!=b][:24])

    def click(self,index):
        x0,y0,x1,y1=RECTS[index]
        self.move((x0+x1)//2,(y0+y1)//2)
        self.frame(down=True);self.frame(down=False)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--case',choices=['all','keyboard','mouse','files','fallback'],default='all');args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    report=dict(passed=False,physical_hardware_io=False,cases=[],images={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (root/'target/native-desktop/paint.prg',root/'target/native/kestrel.prg')})
    def done(name,p):
        report['cases'].append(dict(name=name,keys=p.events,frames=p.frames,instructions=p.instructions))
        print('PASS:',name,flush=True)
    original=calc.Machine
    try:
        if args.case in ('all','keyboard'):
            p=GraphicalPaint();p.check();assert p.position==(8,32) and p.bus.video[0xd015]==3
            saved_keys=bytes(p.ram[p.symbol('pa_saved_keys'):p.symbol('pa_saved_keys')+256])
            assert p.ram[0x1000:0x1014]==bytes([1]*10)+bytes.fromhex('8589868a878b888c8384')
            p.key(32);p.check();assert p.document()[0]==128
            p.key(0x1d);p.key(ord('+'));p.key(32);p.check();assert p.document()[0]==192 and p.document()[8192]==0x20
            p.key(ord('U'));p.check();assert p.document()[0]==128 and p.document()[8192]==0x10
            p.key(ord('U'));p.key(ord('E'));p.key(32);p.check();assert p.document()[0]==128
            p.key(ord('C'));p.check();assert not any(p.document()[:8192])
            before=p.document(1);p.key(ord('C'));assert p.document(1)==before
            p.key(ord('U'));p.check();assert p.document()[0]==128
            p.key(27);p.check();assert p.value('ui_selected')==25
            p.key(13);p.check();assert p.value('pa_mode')==0 and p.value('pd_dirty')
            p.key(ord('O'));p.check();p.key(27);p.check()
            p.close();p.restored();assert bytes(p.ram[0x1000:0x1100])==saved_keys
            done('keyboard drawing, colors, eraser, undo/redo, repeated clear and dirty close/open protection',p)

            p=GraphicalPaint();p.install(pattern(37));p.key(ord('U'));p.check()
            p.set('pd_x',254,2);p.set('pd_y',143);p.key(0x1d);p.check()
            p.key(0x1d);p.check();assert p.value('pa_view_x')==1
            p.key(0x11);p.check();assert p.value('pa_view_y')==1
            p.set('pd_x',318,2);p.set('pd_y',198);p.key(0x1d);p.key(0x11);p.check()
            assert (p.value('pa_view_x'),p.value('pa_view_y'),p.position)==(8,7,(263,175))
            p.key(0x1d);p.key(0x11);p.check();p.key(32);p.check()
            p.key(0x13);p.check();assert p.position==(8,32) and p.value('pa_view_x')==p.value('pa_view_y')==0
            p.key(9);p.check();p.key(13);p.check()
            p.close();p.restored();done('full-image viewport and colors, 255/256 and bottom/right pan, saturated edges and Home',p)
        if args.case in ('all','mouse'):
            p=GraphicalPaint();p.frame();p.check();p.move(24,48);p.frame(down=True)
            wanted=bytearray(bytes(8192)+b'\x10'*1024);last=aim=(16,16);origin=p.position
            # A first jump of 6 pixels or more is held a sample, so the stroke
            # runs from the last drawn point to wherever the pointer lands.
            for dx,dy in [(12,7),(20,20),(20,-7),(-10,-20)]:
                aim=(aim[0]+dx,aim[1]+dy)
                p.frame(dx=dx,dy=dy,down=True);p.check()
                now=(p.position[0]-origin[0]+16,p.position[1]-origin[1]+16)
                assert now in (last,aim),(now,last,aim)
                for x,y in segment(last,now) if now!=last else ():wanted[y//8*320+x//8*8+y%8]|=128>>(x%8)
                last=now
            assert last==aim
            p.frame(down=False);assert p.document()==wanted
            p.click(2);p.check();assert p.document()==bytes(8192)+b'\x10'*1024
            p.click(2);p.check();assert p.document()==wanted
            p.click(7+5);p.check();assert p.value('pd_color')==5
            p.click(1);p.check();assert p.value('pd_pen')==0
            p.key(9);selection=p.value('ui_selected');p.frame();p.frame();assert p.value('ui_selected')==selection
            p.move(50,60);before=p.document();p.bus.pots=[255,255];p.frame(down=True)
            assert not p.value('pm_seen');p.bus.pots=[64,64];p.frame(down=True);p.frame(down=False)
            assert p.document()==before
            p.key(0x1d);p.bus.pots=[255,255];p.frame();assert p.bus.video[0xd015]==3
            p.close();p.restored();done('connected mouse stroke, one-stroke undo/redo, palette/tools, keyboard focus and disconnect/reconnect',p)
        if args.case in ('all','files'):
            p=GraphicalPaint(files={(9,b'OPENME',b'S'):encode(pattern(21))},device=9)
            p.key(32);p.key(ord('S'));p.check();p.type('PICTURE');p.check();p.key(13);p.check()
            assert p.value('pa_status')==1 and bytes(p.io.files[9,b'PICTURE',b'S'])==encode(p.document())
            p.key(ord('U'));p.check();assert p.value('pd_dirty')
            p.key(ord('U'));p.check();assert not p.value('pd_dirty')
            p.key(ord('S'));p.key(13);p.check();assert p.value('pa_status')==4
            p.key(ord('S'));p.key(21);p.type('CANCEL');p.key(27);p.check();assert (9,b'CANCEL',b'S') not in p.io.files
            p.key(ord('O'));assert p.value('pa_picker_active') and not p.value('pa_bitmap')
            p.key(13);p.check();assert p.document()==pattern(21) and p.value('pa_status')==2
            p.key(ord('U'));p.check();assert p.document()[0]==128
            p.key(ord('S'));p.key(21);p.type('OTHER');p.key(9);assert p.value('pa_picker_active')
            p.type('D10');p.key(13);p.type('S');p.check();assert p.value('pf_device')==10
            p.key(13);p.check();assert bytes(p.io.files[10,b'OTHER',b'S'])==encode(p.document())
            p.close();p.restored();done('Save As editing, complete verified bytes, collision/cancel, staged Open and cross-device picker',p)
        if args.case in ('all','fallback'):
            class Unsupported(original):
                def __init__(self):super().__init__();self.bus.video[0xd015]=1
            calc.Machine=Unsupported
            p=GraphicalPaint();assert not p.value('pa_bitmap') and p.value('pa_view_error')==8
            p.key(32);p.check();p.key(ord('S'));p.type('TEXTSAVE');p.check();p.key(13);p.check()
            assert bytes(p.io.files[8,b'TEXTSAVE',b'S'])==encode(p.document())
            p.close();assert p.bus.video[0xd015]==1 and p.m.stats()==(175,251,32)
            done('foreign sprite owner keeps both text consoles, document tools and verified file saving',p)
        report['passed']=True
    except BaseException as error:report['error']=repr(error);raise
    finally:calc.Machine=original;args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
