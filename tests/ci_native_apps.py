#!/usr/bin/env python3
"""Run native loader instructions against bounded IEC fault fixtures.

ROM banking remains real in ci_native_heap's bus; only the external KERNAL
file interface is modeled here. x128/hardware cover its real serial behavior.
"""
import argparse
import binascii
import hashlib
import json
from pathlib import Path

from py65.devices.mpu6502 import MPU
from ci_native_heap import Machine, ROOT, IMAGE, symbol

RUN=0x1c38


def seal(image):
    data=bytearray(image)
    data[16:18]=bytes(2)
    declared=int.from_bytes(data[10:12],'little')
    data[16:18]=binascii.crc_hqx(data[2:2+declared],0xffff).to_bytes(2,'little')
    return bytes(data)


def fixture(code=b'\xa9\x2a\x60',pages=16):
    header=bytearray(b'NAPP'+bytes([1,1,0,0])+bytes(8)+b'CHECK'+bytes(11))
    header[8:10]=(32+len(code)).to_bytes(2,'little')
    header[10]=pages;header[12]=32
    return seal(b'\0\x60'+header+code)


class IEC:
    def __init__(self,machine,image=None,missing=False,absent=False,read_error=None,close_error=False):
        self.m=machine;self.ram=machine.ram
        self.image=image if image is not None else fixture()
        self.missing,self.absent,self.read_error,self.close_error=missing,absent,read_error,close_error
        self.handles={};self.selected=None;self.status=0;self.dos=0;self.events=[]
        self.filename=b'';self.lfn,self.device,self.sa=0,0,0
        self.expected_filename=b'CHECK,P,R'
        self.ram[0x98:0x9b]=b'\0\0\3'
        self.ram[0xb7:0xbd]=b'\x03\x06\x02\x09\x40\x0c'
        self.ram[0xc6:0xc8]=b'\x0f\x01'
        self.ram[0x9d]=0x80

    def tables(self):
        self.ram[0x98]=len(self.handles)
        for index,(number,h) in enumerate(self.handles.items()):
            self.ram[0x362+index]=number
            self.ram[0x36c+index]=h['device']
            self.ram[0x376+index]=h['sa']|0x60

    def add(self,number,device,sa):
        self.handles[number]=dict(device=device,sa=sa,position=0,data=b'')
        self.tables()

    def stub(self,cpu):
        pc=cpu.pc
        if pc not in (0xff68,0xffba,0xffbd,0xffc0,0xffc6,0xffcf,0xffb7,0xffcc,0xffc3):return False
        def carry(flag):cpu.p=(cpu.p&~1)|int(flag)
        if pc==0xff68:
            self.ram[0xc6],self.ram[0xc7]=cpu.a,cpu.x
        elif pc==0xffba:
            self.lfn,self.device,self.sa=cpu.a,cpu.x,cpu.y
            self.ram[0xb8:0xbb]=bytes([cpu.a,cpu.y,cpu.x])
        elif pc==0xffbd:
            pointer=cpu.x|cpu.y<<8
            self.ram[0xb7]=cpu.a;self.ram[0xbb:0xbd]=pointer.to_bytes(2,'little')
            self.filename=bytes(self.ram[pointer:pointer+cpu.a])
        elif pc==0xffc0:
            assert self.ram[0xc6:0xc8]==b'\0\0','native filename bank was not selected'
            self.events.append(('open',self.lfn,self.device,self.sa,self.filename.hex()))
            self.status=0x80 if self.absent else 0
            carry(self.absent)
            if not self.absent:
                assert self.lfn not in self.handles,'stole an existing logical file'
                self.add(self.lfn,self.device,self.sa)
                if self.sa!=15:
                    assert self.filename==self.expected_filename,self.filename
                    self.handles[self.lfn]['data']=b'' if self.missing else self.image
                    self.dos=62 if self.missing else 0
        elif pc==0xffc6:
            carry(cpu.x not in self.handles)
            if cpu.x in self.handles:
                self.selected=cpu.x;h=self.handles[cpu.x]
                self.ram[0x99]=h['device'];self.status=0
                if h['sa']==15:
                    h['data']=f'{self.dos:02d}, STATUS,00,00\r'.encode();h['position']=0
        elif pc==0xffcf:
            assert self.selected in self.handles,'read without an owned input channel'
            h=self.handles[self.selected];at=h['position']
            if h['sa']!=15 and self.read_error==at:
                cpu.a,self.status=0,2
            elif at>=len(h['data']):
                cpu.a,self.status=0,2
            else:
                cpu.a=h['data'][at];h['position']+=1
                self.status=0x40 if h['position']==len(h['data']) else 0
                if h['sa']==15 and self.status:self.dos=0
        elif pc==0xffb7:
            cpu.a=self.status
        elif pc==0xffcc:
            self.selected=None;self.ram[0x99:0x9b]=b'\0\3'
        elif pc==0xffc3:
            self.events.append(('close',cpu.a))
            self.handles.pop(cpu.a,None);self.tables()
            self.status=1 if self.close_error else 0
        cpu.pc=(cpu.stPopWord()+1)&65535
        return True


