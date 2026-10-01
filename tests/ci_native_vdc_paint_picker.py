#!/usr/bin/env python3
"""Paint's graphical picker, literal image load/save and retained VDC lifetime."""
import argparse
import json
from pathlib import Path
from ci_native_vdc_paint import Paint, heap, VDCBus
from ci_native_paint_files import pattern
from ci_native_directory_ultimate import DirectoryDOS
from ci_native_ultimate import UltimateBus
from native_paint_format import encode
from native_picker_fixture import Picker


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args();original=heap.Bus
    report=dict(passed=False,physical_hardware_io=False,cases=[])
    try:
        for size in (16,64):
            heap.Bus=type('PaintPickerVDC',(VDCBus,),dict(size=size,addressing=64))
            p=Paint();wanted=pattern(43);dos=DirectoryDOS();dos.fragment=103
            dos.direct_write_corruption=True
            dos.directories.update({b'/':[b'\x10Usb0'],b'/Usb0':[b'\x20picture.upnt']})
            dos.files[b'/Usb0/picture.upnt']=bytearray(encode(wanted))
            p.ultimate=dos;p.m.bus=UltimateBus(p.m.bus,dos);p.cpu.memory=p.m.bus
            p.name(b'/',device=1,fmt=3)
            picker=Picker(p);preferences=picker.preferences();free=p.m.stats()
            owner=bytes(p.ram[p.symbol('bk_handle'):p.symbol('bk_handle')+4])
            snapshot=bytes(p.ram[p.symbol('vd_handle'):p.symbol('vd_handle')+4])
            p.key(ord('O'));picker.check(fmt=3,device=1,path=b'/',entries=[b'\x10Usb0'])
            picker.frame();picker.click(16)
            picker.check(fmt=3,device=1,path=b'/Usb0',entries=[b'\x20picture.upnt'])
            p.key(ord('G'));picker.check(fmt=3,device=1,path=b'/Usb0',entries=[b'\x20picture.upnt'],prompt=3,field='/Usb0')
            p.key(21);before=p.bus.data_writes;p.key(ord('/'))
            picker.check(fmt=3,device=1,path=b'/Usb0',entries=[b'\x20picture.upnt'],prompt=3,field='/')
            field_writes=p.bus.data_writes-before;assert 0<field_writes<6000
            p.key(27);picker.check(fmt=3,device=1,path=b'/Usb0',entries=[b'\x20picture.upnt'])
            picker.move(310,190);before=p.bus.data_writes;picker.frame(dx=1)
            pointer_writes=p.bus.data_writes-before;assert pointer_writes<=96
            picker.click(16);p.check();p.clean()
            assert p.document()==wanted and not p.value('pd_dirty')
            assert p.m.stats()==free and picker.preferences()==preferences
            assert bytes(p.ram[p.symbol('bk_handle'):p.symbol('bk_handle')+4])==owner
            assert bytes(p.ram[p.symbol('vd_handle'):p.symbol('vd_handle')+4])==snapshot
            assert dos.handles=={1:None,2:None} and dos.paths=={1:b'/shell',2:b'/browser'}
            p.name(b'/Usb0/COPY.UPNT',device=1,fmt=3);p.key(ord('S'));p.check();p.key(13);p.check()
            assert dos.files[b'/Usb0/COPY.UPNT']==encode(wanted);p.clean()
            p.key(ord('U'));p.check();assert p.document()==bytes(8192)+b'\x10'*1024
            p.close();p.restored()
            report['cases'].append(dict(name=f'{size} KiB full graphical picker and verified UPNT load/save',
                passed=True,instructions=p.instructions,keys=p.events,picker_canvases=picker.checked,
                field_vdc_writes=field_writes,pointer_vdc_writes=pointer_writes,file_bytes=len(encode(wanted))))
            print('PASS:',report['cases'][-1]['name'],flush=True)
            args.report.write_text(json.dumps(report,indent=2)+'\n')
        report['passed']=True
    finally:
        heap.Bus=original;args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
