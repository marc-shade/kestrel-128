#!/usr/bin/env python3
"""Files retains verified copying and screen recovery through component failures."""
import argparse
import json
from pathlib import Path
from ci_native_vdc_files import Files,gui,VDCBus
from ci_native_calc import ROOT


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
                gui.PointerBus=type('FilesFallback',(VDCBus,),dict(present=case!='hardware'))
                provider=case!='component'
                if case=='corrupt':
                    provider=bytearray((ROOT/'target/native-desktop/vdsvc.prg').read_bytes());provider[-1]^=1
                p=Files({(9,b'SOURCE',b'S'):b'FALLBACK'},vdc_component=provider)
                p.vdc_expected=False;p.browser()
                assert not p.value('vd_phase') and not p.value('bk_state')
                p.key(ord('C'));p.rename('COPY');p.key(13)
                p.copy(b'SOURCE',b'COPY',copied=8,verified=8,status=1)
                assert bytes(p.io.files[9,b'COPY',b'S'])==b'FALLBACK'
                p.key(27);p.browser();p.key(27,exited=True);p.restored()
                done(case+' refusal preserves VIC controls, verified copying and both text fallback/cleanup paths',p)
        gui.PointerBus=VDCBus
        if args.group in ('all','modules'):
            p=Files({(9,b'SOURCE',b'S'):b'KEPT SOURCE'});p.browser()
            p.key(ord('C'));p.rename('COPY');p.copy(b'SOURCE',b'COPY')
            original_picker=p.io.files[8,b'FSPICK.PRG',b'P']
            p.io.files[8,b'FSPICK.PRG',b'P']=bytearray(original_picker)
            p.io.files[8,b'FSPICK.PRG',b'P'][-1]^=1
            restored=[];output=p.output
            def observe(value):
                if not restored and p.ram[0xd7]&128:
                    assert not p.value('vd_phase') and p.bus.video_ram==p.bus.original[0]
                    restored.append(True)
                output(value)
            p.output=observe;p.vdc_expected=False;p.key(0x88)
            assert restored and p.value('fc_status')==10 and p.name()==b'COPY',dict(
                restored=restored,status=p.value('fc_status'),name=p.name(),
                phase=p.value('vd_phase'),kind=p.value('fg_kind'),bitmap=p.value('fg_bitmap'),
                same_screen=p.bus.video_ram==p.bus.original[0])
            assert not p.io.handles and p.value('fg_kind')==1
            p.output=output;p.io.files[8,b'FSPICK.PRG',b'P']=original_picker
            p.key(0x88);p.key(27);p.copy(b'SOURCE',b'COPY')
            del p.io.files[8,b'FSVIEW.PRG',b'P'];p.key(0x88);p.key(27)
            assert not p.value('fg_kind') and not p.value('fg_bitmap') and not p.value('vd_phase')
            assert p.name()==b'COPY';p.key(13)
            assert bytes(p.io.files[9,b'COPY',b'S'])==b'KEPT SOURCE'
            p.key(27);p.io.files[8,b'FSVIEW.PRG',b'P']=(ROOT/'target/native-desktop/fsview.prg').read_bytes()
            p.bus.original=None;p.vdc_expected=True;p.key(ord('R'));p.browser()
            p.key(27,exited=True);p.restored()
            done('corrupt picker restores VDC before text; missing graphics preserves copying; Refresh reacquires both displays',p)
        if args.group in ('all','surface'):
            p=Files({(9,b'SOURCE',b'S'):b'RETAINED'});p.browser()
            p.key(ord('C'));p.rename('COPY');original_stub=p.io.stub
            injected=[];restored=[];output=p.output
            def bad_fill(cpu):
                if p.value('fc_picker_active') and cpu.pc==0x1c2c and not injected:
                    p.ram[0x3d05]^=128;injected.append(True)
                return original_stub(cpu)
            def observe(value):
                if injected and not restored and p.ram[0xd7]&128:
                    assert not p.value('vd_phase') and p.bus.video_ram==p.bus.original[0]
                    restored.append(True)
                output(value)
            p.io.stub=bad_fill;p.output=observe;p.vdc_expected=False;p.key(0x88)
            assert injected and restored and p.value('fc_picker_active') and p.name()==b'COPY'
            assert not p.value('vd_phase');p.io.stub=original_stub;p.output=output
            p.key(27);p.copy(b'SOURCE',b'COPY');p.key(13)
            assert bytes(p.io.files[9,b'COPY',b'S'])==b'RETAINED'
            p.key(27);p.bus.original=None;p.vdc_expected=True;p.key(ord('R'));p.browser()
            p.key(27,exited=True);p.restored()
            done('failed picker surface restores VDC before text and retains the complete copy destination',p)
        report['passed']=True
    finally:
        gui.PointerBus=original;args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