def run_case(image=None,expected=0,flags=0,prepare=None,retained=False,ui_exit=None,**faults):
    from ci_native_files import StreamIEC
    m=Machine();ram=m.ram
    data=image if image is not None else fixture()
    name=b'CHECK' if ui_exit is None else b'CALC'
    files={} if faults.get('missing') else {(8,name,b'P'):data}
    iec=StreamIEC(m,files);iec.image=data
    if faults.get('absent'):iec.fail_open=124
    if faults.get('read_error') is not None:iec.fail_read=faults['read_error']
    if faults.get('close_error'):iec.fail_close=122
    ram[0x3d21:0x3d23]=bytes([8,5]);ram[0x3d40:0x3d45]=b'CHECK'
    ram[symbol('ui_system_device')]=8
    # An unrelated owner and open file must survive every success/failure.
    m.alloc(2,1,owner=16,page=0x80)
    protected=bytes(m.bus.ram[1][0x8000:0x8200])
    iec.add(6,9,2)
    if prepare:prepare(m,iec)
    parameters=bytes(ram[0xb7:0xbd])+bytes(ram[0xc6:0xc8])+bytes([ram[0x9d]])
    previous_error=ram[0x3d27]
    cpu=MPU(memory=m.bus,pc=RUN if ui_exit is None else symbol('native_calculator'));cpu.sp=0xe0;cpu.p=0x20|flags
    if ui_exit is None:cpu.stPushWord(0xaff)
    else:iec.expected_filename=b'CALC,P,R'
    returned=0xb00 if ui_exit is None else symbol('native_draw')
    entered=False;entry=(0x6000+int.from_bytes(iec.image[14:16],'little')) if len(iec.image)>=16 else -1
    for steps in range(8000000):
        if cpu.pc==returned and cpu.sp==0xe0:break
        if cpu.pc==entry:
            entered=True
            assert set(iec.handles)=={6},'app started with loader channels still open'
            assert parameters==bytes(ram[0xb7:0xbd])+bytes(ram[0xc6:0xc8])+bytes([ram[0x9d]])
        if not iec.stub(cpu):cpu.step()
    else:raise AssertionError(f'loader did not return, PC={cpu.pc:04x}')
    assert (cpu.a,cpu.p&1)==(expected if ui_exit is None else ui_exit,int(bool(expected))),(expected,cpu.a,hex(cpu.pc))
    if ui_exit is not None:assert ram[0x3d16]==ui_exit
    assert cpu.sp==0xe0 and cpu.p&12==flags&12
    assert ram[0x3d27]==(previous_error if expected==7 else expected)
    assert parameters==bytes(ram[0xb7:0xbd])+bytes(ram[0xc6:0xc8])+bytes([ram[0x9d]])
    assert m.bus.ram[1][0x8000:0x8200]==protected
    assert 6 in iec.handles and iec.handles[6]['device']==9 and iec.handles[6]['sa']==2
    assert not ({120,121}&set(iec.handles)),iec.events
    if not retained:assert not ({122,123,124,125,126}&set(iec.handles)),iec.events
    assert m.bus.config==0x0e and not m.bus.io_writes
    if retained:
        assert ram[0x3d20]==32 and ram[0x3d23]==4
    elif expected!=7:
        assert ram[0x3d20]==0 and ram[0x3d23]==0
        assert all(ram[0x3c00+i]!=32 for i in range(0,256,8))
    if expected and not retained:assert not entered,'executed a rejected image'
    pages=min(96,iec.image[12]) if len(iec.image)>12 else 0
    for bank,address,value in m.bus.far_writes:
        assert bank==0 and 0x6000<=address<0x6000+pages*256,(bank,address,value)
    return m,iec,dict(result=expected,entered=entered,instructions=steps,channel_events=iec.events)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path);args=parser.parse_args()
    report=dict(passed=False,image_sha256=hashlib.sha256(IMAGE.read_bytes()).hexdigest(),cases={})
    cases=report['cases']
    try:
        m,iec,cases['return']=run_case()
        assert m.ram[0x3d24]==42
        _,_,cases['workspace-app-result']=run_case(ui_exit=42)
        assert m.ram[0x6023:0x7000]==bytes(0x7000-0x6023),'declared BSS was not zeroed'
        abi8=bytearray(fixture());abi8[8]=8
        m,iec,cases['abi-1.8-accepted']=run_case(seal(abi8))
        assert m.ram[0x3d24]==42
        abi9=bytearray(fixture());abi9[8]=9
        m,iec,cases['abi-1.9-accepted']=run_case(seal(abi9))
        assert m.ram[0x3d24]==42
        abi12=bytearray(fixture());abi12[8]=12
        m,iec,cases['abi-1.12-accepted']=run_case(seal(abi12))
        assert m.ram[0x3d24]==42
        abi13=bytearray(fixture());abi13[8]=13
        m,iec,cases['abi-1.13-accepted']=run_case(seal(abi13))
        abi14=bytearray(fixture());abi14[8]=14
        m,iec,cases['abi-1.14-accepted']=run_case(seal(abi14))
        assert m.ram[0x3d24]==42 and m.ram[0x3de5:0x3e00]==bytes(27)
        for name,length,pages in [('one-page',256,1),('full-slot',24576,96)]:
            code=b'\xa9\x2a\x60'+bytes((i*29+17)&255 for i in range(length-35))
            m,iec,cases[name]=run_case(fixture(code,pages))
            assert m.ram[0x6000+length-1]==code[-1]
        # EXIT must recover the loader stack even through nested app frames.
        code=b'\x48\x48\xa9\x39\x4c\x3e\x1c'
        m,iec,cases['exit']=run_case(fixture(code),flags=8)
        assert m.ram[0x3d24]==57
        for label,address,action in [('replace-request',0x1c53,1),('workspace-request',0x1c56,2)]:
            image=bytearray(fixture(b'\x48\x48\xa9\x63\x4c'+address.to_bytes(2,'little')))
            image[8]=2
            m,iec,cases[label]=run_case(seal(image),flags=8)
            assert m.ram[0x3d24]==0 and m.ram[0x3d28]==action
        m,iec,cases['stale-request-cleared']=run_case(prepare=lambda m,i:m.ram.__setitem__(0x3d28,2))
        assert m.ram[0x3d28]==0
        _,_,cases['invalid-source-format']=run_case(expected=1,prepare=lambda m,i:m.ram.__setitem__(0x3d2c,4))
        # An app can allocate more owned memory; return releases it too.
        code=bytes.fromhex('a9028d013da9018d023dad203d8d003d20201ca92b60')
        m,iec,cases['owned-allocation']=run_case(fixture(code))
        assert m.stats()==(175,249,31) and m.ram[0x3d24]==43
        mutations=[('origin',0,1),('magic',2,0),('format',6,2),('abi',7,2),('minor',8,15),
                   ('flags',9,1),('pages-zero',12,0),('pages-too-large',12,97),
                   ('reserved',13,1),('entry-header',14,31),('entry-past-end',14,40),
                   ('entry-high',15,1),('title-control',18,13),('size-small',10,32),('size-high',11,17)]
        for name,offset,value in mutations:
            data=bytearray(fixture());data[offset]=value
            _,_,cases[name]=run_case(bytes(data),expected=0x10)
        for length in (0,1,2,10,33,34,35,36):
            _,_,cases[f'truncated-{length}']=run_case(fixture()[:length],expected=0x12)
        _,_,cases['trailing-data']=run_case(fixture()+b'x',expected=0x13)
        bad=bytearray(fixture());bad[-2]^=1
        _,_,cases['checksum']=run_case(bytes(bad),expected=0x14)
        _,_,cases['workspace-load-error']=run_case(bytes(bad),expected=0x14,ui_exit=0x14)
        _,_,cases['missing']=run_case(expected=0x11,missing=True)
        _,_,cases['absent']=run_case(expected=0x11,absent=True)
        _,_,cases['serial-read']=run_case(expected=0x11,read_error=35)
        _,_,cases['close']=run_case(expected=0x11,close_error=True,retained=True)
        assert not cases['close']['entered']
        _,_,cases['interrupt-masked']=run_case(expected=8,flags=4)
        _,_,cases['slot-overlap']=run_case(expected=2,prepare=lambda m,i:m.alloc(1,0,owner=17,page=0x60))
        _,_,cases['busy-owner']=run_case(expected=7,prepare=lambda m,i:m.alloc(1,0,owner=32,page=0x60))
        for name,prepare in [('redirected-input',lambda m,i:m.set(0x99,8)),
                             ('redirected-output',lambda m,i:m.set(0x9a,8)),
                             ('channel-conflict',lambda m,i:i.add(5,8,7)),
                             ('command-conflict',lambda m,i:i.add(5,8,15))]:
            _,_,cases[name]=run_case(expected=0x15,prepare=prepare)
        for name,prepare in [('bad-device',lambda m,i:m.set(0x3d21,31)),
                             ('empty-name',lambda m,i:m.set(0x3d22,0)),
                             ('long-name',lambda m,i:m.set(0x3d22,17)),
                             ('wildcard',lambda m,i:m.set(0x3d40,ord('*')))]:
            _,_,cases[name]=run_case(expected=1,prepare=prepare)
        # Corrupt an owned page tag, then return: keep the whole owner's
        # allocations reserved instead of partially freeing/reusing the slot.
        code=bytes.fromhex('a9008d6038a94a60')
        _,_,cases['corrupt-cleanup']=run_case(fixture(code),expected=9,retained=True)
        report['passed']=True
        print(f'PASS: {len(cases)} native manifest/IEC/lifecycle cases; owned cleanup and unrelated resources preserved',flush=True)
    except BaseException as error:
        report['error']=str(error);raise
    finally:
        if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
