#!/usr/bin/env python3
"""Execute the suite editor's graphical controls, document and file lifetimes."""
import argparse
import hashlib
import json
from pathlib import Path
import traceback
from ci_native_editor import Editor,ROOT
from ci_native_pointer import Pointer,PointerBus,heap
import ci_native_calc as calc
from native_editor_scene import surface,console,RECTS

class GraphicalEditor(Editor):
    position=Pointer.position
    frame=Pointer.frame
    poll=Pointer.poll
    move=Pointer.move
    restored=Pointer.restored

    def __init__(self,*args,configure=lambda bus:None,configure_machine=lambda machine:None,configure_io=lambda editor:None,existing_machine=None,**kwargs):
        self.configure_io=configure_io;self.configured_io=False
        bus=PointerBus() if existing_machine is None else existing_machine.bus;configure(bus);factory=heap.Bus;heap.Bus=lambda:bus
        machine_factory=calc.Machine
        def machine():
            m=machine_factory() if existing_machine is None else existing_machine;configure_machine(m);return m
        calc.Machine=machine
        try:super().__init__(*args,image_prefix='native-desktop',**kwargs)
        finally:heap.Bus=factory;calc.Machine=machine_factory
        while not isinstance(bus.video,dict) and hasattr(bus,'parent'):bus=bus.parent
        self.bus=bus;self.frames=0;self.checked=0;self.module_calls=0
        step=self.cpu.step
        def checked_step():
            if self.cpu.pc==0x1c62:
                assert not self.ram[0x3d12],'module gate entered while readiness is published'
                self.module_calls+=1
            return step()
        self.cpu.step=checked_step

    def loop(self,exited=False):
        if not self.configured_io:
            self.configured_io=True;self.configure_io(self)
        return super().loop(exited)

    def key(self,key,exited=False):
        self.observation_target=None;self.keys.append(key);self.loop(exited);self.events+=1
        assert int.from_bytes(self.ram[0x3d13:0x3d15],'little')==self.events
        if not exited:assert self.cpu.pc==0xffe4 and self.ram[0x3d12]==1

    def click(self,index,*,exited=False):
        x0,y0,x1,y1=RECTS[index];self.move((x0+x1)//2,(y0+y1)//2)
        self.frame(down=True);self.frame(down=False,exited=exited)

    def check(self,want,cursor=None,dirty=None,status=None,name=None,mode=None,released=True,selection=None):
        got=self.contents()
        if got!=want:
            at=next((i for i,(a,b) in enumerate(zip(got,want)) if a!=b),min(len(got),len(want)))
            raise AssertionError(f'document differs at byte {at} (length {len(got)}, want {len(want)}): '
                                 f'got {bytes(got[max(0,at-8):at+8])!r} want {bytes(want[max(0,at-8):at+8])!r}')
        at=self.number('ed_cursor')
        if cursor is not None:assert at==cursor,(at,cursor)
        if dirty is not None:assert self.state()['dirty']==int(dirty)
        if status is not None:assert self.value('ed_status')==status,(self.value('ed_status'),status)
        if name is not None:assert self.string('ed_name')==name
        if mode is not None:assert self.value('ed_mode')==mode,(self.value('ed_mode'),mode)
        assert self.value('eg_bitmap') and self.value('ed_module_kind')==2
        kw=dict(name=self.string('ed_name'),dirty=bool(self.state()['dirty']),device=self.value('ed_device'),fmt=self.value('ed_format'),
                view=self.number('ed_view'),horizontal=self.number('ed_horizontal'),mode=self.value('ed_mode'),field=self.string('ed_field'),
                field_caret=self.value('ed_field_cursor'),status=self.value('ed_status'),search_case=self.value('ed_s_pending_case'),replacements=self.number('ed_s_count'))
        actual_selection=(self.number('es_first'),self.number('es_limit')) if self.value('es_active') else None
        assert actual_selection==selection,(actual_selection,selection)
        kw['selection']=selection
        focus=self.value('ui_selected')
        expected=surface(want,at,focus=focus,more=self.value('eg_more'),field_view=self.ram[self.symbol('ed_field_views')],**kw)
        actual=bytes(self.ram[0xc000:0xe400])
        assert actual==expected,('bitmap',[(i,a,b) for i,(a,b) in enumerate(zip(actual,expected)) if a!=b][:25])
        if not self.value('vd_phase'):
            expected=console(want,at,focus=focus,field_view=self.ram[self.symbol('ed_field_views')+1],**kw)
            assert self.screens[1]==expected,('vdc',[(i,a,b) for i,(a,b) in enumerate(zip(self.screens[1],expected)) if a!=b][:25])
        if released:assert not self.io.handles and self.ram[0x3de0:0x3de4]==bytes(4)
        self.checked+=1

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--case',choices=['keyboard','mouse','search','picker','large','fallback','modules','longfields','cancel_write','cancel_verify','retained','source','reservation','print'],default='keyboard');parser.add_argument('--report',type=Path,required=True);a=parser.parse_args()
    result=dict(passed=False,physical_hardware_io=False,cases=[],images={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ('target/native','target/native-desktop') for p in (ROOT/folder).iterdir() if p.suffix in ('.prg','.d64')})
    try:
        raw=(b'0123456789 ABCDEFGHIJKLMNOPQRSTUVWXYZ\r\n'*1800)[:66053]
        if a.case=='large':
            # The 96-page graphical app leaves room for sixteen complete
            # RAM document chunks. Exercise the exact 64 KiB length boundary;
            # larger positions/spans use the separate REU workflows.
            raw=raw[:65532]
        files={(9,b'SOURCE',b'S'):b'ONE "QUOTE"\r\nTWO\n'+bytes([0,255]),(9,b'LARGE',b'S'):raw}
        options={}
        if a.case=='reservation':
            held=[];foreign=bytes((i*73+19)&255 for i in range(256))
            def reserve(machine):
                held.append(machine.alloc(1,0,16,page=0xc0))
                machine.ram[0xc000:0xc100]=foreign
            options['configure_machine']=reserve
        if a.case=='source':options.update(source_path=b'/Apps/Original/EDITOR',source_context=2)
        if a.case.startswith('cancel_'):files[9,b'SOURCE',b'S']=(b'ROW 12345\r'*410)[:4096]
        if a.case=='fallback':options['configure_io']=lambda e:e.io.files.pop((8,b'EDFIND.PRG',b'P'))
        if a.case=='longfields':
            folder=b'/Usb0/'+b'A'*120+b'/'+b'B'*120
            original=folder+b'/IN.TXT';destination=folder+b'/OUT.TXT'
            assert len(original)==254 and len(destination)==255
            options=dict(source_path=b'/Apps/Original/EDITOR',source_context=2,ultimate_files={original:b'EXACT LONG PATH'},device=2,fmt=3)
        else:options.update(device=9,fmt=2 if a.case=='large' else 0)
        e=GraphicalEditor(files,**options)
        print("Started graphical editor",e.instructions,"instructions",flush=True)
        if a.case=='keyboard':
            e.check(b'',0,False)
            e.type('ONE\rTwo');e.check(b'ONE\rTwo',7,True)
            e.key(0x91);e.check(b'ONE\rTwo',3,True)
            e.key(0x13);e.check(b'ONE\rTwo',0,True)
            e.key(9);e.check(b'ONE\rTwo',0,True)
            e.key(9);assert e.value('ui_selected')==1;e.key(13);e.check(b'ONE\rTwo',0,True,mode=1)
            e.type('SOURCE');e.check(b'ONE\rTwo',0,True,mode=1)
            e.key(27);e.check(b'ONE\rTwo',0,True,mode=0)
            e.key(27);e.check(b'ONE\rTwo',0,True,mode=5)
            e.key(13);e.check(b'ONE\rTwo',0,True,mode=0)
            e.exit(dirty=True);e.restored()
        elif a.case=='print':
            def petscii(data):          # as editor/print.inc sends a document
                out=bytearray()
                for i,c in enumerate(data):
                    if c==10:
                        if i and data[i-1]==13:continue
                        c=13
                    elif c==9:c=32
                    elif c!=13 and not 32<=c<127:continue
                    elif 0x41<=c<=0x5a:c|=0x80
                    elif 0x61<=c<=0x7a:c&=0xdf
                    out.append(c)
                return bytes(out)
            want=b'Hello, World!\rsecond line: 42\rEND';e.type(want.decode());e.check(want,len(want),True)
            parameters=bytes(e.ram[0xb7:0xc0])+bytes(e.ram[0xc6:0xc8])+bytes([e.ram[0x9d]])
            mark=len(e.io.events)
            e.key(16);e.check(want,len(want),True,status=33)          # Ctrl-P, no printer: refused
            assert not e.io.printers and ('open',121,4,7,'') in e.io.events[mark:]
            e.io.printers[4]=bytearray()
            e.key(16);e.check(want,len(want),True,status=32)          # printed
            assert bytes(e.io.printers[4])==petscii(want)==b'\xc8ELLO, \xd7ORLD!\rSECOND LINE: 42\r\xc5\xce\xc4',bytes(e.io.printers[4])
            assert bytes(e.ram[0xb7:0xc0])+bytes(e.ram[0xc6:0xc8])+bytes([e.ram[0x9d]])==parameters,'KERNAL file parameters kept'
            e.exit(dirty=True);e.restored()
        elif a.case=='mouse':
            e.frame();want=b'0123456789\rSECOND LINE\rLAST';e.type(want.decode());e.check(want,len(want),True)
            e.move(40,60);e.frame(down=True);e.frame(down=False);e.check(want,4,True)
            e.type('A');want=want[:4]+b'A'+want[4:];e.check(want,5,True)
            e.click(3);e.check(want,5,True,mode=6)
            e.click(14);assert e.value('ed_s_pending_case')==1
            e.type('line');e.key(13);e.check(want,want.index(b'LINE'),True,status=13,mode=0)
            e.click(5);e.click(8);e.type('000002');e.check(want,mode=3)
            e.move(24,100);e.frame(down=True);e.frame(down=False);assert e.value('ed_field_cursor')==1;e.check(want,mode=3)
            e.key(4);e.type('1');assert e.string('ed_field')=='010002';e.key(13);e.check(want,status=4,mode=3)
            e.key(21);e.type('000003');e.key(13);e.check(want,3,True,mode=0)
            e.exit(dirty=True);e.restored()
        elif a.case=='search':
            want=b'ABABA\raba\rLAST';e.type(want.decode());e.key(0x89)
            e.key(6);e.type('ABA');e.check(want,0,True,mode=6);e.key(13);e.check(want,0,True,status=13)
            e.key(14);e.check(want,2,True,status=13);e.key(14);e.check(want,0,True,status=14)
            e.key(18);e.key(21);e.type('aba')
            for _ in range(3):e.key(9)
            assert e.value('ui_selected')==14;e.key(13);assert e.value('ed_s_pending_case')==1
            e.key(9);e.key(13);e.check(want,0,True,mode=8)
            e.type('X');e.key(13);e.check(want,0,True,mode=9);assert e.value('ui_selected')==13
            e.key(9);e.key(13);want=b'XBA\raba\rLAST';e.check(want,dirty=True,status=17,mode=0)
            e.key(18);e.key(13);e.type('Y');e.key(13);e.key(9);e.key(9);e.key(13)
            want=b'XBA\rY\rLAST';e.check(want,dirty=True,status=17,mode=0);assert e.number('ed_s_count')==1
            e.exit(dirty=True);e.restored()
        elif a.case=='picker':
            from native_browser_check import browser_screen
            from ci_native_browser import expected
            e.type('KEEP DOCUMENT');want=b'KEEP DOCUMENT';e.key(0x86);e.type('COPY')
            before=e.contents();cursor=e.number('ed_cursor');field_state=bytes(e.ram[e.symbol('ed_field_len'):e.symbol('ed_field_len')+8])
            e.key(0x88);assert e.value('ed_module_kind')==1 and not e.value('eg_bitmap') and e.value('fd_active')
            records=expected(e.io.files,9)
            for record in records:record['app']=False
            from native_picker_fixture import Picker
            Picker(e).check(records,mode=2,device=9)
            assert e.contents()==before and e.number('ed_cursor')==cursor
            e.key(27);e.check(want,cursor,True,mode=2)
            assert bytes(e.ram[e.symbol('ed_field_len'):e.symbol('ed_field_len')+8])==field_state
            e.key(13);e.check(want,cursor,False,status=1,name='COPY');assert bytes(e.io.files[9,b'COPY',b'S'])==want
            e.key(0x85);e.key(0x88);e.key(0x11);e.key(13);e.check(want,mode=1)
            assert e.string('ed_field')=='LARGE'
            e.key(27);e.exit();e.restored()
        elif a.case=='large':
            e.prompt(0x85,'LARGE');e.check(raw,0,False,name='LARGE')
            e.prompt(0x88,'00FFF1');at=65521
            if raw[at-1:at+1]==b'\r\n':at+=1
            e.check(raw,at,False,name='LARGE');e.type('C128');want=raw[:at]+b'C128'+raw[at:]
            e.check(want,at+4,True);e.prompt(0x86,'COPY');e.check(want,at+4,False,status=1,name='COPY')
            assert bytes(e.io.files[9,b'COPY',b'S'])==want
            e.key(0x8a);e.check(want,65536,False,name='COPY')
            e.exit();e.restored()
        elif a.case=='fallback':
            assert not e.value('eg_bitmap') and e.value('ed_module_kind')==0
            e.type('KEPT');Editor.check(e,b'KEPT',4,True)
            e.prompt(0x86,'COPY');Editor.check(e,b'KEPT',4,False,status=1,name='COPY')
            assert bytes(e.io.files[9,b'COPY',b'S'])==b'KEPT'
            e.io.files[8,b'EDFIND.PRG',b'P']=(ROOT/'target/native-desktop/edfind.prg').read_bytes()
            e.key(12);e.check(b'KEPT',4,False,status=1,name='COPY')
            e.exit();e.restored()
        elif a.case=='modules':
            e.type('DOCUMENT');want=b'DOCUMENT';picker=e.io.files.pop((8,b'EDPICK.PRG',b'P'))
            e.key(0x85);e.type('SOURCE');e.key(0x88);e.check(want,8,True,status=2,mode=1)
            e.io.files[8,b'EDPICK.PRG',b'P']=picker
            e.key(0x88);assert e.value('fd_active') and e.value('ed_module_kind')==1
            module=e.io.files[8,b'EDFIND.PRG',b'P'];bad=bytearray(module);bad[-1]^=1;e.io.files[8,b'EDFIND.PRG',b'P']=bytes(bad)
            e.key(27);assert not e.value('eg_bitmap') and e.value('ed_module_kind')==0
            Editor.check(e,want,8,True,mode=1)
            e.key(27);e.io.files[8,b'EDFIND.PRG',b'P']=module;e.key(12);e.check(want,8,True,mode=0)
            e.exit(dirty=True);e.restored()
        elif a.case=='longfields':
            e.prompt(0x85,original.decode());e.check(b'EXACT LONG PATH',0,False,name=original.decode())
            e.key(0x86);e.type(destination.decode());e.check(b'EXACT LONG PATH',mode=2)
            assert e.value('ed_field_len')==255 and e.value('ed_field_cursor')==255
            e.type('Z');assert e.string('ed_field')==destination.decode()
            e.key(0x13);e.check(b'EXACT LONG PATH',mode=2);assert e.ram[e.symbol('ed_field_views')]==0
            e.key(5);e.key(13);e.check(b'EXACT LONG PATH',0,False,name=destination.decode(),status=1)
            assert bytes(e.ultimate.files[destination])==b'EXACT LONG PATH'
            # Change the data backend, then reload both modules from the
            # application's original Ultimate context and parent directory.
            e.key(0x8b);e.key(0x85);e.key(0x88);assert e.value('ed_module_kind')==1
            e.key(27);e.check(b'EXACT LONG PATH',0,False,name=destination.decode(),mode=1)
            assert e.value('ed_module_kind')==2
            e.key(27);e.exit();e.restored()
        elif a.case=='retained':
            from ci_native_directory_ultimate import DirectoryDOS
            from ci_native_ultimate import UltimateBus
            e.ultimate=DirectoryDOS(files={b'/FILE00':b'KEPT'})
            e.ultimate.directories[b'/']=[b'\x20'+f'FILE{i:02}'.encode() for i in range(12)]
            e.m.bus=UltimateBus(e.m.bus,e.ultimate);e.cpu.memory=e.m.bus
            e.type('KEPT')
            for _ in range(3):e.key(0x8b)
            e.key(0x86);e.type('/COPY');e.key(0x88)
            e.ultimate.ignore_abort=True;e.key(27)
            assert e.value('ed_module_kind')==1 and not e.value('eg_bitmap') and e.value('bu_cursor')
            assert e.value('ed_status')==9 and e.contents()==b'KEPT'
            address=e.symbol('editor_module');window=bytes(e.ram[address:address+16])
            cursor=bytes(e.ram[e.symbol('bu_cursor'):e.symbol('bu_cursor')+4]);commands=len(e.ultimate.commands)
            e.key(13);assert e.value('ed_status')==9 and b'/COPY' not in e.ultimate.files
            assert e.value('ed_module_kind')==1 and bytes(e.ram[address:address+16])==window
            assert bytes(e.ram[e.symbol('bu_cursor'):e.symbol('bu_cursor')+4])==cursor
            assert len(e.ultimate.commands)==commands and e.contents()==b'KEPT' and e.state()['dirty']
            e.ultimate.ignore_abort=False;e.key(0x86);e.type('/COPY');e.key(0x88)
            assert e.value('fd_active');e.key(27);e.check(b'KEPT',4,True,mode=2)
            e.key(13);e.check(b'KEPT',4,False,status=1,name='/COPY')
            assert bytes(e.ultimate.files[b'/COPY'])==b'KEPT' and bytes(e.ultimate.files[b'/FILE00'])==b'KEPT'
            e.exit();e.restored()
        elif a.case=='source':
            e.type('ORIGINAL SOURCE');want=b'ORIGINAL SOURCE'
            e.key(0x86);e.type('COPY');e.key(0x88);e.type('D10');e.key(13);e.type('S')
            e.check(want,len(want),True,mode=2)
            opened=[command for command in e.ultimate.commands if command[1]==2]
            # Without a VDC, display refusal closes the optional provider.
            # The document memory client then probes it once for REU backing.
            providers=1 if getattr(e,'vdc_expected',False) else 2
            expected=[b'/Apps/Original/EDITOR',b'/Apps/Original/EDFIND.PRG']+[
                b'/Apps/Original/VDSVC.PRG']*providers+[
                b'/Apps/Original/EDPICK.PRG',b'/Apps/Original/EDFIND.PRG']
            result['source_opens']=[command.hex() for command in opened]
            assert [command[3:] for command in opened]==expected,result['source_opens']
            assert all(command[0]==2 for command in opened)
            e.ultimate.inject[3]=lambda command,reply:[(b'',b'71,CLOSE ERROR')]
            e.key(0x88);assert e.value('ed_module_kind')==0 and e.ram[0x3d1b]==4 and not e.value('eg_bitmap')
            e.key(13);assert e.value('ed_status')==9 and (10,b'COPY',b'S') not in e.io.files
            assert e.contents()==want and e.state()['dirty']
            e.ultimate.inject.clear();e.key(0x86);e.type('COPY');e.key(0x88)
            assert e.value('fd_active');e.key(27);e.check(want,len(want),True,mode=2)
            e.key(13);e.check(want,len(want),False,status=1,name='COPY')
            assert bytes(e.io.files[10,b'COPY',b'S'])==want
            if getattr(e,'vdc_expected',False):
                # The failed module-source close restored VDC into text.
                # Explicitly reacquire it after the retained stream recovers.
                e.bus.original=None;e.key(12);e.check(want,len(want),False,status=1,name='COPY')
                providers=[c for c in e.ultimate.commands if c[1]==2 and c[3:].endswith(b'/VDSVC.PRG')]
                assert len(providers)==(1 if e.value('dm_lease') or e.value('eh_available') else 2)
                assert all(c[0]==2 and c[3:]==b'/Apps/Original/VDSVC.PRG' for c in providers)
            e.exit();e.restored()
        elif a.case=='reservation':
            assert not e.value('eg_bitmap') and e.value('eg_error')==2
            e.type('FOREIGN');e.prompt(0x86,'COPY');Editor.check(e,b'FOREIGN',7,False,status=1,name='COPY')
            assert bytes(e.io.files[9,b'COPY',b'S'])==b'FOREIGN' and bytes(e.ram[0xc000:0xc100])==foreign
            stack=bytes(e.ram[0x100:0x200]);e.m.select(held[0],16);e.m.invoke('release');e.ram[0x100:0x200]=stack
            e.key(12);e.check(b'FOREIGN',7,False,status=1,name='COPY');assert not e.value('eg_error')
            e.exit();e.restored()
        elif a.case.startswith('cancel_'):
            phase=2 if a.case=='cancel_write' else 3
            original=files[9,b'SOURCE',b'S'];e.prompt(0x85,'SOURCE');e.type('!');want=b'!'+original
            e.frame();e.key(0x86);e.move(276,152);e.type('COPY')
            assert e.value('ui_selected')==11
            stub=e.io.stub;fired=[];busy=[]
            def cancel(cpu):
                if cpu.pc==0xffe4 and e.value('ed_io_phase')==phase and 512<=e.number('ed_io_pos') and len(fired)<4:
                    at=e.number('ed_io_pos');assert at==512*(len(fired)+1)
                    expected=surface(want,1,name='SOURCE',dirty=True,device=9,fmt=0,field='COPY',field_caret=4,field_view=0,
                        focus=20,busy=1,phase=phase,io_bytes=0)
                    actual=bytes(e.ram[0xc000:0xe400]);assert actual==expected,('busy bitmap',phase,at,[(i,x,y) for i,(x,y) in enumerate(zip(actual,expected)) if x!=y][:20])
                    busy.append(dict(phase=phase,bytes_processed=at,surface_sha256=hashlib.sha256(actual).hexdigest()))
                    e.bus.raster=132 if len(fired)&1 else 100
                    if not len(fired)&1:e.ram[0xa2]=(e.ram[0xa2]+1)&255
                    e.bus.down=len(fired)<2;fired.append(at)
                return stub(cpu)
            e.io.stub=cancel
            try:e.key(13)
            finally:e.io.stub=stub;e.bus.raster=100;e.bus.down=False
            assert fired==[512,1024,1536,2048],fired
            e.check(want,1,True,status=10,name='SOURCE',mode=0)
            assert bytes(e.io.files[9,b'COPY',b'S'])==(want[:2048] if phase==2 else want)
            result['busy_frames']=busy
            e.exit(dirty=True);e.restored()
        result['cases'].append(dict(name=a.case,frames=e.frames,checked=e.checked,events=e.events,instructions=e.instructions,module_calls=e.module_calls))
        result['passed']=True;print('PASS:',a.case,flush=True)
    except BaseException:
        result['error']=traceback.format_exc();raise
    finally:a.report.write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()
