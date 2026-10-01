#!/usr/bin/env python3
"""Exercise byte-range selection through actual Editor keys and 1351 input."""
import argparse
import hashlib
import json
from pathlib import Path
import traceback

import ci_native_editor_gui as gui
from native_editor_check import document_lines


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=('keyboard','replace','mouse','large','fallback','capacity','edges','display'),required=True)
    parser.add_argument('--vdc-kib',type=int,choices=(16,64))
    parser.add_argument('--reu-kib',type=int,choices=(128,512,16384))
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    report=dict(passed=False,physical_hardware_io=False,cases=[],vdc_kib=args.vdc_kib,reu_kib=args.reu_kib,
                images={str(p.relative_to(gui.ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in (gui.ROOT/'target/native-desktop').glob('*.prg')})
    factory=gui.GraphicalEditor
    if args.vdc_kib:
        from ci_native_vdc_editor import Editor
        from ci_native_vdc_desktop import VDCBus
        base=VDCBus;options=dict(size=args.vdc_kib,addressing=16)
        if args.reu_kib:
            from ci_native_reu_calc import CalculatorBus
            base=CalculatorBus;options['reu_kib']=args.reu_kib
        gui.PointerBus=type('SelectionVDC',(base,),options)
        factory=Editor
        if args.case=='display':
            from ci_native_vdc_editor_recovery import RecoveryEditor
            factory=RecoveryEditor
    if args.case=='display':assert args.vdc_kib
    try:
        raw=b'ONE\r\nTwo words\nTHREE\rLAST'
        if args.case=='mouse':raw=b''.join(f'LINE {n:02} abcdefghijklmnopqrstuvwxyz\r\n'.encode() for n in range(28))
        if args.case=='edges':raw=(b'0123456789'*10+b'\r\r\nX\n')*9
        if args.case=='capacity':raw=(b'0123456789ABCDEF\r\n'*300)[:4096]
        if args.case=='large':raw=(b'0123456789 ABCDEFGHIJ\r\n'*6300)[:131118]
        files={(9,b'SOURCE',b'S'):raw}
        e=factory(files,device=9,fmt=2)
        key_costs=[];original_key=e.key
        def profiled_key(value,exited=False):
            before=e.instructions;result=original_key(value,exited=exited)
            key_costs.append(dict(key=value,instructions=e.instructions-before))
            return result
        e.key=profiled_key
        e.prompt(0x85,'SOURCE');e.check(raw,0,False,name='SOURCE')
        print('Selection editor ready:',args.case,flush=True)
        if args.case=='keyboard':
            e.key(2);e.check(raw,0,False,selection=(0,0));assert e.value('es_mark')
            for _ in range(3):e.key(0x1d)
            e.check(raw,3,False,selection=(0,3))
            e.key(0x1d);e.check(raw,5,False,selection=(0,5))
            e.key(2);e.check(raw,5,False,selection=(0,5));assert not e.value('es_mark')
            e.key(0x9d);e.check(raw,0,False)
            e.key(1);e.check(raw,len(raw),False,selection=(0,len(raw)))
            e.prompt(0x86,'COPY');e.check(raw,len(raw),False,name='COPY',status=1,selection=(0,len(raw)))
            assert bytes(e.io.files[9,b'COPY',b'S'])==raw
            e.key(27);e.check(raw,len(raw),False)
            # The third toolbar page exposes the same actions to mouse users.
            e.frame();e.click(5);e.click(5);assert e.value('eg_more')==2
            e.click(22);e.check(raw,len(raw),False,selection=(0,len(raw)))
            e.click(23);e.check(raw,len(raw),False)
            e.click(22);e.type('K');e.check(b'K',1,True);assert e.value('ui_selected')==6
            e.prompt(0x86,'TYPED');e.check(b'K',1,False,name='TYPED',status=1)
            e.key(1);e.click(0,exited=True);e.restored()
        elif args.case=='replace':
            e.key(1);e.type('Z');e.check(b'Z',1,True)
            e.key(1);e.key(13);e.check(b'\r\n',2,True)
            e.key(1);e.key(20);e.check(b'',0,True)
            e.key(2);e.type('a');e.check(b'a',1,True)
            e.type('bcde');e.key(2);e.key(20);e.check(b'abcd',4,True)
            e.key(2);e.key(0x9d);e.key(0x9d)
            e.check(b'abcd',2,True,selection=(2,4))
            e.type('X');e.check(b'abX',3,True)
            e.prompt(0x86,'EDITED');e.check(b'abX',3,False,status=1,name='EDITED')
            assert bytes(e.io.files[9,b'EDITED',b'S'])==b'abX'
            e.exit();e.restored()
        elif args.case=='mouse':
            e.frame();e.move(24,60);e.frame(down=True)
            e.check(raw,2,False,selection=(2,2))
            e.move(64,68);e.frame(down=False)
            end=document_lines(raw)[1][0]+7
            e.check(raw,end,False,selection=(2,end))
            e.type('M');want=raw[:2]+b'M'+raw[end:]
            e.check(want,3,True)
            # A keyboard action takes ownership from a held drag. Releasing
            # the mouse afterward must not replay its old document click.
            e.move(24,60);e.frame(down=True);e.move(40,60)
            e.key(1);e.frame(down=False)
            e.check(want,len(want),True,selection=(0,len(want)))
            e.key(7);e.key(0x89)
            # Drag across the viewport edge: each held sample scrolls and the
            # release over another control must never activate that control.
            e.move(40,60);e.frame(down=True);start=e.number('ed_cursor')
            e.move(40,190)
            before=e.number('ed_view')
            for _ in range(3):e.frame(down=True)
            assert e.number('ed_view')>before
            end=e.number('ed_cursor');e.frame(down=False)
            e.check(want,end,True,mode=0,selection=(start,end))
            assert not e.value('es_drag') and not e.value('es_mark')
            e.key(7);e.exit(dirty=True);e.restored()
        elif args.case=='large':
            at=65530;e.prompt(0x88,f'{at:06X}');e.key(2)
            end=at
            for _ in range(14):
                end+=2 if raw[end:end+2]==b'\r\n' else 1
                e.key(0x1d)
            assert end>65535
            e.check(raw,end,False,selection=(at,end))
            e.type('!');want=raw[:at]+b'!'+raw[end:]
            e.check(want,at+1,True)
            e.prompt(0x86,'LARGE COPY');e.check(want,at+1,False,status=1,name='LARGE COPY')
            assert bytes(e.io.files[9,b'LARGE COPY',b'S'])==want
            e.key(1);e.key(20);e.check(b'',0,True)
            e.exit(dirty=True);e.restored()
        elif args.case=='display':
            from ci_native_vdc_editor_recovery import paused,ignored,restore
            e.key(1);e.check(raw,len(raw),False,selection=(0,len(raw)))
            selection=e.data('es_active',13)
            view=dict(data=raw,cursor=len(raw),name='SOURCE',dirty=False,
                      view=e.number('ed_view'),horizontal=e.number('ed_horizontal'),selection=(0,len(raw)))
            e.bus.stall=True;e.key(9);paused(e,document_view=view)
            ignored(e,keys=(ord('Q'),13,27,7))
            assert e.data('es_active',13)==selection
            assert restore(e,lambda:e.key(27))
            assert e.contents()==raw and not e.value('es_active') and not e.value('ed_mode')
            # restore() compares every saved VDC byte before the first text
            # output. The resumed editor then legitimately repaints that RAM.
            e.bus.original=None;e.key(12);e.check(raw,len(raw),False)
            e.exit();e.restored()
        elif args.case=='edges':
            e.prompt(0x88,'000040');e.frame();e.move(104,60)
            def endpoint(x,y):
                rows=document_lines(raw);first=[row[0] for row in rows].index(e.number('ed_view'))
                line=max(0,min(len(rows)-1,first+(-1 if y<56 else 16 if y>=184 else (y-56)//8)))
                col=e.number('ed_horizontal')+max(0,x//8-1)
                if x<8 and e.number('ed_horizontal'):col-=1
                return rows[line][0]+min(len(rows[line][1]),col)
            anchor=endpoint(*e.position);e.frame(down=True)
            e.check(raw,anchor,False,selection=(anchor,anchor))
            points=[]
            for target in ((0,60),(0,68),(0,60),(0,20),(319,20),(319,100),(40,190),(40,20)):
                while e.position!=target:
                    x,y=e.position;dx=max(-20,min(20,target[0]-x));dy=max(-20,min(20,target[1]-y))
                    want=endpoint(x+dx,y+dy);e.frame(dx,dy)
                    assert e.number('ed_cursor')==want,(target,e.position,e.number('ed_cursor'),want)
                    assert not (raw[want-1:want+1]==b'\r\n')
                points.append((target,want));e.check(raw,want,False,selection=tuple(sorted((anchor,want))))
            e.frame(down=False);e.check(raw,want,False,selection=tuple(sorted((anchor,want))))
            e.key(7);e.exit();e.restored()
            report['edge_points']=points
        elif args.case=='capacity':
            assert not e.state()['backing'] and e.state()['capacity']==len(raw)==4096
            held=[]
            stack=bytes(e.ram[0x100:0x200])
            for bank in (0,1):
                table=e.ram[0x3800+bank*256:0x3900+bank*256]
                start=0
                while start<255:
                    if table[start]:start+=1;continue
                    end=start+1
                    while end<255 and not table[end]:end+=1
                    token=e.m.alloc(end-start,bank,owner=16,page=start)
                    held.append((token,bank,start,end,bytes(e.bus.ram[bank][start*256:end*256])))
                    start=end
            e.ram[0x100:0x200]=stack
            assert sum(e.m.stats()[:2])==0
            e.key(2);e.key(0x1d);e.check(raw,1,False,selection=(0,1))
            # Growth at zero free pages with nothing reclaimable is refused and
            # changes nothing. History memory is optional (NATIVE-HISTORY: the
            # allocator reclaims it before refusing), so mark it unavailable:
            # the state eh_relieve checks before it returns N_NOMEM.
            available=e.symbol('eh_available');saved_available=e.ram[available];e.ram[available]=0
            old=e.state();e.key(13)
            e.check(raw,1,False,status=3,selection=(0,1));assert e.state()==old
            e.ram[available]=saved_available
            # Same-capacity replacement must still work at zero free pages.
            e.type('Q');want=b'Q'+raw[1:];e.check(want,1,True)
            # With history present, growth reclaims it instead of refusing: the
            # document takes a second chunk, the user is told undo is gone
            # (status 30) and no page held by anyone else is touched.
            e.key(13);want=b'Q\r\n'+raw[1:];e.check(want,3,True,status=30)
            state=e.state()
            assert (state['capacity'],state['chunks'],e.ram[available])==(8192,2,0),(state,e.ram[available])
            for token,bank,start,end,content in held:
                assert bytes(e.bus.ram[bank][start*256:end*256])==content
            e.key(1);e.key(20);e.check(b'',0,True)
            for token,bank,start,end,content in held:
                assert bytes(e.bus.ram[bank][start*256:end*256])==content
                e.m.select(token,16);e.m.invoke('free')
            e.ram[0x100:0x200]=stack
            e.exit(dirty=True);e.restored()
        else:
            e.key(1);e.key(0x86);e.type('COPY');e.key(0x88)
            module=e.io.files.pop((8,b'EDFIND.PRG',b'P'))
            e.key(27);assert not e.value('eg_bitmap')
            e.key(27);assert not e.value('ed_mode') and e.value('es_active')
            e.type('X');assert e.contents()==raw and e.value('ed_status')==12
            assert e.value('es_active') and not e.state()['dirty']
            e.io.files[8,b'EDFIND.PRG',b'P']=module
            e.key(12);e.check(raw,len(raw),False,status=12,selection=(0,len(raw)))
            e.key(7);e.check(raw,len(raw),False)
            e.exit();e.restored()
        report['key_instruction_counts']=key_costs
        report['cases'].append(dict(name=args.case,instructions=e.instructions,checked=e.checked,frames=e.frames,
                                    complete_canvases=e.checked*(2 if args.vdc_kib else 1)))
        report['passed']=True
        print('PASS:',args.case,flush=True)
    except BaseException:
        report['error']=traceback.format_exc()
        raise
    finally:
        args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
