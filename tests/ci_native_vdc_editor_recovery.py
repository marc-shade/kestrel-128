#!/usr/bin/env python3
"""Display faults must preserve documents, file progress and nested search state."""
import argparse
import copy
import json
from pathlib import Path

from ci_native_vdc_editor import Editor,gui,VDCBus
from ci_native_editor_gui import GraphicalEditor as BaseGraphicalEditor
from native_editor_scene import surface


class RecoveryEditor(Editor):
    def check(self,*args,**kwargs):
        BaseGraphicalEditor.check(self,*args,**kwargs)
        if self.value('vd_phase'):self.mirror()


def snapshot(p):
    return dict(document=p.contents(),contexts=p.data('d_states',256),
        position=p.data('ed_io_pos',3),phase=p.value('ed_io_phase'),
        cursor=p.data('ed_cursor',3),probe=p.data('ed_probe',3),
        search_count=p.data('ed_s_count',3),field=p.data('ed_field',256),
        buffers=bytes(p.ram[0x5000:0x5600]),
        heap=bytes(p.ram[0x3800:0x3a00])+bytes(p.ram[0x3c00:0x3d00]),
        tokens=p.data('bk_handle',4)+p.data('vd_handle',4)+p.data('eg_handle',4),
        io=copy.deepcopy(p.io.handles),files={k:bytes(v) for k,v in p.io.files.items()},
        keys=bytes(p.ram[0x1000:0x1100]),callback=bytes(p.ram[0x033c:0x033e]),stack=p.cpu.sp)


def paused(p,*,busy=0,phase=0,document_view=None):
    assert p.value('vd_phase') and p.value('vd_fault') and p.value('eg_vdc_warned')
    # A busy search updates its dialog while the document behind it retains
    # the pre-search view. Partial replacements can move the logical cursor
    # beyond that viewport; they are checked separately as document bytes.
    if document_view is None:
        document_view=dict(data=p.contents(),cursor=p.number('ed_cursor'),name=p.string('ed_name'),
            dirty=bool(p.state()['dirty']),view=p.number('ed_view'),horizontal=p.number('ed_horizontal'))
    want=surface(**document_view,device=p.value('ed_device'),fmt=p.value('ed_format'),mode=p.value('ed_mode'),
        field=p.string('ed_field'),field_caret=p.value('ed_field_cursor'),
        field_view=p.ram[p.symbol('ed_field_views')],status=p.value('ed_status'),
        search_case=p.value('ed_s_pending_case'),replacements=p.number('ed_s_count'),
        focus=p.value('ui_selected'),more=bool(p.value('eg_more')),
        busy=busy,phase=phase,io_bytes=p.number('ed_io_pos'),search_byte=p.number('ed_probe'),help_text=b'VDC paused; Esc restores')
    actual=bytes(p.ram[0xc000:0xe400])
    assert actual==want,('pause canvas',[(i,a,b) for i,(a,b) in enumerate(zip(actual,want)) if a!=b][:24],
        dict(position=p.number('ed_io_pos'),body=p.data('eg_body',280)[240:].hex(),
             cache=p.data('eg_cache',114)[74:].hex(),busy=p.value('eg_busy'),view=p.value('eg_view')))


def ignored(p,keys=(ord('A'),13,0x86,27,27)):
    before=snapshot(p)
    for key in keys:
        p.key(key)
        after=snapshot(p)
        changed=[k for k in before if before[k]!=after[k]]
        differences={k:[(i,a,b) for i,(a,b) in enumerate(zip(before[k],after[k])) if a!=b][:24]
            for k in changed if isinstance(before[k],bytes)}
        assert not changed,('paused state changed',key,changed,differences)


def restore(p,action):
    original=p.output;seen=[]
    def observe(value):
        if p.ram[0xd7]&128 and not seen:
            assert not p.value('vd_phase') and p.bus.video_ram==p.bus.original[0]
            seen.append(True)
        original(value)
    p.output=observe;p.bus.stall=False
    try:action()
    finally:p.output=original
    assert not p.value('vd_phase')
    return seen


