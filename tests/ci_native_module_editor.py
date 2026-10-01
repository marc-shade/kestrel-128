#!/usr/bin/env python3
"""Keep real editor state through cold/warm module use and source failures."""
import argparse
import hashlib
import json
from pathlib import Path

from ci_native_editor import Editor,ROOT
from ci_native_file_dialog import DialogEditor
from ci_native_directory_ultimate import DirectoryDOS
from ci_native_ultimate import UltimateBus
from ci_native_heap import symbol

MODULE=(ROOT/'target/native/edpick.prg').read_bytes()


class ModuleEditor(DialogEditor):
    def __init__(self,source=None,context=1):
        kwargs=dict(source_path=source,source_context=context) if source else {}
        Editor.__init__(self,{(9,b'NOTE',b'S'):b'ORIGINAL\rBYTES'},9,0,**kwargs)
        self.frames=0
        files=dict(self.ultimate.files) if hasattr(self,'ultimate') else {}
        self.ultimate=DirectoryDOS(files=files)
        self.m.bus=UltimateBus(self.m.bus,self.ultimate);self.cpu.memory=self.m.bus
        self.source=source
        self.module_path=source.rsplit(b'/',1)[0]+b'/EDPICK.PRG' if source else None

    def install(self,image):
        if self.source:
            if image is None:self.ultimate.files.pop(self.module_path,None)
            else:self.ultimate.files[self.module_path]=bytearray(image)
        else:
            key=(8,b'EDPICK.PRG',b'P')
            if image is None:self.io.files.pop(key,None)
            else:self.io.files[key]=bytearray(image)

    def field_bytes(self):
        at=self.symbol('ed_field_state')
        return bytes(self.ram[at:at+8]),self.string('ed_field')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path);args=parser.parse_args()
    report=dict(passed=False,images={n:hashlib.sha256((ROOT/'target/native'/n).read_bytes()).hexdigest()
        for n in ('kestrel.prg','editor.prg','edpick.prg')},cases={})
    try:
        for source,context in ((None,1),(b'/Usb0/Tools/TEXT EDITOR.PRG',1),(b'/Usb0/Tools/TEXT EDITOR.PRG',2)):
            for fault in ('missing','crc','short','parent'):
                e=ModuleEditor(source,context);e.keep_workspaces()
                e.prompt(0x85,'NOTE');e.key(5);e.type('!')
                wanted=b'ORIGINAL!\rBYTES';e.check(wanted,cursor=9,dirty=True,name='NOTE')
                e.key(0x86);e.type('SAVED');e.key(0x9d);before=e.field_bytes()
                bad=bytearray(MODULE)
                if fault=='missing':bad=None
                elif fault=='crc':bad[-1]^=1
                elif fault=='short':bad=bad[:600]
                else:bad[12]^=1
                e.install(bad);e.key(9)
                assert e.ram[0x3d1b]==0 and not e.value('fd_active')
                e.check(wanted,cursor=9,dirty=True,name='NOTE',mode=2,status=2)
                assert e.field_bytes()==before and not e.io.handles and e.ultimate.handles=={1:None,2:None}
                e.check_workspaces();e.install(MODULE)
                # Document calls changed UPATH/format/device. The original
                # app source still supplies the module at this explicit retry.
                e.ram[0x4e00:0x4f00]=b'X'*256
                e.key(9);assert e.value('fd_active') and e.ram[0x3d1b]==3
                token=bytes(e.ram[0x3d17:0x3d1a]);e.key(27)
                assert e.ram[0x3d1b]==2 and e.field_bytes()==before
                e.check(wanted,cursor=9,dirty=True,name='NOTE',mode=2,status=0)
                e.check_workspaces()
                # A warm call must work even after the source file disappears.
                e.install(None);e.key(9);assert e.value('fd_active')
                e.key(27);assert bytes(e.ram[0x3d17:0x3d1a])==token
                assert e.field_bytes()==before
                e.key(13);e.check(wanted,cursor=9,dirty=False,name='SAVED',status=1)
                assert bytes(e.io.files[9,b'SAVED',b'S'])==wanted
                e.release_workspaces();e.exit()
                label=f'{"usb"+str(context) if source else "iec"}-{fault}-retry-warm-save'
                report['cases'][label]=dict(instructions=e.instructions,events=e.events,bytes=len(wanted))
                print('PASS: native module editor '+label,flush=True)
        report['passed']=True
    except BaseException as error:report['error']=str(error);raise
    finally:
        if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
