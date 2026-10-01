#!/usr/bin/env python3
"""Loaded Files graphics, complete copies and retained VDC module handoffs."""
import argparse
import json
from pathlib import Path

import ci_native_files_gui as gui
from ci_native_calc import Calculator
from ci_native_vdc_desktop import VDCBus
from native_vdc_mirror import bitmap, attributes


class Files(gui.GraphicalFiles):
    instruction_limit=40000000
    vdc_expected=True

    def output(self,value):
        screen=self.ram[0xd7]>>7
        if screen:
            assert not self.value('vd_phase'),'ROM text during owned VDC graphics'
        row,col=self.row[screen],self.col[screen]
        Calculator.output(self,value)
        if screen:
            chip=getattr(self.m.bus,'native',self.m.bus)
            if value==0x93:
                for i in range(2000):
                    chip.vwrite(i,32);chip.vwrite(0x800+i,15)
            elif 32<=value<128:
                chip.vwrite(row*80+col,self.screens[1][row*80+col])
                chip.vwrite(0x800+row*80+col,15)

    def mirror(self):
        assert self.value('vd_phase')==2 and self.value('vd_live')==1
        assert self.value('vd_fault')==self.value('vm_pending')==0
        source=bytes(self.ram[0xc000:0xe400])
        if self.value('fg_kind')==1:
            x,y=self.position;visible=self.value('pm_seen')
        else:
            from native_picker_fixture import Picker
            picker=Picker(self);x,y=picker.position;visible=picker.value('pm_seen')
        assert (self.number('fg_pointer_x',2),self.value('fg_pointer_y'))==(x,y)
        assert self.value('vd_pointer_visible')==self.value('fg_pointer_visible')==visible
        wanted=bitmap(source,self.bus.size==64,x=x,y=y,
                      pointer=bool(self.value('vd_pointer_visible')))
        assert self.bus.bytes(self.value('vd_base')*256,16000)==wanted,'complete VDC bitmap'
        if self.bus.size==64:
            assert self.bus.bytes(0x8000,2000)==attributes(source),'complete color cells'
            assert self.bus.video_ram[:0x4000]==self.bus.original[0][:0x4000]
            assert self.bus.video_ram[0x8800:]==self.bus.original[0][0x8800:]
        else:
            assert self.bus.video_ram[0x4000:]==self.bus.original[0][0x4000:]

    def canvas(self,*args,**kwargs):
        super().canvas(*args,**kwargs)
        if self.vdc_expected:self.mirror()
        else:assert not self.value('vd_phase')

    def restored(self):
        super().restored()
        assert self.value('vd_phase')==self.value('vd_live')==self.value('bk_state')==0
        if self.bus.original is not None:
            assert self.bus.video_ram==self.bus.original[0],'every VDC byte restored'
            for index in (1,6,8,9,10,12,13,14,15,18,19,20,21,22,23,24,25,26,27,28,32,33):
                assert self.bus.reg[index]==self.bus.original[1][index],index


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--size',type=int,choices=(16,64))
    args=parser.parse_args()
    original=gui.PointerBus
    report=dict(passed=False,physical_hardware_io=False,cases=[])
    try:
        for size in ((args.size,) if args.size else (16,64)):
            gui.PointerBus=type('FilesVDC',(VDCBus,),dict(size=size))
            raw=bytes(range(256))*3+b'\0END'
            p=Files({(9,b'SOURCE',b'S'):raw});p.browser();p.frame();p.browser()
            owner=p.data('bk_handle',4);snapshot=p.data('vd_handle',4)
            p.key(ord('I'));p.preview(b'SOURCE',raw[:128])
            p.key(13);p.preview(b'SOURCE',raw[128:256],offset=128)
            p.key(27);p.browser();p.key(ord('C'));p.copy(b'SOURCE',b'SOURCE')
            p.rename('COPY');p.copy(b'SOURCE',b'COPY')
            p.key(13);p.copy(b'SOURCE',b'COPY',copied=len(raw),verified=len(raw),status=1)
            assert bytes(p.io.files[9,b'COPY',b'S'])==raw
            preferences=p.preferences();p.key(0x88)
            assert p.value('fg_kind')==2 and p.value('fc_picker_active')
            p.mirror();p.key(27);p.copy(b'SOURCE',b'COPY',copied=len(raw),verified=len(raw),status=1)
            assert p.preferences()==preferences
            assert p.data('bk_handle',4)==owner and p.data('vd_handle',4)==snapshot
            p.key(27);p.browser();p.key(27,exited=True);p.restored()
            report['cases'].append(dict(name=f'{size} KiB list, viewer, copy, picker and exact restore',
                passed=True,instructions=p.instructions,keys=p.events,views=p.checked))
            args.report.write_text(json.dumps(report,indent=2)+'\n')
            print('PASS:',report['cases'][-1]['name'],flush=True)
        report['passed']=True
    finally:
        gui.PointerBus=original
        args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