def reopen_and_exit(p):
    p.bus.original=None;p.key(12);p.check(p.contents())
    p.exit(dirty=bool(p.state()['dirty']));p.restored()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--group',choices=('all','idle','exit','open','save','verify','search','picker'),default='all')
    args=parser.parse_args();original=gui.PointerBus
    report=dict(passed=False,physical_hardware_io=False,cases=[])
    def done(name,p,**extra):
        report['cases'].append(dict(name=name,passed=True,instructions=p.instructions,keys=p.events,**extra))
        args.report.write_text(json.dumps(report,indent=2)+'\n');print('PASS:',name,flush=True)
    try:
        gui.PointerBus=VDCBus
        if args.group in ('all','idle'):
            p=RecoveryEditor(device=9);p.type('KEPT');p.check(b'KEPT',4,True)
            p.bus.stall=True;p.key(9);paused(p);ignored(p)
            assert restore(p,lambda:p.key(27));p.check(b'KEPT',4,True,mode=5)
            p.key(ord('N'));reopen_and_exit(p)
            done('paused display ignores edits and retains the dirty document until Escape recovers',p)
        if args.group in ('all','exit'):
            p=RecoveryEditor(device=9);p.check(b'',0,False)
            p.bus.stall=True;p.key(27);p.poll();paused(p);ignored(p)
            p.bus.stall=False;p.key(27,exited=True);p.restored()
            done('clean-document exit waits for complete display restoration before releasing owners',p)
        raw=(b'ROW 12345\r'*1100)[:10240]
        for phase,group in ((1,'open'),(2,'save'),(3,'verify')):
            if args.group not in ('all',group):continue
            p=RecoveryEditor({(9,b'SOURCE',b'S'):raw},device=9)
            if phase==1:
                p.type('ORIGINAL');p.key(0x85);p.type('SOURCE')
                # The dirty Open confirmation is accepted before the transfer begins.
                trigger=ord('Y');p.key(13)
            else:
                p.prompt(0x85,'SOURCE');p.type('X');p.key(0x86);p.type('PARTIAL');trigger=13
            before_document=p.contents();step=p.cpu.step;injected=[]
            def stall():
                if p.cpu.pc==p.symbol('ed_progress') and p.value('ed_io_phase')==phase and not injected:
                    if p.number('ed_io_pos')==8192:p.bus.stall=True;injected.append(8192)
                return step()
            p.cpu.step=stall
            try:p.key(trigger)
            finally:p.cpu.step=step
            assert injected==[8192] and p.value('ed_io_phase')==phase and p.number('ed_io_pos')==8192
            assert p.contents()==before_document
            paused(p,busy=1,phase=phase);ignored(p)
            retained={k:bytes(v) for k,v in p.io.files.items()}
            assert restore(p,lambda:p.key(27));assert p.contents()==before_document
            assert not p.io.handles and {k:bytes(v) for k,v in p.io.files.items()}==retained
            if phase==1:assert (9,b'PARTIAL',b'S') not in p.io.files
            else:assert bytes(p.io.files[9,b'PARTIAL',b'S'])==(before_document[:8192] if phase==2 else before_document)
            reopen_and_exit(p)
            done(group+' pauses at the exact transfer position and retains all document and output bytes',p,position=8192)
        if args.group in ('all','search'):
            p=RecoveryEditor({(9,b'SOURCE',b'S'):raw},device=9);p.prompt(0x85,'SOURCE')
            p.key(6);p.type('ZZZ');step=p.cpu.step;injected=[];trace=[]
            addresses={p.symbol(n):n for n in ('ed_paint_fields','eg_vdc_sync','eg_vdc_guard','ed_cancel_check','ed_search_finish')}
            field_address=p.symbol('ed_paint_fields')
            def stall_search():
                if p.cpu.pc==field_address and p.value('ed_status')==16 and p.number('ed_probe')==256 and not injected:
                    p.bus.stall=True;injected.append(256)
                if p.cpu.pc in addresses:
                    trace.append(dict(at=addresses[p.cpu.pc],probe=p.number('ed_probe'),status=p.value('ed_status'),
                        collecting=p.value('eg_collect'),inside=p.value('eg_inside'),fault=p.value('vd_fault'),
                        phase=p.value('vd_phase'),length=p.number('ed_length'),limit=p.number('ed_s_limit')))
                    if len(trace)>64:del trace[0]
                return step()
            p.cpu.step=stall_search
            try:p.key(13)
            finally:
                p.cpu.step=step;report['search_trace']=trace
            assert injected==[256] and p.value('ed_s_running'),dict(injected=injected,
                running=p.value('ed_s_running'),status=p.value('ed_status'),probe=p.number('ed_probe'),
                phase=p.value('vd_phase'),fault=p.value('vd_fault'),pc=hex(p.cpu.pc),document_bytes=len(p.contents()))
            paused(p,busy=2);ignored(p)
            assert restore(p,lambda:p.key(27));p.check(raw,0,False,status=8)
            assert not p.value('ed_s_running');reopen_and_exit(p)
            done('nested search pauses without edits or stack drift and cancels after restoration',p,position=256)
        if args.group in ('all','picker'):
            from native_picker_fixture import Picker
            p=RecoveryEditor({(9,b'SOURCE',b'S'):raw},device=9);p.type('KEPT')
            p.key(0x86);p.type('COPY');preferences=Picker(p).preferences();p.key(0x88);p.mirror()
            p.bus.stall=True;p.key(9)
            assert p.value('ed_module_kind')==1 and p.value('fd_active') and p.value('vd_fault')
            active_preferences=Picker(p).preferences();window=p.data('editor_module',16);ignored(p)
            assert p.data('editor_module',16)==window and Picker(p).preferences()==active_preferences
            assert restore(p,lambda:p.key(27));p.check(b'KEPT',4,True,mode=2)
            assert Picker(p).preferences()==preferences and p.string('ed_field')=='COPY'
            p.key(27);reopen_and_exit(p)
            done('picker display failure retains its module, caller preferences and dirty document',p)
        report['passed']=True
    finally:
        gui.PointerBus=original;args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
