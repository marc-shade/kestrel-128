#!/usr/bin/env python3
"""Paint's shared picker and long-name field over real native UCI services."""
import argparse
import hashlib
import json
from pathlib import Path

from ci_native_paint_gui import GraphicalPaint
from ci_native_directory_ultimate import DirectoryDOS
from ci_native_ultimate import UltimateBus
from native_paint_format import encode


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True);args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    report=dict(passed=False,physical_hardware_io=False,cases=[],images={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (root/'target/native-desktop/paint.prg',root/'target/native/kestrel.prg')})
    try:
        p=GraphicalPaint();p.ultimate=DirectoryDOS();p.ultimate.fragment=103;p.ultimate.direct_write_corruption=True
        p.ultimate.directories.update({b'/':[b'\x10Usb0'],b'/Usb0':[b'\x10Pictures'],b'/Usb0/Pictures':[]})
        p.m.bus=UltimateBus(p.m.bus,p.ultimate);p.cpu.memory=p.m.bus
        preferences=(bytes(p.ram[0x3d29:0x3d35]),bytes(p.ram[0x4a00:0x4b00]),bytes(p.ram[0x3e00:0x3f00]))
        p.key(32);p.type('SPICTURE');p.key(9);p.type('FFF')
        p.key(0x11)  # Select the only row and focus Choose after the format change.
        p.key(13);p.key(13);p.type('S');p.check()
        assert p.value('pf_device')==1 and p.value('pf_format')==3
        assert bytes(p.ram[p.symbol('pf_name'):p.symbol('pf_name')+p.value('pf_length')])==b'/Usb0/Pictures/PICTURE'
        assert preferences==(bytes(p.ram[0x3d29:0x3d35]),bytes(p.ram[0x4a00:0x4b00]),bytes(p.ram[0x3e00:0x3f00]))
        p.key(13);p.check();assert p.ultimate.files[b'/Usb0/Pictures/PICTURE']==encode(p.document())
        p.clean();assert p.ultimate.paths=={1:b'/shell',2:b'/browser'}
        report['cases'].append('IEC-to-Ultimate folder picker, full-path Save As, verified bytes and browser/DOS restoration')
        p.key(ord('S'));p.key(13);p.check();assert p.value('pa_status') in (4,8)
        assert p.ultimate.files[b'/Usb0/Pictures/PICTURE']==encode(p.document())
        p.key(ord('C'));p.key(ord('O'));p.key(ord('O'));assert p.value('pa_picker_active')
        p.key(0x85);p.key(13);p.check();assert p.document()[0]==128 and p.value('pf_device')==2
        p.clean();assert p.ultimate.paths=={1:b'/shell',2:b'/browser'}
        report['cases'].append('exclusive collision leaves saved image intact; context-2 Open restores the full picture')
        name=b'/Usb0/'+b'P'*60+b'/'+b'Q'*60+b'/'+b'R'*60+b'/'+b'S'*61+b'.UPNT'
        assert len(name)==255
        p.name(name,device=2,fmt=3);p.key(ord('S'));p.check();assert p.value('pa_field_caret')==255
        p.key(0x9d);p.key(20);p.check();p.key(ord('Z'));p.check();assert p.value('pf_length')==255
        p.key(0x13);p.check();assert p.value('pa_field_caret')==0 and p.value('pa_field_view')==0
        p.key(27);p.close();p.restored()
        report['cases'].append('255-byte path field, clipped caret, insertion/delete/Home and cancellation without document loss')
        report.update(passed=True,keys=p.events,instructions=p.instructions)
        print('PASS:',*report['cases'],sep='\n',flush=True)
    except BaseException as error:report['error']=repr(error);raise
    finally:args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
