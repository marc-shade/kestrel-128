#!/usr/bin/env python3
"""Execute native RTC edits against independent calendar and cartridge state."""
import argparse
from collections import deque
from datetime import datetime, timedelta
import json
from pathlib import Path
import re

from py65.devices.mpu6502 import MPU
import ci_native_drives as drives
from ci_native_controls_gui import GraphicalPanel, heap
from ci_native_vdc_controls import Panel as VDCPanel, VDCBus
from ci_native_reu_calc import CalculatorBus
from uci_bus import UCIBus


class ClockDOS(drives.DriveDOS):
    def __init__(self):
        super().__init__()
        self.clock_writes=[]
        self.advance=0
        self.clock_ignored=False
        self.bad_readback=None
        self.write_status=b'00,OK'

    def __setitem__(self,address,value):
        if address==0xdf1c and value==1:
            command=bytes(self.command)
            if command[:2]==b'\x01\x27' and command not in self.faults:
                assert len(command)==8,command
                year,month,day,hour,minute,second=command[2:]
                assert 80<=year<=179,command
                wanted=datetime(year+1900,month,day,hour,minute,second)
                self.clock_writes.append(command)
                observed=wanted+timedelta(seconds=self.advance)
                if not self.clock_ignored:
                    self.time=observed.strftime('%Y/%m/%d %H:%M:%S').encode()
                if self.bad_readback is not None:self.time=self.bad_readback
                reply=wanted.strftime('%a %Y/%m/%d %H:%M:%S').upper().encode()
                self.packets=deque([(reply,self.write_status)])
                return UCIBus.__setitem__(self,address,value)
        return super().__setitem__(address,value)


def field(panel,text,caret=0):
    data=text.encode();assert len(data)<=19
    at=panel.symbol('ut_edit');panel.ram[at:at+19]=data.ljust(19,b' ')
    at=panel.symbol('ut_field');panel.ram[at:at+2]=bytes([len(data),caret])


