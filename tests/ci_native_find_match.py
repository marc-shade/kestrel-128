#!/usr/bin/env python3
"""Compare the assembled matcher with an independent byte-string oracle."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from hwlib import lst_symbol
from py65.devices.mpu6502 import MPU


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    image=(ROOT/'target/native-desktop/fsview.prg').read_bytes()
    ram=bytearray(65536);origin=int.from_bytes(image[:2],'little')
    ram[origin:origin+len(image)-2]=image[2:]
    cpu=MPU(memory=ram)
    symbols={n:lst_symbol('native-desktop/files',n) for n in
             ('fn_match','fn_name_length','fn_load','fm_length','fm_name')}
    def fold(data,iec):
        return bytes(v-128 if iec and 0xc1<=v<=0xda else v-32 if 97<=v<=122 else v for v in data)
    calls=steps=worst=0
    def check(haystack,needle,iec):
        nonlocal calls,steps,worst
        assert len(haystack)<=255 and 1<=len(needle)<=127
        ram[0x3d2a]=0 if iec else 3
        data=0x3a02 if iec else 0x3a01
        ram[data:data+len(haystack)]=haystack
        ram[symbols['fn_load']+1]=data&255
        ram[symbols['fn_name_length']]=len(haystack)
        ram[symbols['fm_length']]=len(needle)
        ram[symbols['fm_name']:symbols['fm_name']+len(needle)]=needle
        cpu.sp=0xff;cpu.stPushWord(0x01ff);cpu.pc=symbols['fn_match']
        for used in range(1000000):
            cpu.step()
            if cpu.pc==0x0200:break
        else:raise AssertionError('matcher did not return')
        want=fold(needle,iec) in fold(haystack,iec)
        assert (not bool(cpu.p&1))==want,(haystack.hex(),needle.hex(),iec,cpu.p)
        assert cpu.sp==0xff
        calls+=1;steps+=used+1;worst=max(worst,used+1)
    report=dict(passed=False,physical_hardware_io=False,cases=[],module_sha256=hashlib.sha256(image).hexdigest())
    try:
        for iec in (False,True):
            for raw in range(256):
                for query in range(32,127):check(bytes([raw]),bytes([query]),iec)
            for length in (1,63,126,127):
                check(b'A'*255,b'A'*(length-1)+b'B',iec)
                check(b'A'*255,b'A'*length,iec)
            for length in (1,2,16,37,38,63,64,126,127):
                query=(b'aBc?'*32)[:length]
                for total in (0,1,16,127,128,254,255):
                    check(b'Z'*total,query,iec)
                    if total>=length:
                        for start in (0,(total-length)//2,total-length):
                            data=bytearray(b'Z'*total);data[start:start+length]=query.upper()
                            check(bytes(data),query,iec)
            rng=random.Random(128)
            alphabet=b'abAB*? .0123'+bytes([0x80,0xa0,0xc1,0xd1,0xe9,0xff])
            for _ in range(400):
                hay=bytes(rng.choice(alphabet) for _ in range(rng.randrange(256)))
                if hay and rng.randrange(2):
                    begin=rng.randrange(len(hay));needle=hay[begin:begin+rng.randrange(1,128)]
                else:needle=bytes(rng.choice(alphabet) for _ in range(rng.randrange(1,128)))
                check(hay,needle,iec)
        report['cases'].append(dict(name='exhaustive single-byte folding and bounded substring oracle',
                                    comparisons=calls,instructions=steps,worst_case_instructions=worst))
        report['passed']=True
        print('PASS:',calls,'assembled matcher comparisons;',steps,'instructions',flush=True)
    finally:
        args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
