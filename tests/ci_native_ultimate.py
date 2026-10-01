#!/usr/bin/env python3
"""Execute native file API and real UCI registers against independent DOS bytes.

The C128 MMU/ROM model and existing DOS/FIFO model are composed at the bus;
no native service routine is replaced. IEC and Ultimate streams coexist.
"""
import argparse
import hashlib
import json
from pathlib import Path

from native_ultimate_dos import Files as DOSFiles
from ci_native_files import (Files,OWNER,HANDLE,DEVICE,NAMELEN,MODE,TYPE,COUNT,
    ACTUAL,EOF,ERROR,DOS,STATUS,BUSY,POSITION,FORMAT,NAME,RECORDS,BUFFER,
    OPEN,READ,WRITE,CLOSE,RELEASE)
from ci_native_heap import ROOT,IMAGE,symbol

PATH=0x4e00


class UltimateBus:
    def __init__(self,native,dos):self.native,self.dos=native,dos
    def __getattr__(self,name):return getattr(self.native,name)
    def __getitem__(self,address):
        if not self.native.config&1 and 0xdf1c<=address<=0xdf1f:return self.dos[address]
        return self.native[address]
    def __setitem__(self,address,value):
        if not self.native.config&1 and 0xdf1c<=address<=0xdf1f:self.dos[address]=value
        else:self.native[address]=value


class Client(Files):
    def __init__(self,files=None,iec=None):
        super().__init__(iec)
        self.ultimate=DOSFiles(files)
        self.m.bus=UltimateBus(self.m.bus,self.ultimate)

    def open_u(self,name,mode=0,device=1,expected=0,**kwargs):
        self.ram[DEVICE]=device;self.ram[FORMAT]=3;self.ram[MODE]=mode
        self.ram[TYPE]=0;self.ram[NAMELEN]=len(name)
        self.ram[PATH:PATH+len(name)]=name
        self.call(OPEN,expected,**kwargs)
        return self.handle()

    def read_u(self,count=512,expected=0,**kwargs):
        self.word(COUNT,count);self.call(READ,expected,**kwargs)
        return bytes(self.ram[BUFFER:BUFFER+self.word(ACTUAL)])

    def write_u(self,data,expected=0,**kwargs):
        self.ram[BUFFER:BUFFER+len(data)]=data
        self.word(COUNT,len(data));self.call(WRITE,expected,**kwargs)
        if not expected:assert self.word(ACTUAL)==len(data)

    def clean(self):
        self.call(RELEASE)
        assert self.ultimate.handles=={1:None,2:None} and not self.io.handles
        assert self.m.stats()==(175,251,32)
        assert self.ultimate.paths=={1:b'/shell',2:b'/browser'}
        assert self.ultimate.discarded==0


def reads():
    count=0
    for size in (0,1,255,256,511,512,513,66053):
        data=bytes((i*73+i//251)&255 for i in range(size));c=Client({b'/Usb0/input':data})
        c.ultimate.fragment=73
        zero=bytes(c.ram[:256]);c.open_u(b'/Usb0/input')
        got=bytearray()
        while not c.ram[EOF]:
            before=bytes(c.ram[BUFFER:BUFFER+512]);part=c.read_u();assert part
            got+=part
            assert c.ram[BUFFER+len(part):BUFFER+512]==before[len(part):]
            assert int.from_bytes(c.ram[POSITION:POSITION+4],'little')==len(got)
        commands=len(c.ultimate.commands);assert c.read_u()==b''
        assert len(c.ultimate.commands)==commands and got==data
        assert bytes(c.ram[:256])==zero
        count+=len(c.ultimate.commands);c.clean()
    return dict(sizes=[0,1,255,256,511,512,513,66053],commands=count)


def writes():
    c=Client();c.ultimate.fragment=117;c.ultimate.direct_write_corruption=True
    c.open_u(b'/Usb0/output',1)
    data=b''
    for size in (1,255,256,257,511,512,512,13):
        chunk=bytes((i*67+len(data))&255 for i in range(size));c.write_u(chunk);data+=chunk
        assert c.ultimate.files[b'/Usb0/output']==data
        assert int.from_bytes(c.ram[POSITION:POSITION+4],'little')==len(data)
    sent=[len(command)-4 for command in c.ultimate.commands if command[1]==5]
    assert sent==[1,255,256,257,511,511,1,511,1,13],sent
    c.call(CLOSE);c.open_u(b'/Usb0/output');got=b''
    while not c.ram[EOF]:got+=c.read_u()
    assert got==data;c.clean()
    return dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),write_lengths=sent)


