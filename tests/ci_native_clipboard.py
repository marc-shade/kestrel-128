#!/usr/bin/env python3
"""Execute the shared clipboard against the native heap and real ROM gateways."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

from ci_native_heap import Machine, BUFFER, OWNER

ROOT = Path(__file__).resolve().parents[1]


def run():
    out=Path(tempfile.mkdtemp(prefix='kestrel-clipboard-cpu-'))
    subprocess.run(['64tass','-a','-B',str(ROOT/'tests/fixtures/native-clipboard.asm'),
        '-o',str(out/'client.prg'),'-l',str(out/'client.sym')],check=True,capture_output=True)
    symbols={n:int(v[1:],16) if v.startswith('$') else int(v) for n,v in re.findall(r'^(\w+)\s*=\s*(\$[0-9a-fA-F]+|[0-9]+)\s*$',
        (out/'client.sym').read_text(),re.M)}
    image=(out/'client.prg').read_bytes();pages=(len(image)-2+255)//256
    m=Machine();r=m.ram;cases=[]
    def num(name):return int.from_bytes(r[symbols[name]:symbols[name]+3],'little')
    def setv(name,value,size=3):m.set(symbols[name],value,size)
    def call(name,want=0,flags=0,interrupt=None):
        c=m.invoke(symbols['cp_'+name],flags=flags,check=False,interrupt=interrupt)
        assert (c.a,c.p&1)==(want,int(bool(want))),(name,c.a,c.p,want)
        if want!=7:assert not r[symbols['CB_BUSY']]
    def launch():
        token=m.alloc(pages,bank=0,owner=32,page=0x60)
        r[0x6000:0x6000+len(image)-2]=image[2:]
        r[0x3d20]=32;r[0x3d23]=2
        return token
    def retire():
        m.set(OWNER,32);m.invoke('release');r[0x3d20]=r[0x3d23]=0
    def publish(data):
        setv('cp_length',len(data));call('begin',flags=8)
        for pos in range(0,len(data),512):
            chunk=data[pos:pos+512];r[BUFFER:BUFFER+len(chunk)]=chunk
            setv('cp_count',len(chunk),2);call('write',flags=8)
        call('commit',flags=8)
    def read(data):
        call('info');assert num('cp_length')==len(data) and r[symbols['cp_format']]==1
        result=bytearray()
        for pos in range(0,len(data),511):
            size=min(511,len(data)-pos);setv('cp_offset',pos);setv('cp_count',size,2)
            call('read',flags=8);result+=r[BUFFER:BUFFER+size]
        assert result==data
        return hashlib.sha256(result).hexdigest()
    first=launch();call('info');assert num('cp_length')==0 and not r[symbols['cp_format']]
    call('read',want=4)
    data=bytes((i*137+i//256)&255 for i in range(15360))
    publish(data);read(data)
    allocations=[r[0x3c00+i*8:0x3c08+i*8] for i in range(32)]
    clip=[v for v in allocations if v[0]==31];assert len(clip)==1 and clip[0][1]==1
    assert clip[0][2]+clip[0][3]<=0x60 or 0xc0<=clip[0][2] and clip[0][2]+clip[0][3]<=0xff
    retire();assert m.stats()==(175,191,31)
    second=launch();assert first!=second;read(data)
    cases.append(dict(name='full 15 KiB byte text survives app release and generation change',sha256=read(data)))
    before=bytes(r[symbols['CB_FORMAT']:symbols['CB_PENDING']])
    for size in (0,15361,65536,0xffffff):setv('cp_length',size);call('begin',want=6)
    for offset,count in ((15360,1),(15359,2),(0,0),(0,513),(65535,1),(65536,1),(0xffffff,1)):
        setv('cp_offset',offset);setv('cp_count',count,2);call('read',want=6)
    assert before==bytes(r[symbols['CB_FORMAT']:symbols['CB_PENDING']]);read(data)
    setv('cp_length',600);call('begin');setv('cp_count',512,2)
    r[BUFFER:BUFFER+512]=b'Z'*512;call('write');call('commit',want=6);read(data)
    retire();launch();call('commit',want=4);call('write',want=4);read(data)
    call('abort');assert not r[symbols['CB_PENDING']]
    cases.append(dict(name='invalid ranges, incomplete writes and a foreign-generation draft keep prior text'))
    # Capacity/slots and the reserved provider window are observed independently.
    blocker=m.alloc(96,bank=1,owner=16,page=0x60)
    blockers=[]
    while True:
        m.set(OWNER,16);m.set(0x3d01,1);m.set(0x3d02,1)
        cpu=m.invoke('alloc',check=False)
        if cpu.p&1:break
        blockers.append(bytes(r[0x3d04:0x3d08]))
    setv('cp_length',15360);call('begin',want=3);read(data)
    m.set(OWNER,16);m.invoke('release');read(data)
    m.alloc(32,bank=1,owner=16,page=0x40)
    m.alloc(96,bank=1,owner=16,page=0x60)
    m.alloc(63,bank=1,owner=16,page=0xc0)
    before=m.metadata();setv('cp_length',15360);call('begin',want=2)
    assert m.metadata()==before;read(data)
    m.set(OWNER,16);m.invoke('release')
    cases.append(dict(name='slot and capacity refusals retain all published bytes and foreign allocations'))
    # A write error cannot turn a partial draft into a successful publication.
    setv('cp_length',4);call('begin');setv('cp_count',4,2)
    injected=[]
    def fail_write(cpu,bus):
        if cpu.pc==0x1c29:
            injected.append(cpu.pc);cpu.pc=(cpu.stPopWord()+1)&65535;cpu.a=9;cpu.p|=1
    call('write',want=9,interrupt=fail_write);assert injected
    call('commit',want=6);read(data);call('abort')
    # Refused freeing keeps both tokens, allowing a later commit retry.
    setv('cp_length',3);call('begin');setv('cp_count',3,2);r[BUFFER:BUFFER+3]=b'new';call('write')
    def fail_free(cpu,bus):
        if cpu.pc==0x1c23:cpu.pc=(cpu.stPopWord()+1)&65535;cpu.a=9;cpu.p|=1
    call('commit',want=9,interrupt=fail_free);read(data);call('commit');read(b'new')
    cases.append(dict(name='write poisoning and uncertain publication cleanup preserve old text and recover'))
    call('info',want=8,flags=4)
    for address in (symbols['CB_BUSY'],0x3d11,0x3d91,0x3d3b):
        r[address]=1;call('info',want=7);assert r[address]==1;r[address]=0
    r[0x3d23]=3;call('info',want=8);r[0x3d23]=2
    # Interrupts during ROM banked transfers cannot break payload or borrowed state.
    fired=[]
    def irq(cpu,bus):
        if not fired and cpu.pc==0x2a2:
            fired.append(cpu.pc);cpu.irq()
    setv('cp_offset',0);setv('cp_count',3,2);call('read',flags=8,interrupt=irq)
    assert fired and r[BUFFER:BUFFER+3]==b'new'
    setv('CB_SEQUENCE',0xffffff);setv('cp_length',1);call('begin',want=0x16);call('clear',want=0x16);read(b'new')
    setv('CB_SEQUENCE',1);call('clear');call('info');assert not num('cp_length') and not r[symbols['cp_format']]
    retire();assert m.stats()==(175,251,32)
    cases.append(dict(name='foreground and reentrancy gates, IRQ preservation, generation retirement and full release'))
    return dict(passed=True,physical_hardware_io=False,cases=cases,output=str(out),
        fixture_bytes=len(image),calls=Machine.calls,longest_steps=Machine.longest)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args();result=run();args.report.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
