#!/usr/bin/env python3
"""Full Files picker graphics, literal paths and verified IEC-to-Ultimate copy."""
import argparse
import json
from pathlib import Path
from ci_native_vdc_files import Files,gui,VDCBus
from native_picker_fixture import Picker


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--size',type=int,choices=(16,64))
    args=parser.parse_args();original=gui.PointerBus
    report=dict(passed=False,physical_hardware_io=False,cases=[])
    try:
        for size in ((args.size,) if args.size else (16,64)):
            gui.PointerBus=type('FilesPickerVDC',(VDCBus,),dict(size=size,addressing=64))
            raw=bytes(range(256))*6+b'END'
            directories={b'/':[b'\x10Usb0'],b'/Usb0':[b'\x20EXISTING']}
            p=Files({(9,b'SOURCE',b'S'):raw},usb={b'/Usb0/EXISTING':b'KEEP'},directories=directories)
            p.key(ord('C'));p.rename('COPY');p.copy(b'SOURCE',b'COPY')
            picker=Picker(p);preferences=picker.preferences();free=p.m.stats()
            owner=p.data('bk_handle',4);snapshot=p.data('vd_handle',4)
            p.key(0x88);p.type('FFF')
            picker.check(mode=2,fmt=3,device=1,path=b'/',entries=directories[b'/'])
            picker.frame();picker.click(16)
            picker.check(mode=2,fmt=3,device=1,path=b'/Usb0',entries=directories[b'/Usb0'])
            p.key(ord('G'))
            picker.check(mode=2,fmt=3,device=1,path=b'/Usb0',entries=directories[b'/Usb0'],prompt=3,field='/Usb0')
            p.key(21);before=p.bus.data_writes;p.key(ord('/'))
            picker.check(mode=2,fmt=3,device=1,path=b'/Usb0',entries=directories[b'/Usb0'],prompt=3,field='/')
            field_writes=p.bus.data_writes-before;assert 0<field_writes<6000
            p.key(27)
            picker.check(mode=2,fmt=3,device=1,path=b'/Usb0',entries=directories[b'/Usb0'])
            picker.move(310,190);before=p.bus.data_writes;picker.frame(dx=1)
            pointer_writes=p.bus.data_writes-before;assert 0<pointer_writes<=96
            picker.click(17)
            p.copy(b'SOURCE',b'/Usb0/COPY',device=1,fmt=3)
            assert p.data('bk_handle',4)==owner and p.data('vd_handle',4)==snapshot
            assert p.m.stats()==free and picker.preferences()==preferences
            p.key(13);p.copy(b'SOURCE',b'/Usb0/COPY',device=1,fmt=3,copied=len(raw),verified=len(raw),status=1)
            assert bytes(p.ultimate.files[b'/Usb0/COPY'])==raw
            assert bytes(p.ultimate.files[b'/Usb0/EXISTING'])==b'KEEP'
            assert p.ultimate.handles=={1:None,2:None}
            assert p.ultimate.paths=={1:b'/shell',2:b'/browser'}
            p.key(27);p.browser();p.key(27,exited=True);p.restored()
            report['cases'].append(dict(name=f'{size} KiB complete picker and verified cross-backend copy',
                passed=True,instructions=p.instructions,keys=p.events,picker_canvases=picker.checked,
                field_vdc_writes=field_writes,pointer_vdc_writes=pointer_writes,file_bytes=len(raw)))
            args.report.write_text(json.dumps(report,indent=2)+'\n')
            print('PASS:',report['cases'][-1]['name'],flush=True)
        report['passed']=True
    finally:
        gui.PointerBus=original;args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
