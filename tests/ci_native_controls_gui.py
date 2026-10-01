#!/usr/bin/env python3
"""Disk-loaded blue Ultimate controls, mouse, picker and guarded confirmations."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from ci_native_pointer import Pointer, PointerBus, heap
from ci_native_drives import DrivePanel
from ci_native_controls import info_body
from native_controls_scene import surface, RECTS
from native_controls_check import panel_screen


class GraphicalPanel(DrivePanel):
    allow_busy_poll=True
    position=Pointer.position
    frame=Pointer.frame
    poll=Pointer.poll
    move=Pointer.move
    restored=Pointer.restored

    def __init__(self,configure=lambda device:None):
        super().__init__(configure)
        self.bus=self.m.bus.native
        self.frames=0
        self.checked=0

    def key(self,key,exited=False):
        self.observation_target=None
        self.keys.append(key);self.loop(exited);self.events+=1
        assert int.from_bytes(self.ram[0x3d13:0x3d15],'little')==self.events
        if not exited:assert self.cpu.pc==0xffe4 and self.ram[0x3d12]==1

    def click(self,index,*,exited=False):
        x0,y0,x1,y1=RECTS[index]
        self.move((x0+x1)//2,(y0+y1)//2)
        self.frame(down=True);self.frame(down=False,exited=exited)

    def check(self,body=None,*,graphical_override=None):
        assert not self.value('ug_picker_active')
        page=self.value('uc_page');focus=self.value('ui_selected');mode=self.value('ug_mode')
        selected=self.value('ud_selected');notice=self.value('ug_notice')
        records=[tuple(self.device.inventory[i:i+3]) for i in range(1,len(self.device.inventory),3)]
        count=len(records);partial=count!=self.device.inventory[0]
        if mode==2:
            at=self.symbol('ut_edit');length=self.value('ut_field')
            text=bytes(self.ram[at:at+length]).decode()
            body=graphical=['YYYY/MM/DD HH:MM:SS  (1980-2079)','',text]
            if focus==17:body.append(' '*self.ram[self.symbol('ut_field')+1]+'^')
        elif mode:
            mount=self.value('ud_pending')==0x23
            body=[('MOUNT IMAGE ON IEC ' if mount else 'EJECT IMAGE FROM IEC ')+str(records[selected][1]),'']
            if mount:
                at=self.symbol('ud_name');name=bytes(self.ram[at:at+self.value('ud_name_length')]).decode().upper()
                body += [name[i:i+36] for i in range(0,len(name),36)]
            graphical=body
        elif body is not None:
            graphical=body
            if page==1:body=['ULTIMATE DRIVE INVENTORY','']+body
        elif page==0:
            target=self.value('uc_target')
            identity=self.device.identities.get(target,b'NO TARGET').rstrip(b'\0').decode()
            body=graphical=info_body(target,identity,self.device.model.decode().upper())
        elif page==1:
            assert not self.value('uc_error')
            graphical=['SLOT TYPE   IEC   POWER','PARTIAL: A/B CHECKED; OTHERS UNKNOWN' if partial else '']
            body=['ULTIMATE DRIVE INVENTORY','']
            if partial:body+=['PARTIAL REPLY: 2 OF 4 RECORDS','']
            for i,(kind,device,on) in enumerate(records):
                power='ON' if on else 'OFF'
                graphical += [f'{">" if i==selected else " "} {i+1}   {kind:02X}     {device}     {power}','']
                body += [f'SLOT {i+1}  TYPE {kind:02X}  IEC {device}  {power}']
            if not records:body+=['NO DRIVE RECORDS']
            else:body+=['','TYPES: 00=1541 01=1571 02=1581','OTHER TYPE CODES SHOWN AS REPORTED.']
        elif page==2:
            count_interfaces=self.device.interfaces;index=self.value('uc_interface')
            body=[f'NETWORK INTERFACES: {count_interfaces}']
            if count_interfaces:
                octets=self.device.addresses[index]
                addresses=['.'.join(map(str,octets[i:i+4])) for i in (0,4,8)]
                body += [f'INTERFACE {index}','','IP:      '+addresses[0],'MASK:    '+addresses[1],
                    'GATEWAY: '+addresses[2],'','CONFIGURED ADDRESSES; LINK UNTESTED.']
            else:body+=['NO INTERFACES AVAILABLE']
            graphical=body
        else:body=graphical=['CARTRIDGE RTC','',self.device.time.decode(),'S SET TIME  R REFRESH CLOCK READING.']
        if graphical_override is not None:graphical=graphical_override
        bitmap=self.value('ug_bitmap')
        if bitmap:
            wanted=surface(graphical,page=page,focus=focus,mode=mode,count=count,notice=notice)
            actual=bytes(self.ram[0xc000:0xe400])
            assert actual==wanted,('bitmap',page,focus,mode,notice,
                [(i,a,b) for i,(a,b) in enumerate(zip(actual,wanted)) if a!=b][:24])
        for bank in ((1,) if bitmap else (0,1)):
            if bank==1 and self.value('vd_phase'):
                continue
            wanted=panel_screen((40,80)[bank],body,page=page,focus=focus,mode=mode,selected=selected,notice=notice)
            assert self.screens[bank]==wanted,('console',bank,page,focus,mode,notice,body,
                [(i,a,b) for i,(a,b) in enumerate(zip(self.screens[bank],wanted)) if a!=b][:24])
        self.checked+=1

    def clean(self):
        assert not self.value('ug_picker_active') and not self.io.handles
        assert self.device.handles=={1:None,2:None} and self.device.paths=={1:b'/shell',2:b'/browser'}
        at=self.symbol('b_cache')
        assert all(self.ram[at+i]==0 for i in range(0,40,4))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--case',choices=['all','keyboard','mouse','picker','faults','fallback','payloads','cleanup'],default='all')
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    report=dict(passed=False,physical_hardware_io=False,cases=[],images={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (root/'target/native-desktop/controls.prg',root/'target/native/kestrel.prg')})
    def done(name,p):
        report['cases'].append(dict(name=name,keys=p.events,frames=p.frames,views=p.checked,instructions=p.instructions,
            mutations=[command.hex() for command in p.device.mutations]))
        print('PASS:',name,flush=True)
    try:
        if args.case in ('all','keyboard'):
            p=GraphicalPanel();p.check();assert p.value('ug_bitmap') and p.value('ui_selected')==0
            saved_keys=bytes(p.ram[0x1000:0x1100])
            p.key(9);assert p.value('ui_selected')==1;p.key(13);assert p.value('uc_page')==1;p.check()
            p.key(ord('M'));assert p.value('ug_notice')==3 and not p.value('ug_picker_active');p.check()
            p.key(0x11);assert p.value('ud_selected')==1 and p.value('ui_selected')==13;p.check()
            p.key(ord('E'));assert p.value('ug_mode')==1 and p.value('ui_selected')==11;p.check()
            p.key(13);assert not p.value('ug_mode') and p.value('ug_notice')==2;p.check()
            p.key(ord('E'));p.key(9);assert p.value('ui_selected')==10;p.check()
            p.key(13);assert p.device.mutations==[b'\x01\x24\x09'];p.check()
            p.key(ord('R'));assert not p.value('ug_notice');p.check()
            p.key(ord('N'));p.check();p.key(0x1d);assert p.value('uc_interface')==1;p.check()
            p.key(ord('T'));p.check();p.key(9);assert p.value('ui_selected')==4
            p.key(9);assert p.value('ui_selected')==7;p.check()
            p.key(ord('I'));p.key(0x9d);assert p.value('uc_target')==3;p.check()
            assert bytes(p.ram[0x1000:0x1100])==saved_keys
            p.close();p.restored();done('blue tabs, all panels, drive selection, protected system disk, default Cancel and one confirmed eject',p)
        if args.case in ('all','mouse'):
            p=GraphicalPanel();p.frame();p.click(1);assert p.value('uc_page')==1;p.check()
            p.click(6);assert p.value('ud_selected')==1;p.check()
            p.click(9);assert p.value('ug_mode')==1;p.check()
            p.move(80,170);p.frame(down=True);p.move(280,190);p.frame(down=False)
            assert not p.device.mutations and p.value('ug_mode')==1
            p.click(11);p.check();assert not p.value('ug_mode')
            p.click(14);assert p.value('ud_selected')==2;p.check()
            p.click(8);assert p.value('ug_notice')==5 and not p.value('ug_picker_active');p.check()
            p.click(13);p.click(9);p.click(10);assert p.device.mutations==[b'\x01\x24\x09'];p.check()
            p.frame();assert p.device.mutations==[b'\x01\x24\x09']
            p.click(2);p.check();p.click(6);assert p.value('uc_interface')==1;p.check()
            p.click(3);p.check();p.click(0);p.check();p.click(4,exited=True);p.restored()
            done('mouse tabs, previous/next, drive rows, press-drag cancellation, explicit confirm and exit restore',p)
        if args.case in ('all','picker'):
            p=GraphicalPanel();p.device.directories[b'/']=[b'\x10Usb0']
            p.key(ord('D'));p.key(0x11)
            preferences=(bytes(p.ram[0x3d29:0x3d35]),bytes(p.ram[0x4a00:0x4b00]),bytes(p.ram[0x3e00:0x3f00]))
            keys=bytes(p.ram[0x1000:0x1100]);p.key(ord('M'))
            assert p.value('ug_picker_active') and not p.value('ug_bitmap')
            assert bytes(p.ram[0x1000:0x1100])==keys
            p.key(13);p.key(13);assert not p.value('ug_picker_active') and p.value('ug_mode')==1
            p.check();p.clean();assert p.value('ui_selected')==11 and not p.device.mutations
            assert preferences==(bytes(p.ram[0x3d29:0x3d35]),bytes(p.ram[0x4a00:0x4b00]),bytes(p.ram[0x3e00:0x3f00]))
            p.key(27);p.check();p.key(ord('M'));p.key(0x85);p.key(13);p.check()
            assert p.value('ud_context')==2
            p.device.accept_without_change=True;before=copy.deepcopy(p.device.mounted)
            p.key(9);p.key(13);p.check();assert p.value('ug_notice')==1 and p.device.mounted==before
            assert p.device.mutations==[b'\x02\x23\x09/Usb0/work.d64']
            p.key(ord('R'));p.check();assert p.device.mutations==[b'\x02\x23\x09/Usb0/work.d64']
            p.key(ord('M'));p.key(27);p.check();p.clean();p.close();p.restored()
            done('Ultimate picker, both contexts, full-path confirmation, cancellation and acceptance without a false mounted-state claim',p)

            parent=b'/'+b'A'*60+b'/'+b'B'*60+b'/'+b'C'*60+b'/'+b'D'*60
            name=parent+b'/IMAGE1.d64';assert len(name)==255
            p=GraphicalPanel();p.device.directories[parent]=[b'\x20IMAGE1.d64'];p.device.files[name]=bytearray(b'LONG IMAGE')
            p.key(ord('D'));p.key(0x11);p.name(name,2);p.key(ord('M'));p.key(13)
            assert p.value('ug_mode')==1 and p.value('ud_name_length')==255;p.check();p.clean()
            p.key(9);p.key(13);p.check();assert p.device.mutations==[b'\x02\x23\x09'+name]
            p.close();p.restored();done('255-byte picker result is fully shown on confirmation and transmitted without clipping',p)
        if args.case in ('all','faults'):
            p=GraphicalPanel();p.key(ord('D'));p.key(0x11);p.key(ord('E'))
            p.device.inventory=bytes([4,0,8,1,0,10,1,4,12,1,5,11,0])
            p.key(9);p.key(13);assert not p.value('ug_mode') and p.value('ug_notice')==6 and not p.device.mutations;p.check()
            p.key(ord('R'));p.key(ord('E'));p.key(27);p.check()
            p.device.inventory=bytes([4,0,8,1,0,9,1]);p.key(ord('R'));p.check()
            p.key(ord('E'));p.key(9);p.device.faults[b'\x01\x24\x09']=[(b'',b'71,DRIVE REJECTED')]
            p.key(13);assert not p.value('ug_mode') and p.value('ug_notice')==9 and not p.device.mutations
            p.check(['UNAVAILABLE: 11  DOS 47  LINK 00','71,DRIVE REJECTED'])
            issued=p.device.commands.count(b'\x01\x24\x09');p.key(ord('R'))
            assert p.device.commands.count(b'\x01\x24\x09')==issued;p.check()
            p.close();p.restored();done('changed destination, partial inventory checks and rejected command cannot silently replay',p)
        if args.case in ('all','fallback'):
            class ForeignSprites(PointerBus):
                def __init__(self):super().__init__();self.video[0xd015]=1
            original=heap.Bus;heap.Bus=ForeignSprites
            try:p=GraphicalPanel()
            finally:heap.Bus=original
            assert not p.value('ug_bitmap') and p.value('ug_error')==8;p.check()
            p.key(ord('D'));p.key(0x11);p.key(ord('E'));p.check();p.key(9);p.key(13);p.check()
            assert p.device.mutations==[b'\x01\x24\x09'];p.close()
            assert p.bus.video[0xd015]==1 and p.m.stats()==(175,251,32)
            done('foreign sprite owner retains both text consoles and guarded keyboard controls',p)
        if args.case in ('all','payloads'):
            p=GraphicalPanel();p.device.model=b'a'*64;p.device.identities[4]=b'X'*512;p.key(ord('I'))
            suffix=['','TARGET 4']+['X'*36]*4+['...']
            p.check(['HARDWARE','A'*36,'...']+suffix,
                graphical_override=['HARDWARE','A'*33+'...']+suffix)
            p.device.model=b'a\x01\xffb\0ignored';p.device.identities[4]=b'valid\0ignored';p.key(ord('R'))
            p.check(['HARDWARE','A..B','','TARGET 4','VALID'])
            p.device.time=b'2026/02/29 12:00:00';p.key(ord('T'))
            p.check(['CARTRIDGE RTC','','UNAVAILABLE: 09  DOS 00  LINK 00','INVALID REPLY; R RETRIES THE QUERY.'])
            p.close();p.restored();done('long identification clipping, control-byte substitution, NUL termination and malformed RTC in complete blue/text views',p)
        if args.case in ('all','cleanup'):
            p=GraphicalPanel();p.device.directories[b'/Usb0']=[b'\x20'+f'DISK{i:02d}.d64'.encode() for i in range(40)]
            p.key(ord('D'));p.key(0x11);p.name();p.key(ord('M'))
            assert p.value('ug_picker_active') and p.value('bu_cursor') and not p.value('ug_bitmap')
            p.device.delay=None;p.key(27)
            assert not p.value('ug_picker_active') and p.value('ug_notice')==10 and p.value('bu_cursor')
            assert p.device.paths[1]==b'/Usb0' and not p.device.mutations;p.check()
            stack=p.cpu.sp;keys=bytes(p.ram[0x1000:0x1100])
            for key in (ord('M'),ord('E'),27):
                p.key(key);assert p.cpu.sp==stack and p.value('ug_notice')==10
                assert not p.value('ug_mode') and not p.value('ug_picker_active') and not p.device.mutations
                assert bytes(p.ram[0x1000:0x1100])==keys;p.check()
            p.device.delay=0;p.key(ord('R'));p.check();p.clean()
            assert not p.value('bu_cursor') and p.value('ug_notice')==0
            p.close();p.restored();done('uncertain picker abort retains ownership, blocks mount/eject/exit, preserves input and recovers on explicit Refresh',p)
        report['passed']=True
    except BaseException as error:report['error']=repr(error);raise
    finally:args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
