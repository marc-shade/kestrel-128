#!/usr/bin/env python3
"""Assembled generic UCI packet gate: bounds, serialization and shared ownership."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from ci_native_query import Client
from ci_native_files import BUFFER,COUNT,ACTUAL,OWNER,BUSY,DOS,STATUS,CLOSE,RECORDS
from ci_native_heap import IMAGE,symbol

COMMAND=0x1c71


def packet(client,command,expected=0,**kwargs):
    assert 2<=len(command)<=512
    client.ram[BUFFER:BUFFER+len(command)]=command
    client.word(COUNT,len(command)-2)
    count=client.call(COMMAND,expected,**kwargs)
    return bytes(client.ram[BUFFER:BUFFER+count])


def run():
    cases={}
    for body in (0,1,253,254,255,256,509,510):
        c=Client();command=b'\x04\x70'+bytes((i*73+body)&255 for i in range(body))
        response=bytes((i*31+body)&255 for i in range(512))
        c.ultimate.replies[command]=[(response[:255],b''),(response[255:],b'00,OK')]
        paths=copy.deepcopy(c.ultimate.paths);interrupts=[]
        before=bytes(c.ram[:256]);after_buffer=bytes(c.ram[BUFFER+512:BUFFER+768])
        def irq(cpu,steps):
            if steps%101==0 and not cpu.p&4:cpu.irq();interrupts.append(steps)
        assert packet(c,command,flags=8,interrupt=irq)==response
        assert c.ultimate.commands==[command] and c.ultimate.paths==paths
        assert before==bytes(c.ram[:256]) and after_buffer==bytes(c.ram[BUFFER+512:BUFFER+768])
        assert interrupts and not c.ram[BUSY] and not c.ram[DOS] and not c.ram[STATUS]
        cases['body-'+str(body)]=dict(command_bytes=len(command),reply_bytes=512,irq_count=len(interrupts))
    c=Client();request=bytes(c.ram[BUFFER:BUFFER+512])
    for length in (511,512,513,767,768,1023,32767,65279,65533,65534,65535):
        c.word(COUNT,length);c.call(COMMAND,1)
        assert c.word(ACTUAL)==0 and bytes(c.ram[BUFFER:BUFFER+512])==request
    assert not c.ultimate.commands and not c.ultimate.command and not c.ultimate.aborted
    cases['invalid-lengths']=dict(rejected=11,no_device_writes=True,no_count_wrap=True)
    for name,setup,error in (
            ('absent',lambda c:setattr(c.ultimate,'present',False),0x11),
            ('foreign-transaction',lambda c:setattr(c.ultimate,'state',0x10),0x15),
            ('file-lock',lambda c:c.ram.__setitem__(BUSY,1),7),
            ('heap-lock',lambda c:c.ram.__setitem__(0x3d11,1),7),
            ('zero-owner',lambda c:c.ram.__setitem__(OWNER,0),1),
            ('retired-owner',lambda c:c.ram.__setitem__(OWNER,255),1)):
        c=Client();setup(c);packet(c,b'\x04\x01',expected=error)
        assert not c.ultimate.command and not c.ultimate.commands and not c.ultimate.aborted
        cases[name]=dict(error=error,no_device_writes=True)
    c=Client();packet(c,b'\x04\x01',expected=8,flags=4)
    assert not c.ultimate.command and not c.ultimate.commands
    cases['masked-irq']=dict(error=8)
    for name,replies,prefix,status in (
            ('target-error',[(b'FAIL',b'81,INVALID PARAMS')],b'FAIL',0),
            ('first-error',[(b'A',b'71,ERROR'),(b'B',b'00,OK')],b'AB',0),
            ('missing-status',[(b'A',b'')],b'A',0),
            ('long-status',[(b'A',b'00,'+b'Z'*29)],b'A',0xfc),
            ('long-response',[(b'Z'*513,b'00,OK')],b'Z'*512,0xfc)):
        c=Client();command=b'\x02\x24\x09';c.ultimate.replies[command]=replies
        assert packet(c,command,expected=0x11)==prefix
        assert c.ultimate.commands==[command] and c.ram[STATUS]==status and not c.ram[BUSY]
        cases[name]=dict(prefix=len(prefix),transport_status=status)
    for delay in (100,None):
        c=Client();command=b'\x01\x23\x09/Usb0/picture.d64'
        c.ultimate.replies[command]=[(b'',b'00,OK')];c.ultimate.stuck=True;c.ultimate.delay=delay
        packet(c,command,expected=0x11,max_steps=12000000)
        assert c.ultimate.commands==[command] and c.ultimate.abort_requests==1 and c.ram[STATUS]==255
        if delay is None:
            packet(c,command,expected=0x15)
            assert c.ultimate.commands==[command] and c.ultimate.abort_requests==1
            c.ultimate.complete_abort()
        cases['abort-'+str(delay)]=dict(single_command=True,single_abort=True,no_replay=True)
    c=Client();file_handle=c.open_u(b'/kept',device=2);cursor=c.directory()
    command=b'\x04\x01';c.ultimate.replies[command]=[(b'ID',b'00,OK')]
    records=bytes(c.ram[RECORDS:RECORDS+32]);paths=copy.deepcopy(c.ultimate.paths)
    assert packet(c,command)==b'ID' and c.ultimate.paths==paths
    assert bytes(c.ram[RECORDS:RECORDS+32])==records
    assert c.read_u()==b'\x20ONE';sent=len(c.ultimate.commands)
    packet(c,command,expected=0x15);assert len(c.ultimate.commands)==sent and not c.ultimate.aborted
    assert c.read_u()==b'\x20TWO';c.call(CLOSE);c.select(file_handle)
    assert c.read_u()==b'PRESERVED';c.clean()
    cases['shared-file-cursor-lifetime']=dict(pending_cursor_refused=True,file_and_paths_preserved=True)
    return cases


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True);args=parser.parse_args()
    report=dict(passed=False,physical_hardware_io=False,kernel_sha256=hashlib.sha256(IMAGE.read_bytes()).hexdigest())
    try:report['cases']=run();report['passed']=True;print('PASS:',len(report['cases']),'native command workflows',flush=True)
    except BaseException as error:report['error']=repr(error);raise
    finally:args.report.write_text(json.dumps(report,indent=2)+'\n')
