#!/usr/bin/env python3
"""Shared bitmap picker through four real callers, full directories and faults."""
import argparse
import hashlib
import json
from pathlib import Path
import traceback
from ci_native_editor_gui import GraphicalEditor
from ci_native_editor import Editor
from ci_native_browser import expected
from ci_native_directory_ultimate import DirectoryDOS
from ci_native_ultimate import UltimateBus
from native_picker_fixture import Picker
from ci_native_calc import ROOT


def records(app,device=9):
    result=expected(app.io.files,device)
    for row in result:row['app']=False
    return result


def usb(app,directories,files=None):
    app.ultimate=DirectoryDOS(files=files);app.ultimate.directories.update(directories)
    app.m.bus=UltimateBus(app.m.bus,app.ultimate);app.cpu.memory=app.m.bus


def heap_state(app):
    return tuple(sum(v==0 for v in app.ram[table:table+256]) for table in (0x3800,0x3900))+(sum(app.ram[0x3c00+i*8]==0 for i in range(32)),)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--case',choices=['keyboard','mouse','paths','large','formats','callers','fallback'],required=True);parser.add_argument('--report',type=Path,required=True);a=parser.parse_args()
    result=dict(passed=False,physical_hardware_io=False,cases=[],images={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ['target/native','target/native-desktop'] for p in (ROOT/folder).iterdir() if p.suffix in ('.prg','.d64')})
    def done(name,p):
        app=p.app;result['cases'].append(dict(name=name,frames=p.frames,checked=p.checked,keys=app.events,instructions=app.instructions));print('PASS:',name,flush=True)
    try:
        files={(9,f'FILE{i:03}'.encode(),b'S'):bytes([i])*3 for i in range(20)}
        if a.case in ('keyboard','mouse'):
            e=GraphicalEditor(files,device=9);p=Picker(e);e.type('KEEP');e.key(0x86);e.type('COPY');saved=p.preferences();before=e.contents();state=e.data('ed_field_len',8) if hasattr(e,'data') else bytes(e.ram[e.symbol('ed_field_len'):e.symbol('ed_field_len')+8])
            e.key(0x88);rows=records(e);p.check(rows,mode=2,focus=4)
            if a.case=='keyboard':
                e.key(ord('N'));p.check(rows,mode=2,selected=8)
                e.key(ord('B'));p.check(rows,mode=2,selected=0)
                e.key(9);p.check(rows,mode=2,selected=0,focus=5)
                e.key(13);assert e.string('ed_field')=='FILE001'
                e.check(before,4,True,mode=2)
                e.key(0x88);p.check(rows,mode=2,focus=4)
                e.key(ord('D'));p.check(rows,mode=2,prompt=1,field='',focus=19)
                e.type('10');p.check(rows,mode=2,prompt=1,field='10',focus=19)
                e.key(13);p.check(records(e,10),mode=2,device=10)
                e.key(ord('S'));assert e.string('ed_field')=='FILE001' and e.value('ed_device')==10
                assert p.preferences()==saved
                e.key(13);e.check(before,4,False,mode=0,name='FILE001');assert bytes(e.io.files[10,b'FILE001',b'S'])==before
                e.exit();e.restored();done('keyboard focus, full page navigation, editable device, Use Here and verified save',p)
            else:
                p.frame();p.click(7);p.check(rows,mode=2,selected=3,focus=7)
                p.move(250,175);p.frame(down=True);p.move(300,130);p.frame(down=False)
                p.check(rows,mode=2,selected=3)
                p.move(52,172);p.frame(down=True);e.key(9);p.frame(down=False)
                p.check(rows,mode=2,selected=3,focus=17)
                p.click(1);p.check(rows,mode=2,prompt=1,focus=19,selected=3)
                e.type('10');p.check(rows,mode=2,prompt=1,field='10',selected=3)
                p.click(18);p.check(rows,mode=2,selected=3)
                p.click(18);e.check(before,4,True,mode=2)
                assert p.preferences()==saved and bytes(e.ram[e.symbol('ed_field_len'):e.symbol('ed_field_len')+8])==state
                e.key(27);e.exit(dirty=True);e.restored();done('mouse row selection, cancelled drag, field and modal Cancel preserve caller',p)
        elif a.case=='paths':
            parent=b'/'+b'A'*124+b'/'+b'B'*124;assert len(parent)==250
            entries=[b'\x20'+f'NAME{i:03}'.encode() for i in range(19)]
            e=GraphicalEditor(device=9);usb(e,{b'/':[],parent:entries});p=Picker(e)
            e.type('KEPT');before=e.contents()
            for _ in range(3):e.key(0x8b)
            e.key(0x86);e.type('/COPY');e.key(0x88);p.check(mode=2,fmt=3,device=1,path=b'/',entries=[])
            e.key(ord('G'));p.check(mode=2,prompt=3,fmt=3,device=1,path=b'/',entries=[],field='/')
            e.key(21);e.type(parent.decode());p.check(mode=2,prompt=3,fmt=3,device=1,path=b'/',entries=[],field=parent.decode())
            p.frame();p.click(19);assert p.value('b_usb_cursor')<250
            e.key(5);e.key(0x85);p.check(mode=2,prompt=3,fmt=3,device=1,path=b'/',entries=[],field=parent.decode(),prompt_device=2)
            e.key(13);p.check(mode=2,fmt=3,device=2,path=parent,entries=entries[:8],more=True)
            e.key(ord('N'));p.check(mode=2,fmt=3,device=2,path=parent,entries=entries[8:16],base=8,more=True)
            e.key(ord('G'));e.key(21);e.type('/MISSING');e.key(13)
            p.check(mode=2,fmt=3,device=2,path=parent,entries=entries[8:16],base=8,more=True,error='DISK I/O ERROR')
            e.key(ord('S'));assert e.string('ed_field')==parent.decode()+'/COPY';e.check(before,4,True,mode=2)
            e.key(27);e.exit(dirty=True);e.restored();done('long raw path, mouse caret, both DOS contexts, page navigation and failed path recovery',p)
        elif a.case=='large':
            raw=(b'0123456789 ABCDEFGHIJKLMNOPQRSTUVWXYZ\r\n'*1800)[:66053]
            files={(9,f'FILE{i:03}'.encode(),b'S'):bytes([i&255]) for i in range(295)};files[9,b'LARGE',b'S']=raw
            e=GraphicalEditor(files,device=9,fmt=2);e.io.formats[10]=2;e.prompt(0x85,'LARGE');e.prompt(0x88,'010001');at=e.number('ed_cursor');e.type('C128');want=raw[:at]+b'C128'+raw[at:]
            e.check(want,at+4,True);p=Picker(e);e.key(0x86);e.type('COPY');saved=p.preferences();heap_before=heap_state(e);e.key(0x88)
            rows=records(e);assert len(rows)==296;p.check(rows,mode=2,fmt=2)
            for page in range(1,37):
                e.key(ord('N'));p.check(rows,mode=2,fmt=2,selected=page*8);assert e.contents()==want
            cached=sum(e.ram[0x3c00+(tag-1)*8+3] for tag in p.data('b_cache',40)[::4] if tag)
            assert cached==19,(cached,heap_state(e));result['capacity']=dict(entries=296,document_bytes=len(want),banked_picker_pages=cached,heap_at_picker=heap_state(e))
            e.key(27);e.check(want,at+4,True,mode=2);assert heap_state(e)==heap_before and p.preferences()==saved
            e.key(0x88);e.type('D10');e.key(13);e.key(ord('S'))
            e.key(13)
            assert e.value('ed_status')==1,('save',e.value('ed_status'),e.value('ed_device'),e.value('ed_format'),e.io.formats)
            e.check(want,at+4,False,name='COPY');assert bytes(e.io.files[10,b'COPY',b'S'])==want
            assert bytes(e.io.files[9,b'LARGE',b'S'])==raw
            e.exit();e.restored();done('full 296-entry D81 beside edited >64 KiB document, exact cache release and verified save',p)
        elif a.case=='formats':
            e=GraphicalEditor({(9,f'FILE{i:03}'.encode(),b'S'):bytes([i&255]) for i in range(296)},device=9,fmt=2)
            entries=[b'\x20'+f'USB{i:03}'.encode() for i in range(24)];usb(e,{b'/':entries});p=Picker(e)
            e.key(0x85);e.key(0x88);p.check(records(e),fmt=2)
            e.key(ord('F'));p.check(fmt=3,device=1,path=b'/',entries=entries[:8],more=True)
            e.key(ord('N'));p.check(fmt=3,device=1,path=b'/',entries=entries[8:16],base=8,more=True)
            full=dict(e.io.files)
            def change_disk(fmt,count):
                e.io.files={k:v for k,v in full.items() if k[0]!=9 or int(k[1][4:])<count};e.io.formats[9]=fmt
            change_disk(0,144);e.key(ord('F'));p.check(records(e),fmt=0)
            change_disk(1,144);e.key(ord('F'));p.check(records(e),fmt=1)
            change_disk(2,296);e.key(ord('F'));p.check(records(e),fmt=2)
            e.key(27);e.key(27);e.exit();e.restored();done('IEC/Ultimate cache reuse across formats retains complete directory capacity',p)
        elif a.case=='callers':
            from ci_native_files_gui import GraphicalFiles
            from ci_native_paint_gui import GraphicalPaint
            from ci_native_paint_files import pattern
            from native_paint_format import encode
            from ci_native_controls_gui import GraphicalPanel
            f=GraphicalFiles({(9,b'SOURCE',b'S'):bytes(range(256))*3});p=Picker(f);f.key(ord('C'));f.rename('COPY');saved=p.preferences();f.key(0x88)
            p.check(records(f),mode=2);p.frame();p.click(1);f.type('10');p.click(16);p.check(records(f,10),mode=2,device=10)
            p.click(17);assert p.preferences()==saved;f.key(13);assert bytes(f.io.files[10,b'COPY',b'S'])==bytes(range(256))*3
            f.key(27);f.key(27,exited=True);f.restored();done('Files graphical destination picker and complete multi-buffer verified copy',p)
            f=GraphicalPaint(files={(9,b'PICTURE',b'S'):encode(pattern(21))},device=9);p=Picker(f);f.key(ord('O'));p.check(records(f));p.frame();p.click(16)
            f.check();assert f.document()==pattern(21);f.close();f.restored();done('Paint shared font/pointer picker stages exact full image and restores its canvas',p)
            f=GraphicalPanel();f.device.directories[b'/']=[b'\x10Usb0'];p=Picker(f);f.key(ord('D'));f.key(0x11);f.key(ord('M'))
            p.check(fmt=3,device=1,path=b'/',entries=[b'\x10Usb0']);p.frame();p.click(16)
            p.check(fmt=3,device=1,path=b'/Usb0',entries=[b'\x20work.d64']);p.click(16)
            assert f.value('ug_mode')==1 and not f.device.mutations;f.check();f.key(27);f.close();f.restored();done('Ultimate shared pointer picker returns to explicit full-path drive confirmation',p)
        elif a.case=='fallback':
            held=[];foreign=bytes((i*73+19)&255 for i in range(256))
            def reserve(m):held.append(m.alloc(1,0,16,page=0xc0));m.ram[0xc000:0xc100]=foreign
            e=GraphicalEditor(files,device=9,configure_machine=reserve);usb(e,{b'/':[]});p=Picker(e);e.type('KEPT');e.key(0x86);e.type('COPY');e.key(0x88)
            assert p.active() and not p.value('pg_bitmap') and p.value('pg_error')==2 and bytes(e.ram[0xc000:0xc100])==foreign
            e.type('FFF');e.key(0x85);assert e.ram[0x3d29:0x3d2b]==bytes([2,3]) and not p.value('pg_bitmap')
            e.key(ord('F'))
            saved=bytes(e.ram[0x100:0x200]);e.m.select(held[0],16);e.m.invoke('release');e.ram[0x100:0x200]=saved
            e.key(ord('R'));p.check(records(e),mode=2)
            e.key(27);e.check(b'KEPT',4,True,mode=2);e.key(27);e.exit(dirty=True);e.restored();done('foreign surface remains intact; explicit refresh acquires graphics and returns safely',p)
        result['passed']=True
    except BaseException:result['error']=traceback.format_exc();raise
    finally:a.report.write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()
