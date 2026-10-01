#!/usr/bin/env python3
"""Stand-alone service libraries (docs/NATIVE-SERVICES.md) in Py65: the XBIOS
Random generator against the Atari formula, and the SID bell's register
writes."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile

from py65.devices.mpu6502 import MPU

ROOT = Path(__file__).resolve().parents[1]
HALT = 0x0400


class Memory(bytearray):
    """64 KiB that records writes to the SID."""
    def __init__(self):
        super().__init__(65536); self.sid = []

    def __setitem__(self, address, value):
        if isinstance(address, int) and 0xd400 <= address <= 0xd418:
            self.sid.append((address, value))
        super().__setitem__(address, value)


def assemble(include):
    work = Path(tempfile.mkdtemp(prefix='kestrel-services-'))
    src = work/'t.asm'
    src.write_text(f'* = $2000\n.include "{ROOT}/src/native/{include}"\n')
    subprocess.run(['64tass', '-a', '-B', str(src), '-o', str(work/'t.prg'), '-l', str(work/'t.sym')],
                   check=True, capture_output=True)
    prg = (work/'t.prg').read_bytes()
    labels = {n: int(v, 16) for n, v in re.findall(r'^(\w+)\s*=\s*\$([0-9a-fA-F]+)', (work/'t.sym').read_text(), re.M)}
    return prg, labels


def call(mem, labels, name, steps=200000):
    cpu = MPU(memory=mem, pc=labels[name])
    cpu.sp = 0xff
    cpu.stPushWord(HALT-1)
    for _ in range(steps):
        if cpu.pc == HALT:
            return cpu
        cpu.step()
    raise AssertionError('no return from '+name)


def model(seed):
    seed = (seed*3141592621+1) & 0xffffffff
    return seed, (seed >> 8) & 0xffffff


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    report = dict(passed=False, physical_hardware_io=False, cases=[])

    def done(name, **extra):
        report['cases'].append(dict(name=name, **extra))
        args.report.write_text(json.dumps(report, indent=2)+'\n')
        print('PASS:', name, flush=True)

    try:
        prg, labels = assemble('random.inc')
        mem = Memory(); mem[0x2000:0x2000+len(prg)-2] = prg[2:]
        state = labels['rn_state']
        seed = 0x12345678
        mem[state:state+4] = seed.to_bytes(4, 'little')
        for i in range(1000):
            cpu = call(mem, labels, 'rn_random')
            seed, want = model(seed)
            got = cpu.a | cpu.x << 8 | cpu.y << 16
            assert got == want and int.from_bytes(mem[state:state+4], 'little') == seed, (i, hex(got), hex(want))
        done('1,000 results equal seed*3141592621+1, bits 8..31, from a fixed seed')

        mem[state:state+4] = bytes(4)
        mem[0xa1], mem[0xa2], mem[0xd012], mem[0xdc04] = 0x34, 0x56, 0x78, 0x9a
        cpu = call(mem, labels, 'rn_random')
        seed = 0x56 | 0x78 << 8 | 0x9a << 16 | (0x34 | 1) << 24
        seed, want = model(seed)
        assert cpu.a | cpu.x << 8 | cpu.y << 16 == want
        done('an unseeded generator seeds itself from the jiffy clock, raster and CIA timer')

        prg, labels = assemble('sound.inc')
        mem = Memory(); mem[0x2000:0x2000+len(prg)-2] = prg[2:]
        mem[0xd418] = 0x30                                     # a filter mode, volume 0
        mem.sid.clear()
        call(mem, labels, 'sd_bell')
        writes = mem.sid
        assert writes[0] == (0xd404, 0) and writes[-1] == (0xd404, 0x11), writes
        regs = {a: v for a, v in writes}
        assert (regs[0xd400] | regs[0xd401] << 8) == 14985 and regs[0xd405] == 0x09 and regs[0xd406] == 0
        assert regs[0xd418] == 0x0f, 'volume 15, no filter: $d418 cannot be read back'
        done('the bell: gate off, 880 Hz (PAL), attack 0 decay 9 sustain 0, volume 15 written (not read), triangle gate on last',
             writes=[f'{a:04x}={v:02x}' for a, v in writes])

        mem.sid.clear()
        call(mem, labels, 'sd_click')
        writes = mem.sid
        assert writes[0] == (0xd404, 0) and writes[-1] == (0xd404, 0x81), writes
        regs = {a: v for a, v in writes}
        assert (regs[0xd400] | regs[0xd401] << 8) == 0x4000 and regs[0xd405] == 0 and regs[0xd406] == 0
        assert regs[0xd418] == 0x0f
        done('the key click: gate off, noise at $4000, attack 0 decay 0 sustain 0, volume 15, noise gate on last',
             writes=[f'{a:04x}={v:02x}' for a, v in writes])
        report['passed'] = True
    finally:
        args.report.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
