#!/usr/bin/env python3
"""Execute disk-loaded Files graphics, module replacement and byte-exact copies."""
import argparse
import hashlib
import json
from pathlib import Path

from ci_native_pointer import Pointer, PointerBus, heap
from ci_native_files_copy import CopyFiles
import ci_native_calc as calc
from ci_native_browser import expected
from native_browser_check import browser_screen, ultimate_browser_screen, preview_screen, screen_bytes
from native_files_copy_check import copy_screen
from native_files_scene import surface, RECTS, label
from native_field_check import field_cells


def ascii_rows(screen):
    def value(code):
        code &= 127
        if code<32:code+=64
        elif code>=64:code+=32
        if 97<=code<=122:code-=32
        return code
    return [bytes(map(value,screen[i:i+40])) for i in range(0,1000,40)]


class GraphicalFiles(CopyFiles):
    position=Pointer.position
    frame=Pointer.frame
    poll=Pointer.poll
    move=Pointer.move
    restored=Pointer.restored

    def __init__(self,*args,configure=lambda bus:None,configure_machine=lambda machine:None,**kwargs):
        bus=PointerBus();configure(bus)
        factory=heap.Bus;heap.Bus=lambda:bus
        machine_factory=calc.Machine
        def machine():
            result=machine_factory();configure_machine(result);return result
        calc.Machine=machine
        try:super().__init__(*args,**kwargs)
        finally:heap.Bus=factory;calc.Machine=machine_factory
        self.bus=bus;self.checked=0;self.module_calls=0
        step=self.cpu.step
        def checked_step():
            if self.cpu.pc==0x1c62:
                assert not self.ram[0x3d12],'module scratch must not change while the app publishes idle'
                self.module_calls+=1
            return step()
        self.cpu.step=checked_step

    def key(self,key,exited=False):
        self.observation_target=None;self.keys.append(key);self.loop(exited);self.events+=1
        assert int.from_bytes(self.ram[0x3d13:0x3d15],'little')==self.events
        if not exited:assert self.cpu.pc==0xffe4 and self.ram[0x3d12]==1

    def click(self,index,*,exited=False):
        x0,y0,x1,y1=RECTS[index];self.move((x0+x1)//2,(y0+y1)//2)
        self.frame(down=True);self.frame(down=False,exited=exited)

    def footer(self,screen):
        screen=bytearray(screen);focus=self.value('ui_selected');view=self.value('fv_view')
        text='File row' if 11<=focus<19 else 'Name / value' if focus==25 else label(focus,view,self.value('fc_phase'))
        rows=['']*23+['TAB CONTROLS  ENTER ACTIVATE','FOCUS: '+text.upper()]
        ending=screen_bytes(80,rows);screen[23*80:]=ending[23*80:]
        return bytes(screen)

    def canvas(self,rows,*,count=0,ultimate=False,caret=None,help_text=b'Tab controls  Enter activate'):
        assert self.value('fg_kind')==1 and self.value('fg_bitmap')
        actual=self.data('fv_body',1000);expected_body=b''.join(rows)
        assert actual==expected_body,('formatter',[(i,a,b) for i,(a,b) in enumerate(zip(actual,expected_body)) if a!=b][:24])
        want=surface(rows,view=self.value('fv_view'),focus=self.value('ui_selected'),count=count,
            ultimate=ultimate,phase=self.value('fc_phase'),caret=caret,help_text=help_text)
        actual=bytes(self.ram[0xc000:0xe400])
        assert actual==want,('palette',[(i,a,b) for i,(a,b) in enumerate(zip(actual,want)) if a!=b][:24])
        self.checked+=1

    def browser(self,*,device=9,fmt=0,selected=0,error=None):
        records=expected(self.io.files,device)
        want=browser_screen(40,records,selected,device,fmt,error,files_app=True)
        self.canvas(ascii_rows(want),count=min(8,max(0,len(records)-selected//8*8)))
        if not self.value('vd_phase'):
            assert self.screens[1]==self.footer(browser_screen(80,records,selected,device,fmt,error,files_app=True))

    def copy(self,source,name,**kwargs):
        view0=self.ram[self.symbol('fc_views')];view1=self.ram[self.symbol('fc_views')+1]
        caret=self.value('fc_caret')
        want=copy_screen(40,source,name,caret=caret,view=view0,graphical=True,**kwargs)
        self.canvas(ascii_rows(want),caret=caret-view0+7)
        if not self.value('vd_phase'):
            expected_console=self.footer(copy_screen(80,source,name,caret=caret,view=view1,graphical_controls=True,**kwargs))
            assert self.screens[1]==expected_console,('copy console',[(i,a,b) for i,(a,b) in enumerate(zip(self.screens[1],expected_console)) if a!=b][:24])
        assert self.name()==name and self.number('fc_copied')==kwargs.get('copied',0)
        assert self.number('fc_verified')==kwargs.get('verified',0)
        assert self.value('fc_status')==kwargs.get('status',0)

    def ultimate_browser(self,path,entries,*,base=0,selected=0,device=1,more=False,error=None):
        kw=dict(base=base,selected=selected,device=device,more=more,error=error,files_app=True)
        self.canvas(ascii_rows(ultimate_browser_screen(40,path,entries,**kw)),count=len(entries),ultimate=True)
        if not self.value('vd_phase'):
            assert self.screens[1]==self.footer(ultimate_browser_screen(80,path,entries,**kw))

    def preview(self,name,data,*,offset=0,eof=False):
        self.canvas(ascii_rows(preview_screen(40,name,data,offset,eof)))
        if not self.value('vd_phase'):
            assert self.screens[1]==self.footer(preview_screen(80,name,data,offset,eof))

    def form(self,view,value,*,caret=None,context=1):
        if caret is None:caret=len(value)
        assert self.value('fv_view')==view
        names={2:'b_device_state',3:'b_usb_state',4:'fc_device_state'}
        at=self.symbol(names[view]);viewport=self.ram[at+5]
        lines=['']*25
        lines[0]={2:'DEVICE: 8 TO 30',3:'DIRECTORY PATH; F1 CHANGES DOS',4:'DEVICE / DOS CONTEXT'}[view]
        if view==3:lines[1]='DOS: '+str(context)
        data=bytearray(screen_bytes(40,lines));data[7*40:7*40+38]=field_cells(value,38,caret,viewport)
        self.canvas(ascii_rows(data),caret=caret-viewport+1)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--case',choices=('all','keyboard','mouse','picker','fallback','fields','ultimate','modules',
        'longfields','gestures','retained','source','cancel','reservation'),default='all');args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    report=dict(passed=False,physical_hardware_io=False,cases=[],images={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [root/'target/native/kestrel.prg']+[root/f'target/native-desktop/{name}.prg' for name in ('files','fsview','fspick')]})
    def done(name,p):
        report['cases'].append(dict(name=name,keys=p.events,pointer_frames=p.frames,views=p.checked,
            module_calls=p.module_calls,instructions=p.instructions))
        print('PASS:',name,flush=True)
    try:
        if args.case in ('all','keyboard'):
            raw=bytes(range(256))*3+b'\0END'
            p=GraphicalFiles({(9,b'SOURCE',b'S'):raw});p.browser();assert p.value('ui_selected')==11
            p.key(ord('C'));p.copy(b'SOURCE',b'SOURCE');assert p.value('ui_selected')==25
            p.rename('COPY');p.copy(b'SOURCE',b'COPY')
            p.key(13);p.copy(b'SOURCE',b'COPY',copied=len(raw),verified=len(raw),status=1)
            assert bytes(p.io.files[9,b'COPY',b'S'])==raw
            p.key(13);p.copy(b'SOURCE',b'COPY',status=4,error=0x11,dos=63)
            p.key(27);p.browser();p.key(27,exited=True);p.restored()
            done('blue list and copy form, editing, verified copy, exclusive-name refusal and teardown',p)
        if args.case in ('all','mouse'):
            files={(9,f'FILE{i:02}'.encode(),b'S'):bytes([i])*20 for i in range(11)}
            p=GraphicalFiles(files);p.browser();p.frame();p.click(13);p.browser(selected=2)
            p.key(19)  # An unhandled list key must not steal later mouse focus.
            p.click(7);p.browser(selected=10);assert p.value('ui_selected')==7
            p.click(6);p.browser(selected=2);assert p.value('ui_selected')==6
            p.click(10);p.copy(b'FILE02',b'FILE02')
            p.click(25);p.rename('MOUSE COPY');p.copy(b'FILE02',b'MOUSE COPY')
            p.click(23);p.copy(b'FILE02',b'MOUSE COPY',copied=20,verified=20,status=1)
            p.click(24);p.browser(selected=2);p.click(0,exited=True);p.restored()
            done('mouse selection, directory paging, filename field, verified copy and desktop return',p)
        if args.case in ('all','picker'):
            p=GraphicalFiles({(9,b'SOURCE',b'S'):b'MODULE PICKER\0DATA'})
            p.key(ord('C'));p.rename('COPY');p.copy(b'SOURCE',b'COPY');before=p.preferences()
            keys=bytes(p.ram[0x1000:0x1100]);callback=bytes(p.ram[0x033c:0x033e])
            p.key(0x88);assert p.value('fg_kind')==2 and p.value('fc_picker_active') and not p.value('fg_bitmap')
            assert bytes(p.ram[0x1000:0x1100])==keys and bytes(p.ram[0x033c:0x033e])==callback
            p.key(27);assert p.value('fg_kind')==1 and p.preferences()==before
            p.copy(b'SOURCE',b'COPY');p.key(0x88);p.type('D10');p.key(13);p.type('S')
            p.copy(b'SOURCE',b'COPY',device=10);p.key(13)
            p.copy(b'SOURCE',b'COPY',device=10,copied=18,verified=18,status=1)
            p.key(27);p.key(27,exited=True);p.restored()
            done('replace graphics with picker and reload, retain keyboard ownership, choose another device and verify',p)
        if args.case in ('all','fallback'):
            p=GraphicalFiles({(9,b'SOURCE',b'S'):b'FALLBACK'},configure=lambda bus:bus.video.update({0xd015:4}))
            assert not p.value('fg_bitmap') and p.value('fg_error')==8
            p.key(ord('C'));p.rename('COPY');p.key(13)
            assert bytes(p.io.files[9,b'COPY',b'S'])==b'FALLBACK'
            p.key(27);p.key(27,exited=True)
            assert p.bus.video[0xd015]==4 and p.m.stats()==(175,251,32)
            done('foreign sprites refuse graphics while both text consoles retain copying and cleanup',p)
        if args.case in ('all','fields'):
            raw=bytes(range(256))+b'LAST PAGE'
            p=GraphicalFiles({(9,b'SOURCE',b'S'):raw,(10,b'OTHER',b'S'):b'OTHER'})
            p.key(ord('I'));p.preview(b'SOURCE',raw[:128])
            p.key(13);p.preview(b'SOURCE',raw[128:256],offset=128)
            p.key(13);p.preview(b'SOURCE',raw[256:],offset=256,eof=True)
            p.key(27);p.browser();p.key(ord('D'));p.form(2,b'')
            p.type('10');p.form(2,b'10');p.key(9);assert p.value('ui_selected')==26
            p.key(13);p.browser(device=10)
            p.key(ord('C'));p.key(0x85);p.form(4,b'');p.type('9');p.form(4,b'9')
            p.key(27);p.copy(b'OTHER',b'OTHER',source_device=10,device=10)
            p.key(27);p.key(27,exited=True);p.restored()
            done('complete 128-byte viewer pages, EOF, mouse-ready device fields, Tab confirmation and cancellation',p)
        if args.case in ('all','ultimate'):
            entries=[b'\x20'+f'FILE{i:02}'.encode() for i in range(11)]
            data={b'/Usb0/FILE00':b'ULTIMATE BYTES\0END'}
            dirs={b'/':[b'\x10Usb0'],b'/Usb0':entries}
            p=GraphicalFiles(usb=data,directories=dirs);p.type('FFF');p.ultimate_browser(b'/',dirs[b'/'])
            p.key(13);p.ultimate_browser(b'/Usb0',entries[:8],more=True)
            p.key(ord('N'));p.ultimate_browser(b'/Usb0',entries[8:],base=8)
            p.key(ord('B'));p.ultimate_browser(b'/Usb0',entries[:8],more=True)
            p.key(ord('G'));p.form(3,b'/Usb0');p.key(21);p.type('/Usb0');p.form(3,b'/Usb0')
            p.key(0x85);p.form(3,b'/Usb0',context=2);p.key(13)
            p.ultimate_browser(b'/Usb0',entries[:8],device=2,more=True)
            p.key(ord('C'));p.copy(b'/Usb0/FILE00',b'/Usb0/FILE00',source_device=2,source_format=3,device=1,fmt=3)
            p.rename('/COPY');p.key(13)
            p.copy(b'/Usb0/FILE00',b'/COPY',source_device=2,source_format=3,device=1,fmt=3,copied=18,verified=18,status=1)
            assert bytes(p.ultimate.files[b'/COPY'])==data[b'/Usb0/FILE00']
            p.key(27);p.key(27,exited=True);p.restored()
            done('Ultimate folders, every visible row, paging, editable path and DOS selection, two-context verified copy',p)
        if args.case in ('all','modules'):
            p=GraphicalFiles({(9,b'SOURCE',b'S'):b'RETAINED SOURCE'})
            p.key(ord('C'));p.rename('COPY')
            original=p.io.files[8,b'FSPICK.PRG',b'P'];p.io.files[8,b'FSPICK.PRG',b'P']=bytearray(original)
            p.io.files[8,b'FSPICK.PRG',b'P'][-1]^=1
            p.key(0x88);assert p.value('fc_active') and not p.value('fc_picker_active') and p.value('fc_status')==10
            assert p.name()==b'COPY' and p.value('fg_kind')==1 and p.value('fg_bitmap')
            assert not p.io.handles
            p.io.files[8,b'FSPICK.PRG',b'P']=original;p.key(0x88);assert p.value('fc_picker_active')
            p.key(27);p.copy(b'SOURCE',b'COPY')
            del p.io.files[8,b'FSVIEW.PRG',b'P'];p.key(0x88);p.key(27)
            assert p.value('fg_kind')==0 and not p.value('fg_bitmap') and p.name()==b'COPY'
            p.key(13);assert bytes(p.io.files[9,b'COPY',b'S'])==b'RETAINED SOURCE'
            p.key(27);p.key(27,exited=True)
            assert p.m.stats()==(175,251,32) and not p.value('nk_active')
            assert bytes(p.ram[0x1000:0x1100])==p.data('nk_saved_keys',256)
            done('corrupt picker rejected before entry, explicit retry, missing graphics returns to a usable copy dialog',p)
        if args.case in ('all','longfields'):
            source=b'/'+b'A'*254;raw=b'FULL LENGTH PATH\0DATA'
            directory=b'/Usb0/'+b'B'*121
            p=GraphicalFiles(usb={source:raw},directories={b'/':[b'\x20'+source[1:]],directory:[]})
            p.type('FFF');p.key(ord('C'))
            kwargs=dict(source_device=1,source_format=3,device=2,fmt=3)
            p.copy(source,source,**kwargs);assert p.value('fc_caret')==255
            p.key(ord('X'));p.copy(source,source,**kwargs)
            p.key(0x13);p.copy(source,source,**kwargs);assert p.value('fc_caret')==0
            p.key(0x1d);p.type('Z');p.copy(source,source,**kwargs)
            p.key(20);name=source[1:];p.copy(source,name,**kwargs)
            p.type('/');p.copy(source,source,**kwargs)
            # Total paths can reach 255 bytes; firmware create components
            # are limited to 127 bytes, independently of the editable field.
            name=directory+b'/'+b'C'*127;assert len(name)==255
            p.rename(name.decode());p.copy(source,name,**kwargs)
            p.frame();p.move(160,108);p.frame(down=True);p.frame(down=False)
            caret=p.value('fc_caret');assert 0<caret<255
            p.copy(source,name,**kwargs);p.key(20);name=name[:caret-1]+name[caret:]
            p.copy(source,name,**kwargs);p.key(13)
            p.copy(source,name,copied=len(raw),verified=len(raw),status=1,**kwargs)
            assert bytes(p.ultimate.files[name])==raw and bytes(p.ultimate.files[source])==raw
            p.key(27);p.key(ord('G'));p.key(21);p.type('/'+('P'*254));p.form(3,b'/'+b'P'*254)
            p.key(0x13);p.form(3,b'/'+b'P'*254,caret=0)
            p.key(21);p.type('/');p.form(3,b'/');p.key(27)
            p.key(27,exited=True);p.restored()
            done('255-byte raw paths, full-field refusal, both viewport ends, mouse caret, deletion and exact long-name copy',p)
        if args.case in ('all','gestures'):
            p=GraphicalFiles({(9,b'SOURCE',b'S'):b'GESTURE DATA'})
            p.frame();p.move(300,16);p.frame(down=True);p.move(300,180);p.frame(down=False)
            assert p.ram[0x3d20]==32
            p.key(ord('C'));p.rename('COPY');p.move(220,152);p.frame(down=True)
            p.key(27);p.frame(down=False);p.browser()
            assert (9,b'COPY',b'S') not in p.io.files and p.value('pm_arm')==255
            p.key(ord('C'));p.rename('COPY');p.key(9);assert p.value('ui_selected')==0
            for focus in (19,20,21,22,23):p.key(9);assert p.value('ui_selected')==focus
            p.key(13);p.copy(b'SOURCE',b'COPY',copied=12,verified=12,status=1)
            assert bytes(p.io.files[9,b'COPY',b'S'])==b'GESTURE DATA'
            p.key(27);p.key(27,exited=True);p.restored()
            done('drag outside cancels, keyboard modal exit disarms a held click, Tab visits enabled controls and Enter copies',p)
        if args.case in ('all','retained'):
            entries=[b'\x20'+f'FILE{i:02}'.encode() for i in range(12)]
            p=GraphicalFiles(usb={b'/FILE00':b'KEPT'},directories={b'/':entries})
            p.type('FFF');p.key(ord('C'));p.rename('/COPY');before=p.preferences();p.key(0x88)
            p.ultimate.ignore_abort=True;p.key(27)
            assert p.value('fg_kind')==2 and not p.value('fg_bitmap') and p.value('fc_picker_cursor')
            assert p.value('fc_status')==10 and p.preferences()==before
            window=p.data('files_module',16);cursor=p.data('fc_picker_cursor',4);commands=len(p.ultimate.commands)
            p.key(13);assert p.value('fc_status')==9 and b'/COPY' not in p.ultimate.files
            assert p.value('fg_kind')==2 and p.data('files_module',16)==window and p.data('fc_picker_cursor',4)==cursor
            assert len(p.ultimate.commands)==commands
            p.ultimate.ignore_abort=False;p.key(0x88);assert p.value('fc_picker_active')
            p.key(27);p.copy(b'/FILE00',b'/COPY',source_device=1,source_format=3,device=2,fmt=3)
            p.key(13);assert bytes(p.ultimate.files[b'/COPY'])==b'KEPT'
            p.key(27);p.key(27,exited=True);p.restored()
            done('failed picker abort retains its code and cursor, blocks replacement and copying, then retries cleanly',p)
        if args.case in ('all','source'):
            raw=b'SOURCE FOLDER KEPT\0DATA';path=b'/Apps/Original/FILES'
            p=GraphicalFiles({(9,b'SOURCE',b'S'):raw},source_path=path,source_context=2)
            assert p.loaded_source_commands and p.ram[0x3dbc]==2
            p.key(ord('C'));p.rename('COPY');p.key(0x88);p.type('D10');p.key(13);p.type('S')
            p.copy(b'SOURCE',b'COPY',device=10)
            opened=[command for command in p.loaded_source_commands+p.ultimate.commands if command[1]==2]
            assert [command[3:] for command in opened]==[path,b'/Apps/Original/FSVIEW.PRG',
                b'/Apps/Original/VDSVC.PRG',b'/Apps/Original/FSPICK.PRG',b'/Apps/Original/FSVIEW.PRG']
            assert all(command[0]==2 for command in opened)
            p.ultimate.inject[3]=lambda command,reply:[(b'',b'71,CLOSE ERROR')]
            p.key(0x88);assert p.value('fg_kind')==0 and p.ram[0x3d1b]==4 and not p.value('fg_bitmap')
            p.key(13);assert p.value('fc_status')==9 and (10,b'COPY',b'S') not in p.io.files
            p.ultimate.inject.clear();p.key(0x88);assert p.value('fc_picker_active')
            p.key(27);p.copy(b'SOURCE',b'COPY',device=10);p.key(13)
            assert bytes(p.io.files[10,b'COPY',b'S'])==raw
            p.key(27);p.key(27,exited=True);p.restored()
            done('Ultimate-loaded core and both modules retain the original source context/folder; uncertain module close blocks new I/O',p)
        if args.case in ('all','cancel'):
            raw=bytes(range(256))*16
            for phase in (1,2):
                p=GraphicalFiles({(9,b'SOURCE',b'S'):raw});p.key(ord('C'));p.rename('PARTIAL')
                p.frame();p.move(284,152);p.key(9);assert p.value('ui_selected')==25
                original=p.io.stub;stages=[]
                def stub(cpu):
                    if (cpu.pc==0xffe4 and p.value('fc_phase')==phase and len(stages)<4
                            and p.number('fc_copied' if phase==1 else 'fc_verified')>=512):
                        stage=len(stages);stages.append(p.number('fc_copied' if phase==1 else 'fc_verified'))
                        if stage%2==0:p.ram[0xa2]=(p.ram[0xa2]+1)&255
                        p.bus.raster=100 if stage%2==0 else 132
                        p.bus.down=stage<2
                    return original(cpu)
                p.io.stub=stub;p.key(13);p.io.stub=original;p.bus.raster=100
                assert len(stages)==4 and stages==[512,1024,1536,2048],stages
                p.copy(b'SOURCE',b'PARTIAL',copied=2048 if phase==1 else len(raw),
                    verified=2048 if phase==2 else 0,status=2,partial=True)
                assert bytes(p.io.files[9,b'PARTIAL',b'S'])==(raw[:2048] if phase==1 else raw)
                assert bytes(p.io.files[9,b'SOURCE',b'S'])==raw
                p.key(27);p.key(27,exited=True);p.restored()
                done('mouse Cancel during '+('copy' if phase==1 else 'verification')+' retains exact new bytes and consumes no keyboard shortcut',p)
        if args.case in ('all','reservation'):
            held=[];foreign=bytes((i*73+19)&255 for i in range(256))
            def reserve(machine):
                held.append(machine.alloc(1,0,16,page=0xc0))
                machine.ram[0xc000:0xc100]=foreign
            p=GraphicalFiles({(9,b'SOURCE',b'S'):b'RESERVATION'},configure_machine=reserve)
            assert not p.value('fg_bitmap') and p.value('fg_error')==2
            p.key(ord('C'));p.rename('COPY');p.key(13)
            assert bytes(p.io.files[9,b'COPY',b'S'])==b'RESERVATION'
            assert bytes(p.ram[0xc000:0xc100])==foreign
            p.key(27);stack=bytes(p.ram[0x100:0x200])
            p.m.select(held[0],16);p.m.invoke('release');p.ram[0x100:0x200]=stack
            p.key(ord('R'));p.browser();assert p.value('fg_error')==0
            p.key(27,exited=True);p.restored()
            done('foreign display reservation survives a fallback copy; explicit refresh acquires graphics after the owner releases it',p)
        report['passed']=True
    except BaseException as error:report['error']=repr(error);raise
    finally:args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
