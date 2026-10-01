#!/usr/bin/env python3
"""Real Editor operations with independent complete VIC and VDC images."""
import argparse
import json
from pathlib import Path
import sys

import ci_native_editor_gui as gui
from ci_native_vdc_desktop import VDCBus
from native_vdc_mirror import bitmap, attributes


class Editor(gui.GraphicalEditor):
    vdc_expected=True

    def data(self,name,count):
        start=self.symbol(name)
        return bytes(self.ram[start:start+count])

    def output(self,value):
        screen=self.ram[0xd7]>>7
        if screen:assert not self.value('vd_phase'),'ROM text during owned VDC graphics'
        row,col=self.row[screen],self.col[screen]
        super().output(value)
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
        if self.value('ed_module_kind')==2:
            x,y=self.position;visible=self.value('pm_seen')
        else:
            from native_picker_fixture import Picker
            picker=Picker(self);x,y=picker.position;visible=picker.value('pm_seen')
        assert (self.number('eg_pointer_x',2),self.value('eg_pointer_y'))==(x,y)
        assert self.value('vd_pointer_visible')==self.value('eg_pointer_visible')==visible
        expected=bitmap(source,self.bus.size==64,x=x,y=y,pointer=bool(visible))
        actual=self.bus.bytes(self.value('vd_base')*256,16000)
        assert actual==expected,('complete VDC bitmap',[(i,a,b) for i,(a,b) in enumerate(zip(actual,expected)) if a!=b][:16])
        if self.bus.size==64:
            assert self.bus.bytes(0x8000,2000)==attributes(source),'complete VDC color cells'
            assert self.bus.video_ram[:0x4000]==self.bus.original[0][:0x4000]
            assert self.bus.video_ram[0x8800:]==self.bus.original[0][0x8800:]
        else:
            assert self.bus.video_ram[0x4000:]==self.bus.original[0][0x4000:]

    def check(self,*args,**kwargs):
        super().check(*args,**kwargs)
        self.mirror()

    def restored(self):
        super().restored()
        assert self.value('vd_phase')==self.value('vd_live')==self.value('bk_state')==0
        if self.bus.original is None:
            assert self.bus.data_writes==0,'refused provider never borrowed VDC RAM'
            return
        assert self.bus.video_ram==self.bus.original[0],'every VDC byte restored'
        for index in (1,6,8,9,10,12,13,14,15,18,19,20,21,22,23,24,25,26,27,28,32,33):
            assert self.bus.reg[index]==self.bus.original[1][index],index


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--size',type=int,choices=(16,64),required=True)
    parser.add_argument('--addressing',type=int,choices=(16,64),default=16)
    parser.add_argument('--reu-kib',type=int,choices=(128,512,16384))
    parser.add_argument('--case',choices=('keyboard','mouse','search','picker','cancel_write','cancel_verify','longfields','source'),required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    original_bus,original_app,argv=gui.PointerBus,gui.GraphicalEditor,sys.argv
    try:
        base=VDCBus
        options=dict(size=args.size,addressing=args.addressing)
        if args.reu_kib:
            from ci_native_reu_calc import CalculatorBus
            base=CalculatorBus;options['reu_kib']=args.reu_kib
        gui.PointerBus=type('EditorVDC',(base,),options)
        if args.case=='source':
            from ci_native_vdc_editor_recovery import RecoveryEditor
            gui.GraphicalEditor=RecoveryEditor
        else:gui.GraphicalEditor=Editor
        sys.argv=[argv[0],'--case',args.case,'--report',str(args.report)]
        gui.main()
        report=json.loads(args.report.read_text());report['vdc_kib']=args.size
        report['initial_addressing']=args.addressing
        report['reu_kib']=args.reu_kib
        report['complete_vic_and_vdc_canvases']=sum(case['checked'] for case in report['cases'])
        args.report.write_text(json.dumps(report,indent=2)+'\n')
    finally:
        gui.PointerBus,gui.GraphicalEditor,sys.argv=original_bus,original_app,argv


if __name__=='__main__':main()
