#!/usr/bin/env python3
"""Execute filename search through the loaded Files module and real services."""
import argparse
import json
from pathlib import Path

import ci_native_files_gui as gui
from ci_native_vdc_files import Files as VDCFiles, VDCBus
from native_browser_check import screen_bytes
from native_files_find_check import rows, bitmap

CAPTURES = None
CAPTURE_COUNT = 0


def fixture(files=None, *, size=None, **kwargs):
    old = gui.PointerBus
    if size:
        gui.PointerBus = type('FindVDC', (VDCBus,), dict(size=size))
    try:
        p = (VDCFiles if size else gui.GraphicalFiles)(files, **kwargs)
    finally:
        gui.PointerBus = old
    p.checked_find = 0
    return p


def dialog(p, query=b'', *, result=7, device=9, ultimate=False, path=b'/Usb0',
           error=0, dos=0, status=b''):
    global CAPTURE_COUNT
    assert p.value('fm_active') == 2 and p.value('fv_view') == 8
    assert not p.value('fm_sent')
    assert p.value('fm_result') == result
    assert p.value('fm_error') == error
    assert p.data('fm_name', p.value('fm_length')) == query
    assert p.ram[0x3d1b] == 3, 'search must retain the checked module'
    field = p.data('fm_state', 8)
    assert field[0] == len(query)
    args = dict(result=result,device=device,ultimate=ultimate,path=path,
                error=error,dos=dos,status=status,caret=field[1],viewport=field[5])
    text = rows(query, **args)
    assert p.data('fv_body',1000) == b''.join(text), 'complete search formatter'
    expected = bitmap(query,focus=p.value('ui_selected'),**args)
    actual = bytes(p.ram[0xc000:0xe400])
    assert actual == expected, ('complete search bitmap',
        [(i,a,b) for i,(a,b) in enumerate(zip(actual,expected)) if a!=b][:16])
    if isinstance(p,VDCFiles):
        p.mirror()
    else:
        body=bytearray(v-64 if 64<=v<96 else v-32 if 96<=v<128 else v
                       for v in b''.join(text))
        if p.value('ui_selected')==25:
            body[280+field[1]-field[5]+1]|=128
        console=bytearray(screen_bytes(80,['']*25))
        for row in range(13):console[row*80:row*80+40]=body[row*40:row*40+40]
        console=p.footer(console)
        assert p.screens[1]==console,'complete fallback console'
    if CAPTURES is not None:
        prefix=f'{CAPTURE_COUNT:03d}';CAPTURE_COUNT+=1
        (CAPTURES/(prefix+'-actual.vic')).write_bytes(actual)
        (CAPTURES/(prefix+'-expected.vic')).write_bytes(expected)
        meta=dict(query_hex=query.hex(),result=result,device=device,ultimate=ultimate,
                  caret=field[1],viewport=field[5],focus=p.value('ui_selected'),
                  vdc_size=p.bus.size if isinstance(p,VDCFiles) else 0)
        if isinstance(p,VDCFiles):
            (CAPTURES/(prefix+'-vdc.bin')).write_bytes(p.bus.bytes(p.value('vd_base')*256,16000))
            if p.bus.size==64:(CAPTURES/(prefix+'-attributes.bin')).write_bytes(p.bus.bytes(0x8000,2000))
            meta.update(pointer_x=p.position[0],pointer_y=p.position[1],pointer_visible=bool(p.value('vd_pointer_visible')))
        else:
            (CAPTURES/(prefix+'-actual.console')).write_bytes(p.screens[1])
            (CAPTURES/(prefix+'-expected.console')).write_bytes(console)
        (CAPTURES/(prefix+'.json')).write_text(json.dumps(meta,indent=2)+'\n')
    p.checked_find+=1


def start(p, query):
    p.key(6)
    p.key(21)
    p.type(query.decode('ascii'))


