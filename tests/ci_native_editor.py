#!/usr/bin/env python3
"""Exercise the real native editor, banked documents, screens and stored bytes."""
import argparse
import hashlib
import json
from pathlib import Path

from ci_native_calc import Calculator,ROOT
from ci_native_document import Document
from native_editor_check import editor_screen,document_lines


class Editor(Calculator):
    instruction_limit=150000000
    allow_busy_poll=True

    def __init__(self,files=None,device=8,fmt=0,**source):
        self.reverse=[False,False]
        self.original_keys=bytes(range(1,11))+bytes((i*73+19)&255 for i in range(246))
        self.seeded_keys=False
        super().__init__('editor',files,loader_name=b'EDITOR',device=device,fmt=fmt,**source)
        self.symbols={'d_states':self.symbol('d_states')}
        assert self.ram[0x1000:0x1014]==bytes([1]*10)+bytes.fromhex('8589868a878b888c8384')
        assert self.ram[self.symbol('ed_saved_keys'):self.symbol('ed_saved_keys')+256]==self.original_keys
        assert self.ram[0xd1:0xd3]==bytes(2)

    def loop(self,exited=False):
        if not self.seeded_keys:
            self.ram[0x1000:0x1100]=self.original_keys
            self.seeded_keys=True
        super().loop(exited)

    def output(self,value):
        bank=self.ram[0xd7]>>7;columns=(40,80)[bank]
        assert self.ram[0xf4]==0,'literal text or reverse control emitted in ROM quote mode'
        if value in (0x12,0x92):self.reverse[bank]=value==0x12;return
        if value==0x93:self.reverse[bank]=False
        if 32<=value<128:
            before=self.row[bank]*columns+self.col[bank]
            super().output(value)
            if self.reverse[bank]:self.screens[bank][before]|=128
        else:super().output(value)
        if value==34:self.ram[0xf4]=1

    def state(self,slot=None):
        return Document.state(self,self.value('ed_active') if slot is None else slot)

    def contents(self):return Document.bytes(self,self.value('ed_active'))

    def number(self,name,size=3):
        at=self.symbol(name);return int.from_bytes(self.ram[at:at+size],'little')

    def string(self,name):
        at=self.symbol(name);return bytes(self.ram[at:at+256]).split(b'\0')[0].decode('latin1')

    def check(self,want,cursor=None,dirty=None,status=None,name=None,mode=None,released=True):
        assert self.contents()==want
        actual=self.number('ed_cursor')
        if cursor is not None:assert actual==cursor,(actual,cursor)
        if dirty is not None:assert self.state()['dirty']==int(dirty)
        if status is not None:assert self.value('ed_status')==status,(self.value('ed_status'),status)
        if name is not None:assert self.string('ed_name')==name
        if mode is not None:assert self.value('ed_mode')==mode
        view=self.number('ed_view');horizontal=self.number('ed_horizontal')
        for bank,columns in enumerate((40,80)):
            expected=editor_screen(columns,want,actual,name=self.string('ed_name'),dirty=bool(self.state()['dirty']),
                                   device=self.value('ed_device'),fmt=self.value('ed_format'),view=view,horizontal=horizontal,
                                   mode=self.value('ed_mode'),field=self.string('ed_field'),status=self.value('ed_status'),
                                   field_caret=self.value('ed_field_cursor'),field_view=self.ram[self.symbol('ed_field_views')+bank],
                                   search_case=self.value('ed_s_pending_case'),replacements=self.number('ed_s_count'))
            if self.screens[bank]!=expected:
                rows=[(row,bytes(self.screens[bank][row*columns:(row+1)*columns]).hex(),
                       expected[row*columns:(row+1)*columns].hex()) for row in range(25)
                      if self.screens[bank][row*columns:(row+1)*columns]!=expected[row*columns:(row+1)*columns]]
                raise AssertionError(('editor screen',bank,rows[:3]))
        if released:assert not self.io.handles and self.ram[0x3de0:0x3de4]==bytes(4)

    def prompt(self,key,name,confirm=None):
        self.key(key);self.type(name);self.key(13)
        if confirm is not None:self.type(confirm)

    def exit(self,dirty=False):
        self.key(27,exited=not dirty)
        if dirty:self.key(ord('Y'),exited=True)
        assert self.ram[0x1000:0x1100]==self.original_keys
        assert self.ram[0xd1:0xd3]==bytes(2)

    def cancel_transfer(self,key,name):
        self.key(key);self.type(name)
        self.observation_target=self.events+2;self.observation_done=False
        self.keys.extend([13,27]);observed=[];original=self.io.stub
        def observe(cpu):
            if cpu.pc==0xffe4 and self.keys==[27]:
                assert self.ram[0x3d12]==0
                observed.append(dict(phase=self.value('ed_io_phase'),bytes=self.number('ed_io_pos')))
            return original(cpu)
        self.io.stub=observe
        try:self.loop()
        finally:self.io.stub=original
        self.events+=2
        assert self.observation_done and int.from_bytes(self.ram[0x3d13:0x3d15],'little')==self.events
        assert len(observed)==1 and observed[0]['bytes']==512,observed

    def quarantine_exit(self):
        """A failed CLOSE must reserve its owner, including the document RAM."""
        self.key(27);self.check(self.contents(),mode=5,released=False)
        before=self.m.stats();self.keys.append(ord('Y'));cpu=self.cpu
        for steps in range(100000):
            if cpu.pc==0xb00 and cpu.sp==0xe0:break
            if self.io.stub(cpu):continue
            if cpu.pc==0xffe4:
                assert self.keys
                cpu.a=self.keys.pop(0);cpu.FlagsNZ(cpu.a);cpu.pc=(cpu.stPopWord()+1)&65535
            else:cpu.step()
        else:raise AssertionError('quarantined editor exit did not return')
        self.events+=1;self.instructions+=steps
        assert self.ram[0x3d20]==32 and self.ram[0x3d23]==4 and self.ram[0x3d27]==0x11
        assert self.m.stats()==before and self.ram[0x1000:0x1100]==self.original_keys
        assert int.from_bytes(self.ram[0x3d13:0x3d15],'little')==self.events


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path);parser.add_argument('--quick',action='store_true');args=parser.parse_args()
    report=dict(passed=False,images={name:hashlib.sha256((ROOT/'target/native'/name).read_bytes()).hexdigest()
                                   for name in ('kestrel.prg','editor.prg')},cases={})
    def done(name,e):
        report['cases'][name]=dict(events=e.events,instructions=e.instructions,stored_files=len(e.io.files))
        print('PASS: native editor '+name,flush=True)
    try:
        e=Editor();e.check(b'',0,False)
        e.type('ONE\rTWO');want=b'ONE\rTWO';e.check(want,7,True)
        e.key(0x91);e.check(want,3,True)
        e.key(0x11);e.check(want,7,True)
        e.key(0x13);e.check(want,4)
        e.key(0x9d);e.check(want,3)
        e.key(0x1d);e.check(want,4)
        e.key(20);want=b'ONETWO';e.check(want,3)
        e.key(0x89);e.type('START ');want=b'START ONETWO';e.check(want,6)
        e.key(0x8a);e.type(' END');want+=b' END';e.check(want,len(want))
        e.key(27);e.check(want,mode=5);e.key(ord('N'));e.check(want,mode=0)
        e.prompt(0x88,'FFFFFF');e.check(want,status=4,mode=3);e.key(27)
        e.prompt(0x88,'000002');e.check(want,2,True,mode=0)
        e.exit(dirty=True);done('typing-insert-delete-cursor-prompts-and-dirty-exit',e)

        raw=b'ONE\r\nTWO\nTHREE\r'+bytes([0,255])+b' "QUOTED" END'
        e=Editor({(8,b'SOURCE',b'S'):raw,(8,b'EMPTY',b'S'):b''})
        e.prompt(0x85,'SOURCE');e.check(raw,0,False,name='SOURCE')
        assert e.value('ed_newline')==2
        e.key(5);e.check(raw,3)
        e.key(0x1d);e.check(raw,5)
        e.key(0x9d);e.check(raw,3)
        e.prompt(0x88,'000004');e.check(raw,5)
        e.key(13);want=raw[:5]+b'\r\n'+raw[5:];e.check(want,7,True)
        e.prompt(0x86,'COPY');e.check(want,7,False,status=1,name='COPY')
        assert bytes(e.io.files[8,b'COPY',b'S'])==want
        e.type('!');want=want[:7]+b'!'+want[7:];e.check(want,8,True)
        e.prompt(0x86,'COPY');e.check(want,8,True,status=6,name='COPY')
        assert bytes(e.io.files[8,b'COPY',b'S'])==raw[:5]+b'\r\n'+raw[5:]
        e.prompt(0x85,'MISSING');e.check(want,mode=5);e.type('Y');e.check(want,8,True,status=2,name='COPY')
        e.io.fail_flush=True;e.prompt(0x86,'PARTIAL');e.check(want,8,True,status=7)
        e.io.fail_flush=False
        original=e.io.stub;changed=False
        def corrupt_reopen(cpu):
            nonlocal changed
            if cpu.pc==0xffc0 and e.io.filename==b'BADVERIFY,S,R' and not changed:
                e.io.files[8,b'BADVERIFY',b'S'][-1]^=1;changed=True
            return original(cpu)
        e.io.stub=corrupt_reopen;e.prompt(0x86,'BADVERIFY')
        assert changed;e.check(want,8,True,status=7)
        e.io.stub=original
        e.prompt(0x85,'EMPTY',confirm='Y');e.check(b'',0,False,name='EMPTY')
        e.prompt(0x86,'EMPTYCOPY');e.check(b'',0,False,status=1,name='EMPTYCOPY')
        assert bytes(e.io.files[8,b'EMPTYCOPY',b'S'])==b''
        e.exit();done('mixed-line-endings-empty-files-transactional-open-and-verified-save',e)

        raw=b'"'+b'X'*110+b'"\r\n'+b'SHORT\r\n'+b'Y'*90+b'\r\n'+b'LINE\n'*25
        e=Editor({(8,b'LONG',b'S'):raw,(8,b'CHUNKS',b'S'):b'Z'*1557})
        e.prompt(0x85,'LONG');e.check(raw,0,False,name='LONG')
        e.prompt(0x88,'000050');e.check(raw,80);assert e.number('ed_horizontal')>0
        e.key(0x11);e.check(raw,119)
        e.key(0x11);e.check(raw,201)
        e.key(0x91);e.check(raw,119)
        e.key(0x91);e.check(raw,80)
        e.key(0x8a);e.check(raw,len(raw));assert e.number('ed_view')>0
        e.key(0x89);e.check(raw,0);assert e.number('ed_view')==0
        e.cancel_transfer(0x85,'CHUNKS');e.check(raw,0,False,status=8,name='LONG')
        assert not e.state(e.value('ed_active')^128)['chunks']
        e.io.fail_read=700;e.prompt(0x85,'CHUNKS');e.check(raw,0,False,status=2,name='LONG')
        e.io.fail_read=None
        e.prompt(0x85,'CHUNKS');e.type('!');want=b'!'+b'Z'*1557
        e.cancel_transfer(0x86,'CANCELLED');e.check(want,1,True,status=10,name='CHUNKS')
        assert bytes(e.io.files[8,b'CANCELLED',b'S'])==want[:512]
        e.prompt(0x86,'RECOVER');e.check(want,1,False,status=1,name='RECOVER')
        assert bytes(e.io.files[8,b'RECOVER',b'S'])==want
        e.exit();done('quoted-long-lines-viewport-retained-column-cancellation-and-read-failure',e)

        for lfn in (122,124):
            e=Editor({(8,b'SOURCE',b'S'):b'ORIGINAL',(8,b'EMPTY',b'S'):b''})
            e.prompt(0x85,'SOURCE');e.type('!');want=b'!ORIGINAL'
            e.io.fail_close=lfn;e.prompt(0x86,'CLOSEFAIL')
            e.check(want,1,True,name='SOURCE',status=9,released=False)
            assert e.ram[0x3dc0]==32 and e.ram[0x3dc3]&4
            assert bytes(e.io.files[8,b'CLOSEFAIL',b'S'])==want
            prior=len(e.io.events);e.io.fail_close=None
            e.prompt(0x85,'EMPTY',confirm='Y');e.check(want,1,True,name='SOURCE',status=9,released=False)
            assert len(e.io.events)==prior,'uncertain CLOSE was retried or new file I/O was attempted'
            e.quarantine_exit();assert e.contents()==want
            done(f'uncertain-close-{lfn}-retains-document-and-quarantines-owner',e)

        for fmt,newline in ((0,b'\r'),(1,b'\n'),(2,b'\r\n')):
            raw=b'X'*511+newline+b'NEXT'
            e=Editor({(9,b'EDGE',b'S'):raw},device=9,fmt=fmt)
            e.prompt(0x85,'EDGE');e.check(raw,0,False,name='EDGE')
            assert e.value('ed_newline')==(0 if newline==b'\r' else 1 if newline==b'\n' else 2)
            e.key(0x8a);e.key(13);want=raw+newline;e.check(want,len(want),True)
            e.prompt(0x86,'EDGEOUT');e.check(want,len(want),False,status=1)
            assert bytes(e.io.files[9,b'EDGEOUT',b'S'])==want
            e.prompt(0x8c,'31');e.check(want,status=4,mode=4);e.key(27)
            e.prompt(0x8c,'10');assert e.ram[0x3d29]==10
            e.key(0x8b);assert e.ram[0x3d2a]==(fmt+1)%4
            e.exit();done(f'device-9-format-{fmt}-newline-across-transfer-boundary',e)

        if not args.quick:
            raw=(b'0123456789 ABCDEFGHIJKLMNOPQRSTUVWXYZ\r\n'*1800)[:66053]
            e=Editor({(9,b'LARGE',b'S'):raw,(9,b'ANOTHER',b'S'):raw},device=9,fmt=2)
            e.prompt(0x85,'LARGE');e.check(raw,0,False,name='LARGE');assert e.banks=={0,1}
            e.prompt(0x88,'010001');at=e.number('ed_cursor');assert at>=65536
            e.type('C128');want=raw[:at]+b'C128'+raw[at:];e.check(want,at+4,True)
            e.key(20);want=want[:at+3]+want[at+4:];e.check(want,at+3,True)
            e.prompt(0x85,'ANOTHER',confirm='Y');e.check(want,at+3,True,status=3,name='LARGE')
            assert not e.state(e.value('ed_active')^128)['chunks']
            e.prompt(0x86,'LARGEOUT');e.check(want,at+3,False,status=1,name='LARGEOUT')
            assert bytes(e.io.files[9,b'LARGEOUT',b'S'])==want
            e.key(0x87);e.check(b'',0,False,name='')
            e.prompt(0x85,'LARGEOUT');e.check(want,0,False,name='LARGEOUT')
            report['large_saved_bytes']=len(want);report['large_saved_sha256']=hashlib.sha256(want).hexdigest()
            e.exit();done('over-64-KiB-edit-oom-retains-document-save-close-and-reopen',e)
        report.update(passed=True,quick=args.quick)
        print('PASS: native editor application, complete dual screens, document ownership and stored-byte verification',flush=True)
    except BaseException as error:report['error']=str(error);raise
    finally:
        if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
