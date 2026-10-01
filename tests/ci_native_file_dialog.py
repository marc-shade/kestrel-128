#!/usr/bin/env python3
"""Execute modal native file selection with a live, owned editor document."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace

from ci_native_editor import Editor, ROOT
from ci_native_browser import expected
from ci_native_directory_ultimate import DirectoryDOS
from ci_native_ultimate import UltimateBus
from native_browser_check import browser_screen, ultimate_browser_screen


class DialogEditor(Editor):
    def __init__(self, files=None, device=9, fmt=0, *, usb=None, directories=None):
        super().__init__(files,device,fmt)
        self.frames=0
        if usb is not None or directories is not None:
            self.ultimate=DirectoryDOS(files=usb)
            self.ultimate.trailing_paths=True
            self.ultimate.directories.update(directories or {})
            self.m.bus=UltimateBus(self.m.bus,self.ultimate)
            self.cpu.memory=self.m.bus

    def heap_call(self, operation, *args, **kwargs):
        saved=bytes(self.ram[0x100:0x200])
        try:return getattr(self.m,operation)(*args,**kwargs)
        finally:self.ram[0x100:0x200]=saved

    def keep_workspaces(self):
        self.workspace_data=[]
        for bank,page in ((0,0xdf),(1,4)):
            handle=self.heap_call('alloc',32,bank,16,page=page)
            contents=bytes((i*73+bank*37+19)&255 for i in range(8192))
            self.m.bus.ram[bank][page*256:(page+32)*256]=contents
            descriptor=bytes(self.ram[0x3c00+(handle[0]-1)*8:0x3c00+handle[0]*8])
            self.workspace_data.append((bank,page,handle,descriptor,contents))

    def check_workspaces(self):
        for bank,page,handle,descriptor,contents in self.workspace_data:
            assert self.m.bus.ram[bank][page*256:(page+32)*256]==contents
            assert bytes(self.ram[0x3c00+(handle[0]-1)*8:0x3c00+handle[0]*8])==descriptor

    def release_workspaces(self):
        self.check_workspaces()
        self.m.select(self.workspace_data[0][2],16)
        self.heap_call('invoke','release')

    def preferences(self):
        return (bytes(self.ram[0x3d29:0x3d35]),bytes(self.ram[0x4a00:0x4b00]),
                bytes(self.ram[0x3e00:0x3f00]))

    def begin(self,mode=1,name=''):
        self.key(0x85 if mode==1 else 0x86)
        self.type(name)
        self.kept_preferences=self.preferences()
        self.kept_document=self.contents()
        self.kept_context=bytes(self.ram[self.symbol('d_states'):self.symbol('d_states')+256])
        self.kept_position=tuple(self.number(name) for name in ('ed_cursor','ed_view','ed_horizontal'))
        self.kept_pages=bytes(self.ram[0x3800:0x3a00])
        self.key(9)
        assert self.value('fd_active')==1
        self.intact()

    def queue(self,keys):
        self.observation_target=self.events+len(keys);self.observation_done=False
        self.keys.extend(keys);self.loop();assert self.observation_done
        self.events+=len(keys)
        assert int.from_bytes(self.ram[0x3d13:0x3d15],'little')==self.events

    def intact(self,returned=False,retained=False):
        assert self.contents()==self.kept_document
        assert bytes(self.ram[self.symbol('d_states'):self.symbol('d_states')+256])==self.kept_context
        assert tuple(self.number(name) for name in ('ed_cursor','ed_view','ed_horizontal'))==self.kept_position
        if returned:
            assert self.preferences()==self.kept_preferences
            assert bytes(self.ram[0x3800:0x3a00])==self.kept_pages
            assert not self.value('fd_active')
            assert bool(self.value('bu_cursor'))==retained
            assert not self.io.handles
            if hasattr(self,'ultimate') and not retained:
                assert self.ultimate.paths=={1:b'/shell',2:b'/browser'}
                assert self.ultimate.handles=={1:None,2:None} and self.ultimate.state==0

    def check_picker(self,*,records=None,path=None,entries=None,base=0,selected=0,device=None,fmt=None,more=False,error=None,prompt=None,path_prompt=None):
        self.intact()
        assert self.value('fd_active') and self.ram[0x3d12]==1
        for screen,columns in zip(self.screens,(40,80)):
            if path is None:
                wanted=browser_screen(columns,records,selected,device,fmt,error,prompt,picker=True)
            else:
                wanted=ultimate_browser_screen(columns,path,entries,base,selected,device,more,error,
                                               path_prompt=path_prompt,picker=True)
            assert screen==wanted,('picker screen',columns,[(i,a,b) for i,(a,b) in enumerate(zip(screen,wanted)) if a!=b][:12])
            self.frames+=1


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path)
    parser.add_argument('--case',choices=('all','small','large','edges'),default='all');args=parser.parse_args()
    report=dict(passed=False,images={name:hashlib.sha256((ROOT/'target/native'/name).read_bytes()).hexdigest()
                                   for name in ('kestrel.prg','browse.prg','editor.prg')},cases={})
    def done(label,e):
        report['cases'][label]=dict(events=e.events,instructions=e.instructions,frames=e.frames)
        print('PASS: native file dialog '+label,flush=True)
    try:
        if args.case in ('all','small'):
            for fmt in (0,1,2):
                raw=b'RAW\r\nBYTES\0\xff'
                files={(9,b'NOTE "ONE"',b'S'):raw,(9,b'PROGRAM',b'P'):b'\x01\x08RAW PRG',(9,b'USER',b'U'):b'USR BYTES'}
                e=DialogEditor(files,fmt=fmt);e.type('KEEP\rDOCUMENT');want=e.contents()
                records=expected(files,9)
                for record in records:record['app']=False
                e.begin();e.check_picker(records=records,selected=0,device=9,fmt=fmt)
                e.key(27);e.intact(returned=True);e.check(want,mode=1)
                e.key(27);e.begin();e.key(0x11);e.key(13)
                e.intact(returned=True);e.check(want,mode=1)
                assert e.string('ed_field')=='PROGRAM' and e.value('ed_file_type')==1
                e.key(13);e.check(want,mode=5);e.type('Y');e.check(b'\x01\x08RAW PRG',0,False,name='PROGRAM')
                e.begin(mode=2,name='COPY');e.type('S');e.intact(returned=True)
                assert e.string('ed_field')=='COPY' and e.value('ed_file_type')==0
                e.key(13);e.check(b'\x01\x08RAW PRG',0,False,status=1,name='COPY')
                assert bytes(e.io.files[9,b'COPY',b'S'])==b'\x01\x08RAW PRG'
                e.exit();done(f'iec-{fmt}-cancel-prg-open-and-save-as',e)

            folder=b'/Usb0/QUOTED "FOLDER"'
            name=b'A'*45+b' RAW\x01\xff.TXT'
            data=b'EXACT SELECTED BYTES\0\xff'
            entries=[b'\x10EMPTY',b'\x20'+name]
            e=DialogEditor(usb={folder+b'/'+name:data},directories={b'/':[b'\x10Usb0'],b'/Usb0':[b'\x10QUOTED "FOLDER"'],folder:entries,folder+b'/EMPTY':[]})
            e.type('KEPT DOCUMENT');want=e.contents()
            for _ in range(3):e.key(0x8b)
            e.begin();e.check_picker(path=b'/',entries=[b'\x10Usb0'],device=1)
            e.key(13);e.check_picker(path=b'/Usb0/',entries=[b'\x10QUOTED "FOLDER"'],device=1)
            e.key(13);e.check_picker(path=folder+b'/',entries=entries,device=1)
            e.key(13);e.check_picker(path=folder+b'/EMPTY/',entries=[],device=1)
            e.type('P');e.key(0x11);e.key(13);e.intact(returned=True)
            full=(folder+b'/'+name).decode('latin1')
            assert e.string('ed_field')==full
            e.check(want,mode=1)
            e.key(13);e.type('Y');e.check(data,0,False,name=full)
            e.begin(mode=2,name='NEW.TXT');e.type('S');e.intact(returned=True)
            assert e.string('ed_field')==(folder+b'/NEW.TXT').decode()
            e.key(13);e.check(data,0,False,status=1,name=(folder+b'/NEW.TXT').decode())
            assert e.ultimate.files[folder+b'/NEW.TXT']==data
            e.exit();done('ultimate-folder-empty-full-raw-name-and-save-as',e)

            entries=[b'\x20'+f'ROW {i:03d}'.encode() for i in range(40)]
            e=DialogEditor(usb={},directories={b'/':[b'\x10Usb0'],b'/Usb0':entries})
            e.type('DOCUMENT REMAINS DIRTY');want=e.contents()
            for _ in range(3):e.key(0x8b)
            e.begin(name='/Usb0/');e.check_picker(path=b'/Usb0/',entries=entries[:8],device=1,more=True)
            e.queue([ord('N'),27])
            e.check_picker(path=b'/Usb0/',entries=entries[:8],device=1,more=True,error='SCAN CANCELLED; PREVIOUS PAGE RETAINED')
            e.type('G');e.key(21);e.type('/MISSING');e.key(13)
            e.check_picker(path=b'/Usb0/',entries=entries[:8],device=1,more=True,error='DISK I/O ERROR')
            e.type('N');e.check_picker(path=b'/Usb0/',entries=entries[8:16],base=8,device=1,more=True)
            e.ultimate.ignore_abort=True;e.key(27)
            e.intact(returned=True,retained=True);e.check(want,dirty=True,status=9,mode=1,released=False)
            assert e.ultimate.cancel_attempts and e.ultimate.paths[1]==b'/Usb0'
            e.ultimate.ignore_abort=False;e.key(9)
            assert e.value('fd_active')
            e.key(27);e.intact(returned=True);e.check(want,dirty=True,status=0,mode=1)
            e.key(27);e.exit(dirty=True);done('cancel-missing-directory-and-owned-close-recovery',e)

            e=DialogEditor(usb={},directories={b'/':[b'\x10Usb0']})
            e.type('MEMORY PRESSURE');want=e.contents()
            for _ in range(3):e.key(0x8b)
            reservations=[]
            for bank,table in ((0,0x3800),(1,0x3900)):
                page=0
                while page<255:
                    if e.ram[table+page]:page+=1;continue
                    start=page
                    while page<255 and not e.ram[table+page]:page+=1
                    reservations.append(e.heap_call('alloc',page-start,bank,77,page=start))
            before=e.preferences();pages=bytes(e.ram[0x3800:0x3a00])
            e.key(0x85);e.type('/');e.key(9)
            assert not e.value('fd_active') and e.value('fd_error')==2
            e.check(want,dirty=True,status=3,mode=1)
            assert e.preferences()==before and bytes(e.ram[0x3800:0x3a00])==pages
            assert e.string('ed_field')=='/' and e.ultimate.paths=={1:b'/shell',2:b'/browser'}
            e.m.select(reservations[0],77);e.heap_call('invoke','release')
            e.key(9);assert e.value('fd_active');e.key(27);e.key(27);e.exit(dirty=True)
            done('cache-allocation-failure-preserves-document-and-field',e)

        if args.case in ('all','large'):
            raw=(b'0123456789 ABCDEFGHIJKLMNOPQRSTUVWXYZ\r\n'*1800)[:66053]
            entries=[b'\x20'+f'FILE {i:04d}'.encode() for i in range(300)]
            e=DialogEditor(usb={b'/Usb0/LARGE':raw},directories={b'/':[b'\x10Usb0'],b'/Usb0':entries})
            e.keep_workspaces()
            for _ in range(3):e.key(0x8b)
            e.prompt(0x85,'/Usb0/LARGE');e.check(raw,0,False,name='/Usb0/LARGE')
            e.prompt(0x88,'010001');e.type('C128');e.key(20)
            want=raw[:65537]+b'C12'+raw[65537:]
            e.check(want,65540,True);e.check_workspaces()
            e.begin(mode=2,name='/Usb0/LARGE COPY')
            e.check_picker(path=b'/Usb0/',entries=entries[:8],device=1,more=True)
            for base in range(8,264,8):
                e.type('N');e.check_picker(path=b'/Usb0/',entries=entries[base:base+8],base=base,device=1,more=True)
                e.check_workspaces()
            e.type('B');e.check_picker(path=b'/Usb0/',entries=entries[248:256],base=248,device=1,more=True)
            e.key(9);e.check_picker(path=b'/Usb0/',entries=entries[:8],device=2,more=True)
            e.type('S');e.intact(returned=True);e.check_workspaces()
            assert e.string('ed_field')=='/Usb0/LARGE COPY' and e.value('ed_device')==2, (e.string('ed_field'),e.value('ed_device'),e.value('fd_error'),e.value('fd_result'),e.value('fd_chosen_device'),e.value('fd_leaf_at'),e.value('fd_candidate_length'))
            e.check(want,65540,True,mode=2)
            e.key(13);e.check(want,65540,False,status=1,name='/Usb0/LARGE COPY');e.check_workspaces()
            assert e.ultimate.files[b'/Usb0/LARGE COPY']==want
            e.release_workspaces();e.exit()
            report['saved_large']=dict(bytes=len(want),sha256=hashlib.sha256(want).hexdigest())
            done('large-document-two-workspaces-300-entries-and-verified-save',e)

        if args.case in ('all','edges'):
            files={(9,f'FILE{i:03d}'.encode(),b'S'):bytes([i&255]) for i in range(296)}
            e=DialogEditor(files,fmt=2);e.type('LIVE DOCUMENT');want=e.contents()
            records=expected(files,9);e.begin()
            e.check_picker(records=records,device=9,fmt=2)
            for _ in range(36):e.type('N')
            e.check_picker(records=records,selected=288,device=9,fmt=2)
            for _ in range(7):e.key(0x11)
            e.check_picker(records=records,selected=295,device=9,fmt=2)
            e.key(13);e.intact(returned=True);e.check(want,mode=1)
            assert e.string('ed_field')=='FILE295'
            e.key(13);e.type('Y');e.check(bytes([295&255]),0,False,name='FILE295')
            e.exit();done('complete-296-entry-d81-cache-and-selection',e)

            e=DialogEditor(usb={},directories={b'/':[]});e.type('KEPT')
            e.begin(mode=2,name='COPY');e.type('FFF');e.type('S');e.intact(returned=True)
            assert e.string('ed_field')=='/COPY' and e.value('ed_format')==3
            assert e.ram[0x3d29:0x3d2b]==bytes([9,0])
            e.key(27);e.prompt(0x8c,'2')
            assert e.ram[0x3d29:0x3d2b]==bytes([2,3]),'explicit device preference must include its backend'
            e.exit(dirty=True);done('dialog-backend-isolation-and-explicit-device-preference',e)

            name=b'P'*254;too_long=b'Q'*255;data=b'EXACT 255 BYTE PATH'
            entries=[b'\x20'+name,b'\x20'+too_long]
            e=DialogEditor(usb={b'/'+name:data},directories={b'/':entries})
            for _ in range(3):e.key(0x8b)
            e.begin();e.key(0x11);before=len(e.ultimate.commands);e.key(13)
            e.check_picker(path=b'/',entries=entries,selected=1,device=1,error='PATH TOO LONG; CANNOT OPEN THIS NAME')
            assert len(e.ultimate.commands)==before
            e.key(0x91);e.key(13);e.intact(returned=True)
            assert e.value('ed_field_len')==255 and e.string('ed_field')==(b'/'+name).decode()
            e.check(b'',mode=1);e.key(13);e.check(data,0,False,name=(b'/'+name).decode())
            e.exit();done('complete-255-byte-target-and-overflow-rejection',e)

            from hw_native_usb_browser import Navigation
            entries=[b'\x20'+f'ROW {i:03} "'.encode()+bytes([65+i])*((i*11)%200) for i in range(24)]
            e=DialogEditor(usb={},directories={b'/':entries})
            for _ in range(3):e.key(0x8b)
            e.begin()
            work=Path(tempfile.mkdtemp(prefix='kestrel-dialog-observer-decoder-'))
            def read(address,count=1):return bytes(e.ram[address:address+count])
            def capture(label,bank=0,address=0,count=2000):
                data=bytes(e.m.bus.ram[bank][address:address+count])
                (work/(label+'.bin')).write_bytes(data);return data
            client=SimpleNamespace(read=read,cpu_read=lambda label,address,count:capture(label,address=address,count=count),
                                   capture=SimpleNamespace(capture=capture))
            decoded={'usb_dialogs':{'oracles':{'private':{'path_hex':'2f','pages':{'0':{'entries_hex':[entry.hex() for entry in entries]}}}}}}
            observer=Navigation(client,work,decoded,b'/',{},lambda:None,image='editor',report_key='usb_dialogs')
            for base in (0,8,16):
                if base:e.type('N')
                actual,got=observer.raw_page('page-'+str(base))
                assert actual['cache_record_bytes']==256 and actual['base']==base and got==entries[base:base+8]
                assert actual['selected_name_hex']==entries[base][1:].hex()
            e.key(27);e.intact(returned=True);e.key(27);e.exit()
            done('physical-cache-decoder-against-executed-picker',e)
            report['cases']['physical-cache-decoder-against-executed-picker']['evidence']=str(work)
        report['passed']=True
    except BaseException as error:report['error']=str(error);raise
    finally:
        if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