def main():
    global CAPTURES
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--group',choices=('all','iec','ultimate','failures','safety','vdc16','vdc64'),default='all')
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    CAPTURES=args.report.with_name(args.report.stem+'-captures');CAPTURES.mkdir(exist_ok=False)
    report=dict(passed=False,physical_hardware_io=False,cases=[])
    def done(name,p):
        report['cases'].append(dict(name=name,keys=p.events,instructions=p.instructions,
                                   views=p.checked,search_frames=p.checked_find))
        args.report.write_text(json.dumps(report,indent=2)+'\n');print('PASS:',name,flush=True)
    try:
        if args.group in ('all','iec'):
            files={(9,f'FILE{i:03d}'.encode(),b'S'):bytes([i%256]) for i in range(296)}
            p=fixture(files,fmt=2);p.browser(fmt=2)
            p.key(6);dialog(p);p.key(13);dialog(p,result=12)
            p.type('file29');dialog(p,b'file29');before=p.io.reads;p.key(13)
            p.browser(fmt=2,selected=290);assert p.io.reads==before,'IEC search must use the complete retained snapshot'
            p.key(6);dialog(p,b'file29');p.key(13);p.browser(fmt=2,selected=291)
            start(p,b'file000');p.key(13);p.browser(fmt=2,selected=0)
            done('296-entry D81 snapshot, substring case folding, repeated search and wrap',p)
            before=p.preferences();start(p,b'absent');p.key(13);dialog(p,b'absent',result=8)
            assert p.preferences()==before and p.number('b_selected',2)==0
            p.key(27);p.browser(fmt=2);p.key(27,exited=True);p.restored()
            done('empty query and no match preserve the listing, selection and resources',p)

            names=[b'FIRST',b'AB\xc3\xc4END',b'WILD*CARD',b'LAST']
            p=fixture({(9,n,b'S'):b'KEEP' for n in names})
            start(p,b'cdend');p.key(13);p.browser(selected=1)
            start(p,b'*');p.key(13);p.browser(selected=2)
            p.key(27,exited=True);p.restored()
            done('PETSCII alternate alphabet and literal wildcard characters',p)

        if args.group in ('all','ultimate'):
            entries=[b'\x20'+f'ITEM{i:04d}'.encode() for i in range(521)]
            entries[260]=b'\x20'+b'Q'*250+b'tailZ'
            entries[520]=b'\x10Last Folder'
            p=fixture(directories={b'/':entries});p.type('FFF')
            start(p,b'item0259');dialog(p,b'item0259',ultimate=True,device=1,path=b'/')
            p.key(13);p.ultimate_browser(b'/',entries[256:264],base=256,selected=3,more=True)
            assert p.number('bu_base')==256 and p.value('bu_row')==3
            start(p,b'tailz');p.key(13);p.ultimate_browser(b'/',entries[256:264],base=256,selected=4,more=True)
            start(p,b'last folder');p.key(13);p.ultimate_browser(b'/',entries[520:],base=520)
            assert not p.value('bu_cursor')
            start(p,b'item0001');p.key(13);p.ultimate_browser(b'/',entries[:8],selected=1,more=True)
            done('521 streamed entries, 32-bit ordinals, full 255-byte names, directories and wrap',p)
            p.key(0x85);start(p,b'item0017');p.key(13)
            p.ultimate_browser(b'/',entries[16:24],base=16,selected=1,more=True,device=2)
            before=p.preferences();start(p,b'not here');p.key(13)
            dialog(p,b'not here',result=8,ultimate=True,device=2,path=b'/')
            assert p.preferences()==before and not p.value('bu_cursor')
            p.key(27);p.key(27,exited=True);p.clean();p.restored()
            done('DOS context 2 and absent matches preserve full selection and close owned cursors',p)

        if args.group in ('all','vdc16','vdc64'):
            sizes=(16,64) if args.group=='all' else (int(args.group[3:]),)
            for size in sizes:
                p=fixture({(9,b'FIRST',b'S'):b'1',(9,b'SECOND',b'S'):b'2'},size=size)
                p.frame();p.click(31);dialog(p)
                p.type('sec');dialog(p,b'sec');p.click(26);p.browser(selected=1)
                p.click(31);dialog(p,b'sec');p.click(27);p.browser(selected=1)
                p.key(27,exited=True);p.restored()
                done(f'{size} KiB VDC, button 31 boundary, mouse Find/Back and exact screen restore',p)

        if args.group in ('all','failures'):
            entries=[b'\x20'+f'NAME{i:04d}'.encode() for i in range(65)]
            p=fixture(directories={b'/':entries});p.type('FFF');before=p.preferences()
            start(p,b'NAME0060')
            original=p.io.stub;fired=[]
            def cancel(cpu):
                if cpu.pc==0xffe4 and p.value('fg_searching') and not fired:
                    fired.append(True);p.keys.append(27)
                return original(cpu)
            p.io.stub=cancel;p.observation_target=None
            p.keys.append(13);p.loop();p.events+=2;p.io.stub=original
            assert int.from_bytes(p.ram[0x3d13:0x3d15],'little')==p.events
            assert p.cpu.pc==0xffe4 and p.ram[0x3d12]==1
            assert fired and p.preferences()==before
            dialog(p,b'NAME0060',result=10,ultimate=True,device=1,path=b'/')
            assert not p.value('bu_cursor') and p.ultimate.paths=={1:b'/shell',2:b'/browser'}
            p.key(13);p.ultimate_browser(b'/',entries[56:64],base=56,selected=4,more=True)
            done('cancel an active directory search, keep the published page and retry',p)

            before=p.preferences();start(p,b'NAME0001')
            p.ultimate.inject[0x14]=lambda command,reply:[(b'\x20BAD\0NAME',b'00,OK')]
            p.key(13);dialog(p,b'NAME0001',result=11,error=0x11,ultimate=True,device=1,path=b'/')
            assert p.preferences()==before and not p.value('bu_cursor')
            del p.ultimate.inject[0x14]
            p.key(13);p.ultimate_browser(b'/',entries[:8],selected=1,more=True)
            done('malformed directory replies preserve the old page and allow a clean retry',p)

            start(p,b'NAME0064');p.key(13);assert not p.value('bu_cursor')
            before=p.preferences();start(p,b'NAME0001')
            commands=len(p.ultimate.commands);aborts=p.ultimate.cancel_attempts
            p.ultimate.state=0x10;p.ultimate.stuck=True;p.key(13)
            dialog(p,b'NAME0001',result=11,error=0x15,ultimate=True,device=1,path=b'/')
            assert len(p.ultimate.commands)==commands and p.ultimate.cancel_attempts==aborts
            assert p.preferences()==before and not p.value('bu_cursor')
            p.ultimate.state=0;p.ultimate.stuck=False;p.key(27)
            done('foreign transaction refused without a packet, abort or selection change',p)
            p.key(27,exited=True);p.clean();p.restored()
        if args.group in ('all','safety'):
            entries=[b'\x20'+f'NAME{i:04d}'.encode() for i in range(65)]
            p=fixture(directories={b'/':entries});p.type('FFF');before=p.preferences()
            start(p,b'NAME0060');p.frame();p.move(284,152)
            for _ in range(4):
                if p.value('ui_selected')==25:break
                p.key(9)
            assert p.value('ui_selected')==25
            original=p.io.stub;phase=[0];armed=[]
            def mouse_cancel(cpu):
                if cpu.pc==0xffe4 and p.value('fg_searching'):
                    if phase[0]==0 and p.value('bu_new_count')>=3:
                        dialog(p,b'NAME0060',result=9,ultimate=True,device=1,path=b'/')
                        p.bus.down=True;p.ram[0xa2]=(p.ram[0xa2]+1)&255;p.bus.raster=100;phase[0]=1
                    elif phase[0]==1:
                        p.bus.raster=132
                        if p.value('pm_arm')==27:
                            armed.append(True);p.bus.down=False
                            p.ram[0xa2]=(p.ram[0xa2]+1)&255;p.bus.raster=100;phase[0]=2
                    elif phase[0]==2:p.bus.raster=132
                return original(cpu)
            p.io.stub=mouse_cancel;p.observation_target=None;p.keys.append(13);p.loop();p.events+=1;p.io.stub=original
            assert armed and int.from_bytes(p.ram[0x3d13:0x3d15],'little')==p.events
            assert p.preferences()==before and not p.value('bu_cursor')
            dialog(p,b'NAME0060',result=10,ultimate=True,device=1,path=b'/')
            p.key(27);p.ultimate_browser(b'/',entries[:8],more=True)
            done('1351 Back cancels after partial page writes with no extra keyboard event',p)

            p.key(ord('R'));cursor=p.data('bu_cursor',4);assert cursor[0]
            before=p.preferences();start(p,b'NAME0001')
            reads=sum(c[1]==0x14 for c in p.ultimate.commands)
            p.ultimate.ignore_abort=True;p.key(13)
            dialog(p,b'NAME0001',result=11,error=0x11,ultimate=True,device=1,path=b'/')
            assert p.preferences()==before and p.data('bu_cursor',4)==cursor
            assert sum(c[1]==0x14 for c in p.ultimate.commands)==reads
            p.ultimate.ignore_abort=False;p.key(13)
            p.ultimate_browser(b'/',entries[:8],selected=1,more=True)
            p.key(27,exited=True);p.clean();p.restored()
            done('uncertain cursor close retains ownership and blocks a new scan until recovery',p)

            p=fixture({(9,b'FIRST',b'S'):b'1',(9,b'SECOND',b'S'):b'2'},size=16)
            start(p,b'SECOND');p.bus.stall=True;p.key(13)
            assert p.value('fm_active')==2 and p.value('vd_fault') and p.value('b_selected')==0
            p.key(ord('A'));assert p.value('b_selected')==0
            p.bus.stall=False;p.vdc_expected=False
            original=p.cpu.step;restored=[]
            def restore_before_text():
                if p.cpu.pc==p.symbol('fm_leave'):
                    assert p.value('vd_phase')==0 and p.bus.video_ram==p.bus.original[0]
                    restored.append(True)
                return original()
            p.cpu.step=restore_before_text;p.key(27);p.cpu.step=original
            assert restored==[True] and not p.value('fg_searching')
            p.bus.original=None;p.key(27,exited=True);p.restored()
            done('failed VDC presentation freezes search and restores every screen byte before text resumes',p)
        report['passed']=True
    finally:
        args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
