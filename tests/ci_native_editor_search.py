#!/usr/bin/env python3
"""Actual editor controls, banked bytes and dual screens against Python oracles."""
import argparse
import hashlib
import json
from pathlib import Path
import random

from ci_native_editor import Editor, ROOT


def query(e, text, key=6, ignore_case=False):
    e.key(key);e.key(21);e.type(text)
    if bool(e.value('ed_s_pending_case')) != ignore_case:e.key(9)
    e.check(e.contents(), mode=6 if key==6 else 7)
    e.key(13)


def replace_prompt(e, text, replacement, ignore_case=False):
    query(e,text,18,ignore_case)
    e.check(e.contents(),mode=8)
    e.type(replacement);e.key(13);e.check(e.contents(),mode=9)


def queued_cancel(e, trigger):
    e.observation_target=e.events+2;e.observation_done=False
    e.keys.extend([trigger,27]);e.loop();e.events+=2
    assert e.observation_done
    assert int.from_bytes(e.ram[0x3d13:0x3d15],'little')==e.events


def injected(e, address, nth, error):
    old=e.io.stub;seen=[]
    def stub(cpu):
        if cpu.pc==address:
            seen.append(e.number('ed_s_count'))
            if len(seen)==nth:
                cpu.a=error;cpu.p|=1;cpu.pc=(cpu.stPopWord()+1)&65535
                return True
        return old(cpu)
    e.io.stub=stub
    return old,seen


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    images={name:hashlib.sha256((ROOT/'target/native'/name).read_bytes()).hexdigest()
            for name in ('kestrel.prg','editor.prg','edpick.prg','edfind.prg')}
    report=dict(passed=False,images=images,cases={})
    def done(name,e,**extra):
        report['cases'][name]=dict(events=e.events,instructions=e.instructions,**extra)
        print('PASS: native editor search '+name,flush=True)
    try:
        e=Editor();e.key(14);e.check(b'',0,False,mode=6)
        e.key(13);e.check(b'',mode=6);e.key(27)
        query(e,'EMPTY');e.check(b'',0,False,status=15)
        e.exit();done('empty-document-empty-query-and-next-before-first-find',e)

        raw=b'ABABA abc ABC Abc\r\n'+bytes([0,255])+b' "quoted" abc'
        e=Editor({(8,b'SOURCE',b'S'):raw});e.prompt(0x85,'SOURCE')
        query(e,'ABA');e.check(raw,0,False,status=13)
        e.key(14);e.check(raw,2,False,status=13)
        e.key(14);e.check(raw,0,False,status=14)
        e.prompt(0x88,'000001');query(e,'ABABA');e.check(raw,0,False,status=14)
        query(e,'abc');e.check(raw,6,False,status=13)
        e.key(14);e.check(raw,raw.rfind(b'abc'),False,status=13)
        e.key(14);e.check(raw,6,False,status=14)
        query(e,'abc',ignore_case=True);e.check(raw,6,False,status=13)
        e.key(14);e.check(raw,10,False,status=13)
        e.key(6);e.key(9);e.key(27);e.key(14);e.check(raw,14,False,status=13)
        assert e.value('ed_s_case')==1,'cancelled field changed the accepted case setting'
        query(e,'MISSING');e.check(raw,14,False,status=15)
        query(e,'"quoted"');e.check(raw,raw.index(b'"'),False,status=13)
        e.exit();done('overlap-wrap-cross-cursor-case-cancel-quotes-and-binary-preservation',e)

        raw=b'AA AA aa\r\n\0\xffEND'
        e=Editor({(8,b'S',b'S'):raw});e.prompt(0x85,'S')
        replace_prompt(e,'AA','AAAA');e.key(27);e.check(raw,0,False)
        replace_prompt(e,'AA','AAAA');e.type('O');want=b'AAAA'+raw[2:]
        e.check(want,0,True,status=17);assert e.number('ed_s_count')==1
        replace_prompt(e,'AA','A',True);e.type('A');want=b'AA A A\r\n\0\xffEND'
        e.check(want,5,True,status=17);assert e.number('ed_s_count')==4
        replace_prompt(e,'A','');e.type('A');want=want.replace(b'A',b'')
        e.check(want,2,True,status=17);assert e.number('ed_s_count')==4
        replace_prompt(e,'ABSENT','X');e.type('A');e.check(want,2,True,status=17)
        assert e.number('ed_s_count')==0
        e.prompt(0x86,'RESULT');e.check(want,2,False,status=1,name='RESULT')
        assert bytes(e.io.files[8,b'RESULT',b'S'])==want
        e.key(0x87);e.prompt(0x85,'RESULT');e.check(want,0,False)
        e.exit();done('replace-one-all-growth-shrink-delete-cancel-save-and-reopen',e)

        raw=b'A'*2048
        e=Editor({(8,b'S',b'S'):raw});e.prompt(0x85,'S')
        e.key(6);e.type('Z');queued_cancel(e,13)
        e.check(raw,0,False,status=8)
        replace_prompt(e,'A','B');queued_cancel(e,ord('A'))
        e.check(b'B'+raw[1:],0,True,status=18);assert e.number('ed_s_count')==1
        e.exit(True);done('cancel-scan-and-retain-counted-completed-replacement',e)

        raw=b'A'*4096
        for fail_at,count in ((1,0),(2,65)):
            e=Editor({(8,b'S',b'S'):raw});e.prompt(0x85,'S')
            replace_prompt(e,'A','X'*64)
            old,seen=injected(e,0x1c20,fail_at,2)
            e.type('A');e.io.stub=old
            want=b'X'*(count*64)+raw[count:]
            e.check(want,max(0,(count-1)*64),bool(count),status=19 if count else 3)
            assert e.number('ed_s_count')==count and len(seen)==fail_at
            assert not e.state()['fault']
            e.exit(bool(count));done(f'oom-at-allocation-{fail_at}-preserves-unreplaced-original',e,count=count)

        raw=b'A'*4096+b'B\r\nTAIL'
        e=Editor({(8,b'S',b'S'):raw});e.prompt(0x85,'S')
        pattern='A'*63+'B';query(e,pattern);e.check(raw,4033,False,status=13)
        e.key(6);assert e.string('ed_field')==pattern
        e.type('X');assert e.string('ed_field')==pattern
        e.key(0x13);e.key(20);e.check(raw,mode=6)
        e.key(21);e.type('A'*63+'Z')
        comparisons=[];old=e.io.stub;compare=e.symbol('ed_search_compare')
        def measured(cpu):
            if cpu.pc==compare:comparisons.append(cpu.pc)
            return old(cpu)
        e.io.stub=measured;e.key(13);e.io.stub=old
        e.check(raw,4033,False,status=15)
        assert len(comparisons)<2*(len(raw)+4033+64),len(comparisons)
        e.exit();done('64-byte-field-and-linear-repeated-prefix-search',e,comparisons=len(comparisons))

        raw=bytearray((b'LINE OF TEXT\r\n'*4800)[:66053]);needle=b'EDGE MATCH'
        offsets=(507,4091,65531)
        for at in offsets:raw[at:at+len(needle)]=needle
        raw=bytes(raw)
        from ci_native_file_dialog import DialogEditor
        e=DialogEditor({(9,b'LARGE',b'S'):raw},device=9)
        e.keep_workspaces()
        e.prompt(0x85,'LARGE');query(e,needle.decode());e.check(raw,offsets[0],False,status=13)
        for at in offsets[1:]:e.key(14);e.check(raw,at,False,status=13)
        e.key(14);e.check(raw,offsets[0],False,status=14)
        replace_prompt(e,needle.decode(),'SMALL');e.type('A');want=raw.replace(needle,b'SMALL')
        e.check(want,offsets[-1]-10,True,status=17);assert e.number('ed_s_count')==3
        assert e.banks=={0,1} and len(want)>65536
        e.prompt(0x86,'SAVED');e.check(want,offsets[-1]-10,False,status=1)
        assert bytes(e.io.files[9,b'SAVED',b'S'])==want
        e.key(0x87);e.prompt(0x85,'SAVED');e.check(want,0,False)
        e.check_workspaces();e.release_workspaces()
        e.exit();done('512-4K-64K-boundaries-two-workspaces-and-large-save-reopen',e,
                      bytes=len(want),sha256=hashlib.sha256(want).hexdigest())

        rng=random.Random(12865);raw=bytes(rng.choice(b'AB ab') for _ in range(160))
        e=Editor({(8,b'S',b'S'):raw});e.prompt(0x85,'S')
        for _ in range(12):
            start=rng.randrange(len(raw)+1);at=rng.randrange(len(raw)-5)
            pattern=raw[at:at+rng.randrange(1,6)];fold=bool(rng.randrange(2))
            hay=raw.lower() if fold else raw;pat=pattern.lower() if fold else pattern
            found=hay.find(pat,start);wrapped=found<0
            if wrapped:found=hay.find(pat)
            e.prompt(0x88,f'{start:06X}');query(e,pattern.decode(),ignore_case=fold)
            e.check(raw,found,False,status=14 if wrapped else 13)
        e.exit();done('deterministic-independent-find-oracle',e)

        from ci_native_module_editor import ModuleEditor
        search_image=(ROOT/'target/native/edfind.prg').read_bytes()
        for source,context in ((None,1),(b'/Usb0/Tools/EDITOR.PRG',1),(b'/Usb0/Tools/EDITOR.PRG',2)):
            e=ModuleEditor(source,context);e.prompt(0x85,'NOTE');raw=b'ORIGINAL\rBYTES'
            files=e.ultimate.files if source else e.io.files
            name=source.rsplit(b'/',1)[0]+b'/EDFIND.PRG' if source else (8,b'EDFIND.PRG',b'P')
            files.pop(name)
            e.key(6);e.check(raw,0,False,status=2)
            files[name]=bytearray(search_image)
            query(e,'original',ignore_case=True);e.check(raw,0,False,status=13)
            files.pop(name);e.key(14);e.check(raw,0,False,status=14)
            e.key(0x85);e.key(9);assert e.value('fd_active') and e.value('ed_module_kind')==1
            e.key(27);e.key(27);e.key(14);e.check(raw,0,False,status=2)
            bad=bytearray(search_image);bad[-1]^=1;files[name]=bad
            e.key(14);e.check(raw,0,False,status=2)
            files[name]=bytearray(search_image)
            e.key(14);e.check(raw,0,False,status=14)
            assert e.value('ed_s_case')==1 and e.value('ed_module_kind')==2
            e.ram[e.symbol('ed_picker_token')]^=128
            e.key(14);e.check(raw,0,False,status=2)
            e.key(14);e.check(raw,0,False,status=14)
            e.exit();done(f'module-{context if source else "iec"}-missing-crc-warm-picker-retry-query-retained',e)

        for fault in ('cursor','cache'):
            entries=[b'\x20'+f'ROW {i:03d}'.encode() for i in range(40)]
            e=DialogEditor(usb={},directories={b'/Usb0':entries})
            e.type('KEPT');raw=b'KEPT'
            for _ in range(3):e.key(0x8b)
            e.begin(name='/Usb0/');token=bytes(e.ram[0x3d17:0x3d1a])
            if fault=='cursor':e.ultimate.ignore_abort=True
            else:old,seen=injected(e,0x1c23,1,7)
            e.key(27)
            if fault=='cache':e.io.stub=old;assert seen
            e.key(27);e.key(6)
            e.check(raw,4,True,status=2,released=fault!='cursor')
            assert e.value('ed_module_kind')==1 and bytes(e.ram[0x3d17:0x3d1a])==token
            if fault=='cursor':e.ultimate.ignore_abort=False
            e.key(0x85);e.key(9);assert e.value('fd_active')
            e.key(27);e.key(27)
            query(e,'KEPT');e.check(raw,0,True,status=14)
            e.exit(True);done('module-switch-refuses-retained-picker-'+fault,e)

        e=Editor({(8,b'S',b'S'):b'LINE\n'*300});e.prompt(0x85,'S')
        e.key(6);e.type('MISSING');old,seen=injected(e,0x1c26,1,4)
        e.key(13);e.io.stub=old
        assert seen and e.state()['fault']==4 and e.value('ed_status')==5
        e.exit(True);done('read-failure-reports-fault-not-no-match',e)
        assert images=={name:hashlib.sha256((ROOT/'target/native'/name).read_bytes()).hexdigest() for name in images}
        report['passed']=True
    except BaseException as error:report['error']=str(error);raise
    finally:
        if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
