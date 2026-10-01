#!/usr/bin/env python3
"""Retained Claude terminal and graphical controls on both physical VDC sizes."""
import argparse
import json
from pathlib import Path

from ci_native_claude_gui import GraphicalClient,heap
from ci_native_vdc_desktop import VDCBus
from native_vdc_mirror import bitmap,attributes


class TerminalVDC(VDCBus):
    right=False

    def __getitem__(self,address):
        value=super().__getitem__(address)
        if not self.config&1 and address==0xdc01 and self.right:value&=254
        return value

    def __setitem__(self,address,value):
        # Terminal scroll permits either direction between disjoint rows.
        if not self.config&1 and address==0xd601 and self.selected==30 and self.reg[24]&128:
            assert self.ready
            self.ready,self.busy=False,2
            if self.original is None:self.original=bytes(self.video_ram),bytes(self.reg)
            self.reg[30]=value
            dest=self.reg[18]*256+self.reg[19];source=self.reg[32]*256+self.reg[33]
            count=value or 256
            assert source+count<=dest or dest+count<=source
            data=self.bytes(source,count)
            for i,byte in enumerate(data):self.vwrite(dest+i,byte)
            self.reg[32],self.reg[33]=(source+count)>>8,(source+count)&255
            self.reg[31]=data[-1];self.block_copies+=1
            self.advance(dest+count);self.busy=count*2
            if self.stall_register==(self.selected,value):self.stall=True
            return
        super().__setitem__(address,value)


class Claude(GraphicalClient):
    instruction_limit=20000000

    def __init__(self,**options):
        options.setdefault('vdc_component',True)
        super().__init__(**options)
        self.vdc_checked=0

    def check(self):
        super().check()
        if self.value('cg_vdc_owned'):
            assert self.value('vd_phase')==2 and self.value('vd_live')==1
            assert self.value('vd_fault')==self.value('cg_recovery')==self.value('vm_pending')==0
            source=bytes(self.ram[0xc000:0xe400]);x,y=self.position
            expected=bitmap(source,self.bus.size==64,x=x,y=y,pointer=bool(self.value('pm_seen')))
            actual=self.bus.bytes(self.value('vd_base')*256,16000)
            assert actual==expected,('VDC bitmap',[(i,a,b) for i,(a,b) in enumerate(zip(actual,expected)) if a!=b][:12])
            if self.bus.size==64:assert self.bus.bytes(0x8000,2000)==attributes(source)
            self.vdc_checked+=1
        else:
            assert self.value('vd_phase')==self.value('bk_state')==0
            chars,attrs=self.terminal()
            assert self.bus.bytes(0,2000)==chars and self.bus.bytes(0x800,2000)==attrs
            assert self.bus.bytes(0x3000,4096)==bytes(self.ram[0x5000:0x6000])

    def right_click(self):
        self.frame()
        before=self.events;menu=self.value('cg_menu')
        self.bus.right=True;self.frame();assert self.value('cg_menu')==menu^1
        self.frame();assert self.value('cg_menu')==menu^1
        self.bus.right=False;self.frame()
        assert self.events==before and self.value('cg_menu')==menu^1


