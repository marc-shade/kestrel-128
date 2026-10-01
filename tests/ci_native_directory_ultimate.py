#!/usr/bin/env python3
"""Execute owned native directory cursors against the UCI packet/DOS model."""
import argparse
import hashlib
import json
from pathlib import Path
import posixpath

from ci_native_ultimate import Client as FileClient, DOSFiles
from ci_native_files import OWNER,HANDLE,RECORDS,BUFFER,COUNT,ACTUAL,EOF,DOS,STATUS,POSITION,FORMAT,BUSY,READ,WRITE,CLOSE,RELEASE
from ci_native_heap import IMAGE,symbol


class DirectoryDOS(DOSFiles):
    def __init__(self,entries=None,files=None):
        super().__init__(files)
        self.directories={b'/':[],b'/shell':[],b'/browser':[],b'/Usb0':list(entries or [])}
        self.snapshots={1:None,2:None}
        self.ignore_abort=False
        self.cancel_attempts=0
        self.trailing_paths=False

    def __setitem__(self,address,value):
        if address==0xdf1c and value==4:
            self.cancel_attempts+=1
            if self.ignore_abort:return
        super().__setitem__(address,value)

    def respond(self,command):
        target,op=command[:2]
        if op==0x12:
            path=self.paths[target]
            if self.trailing_paths and path!=b'/':path=path.rstrip(b'/')+b'/'
            return [(path,b'00,OK')]
        if op==0x11:
            path=posixpath.normpath(command[2:])
            if path not in self.directories:return [(b'',b'71,NO DIRECTORY')]
            self.paths[target]=path
            return [(b'',b'00,OK')]
        if op==0x13:
            self.snapshots[target]=list(self.directories[self.paths[target]])
            return [(b'',b'00,OK' if self.snapshots[target] else b'01,DIRECTORY EMPTY')]
        if op==0x14:
            entries=self.snapshots[target]
            assert entries,'READ_DIR without a nonempty snapshot'
            return [(entry,b'00,OK' if i==len(entries)-1 else b'') for i,entry in enumerate(entries)]
        reply=super().respond(command)
        if op==2 and command[2]==7 and reply==[(b'',b'00,OK')]:
            parent,leaf=posixpath.split(command[3:])
            entries=self.directories.get(parent)
            if entries is not None and all(entry[1:]!=leaf for entry in entries):
                entries.append(b'\x20'+leaf)
                entries.sort(key=lambda entry:(not bool(entry[0]&0x10),entry[1:].upper()))
        return reply


