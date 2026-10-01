#!/usr/bin/env python3
"""Full VDC picker canvases, path editing, mouse input and one confirmed mount."""
import argparse
import json
from pathlib import Path
from ci_native_vdc_controls import Panel, VDCBus, heap
from native_picker_fixture import Picker


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args();original_bus=heap.Bus
    report=dict(passed=False,physical_hardware_io=False,cases=[])
    try:
        for size in (16,64):
            heap.Bus=type('PickerVDC',(VDCBus,),dict(size=size,addressing=64))
            app=Panel();app.device.directories[b'/']=[b'\x10Usb0']
            app.key(ord('D'));app.key(0x11);app.check()
            before=app.m.stats();saved=Picker(app).preferences()
            token=bytes(app.ram[app.symbol('bk_handle'):app.symbol('bk_handle')+4])
            app.key(ord('M'));picker=Picker(app)
            picker.check(fmt=3,device=1,path=b'/',entries=[b'\x10Usb0'])
            picker.frame();picker.click(16)
            picker.check(fmt=3,device=1,path=b'/Usb0',entries=[b'\x20work.d64'])
            app.key(ord('G'))
            picker.check(fmt=3,device=1,path=b'/Usb0',entries=[b'\x20work.d64'],prompt=3,field='/Usb0')
            app.key(21)
            writes=app.bus.data_writes
            app.key(ord('/'))
            picker.check(fmt=3,device=1,path=b'/Usb0',entries=[b'\x20work.d64'],prompt=3,field='/')
            field_writes=app.bus.data_writes-writes
            assert 0<field_writes<6000,field_writes
            app.key(27)
            picker.check(fmt=3,device=1,path=b'/Usb0',entries=[b'\x20work.d64'])
            picker.move(310,190)
            writes=app.bus.data_writes;picker.frame(dx=1)
            assert app.bus.data_writes-writes<=96,'pointer move redrew the dialog'
            picker.click(16)
            assert not app.value('ug_picker_active') and app.value('ug_mode')==1
            app.check();app.clean()
            assert app.m.stats()==before and not app.value('ug_scratch_handle')
            assert picker.preferences()==saved
            assert bytes(app.ram[app.symbol('bk_handle'):app.symbol('bk_handle')+4])==token
            assert not app.device.mutations
            app.key(9);app.check();app.key(13);app.check()
            assert app.device.mutations==[b'\x01\x23\x09/Usb0/work.d64']
            app.key(27,exited=True);app.restored()
            report['cases'].append(dict(name=f'{size} KiB / 64 KiB addressing: complete picker and confirmed mount',
                passed=True,instructions=app.instructions,keys=app.events,frames=app.frames,
                picker_canvases=picker.checked,field_vdc_writes=field_writes,
                command=app.device.mutations[0].hex()))
            args.report.write_text(json.dumps(report,indent=2)+'\n')
            print('PASS:',report['cases'][-1]['name'],flush=True)
        report['passed']=True
    finally:
        heap.Bus=original_bus
        args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
