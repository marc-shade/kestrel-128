#!/usr/bin/env python3
"""Full editor UI, owned native file backend and UCI/FAT byte model together."""
import argparse
import hashlib
import json
from pathlib import Path

from ci_native_editor import Editor,ROOT
from ci_native_ultimate import UltimateBus,DOSFiles


class UltimateEditor(Editor):
    def __init__(self,files=None):
        super().__init__()
        self.ultimate=DOSFiles(files)
        self.ultimate.direct_write_corruption=True
        self.ultimate.fragment=103
        self.m.bus=UltimateBus(self.m.bus,self.ultimate);self.cpu.memory=self.m.bus
        for _ in range(3):self.key(0x8b)
        assert self.value('ed_format')==3 and self.value('ed_device')==1
        self.check(b'',0,False)

    def check(self,*args,**kwargs):
        super().check(*args,**kwargs)
        if hasattr(self,'ultimate') and kwargs.get('released',True):
            assert self.ultimate.handles=={1:None,2:None}
            assert self.ultimate.paths=={1:b'/shell',2:b'/browser'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path);args=parser.parse_args()
    report=dict(passed=False,images={n:hashlib.sha256((ROOT/'target/native'/n).read_bytes()).hexdigest()
                for n in ('kestrel.prg','editor.prg')},cases={})
    def done(name,e):
        report['cases'][name]=dict(events=e.events,instructions=e.instructions,commands=len(e.ultimate.commands))
        print('PASS: native Ultimate editor '+name,flush=True)
    try:
        raw=b'ONE "QUOTED" LINE\r\nTWO\nTHREE\r'+bytes([0,255])+b' END'
        name='/USB0/'+('LONG PATH/'*4)+'SOURCE.TXT'
        e=UltimateEditor({name.encode():raw,b'/USB0/EMPTY':b''})
        e.prompt(0x85,name);e.check(raw,0,False,name=name)
        e.prompt(0x88,'000005');e.type('!');want=raw[:5]+b'!'+raw[5:]
        e.check(want,6,True,name=name)
        save='/USB0/'+('OTHER PATH/'*5)+'COPY.TXT'
        e.prompt(0x86,save);e.check(want,6,False,name=save,status=1)
        assert e.ultimate.files[save.encode()]==want
        e.type('?');changed=want[:6]+b'?'+want[6:]
        e.prompt(0x86,save);e.check(changed,7,True,name=save,status=7)
        assert e.ultimate.files[save.encode()]==want
        e.prompt(0x8c,'2');assert e.value('ed_device')==2
        e.prompt(0x8c,'8');e.check(changed,7,True,status=4,mode=4);e.key(27)
        e.prompt(0x85,'/USB0/EMPTY',confirm='Y');e.check(b'',0,False,name='/USB0/EMPTY')
        e.prompt(0x86,'/USB0/EMPTY COPY');e.check(b'',0,False,status=1,name='/USB0/EMPTY COPY')
        e.exit();done('long-path-screens-mixed-bytes-exclusive-save-and-two-contexts',e)

        raw=b'X'*1557;e=UltimateEditor({b'/SOURCE':raw})
        e.prompt(0x85,'/SOURCE');e.type('!');want=b'!'+raw
        e.ultimate.write_limit=17;e.prompt(0x86,'/SHORT')
        e.check(want,1,True,name='/SOURCE',status=7)
        e.ultimate.write_limit=None
        def corrupt(command,reply):
            if command[2]==1 and command[3:]==b'/BAD REOPEN':
                e.ultimate.files[b'/BAD REOPEN'][-1]^=1
            return reply
        e.ultimate.inject[2]=corrupt;e.prompt(0x86,'/BAD REOPEN')
        e.check(want,1,True,name='/SOURCE',status=7)
        e.ultimate.inject.clear()
        e.cancel_transfer(0x86,'/CANCELLED');e.check(want,1,True,status=10,name='/SOURCE')
        assert e.ultimate.files[b'/CANCELLED']==want[:512]
        e.prompt(0x86,'/RECOVER');e.check(want,1,False,status=1,name='/RECOVER')
        e.exit();done('short-write-reopen-mismatch-cancel-and-recovery',e)

        raw=(b'0123456789 ABCDEFGHIJKLMNOPQRSTUVWXYZ\r\n'*1800)[:66053]
        e=UltimateEditor({b'/USB0/LARGE':raw,b'/USB0/ANOTHER':raw})
        e.prompt(0x85,'/USB0/LARGE');e.check(raw,0,False,name='/USB0/LARGE');assert e.banks=={0,1}
        e.prompt(0x88,'010001');e.type('C128');e.key(20)
        want=raw[:65537]+b'C12'+raw[65537:]
        e.check(want,65540,True,name='/USB0/LARGE')
        e.prompt(0x85,'/USB0/ANOTHER',confirm='Y')
        e.check(want,65540,True,name='/USB0/LARGE',status=3)
        e.prompt(0x86,'/USB0/LARGE COPY');e.check(want,65540,False,name='/USB0/LARGE COPY',status=1)
        assert e.ultimate.files[b'/USB0/LARGE COPY']==want
        e.key(0x87);e.check(b'',0,False)
        e.prompt(0x85,'/USB0/LARGE COPY');e.check(want,0,False,name='/USB0/LARGE COPY')
        e.exit();done('over-64-KiB-bank-boundary-oom-preservation-save-and-reopen',e)
        report['saved']=dict(bytes=len(want),sha256=hashlib.sha256(want).hexdigest())
        report['passed']=True
    except BaseException as error:report['error']=str(error);raise
    finally:
        if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
