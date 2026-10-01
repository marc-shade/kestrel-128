#!/usr/bin/env python3
"""Clipboard packet framing, negotiation and terminal input ordering."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'apps/claude/host'))
import bridge
import protocol

class Link:
    def __init__(self):self.output=bytearray();self.credits=0
    def queue(self,data):self.output.extend(data)
    def add_credit(self):self.credits+=1

def machine():
    link=Link();b=bridge.Bridge(link,[],panel=False);b.client_ready=True
    return b,link

def packet(data,chunk=64):
    out=bytearray(b'\0\6'+len(data).to_bytes(2,'little'))
    for pos in range(0,len(data),chunk):
        part=data[pos:pos+chunk];out+=b'\0\5'+bytes([len(part)])+part
    return bytes(out)+b'\0\7'

def run():
    cases=[]
    text=bytes(range(32,127))+b'\t\r\nsecond\rthird\n'
    expected=b'\x1b[200~'+text.replace(b'\r\n',b'\n').replace(b'\r',b'\n')+b'\x1b[201~'
    stream=b'A\0\4'+packet(text)+b'B\0\3'
    for split in range(len(stream)+1):
        b,link=machine()
        out=b._take_control(stream[:split],translated=True)+b._take_control(stream[split:],translated=True)
        assert out==b'a'+expected+b'b',(split,out)
        assert link.output==bytes([13,1,14,0]) and link.credits==1
    b,link=machine();out=b''.join(b._take_control(bytes([v]),translated=True) for v in stream)
    assert out==b'a'+expected+b'b'
    cases.append('every split, escaped zero lengths, byte-at-a-time input, ASCII and newline conversion, ordered keys')
    big=(b'line 0123456789\n'*1100)[:16384]
    b,link=machine();b._take_control(b'\0\4')
    assert b._take_control(packet(big),translated=True)==b'\x1b[200~'+big+b'\x1b[201~'
    assert not b.paste_data
    for data in (b'\0\2\0\3\0\7',b'escape\x1b[201~',bytes([127]),bytes([128]),b''):
        b,link=machine();b._take_control(b'\0\4')
        assert b._take_control(packet(data),translated=True)==b''
        assert link.output[-2:]==bytes([14,1])
    cases.append('16 KiB exact limit, NUL/control/escape/non-ASCII rejection before terminal delivery')
    for data in (b'\0\6\x02\0\0\5\x01A\0\7',
                 b'\0\6\x01\0\0\5\x02AB\0\7',
                 b'\0\6\x01\0\0\5\0\0\7',
                 b'\0\6\x01\0\0\5\x41'+b'A'*65+b'\0\7',
                 b'\0\6\x01\x40\0\7'):
        b,link=machine();b._take_control(b'\0\4')
        assert b._take_control(data,translated=True)==b'' and link.output[-2:]==bytes([14,1])
    b,link=machine();assert b._take_control(packet(b'text'),translated=True)==b'' and not link.output
    b,link=machine();b._take_control(b'\0\4')
    assert not b._take_control(packet(b'AB')[:-2]+b'\0\3\0\10\0\7',translated=True)
    assert link.credits==1 and not b.paste_data
    b,link=machine();b._take_control(b'\0\4')
    assert not b._take_control(packet(b'AB')[:-2]+b'\0\2\0\3',translated=True)
    assert b.client_closed and not b.paste_data and link.credits==1
    cases.append('unsupported negotiation, malformed counts, incomplete/extra payload, cancellation, BYE and credits')
    return dict(passed=True,physical_hardware_io=False,cases=cases)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args();result=run();args.report.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
