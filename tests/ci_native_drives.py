#!/usr/bin/env python3
"""Native drive policy and literal mount/eject commands, with independent UCI state."""
import argparse
from collections import deque
import copy
import hashlib
import json
from pathlib import Path

from py65.devices.mpu6502 import MPU
import ci_native_controls as panels
from ci_native_files import RECORDS
from uci_bus import UCIBus


class DriveDOS(panels.PanelDOS):
    def __init__(self):
        super().__init__()
        self.inventory=bytes([4,0,8,1,0,9,1,4,10,1,5,11,0])
        self.powers={0:b'on',1:b'on'}
        self.files[b'/Usb0/work.d64']=bytearray(b'DISK FIXTURE')
        self.directories[b'/Usb0']=[b'\x20work.d64']
        self.mounted={8:b'/system.d64',9:b'/original.d64'}
        self.mutations=[];self.accept_without_change=False

    def __setitem__(self,address,value):
        if address==0xdf1c and value==1:
            command=bytes(self.command)
            if command in self.faults:return super().__setitem__(address,value)
            if command in (b'\x04\x34',b'\x04\x35'):
                reply=[(self.powers[command[1]-0x34],b'00,OK')]
            elif len(command)>=3 and command[0] in (1,2) and command[1] in (0x23,0x24):
                target,op,device=command[:3]
                assert 8<=device<=30 and device!=8,('attempted system-drive mutation',command)
                if op==0x23:
                    path=command[3:];assert path.startswith(b'/') and b'\0' not in path
                    assert path in self.files,('missing modeled image',path)
                else:assert len(command)==3;path=None
                self.mutations.append(command)
                if not self.accept_without_change:self.mounted[device]=path
                reply=[(b'',b'00,OK')]
            else:return super().__setitem__(address,value)
            self.packets=deque(reply)
            return UCIBus.__setitem__(self,address,value)
        return super().__setitem__(address,value)


class DrivePanel(panels.Panel):
    def __init__(self,configure=lambda device:None):
        panels.PanelDOS=DriveDOS
        super().__init__(configure)

    def set(self,name,value,size=1):
        at=self.symbol(name);self.ram[at:at+size]=value.to_bytes(size,'little')

    def name(self,path=b'/Usb0/work.d64',context=1):
        at=self.symbol('ud_name');self.ram[at:at+len(path)]=path
        self.set('ud_name_length',len(path));self.set('ud_context',context)

    def call(self,name,a=0,expected=0):
        stack=bytes(self.ram[0x100:0x200])
        try:
            cpu=MPU(memory=self.m.bus,pc=self.symbol(name));cpu.sp=0xe0;cpu.p=0x20;cpu.a=a;cpu.stPushWord(0xaff)
            for steps in range(12000000):
                if cpu.pc==0xb00 and cpu.sp==0xe0:break
                if not self.io.stub(cpu):cpu.step()
            else:raise AssertionError((name,'did not return',hex(cpu.pc)))
            assert (cpu.a,bool(cpu.p&1))==(expected,bool(expected)),(name,cpu.a,expected,hex(cpu.pc))
            assert self.m.bus.config==0x0e and not cpu.p&12
        finally:self.ram[0x100:0x200]=stack

    def ready(self):
        self.call('ud_probe');self.set('ud_selected',1);self.name()

    def close(self):
        self.key(27,exited=True)
        assert self.m.stats()==(175,251,32) and self.device.paths=={1:b'/shell',2:b'/browser'}
        assert self.device.mounted[8]==b'/system.d64'