def invoke(panel,name):
    stack=bytes(panel.ram[0x100:0x200])
    cpu=MPU(memory=panel.m.bus,pc=panel.symbol(name));cpu.sp=0xe0;cpu.p=0x20
    cpu.stPushWord(0xaff)
    try:
        for steps in range(20000):
            if cpu.pc==0xb00 and cpu.sp==0xe0:return cpu
            cpu.step()
        raise AssertionError((name,hex(cpu.pc)))
    finally:panel.ram[0x100:0x200]=stack


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--case',choices=('calendar','input','protocol','vdc16','vdc64','fault'),required=True)
    args=parser.parse_args()
    report=dict(passed=False,physical_hardware_io=False,cases=[])
    original_bus,original_dos=heap.Bus,drives.DriveDOS
    drives.DriveDOS=ClockDOS

    def done(name,p,**extra):
        report['cases'].append(dict(name=name,passed=True,instructions=p.instructions,
            keys=p.events,frames=p.frames,views=p.checked,
            commands=[c.hex() for c in p.device.commands],**extra))
        args.report.write_text(json.dumps(report,indent=2)+'\n')
        print('PASS:',name,flush=True)

    def open_clock(p):
        p.key(ord('T'));p.key(ord('S'))
        assert p.value('ug_mode')==2 and p.value('ui_selected')==17

    def submit(p,text):
        field(p,text);p.key(13)
        assert p.value('ug_mode')==2 and p.value('ui_selected')==10
        p.check();p.key(13)
        assert p.value('ug_mode')==0

    try:
        if args.case=='calendar':
            p=GraphicalPanel();open_clock(p)
            values=['','2000/01/01 00:00:0','2000-01-01 00:00:00',
                    '2000/01/01T00:00:00','2000/01/01 24:00:00',
                    '2000/01/01 00:60:00','2000/01/01 00:00:60',
                    '1979/12/31 23:59:59','2080/01/01 00:00:00',
                    '1900/02/29 00:00:00','2000/02/29 00:00:00',
                    '2079/12/31 23:59:59','1980/01/01 00:00:00',
                    '0000/01/01 00:00:00','9999/12/31 23:59:59']
            values += [f'{year:04d}/{month:02d}/{day:02d} 23:59:59'
                       for year in (1980,1999,2000,2004,2026,2079)
                       for month in range(14) for day in (0,1,28,29,30,31,32)]
            base='2026/09/14 12:34:56'
            values += [base[:i]+char+base[i+1:] for i in range(19) for char in ('A','\x01')]
            commands=list(p.device.commands)
            for value in values:
                field(p,value)
                try:
                    parsed=datetime.strptime(value,'%Y/%m/%d %H:%M:%S')
                    valid=bool(re.fullmatch(r'\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}',value)) and 1980<=parsed.year<=2079
                except ValueError:valid=False
                result=invoke(p,'ut_validate')
                assert bool(result.p&1)==(not valid),(value,result.a,result.p)
            assert p.device.commands==commands and not p.device.clock_writes
            p.key(27);p.check();p.close();p.restored()
            done('calendar, wire-year limits, field shape and character validation without I/O',p,dates=len(values))

        if args.case=='input':
            p=GraphicalPanel();p.key(ord('T'));p.check()
            p.key(9);p.key(9);p.key(9)
            assert p.value('ui_selected')==16;p.key(13);p.check()
            p.key(21);p.type('2028/02/30 23:59:58');p.key(13)
            assert p.value('ug_notice')==13 and p.value('ui_selected')==17
            assert not p.device.clock_writes;p.check()
            p.key(21);p.type('2028/02/29 23:59:58');p.key(13);p.check()
            assert not p.device.clock_writes
            p.key(9);p.key(13);p.check()
            assert p.value('ug_mode')==0 and not p.device.clock_writes
            open_clock(p);p.key(21);p.type('2028/02/29 23:59:58');p.check()
            assert bytes(p.ram[p.symbol('ut_offsets'):p.symbol('ut_offsets')+6])==bytes([2,5,8,11,14,17])
            p.key(13);p.key(13)
            assert p.device.clock_writes==[b'\x01\x27\x80\x02\x1d\x17\x3b\x3a']
            assert p.device.commands[-2:]==[p.device.clock_writes[0],b'\x01\x26']
            assert p.value('ug_notice')==16;p.check()
            p.key(ord('R'));p.key(13);p.check()
            assert len(p.device.clock_writes)==1
            p.close();p.restored()
            done('keyboard editing, invalid leap day, cancelled confirmation, exact binary packet and readback',p)

        if args.case=='protocol':
            p=GraphicalPanel()
            for text,advance in [('1980/01/01 00:00:00',0),('1999/12/31 23:59:59',1),
                                 ('2000/02/28 23:59:59',2),('2026/02/28 23:59:59',1),
                                 ('2026/04/30 23:59:59',2),('2079/12/31 23:59:57',2)]:
                open_clock(p);p.device.advance=advance;submit(p,text)
                assert p.value('ug_notice')==16,(text,p.value('ug_notice'));p.check()
            done('readback advances across minute, day, leap day, month and century boundaries',p)
            for mode,wanted_notice in [('ignored',15),('too-late',15),('backwards',15),
                                        ('invalid',14),('wrong-century',14),('status',14)]:
                p.device.clock_ignored=False;p.device.advance=0;p.device.bad_readback=None;p.device.write_status=b'00,OK'
                open_clock(p)
                if mode=='ignored':p.device.clock_ignored=True
                if mode=='too-late':p.device.advance=3
                if mode=='backwards':p.device.advance=-1
                if mode=='invalid':p.device.bad_readback=b'2026/02/30 12:34:56'
                if mode=='wrong-century':p.device.bad_readback=b'0080/01/01 00:00:00'
                if mode=='status':p.device.write_status=b'71,CLOCK ERROR'
                submit(p,'2026/09/14 12:34:56')
                assert p.value('ug_notice')==wanted_notice,(mode,p.value('ug_notice'))
                count=len(p.device.clock_writes);p.key(ord('R'))
                assert len(p.device.clock_writes)==count
            p.device.time=b'2026/09/14 12:34:56';p.device.write_status=b'00,OK';p.device.bad_readback=None
            p.key(ord('R'));p.check();p.close();p.restored()
            done('ignored writes, different or malformed readings and rejected status consume each confirmation once',p)

        if args.case in ('vdc16','vdc64'):
            size=int(args.case[3:]);heap.Bus=type('ClockVDC',(CalculatorBus,),dict(size=size,reu_kib=128))
            p=VDCPanel();p.frame();p.click(3);p.click(16);p.check()
            p.key(21);writes=p.bus.data_writes;steps=p.instructions
            p.key(ord('2'));p.check()
            field_writes=p.bus.data_writes-writes;field_steps=p.instructions-steps
            assert 0<field_writes<2000,field_writes
            p.type('000/01/01 00:00:00');p.check()
            p.move(100,80);writes=p.bus.data_writes;p.frame(dx=1);p.check()
            pointer_writes=p.bus.data_writes-writes
            assert pointer_writes<=96,pointer_writes
            p.click(10);assert p.value('ug_notice')==16;p.check()
            assert p.device.clock_writes==[b'\x01\x27\x64\x01\x01\x00\x00\x00']
            assert p.device.time==b'2000/01/01 00:00:00'
            p.click(16);p.click(11);p.check()
            p.click(16);p.key(9);p.check();p.click(17)
            assert p.value('ui_selected')==17;p.check()
            p.key(27);p.check();assert len(p.device.clock_writes)==1
            p.close();p.restored()
            done(f'{size} KiB VDC: mouse/keyboard edit, focus, confirm/cancel, complete canvases and restored REU/display',p,field_vdc_writes=field_writes,field_instructions=field_steps,pointer_vdc_writes=pointer_writes)

        if args.case=='fault':
            heap.Bus=type('ClockFaultVDC',(VDCBus,),dict(size=64))
            p=VDCPanel();open_clock(p);p.check();p.bus.stall=True
            p.key(9);assert p.value('vd_fault')
            owned,stack=p.m.stats(),p.cpu.sp
            for key in (13,ord('S'),ord('R'),27):
                p.key(key);assert not p.device.clock_writes and p.m.stats()==owned and p.cpu.sp==stack
            p.bus.stall=False;p.key(27,exited=True);p.restored()
            done('uncertain display state prevents clock writes and retains ownership until restoration',p)
        report['passed']=True
    except BaseException as error:
        report['error']=repr(error)
        if 'p' in locals():
            report['failure_commands']=[command.hex() for command in p.device.commands]
            report['failure_writes']=[command.hex() for command in p.device.clock_writes]
            report['failure_state']={name:p.value(name) for name in ('ug_mode','ui_selected','ug_notice','ut_field','uc_error')}
        raise
    finally:
        heap.Bus,drives.DriveDOS=original_bus,original_dos
        args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
