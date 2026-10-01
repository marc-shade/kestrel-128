#!/usr/bin/env python3
"""Execute owned native IEC streams with independent files and injected faults."""
import argparse
import hashlib
import json
from pathlib import Path

from py65.devices.mpu6502 import MPU
from ci_native_heap import Machine, ROOT, IMAGE
from ci_native_apps import IEC, fixture, seal

OWNER=0x3d80;HANDLE=0x3d81;DEVICE=0x3d85;NAMELEN=0x3d86;MODE=0x3d87;TYPE=0x3d88
COUNT=0x3d89;ACTUAL=0x3d8b;EOF=0x3d8d;ERROR=0x3d8e;DOS=0x3d8f;STATUS=0x3d90
BUSY=0x3d91;POSITION=0x3d92;FORMAT=0x3d96;NAME=0x3da0;RECORDS=0x3dc0;BUFFER=0x3a00
OPEN=0x1c41;READ=0x1c44;WRITE=0x1c47;CLOSE=0x1c4a;RELEASE=0x1c4d


class StreamIEC(IEC):
    def __init__(self,machine,files=None):
        super().__init__(machine)
        self.files={key:bytearray(value) for key,value in (files or {}).items()}
        self.codes={};self.output=None;self.pending=None
        self.fail_open=None;self.fail_read=None;self.fail_write=None
        self.fail_close=None;self.fail_flush=False;self.bad_status=None
        self.reads=0;self.writes=0
        self.formats={};self.blocks={};self.edit_blocks=None;self.fail_block=None
        self.command=bytearray();self.short_eoi_quirk=True
        self.locked=set();self.status_text={};self.fail_command=None
        self.identity={}   # device -> the 73 line "UI" returns, instead of the ROM's for its format
        self.printers={}   # device 4..7 -> the bytes a present printer received
        self.sectors={}    # device -> {(track, sector): bytearray(256)}: the disk U1/U2 reach
        self.protected=set()        # devices whose disk is write-protected (U2 answers 26)
        self.sector_faults={}       # (device, b'U1'/b'U2', track, sector) -> (code, status text)

    def buffer_command(self,device,command):
        """U1/U2 (read/write a whole sector through a "#" buffer channel) and
        B-P (its buffer pointer), sent on the command channel as "U1:2 0 T S",
        "U2:2 0 T S" and "B-P:2 0", as the 1541/1571/1581 DOS answers them."""
        self.events.append(('buffer',device,command))
        verb,_,args=command.rstrip(b'\r').partition(b':')
        fields=args.split()
        channel=int(fields[0]) if fields else -1
        h=next((h for h in self.handles.values() if h['device']==device and h['sa']==channel and 'buffer' in h),None)
        disk=self.sectors.get(device,{})
        if h is None:code,text=70,'70,NO CHANNEL,00,00'
        elif verb==b'B-P' and len(fields)==2:
            h['position']=int(fields[1])&255;code,text=0,'00, OK,00,00'
        elif verb in (b'U1',b'U2') and len(fields)==4:
            track,sector=int(fields[2]),int(fields[3])
            fault=self.sector_faults.get((device,verb,track,sector))
            if fault:code,text=fault
            elif (track,sector) not in disk:code,text=66,f'66,ILLEGAL TRACK OR SECTOR,{track:02d},{sector:02d}'
            elif verb==b'U2' and device in self.protected:code,text=26,f'26,WRITE PROTECT ON,{track:02d},{sector:02d}'
            else:
                if verb==b'U1':h['buffer'][:]=disk[track,sector]
                else:disk[track,sector][:]=h['buffer'];self.directory_written(device,track)
                h['position']=0;code,text=0,'00, OK,00,00'
        else:code,text=31,'31,SYNTAX ERROR,00,00'
        self.codes[device]=code;self.status_text[device]=(text+'\r').encode()

    def listing(self,device):
        """The "$" file a CBM drive sends: a BASIC program whose line numbers
        are block counts, ending with the BLOCKS FREE line."""
        capacity=(664,1328,3160)[self.formats.get(device,0)]
        used=0;lines=[(0,b'\x12"MODEL DISK      " 00 2A')]
        for (dev,name,kind),data in self.files.items():
            if dev!=device:continue
            blocks=max(1,(len(data)+253)//254);used+=blocks
            lines.append((blocks,b'   "'+name+b'"'+b' '*(17-len(name))+{b'S':b'SEQ',b'P':b'PRG',b'U':b'USR'}[kind]))
        lines.append((capacity-used,b'BLOCKS FREE.             '))
        out=bytearray(b'\x01\x04')
        for number,text in lines:
            out+=b'\x01\x01'+number.to_bytes(2,'little')+text+b'\0'
        return bytes(out+b'\0\0')

    def dos_command(self,device,command):
        """A DOS command sent as the name of an OPEN on secondary 15: CBM DOS
        scratch (locked files are skipped and the count says so), rename, format
        and the UI reset with its identity line."""
        self.events.append(('dos',device,command))
        if self.fail_command is not None:
            code,text=self.fail_command
        elif command.startswith(b'S0:') and len(command)>3:
            name=command[3:]
            keys=[k for k in self.files if k[0]==device and k[1]==name and k not in self.locked]
            for k in keys:del self.files[k]
            code,text=1,f'01, FILES SCRATCHED,{len(keys):02d},00'
        elif command.startswith(b'R0:') and b'=' in command[3:]:
            new,old=command[3:].split(b'=',1)
            found=[k for k in self.files if k[0]==device and k[1]==old]
            if any(k[0]==device and k[1]==new for k in self.files):code,text=63,'63,FILE EXISTS,00,00'
            elif not found:code,text=62,'62,FILE NOT FOUND,00,00'
            else:
                key=found[0];renamed=(device,new,key[2])  # keeps its directory slot
                self.files={renamed if k==key else k:v for k,v in self.files.items()}
                if key in self.locked:self.locked.discard(key);self.locked.add(renamed)
                code,text=0,'00, OK,00,00'
        elif command==b'UI':          # DOS reset: 73 and the ROM's name (VICE 1541/1571/1581 ROMs)
            code,text=73,self.identity.get(device,('73,CBM DOS V2.6 1541,00,00','73,CBM DOS V3.0 1571,00,00',
                                                  '73,COPYRIGHT CBM DOS V10 1581,00,00')[self.formats.get(device,0)])
        elif command.startswith(b'N0:') and b',' in command[3:]:
            for k in [k for k in self.files if k[0]==device]:   # a new, empty disk
                del self.files[k];self.locked.discard(k)
            code,text=0,'00, OK,00,00'
        else:
            code,text=31,'31,SYNTAX ERROR,00,00'
        self.codes[device]=code;self.status_text[device]=text.encode()+b'\r'

    def directory_written(self,device,track):
        """A written directory sector sets or clears its files' locks (type bit
        6), as the drive's listing then shows them."""
        if track!=(40 if self.formats.get(device,0)==2 else 18):return
        for (t,_),block in self.sectors.get(device,{}).items():
            if t!=track:continue
            for i in range(0,256,32):
                kind=block[i+2]
                if not kind&0x80 or not 1<=kind&7<=3:continue
                key=(device,bytes(block[i+5:i+21]).rstrip(b'\xa0'),b'SPU'[(kind&7)-1:kind&7])
                if key in self.files:(self.locked.add if kind&0x40 else self.locked.discard)(key)

    def disk_blocks(self,device):
        """Construct CBM sectors from files independently of the kernel parser."""
        fmt=self.formats.get(device,0);tracks=(35,70,80)[fmt]
        directory=40 if fmt==2 else 18;first=3 if fmt==2 else 1
        def sectors(track):
            if fmt==2:return 40
            side=(track-1)%35+1
            return 21 if side<=17 else 19 if side<=24 else 18 if side<=30 else 17
        available=iter((t,s) for t in range(1,tracks+1) for s in range(sectors(t))
                       if t!=directory and not (fmt==1 and t==53))
        blocks={};entries=[]
        for (dev,name,kind),data in self.files.items():
            if dev!=device:continue
            parts=[data[i:i+254] for i in range(0,len(data),254)] or [b'']
            chain=[next(available) for part in parts]
            for i,(address,part) in enumerate(zip(chain,parts)):
                link=chain[i+1] if i+1<len(chain) else (0,len(part)+1)
                blocks[address]=bytearray(bytes(link)+bytes(part).ljust(254,b'\0'))
            entry=bytearray(32);entry[2]=0x81+(b'S',b'P',b'U').index(kind)+(0x40 if (dev,name,kind) in self.locked else 0)
            entry[3:5]=bytes(chain[0]);entry[5:21]=name.ljust(16,b'\xa0')
            entry[30:32]=len(chain).to_bytes(2,'little');entries.append(entry)
        groups=[entries[i:i+8] for i in range(0,len(entries),8)] or [[]]
        for i,group in enumerate(groups):
            block=bytearray(b''.join(group).ljust(256,b'\0'))
            block[:2]=bytes((directory,first+i+1) if i+1<len(groups) else (0,255))
            blocks[directory,first+i]=block
        if self.edit_blocks:self.edit_blocks(blocks)
        return blocks

    def finish(self,cpu,carry=False):
        cpu.p=(cpu.p&~1)|int(carry);cpu.pc=(cpu.stPopWord()+1)&65535
        return True

    def flush(self):
        if self.pending is not None:
            h,value=self.pending;self.pending=None
            key=h['key'];at=len(self.files[key])
            if self.fail_flush or self.fail_write==at:self.status=1
            else:self.files[key].append(value);self.writes+=1

    def stub(self,cpu):
        pc=cpu.pc
        if pc==0xffc0:
            assert self.ram[0xc6:0xc8]==bytes(2)
            self.events.append(('open',self.lfn,self.device,self.sa,self.filename.hex()))
            self.status=0
            if self.fail_open==self.lfn:
                self.status=0x80;return self.finish(cpu,True)
            assert self.lfn not in self.handles,'overwrote another LFN'
            self.add(self.lfn,self.device,self.sa)
            h=self.handles[self.lfn]
            if self.sa==10:
                assert self.filename==b'#'
                self.blocks[self.device]=self.disk_blocks(self.device)
                self.codes[self.device]=0
            elif self.filename==b'#':                          # a buffer channel for U1/U2/B-P
                h.update(buffer=bytearray(256),position=0,key=None,mode=b'B',valid=True)
                self.codes[self.device]=0
            elif self.sa==15:
                if self.filename:self.dos_command(self.device,bytes(self.filename))
            elif 4<=self.device<=7:                          # a printer: OPEN sends nothing
                h.update(key=None,mode=b'P',valid=True,printer=True)
            elif self.sa==0 and self.filename==b'$':        # a directory listing
                h.update(data=self.listing(self.device),key=None,mode=b'R',valid=True)
                self.codes[self.device]=0
            else:
                name,kind,mode=self.filename.rsplit(b',',2)
                assert kind in (b'S',b'P',b'U') and mode in (b'R',b'W')
                key=(self.device,name,kind);h.update(key=key,mode=mode)
                if mode==b'W':
                    exists=any(d==self.device and n==name for d,n,k in self.files)
                    self.codes[self.device]=63 if exists else 0
                    if not exists:self.files[key]=bytearray()
                else:self.codes[self.device]=0 if key in self.files else 62
                h['valid']=self.codes[self.device]==0
            return self.finish(cpu)
        if pc==0xffc6:
            if cpu.x not in self.handles:return self.finish(cpu,True)
            self.selected=cpu.x;h=self.handles[cpu.x];self.status=0
            self.ram[0x99]=h['device']
            if h['sa']==15:
                code=self.codes.get(h['device'],0)
                h['data']=(self.bad_status if self.bad_status is not None else
                           self.status_text.pop(h['device'],None) or f'{code:02d}, STATUS,00,00\r'.encode())
                h['position']=0
            return self.finish(cpu)
        if pc==0xffc9:
            if cpu.x not in self.handles:return self.finish(cpu,True)
            h=self.handles[cpu.x]
            if h.get('printer') and h['device'] not in self.printers:
                self.status=0x80;cpu.a=5;return self.finish(cpu,True)   # DEVICE NOT PRESENT
            self.output=cpu.x;self.ram[0x9a]=h['device'];self.status=0
            return self.finish(cpu)
        if pc==0xffcf:
            assert self.selected in self.handles
            h=self.handles[self.selected];at=h['position'];self.reads+=1
            if 'buffer' in h:
                cpu.a=h['buffer'][at];h['position']=(at+1)&255
                self.status=0x40 if at==255 else 0
                return self.finish(cpu)
            data=h['data'] if h['sa'] in (0,10,15) else self.files.get(h['key'],b'')
            if h['sa'] not in (0,10,15) and self.short_eoi_quirk:
                if len(data)==0:data=bytes(254)
                elif len(data)==1:data=bytes(data)+b'\0\2'+bytes(data)
            if h['sa'] not in (10,15) and self.fail_read==at:cpu.a,self.status=0,2
            elif at>=len(data):cpu.a,self.status=0,2
            else:
                cpu.a=data[at];h['position']+=1
                self.status=0x40 if h['position']==len(data) else 0
                if h['sa']==15 and self.status:self.codes[h['device']]=0
            return self.finish(cpu)
        if pc==0xffd2 and self.output is not None:
            assert self.output in self.handles
            h=self.handles[self.output]
            if 'buffer' in h:
                h['buffer'][h['position']]=cpu.a;h['position']=(h['position']+1)&255
                return self.finish(cpu)
            if h.get('printer'):
                self.printers[h['device']].append(cpu.a);return self.finish(cpu)
            if h['sa']==15:
                self.command.append(cpu.a);return self.finish(cpu)
            assert h['valid'] and h['mode']==b'W'
            self.flush()
            if not self.status:self.pending=(h,cpu.a)
            return self.finish(cpu)
        if pc==0xffcc:
            if self.command:
                command=bytes(self.command);self.command.clear()
                dev=self.handles[self.output]['device']
                if not command.startswith(b'U1:10 0 '):
                    self.buffer_command(dev,command)
                    self.flush();self.output=self.selected=None
                    self.ram[0x99:0x9b]=b'\0\3'
                    return self.finish(cpu)
                _,_,track,sector=command.split()
                address=int(track),int(sector)
                self.events.append(('block-read',dev,*address))
                raw=self.blocks[dev].get(address)
                self.codes[dev]=20 if address==self.fail_block else 0 if raw is not None else 66
                h=next(h for h in self.handles.values() if h['device']==dev and h['sa']==10)
                h.update(data=raw or bytes(256),position=0)
            self.flush();self.output=self.selected=None
            self.ram[0x99:0x9b]=b'\0\3'
            return self.finish(cpu)
        if pc==0xffc3:
            self.events.append(('close',cpu.a))
            closing=self.handles.get(cpu.a)
            if closing and closing['sa']==15:
                assert not any(h['device']==closing['device'] and h['sa']!=15 for n,h in self.handles.items() if n!=cpu.a), 'CLOSE 15 would close another disk stream'
            self.flush();self.handles.pop(cpu.a,None);self.tables()
            self.status=1 if cpu.a==self.fail_close else 0
            return self.finish(cpu)
        return super().stub(cpu)


class Files:
    def __init__(self,files=None):
        self.m=Machine();self.ram=self.m.ram;self.io=StreamIEC(self.m,files)
        self.ram[OWNER]=32;self.calls=0;self.instructions=0
        self.ram[BUFFER:BUFFER+512]=b'\xa5'*512

    def word(self,addr,value=None):
        if value is not None:self.ram[addr:addr+2]=value.to_bytes(2,'little')
        return int.from_bytes(self.ram[addr:addr+2],'little')

    def handle(self):return bytes(self.ram[HANDLE:HANDLE+4])

    def call(self,entry,expected=0,flags=0,heap_unchanged=True,interrupt=None,max_steps=1000000):
        parameters=bytes(self.ram[0xb7:0xbd])+bytes(self.ram[0xc6:0xc8])+bytes([self.ram[0x9d]])
        heap=bytes(self.ram[0x3800:0x3a00])+bytes(self.ram[0x3c00:0x3d00])
        cpu=MPU(memory=self.m.bus,pc=entry);cpu.sp=0xe0;cpu.p=0x20|flags;cpu.stPushWord(0xaff)
        previous_error=self.ram[ERROR]
        for steps in range(max_steps):
            if cpu.pc==0xb00 and cpu.sp==0xe0:break
            if interrupt:interrupt(cpu,steps)
            if not self.io.stub(cpu):cpu.step()
        else:raise AssertionError(f'file operation did not return: {entry:04x}, PC={cpu.pc:04x}')
        self.calls+=1;self.instructions+=steps
        assert (cpu.a,cpu.p&1)==(expected,int(bool(expected))),(hex(entry),cpu.a,expected,hex(cpu.pc))
        assert cpu.p&12==flags&12 and cpu.sp==0xe0
        assert self.ram[ERROR]==(previous_error if expected==7 else expected)
        assert parameters==bytes(self.ram[0xb7:0xbd])+bytes(self.ram[0xc6:0xc8])+bytes([self.ram[0x9d]])
        if heap_unchanged:
            assert heap==bytes(self.ram[0x3800:0x3a00])+bytes(self.ram[0x3c00:0x3d00])
        assert self.m.bus.config==0x0e and not self.m.bus.io_writes
        return self.word(ACTUAL)

    def open(self,name=b'NOTE',device=8,mode=0,kind=0,owner=32,expected=0,flags=0,fmt=0):
        self.ram[OWNER]=owner;self.ram[DEVICE:TYPE+1]=bytes([device,len(name),mode,kind])
        self.ram[FORMAT]=fmt
        self.ram[NAME:NAME+len(name)]=name
        self.call(OPEN,expected,flags);return self.handle()

    def select(self,handle,owner=32):self.ram[HANDLE:HANDLE+4]=handle;self.ram[OWNER]=owner

    def read(self,count=512,expected=0):
        self.word(COUNT,count);n=self.call(READ,expected)
        return bytes(self.ram[BUFFER:BUFFER+n])

    def write(self,data,expected=0):
        self.ram[BUFFER:BUFFER+len(data)]=data;self.word(COUNT,len(data))
        return self.call(WRITE,expected)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path);args=parser.parse_args()
    report=dict(passed=False,kernel_sha256=hashlib.sha256(IMAGE.read_bytes()).hexdigest(),cases={})
    cases=report['cases']
    def done(name,f):cases[name]=dict(calls=f.calls,instructions=f.instructions,events=f.io.events)
    try:
        pattern=bytes((i*73+i//251)&255 for i in range(1557))
        f=Files({(8,b'NOTE',b'S'):pattern});f.io.add(6,9,2)
        h=f.open(flags=8)
        assert h==b'\1\1\0\0' and set(f.io.handles)=={6,122,124}
        actual=b''.join(f.read(n) for n in (1,255,256,512,512,512))
        assert actual==pattern and f.ram[EOF]==1
        old_reads=f.io.reads;assert f.read(512)==b'' and f.io.reads==old_reads
        assert int.from_bytes(f.ram[POSITION:POSITION+4],'little')==len(pattern)
        f.call(CLOSE);assert set(f.io.handles)=={6}
        f.call(READ,4);done('binary-read-eof-stale',f)

        f=Files({(8,b'NOTE',b'S'):pattern});src=f.open();dst=f.open(b'COPY',mode=1,owner=33)
        out=bytearray()
        while True:
            f.select(src);data=f.read(512);out+=data
            if data:f.select(dst,33);assert f.write(data)==len(data)
            if not data:break
        f.select(dst,33);f.call(CLOSE);f.select(src);f.call(CLOSE)
        assert bytes(f.io.files[8,b'COPY',b'S'])==pattern==out
        assert not f.io.handles and not f.io.pending
        f.open(b'COPY',mode=1,expected=0x11);assert f.ram[DOS]==63 and f.handle()==bytes(4)
        assert bytes(f.io.files[8,b'COPY',b'S'])==pattern
        done('two-owners-copy-exclusive',f)
        f=Files({(8,b'NOTE',b'P'):b'\1\x08original'})
        f.open(mode=1,expected=0x11);assert f.ram[DOS]==63
        assert set(f.io.files)=={(8,b'NOTE',b'P')};done('exclusive-name-across-types',f)

        f=Files();f.open(mode=1);f.io.codes[8]=72
        assert f.write(b'accepted')==8 and f.ram[DOS]==0
        f.call(CLOSE,0x11);assert f.ram[DOS]==72 and f.ram[RECORDS]==32
        assert f.ram[RECORDS+3]&4
        events=len(f.io.events);f.call(RELEASE,0x11);assert len(f.io.events)==events
        done('deferred-dos-error-at-close',f)

        f=Files({(8,b'NOTE',b'S'):b'x',(9,b'OTHER',b'P'):b'\1\x08abc'})
        h=f.open();other=f.open(b'OTHER',9,kind=1,owner=33)
        f.open(expected=3);f.select(other);f.call(READ,5)
        f.ram[OWNER]=32;f.call(RELEASE);assert set(f.io.handles)=={123,125}
        f.select(other,33);assert f.read(512)==b'\1\x08abc';f.call(CLOSE)
        new=f.open();assert new==b'\1\2\0\0';f.select(h);f.call(CLOSE,4)
        f.select(new);f.call(CLOSE);done('owner-release-generation',f)

        for size in (0,1,2,3,4,253,254,255,256,257,507,508,509,510):
            data=bytes((i*97)&255 for i in range(size))
            f=Files({(8,b'NOTE',b'S'):data});f.open()
            actual=bytearray()
            while not f.ram[EOF]:actual+=f.read(255)
            assert actual==data
            before=f.io.reads;assert f.read()==b'' and f.io.reads==before
            f.call(CLOSE);done(f'exact-extent-{size}',f)
        f=Files({(8,b'NOTE',b'S'):b'\0\0\2\0'});f.open()
        assert f.read()==b'\0\0\2\0';f.call(CLOSE);done('legitimate-link-like-data',f)
        for actual in (b'123456789',b'12345678901'):
            f=Files({(8,b'NOTE',b'S'):b'1234567890'});f.open()
            f.io.files[8,b'NOTE',b'S']=bytearray(actual)
            assert f.read(expected=0x11)==actual[:10] and not f.ram[EOF]
            assert f.ram[RECORDS+3]&2
            f.call(CLOSE);done(f'stream-extent-mismatch-{len(actual)}',f)

        for fmt,address in ((0,(35,16)),(1,(70,16)),(2,(80,39))):
            f=Files({(8,b'SIXTEEN-LETTERS!',b'U'):b'last track'})
            f.io.formats[8]=fmt
            def relocate(blocks,address=address,fmt=fmt):
                blocks[address]=blocks.pop((1,0))
                blocks[(40,3) if fmt==2 else (18,1)][3:5]=bytes(address)
            f.io.edit_blocks=relocate
            f.open(b'SIXTEEN-LETTERS!',kind=2,fmt=fmt)
            assert f.read()==b'last track';f.call(CLOSE);done(f'geometry-last-sector-{fmt}',f)
        many={(8,f'FILE{i:02d}'.encode(),b'S'):b'item' for i in range(17)}
        f=Files(many);f.open(b'FILE16');assert f.read()==b'item';f.call(CLOSE)
        done('multiple-directory-sectors',f)

        def edit_chain(blocks,offset,data):blocks[1,0][offset:offset+len(data)]=data
        def edit_entry(blocks,offset,data):blocks[18,1][offset:offset+len(data)]=data
        for label,mutate in [
            ('zero-final-length',lambda b:edit_chain(b,0,b'\0\0')),
            ('cycle',lambda b:edit_chain(b,0,b'\1\0')),
            ('zero-track',lambda b:edit_entry(b,3,b'\0')),
            ('track-high',lambda b:edit_entry(b,3,b'\x24')),
            ('sector-high',lambda b:edit_entry(b,4,b'\x15')),
            ('directory-data',lambda b:edit_entry(b,3,b'\x12\1')),
            ('blocks-zero',lambda b:edit_entry(b,30,b'\0\0')),
            ('blocks-excess',lambda b:edit_entry(b,30,b'\xac\2')),
            ('blocks-early-end',lambda b:edit_entry(b,30,b'\2\0'))]:
            f=Files({(8,b'NOTE',b'S'):b'x'});f.io.edit_blocks=mutate
            f.open(expected=9);assert f.handle()==bytes(4) and not f.io.handles
            done('corrupt-'+label,f)
        for label,mutate in [
            ('directory-cycle',lambda b:edit_entry(b,0,b'\x12\1')),
            ('directory-wrong-track',lambda b:edit_entry(b,0,b'\1\0')),
            ('directory-header',lambda b:edit_entry(b,0,b'\x12\0'))]:
            f=Files({(8,b'NOTE',b'S'):b'x'});f.io.edit_blocks=mutate
            f.open(b'ABSENT',expected=9);assert not f.io.handles
            assert sum(e[0]=='block-read' for e in f.io.events)<=18
            done('corrupt-'+label,f)
        f=Files({(8,b'NOTE',b'S'):b'x'});f.io.fail_block=(1,0)
        f.open(expected=0x11);assert f.ram[DOS]==20 and not f.io.handles
        done('metadata-disk-error',f)
        f=Files({(8,b'NOTE',b'S'):b'x'});f.io.fail_close=126
        f.open(expected=0x11);assert f.ram[RECORDS]==32 and f.ram[RECORDS+3]&4
        events=len(f.io.events);f.call(RELEASE,0x11);assert len(f.io.events)==events
        done('metadata-close-uncertain',f)

        for label,edit in [
            ('zero-owner',lambda f:f.ram.__setitem__(OWNER,0)),
            ('owner-255',lambda f:f.ram.__setitem__(OWNER,255)),
            ('device-low',lambda f:f.ram.__setitem__(DEVICE,7)),
            ('device-high',lambda f:f.ram.__setitem__(DEVICE,31)),
            ('mode',lambda f:f.ram.__setitem__(MODE,3)),
            ('type',lambda f:f.ram.__setitem__(TYPE,3)),
            ('format',lambda f:f.ram.__setitem__(FORMAT,3)),
            ('name-empty',lambda f:f.ram.__setitem__(NAMELEN,0)),
            ('name-long',lambda f:f.ram.__setitem__(NAMELEN,17))]:
            f=Files();f.ram[DEVICE:TYPE+1]=bytes([8,4,0,0]);f.ram[NAME:NAME+4]=b'NOTE'
            edit(f);f.call(OPEN,1);assert not f.io.events;done(label,f)
        for ch in b'*?,:/\\@#$\x1f\x7f':
            f=Files();f.open(bytes([ch]),expected=1);assert not f.io.events;done(f'name-{ch:02x}',f)

        for label,prepare in [
            ('foreign-lfn',lambda f:f.io.add(122,9,2)),
            ('foreign-data',lambda f:f.io.add(6,8,8)),
            ('foreign-same-device',lambda f:f.io.add(6,8,2)),
            ('foreign-command',lambda f:f.io.add(6,8,15)),
            ('command-lfn',lambda f:f.io.add(124,9,2)),
            ('metadata-lfn',lambda f:f.io.add(126,9,2)),
            ('table-count',lambda f:f.ram.__setitem__(0x98,255))]:
            f=Files();prepare(f);before=dict(f.io.handles);f.open(expected=0x15)
            assert f.io.handles==before and not f.io.events;done(label,f)

        for count in (0,513,65535):
            f=Files({(8,b'NOTE',b'S'):pattern});f.open();events=len(f.io.events)
            f.read(count,6);assert len(f.io.events)==events;done(f'count-{count}',f)
        f=Files({(8,b'NOTE',b'S'):pattern});f.open();f.io.fail_read=257
        assert f.read(512,0x11)==pattern[:257]
        events=len(f.io.events);assert f.read(1,0x11)==b'' and len(f.io.events)==events
        assert f.ram[STATUS]==0 and f.ram[RECORDS+7]==0x11
        f.io.fail_read=None;f.call(CLOSE);assert not f.io.handles;done('read-prefix-poison-close',f)

        f=Files();f.open(mode=1);f.io.fail_write=257
        f.write(pattern[:512],0x11);assert f.word(ACTUAL)==258
        assert bytes(f.io.files[8,b'NOTE',b'S'])==pattern[:257]
        events=len(f.io.events);f.write(b'x',0x11);assert len(f.io.events)==events
        f.io.fail_write=None;f.call(CLOSE);done('write-prefix-poison',f)

        f=Files();f.open(mode=1);f.io.fail_flush=True
        f.write(b'x',0x11);assert f.word(ACTUAL)==1 and f.io.files[8,b'NOTE',b'S']==b''
        f.io.fail_flush=False;f.call(CLOSE);done('deferred-final-byte-error',f)

        for lfn in (122,124):
            f=Files({(8,b'NOTE',b'S'):b'x'});f.open();f.io.fail_close=lfn
            f.call(CLOSE,0x11);assert f.ram[RECORDS]==32 and f.ram[RECORDS+3]&4
            events=len(f.io.events);f.io.fail_close=None;f.call(RELEASE,0x11)
            assert len(f.io.events)==events;done(f'uncertain-close-{lfn}',f)
        for lfn in (122,124,126):
            f=Files({(8,b'NOTE',b'S'):b'x'});f.io.fail_open=lfn;f.open(expected=0x11)
            assert not f.io.handles and f.handle()==bytes(4);done(f'open-fault-{lfn}',f)

        for reply in (b'7X, BAD\r',b'00X BAD\r',b'00, NO TERMINATOR',b'x'*41):
            f=Files({(8,b'NOTE',b'S'):b'x'});f.io.bad_status=reply;f.open(expected=0x11)
            assert not f.io.handles;done('status-'+reply.hex(),f)
        f=Files({(8,b'NOTE',b'S'):b'x'});f.open();f.open(owner=32)
        f.ram[RECORDS+16+12]=3;events=len(f.io.events);f.call(RELEASE,9)
        assert len(f.io.events)==events and set(f.io.handles)=={122,123,124}
        done('atomic-corrupt-release',f)

        f=Files({(8,b'NOTE',b'S'):b'x'});f.ram[RECORDS+4:RECORDS+7]=b'\xff\xff\xfe'
        h=f.open();assert h==b'\1\0\0\xff';f.call(CLOSE)
        f.ram[RECORDS+4:RECORDS+7]=b'\xfe\xff\xff';h=f.open();assert h==b'\1\xff\xff\xff'
        f.call(CLOSE);h=f.open();assert h[0]==2;f.call(CLOSE);done('generation-carry-retirement',f)
        f=Files({(8,b'NOTE',b'S'):pattern});f.open()
        f.ram[RECORDS+8:RECORDS+12]=b'\xff'*4;events=len(f.io.events)
        f.read(1,6);assert len(f.io.events)==events;done('position-overflow',f)
        f=Files();f.open(flags=4,expected=8);assert not f.io.events;done('interrupt-masked',f)
        f=Files();f.ram[BUSY]=1;f.ram[ERROR]=0x63;f.open(expected=7)
        assert not f.io.events and f.ram[BUSY]==1 and f.ram[ERROR]==0x63;done('busy',f)
        code=bytearray()
        for address,value in [(OWNER,32),(DEVICE,8),(NAMELEN,4),(MODE,0),(TYPE,0)]+[(NAME+i,v) for i,v in enumerate(b'NOTE')]:
            code+=bytes([0xa9,value,0x8d,address&255,address>>8])
        code+=bytes([0x20,OPEN&255,OPEN>>8,0xa9,42,0x4c,0x3e,0x1c])
        for label,failed,action,address in [
                ('app-auto-close',False,0,0x1c3e),('app-retains-close-error',True,0,0x1c3e),
                ('replace-closes-before-handoff',False,1,0x1c53),('replace-retains-close-error',True,1,0x1c53),
                ('workspace-closes-before-return',False,2,0x1c56),('workspace-retains-close-error',True,2,0x1c56)]:
            payload=bytearray(code);payload[-2:]=address.to_bytes(2,'little')
            app=bytearray(fixture(payload));app[8]=2;app=seal(app)
            f=Files({(8,b'CHECK',b'P'):app,(8,b'NOTE',b'S'):b'owned',
                     (9,b'OTHER',b'S'):b'foreign'})
            other=f.open(b'OTHER',device=9,owner=33)
            f.ram[0x3d21:0x3d23]=bytes([8,5]);f.ram[0x3d40:0x3d45]=b'CHECK'
            def app_close_fault(cpu,steps):
                if failed and cpu.pc==0x6020:f.io.fail_close=123
            f.call(0x1c38,expected=0x11 if failed else 0,heap_unchanged=False,interrupt=app_close_fault)
            assert f.ram[0x3d24]==(42 if action==0 else 0) and f.ram[0x3d28]==action
            assert f.ram[0x3d20]==(32 if failed else 0) and f.ram[0x3d23]==(4 if failed else 0)
            assert f.ram[RECORDS]==33 and f.ram[RECORDS+16]==(32 if failed else 0)
            assert f.m.stats()==((159,251,31) if failed else (175,251,32))
            f.io.fail_close=None;f.select(other,33);assert f.read()==b'foreign';f.call(CLOSE)
            done(label,f)
        report['passed']=True
        print(f'PASS: {len(cases)} native stream/ownership/fault cases',flush=True)
    except BaseException as error:report['error']=str(error);raise
    finally:
        if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