class Client(FileClient):
    def __init__(self,entries=None,files=None,iec=None):
        super().__init__(files,iec)
        self.ultimate=DirectoryDOS(entries,files)
        self.m.bus.dos=self.ultimate

    def directory(self,path=b'/Usb0',device=1,expected=0,**kwargs):
        self.ram[HANDLE:HANDLE+4]=bytes(4)
        return self.open_u(path,mode=2,device=device,expected=expected,**kwargs)

    def clean(self):
        super().clean()
        assert not self.ram[symbol('nd_slot')] and not self.ram[symbol('nd_active')]
        assert self.ultimate.state==0


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path);args=parser.parse_args()
    report=dict(passed=False,kernel_sha256=hashlib.sha256(IMAGE.read_bytes()).hexdigest(),cases={})
    cases=report['cases']
    def done(label,c):
        cases[label]=dict(calls=c.calls,instructions=c.instructions,
            commands=[cmd.hex() for cmd in c.ultimate.commands],aborts=c.ultimate.cancel_attempts)
    try:
        for count in (0,1,300):
            entries=[bytes([0x10 if i%7==0 else 0x20])+f'FILE {i:04d}'.encode() for i in range(count)]
            c=Client(entries);c.directory();got=[]
            while not c.ram[EOF]:
                got.append(c.read_u())
                assert int.from_bytes(c.ram[POSITION:POSITION+4],'little')==len(got)
            assert got==entries and c.ultimate.paths=={1:b'/Usb0',2:b'/browser'}
            sent=len(c.ultimate.commands);assert c.read_u()==b'' and len(c.ultimate.commands)==sent
            assert sum(cmd[1]==0x14 for cmd in c.ultimate.commands)==int(count>0)
            assert not c.ultimate.discarded;c.clean();done('entries-'+str(count),c)

        c=Client([b'\x20'+b'Q"'*127+b'Z',b'\x10'+bytes([0x80,0xa0,0xff])+b' NAME'])
        c.directory(device=2);assert len(c.read_u())==256
        assert c.read_u()==b'\x10'+bytes([0x80,0xa0,0xff])+b' NAME'
        assert c.ram[EOF];c.clean();done('full-name-second-context',c)

        c=Client([b'\x20FIRST',b'\x20SECOND'])
        original=b'/'+b'A'*254;target=b'/'+b'B'*254
        c.ultimate.paths[1]=original;c.ultimate.directories[original]=[]
        c.ultimate.directories[target]=c.ultimate.directories[b'/Usb0']
        c.directory(target);assert c.read_u()==b'\x20FIRST';c.call(CLOSE)
        assert c.ultimate.paths[1]==original and c.ultimate.cancel_attempts==1
        assert not c.ram[symbol('nd_slot')];done('255-byte-original-and-target-paths',c)

        for target,canonical in ((b'/Usb0//./',b'/Usb0'),(b'/Usb0/..',b'/')):
            c=Client([b'\x20ONE']);c.directory(target)
            assert bytes(c.ram[0x4e00:0x4e00+c.ram[0x3d86]])==canonical
            assert c.ultimate.paths[1]==canonical;c.clean();done('canonical-'+target.decode(),c)

        for consumed in (0,1,2):
            c=Client([b'\x20ONE',b'\x20TWO']);old=c.directory()
            for _ in range(consumed):c.read_u()
            c.call(CLOSE);assert c.ultimate.cancel_attempts==int(consumed==1)
            new=c.directory();assert old!=new
            before=len(c.ultimate.commands);c.select(old);c.call(CLOSE,4)
            assert len(c.ultimate.commands)==before
            c.select(new);c.clean();done('close-and-stale-'+str(consumed),c)

        c=Client([b'\x20ONE',b'\x20TWO'],{b'/kept':b'KEEP'})
        other=c.open_u(b'/kept',device=2);cursor=c.directory()
        assert cursor[0]==2 and c.read_u()==b'\x20ONE'
        records=bytes(c.ram[RECORDS:RECORDS+32]);before=len(c.ultimate.commands)
        c.select(other);c.read_u(expected=0x15);c.call(CLOSE,0x15)
        assert bytes(c.ram[RECORDS:RECORDS+32])==records and len(c.ultimate.commands)==before
        c.select(cursor);c.call(RELEASE)
        assert c.ultimate.handles[2] is None and c.ultimate.cancel_attempts==1
        assert [cmd[1] for cmd in c.ultimate.commands[-3:]]==[0x11,0x12,3]
        c.clean();done('release-directory-before-other-context-file',c)

        c=Client([b'\x20ONE',b'\x20TWO'],iec={(8,b'NOTE',b'S'):b'IEC STILL WORKS'})
        cursor=c.directory();assert c.read_u()==b'\x20ONE'
        iec=c.open(owner=33);assert c.read()==b'IEC STILL WORKS';c.call(CLOSE)
        c.select(cursor);assert c.read_u()==b'\x20TWO';c.clean();done('iec-during-directory-stream',c)

        c=Client([b'\x20ONE']);cursor=c.directory()
        before=len(c.ultimate.commands);c.directory(device=2,expected=0x15)
        c.select(cursor,33);c.read_u(expected=5);c.call(CLOSE,5)
        assert len(c.ultimate.commands)==before
        c.select(cursor);c.clean();done('one-cursor-and-owner-checks',c)
        c=Client(files={b'/foreign':b'PRESERVED'})
        c.ultimate.handles[1]=dict(name=b'/foreign',mode=1,pos=3)
        c.directory(expected=0x15)
        assert [cmd[1] for cmd in c.ultimate.commands]==[7]
        assert c.ultimate.handles[1]['pos']==3 and not c.ultimate.cancel_attempts
        done('foreign-file-preserved',c)
        c=Client();c.ultimate.state=0x10;c.ultimate.stuck=True
        c.directory(expected=0x15);assert not c.ultimate.commands and not c.ultimate.cancel_attempts
        done('foreign-transaction-preserved',c)

        for original in (b'',b'not-absolute',b'/NUL\0PATH',b'/'+b'A'*255):
            c=Client();c.ultimate.paths[1]=original;c.directory(expected=0x11)
            assert not c.handle()[0] and not c.ram[symbol('nd_slot')]
            assert all(cmd[1] in (7,0x12) for cmd in c.ultimate.commands)
            done('reject-original-'+original.hex(),c)
        for op in (0x11,0x13):
            c=Client([b'\x20ONE']);c.ultimate.inject[op]=lambda cmd,reply:[(b'',b'71,DIRECTORY ERROR')]
            c.directory(expected=0x11);assert c.handle()[0] and c.ram[symbol('nd_slot')]
            del c.ultimate.inject[op];c.clean();done('open-failure-owned-'+str(op),c)

        packets=[[(b'',b'00,OK')],[(b'\x20',b'00,OK')],[(b'\x20A\0B',b'00,OK')],
                 [(b'\x20A/B',b'00,OK')],[(b'\x20A\\B',b'00,OK')],[(b'\x20'+b'A'*256,b'00,OK')],
                 [(bytes(513),b'00,OK')],[(b'\x20ONE',b'')],[(b'\x20ONE',b'71,READ ERROR')],
                 [(b'\x20ONE',b'71,READ ERROR'),(b'\x20TWO',b'00,OK')]]
        for index,reply in enumerate(packets):
            c=Client([b'\x20ONE']);c.directory()
            c.ultimate.inject[0x14]=lambda cmd,wanted,reply=reply:reply
            assert c.read_u(expected=0x11)==b'' and not c.ram[EOF]
            before=len(c.ultimate.commands);c.read_u(expected=0x11)
            assert len(c.ultimate.commands)==before
            c.clean();done('malformed-or-failed-packet-'+str(index),c)

        c=Client([b'\x20ONE',b'\x20TWO']);c.directory();c.read_u()
        c.ultimate.ignore_abort=True;c.call(CLOSE,0x11,max_steps=6000000)
        assert c.ram[symbol('nd_active')]==1 and c.ram[symbol('nd_slot')]
        assert c.ultimate.paths[1]==b'/Usb0'
        c.ultimate.ignore_abort=False;c.clean();assert c.ultimate.cancel_attempts==2
        done('unconfirmed-abort-retains-owner',c)

        c=Client([b'\x20ONE']);c.directory()
        c.ultimate.inject[0x12]=lambda cmd,reply:[(b'/wrong',b'00,OK')]
        c.call(CLOSE,0x11);assert c.ram[symbol('nd_slot')] and c.ram[STATUS]==0xfc
        del c.ultimate.inject[0x12];c.clean();done('restore-readback-mismatch-retains-owner',c)
        c=Client([b'\x20ONE',b'\x20TWO']);c.directory();c.read_u()
        c.ultimate.present=False;c.call(CLOSE,0x11)
        assert c.ram[STATUS]==0xfe and c.ram[symbol('nd_active')]
        c.ultimate.present=True;c.clean();done('absent-during-cancel',c)

        c=Client([b'\x20ONE',b'\x20TWO']);c.directory()
        c.read_u(count=256,expected=6);c.write_u(b'X',expected=1)
        c.ram[POSITION:POSITION+4]=bytes(4)
        c.ram[RECORDS+8:RECORDS+12]=b'\xfe\xff\xff\xff'
        assert c.read_u()==b'\x20ONE'
        before=len(c.ultimate.commands);c.read_u(expected=6)
        assert len(c.ultimate.commands)==before;c.clean();done('count-mode-and-position-bounds',c)

        c=Client([b'\x20ONE']);attempts=[]
        def irq(cpu,steps):
            if steps%101==0 and not cpu.p&4:cpu.irq();attempts.append(steps)
        zero=bytes(c.ram[:256]);c.directory(flags=8,interrupt=irq)
        assert c.read_u(flags=8,interrupt=irq)==b'\x20ONE'
        assert bytes(c.ram[:256])==zero and attempts
        c.ram[BUSY]=1;c.call(READ,7);c.ram[BUSY]=0;c.clean();done('decimal-irqs-and-reentry',c)
        c=Client();c.directory(flags=4,expected=8);assert not c.ultimate.commands
        c.ram[FORMAT]=3;c.call(0x1c50,1);assert not c.ultimate.commands
        done('masked-call-and-iec-page-api',c)

        report['passed']=True
        print(f'PASS: {len(cases)} owned Ultimate directory cases; complete names, cursor packets, CWD restoration and cleanup',flush=True)
    except BaseException as error:report['error']=str(error);raise
    finally:
        if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
