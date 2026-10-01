#!/usr/bin/env python3
"""Editor keeps document and file operations usable through display refusals."""
import argparse
import json
from pathlib import Path

from ci_native_vdc_editor_recovery import RecoveryEditor
from ci_native_vdc_editor import gui,VDCBus
from ci_native_calc import ROOT
from ci_native_editor import Editor as TextEditor


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--group',choices=('all','open','modules','surface'),default='all')
    args=parser.parse_args();original=gui.PointerBus
    report=dict(passed=False,physical_hardware_io=False,cases=[])
    def done(name,p):
        report['cases'].append(dict(name=name,passed=True,instructions=p.instructions,keys=p.events))
        args.report.write_text(json.dumps(report,indent=2)+'\n');print('PASS:',name,flush=True)
    try:
        if args.group in ('all','open'):
            for case in ('hardware','component','corrupt'):
                gui.PointerBus=type('EditorFallback',(VDCBus,),dict(present=case!='hardware'))
                provider=case!='component'
                if case=='corrupt':
                    provider=bytearray((ROOT/'target/native-desktop/vdsvc.prg').read_bytes());provider[-1]^=1
                p=RecoveryEditor(device=9,vdc_component=provider);p.check(b'',0,False)
                assert not p.value('vd_phase')
                # Without the chip the component still hosts the span history
                # (docs/NATIVE-HISTORY.md); a missing or corrupt one is unloaded.
                hosted=case=='hardware'
                assert p.value('bk_state')==(2 if hosted else 0) and p.value('eh_available')==hosted
                p.type('KEPT');p.check(b'KEPT',4,True)
                p.prompt(0x86,'COPY');p.check(b'KEPT',4,False,status=1,name='COPY')
                assert bytes(p.io.files[9,b'COPY',b'S'])==b'KEPT'
                p.exit();p.restored()
                done(case+' refusal keeps editing, verified Save As and complete cleanup',p)
        gui.PointerBus=VDCBus
        if args.group in ('all','modules'):
            p=RecoveryEditor(device=9);p.type('KEPT');p.key(0x86);p.type('COPY')
            picker=p.io.files[8,b'EDPICK.PRG',b'P'];bad=bytearray(picker);bad[-1]^=1
            p.io.files[8,b'EDPICK.PRG',b'P']=bad
            restored=[];output=p.output
            def observe(value):
                if p.ram[0xd7]&128 and not restored:
                    assert not p.value('vd_phase') and p.bus.video_ram==p.bus.original[0]
                    restored.append(True)
                output(value)
            p.output=observe;p.key(0x88);p.output=output
            assert restored and not p.value('vd_phase') and not p.io.handles
            p.check(b'KEPT',4,True,mode=2,status=2);assert p.string('ed_field')=='COPY'
            p.io.files[8,b'EDPICK.PRG',b'P']=picker;p.key(0x88);p.key(27)
            p.check(b'KEPT',4,True,mode=2)
            graphics=p.io.files.pop((8,b'EDFIND.PRG',b'P'));p.key(0x88);p.key(27)
            assert not p.value('ed_module_kind') and not p.value('eg_bitmap') and not p.value('vd_phase')
            TextEditor.check(p,b'KEPT',4,True,mode=2);p.key(13)
            TextEditor.check(p,b'KEPT',4,False,status=1,name='COPY')
            assert bytes(p.io.files[9,b'COPY',b'S'])==b'KEPT'
            p.io.files[8,b'EDFIND.PRG',b'P']=graphics;p.bus.original=None;p.key(12)
            p.check(b'KEPT',4,False,status=1,name='COPY');p.exit();p.restored()
            done('corrupt picker restores the display; missing graphics keeps the document and verified saving usable',p)
        if args.group in ('all','surface'):
            p=RecoveryEditor(device=9);p.type('KEPT');p.key(0x86);p.type('COPY')
            original_stub=p.io.stub;output=p.output;injected=[];restored=[]
            def bad_fill(cpu):
                if p.value('fd_active') and cpu.pc==0x1c2c and not injected:
                    p.ram[0x3d05]^=128;injected.append(True)
                return original_stub(cpu)
            def observe(value):
                if injected and p.ram[0xd7]&128 and not restored:
                    assert not p.value('vd_phase') and p.bus.video_ram==p.bus.original[0]
                    restored.append(True)
                output(value)
            p.io.stub=bad_fill;p.output=observe;p.key(0x88)
            p.io.stub=original_stub;p.output=output
            assert injected and restored and p.value('fd_active') and not p.value('pg_bitmap')
            assert p.contents()==b'KEPT' and p.string('ed_field')=='COPY'
            p.key(27);p.check(b'KEPT',4,True,mode=2);p.key(13)
            p.check(b'KEPT',4,False,status=1,name='COPY');assert bytes(p.io.files[9,b'COPY',b'S'])==b'KEPT'
            p.bus.original=None;p.key(12);p.check(b'KEPT',4,False,status=1,name='COPY')
            p.exit();p.restored()
            done('failed picker surface restores VDC before text and retains the complete dirty document',p)
        report['passed']=True
    finally:
        gui.PointerBus=original;args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
