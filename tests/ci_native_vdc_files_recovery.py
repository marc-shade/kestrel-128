#!/usr/bin/env python3
"""Failed VDC restores retain Files owners, launch identity and copy progress."""
import argparse
import copy
import json
from pathlib import Path

from ci_native_vdc_files import Files,gui,VDCBus
from native_files_copy_check import copy_screen
from native_browser_check import browser_screen
from ci_native_browser import expected


def paused(p,rows,**options):
    assert p.value('vd_phase') and p.value('vd_fault') and p.value('fg_vdc_warned')
    gui.GraphicalFiles.canvas(p,rows,help_text=b'VDC paused; Esc restores',**options)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--group',choices=('all','idle','copy','verify','picker','launch'),default='all')
    args=parser.parse_args();original=gui.PointerBus
    report=dict(passed=False,physical_hardware_io=False,cases=[])
    def done(name,p,**extra):
        report['cases'].append(dict(name=name,passed=True,instructions=p.instructions,keys=p.events,**extra))
        args.report.write_text(json.dumps(report,indent=2)+'\n');print('PASS:',name,flush=True)
    try:
        gui.PointerBus=VDCBus
        if args.group in ('all','idle'):
            p=Files({(9,b'SOURCE',b'S'):b'ORIGINAL'});p.browser()
            p.bus.stall=True;p.key(9)
            rows=gui.ascii_rows(browser_screen(40,expected(p.io.files,9),0,9,0,files_app=True))
            paused(p,rows,count=1);owned,stack=p.m.stats(),p.cpu.sp
            for key in (ord('C'),ord('I'),13,27,27):
                p.key(key);assert p.m.stats()==owned and p.cpu.sp==stack
                assert not p.value('fc_active') and not p.value('b_preview')
                assert bytes(p.io.files[9,b'SOURCE',b'S'])==b'ORIGINAL'
            p.bus.stall=False;p.key(27,exited=True);p.restored()
            done('idle display failure freezes actions, shows a notice and retains owners until Escape restores',p)
        for phase,group in ((1,'copy'),(2,'verify')):
            if args.group not in ('all',group):continue
            raw=bytes(range(256))*40
            p=Files({(9,b'SOURCE',b'S'):raw});p.instruction_limit=120000000
            p.key(ord('C'));p.rename('PARTIAL');p.copy(b'SOURCE',b'PARTIAL')
            step=p.cpu.step;progress=p.symbol('fc_progress');phase_at=p.symbol('fc_phase')
            count_at=p.symbol('fc_copied' if phase==1 else 'fc_verified');injected=[]
            def stall():
                if p.cpu.pc==progress and p.ram[phase_at]==phase and not injected:
                    count=int.from_bytes(p.ram[count_at:count_at+4],'little')
                    if count==8192:p.bus.stall=True;injected.append(count)
                return step()
            p.cpu.step=stall;p.key(13);p.cpu.step=step
            assert injected==[8192] and p.value('fc_phase')==phase
            copied=8192 if phase==1 else len(raw);verified=8192 if phase==2 else 0
            rows=gui.ascii_rows(copy_screen(40,b'SOURCE',b'PARTIAL',copied=copied,
                verified=verified,phase=phase,caret=p.value('fc_caret'),
                view=p.ram[p.symbol('fc_views')],graphical=True))
            paused(p,rows)
            owned,stack=p.m.stats(),p.cpu.sp;handles=copy.deepcopy(p.io.handles)
            tokens=p.data('fc_handles',8);chunk=p.data('fc_data',1024)
            for key in (ord('A'),13,0x88,27,27):
                p.key(key);assert p.m.stats()==owned and p.cpu.sp==stack
                assert p.number('fc_copied')==copied and p.number('fc_verified')==verified
                assert p.io.handles==handles and p.data('fc_handles',8)==tokens
                assert p.data('fc_data',1024)==chunk
                assert bytes(p.io.files[9,b'PARTIAL',b'S'])==raw[:copied]
                assert bytes(p.io.files[9,b'SOURCE',b'S'])==raw
            p.bus.stall=False;p.vdc_expected=False;p.key(27)
            p.copy(b'SOURCE',b'PARTIAL',copied=copied,verified=verified,status=2,partial=True)
            assert bytes(p.io.files[9,b'PARTIAL',b'S'])==raw[:copied]
            assert not p.io.handles and not p.value('fc_handles') and not p.data('fc_handles',8)[4]
            p.key(27);p.browser();p.bus.original=None;p.vdc_expected=True
            p.key(ord('R'));p.browser();p.key(27,exited=True);p.restored()
            done(f'display failure pauses {group} at an exact chunk; Escape preserves the destination and Refresh recovers',
                 p,copied=copied,verified=verified)
        if args.group in ('all','picker'):
            p=Files({(9,b'SOURCE',b'S'):b'PICKER SOURCE'});p.key(ord('C'));p.rename('COPY')
            preferences=p.preferences();p.key(0x88);p.mirror()
            picker_preferences=p.preferences()
            p.bus.stall=True;p.key(9)
            assert p.value('fg_kind')==2 and p.value('fc_picker_active') and p.value('vd_fault')
            owned,stack=p.m.stats(),p.cpu.sp;name=p.name();window=p.data('files_module',16)
            tokens=p.data('bk_handle',4)+p.data('vd_handle',4)
            for key in (ord('S'),13,27,27):
                p.key(key);assert p.m.stats()==owned and p.cpu.sp==stack
                assert p.name()==name and p.data('files_module',16)==window
                assert p.data('bk_handle',4)+p.data('vd_handle',4)==tokens
                assert p.preferences()==picker_preferences and (9,b'COPY',b'S') not in p.io.files
            p.bus.stall=False;p.vdc_expected=False;p.key(27);p.copy(b'SOURCE',b'COPY')
            assert not p.value('fc_picker_active') and p.preferences()==preferences
            p.key(27);p.bus.original=None;p.vdc_expected=True;p.key(ord('R'));p.browser()
            p.key(27,exited=True);p.restored()
            done('failed display retains an active picker module and destination until Escape restores and cancels',p)
        if args.group in ('all','launch'):
            from ci_native_calc import ROOT
            target=(ROOT/'target/native-desktop/calc.prg').read_bytes()
            p=Files({(9,b'CALC',b'P'):target},fmt=2);p.browser(fmt=2)
            before=bytes(p.ram[0x3d21:0x3d23])+bytes(p.ram[0x3d2c:0x3d2e])+bytes(p.ram[0x3d40:0x3d60])+bytes(p.ram[0x4e00:0x4f00])
            p.bus.stall=True;p.key(13);p.key(ord('X'))
            after=bytes(p.ram[0x3d21:0x3d23])+bytes(p.ram[0x3d2c:0x3d2e])+bytes(p.ram[0x3d40:0x3d60])+bytes(p.ram[0x4e00:0x4f00])
            assert before==after and p.value('vd_fault') and p.ram[0x3d20]==32
            assert p.ram[0x3d60:0x3d80]==p.image[2:34]
            p.bus.stall=False;p.key(27,exited=True);p.restored()
            done('failed restoration refuses app replacement without changing Files launch identity',p)
        report['passed']=True
    finally:
        gui.PointerBus=original;args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
