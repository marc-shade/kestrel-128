#!/usr/bin/env python3
"""Execute shipped boot wrappers; reject damaged streams before kernel entry."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
from py65.devices.mpu6502 import MPU

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_boot_pack import pack, unpack


def symbols(path):
    text=path.read_text()
    found={m[1]:int(m[2],16) for m in re.finditer(r'^(\w+)\s*=\s*\$([0-9a-f]+)$',text,re.M)}
    found['BOOT_INPUT']=int(re.search(r'^BOOT_INPUT\s*=\s*(\d+)$',text,re.M)[1])   # constant, written in decimal
    return found


class Memory:
    def __init__(self, prg, labels, end):
        self.data = [(i*37+(i>>8)*29+17)&255 for i in range(65536)]
        self.data[0x1c01:0x1c01+len(prg)-2] = prg[2:]
        self.data[0xd505], self.data[0xff00] = 0, 0x0e
        length = labels['boot_file_end']-labels['boot_payload']
        self.allowed = ((0x100,0x200), (0x1300,(labels['decoder_end']+255)&~255),
                        (0x1c01,max(end,labels['decoder_image'])),
                        (labels['BOOT_INPUT'],(labels['BOOT_INPUT']+length+255)&~255), (0xff00,0xff01))
        self.writes = set()

    def __getitem__(self, at): return self.data[at]
    def __setitem__(self, at, value):
        assert any(start <= at < end for start,end in self.allowed), ('boot write outside declared regions',hex(at))
        self.writes.add(at); self.data[at] = value


def execute(prg, labels, raw, *, passed, status=0x20, c64=False):
    memory = Memory(prg,labels,0x1c01+len(raw))
    memory.data[0xd505] = 0x40 if c64 else 0
    cpu = MPU(memory=memory,pc=0x1c10);cpu.sp=0xe0;cpu.p=status
    cpu.stPushWord(0x0afe)
    message = bytearray()
    decoded = False
    for steps in range(3500000):
        if cpu.pc == 0x1c10 and decoded:
            assert passed and not message
            assert bytes(memory.data[0x1c01:0x1c01+len(raw)]) == raw
            assert cpu.sp == 0xde
            break
        if cpu.pc == 0x0aff:
            assert not passed
            assert cpu.sp == 0xe0
            assert message == (b'' if c64 else b'\rBOOT ERROR - RELOAD\r')
            break
        if cpu.pc == 0xffd2:
            message.append(cpu.a)
            cpu.pc = cpu.stPopWord()+1
            continue
        if cpu.pc < 0x1c01:
            decoded = True
            assert 0x1300 <= cpu.pc < labels['decoder_end'], hex(cpu.pc)
        else:
            assert not decoded and 0x1c10 <= cpu.pc < labels['decoder_image'], hex(cpu.pc)
        if decoded and cpu.pc == labels['COPY_MATCH_LOOP']:
            at = memory.data[cpu.pc+1] | memory.data[cpu.pc+2] << 8
            end = memory.data[labels['boot_write']+1] | memory.data[labels['boot_write']+2] << 8
            assert 0x1c01 <= at < min(end, 0x1c01+len(raw)), ('unowned match read',hex(at))
        if decoded and cpu.pc == labels['boot_read']:
            at = memory.data[cpu.pc+1] | memory.data[cpu.pc+2] << 8
            assert labels['BOOT_INPUT'] <= at < labels['BOOT_INPUT']+labels['boot_file_end']-labels['boot_payload']
        if decoded and cpu.pc == labels['boot_write']:
            at = memory.data[cpu.pc+1] | memory.data[cpu.pc+2] << 8
            assert 0x1c01 <= at < 0x1c01+len(raw), ('decoded write beyond output',hex(at))
        cpu.step()
    else:
        raise AssertionError(('boot did not terminate',hex(cpu.pc)))
    assert cpu.p&0x0c == status&0x0c
    assert memory.data[0xff00] == 0x0e
    if c64:
        assert all(0x100 <= at < 0x200 for at in memory.writes)
    return steps


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True);args=parser.parse_args()
    report=dict(passed=False,physical_hardware_io=False,cases=[])
    try:
        for folder in ('native','native/d81','native-desktop','native-desktop/d81'):
            path=ROOT/'target'/folder
            raw=(path/'kestrel.prg').read_bytes()[2:]
            prg=(path/'kestrel-boot.prg').read_bytes()
            labels=symbols(path/'kestrel-boot.sym')
            payload=labels['boot_payload']-0x1c01+2
            assert prg[payload:] == pack(raw) and unpack(prg[payload:],len(raw)) == raw
            for status in (0x20,0x24,0x28,0x2c):
                steps=execute(prg,labels,raw,passed=True,status=status)
                report['cases'].append(dict(name=folder+' exact kernel and D/I preservation',status=status,instructions=steps,
                    boot_sha256=hashlib.sha256(prg).hexdigest(),kernel_sha256=hashlib.sha256(raw).hexdigest()))
        # Exercise errors in the real decoder, including its nested read/write
        # stack frames. Payload damage cannot choose output addresses or entry.
        cases=[]
        for index in (0,1,127,len(prg[payload:])//2,len(prg[payload:])-2,len(prg[payload:])-1):
            broken=bytearray(prg);broken[payload+index]^=1
            cases.append((f'payload bit flip at {index}',bytes(broken)))
        broken=bytearray(prg);broken[payload:]=bytes([255,0])*((len(prg)-payload)//2)+bytes((len(prg)-payload)%2)
        cases.append(('invalid repeated-offset stream',bytes(broken)))
        for length in (payload+1,payload+(len(prg)-payload)//2,len(prg)-1):
            cases.append((f'truncated file at {length}',prg[:length]))
        for name,broken in cases:
            # A flipped match-offset bit inside a run of equal bytes can decode to
            # the identical kernel; the reference unpacker decides which outcome the
            # 6502 decoder must reach (refusal, or the exact CRC-checked kernel).
            try:identical=unpack(broken[payload:],len(raw))==raw
            except ValueError:identical=False
            steps=execute(broken,labels,raw,passed=identical)
            report['cases'].append(dict(name=name,instructions=steps,decodes_identically=identical))
        steps=execute(prg,labels,raw,passed=False,c64=True)
        report['cases'].append(dict(name='C64 mode refusal before map or scratch writes',instructions=steps))
        from native_boot_fixtures import assemble, valid_blocks
        with tempfile.TemporaryDirectory(prefix='kestrel-boot-fixtures-') as temporary:
            work = Path(temporary)
            for name, block in valid_blocks():
                encoded, decoded = bytes(block.data), bytes(block.decoded)
                assert unpack(encoded,len(decoded)) == decoded, ('Python decoder',name)
                fixture, syms = assemble(ROOT,work,name,encoded,decoded)
                steps = execute(fixture,syms,decoded,passed=True)
                report['cases'].append(dict(name=name,instructions=steps,decoded_bytes=len(decoded),
                                           python_decoder_agrees=True))
            failures = {
                'first 5-bit match': bytes.fromhex('00 f0'),
                'first 9-bit match': bytes.fromhex('40 ff'),
                'first 13-bit match': bytes.fromhex('80 f0 ff'),
                'first 16-bit match': bytes.fromhex('c0 80 00'),
                'repeat before any offset': bytes.fromhex('e0'),
                'zero offset': bytes.fromhex('c0 00 00'),
                'forward offset': bytes.fromhex('c0 00 01'),
                'missing nibble': bytes.fromhex('18'),
                'missing offset byte': bytes.fromhex('40'),
                'missing offset high byte': bytes.fromhex('c0'),
                'missing extended literal byte': bytes.fromhex('18 f0'),
                'missing extended literal word': bytes.fromhex('18 f0 ef 00'),
                'reserved literal extension': bytes.fromhex('18 f0 ee'),
                'reserved match extension': bytes.fromhex('47 00 f0 ea'),
                'early terminator': bytes.fromhex('47 00 f0 e8'),
                'literal output overflow': bytes.fromhex('18 f0 ef ff ff')+bytes(101),
                'overlapping match output overflow': bytes.fromhex('0f 41 ff e9 ff ff'),
                'zero extended match': bytes.fromhex('0f 41 ff e9 00 00'),
                'zero extended literal': bytes.fromhex('18 f0 ef 00 00'),
                'missing end marker': encoded[:-1],
                'extra input after end': encoded+b'\0',
            }
            for name, encoded_bad in failures.items():
                expected = decoded if name in ('missing end marker','extra input after end') else bytes(100)
                try: unpack(encoded_bad,len(expected))
                except ValueError: pass
                else: raise AssertionError(('host accepted malformed stream',name))
                fixture, syms = assemble(ROOT,work,'bad',encoded_bad,expected)
                steps = execute(fixture,syms,expected,passed=False,status=0x2c)
                report['cases'].append(dict(name=name,instructions=steps,host_rejected=True))
            wrong = bytes([decoded[0]^1])+decoded[1:]
            fixture, syms = assemble(ROOT,work,'bad-crc',encoded,wrong)
            steps = execute(fixture,syms,wrong,passed=False)
            report['cases'].append(dict(name='valid complete stream with wrong CRC',instructions=steps))
        report['passed']=True
    except BaseException as error:
        report['error']=repr(error);raise
    finally:
        args.report.write_text(json.dumps(report,indent=2)+'\n')
    print('PASS:',len(report['cases']),'boot decode and rejection cases',flush=True)


if __name__=='__main__':main()