def run(size,addressing,case):
    heap.Bus=type('ConfiguredTerminalVDC',(TerminalVDC,),dict(size=size,addressing=addressing))
    rows=[]
    def done(name,c,**extra):
        row=dict(name=name,passed=True,keys=c.events,frames=c.frames,
                 instructions=c.instructions,vdc_frames=c.vdc_checked,**extra)
        rows.append(row);print('PASS:',name,flush=True)

    if case=='core':
        c=Claude();c.check();assert c.value('cg_vdc_owned')
        c.frame();c.click(4);c.check();c.click(3);c.check()
        c.click(0);c.check();assert not c.value('cg_vdc_owned') and c.value('cg_live')==1
        chars=bytearray(b' '*2000);attrs=bytearray([0x8e]*2000)
        stream=bytearray([1,14])
        for row in range(25):
            data=bytes((row*80+col)*29&255 for col in range(80));attr=(row*13)&0x6f
            chars[row*80:(row+1)*80]=data;attrs[row*80:(row+1)*80]=bytes([attr|128])*80
            stream+=bytes([2,row,0,attr,80])+data
        c.feed(stream+b'\5');assert c.terminal()==(chars,attrs);c.check()
        c.right_click();c.check();assert c.value('cg_menu')==1 and c.value('cg_vdc_owned')
        c.click(5);c.check();assert c.value('cg_view')==1
        c.click(4);c.click(5);c.check();assert c.value('cg_view')==2 and c.value('cg_top')==9
        glyph=bytes([1,2,4,8,16,32,64,128])
        c.feed(bytes([10,255])+glyph+bytes([3,24,77,0x6f,255,255,4,24,79,5]))
        chars[1997:]=bytes([255])*3;attrs[1997:]=bytes([0xef])*3
        assert c.terminal()==(chars,attrs);c.check()
        # A view change may happen between a RUN header and its last byte.
        c.feed(bytes([2,17,39,0x2f,5,1,2]))
        c.click(6);c.check();assert not c.value('cg_vdc_owned') and not c.value('cg_menu')
        c.feed(bytes([3,4,5,5]));chars[1399:1404]=bytes([1,2,3,4,5]);attrs[1399:1404]=bytes([0xaf])*5
        assert c.terminal()==(chars,attrs);c.check()
        c.key(255);c.check();assert c.value('cg_vdc_owned')
        c.right_click();c.check();assert not c.value('cg_vdc_owned')
        c.key(27);assert c.chip.sent[-1]==27
        c.key(255);c.check();c.click(2);c.check();assert c.value('_closeOutcome')==1
        c.feed(bytes([9,0x5a]),exited=True);c.restored()
        assert not c.value('_rxDropped') and not c.value('_rxOverruns')
        done('mouse/keyboard controls, both terminal halves, live glyphs and split RUN across the graphical-to-text handoff',c)
    elif case=='fault':
        c=Claude();c.check();c.key(13);c.check();c.key(255);c.check()
        c.bus.stall=True;c.key(9)
        assert c.value('cg_recovery') and c.value('cg_vdc_owned')
        retained=c.m.stats();keys=bytes(c.ram[0x1000:0x1100]);vector=bytes(c.ram[0x318:0x31a])
        before=bytes(c.chip.sent);c.key(ord('X'));assert bytes(c.chip.sent)==before
        c.key(27);assert c.m.stats()==retained and c.value('cg_recovery')
        c.feed(bytes([3,24,79,15,1,65,5]));assert c.terminal()[0][-1:]==b'A'
        assert bytes(c.ram[0x1000:0x1100])==keys and bytes(c.ram[0x318:0x31a])==vector
        c.bus.stall=False;c.key(27);c.check();assert not c.value('cg_vdc_owned')
        c.close();c.restored();done('stalled graphics retain terminal input and ownership; Escape restores the complete current terminal',c)
    elif case=='stream':
        c=Claude();c.key(13);c.check()
        data=bytearray([1,14])
        for row in range(25):
            data+=bytes([7,row,row&15,40])+bytes([row+32])*40
            data+=bytes([2,row,0,14,80])+bytes([row+65])*80
        data+=b'\5'
        normal_step=c.cpu.step
        schedule=dict(at=0,credits=192,tx=len(c.chip.sent),due=c.cpu.processorCycles+260,
                      nested=False,peak=0,transfers=0,component=0,maps=set())
        def paced_step():
            normal_step()
            if schedule['nested']:return
            while len(c.chip.sent)-schedule['tx']>=2:
                pair=c.chip.sent[schedule['tx']:schedule['tx']+2];schedule['tx']+=2
                assert pair==b'\0\3',pair
                schedule['credits']+=64
            if not schedule['at']:
                if c.chip.config!=0x4e:return
            elif c.cpu.processorCycles<schedule['due']:return
            schedule['due']=c.cpu.processorCycles+260
            if not schedule['credits'] or schedule['at']==len(data):return
            if c.ram[0x3d11]:schedule['transfers']+=1
            if c.chip.config==0x4e:schedule['component']+=1
            schedule['maps'].add(c.chip.config)
            schedule['nested']=True
            try:c.nmi(data[schedule['at']])
            finally:schedule['nested']=False
            schedule['at']+=1;schedule['credits']-=1
            schedule['peak']=max(schedule['peak'],(c.value('_rxHead')-c.value('_rxTail'))&255)
        c.cpu.step=paced_step
        try:
            c.key(255)                 # bytes first arrive inside the real VDSVC
            for _ in range(12000):
                c.poll()
                if schedule['at']==len(data) and c.value('_rxHead')==c.value('_rxTail'):break
            else:raise AssertionError('paced stream did not drain')
        finally:c.cpu.step=normal_step
        c.check();assert c.value('cg_vdc_owned')
        assert c.terminal()[0]==b''.join(bytes([row+65])*80 for row in range(25))
        assert bytes(c.ram[0x400:0x7e8])==b''.join(bytes([row+32])*40 for row in range(25))
        assert schedule['component'] and schedule['transfers'] and 0x4e in schedule['maps']
        assert schedule['peak']<=192 and not c.value('_rxDropped') and not c.value('_rxOverruns')
        c.key(27);c.check();c.close();c.restored()
        done('192-byte host window survives 38400-baud NMI arrivals inside the bank-1 display service',c,
             bytes_received=len(data),peak_ring=schedule['peak'],component_interrupts=schedule['component'],
             transfer_interrupts=schedule['transfers'],interrupted_maps=sorted(schedule['maps']))
    elif case=='teardown':
        c=Claude();c.key(13);c.key(255);c.check()
        retained=c.m.stats();c.bus.stall=True;c.key(0x8c)
        c.feed(bytes([9,0x5a]))
        assert c.value('cg_retiring') and c.value('cg_recovery') and c.value('cg_vdc_owned')
        assert not c.value('serialOwned') and c.m.stats()==retained
        assert bytes(c.ram[0x318:0x31a])==c.borrowed['vector']
        assert c.value('pm_active') and c.value('cg_keys_owned') and c.value('_tm_live')
        c.key(27);assert c.m.stats()==retained and c.value('cg_recovery')
        c.bus.stall=False;c.key(27,exited=True);c.restored()
        done('acknowledged close retains graphics and model until a stalled VDC can be restored',c)

        c=Claude();c.key(13);c.check()
        # The original font restore is required even when no overlay is open.
        c.bus.stall_register=(18,0x30)
        c.feed(bytes([9,0x5a]));assert c.bus.stall and c.value('cg_retiring')
        assert c.value('videoFault')==8 and c.value('_tm_live') and c.value('pm_active')
        retained=c.m.stats();c.key(27);assert c.m.stats()==retained
        c.bus.stall_register=None;c.bus.stall=False;c.key(0x8c,exited=True);c.restored()
        done('original-font restore timeout retains ownership and supports a later Desktop retry',c)
    return rows


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--size',type=int,choices=(16,64),required=True)
    parser.add_argument('--addressing',type=int,choices=(16,64),default=16)
    parser.add_argument('--case',choices=('core','fault','stream','teardown'),default='core')
    parser.add_argument('--report',type=Path,required=True);args=parser.parse_args()
    result=dict(passed=False,physical_hardware_io=False,vdc_kib=args.size,addressing=args.addressing)
    try:result['cases']=run(args.size,args.addressing,args.case);result['passed']=True
    except BaseException as error:result['error']=repr(error);raise
    finally:args.report.write_text(json.dumps(result,indent=2)+'\n')