def run():
    cases=[]
    def done(name):cases.append(name);print('PASS:',name,flush=True)
    p=DrivePanel();p.ready();initial=copy.deepcopy(p.device.mounted)
    p.call('ud_prepare',0x23);assert p.value('ud_pending')==0x23 and p.device.mounted==initial
    p.call('ud_cancel');p.call('ud_confirm',expected=0x87);assert not p.device.mutations
    p.close();done('prepare/cancel never changes a drive; absent confirmation is rejected')

    for context in (1,2):
        p=DrivePanel();p.ready();p.name(context=context);before=len(p.device.commands)
        p.call('ud_prepare',0x23);p.call('ud_confirm')
        assert p.device.mutations==[bytes([context,0x23,9])+b'/Usb0/work.d64']
        assert p.device.commands[before:]==[b'\x04\x29\x01',b'\x01\x07',b'\x02\x07',p.device.mutations[0]]
        assert not p.value('ud_pending') and p.device.mounted[9]==b'/Usb0/work.d64'
        p.call('ud_prepare',0x24);p.call('ud_confirm');assert p.device.mounted[9] is None
        assert p.device.mutations[-1]==bytes([context,0x24,9]);p.close()
    done('literal full-path mount/eject in both DOS contexts, fresh inventory and both file probes')

    p=DrivePanel();p.ready();long=b'/'+b'A'*249+b'.g71';assert len(long)==254
    long=b'/'+b'A'*250+b'.g71';assert len(long)==255;p.device.files[long]=bytearray(b'IMAGE')
    p.name(long,2);p.call('ud_prepare',0x23);p.call('ud_confirm')
    assert p.device.mutations==[b'\x02\x23\x09'+long] and len(p.device.mutations[0])==258
    p.close();done('255-byte image path reaches firmware without truncation or count wrap')

    p=DrivePanel();p.ready()
    for extension in (b'd64',b'D71',b'd81',b'g64',b'G71'):
        p.name(b'/x.'+extension);p.call('ud_prepare',0x23);p.call('ud_cancel')
    for path in (b'',b'x.d64',b'/.d64',b'/x.g81',b'/x.txt',b'/x.d640',b'/a\0b.d64'):
        p.name(path);p.call('ud_prepare',0x23,expected=0x84)
    for context in (0,3,255):p.name(context=context);p.call('ud_prepare',0x23,expected=0x86)
    assert not p.device.mutations;p.close();done('supported image suffixes, absolute paths, full-name NUL and context checks')

    p=DrivePanel();p.ready();p.set('ud_selected',0);p.call('ud_prepare',0x24,expected=0x81)
    p.device.inventory=bytes([2,0,9,1,0,8,1]);p.call('ud_probe')
    for index in (0,1):p.set('ud_selected',index);p.call('ud_prepare',0x24,expected=0x81)
    assert not p.device.mutations;p.close();done('system IEC address and formerly observed system slots remain locked')

    for record,error in (([0,9,0],0x82),([3,9,1],0x80),([4,9,1],0x80),([0,0,1],0x80)):
        p=DrivePanel();p.device.inventory=bytes([2,0,8,1]+record);p.ready()
        p.call('ud_prepare',0x24,expected=error);assert not p.device.mutations;p.close()
    for power in (0,1):
        p=DrivePanel();p.device.inventory=bytes([3,0,8,1,0,9,1,4,9,power]);p.ready()
        p.call('ud_prepare',0x24,expected=0x80);assert not p.device.mutations;p.close()
    done('off, unsupported, invalid and duplicate destinations cannot reach a mutating command')

    for replacement in (bytes([1,0,8,1]),bytes([2,0,8,1,1,9,1]),
                        bytes([2,0,8,1,0,10,1]),bytes([2,0,8,1,0,9,0])):
        p=DrivePanel();p.ready();p.call('ud_prepare',0x24);p.device.inventory=replacement
        p.call('ud_confirm',expected=0x83);assert not p.value('ud_pending') and not p.device.mutations;p.close()
    done('changed count, type, address or power invalidates the confirmed snapshot')

    p=DrivePanel();p.device.inventory=bytes([4,0,8,1,0,9,1]);p.ready()
    assert p.value('ud_verified') and p.value('ud_partial')
    p.call('ud_prepare',0x24);p.call('ud_confirm');assert p.device.mutations==[b'\x01\x24\x09']
    assert p.device.commands[-6:]==[b'\x04\x29\x01',b'\x04\x34',b'\x04\x35',b'\x01\x07',b'\x02\x07',b'\x01\x24\x09']
    p.close();done('documented short inventory is reconciled with independent A/B power queries')
    for power in (b'off',b'ON',b'onX',b'',b'on  '):
        p=DrivePanel();p.device.inventory=bytes([4,0,8,1,0,9,1]);p.device.powers[1]=power
        p.call('ud_probe',expected=9);assert not p.value('ud_verified') and not p.device.mutations;p.close()
    done('mismatching or malformed independent power replies disable partial-inventory operations')

    for address in (0x98,RECORDS,RECORDS+16):
        p=DrivePanel();p.ready();saved=p.ram[address];p.ram[address]=1
        p.call('ud_prepare',0x24,expected=0x85);assert not p.device.mutations
        p.ram[address]=saved;p.close()
    for context in (1,2):
        p=DrivePanel();p.ready();p.device.files[b'/foreign']=bytearray(b'OTHER CLIENT DATA')
        p.device.handles[context]=dict(name=b'/foreign',mode=1,pos=123)
        before=copy.deepcopy(p.device.handles);p.call('ud_prepare',0x24)
        p.call('ud_confirm',expected=0x85)
        assert p.device.handles==before and not p.device.mutations;p.device.handles[context]=None;p.close()
    done('native, KERNAL and either foreign DOS file remain untouched; operation is refused')

    p=DrivePanel();p.ready();p.call('ud_prepare',0x23)
    command=b'\x01\x23\x09/Usb0/work.d64';p.device.faults[command]=[(b'',b'81,INVALID PARAMS')]
    before=copy.deepcopy(p.device.mounted);p.call('ud_confirm',expected=0x11)
    p.call('ud_confirm',expected=0x87);assert p.device.mounted==before
    assert p.device.commands.count(command)==1;p.close()
    done('target rejection consumes confirmation once and never replays a mount')
    return cases


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True);args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    report=dict(passed=False,physical_hardware_io=False,cases=[],images={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (root/'target/native/kestrel.prg',root/'target/native-desktop/controls.prg')})
    original=panels.PanelDOS
    try:report['cases']=run();report['passed']=True
    except BaseException as error:report['error']=repr(error);raise
    finally:panels.PanelDOS=original;args.report.write_text(json.dumps(report,indent=2)+'\n')
