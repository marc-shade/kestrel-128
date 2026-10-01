#!/usr/bin/env python3
"""Native browser cache, navigation, app requests and binary previews on CPU."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from ci_native_calc import Calculator,ROOT
sys.path.insert(0,str(ROOT))
from native_browser_check import browser_screen,preview_screen


class Browser(Calculator):
    instruction_limit=20000000
    allow_busy_poll=True

    def __init__(self,files=None,device=8,fmt=0,*,ultimate_files=None):
        super().__init__('browse',files,loader_name=b'BROWSE',device=device,fmt=fmt,ultimate_files=ultimate_files)
        self.original={key:bytes(value) for key,value in self.io.files.items()}

    def word(self,name):
        address=self.symbol(name);return int.from_bytes(self.ram[address:address+2],'little')

    def records(self):
        handle=self.ram[self.symbol('b_cache')]
        descriptor=0x3c00+(handle-1)*8
        assert self.ram[descriptor:descriptor+2]==bytes([32,1])
        start=self.ram[descriptor+2]*256
        return [bytes(self.m.bus.ram[1][start+i*32:start+(i+1)*32]) for i in range(self.word('b_total'))]

    def check(self,records,error=None,prompt=None):
        for bank,columns in enumerate((40,80)):
            want=browser_screen(columns,records,self.word('b_selected'),self.ram[0x3d29],self.ram[0x3d2a],error,prompt)
            assert self.screens[bank]==want,(bank,'browser complete screen')
        assert {key:bytes(value) for key,value in self.io.files.items()}==self.original

    def preview(self,name,data,offset=0,eof=False,error=None):
        assert self.value('b_preview')==1 and self.value('b_view_count')==len(data)
        for bank,columns in enumerate((40,80)):
            assert self.screens[bank]==preview_screen(columns,name,data,offset,eof,error),(bank,'preview complete screen')
        assert self.value('b_eof')==int(eof or bool(error))


def expected(files,device):
    return [dict(name=name,type=(b'S',b'P',b'U').index(kind)+1,flags=128,
                 blocks=max(1,(len(data)+253)//254),app=len(data)>=34 and data[:6]==b'\0\x60NAPP')
            for (dev,name,kind),data in files.items() if dev==device]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path);args=parser.parse_args()
    report=dict(passed=False,images={name:hashlib.sha256((ROOT/'target/native'/name).read_bytes()).hexdigest()
                                  for name in ('kestrel.prg','calc.prg','browse.prg')},cases={})
    cases=report['cases']
    def done(name,b):cases[name]=dict(events=b.events,instructions=b.instructions,files=len(b.io.files))
    try:
        data=bytes(range(256))+b'\0\r';calc=(ROOT/'target/native/calc.prg').read_bytes()
        files={(8,b'BINARY',b'S'):data,(8,b'ZERO',b'S'):b'\0',(8,b'EMPTY',b'S'):b'',(8,b'CALC',b'P'):calc}
        b=Browser(files);records=expected(b.io.files,8);b.check(records)
        assert b.m.stats()==(175-b.image[12],214,30)
        assert [r[2:18].rstrip(b'\xa0') for r in b.records()]==[r['name'] for r in records]
        b.key(13);b.preview(b'BINARY',data[:128])
        b.type('N');b.preview(b'BINARY',data[128:256],128)
        b.key(13);b.preview(b'BINARY',data[256:],256,eof=True)
        reads=b.io.reads;b.type('N');assert b.io.reads==reads
        b.key(27);b.check(records)
        b.key(0x11);b.key(13);b.preview(b'ZERO',b'\0',eof=True);b.key(27)
        b.key(0x11);b.key(13);b.preview(b'EMPTY',b'',eof=True);b.key(27)
        b.type('A');assert b.word('b_selected')==3;b.check(records)
        b.key(13,exited=True)
        assert b.ram[0x3d28]==1 and b.ram[0x3d21:0x3d23]==bytes([8,4]) and b.ram[0x3d40:0x3d44]==b'CALC'
        done('binary-tiny-empty-and-app-handoff',b)
        files={(8,f'FILE{i:02}'.encode(),b'S'):bytes([i])*i for i in range(18)}
        b=Browser(files);records=expected(b.io.files,8)
        for key,wanted in [('N',8),('N',16),('N',18),('B',10),('B',2),('B',0)]:
            b.type(key);assert b.word('b_selected')==wanted;b.check(records)
        b.type('D12');b.check(records,prompt='12');b.key(20);b.check(records,prompt='1')
        b.key(13);assert b.value('b_prompt')==1
        b.key(27);b.check(records)
        b.key(0x91);assert b.word('b_selected')==0
        b.type('R');b.check(records)
        b.key(27,exited=True);assert b.ram[0x3d28]==2
        done('paging-device-prompt-refresh-and-workspace',b)
        for fmt in (1,2):
            files={(9,b'CALC',b'P'):calc,(9,b'SIXTEENCHARACTER',b'U'):b'abc'}
            b=Browser(files,device=9,fmt=fmt);records=expected(b.io.files,9);b.check(records)
            b.key(13,exited=True)
            assert b.ram[0x3d28]==1 and b.ram[0x3d21]==9 and b.ram[0x3d2c]==fmt
            done(f'device-9-format-{fmt}-app-context',b)
        b=Browser({(9,b'NOTE',b'S'):b'abcdef'},device=9);records=expected(b.io.files,9)
        b.type('A');b.check(records,error='NO NATIVE APPLICATIONS FOUND')
        b.type('R');b.check(records)
        b.io.fail_read=3;b.key(13);b.preview(b'NOTE',b'abc',error='DISK I/O ERROR')
        b.key(27);b.key(27,exited=True);done('no-apps-and-preview-error',b)
        for kind in (b'S',b'P'):
            files={(9,b'A',kind):calc if kind==b'P' else b'FIRST',
                   (9,b'A\xa0B',kind):calc if kind==b'P' else b'SECOND'}
            b=Browser(files,device=9);records=expected(b.io.files,9)
            records[1]['app']=False
            b.check(records)
            assert b.records()[1][20]==0,'unsupported name was discovered through a shorter alias'
            b.key(0x11);before=list(b.io.events);b.key(13)
            assert b.value('b_preview')==0 and b.io.events==before,'selected name opened its shorter prefix'
            assert b.ram[0x3d86]==3 and b.ram[0x3da0:0x3da3]==b'A\xa0B'
            b.check(records,error='INVALID NAME OR DEVICE')
            b.key(27,exited=True);done('embedded-shifted-space-'+kind.decode(),b)
        files={(9,f'F{i:03}'.encode(),b'S'):b'' for i in range(296)}
        b=Browser(files,device=9,fmt=2);records=expected(b.io.files,9);b.check(records)
        assert b.word('b_total')==296 and len(b.records())==296
        for _ in range(36):b.type('N')
        assert b.word('b_selected')==288;b.check(records)
        for _ in range(7):b.key(0x11)
        assert b.word('b_selected')==295;b.check(records)
        b.key(0x11);assert b.word('b_selected')==295
        b.key(27,exited=True);done('complete-d81-capacity-and-16-bit-selection',b)
        report['passed']=True
        print(f'PASS: {len(cases)} native browser workflows, complete screens, previews and owned handoff',flush=True)
    except BaseException as error:report['error']=str(error);raise
    finally:
        if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
