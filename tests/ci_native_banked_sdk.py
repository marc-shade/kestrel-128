#!/usr/bin/env python3
"""Run both complete consoles of the separate-file banked SDK example."""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import tempfile

from py65.devices.mpu6502 import MPU
import ci_native_heap as heap
from ci_native_calc import Calculator
from ci_native_files import StreamIEC
from ci_native_ultimate import DOSFiles,UltimateBus
from native_banked_bus import BankedBus

ROOT = Path(__file__).resolve().parents[1]
APP = b'BANKDEMO.PRG'
PROVIDER = b'BKREU.PRG'


class Demo(Calculator):
    instruction_limit = 12000000

    def __init__(self,output,*,fmt=0,context=1,present=True,corrupt=False,missing=False):
        heap.Bus = type('Bus',(BankedBus,),dict(reu_present=present))
        self.m = heap.Machine(); self.ram = self.m.ram
        self.image_name = 'banked-sdk'
        self.image = (output/'BANKDEMO.PRG').read_bytes()
        provider = bytearray((output/'BKREU.PRG').read_bytes())
        if corrupt: provider[-1] ^= 1
        self.symbols = {}
        for name in ('parent','provider'):
            self.symbols[name] = {n:int(v,16) for n,v in re.findall(r'^(\w+)\s*=\s*\$([\da-fA-F]+)',
                                                    (output/(name+'.sym')).read_text(),re.M)}
        probe = self.symbols['provider']['ru_probe_data']
        self.m.bus.reu_bank1_hosts.append((probe,probe+2))
        self.io = StreamIEC(self.m,{(8,APP,b'P'):self.image,(8,PROVIDER,b'P'):provider})
        if missing: del self.io.files[8,PROVIDER,b'P']
        self.io.formats[8] = min(fmt,2)
        self.ram[0x3d21:0x3d23] = bytes([8,len(APP)])
        self.ram[0x3d40:0x3d40+len(APP)] = APP
        self.ram[0x3d2c:0x3d2e] = bytes([fmt,8])
        if fmt == 3:
            path = b'/Usb0/SDK/'+APP
            self.ultimate = DOSFiles({path:self.image,b'/Usb0/SDK/'+PROVIDER:provider})
            if missing: del self.ultimate.files[b'/Usb0/SDK/'+PROVIDER]
            self.ultimate.fragment = 7
            self.m.bus = UltimateBus(self.m.bus,self.ultimate)
            self.ram[0x3d21:0x3d23] = bytes([context,len(path)])
            self.ram[0x4e00:0x4e00+len(path)] = path
        self.initial_reu = bytes(self.m.bus.reu_ram)
        self.cpu = MPU(memory=self.m.bus,pc=0x1c38)
        self.cpu.sp,self.cpu.p = 0xe0,0x20
        self.cpu.stPushWord(0xaff)
        self.screens = [bytearray(b' '*1000),bytearray(b' '*2000)]
        self.reverse = [False,False]; self.row=[0,0];self.col=[0,0];self.keys=[]
        self.events=self.instructions=0;self.observation_target=None;self.observation_done=False
        self.loop()

    def symbol(self,name):
        return self.symbols['parent']['input_loop' if name == 'cloop' else name]

    def check(self,passes=0,error=0):
        assert (self.value('demo_passes'),self.value('demo_error')) == (passes,error)
        lines = ['BANKED MEMORY DEMO',f'PASSED TESTS (HEX): ${passes:02X}',
                 f'LAST ERROR (HEX): ${error:02X}','','RETURN: 512-BYTE REU WRITE/READ TEST',
                 'ESC: RELEASE RESOURCES AND EXIT']
        for screen,columns in zip(self.screens,(40,80)):
            expected = bytearray(b' '*(columns*25))
            for row,line in enumerate(lines):
                expected[row*columns:row*columns+len(line)] = bytes(v-64 if 64<=v<96 else v for v in line.encode())
            assert screen == expected, columns


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    work=Path(tempfile.mkdtemp(prefix='kestrel-banked-sdk-'))
    spec=importlib.util.spec_from_file_location('banked_build',ROOT/'examples/native-banked/build.py')
    build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)
    images=build.build(work)
    report=dict(passed=False,physical_hardware_io=False,work=str(work),images=images,cases=[])
    try:
        for fmt,context,present,corrupt,missing in ((0,1,True,False,False),(1,1,True,False,False),
                (2,1,True,False,False),(3,1,True,False,False),(3,2,True,False,False),
                (0,1,False,False,False),(3,1,True,True,False),(0,1,True,False,True),(3,1,True,False,True)):
            demo=Demo(work,fmt=fmt,context=context,present=present,corrupt=corrupt,missing=missing)
            error=17 if missing else 20 if corrupt else 0 if present else 21
            demo.check(error=error)
            expected=bytearray(demo.initial_reu)
            for number in range(1,4):
                demo.key(13)
                demo.check(passes=number if not error else 0,error=error)
            if not error: expected[:512]=bytes(range(256))+bytes(i^0x55 for i in range(256))
            assert demo.m.bus.reu_ram == expected
            demo.key(27,exited=True)
            assert demo.m.bus.reu_ram == expected
            if hasattr(demo,'ultimate'): assert demo.ultimate.handles == {1:None,2:None}
            report['cases'].append(dict(format=fmt,context=context,present=present,corrupt=corrupt,missing=missing,
                complete_screens=8,events=demo.events,instructions=demo.instructions,exit_releases_all=True))
            print('PASS: SDK',fmt,context,present,corrupt,flush=True)
        report['passed']=True
    finally:
        args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__ == '__main__': main()