def ownership():
    c=Client({b'/one':b'1',b'/two':b'2'},iec={(8,b'IEC',b'S'):b'IEC DATA'})
    one=c.open_u(b'/one')
    before=len(c.ultimate.commands);c.open_u(b'/two',expected=0x15)
    assert len(c.ultimate.commands)==before
    two=c.open_u(b'/two',device=2)
    c.ram[HANDLE:HANDLE+4]=one;c.ram[OWNER]=33;c.call(READ,5)
    c.ram[OWNER]=32;assert c.read_u()==b'1';c.call(CLOSE)
    c.call(READ,4)
    c.ram[DEVICE]=8;c.ram[FORMAT]=0;c.ram[MODE]=0;c.ram[TYPE]=0
    c.ram[NAMELEN]=3;c.ram[NAME:NAME+3]=b'IEC';c.call(OPEN)
    iec=c.handle();assert c.read_u()==b'IEC DATA'
    c.ram[HANDLE:HANDLE+4]=two;assert c.read_u()==b'2'
    c.clean();assert iec!=one
    foreign=Client({b'/foreign':b'x'})
    foreign.ultimate.handles[1]=dict(name=b'/foreign',mode=1,pos=0)
    foreign.open_u(b'/foreign',expected=0x15)
    assert [cmd[1] for cmd in foreign.ultimate.commands]==[7]
    assert foreign.ultimate.handles[1] is not None
    foreign.call(RELEASE);assert foreign.ultimate.handles[1] is not None
    busy=Client();busy.ultimate.state=0x10;busy.ultimate.stuck=True
    busy.open_u(b'/new',1,expected=0x15)
    assert not busy.ultimate.commands and not busy.ultimate.aborted
    return dict(mixed_backends=True,foreign_file_preserved=True,foreign_transaction_preserved=True)


def failures():
    results=[]
    for kind in ('short-read','read-error','overlong','bad-status','short-write','verify','tail-write','seek'):
        c=Client({b'/input':bytes(range(256))*3})
        if kind in ('short-read','read-error','overlong','bad-status'):
            c.open_u(b'/input')
            if kind=='short-read':c.ultimate.read_limit=300
            if kind=='read-error':c.ultimate.read_status=b'71,DISK ERROR'
            if kind=='overlong':c.ultimate.inject[4]=lambda cmd,reply:[(bytes(513),b'00,OK')]
            if kind=='bad-status':c.ultimate.read_status=b'00,OK'+b'X'*40
            c.read_u(expected=0x11)
        else:
            c.open_u(b'/output',1)
            if kind=='short-write':c.ultimate.write_limit=7
            if kind=='tail-write':c.ultimate.write_limit={1:0}
            if kind=='verify':c.ultimate.inject[4]=lambda cmd,reply:[(b'X'*512,b'')]
            if kind=='seek':c.ultimate.inject[6]=lambda cmd,reply:[(b'',b'71,BAD SEEK')]
            c.write_u(bytes(range(256))*2,expected=0x11)
        assert c.word(ACTUAL)==0 and c.ram[RECORDS+3]&6==6
        commands=len(c.ultimate.commands)
        c.read_u(expected=1 if kind in ('short-write','verify','tail-write','seek') else 0x11)
        assert len(c.ultimate.commands)==commands,'failed operation replayed'
        c.clean();results.append(kind)
    c=Client();c.open_u(b'/missing',expected=0x11)
    assert c.ram[RECORDS] and c.ram[RECORDS+3]&4
    c.clean()                  # status 84 proves rejected OPEN owns no file
    c=Client({b'/input':b'abc'});c.open_u(b'/input')
    c.ultimate.inject[3]=lambda cmd,reply:[(b'',b'71,CLOSE ERROR')]
    c.call(CLOSE,0x11);assert c.ram[RECORDS]
    del c.ultimate.inject[3];c.clean()
    c=Client();c.ultimate.present=False;c.open_u(b'/absent',expected=0x11)
    assert not c.ultimate.commands and c.ram[STATUS]==0xfe
    return dict(cases=results+['missing-open-close-84','uncertain-close-retry','absent'])


