#!/usr/bin/env python3
"""Execute native suite Files copy against IEC and Ultimate packet models."""
import argparse
import hashlib
import json
from pathlib import Path

from ci_native_calc import Calculator,ROOT
from ci_native_heap import IMAGE as KERNEL_IMAGE
from ci_native_browser import expected
from ci_native_directory_ultimate import DirectoryDOS
from ci_native_ultimate import UltimateBus
from native_browser_check import browser_screen,ultimate_browser_screen
from native_files_copy_check import copy_screen
from native_picker_scene import console as picker_console


class CopyFiles(Calculator):
    instruction_limit=120000000
    allow_busy_poll=True

    def __init__(self,files=None,device=9,fmt=0,*,usb=None,directories=None,source_path=None,source_context=1,vdc_component=True):
        super().__init__('files',files,loader_name=b'FILES',device=device,fmt=fmt,image_prefix='native-desktop',
            ultimate_files=usb if source_path is not None else None,source_path=source_path,source_context=source_context,
            vdc_component=vdc_component)
        self.frames=0
        if usb is not None or directories is not None or source_path is not None:
            previous=getattr(self,'ultimate',None)
            self.loaded_source_commands=list(previous.commands) if previous is not None else []
            self.ultimate=DirectoryDOS(files=previous.files if previous is not None else usb)
            self.ultimate.fragment=103
            self.ultimate.direct_write_corruption=True
            self.ultimate.directories.update(directories or {})
            if isinstance(self.m.bus,UltimateBus):self.m.bus.dos=self.ultimate
            else:self.m.bus=UltimateBus(self.m.bus,self.ultimate)
            self.cpu.memory=self.m.bus

    def number(self,name,size=4):
        at=self.symbol(name);return int.from_bytes(self.ram[at:at+size],'little')

    def data(self,name,length):
        at=self.symbol(name);return bytes(self.ram[at:at+length])

    def name(self):return self.data('fc_name',self.value('fc_length'))

    def preferences(self):
        return (bytes(self.ram[0x3d29:0x3d35]),bytes(self.ram[0x4a00:0x4b00]),bytes(self.ram[0x3e00:0x3f00]))

    def check(self,source,name,**kwargs):
        assert self.value('fc_active') and not self.value('fc_picker_active')
        assert self.name()==name
        assert self.data('fc_source',self.value('fc_source_length'))==source
        for bank,columns in enumerate((40,80)):
            want=copy_screen(columns,source,name,caret=self.value('fc_caret'),
                view=self.ram[self.symbol('fc_views')+bank],**kwargs)
            assert self.screens[bank]==want,('copy screen',columns,
                [(i,a,b) for i,(a,b) in enumerate(zip(self.screens[bank],want)) if a!=b][:16])
            self.frames+=1
        assert self.number('fc_copied')==kwargs.get('copied',0)
        assert self.number('fc_verified')==kwargs.get('verified',0)
        assert self.value('fc_status')==kwargs.get('status',0)

    def clean(self):
        assert not self.io.handles
        assert self.data('fc_handles',1)==b'\0' and self.data('fc_handles',8)[4]==0
        if self.value('fg_kind')==2:
            assert not self.value('fc_picker_cursor') and not self.value('fc_picker_iec_handle')
            assert self.data('fc_picker_cache',40)[::4]==bytes(10)
        if hasattr(self,'ultimate'):
            assert self.ultimate.handles=={1:None,2:None}
            assert self.ultimate.paths=={1:b'/shell',2:b'/browser'} and self.ultimate.state==0

    def rename(self,name):self.key(21);self.type(name)

    def destination(self,device):self.key(0x85);self.type(str(device));self.key(13)

    def finish(self):
        self.clean();self.key(27);self.key(27,exited=True)
        assert self.ram[0x3d28]==0

    def queue(self,keys):
        self.observation_target=self.events+len(keys);self.observation_done=False
        self.keys.extend(keys);self.loop();assert self.observation_done
        self.events+=len(keys)
        assert int.from_bytes(self.ram[0x3d13:0x3d15],'little')==self.events

    def cancel_at(self,phase,count):
        original=self.io.stub;fired=[]
        def stub(cpu):
            if (not fired and cpu.pc==0xffe4 and self.value('fc_phase')==phase
                    and self.number('fc_copied' if phase==1 else 'fc_verified')>=count):
                fired.append(True);self.keys.append(27)
            return original(cpu)
        self.io.stub=stub
        self.observation_target=self.events+2;self.observation_done=False
        self.keys.append(13);self.loop();assert fired and self.observation_done
        self.events+=2;self.io.stub=original


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path)
    parser.add_argument('--case',choices=('all','iec','ultimate','faults'),default='all');args=parser.parse_args()
    report=dict(passed=False,images={'kestrel.prg':hashlib.sha256(KERNEL_IMAGE.read_bytes()).hexdigest(),
        'files.prg':hashlib.sha256((ROOT/'target/native-desktop/files.prg').read_bytes()).hexdigest()},cases={})
    def done(label,b):
        report['cases'][label]=dict(events=b.events,instructions=b.instructions,frames=b.frames)
        print('PASS: native Files copy '+label,flush=True)
    try:
        if args.case in ('all','iec'):
            for fmt,kind,length in ((0,b'S',0),(0,b'P',1),(1,b'U',511),(1,b'P',512),(2,b'S',66058)):
                raw=bytes((i*73+19)&255 for i in range(length));source={(9,b'SOURCE',kind):raw}
                b=CopyFiles(source,fmt=fmt);b.type('C')
                kind_id=(b'S',b'P',b'U').index(kind)
                b.check(b'SOURCE',b'SOURCE',source_format=fmt,fmt=fmt,kind=kind_id)
                before=b.preferences();b.rename('COPY');b.key(9)
                assert b.value('fc_picker_active')
                for screen,columns in zip(b.screens,(40,80)):
                    wanted=picker_console(expected(source,9),device=9,fmt=fmt,columns=columns)
                    assert screen==wanted,('picker console',columns,
                        [(i,a,z) for i,(a,z) in enumerate(zip(screen,wanted)) if a!=z][:30])
                    b.frames+=1
                b.type('D10');b.key(13);b.type('S')
                assert b.preferences()==before
                b.check(b'SOURCE',b'COPY',source_format=fmt,device=10,fmt=fmt,kind=kind_id)
                b.io.formats[10]=fmt;b.key(13)
                if not length:
                    b.check(b'SOURCE',b'COPY',source_format=fmt,device=10,fmt=fmt,kind=kind_id,status=13)
                    assert (10,b'COPY',kind) not in b.io.files
                    b.finish();done('iec-empty-rejected-before-create',b);continue
                b.check(b'SOURCE',b'COPY',source_format=fmt,device=10,fmt=fmt,kind=kind_id,copied=length,verified=length,status=1)
                assert bytes(b.io.files[10,b'COPY',kind])==raw and bytes(b.io.files[9,b'SOURCE',kind])==raw
                b.clean();b.key(13)
                b.check(b'SOURCE',b'COPY',source_format=fmt,device=10,fmt=fmt,kind=kind_id,status=4,error=0x11,dos=63)
                assert bytes(b.io.files[10,b'COPY',kind])==raw
                b.finish();done(f'iec-{fmt}-{kind.decode()}-{length}-cross-drive-picker-exclusive-verified',b)

            # Files now owns the keyboard for its entire app/module lifetime.
            # Install the foreign table before entry, then verify exact teardown.
            import ci_native_calc as calc
            machine=calc.Machine();key_table=bytes((i*31+7)&255 for i in range(256))
            machine.ram[0x1000:0x1100]=key_table
            factory=calc.Machine;calc.Machine=lambda:machine
            try:b=CopyFiles({(9,b'NAME',b'S'):b'QUOTED\0BINARY\xff'})
            finally:calc.Machine=factory
            b.type('C');assert b.ram[0x1000:0x1014]==bytes([1]*10)+bytes.fromhex('8589868a878b888c8384')
            b.key(9);b.key(27);b.check(b'NAME',b'NAME')
            b.destination(9);b.rename('NAME "COPY"');b.key(13)
            b.check(b'NAME',b'NAME "COPY"',copied=14,verified=14,status=1)
            assert bytes(b.io.files[9,b'NAME "COPY"',b'S'])==b'QUOTED\0BINARY\xff'
            b.key(0x9d);b.check(b'NAME',b'NAME "COPY"',copied=14,verified=14,status=1)
            b.type('!');b.check(b'NAME',b'NAME "COPY!"')
            b.finish();assert b.ram[0x1000:0x1100]==key_table
            done('same-drive-quoted-name-picker-cancel-and-function-key-lifetime',b)

            import ci_native_calc as calc
            machine=calc.Machine();held=[]
            for bank,page in ((0,0xdf),(1,4)):
                handle=machine.alloc(32,bank,16,page=page)
                data=bytes((i*53+bank*17)&255 for i in range(8192))
                machine.bus.ram[bank][page*256:(page+32)*256]=data
                held.append((bank,page,handle,data))
            factory=calc.Machine;calc.Machine=lambda:machine
            try:b=CopyFiles({(9,b'SOURCE',b'S'):bytes(range(256))*3})
            finally:calc.Machine=factory
            b.type('C');b.rename('COPY');b.key(9);b.type('S');b.key(13);b.clean();b.key(27)
            for bank,page,handle,data in held:
                assert machine.bus.ram[bank][page*256:(page+32)*256]==data
                assert machine.ram[0x3c00+(handle[0]-1)*8]==16
            saved=bytes(b.ram[0x100:0x200]);machine.select(held[0][2],16);machine.invoke('release');b.ram[0x100:0x200]=saved
            b.key(27,exited=True);done('two-preexisting-banked-workspaces-preserved-through-copy-and-picker',b)

        if args.case in ('all','ultimate'):
            for source_usb in (False,True):
                b=CopyFiles({} if source_usb else {(9,b'SOURCE',b'S'):b''},
                    usb={b'/SOURCE':b''} if source_usb else {},directories={b'/':[b'\x20SOURCE']} if source_usb else {})
                if source_usb:b.type('FFF')
                b.type('C')
                if not source_usb:
                    for _ in range(3):b.key(0x86)
                b.rename('/EMPTY COPY');b.key(13)
                b.check(b'/SOURCE' if source_usb else b'SOURCE',b'/EMPTY COPY',source_device=1 if source_usb else 9,
                    source_format=3 if source_usb else 0,device=2 if source_usb else 1,fmt=3,status=1)
                assert b.ultimate.files[b'/EMPTY COPY']==b''
                b.finish();done('zero-byte-to-ultimate-from-'+('ultimate' if source_usb else 'iec'),b)
            raw=bytes(range(256))*5+b'\0END'
            b=CopyFiles({(9,b'SOURCE',b'U'):raw},usb={},directories={b'/':[b'\x10Usb0'],b'/Usb0':[b'\x10EMPTY'],b'/Usb0/EMPTY':[]})
            b.type('C');b.rename('COPY');before=b.preferences();b.key(9)
            b.type('FFF');b.key(13);b.key(13);b.type('S')
            assert b.preferences()==before
            b.check(b'SOURCE',b'/Usb0/EMPTY/COPY',device=1,fmt=3,kind=2)
            b.key(13);b.check(b'SOURCE',b'/Usb0/EMPTY/COPY',device=1,fmt=3,kind=2,copied=len(raw),verified=len(raw),status=1)
            assert b.ultimate.files[b'/Usb0/EMPTY/COPY']==raw
            b.finish();done('iec-to-ultimate-empty-folder-picker',b)

            long=b'Q"'*42+b' RAW\x01\xff'
            source=b'/Usb0/'+long
            entries=[b'\x20'+long]+[b'\x20'+f'OTHER{i}'.encode() for i in range(12)]
            b=CopyFiles(usb={source:raw},directories={b'/':[b'\x10Usb0'],b'/Usb0':entries})
            b.type('FFF');b.key(13);b.type('C')
            b.check(source,source,source_device=1,source_format=3,device=2,fmt=3)
            b.destination(1);b.rename('/Usb0/COPY');b.key(13)
            b.check(source,b'/Usb0/COPY',source_device=1,source_format=3,device=1,fmt=3,status=8)
            b.destination(2);b.key(13)
            b.check(source,b'/Usb0/COPY',source_device=1,source_format=3,device=2,fmt=3,copied=len(raw),verified=len(raw),status=1)
            assert b.ultimate.files[source]==raw and b.ultimate.files[b'/Usb0/COPY']==raw
            b.clean();b.key(27)
            assert b.ram[0x3d34]==len(long) and bytes(b.ram[0x3e00:0x3e00+len(long)])==long
            b.key(27,exited=True);assert b.ram[0x3d28]==0
            done('ultimate-two-context-long-raw-name-active-cursor-selection-and-desktop',b)

            for length in (0,1,66058):
                data=bytes((i*17+101)&255 for i in range(length))
                b=CopyFiles(usb={b'/SOURCE':data},directories={b'/':[b'\x20SOURCE']})
                b.type('FFF');b.type('C');b.key(0x86);b.destination(9);b.rename('COPY');b.key(0x87)
                b.key(13)
                if not length:
                    b.check(b'/SOURCE',b'COPY',source_device=1,source_format=3,device=9,kind=1,status=13)
                    assert (9,b'COPY',b'P') not in b.io.files
                    b.finish();done('ultimate-empty-to-iec-rejected-before-create',b);continue
                b.check(b'/SOURCE',b'COPY',source_device=1,source_format=3,device=9,kind=1,copied=length,verified=length,status=1)
                assert bytes(b.io.files[9,b'COPY',b'P'])==data
                b.finish();done(f'ultimate-to-iec-raw-prg-{length}',b)

        if args.case in ('all','faults'):
            raw=bytes(range(256))*7
            for phase in (1,2):
                b=CopyFiles({(9,b'SOURCE',b'S'):raw});b.type('C');b.rename('PARTIAL');b.cancel_at(phase,512)
                b.check(b'SOURCE',b'PARTIAL',copied=512 if phase==1 else len(raw),verified=512 if phase==2 else 0,status=2,partial=True)
                assert bytes(b.io.files[9,b'PARTIAL',b'S'])==(raw[:512] if phase==1 else raw)
                assert bytes(b.io.files[9,b'SOURCE',b'S'])==raw
                b.finish();done(f'cancel-phase-{phase}-retains-new-file-and-source',b)

            for change in ('truncate','append','corrupt'):
                b=CopyFiles({(9,b'SOURCE',b'S'):raw});b.type('C');b.rename('BAD');original=b.io.stub;changed=[]
                def stub(cpu):
                    if not changed and cpu.pc==0xffc0 and b.value('fc_phase')==2:
                        changed.append(True);key=(9,b'BAD',b'S')
                        if change=='truncate':del b.io.files[key][-1:]
                        elif change=='append':b.io.files[key].append(99)
                        else:b.io.files[key][-1]^=1
                    return original(cpu)
                b.io.stub=stub;b.key(13)
                b.check(b'SOURCE',b'BAD',copied=len(raw),verified=len(raw) if change=='append' else 1536,status=7,partial=True)
                assert changed and bytes(b.io.files[9,b'SOURCE',b'S'])==raw
                b.io.stub=original;b.finish();done('reopen-detects-'+change,b)

            b=CopyFiles({(9,b'SOURCE',b'S'):raw});b.type('C');b.rename('FAIL');b.io.fail_write=17;b.key(13)
            assert b.value('fc_status')==3 and bytes(b.io.files[9,b'FAIL',b'S'])==raw[:17]
            b.clean();b.io.fail_write=None;b.rename('RECOVER');b.key(13)
            b.check(b'SOURCE',b'RECOVER',copied=len(raw),verified=len(raw),status=1)
            b.finish();done('short-write-kept-without-replay-then-new-name-recovers',b)

            b=CopyFiles({(9,b'SOURCE',b'S'):raw});b.type('C');b.rename('MISSING');del b.io.files[9,b'SOURCE',b'S'];b.key(13)
            assert b.value('fc_status')==3 and (9,b'MISSING',b'S') not in b.io.files
            b.finish();done('source-disappeared-before-open-no-destination',b)

            b=CopyFiles({(9,b'SOURCE',b'S'):raw});b.type('C');b.rename('READFAIL');b.io.fail_read=513;b.key(13)
            b.check(b'SOURCE',b'READFAIL',copied=512,status=3,partial=True,error=0x11)
            assert bytes(b.io.files[9,b'READFAIL',b'S'])==raw[:512]
            b.io.fail_read=None;b.finish();done('source-read-error-retains-confirmed-prefix',b)

            b=CopyFiles({(9,b'SOURCE',b'S'):raw},usb={})
            b.type('C');b.key(0x86);b.key(0x86);b.key(0x86);b.rename('/SHORT')
            b.ultimate.write_limit=17;b.key(13)
            assert b.value('fc_status')==3 and b.ultimate.files[b'/SHORT']==raw[:17]+b'\xff'
            assert [len(cmd)-4 for cmd in b.ultimate.commands if cmd[1]==5]==[511,1],'uncertain transfer was replayed'
            b.ultimate.write_limit=None;b.finish();done('ultimate-short-write-no-replay',b)

            b=CopyFiles(usb={b'/SOURCE':raw,b'/FOREIGN':b'KEPT'},directories={b'/':[b'\x20SOURCE']})
            b.type('FFF');b.type('C');b.rename('/COPY')
            foreign=dict(name=b'/FOREIGN',mode=1,pos=2);b.ultimate.handles[2]=dict(foreign)
            b.key(13);assert b.value('fc_status')==3 and b.value('fc_error')==0x15
            assert b.ultimate.handles[2]==foreign and b'/COPY' not in b.ultimate.files
            b.ultimate.handles[2]=None;b.finish();done('foreign-ultimate-context-preserved',b)

            entries=[b'\x20'+f'FILE{i:02}'.encode() for i in range(12)]
            b=CopyFiles(usb={b'/FILE00':raw},directories={b'/':entries})
            b.type('FFF');b.type('C');b.rename('/COPY');before=b.preferences();b.key(9)
            b.ultimate.ignore_abort=True;b.key(27)
            assert b.value('fc_status')==10 and b.value('fc_picker_cursor') and b.preferences()==before
            b.key(13);assert b.value('fc_status')==9 and b'/COPY' not in b.ultimate.files
            b.ultimate.ignore_abort=False;b.key(27);b.key(27,exited=True)
            assert b.ultimate.handles=={1:None,2:None} and not b.ultimate.state
            done('picker-abort-failure-retained-and-cleanup-recovered',b)

            b=CopyFiles(usb={b'/SOURCE':raw},directories={b'/':[b'\x20SOURCE']})
            b.type('FFF');b.type('C');b.rename('/COPY')
            b.ultimate.inject[3]=lambda cmd,reply:[(b'',b'71,CLOSE ERROR')]
            b.key(13);assert b.value('fc_status')==9 and b.data('fc_handles',8)[4]
            b.key(27);assert b.value('fc_active') and b.value('fc_status')==9
            b.ultimate.inject.clear();b.key(27);b.key(27,exited=True)
            assert b.ultimate.handles=={1:None,2:None}
            done('ultimate-close-failure-retains-handle-and-retries-cleanup',b)
        report['passed']=True
    except BaseException as error:report['error']=str(error);raise
    finally:
        if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
