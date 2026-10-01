#!/usr/bin/env python3
"""Exercise the disk-loaded native calculator, history and exit lifecycle."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from py65.devices.mpu6502 import MPU
from ci_native_heap import Machine,ROOT
from ci_native_apps import RUN
from ci_native_files import StreamIEC
sys.path.insert(0,str(ROOT))
from hwlib import lst_symbol
from native_clipboard_check import released_stats


class Calculator:
    instruction_limit=2000000
    allow_busy_poll=False
    expected_exit_code=0

    def __init__(self,image_name='calc',files=None,loader_name=b'CHECK',device=8,fmt=0,
                 *,ultimate_files=None,source_path=None,source_context=1,image_prefix='native',vdc_component=True):
        self._symbol_cache={}
        self.m=Machine();self.ram=self.m.ram
        self.image_name=image_name;self.image_prefix=image_prefix
        self.image=(ROOT/'target'/self.image_prefix/f'{image_name}.prg').read_bytes()
        self.io=StreamIEC(self.m,{**(files or {}),(8,loader_name,b'P'):self.image})
        if image_name=='editor':
            self.io.files[8,b'EDPICK.PRG',b'P']=(ROOT/'target'/self.image_prefix/'edpick.prg').read_bytes()
            self.io.files[8,b'EDFIND.PRG',b'P']=(ROOT/'target'/self.image_prefix/'edfind.prg').read_bytes()
            if image_prefix=='native-desktop':self.io.files[8,b'EDCLIP.PRG',b'P']=(ROOT/'target'/self.image_prefix/'edclip.prg').read_bytes()
        if image_name=='files':
            for name in ('fspick','fsview','fsopen'):
                self.io.files[8,name.upper().encode()+b'.PRG',b'P']=(ROOT/'target'/self.image_prefix/f'{name}.prg').read_bytes()
        if image_name=='sheet':
            for name in ('shfont','shcalc','shclip'):
                self.io.files[8,name.upper().encode()+b'.PRG',b'P']=(ROOT/'target'/self.image_prefix/f'{name}.prg').read_bytes()
        provider = None
        if image_prefix=='native-desktop' and image_name in ('calc','desktop','controls','paint','files','editor','claude','sheet','gemdesk') and vdc_component is not False:
            provider = ((ROOT/'target/native-desktop/vdsvc.prg').read_bytes()
                        if vdc_component is True else bytes(vdc_component))
            self.io.files[8,b'VDSVC.PRG',b'P']=provider
        self.io.formats[device]=fmt
        self.ram[0x3d21:0x3d23]=bytes([8,len(loader_name)])
        self.ram[0x3d40:0x3d40+len(loader_name)]=loader_name
        self.ram[0x3d29:0x3d2b]=bytes([device,fmt])
        # A separate data device does not change the boot app's D64 geometry.
        self.ram[0x3d2c]=fmt if device==8 else 0;self.ram[0x3d2d]=8
        self.ram[0x3de4]=fmt if device==8 else 0
        if ultimate_files is not None or source_path is not None:
            from ci_native_ultimate import UltimateBus,DOSFiles
            data=dict(ultimate_files or {})
            if source_path is not None:data[source_path]=self.image
            if source_path is not None and image_name=='editor':
                data[source_path.rsplit(b'/',1)[0]+b'/EDPICK.PRG']=(ROOT/'target'/self.image_prefix/'edpick.prg').read_bytes()
                data[source_path.rsplit(b'/',1)[0]+b'/EDFIND.PRG']=(ROOT/'target'/self.image_prefix/'edfind.prg').read_bytes()
                if image_prefix=='native-desktop':data[source_path.rsplit(b'/',1)[0]+b'/EDCLIP.PRG']=(ROOT/'target'/self.image_prefix/'edclip.prg').read_bytes()
            if source_path is not None and image_name=='files':
                for name in ('fspick','fsview','fsopen'):
                    data[source_path.rsplit(b'/',1)[0]+b'/'+name.upper().encode()+b'.PRG']=(ROOT/'target'/self.image_prefix/f'{name}.prg').read_bytes()
            if source_path is not None and provider is not None:
                prefix = source_path.rsplit(b'/',1)[0]+b'/' if b'/' in source_path else b''
                data[prefix+b'VDSVC.PRG']=provider
            if source_path is not None and image_name=='sheet':
                for name in ('shfont','shcalc','shclip'):
                    data[source_path.rsplit(b'/',1)[0]+b'/'+name.upper().encode()+b'.PRG']=(ROOT/'target'/self.image_prefix/f'{name}.prg').read_bytes()
            self.ultimate=DOSFiles(data);self.ultimate.fragment=103
            self.ultimate.direct_write_corruption=True
            self.m.bus=UltimateBus(self.m.bus,self.ultimate)
            if source_path is not None:
                self.ram[0x3d21]=source_context;self.ram[0x3d22]=len(source_path);self.ram[0x3d2c]=3
                self.ram[0x4e00:0x4e00+len(source_path)]=source_path
        self.cpu=MPU(memory=self.m.bus,pc=RUN);self.cpu.sp=0xe0;self.cpu.p=0x20
        self.cpu.stPushWord(0xaff)
        self.screens=[bytearray(b' '*1000),bytearray(b' '*2000)]
        self.reverse=[False,False]
        self.row=[0,0];self.col=[0,0];self.keys=[];self.events=0;self.instructions=0
        self.observation_target=None;self.observation_done=False
        self.loop()
        assert self.ram[0x3d20]==32 and self.ram[0x3d23]==2
        assert not self.io.handles

    def symbol(self,name):
        if name not in self._symbol_cache:
            self._symbol_cache[name]=lst_symbol(self.image_prefix+'/'+self.image_name,name)
        return self._symbol_cache[name]
    def value(self,name):return self.ram[self.symbol(name)]
    def display(self):return bytes(self.ram[self.symbol('dispbuf'):self.symbol('dispbuf')+8]).split(b'\0')[0].decode()

    def output(self,value):
        bank=self.ram[0xd7]>>7;cols=40 if bank==0 else 80
        if value in (0x12,0x92):self.reverse[bank]=value==0x12;return
        if value==0x93:
            self.reverse[bank]=False
            self.screens[bank][:]=b' '*(cols*25);self.row[bank]=self.col[bank]=0
        elif value==13:self.row[bank]+=1;self.col[bank]=0
        else:
            assert 32<=value<128,value
            assert self.row[bank]<25,'unexpected calculator screen scroll'
            code=value-64 if 64<=value<96 else value-32 if value>=96 else value
            self.screens[bank][self.row[bank]*cols+self.col[bank]]=code|(128 if self.reverse[bank] else 0)
            self.col[bank]+=1
            if self.col[bank]==cols:self.col[bank]=0;self.row[bank]+=1

    def loop(self,exited=False):
        cpu=self.cpu
        for steps in range(self.instruction_limit):
            if self.observation_target is not None and not self.observation_done:
                consumed=int.from_bytes(self.ram[0x3d13:0x3d15],'little')
                if consumed==self.observation_target and self.ram[0x3d12]==1:
                    ready_pc=self.symbol('b_get_key') if self.image_name in ('browse','files') else self.symbol('cloop')+5
                    if self.image_name=='editor':ready_pc=self.symbol('ed_get_key')
                    if self.image_name=='files' and self.value('fc_active'):
                        ready_pc=self.symbol('fc_picker_get_key') if self.value('fc_picker_active') else self.symbol('fc_get_key')
                    if self.image_name=='editor' and self.value('fd_active'):
                        ready_pc=self.symbol('b_get_key')
                    assert cpu.pc==ready_pc,('ready published before input loop',hex(cpu.pc),consumed)
                    self.observation_done=True
            if cpu.pc==0xb00 and cpu.sp==0xe0:
                assert exited,'calculator exited unexpectedly'
                assert self.ram[0x3d20]==0 and self.ram[0x3d23:0x3d25]==bytes([0,self.expected_exit_code])
                assert self.m.stats()==released_stats(self.m) and not self.io.handles
                self.instructions+=steps;return
            if cpu.pc==0xffe4 and not self.keys:
                if self.ram[0x3d12]==1:
                    assert not exited
                    self.instructions+=steps;return
                assert self.allow_busy_poll,'GETIN while application readiness is clear'
            if self.io.stub(cpu):continue
            if cpu.pc in (0xffe4,0xffd2,0xff5f,0xfff0):
                if cpu.pc==0xffe4:
                    cpu.a=self.keys.pop(0) if self.keys else 0
                    cpu.FlagsNZ(cpu.a)
                elif cpu.pc==0xffd2:self.output(cpu.a)
                elif cpu.pc==0xff5f:self.ram[0xd7]^=0x80
                else:
                    bank=self.ram[0xd7]>>7;columns=(40,80)[bank]
                    if cpu.p&cpu.CARRY:cpu.x,cpu.y=self.row[bank],self.col[bank]
                    else:
                        assert cpu.x<25 and cpu.y<columns,('PLOT outside screen',cpu.x,cpu.y)
                        self.row[bank],self.col[bank]=cpu.x,cpu.y
                cpu.pc=(cpu.stPopWord()+1)&65535
            else:cpu.step()
        raise AssertionError(f'calculator did not reach input, PC={cpu.pc:04x}')

    def key(self,key,exited=False):
        self.observation_target=self.events+1;self.observation_done=False
        self.keys.append(key);self.loop(exited)
        if not exited:assert self.observation_done
        self.events+=1
        assert int.from_bytes(self.ram[0x3d13:0x3d15],'little')==self.events

    def type(self,text):
        for key in text.encode():self.key(key)

    def history(self):
        handle=self.ram[self.symbol('history_handle')]
        record=0x3c00+(handle-1)*8
        assert self.ram[record]==32 and self.ram[record+1]==1
        start=self.ram[record+2]*256
        head,count=self.value('history_head'),self.value('history_count')
        return [bytes(self.m.bus.ram[1][start+((head-1-i)&31)*16:start+((head-1-i)&31)*16+16]).decode().rstrip()
                for i in range(count)]

    def check_screens(self,save_prompt=None,save_status=None):
        from native_capture import calculator_screen
        history=self.history();view=self.value('history_view')
        for bank,cols in ((0,40),(1,80)):
            want=calculator_screen(cols,self.display(),history,view,save_prompt,save_status,usb=self.ram[0x3d2c]==3,
                save_caret=self.value('save_cursor'),save_view=self.ram[self.symbol('save_views')+bank])
            assert self.screens[bank]==want,(bank,self.display(),history)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path);args=parser.parse_args()
    report=dict(passed=False,calc_sha256=hashlib.sha256((ROOT/'target/native/calc.prg').read_bytes()).hexdigest(),
                kernel_sha256=hashlib.sha256((ROOT/'target/native/kestrel.prg').read_bytes()).hexdigest())
    try:
        calc=Calculator();calc.check_screens()
        examples=[('12+30=','42'),('65535/255=','257'),('65535/32768=','1'),('65535*1=','65535'),
                  ('300*300=','OVF'),('65535+1=','OVF'),('0-1=','OVF'),('37/0=','DIV/0'),
                  ('9=+1=','10'),('5+6*7=','77'),('12345\x14=','1234')]
        for text,want in examples:
            calc.type('C'+text);assert calc.display()==want,(text,calc.display(),want)
            calc.check_screens()
        calc.type('C1/0=');calc.key(27,exited=True)
        report['arithmetic_cases']=len(examples)
        report['arithmetic_events']=calc.events
        calc=Calculator()
        for number in range(1,41):calc.type('C'+str(number)+'=')
        assert calc.history()==list(map(str,range(40,8,-1)))
        assert calc.value('history_head')==8 and calc.value('history_count')==32
        calc.check_screens()
        for view in (8,16,24,24):
            calc.type('N');assert calc.value('history_view')==view;calc.check_screens()
        for view in (16,8,0,0):
            calc.type('B');assert calc.value('history_view')==view;calc.check_screens()
        calc.key(27,exited=True)
        report.update(history_results=40,retained=32,history_events=calc.events,
                      history_instructions=calc.instructions,complete_screens=True,exit_releases_all=True)
        calc=Calculator();calc.type('S');calc.check_screens(save_status='NO RESULTS TO SAVE')
        calc.type('12+30=C65535+1=')
        calc.type('SHISTORYX');calc.key(20);calc.check_screens(save_prompt='HISTORY')
        calc.key(27);assert not calc.io.handles and (8,b'HISTORY',b'S') not in calc.io.files
        calc.type('SHISTORY');calc.key(13)
        assert bytes(calc.io.files[8,b'HISTORY',b'S'])==b'42\rOVF\r'
        assert not calc.io.handles and calc.value('save_status')==1
        calc.check_screens(save_status='HISTORY SAVED AND VERIFIED')
        calc.type('SHISTORY');calc.key(13)
        calc.check_screens(save_status='FILE EXISTS - CHOOSE ANOTHER NAME')
        assert bytes(calc.io.files[8,b'HISTORY',b'S'])==b'42\rOVF\r'
        calc.type('SCANCEL');calc.key(27);calc.check_screens()
        calc.io.fail_flush=True;calc.type('SPARTIAL');calc.key(13)
        calc.check_screens(save_status='DISK ERROR; FILE MAY BE PARTIAL')
        assert not calc.io.handles and len(calc.io.files[8,b'PARTIAL',b'S'])<7
        calc.io.fail_flush=False;calc.key(27,exited=True)
        # The ring's maximum export has 32 five-digit results and delimiters.
        calc=Calculator()
        for _ in range(40):calc.type('C65535=')
        calc.type('SMAXIMUM');calc.key(13)
        assert bytes(calc.io.files[8,b'MAXIMUM',b'S'])==b'65535\r'*32
        calc.check_screens(save_status='HISTORY SAVED AND VERIFIED');calc.key(27,exited=True)
        report.update(passed=True,saved_history_verified=True,saved_maximum_bytes=192,existing_name_preserved=True,
                      save_cancel_and_fault=True)
        for fmt in (1,2):
            calc=Calculator(fmt=fmt);calc.type('12+30=SSHARED');calc.key(13)
            assert calc.ram[0x3d96]==fmt and bytes(calc.io.files[8,b'SHARED',b'S'])==b'42\r'
            calc.check_screens(save_status='HISTORY SAVED AND VERIFIED');calc.key(27,exited=True)
        report['source_disk_formats']=[0,1,2]
        print('PASS: native calculator arithmetic/errors, 32-result banked history, paging, both screens and exit cleanup',flush=True)
    except BaseException as error:report['error']=str(error);raise
    finally:
        if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
