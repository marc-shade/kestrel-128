#!/usr/bin/env python3
"""REU screen backing survives Editor documents and checked picker swaps."""
import argparse
import json
from pathlib import Path

from ci_native_vdc_editor_recovery import RecoveryEditor,ignored
from ci_native_vdc_editor import gui
from ci_native_reu_calc import CalculatorBus,component,COMPONENT_PAGES
from native_document_reu import extent
from native_picker_fixture import Picker
from ci_native_browser import expected


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--group',choices=('all','normal','recovery'),default='all')
    args=parser.parse_args();original=gui.PointerBus
    report=dict(passed=False,physical_hardware_io=False,cases=[])
    raw=bytes(range(256))*16+b'END'
    def start(**options):
        gui.PointerBus=type('EditorREU',(CalculatorBus,),options)
        return RecoveryEditor({(9,b'SOURCE',b'S'):raw},device=9)
    def done(name,p,**extra):
        report['cases'].append(dict(name=name,passed=True,instructions=p.instructions,keys=p.events,
            dmas=len(p.bus.reu_transactions),**extra))
        args.report.write_text(json.dumps(report,indent=2)+'\n');print('PASS:',name,flush=True)
    try:
        if args.group in ('all','normal'):
            for size,kib in ((16,128),(64,16384)):
                p=start(size=size,reu_kib=kib);p.check(b'',0,False)
                assert p.value('vs_reu')==p.value('ru_active')==1
                base,pages=p.value('vd_base')*256,p.value('vd_pages')
                assert p.bus.reu_ram[:pages*256]==p.bus.original[0][base:base+pages*256]
                assert p.bus.reu_ram[pages*256:]==p.bus.reu_original[pages*256:]
                tokens=p.data('vs_token',8)+p.data('bk_handle',4)+p.data('eg_handle',4)
                assert component(p,'vs_token',8)==tokens[:8]
                free=bytes(p.ram[0x3800:0x3a00]).count(0)
                assert free==426-96-16-36-COMPONENT_PAGES
                assert p.value('dm_mode')==2 and p.value('dm_lease')==1
                p.prompt(0x85,'SOURCE');p.check(raw,0,False,name='SOURCE')
                assert p.state()['backing']==1 and p.state()['chunks']==1
                document_start,count=extent(p,p.state())
                p.key(0x86);p.type('COPY');preferences=Picker(p).preferences();p.key(0x88)
                rows=expected(p.io.files,9)
                for row in rows:row['app']=False
                Picker(p).check(rows,mode=2,device=9);p.mirror();p.key(27)
                p.check(raw,0,False,name='SOURCE',mode=2);assert Picker(p).preferences()==preferences
                assert p.data('vs_token',8)+p.data('bk_handle',4)+p.data('eg_handle',4)==tokens
                assert component(p,'vs_token',8)==tokens[:8]
                p.key(13);p.check(raw,0,False,status=1,name='COPY')
                assert bytes(p.io.files[9,b'COPY',b'S'])==raw and bytes(p.io.files[9,b'SOURCE',b'S'])==raw
                assert p.data('vs_token',8)+p.data('bk_handle',4)+p.data('eg_handle',4)==tokens
                p.exit();p.restored()
                assert p.bus.reu_ram[pages*256:document_start]==p.bus.reu_original[pages*256:document_start]
                assert p.bus.reu_ram[document_start+count:]==p.bus.reu_original[document_start+count:]
                assert not p.value('dm_lease')
                done(f'{size} KiB VDC / {kib} KiB REU retains documents, picker and exact display backup',p,free_pages=free,file_bytes=len(raw))
        if args.group in ('all','recovery'):
            p=start(size=64);p.check(b'',0,False)
            p.bus.reu_fault_from=len(p.bus.reu_transactions)+1;p.key(27);p.poll()
            assert p.value('vd_phase')==2 and p.value('vd_fault')==17 and p.value('eg_vdc_warned')
            ignored(p)
            p.bus.reu_fault_from=None;p.key(27,exited=True);p.restored()
            done('failed REU screen reads block exit and edits until restoration succeeds',p)
            p=start(size=16,fault_start=2)
            assert p.value('vd_phase')==1 and p.value('ru_probe_live')
            p.key(ord('A'));ignored(p);assert p.contents()==b''
            p.bus.reu_fault_from=None;p.key(27,exited=True);p.restored()
            assert p.bus.reu_ram==p.bus.reu_original and not p.value('ru_probe_live')
            done('failed REU probe recovery retains every byte and refuses document edits',p)
        report['passed']=True
    finally:
        gui.PointerBus=original;args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