def names_and_platform():
    c=Client()
    for name in (b'',b'relative',b'/bad\0name',b'/'+b'X'*128):
        c.open_u(name,1,expected=1)
        assert not c.ultimate.commands
    name=b'/'+b'A'*126+b'/'+b'B'*127
    assert len(name)==255
    c.open_u(name,1);c.clean();assert name in c.ultimate.files
    c=Client({b'/irq':bytes(range(256))*2})
    attempts=[]
    def irq(cpu,steps):
        if steps%101==0 and not cpu.p&4:cpu.irq();attempts.append(steps)
    zero=bytes(c.ram[:256]);c.open_u(b'/irq',flags=8,interrupt=irq)
    assert c.read_u(flags=8,interrupt=irq)==bytes(range(256))*2
    assert bytes(c.ram[:256])==zero and len(attempts)>20
    c.clean()
    c=Client();c.open_u(b'/masked',flags=4,expected=8)
    assert not c.ultimate.commands
    return dict(longest_path=255,creation_component_limit=127,irq_attempts=len(attempts),zero_page_preserved=True)


def protocol_edges():
    c=Client({b'/TIMEOUT':b'abc'});c.open_u(b'/TIMEOUT')
    c.ultimate.stuck=True;c.read_u(expected=0x11,max_steps=6000000)
    assert c.ram[STATUS]==0xff and c.ultimate.aborted==1
    assert c.ram[RECORDS] and c.ram[RECORDS+3]&4
    c.ultimate.stuck=False;c.clean()
    for packets in ([(b'A',b'71,READ ERROR'),(b'B',b'00,OK')],
                    [(b'A',b'00,OK'),(b'B',b'71,READ ERROR')]):
        c=Client({b'/ERROR':b'AB'});c.open_u(b'/ERROR')
        c.ultimate.inject[4]=lambda cmd,reply:packets
        c.read_u(2,expected=0x11);assert c.ram[DOS]==71;c.clean()
    c=Client({b'/LARGE':bytes(range(256))*65536+b'X'})
    c.open_u(b'/LARGE');assert c.ram[symbol('nu_high')]==1
    assert c.read_u(1)==b'\0'
    assert c.ram[RECORDS+13:RECORDS+16]==bytes(3) and c.ram[symbol('nu_high')]==1
    assert c.read_u()==(bytes(range(1,256))+bytes(range(256))+b'\0')
    assert c.ram[RECORDS+13:RECORDS+16]==b'\0\xfe\xff' and not c.ram[symbol('nu_high')]
    before=len(c.ultimate.commands);c.ram[BUSY]=1;c.call(READ,7);c.ram[BUSY]=0
    assert len(c.ultimate.commands)==before;c.clean()
    return dict(bounded_timeout=True,first_error_retained_across_packets=True,extent_bytes=16777217,reentry_rejected=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path);args=parser.parse_args()
    report=dict(passed=False,kernel_sha256=hashlib.sha256(IMAGE.read_bytes()).hexdigest(),cases={})
    try:
        for check in (reads,writes,ownership,failures,names_and_platform,protocol_edges):
            report['cases'][check.__name__]=check();print('PASS: native Ultimate '+check.__name__,flush=True)
        report['passed']=True
    except BaseException as error:report['error']=str(error);raise
    finally:
        if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
