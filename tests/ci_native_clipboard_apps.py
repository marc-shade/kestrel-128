#!/usr/bin/env python3
"""Loaded Editor/Claude clipboard workflows on one native kernel instance."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import traceback

from ci_native_editor_gui import GraphicalEditor, ROOT
from native_clipboard_check import published

def clip(editor,data):
    assert published(editor.m)[0]==data

def case_editor(large=False):
    raw=(b'0123456789 AbCdEf\r\n'*1000)[:15360] if large else b'abc\r\nDEF\nlast'
    e=GraphicalEditor({(9,b'INPUT',b'S'):raw},device=9)
    e.prompt(0x85,'INPUT');e.check(raw,0,False)
    e.key(3);e.check(raw,0,False,status=22)
    e.key(22);e.check(raw,0,False,status=23)
    e.key(1);e.key(3);e.check(raw,len(raw),False,status=20,selection=(0,len(raw)));clip(e,raw)
    print('copied',len(raw),flush=True)
    e.key(7);e.key(22);e.check(raw*2,len(raw)*2,True,status=30 if large else 21);clip(e,raw)
    print('pasted',len(raw)*2,flush=True)
    if not large:
        e.frame();e.click(5);e.click(5);e.click(5);e.click(26)
        want=raw*3;e.check(want,len(want),True,status=21)
        e.key(1);e.key(24);e.check(b'',0,True,status=20);clip(e,want)
        e.key(22);e.check(want,len(want),True,status=21)
        e.prompt(0x86,'SAVED');assert bytes(e.io.files[9,b'SAVED',b'S'])==want
        e.key(11);e.check(want,len(want),False,status=26);clip(e,b'')
        e.key(22);e.check(want,len(want),False,status=23)
        e.exit()
    else:
        # This RAM-only paste reclaims optional history to make room for the
        # full document. It must announce that loss and refuse stale replay.
        e.key(26);e.check(raw*2,len(raw)*2,True,status=31);clip(e,raw)
        # An oversized Copy and Cut must keep both the selected document and
        # the previous clipboard. Clear releases the retained item explicitly.
        e.key(1);e.key(3);e.check(raw*2,len(raw)*2,True,status=24,selection=(0,len(raw)*2));clip(e,raw)
        e.key(24);e.check(raw*2,len(raw)*2,True,status=24,selection=(0,len(raw)*2));clip(e,raw)
        e.key(7);e.key(11);e.exit(dirty=True)
    e.restored()
    return dict(name='large Editor clipboard' if large else 'Editor keys, mouse, saved bytes and clear',
                keys=e.events,instructions=e.instructions,canvases=e.checked,bytes=len(raw))

def case_capacity():
    raw=(b'ROW 0123456789\r'*400)[:5000]
    # Keep this capacity-refusal fixture independent of the optional history
    # provider, which can now be reclaimed to satisfy document growth.
    e=GraphicalEditor({(9,b'INPUT',b'S'):raw},device=9,vdc_component=False)
    e.prompt(0x85,'INPUT');e.key(1);e.key(3);clip(e,raw);e.key(7)
    e.key(0x87);e.check(b'',0,False)
    stack=bytes(e.ram[0x100:0x200]);held=[];keep=None
    for bank,first in ((1,4),(0,0x50)):
        page=first
        while page<255:
            if e.ram[0x3800+bank*256+page]:page+=1;continue
            start=page
            while page<255 and not e.ram[0x3800+bank*256+page]:page+=1
            count=page-start
            if keep is None and bank==1 and count>=16:
                keep=(bank,start);start+=16;count-=16
            if count:
                token=e.m.alloc(count,bank,77,page=start)
                held.append((bank,start*256,bytes(e.m.bus.ram[bank][start*256:page*256])))
    e.ram[0x100:0x200]=stack;assert keep is not None
    e.key(22);e.check(b'',0,False,status=3);clip(e,raw)
    assert e.state()['capacity']==4096,e.state()
    for bank,start,data in held:assert e.m.bus.ram[bank][start:start+len(data)]==data
    stack=bytes(e.ram[0x100:0x200]);e.m.set(0x3d00,77);e.m.invoke('release');e.ram[0x100:0x200]=stack
    e.key(22);e.check(raw,len(raw),True,status=30);clip(e,raw)
    e.key(11);e.exit(dirty=True);e.restored()
    return dict(name='partial capacity acquisition refuses Paste without changing text, then retries',instructions=e.instructions,canvases=e.checked)

def case_failures():
    raw=b'AB'
    e=GraphicalEditor(device=9)
    e.type('AB');e.key(1);e.key(3);clip(e,raw)
    module=e.io.files.pop((8,b'EDCLIP.PRG',b'P'))
    e.key(24);e.check(raw,len(raw),True,status=2,selection=(0,len(raw)));clip(e,raw)
    e.io.files[8,b'EDCLIP.PRG',b'P']=module
    original=e.cpu.step;failed=[]
    def step():
        if e.cpu.pc==0x1c26 and e.ram[0x3d00]==31:
            failed.append(e.cpu.pc);e.cpu.pc=(e.cpu.stPopWord()+1)&65535
            e.cpu.a=9;e.cpu.p|=1;return
        original()
    e.cpu.step=step
    try:e.key(22)
    finally:e.cpu.step=original
    assert failed and e.state()['fault'] and e.value('ed_status')==5
    clip(e,raw)
    e.prompt(0x86,'Z')
    assert not e.io.handles and (9,b'Z',b'S') not in e.io.files
    assert e.state()['fault'] and e.value('ed_status')==5
    assert e.value('ed_mode')==0
    e.key(7);e.key(11);e.exit(dirty=True);e.restored()
    return dict(name='missing clipboard module retains selection; uncertain Paste read poisons Save As',
                instructions=e.instructions,canvases=e.checked)

def case_protocol():
    from ci_native_claude_gui import GraphicalClient
    c=GraphicalClient();c.key(13);c.feed(bytes([1,14,2,0,0,14,3,1,2,3,5]))
    c.key(255);c.key(3);assert published(c.m)[0].startswith(b'abc')
    start=len(c.chip.sent);c.key(22)
    assert bytes(c.chip.sent[start:])==b'\0\4' and c.value('cg_paste_active')==3
    # Skip nine clock ticks across a five-tick deadline; elapsed time, not
    # foreground poll count, must expire the actual timeout path.
    at=c.symbol('_pasteTicks');c.ram[at:at+2]=b'\5\0'
    c.ram[0xa2]=(c.ram[0xa2]+9)&255;c.poll()
    assert not c.value('cg_paste_active') and c.value('cg_clip_status')==11
    assert bytes(c.chip.sent[start:])==b'\0\4';c.check()
    c.key(22);c.feed(bytes([13,0,5]));assert not c.value('cg_paste_active') and c.value('cg_clip_status')==11
    c.key(22);c.feed(bytes([13,1,5]));assert c.value('cg_paste_active')==1
    c.key(27);assert c.chip.sent[-2:]==b'\0\10' and c.value('cg_clip_status')==10
    c.key(22);c.feed(bytes([13,1,5]));assert c.value('cg_paste_active')==1
    c.key(3);assert not c.value('cg_paste_active') and c.value('cg_clip_status')==8
    c.key(22);c.feed(bytes([13,1,5]))
    for _ in range(50):
        if c.value('cg_paste_active')==2:break
        c.poll()
    else:raise AssertionError('missing End packet')
    c.feed(bytes([14,1,5]));assert c.value('cg_clip_status')==9 and not c.value('cg_paste_active')
    c.check();c.close();c.restored()
    return dict(name='native capability timeout, refusal, cancellation, publication change and host rejection',
                instructions=c.instructions,canvases=c.checked)

def case_handoff():
    import ci_native_claude as terminal
    from ci_native_claude_gui import GraphicalClient
    sys.path.insert(0,str(ROOT/'apps/claude/host'))
    import bridge
    from ci_claude_clipboard import Link
    raw=(bytes(range(32,127))+b'\r\n')*6+b'END'
    e=GraphicalEditor({(9,b'INPUT',b'S'):raw},device=9)
    e.prompt(0x85,'INPUT');e.key(1);e.key(3);clip(e,raw);e.key(7);e.exit();e.restored()
    first_token=bytes(e.ram[0x3deb:0x3def])
    m=e.m;m.bus=terminal.TerminalBus(m.bus)
    original=terminal.TerminalMachine
    terminal.TerminalMachine=lambda:m
    try:c=GraphicalClient()
    finally:terminal.TerminalMachine=original
    c.events=int.from_bytes(c.ram[0x3d13:0x3d15],'little')
    assert bytes(c.ram[0x3deb:0x3def])==first_token;clip(c,raw)
    c.check();c.key(13);c.key(255);c.check();c.key(22)
    assert c.value('cg_paste_active')==3 and c.chip.sent[-2:]==b'\0\4'
    link=Link();host=bridge.Bridge(link,[],panel=False);host.client_ready=True
    sent=2 # The initial RESYNC is already represented by client_ready.
    delivered=bytearray();turns=0
    for turns in range(80):
        delivered.extend(host._take_control(bytes(c.chip.sent[sent:]),translated=True))
        sent=len(c.chip.sent)
        incoming=bytes(link.output);link.output.clear()
        c.feed(incoming or b'\5')
        if not c.value('cg_paste_active'):break
    else:raise AssertionError('negotiated paste did not complete')
    assert delivered==b'\x1b[200~'+raw.replace(b'\r\n',b'\n')+b'\x1b[201~'
    assert c.value('cg_clip_status')==7
    c.check();clip(c,raw)
    print('Editor to Claude bracketed paste accepted',len(raw),flush=True)
    # Copy all retained terminal rows, including cells outside the VIC view.
    c.key(27);c.feed(bytes([1,14,2,0,0,14,6,1,2,3,65,66,67,5]))
    want=b'abcABC'+b' '*74+b'\n'+(b' '*80+b'\n')*24
    c.key(255);c.key(3);clip(c,want);c.check()
    c.close();c.restored();assert published(m)[0]==want
    print('Claude to Editor retained text',len(want),flush=True)
    e2=GraphicalEditor(device=9,existing_machine=m)
    e2.events=int.from_bytes(e2.ram[0x3d13:0x3d15],'little')
    e2.key(22);e2.check(want,len(want),True,status=21)
    e2.prompt(0x86,'FROMCLAUDE');assert bytes(e2.io.files[9,b'FROMCLAUDE',b'S'])==want
    e2.key(11);e2.exit();e2.restored()
    return dict(name='Editor -> Claude -> Editor on one kernel, negotiated and acknowledged paste',
                editor_bytes=len(raw),terminal_bytes=len(want),turns=turns+1,
                text_sha256=hashlib.sha256(want).hexdigest(),
                instructions=e.instructions+c.instructions+e2.instructions,
                canvases=e.checked+c.checked+e2.checked)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=('editor','large','handoff','capacity','failures','protocol'),required=True)
    parser.add_argument('--report',type=Path,required=True);args=parser.parse_args()
    result=dict(passed=False,physical_hardware_io=False)
    try:
        result['cases']=[case_failures() if args.case=='failures' else case_protocol() if args.case=='protocol' else case_handoff() if args.case=='handoff' else case_capacity() if args.case=='capacity' else case_editor(args.case=='large')]
        result['passed']=True;print('PASS',args.case,flush=True)
    except BaseException:result['error']=traceback.format_exc();raise
    finally:args.report.write_text(json.dumps(result,indent=2)+'\n')
