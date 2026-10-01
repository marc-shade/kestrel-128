#!/usr/bin/env python3
"""Paint drawing and dialogs on both VDC sizes, preserving document and screen."""
import argparse
import json
from pathlib import Path
from ci_native_paint_gui import GraphicalPaint
from ci_native_calc import Calculator
from ci_native_paint_files import pattern
from ci_native_vdc_controls import Panel as UltimatePanel, heap, VDCBus


class Paint(GraphicalPaint):
    instruction_limit=40000000
    def output(self,value):
        screen=self.ram[0xd7]>>7
        if screen:assert not self.value('vd_phase'),'ROM text during owned VDC graphics'
        row,col=self.row[screen],self.col[screen]
        Calculator.output(self,value)
        if screen:
            chip=getattr(self.m.bus,'native',self.m.bus)
            if value==0x93:
                for i in range(2000):chip.vwrite(i,32);chip.vwrite(0x800+i,15)
            elif 32<=value<128:
                chip.vwrite(row*80+col,self.screens[1][row*80+col]);chip.vwrite(0x800+row*80+col,15)

    mirror=UltimatePanel.mirror

    def check(self):
        super().check()
        self.mirror()

    def restored(self):
        super().restored()
        assert self.value('vd_phase')==self.value('vd_live')==self.value('bk_state')==0
        if self.bus.original is not None:
            assert self.bus.video_ram==self.bus.original[0]
            for index in (1,6,8,9,10,12,13,14,15,18,19,20,21,22,23,24,25,26,27,28,32,33):
                assert self.bus.reg[index]==self.bus.original[1][index],index


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--size',choices=('both','16','64'),default='both')
    args=parser.parse_args();original=heap.Bus
    report=dict(passed=False,physical_hardware_io=False,cases=[])
    try:
        for size in ([16,64] if args.size=='both' else [int(args.size)]):
            heap.Bus=type('PaintVDC',(VDCBus,),dict(size=size))
            p=Paint();p.check()
            assert p.value('vd_pointer_visible')==1 and p.position==(8,32)
            original_document=p.document();token=bytes(p.ram[p.symbol('bk_handle'):p.symbol('bk_handle')+4])
            p.key(32);p.check();assert p.document()[0]==128
            before=p.bus.data_writes
            p.key(0x1d);p.check();assert p.position==(9,32)
            pointer_writes=p.bus.data_writes-before
            p.key(ord('+'));p.key(32);p.check()
            assert p.document()[0]==192 and p.document()[8192]==0x20
            p.key(ord('U'));p.check();assert p.document()[0]==128
            p.key(27);p.check();assert p.value('pa_mode')==1 and p.value('ui_selected')==25
            p.key(13);p.check();assert p.value('pa_mode')==0 and p.value('pd_dirty')
            p.key(ord('S'));p.check();p.key(ord('X'));p.check()
            p.key(27);p.check();assert bytes(p.ram[p.symbol('bk_handle'):p.symbol('bk_handle')+4])==token
            p.install(pattern(37));p.key(ord('R'));p.check()
            p.set('pd_x',254,2);p.set('pd_y',143);p.key(0x1d);p.key(0x1d);p.check()
            assert p.value('pa_view_x')==1
            p.key(0x11);p.check();assert p.value('pa_view_y')==1
            p.set('pd_x',318,2);p.set('pd_y',198);p.key(0x1d);p.key(0x11);p.check()
            assert (p.value('pa_view_x'),p.value('pa_view_y'))==(8,7)
            p.key(0x13);p.check();assert (p.value('pa_view_x'),p.value('pa_view_y'))==(0,0)
            p.key(ord('C'));p.key(ord('P'));p.frame();p.move(20,40)
            p.frame(down=True);p.frame(dx=10);p.frame(down=False);p.check()
            drawn=bytearray(bytes(8192)+b'\x10'*1024)
            for x in range(12,23):
                drawn[320+x//8*8]|=128>>(x&7);drawn[8192+40+x//8]=p.value('pd_color')*16
            assert p.document()==drawn,'complete connected mouse stroke'
            p.key(ord('U'));p.check();assert p.document()==bytes(8192)+b'\x10'*1024
            p.close();p.restored()
            assert p.m.stats()==(175,251,32)
            report['cases'].append(dict(name=f'{size} KiB drawing, brush, panning, mouse stroke, undo and dialogs',
                instructions=p.instructions,keys=p.events,pointer_with_status_writes=pointer_writes))
            print('PASS:',report['cases'][-1]['name'],flush=True)
        report['passed']=True
    finally:
        heap.Bus=original;args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
