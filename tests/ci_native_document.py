#!/usr/bin/env python3
"""Run the assembled banked document model against independent byte arrays."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import re
import subprocess
import tempfile

from py65.devices.mpu6502 import MPU
from ci_native_heap import Machine,ROOT,IMAGE


class Document:
    def __init__(self,image,symbols,workspace=False):
        self.m=Machine();self.ram=self.m.ram;self.symbols=symbols
        self.protected=[]
        if workspace:
            for bank,page in ((0,0xc0),(1,4)):
                handle=self.m.alloc(32,bank,owner=16,page=page)
                data=bytes((i*73+bank*31)&255 for i in range(8192))
                self.m.bus.ram[bank][page*256:page*256+8192]=data
                self.protected.append((bank,page,data,handle))
        # Reserve 12 KiB for the app (including the editor's display read cache).
        # Include both workspace blocks and the resident Ultimate reservation.
        self.app=self.m.alloc(48,0,owner=32,page=0x60)
        self.baseline=self.m.stats()
        origin=int.from_bytes(image[:2],'little');self.ram[origin:origin+len(image)-2]=image[2:]
        self.ram[0x3d20]=32;self.calls=0;self.instructions=0;self.irq_attempts=0
        self.call('init')

    def value(self,name,size=1):
        at=self.symbols['d_'+name];return int.from_bytes(self.ram[at:at+size],'little')

    def set(self,name,value,size=1):
        at=self.symbols['d_'+name];self.ram[at:at+size]=value.to_bytes(size,'little')

    def call(self,operation,*,pos=None,data=None,count=None,slot=0,expected=0,interrupt=False,fault=None):
        self.set('slot',slot)
        if pos is not None:self.set('pos',pos,3)
        if data is not None:
            at=self.symbols['d_input'];self.ram[at:at+len(data)]=data
            if operation=='replace':self.set('replace_count',len(data),3)
            else:count=len(data)
        count_bytes=getattr(self,'span_count_bytes',2) if operation=='replace' else 2
        if count is not None:self.set('count',count,count_bytes)
        arguments=self.value('pos',3),self.value('count',count_bytes)
        zero=bytes(self.ram[:256]);config=self.m.bus.config
        cpu=MPU(memory=self.m.bus,pc=self.symbols['doc_'+operation]);cpu.sp=0xe0;cpu.p=0x20
        cpu.stPushWord(0xaff);fault_calls=0
        for steps in range(50000000):
            if cpu.pc==0xb00 and cpu.sp==0xe0:break
            if fault and cpu.pc==fault[0]:
                fault_calls+=1
                if fault_calls==fault[1]:
                    cpu.a=fault[2];cpu.p|=1;cpu.pc=(cpu.stPopWord()+1)&65535;continue
            if interrupt and steps%997==0 and not cpu.p&4:
                cpu.irq();self.irq_attempts+=1
            cpu.step()
        else:raise AssertionError(f'document {operation} did not return at {cpu.pc:04x}')
        self.calls+=1;self.instructions+=steps
        assert (cpu.a,cpu.p&1)==(expected,int(bool(expected))),(operation,cpu.a,expected,hex(cpu.pc))
        assert bytes(self.ram[:256])==zero and self.m.bus.config==config
        assert arguments==(self.value('pos',3),self.value('count',count_bytes))
        for bank,page,data,_ in self.protected:
            assert self.m.bus.ram[bank][page*256:page*256+len(data)]==data
        if operation=='read' and not expected:
            at=self.symbols['d_output'];return bytes(self.ram[at:at+self.value('actual',2)])

    def state(self,slot=0):
        at=self.symbols['d_states']+slot;raw=self.ram[at:at+128]
        return dict(length=int.from_bytes(raw[:3],'little'),gap=int.from_bytes(raw[3:6],'little'),
                    end=int.from_bytes(raw[6:9],'little'),capacity=int.from_bytes(raw[9:12],'little'),
                    dirty=raw[12],chunks=raw[13],fault=raw[14],backing=raw[15],handles=bytes(raw[16:112]))

    def bytes(self,slot=0):
        state=self.state(slot);assert not state['fault']
        assert 0<=state['gap']<=state['end']<=state['capacity']
        assert state['length']==state['capacity']-(state['end']-state['gap'])
        if state['backing']:
            from native_document_reu import physical_bytes
            data=physical_bytes(self,state)
            self.banks={'reu'}
            return bytes(data[:state['gap']]+data[state['end']:])
        # Every chunk is a complete 4 KiB run except, with DOC_PARTIAL, the
        # last one, which may be 1..15 pages; capacity is exactly the owned pages.
        data=bytearray();banks=set();pages_total=0
        for index in range(state['chunks']):
            handle=state['handles'][index*4:index*4+4]
            assert handle[0]
            at=0x3c00+(handle[0]-1)*8;record=self.ram[at:at+8]
            last=index==state['chunks']-1
            assert record[0]==32 and record[4:7]==handle[1:],(index,bytes(record))
            assert record[3]==16 or (last and 1<=record[3]<16),(index,record[3])
            bank,page,pages=record[1],record[2],record[3];banks.add(bank);pages_total+=pages
            data+=self.m.bus.ram[bank][page*256:page*256+pages*256]
        assert state['capacity']==pages_total*256,(state['capacity'],pages_total)
        self.banks=banks
        return bytes(data[:state['gap']]+data[state['end']:])

    def append(self,data,slot=0):
        for offset in range(0,len(data),512):
            self.call('insert',pos=self.state(slot)['length'],data=data[offset:offset+512],slot=slot)

    def check(self,want,slot=0):
        assert self.bytes(slot)==want,(len(want),self.state(slot))
        for offset in sorted({0,max(0,len(want)-511),max(0,len(want)-1),len(want)}):
            assert self.call('read',pos=offset,count=512,slot=slot)==want[offset:offset+512],offset

    def dispose(self):
        for slot in (0,128):self.call('dispose',slot=slot)
        assert self.m.stats()==self.baseline
        self.m.select(self.app,32);self.m.invoke('free')
        for _,_,_,handle in self.protected:self.m.select(handle,16);self.m.invoke('free')
        assert self.m.stats()==(175,251,32)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path);args=parser.parse_args()
    report=dict(passed=False,kernel_sha256=hashlib.sha256(IMAGE.read_bytes()).hexdigest(),cases={})
    try:
        with tempfile.TemporaryDirectory(prefix='kestrel-native-document-') as directory:
            folder=Path(directory);output=folder/'document.prg';labels=folder/'document.sym'
            subprocess.run(['64tass','-a','-B',str(ROOT/'probes/native-document.asm'),'-o',str(output),'-l',str(labels)],check=True,capture_output=True)
            image=output.read_bytes();symbols={name:int(value,16) for name,value in re.findall(r'^(\w+)\s*=\s*\$([0-9a-f]+)$',labels.read_text(),re.M)}
            # The graphical Editor's configuration: short final chunk, compact code.
            partial_out=folder/'partial.prg';partial_labels=folder/'partial.sym'
            subprocess.run(['64tass','-a','-B','-D','DOC_PARTIAL=1','-D','DOC_COMPACT=1',str(ROOT/'probes/native-document.asm'),
                            '-o',str(partial_out),'-l',str(partial_labels)],check=True,capture_output=True)
            partial_image=partial_out.read_bytes()
            partial_symbols={name:int(value,16) for name,value in re.findall(r'^(\w+)\s*=\s*\$([0-9a-f]+)$',partial_labels.read_text(),re.M)}
        report['document_sha256']=hashlib.sha256(image).hexdigest();report['document_bytes']=len(image)
        def done(name,d):
            report['cases'][name]=dict(calls=d.calls,instructions=d.instructions,irq_attempts=d.irq_attempts)
            print('PASS: native document '+name,flush=True)
        d=Document(image,symbols);want=bytearray()
        assert d.call('read',pos=0,count=512)==b''
        for data in (b'A\r\nB\nC\r\0\xff',bytes(range(256)),bytes(range(256))*2):
            d.call('insert',pos=len(want),data=data);want+=data;d.check(want)
        d.call('insert',pos=1,data=b'INSERT\r\n',interrupt=True);want[1:1]=b'INSERT\r\n';d.check(want)
        d.call('delete',pos=2,count=7,interrupt=True);del want[2:9];d.check(want)
        snapshot=d.bytes(),d.state()
        for operation,position,count,error in (('insert',len(want)+1,1,6),('read',len(want)+1,1,6),
                                              ('delete',len(want),1,6),('insert',0,0,1),('read',0,513,1)):
            d.call(operation,pos=position,count=count,expected=error)
            assert (d.bytes(),d.state())==snapshot
        d.call('read',pos=0,count=1,slot=1,expected=1)
        d.dispose();done('byte-preserving-edits-EOF-bounds-and-IRQs',d)

        d=Document(image,symbols);want=bytearray(bytes(range(256))*16);d.append(want)
        d.call('delete',pos=2000,count=1);del want[2000]
        d.call('insert',pos=1000,data=b'X');want[1000:1000]=b'X'
        d.call('insert',pos=2001,data=b'Y'*512);want[2001:2001]=b'Y'*512;d.check(want)
        for offset in (1999,2000,2001,2500,3585,4095,4096):
            assert d.call('read',pos=offset,count=512)==want[offset:offset+512]
        rng=random.Random(128)
        for _ in range(36):
            at=rng.randrange(len(want)+1)
            if rng.randrange(2) or at==len(want):
                payload=rng.randbytes(rng.randrange(1,90));d.call('insert',pos=at,data=payload);want[at:at]=payload
            else:
                size=rng.randrange(1,min(90,len(want)-at)+1);d.call('delete',pos=at,count=size);del want[at:at+size]
            assert d.bytes()==want
        d.check(want);d.dispose();done('overlapping-gap-moves-growth-and-independent-random-edits',d)

        d=Document(image,symbols);want=bytearray(bytes(range(256))*16);d.append(want)
        # With no gap, equal and shorter replacements must not allocate.
        for at,count,data in ((4090,6,b'REPLACE'),(509,7,b'X'),(4090,1,b''),
                              (0,1,b'Y'*512),(4088,512,b'Z'),(1,512,b'')):
            d.call('replace',pos=at,count=count,data=data,interrupt=True)
            want[at:at+count]=data;d.check(want)
        rng=random.Random(65128)
        for _ in range(40):
            at=rng.randrange(len(want));count=rng.randrange(1,min(512,len(want)-at)+1)
            data=rng.randbytes(rng.randrange(513))
            d.call('replace',pos=at,count=count,data=data)
            want[at:at+count]=data;assert d.bytes()==want
        snapshot=d.bytes(),d.state()
        for at,count,data,error in ((len(want),1,b'A',6),(0,0,b'A',1),(0,513,b'A',1),
                                    (0,1,b'A'*513,1)):
            d.call('replace',pos=at,count=count,data=data,expected=error)
            assert (d.bytes(),d.state())==snapshot
        d.dispose();done('replace-shrink-grow-empty-boundaries-random-and-IRQs',d)

        d=Document(image,symbols);want=b'ORIGINAL'+b'X'*(4096-8);d.append(want)
        before=d.bytes(),d.state()
        d.call('replace',pos=0,count=8,data=b'LONGER REPLACEMENT',expected=2,fault=(0x1c20,1,2))
        assert (d.bytes(),d.state())==before
        d.call('replace',pos=0,count=8,data=b'SURVIVES',fault=(0x1c20,1,2))
        want=b'SURVIVES'+want[8:];d.check(want)
        d.call('replace',pos=0,count=8,data=b'',fault=(0x1c20,1,2));d.check(want[8:])
        d.dispose();done('replace-oom-keeps-original-and-no-growth-needs-no-allocation',d)

        d=Document(image,symbols,workspace=True)
        want=bytearray((i*73+(i//256)*17+(i//65536)*29+11)&255 for i in range(66053))
        d.append(want);d.check(want);assert d.banks=={0,1}
        for at,payload in ((65535,b'BEFORE\r\n'),(65536,b'AFTER\n'),(4095,b'CHUNK')):
            d.call('insert',pos=at,data=payload);want[at:at]=payload;assert d.bytes()==want
        d.call('delete',pos=65534,count=17);del want[65534:65551];d.check(want)
        for at,count,data in ((65532,20,b'ACROSS 64K\r\n'),(4090,13,b''),(65530,2,b'LONGER\n')):
            d.call('replace',pos=at,count=count,data=data,interrupt=True)
            want[at:at+count]=data;d.check(want)
        for offset in (4095,65025,65535,65536):
            assert d.call('read',pos=offset,count=512)==want[offset:offset+512]
        d.append(b'PENDING\r\n',slot=128);d.check(b'PENDING\r\n',128);d.check(want)
        before=d.bytes(),d.state()
        # Exhaust all remaining allocatable 4 KiB groups without discarding the
        # active document, exactly as a failed transactional Open must behave.
        pending=bytearray(b'PENDING\r\n')
        while True:
            state=d.state(128)
            if state['capacity']==state['length']:
                d.call('insert',pos=len(pending),data=b'FAIL',slot=128,expected=2)
                break
            size=min(512,state['capacity']-state['length']);data=b'Z'*size
            d.call('insert',pos=len(pending),data=data,slot=128);pending+=data
        assert (d.bytes(),d.state())==before;d.check(pending,128)
        d.call('dispose',slot=128);d.check(want)
        report['large_document_bytes']=len(want);report['large_document_sha256']=hashlib.sha256(want).hexdigest()
        d.dispose();done('over-64-KiB-both-banks-two-contexts-and-oom-preservation',d)

        d=Document(image,symbols);d.append(b'A'*4096+b'B'*512)
        d.call('insert',pos=0,data=b'X',expected=4,fault=(0x1c29,2,4))
        assert d.state()['fault']==4
        d.call('read',pos=0,count=1,expected=9)
        d.call('insert',pos=0,data=b'Y',expected=9)
        d.call('delete',pos=0,count=1,expected=9)
        retained=d.state()['handles']
        d.call('dispose',expected=7,fault=(0x1c23,1,7))
        assert d.state()['handles']==retained
        d.dispose();done('failed-transfer-poisons-document-and-cleanup-can-retry',d)
        d=Document(image,symbols);d.append(b'A'*4096)
        d.call('replace',pos=0,count=6,data=b'REPLACED',expected=4,fault=(0x1c29,2,4))
        assert d.state()['fault']==4
        d.call('read',pos=0,count=1,expected=9)
        d.call('replace',pos=0,count=1,data=b'X',expected=9)
        d.dispose();done('replace-transfer-failure-poisons-context',d)
        # DOC_PARTIAL: when no complete 4 KiB run is left, the final chunk starts
        # at one page and grows in place a page at a time, so the capacity is
        # always the exact page fit of the document and the chunk never moves.
        def free_runs(d):
            runs=[]
            for bank in (0,1):
                table=d.ram[0x3800+bank*256:0x3900+bank*256];start=None
                for page in range(256):
                    if not table[page] and start is None:start=page
                    if (table[page] or page==255) and start is not None:
                        end=page if table[page] else 256;runs.append((bank,start,end));start=None
            return runs
        def exact(d,length):
            state=d.state();tail=max(0,length-4096)
            assert state['capacity']==4096+256*((tail+255)//256),(state['capacity'],length)
        d=Document(partial_image,partial_symbols);want=bytearray((i*37+5)&255 for i in range(4096));d.append(want)
        # Pin all free RAM except the first 11 pages of one bank-1 run: no
        # complete 4 KiB run remains, as beside the Editor's workspace.
        pins=[];kept=None
        for bank,start,end in free_runs(d):
            if kept is None and bank==1 and end-start>=11:
                kept=(bank,start,start+11);start+=11
            if end>start:pins.append(d.m.alloc(end-start,bank,owner=16,page=start))
        assert kept and not any(end-start>=16 for _,start,end in free_runs(d))
        reached=0
        while reached<5:                                   # exact fit through five regrows
            data=bytes((len(want)*11+i)&255 for i in range(100))
            d.call('insert',pos=len(want),data=data);want+=data
            assert d.bytes()==want;exact(d,len(want))
            reached=(d.state()['capacity']-4096)//256
        assert d.state()['chunks']==2
        # Refusal: take the pages after it; growth restores the old range and
        # changes nothing (the chunk is reserved again, bytes in place).
        for bank,start,end in free_runs(d):
            pins.append(d.m.alloc(end-start,bank,owner=16,page=start))
        state=d.state();data=b'R'*(state['capacity']-state['length']+1);before=d.bytes(),d.state()
        d.call('insert',pos=len(want),data=data,expected=2)
        after=d.state();last=(after['chunks']-1)*4
        assert d.bytes()==before[0]
        assert {k:v for k,v in after.items() if k!='handles'}=={k:v for k,v in before[1].items() if k!='handles'}
        # Only the re-reserved last chunk's generation may change; same slot.
        assert after['handles'][:last+1]==before[1]['handles'][:last+1]
        assert after['handles'][last+4:]==before[1]['handles'][last+4:]
        # Edits across the boundary into the short chunk keep exact bytes.
        for at,count,payload in ((4090,20,b'ACROSS THE PARTIAL!!'),(4096,3,b''),(10,5,b'head')):
            d.call('replace',pos=at,count=count,data=payload);want[at:at+count]=payload;d.check(want)
        # With RAM back, the final chunk grows to 4 KiB, then a new chunk follows.
        for handle in pins:d.m.select(handle,16);d.m.invoke('free')
        while d.state()['capacity']<8192:
            data=b'G'*200;d.call('insert',pos=len(want),data=data);want+=data
            assert d.bytes()==want;exact(d,len(want))
        assert d.state()['chunks']==2
        while len(want)<=8192:
            data=b'H'*300;d.call('insert',pos=len(want),data=data);want+=data
        state=d.state();assert state['chunks']==3 and state['capacity']==12288,state
        d.check(want);d.dispose();done('partial-final-chunk-exact-fit-refusal-and-regrowth-to-full-chunks',d)

        report['passed']=True
        print('PASS: native banked document model, exact logical bytes and complete ownership cleanup',flush=True)
    except BaseException as error:report['error']=str(error);raise
    finally:
        if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
