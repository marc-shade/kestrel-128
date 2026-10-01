#!/usr/bin/env python3
"""The held capture (probes/native-read-held.asm with HeldCapture in
hw_native_gem_check.py) in Py65, against a foreground that keeps writing
N_BUFFER as GEMDESK's AES idle loop does.

Checks: the probe copies only after the host's go-ahead and stays in the IRQ
until released; the payload is exact; N_BUFFER is back to the foreground's
own bytes (only its live counter moved); the IRQ vector, stack and $3e00
scratch are restored; the foreground keeps running; an unanswered probe gives
up and returns with code 2."""
import argparse
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'tests')]
from py65.devices.mpu6502 import MPU  # noqa: E402
import hw_native_gem_check as hw  # noqa: E402

N_BUFFER = 0x3a00


class Machine:
    """A 6502 whose foreground is INC $3A05 / JMP, with a 60 Hz IRQ that
    stacks the MMU byte as the native kernel's IRQ entry does."""

    def __init__(self, memory=None, foreground=(0xee, 0x05, 0x3a, 0x4c, 0x00, 0x20)):
        self.m = MPU() if memory is None else MPU(memory=memory); mem = self.m.memory
        mem[0x2000:0x2000+len(foreground)] = list(foreground)
        mem[0x1234:0x1236] = [0x68, 0x40]          # the old IRQ tail: PLA (MMU byte), RTI
        mem[0xff74:0xff77] = [0xb1, 0xfb, 0x60]     # INDFET for bank 0: LDA ($FB),Y
        mem[0x314] = 0x34; mem[0x315] = 0x12
        mem[0x1c13:0x1c19] = list(b'KES128')
        self.m.pc = 0x2000; self.m.sp = 0xff; self.m.p &= ~0x04
        self.steps = 0

    def irq(self):
        m, mem = self.m, self.m.memory
        if m.p & 0x04:
            return
        for b in (m.pc >> 8, m.pc & 255, m.p & ~0x10):
            mem[0x100+m.sp] = b; m.sp = (m.sp-1) & 255
        m.p |= 0x04
        mem[0x100+m.sp] = 0x0e; m.sp = (m.sp-1) & 255
        m.pc = mem[0x314] | mem[0x315] << 8

    def run(self, n):
        for _ in range(n):
            self.m.step(); self.steps += 1
            if self.steps % 17011 == 0:                 # not a multiple of any loop length
                self.irq()


class VDCMemory:
    """64 KiB of RAM with the VDC's two I/O registers: $D600 selects, $D601
    reads/writes the selected register; register 31 moves data at the update
    address (18/19) and increments it. Always ready."""

    def __init__(self):
        self.ram = bytearray(65536)
        self.vram = bytearray((i*11+(i >> 8)*5) & 255 for i in range(65536))
        self.regs = [0]*38
        self.select = 0
        self.selects = []             # every value written to $D600

    def address(self):
        return self.regs[18] << 8 | self.regs[19]

    def advance(self):
        a = (self.address()+1) & 0xffff
        self.regs[18], self.regs[19] = a >> 8, a & 255

    def __len__(self):
        return 65536

    def __getitem__(self, a):
        if isinstance(a, slice):
            return list(self.ram[a])
        if a == 0xd600:
            return 0x80
        if a == 0xd601:
            if self.select == 31:
                v = self.vram[self.address()]; self.advance(); return v
            return self.regs[self.select]
        return self.ram[a]

    def __setitem__(self, a, v):
        if isinstance(a, slice):
            self.ram[a] = bytes(v); return
        if a == 0xd600:
            self.select = v & 63; self.selects.append(v); return
        if a == 0xd601:
            if self.select == 31:
                self.vram[self.address()] = v; self.advance()
            else:
                self.regs[self.select] = v
            return
        self.ram[a] = v


class Monitor:
    """HardwareMonitor's interface; the CPU runs between host requests."""

    def __init__(self, machine):
        self.machine = machine

    def read_mem(self, start, end, bank=0, memspace=0):
        self.machine.run(3000); return bytes(self.machine.m.memory[start:end+1])

    def write_mem(self, start, data, bank=0, memspace=0):
        self.machine.run(500); self.machine.m.memory[start:start+len(data)] = list(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    report = dict(passed=False, cases=[])

    def done(name):
        report['cases'].append(name); args.report.write_text(json.dumps(report, indent=2)+'\n')
        print('PASS:', name, flush=True)

    box = Machine(); mem = box.m.memory
    source = bytes((i*29+3) & 255 for i in range(0x2400)); mem[0xc000:0xe400] = list(source)
    buffer = bytes((i*7) & 255 for i in range(512)); mem[N_BUFFER:N_BUFFER+512] = list(buffer)
    scratch = bytes((i*3+1) & 255 for i in range(512)); mem[0x3e00:0x4000] = list(scratch)
    capture = hw.HeldCapture(Monitor(box), Path(tempfile.mkdtemp()))
    got = capture.capture('surface', address=0xc000, count=0x2400)
    assert got == source, 'payload'
    after = bytes(mem[N_BUFFER:N_BUFFER+512])
    assert [i for i in range(512) if after[i] != buffer[i]] == [5], 'only the foreground\'s counter moved'
    assert bytes(mem[0x3e00:0x4000]) == scratch, [i for i in range(512) if mem[0x3e00+i] != scratch[i]][:8]
    for _ in range(2000):                            # stop in the foreground, not inside an IRQ
        if 0x2000 <= box.m.pc < 0x2006 and not box.m.p & 0x04:
            break
        box.run(1)
    assert mem[0x314] | mem[0x315] << 8 == 0x1234 and box.m.sp == 0xff, (hex(mem[0x314] | mem[0x315] << 8), box.m.sp)
    assert all(c['n_buffer_restored'] and c['scratch_restored'] and c['code'] == 1 for c in capture.records[0]['chunks'])
    counter = mem[0x3a05]; box.run(50000); assert mem[0x3a05] != counter, 'the foreground runs on'
    done('9,216 bytes in 18 held chunks; N_BUFFER, $3e00 scratch, IRQ vector and stack restored; foreground runs on')

    probe = capture.prg                              # the probe alone: its handshake and time-out
    held = Machine(); mem = held.m.memory
    mem[0x3e00:0x3e00+len(probe)-2] = list(probe[2:])
    mem[0x6000:0x6100] = list(range(256)); mem[N_BUFFER:N_BUFFER+256] = [0xaa]*256
    mem[0x3ff0:0x4000] = [0x34, 0x12, 0, 0, 0, 0, 0x60, 0, 1, 0, 0, 0, 0, 0, 0, 0]
    mem[0x314] = 0; mem[0x315] = 0x3e; held.irq()
    held.run(20000)
    assert mem[0x3ffe] == 1 and mem[0x3ff2] == 0 and bytes(mem[N_BUFFER:N_BUFFER+256]) == b'\xaa'*256, 'held, no copy yet'
    mem[0x3ffe] = 2; held.run(20000)
    assert mem[0x3ff2] == 1 and bytes(mem[N_BUFFER:N_BUFFER+256]) == bytes(range(256)), 'copied on 2'
    held.run(20000); assert 0x3e00 <= held.m.pc < 0x3ff0, 'held until released'
    mem[0x3ffe] = 3; held.run(2000)
    assert mem[0x314] | mem[0x315] << 8 == 0x1234, 'released'
    done('the probe copies only after 2 and stays in the IRQ until 3')

    lost = Machine(); mem = lost.m.memory
    mem[0x3e00:0x3e00+len(probe)-2] = list(probe[2:])
    mem[0x3ff0:0x4000] = [0x34, 0x12, 0, 0, 0, 0, 0x60, 16, 0, 0, 0, 0, 0, 0, 0, 0]
    mem[0x314] = 0; mem[0x315] = 0x3e; lost.irq()
    for _ in range(60):
        lost.run(500_000)
        if mem[0x314] | mem[0x315] << 8 == 0x1234:
            break
    assert mem[0x3ff2] == 2 and mem[0x314] | mem[0x315] << 8 == 0x1234, 'an unanswered probe gives up'
    done(f'an unanswered probe returns with code 2 after {lost.steps} instructions')
    # VDC memory: a foreground that is idle at its input wait only half the time
    # (N_READY toggles), so some attempts must come back busy and be retried.
    vdc = VDCMemory()
    toggling = (0xa9, 1, 0x8d, 0x12, 0x3d, 0xee, 0x05, 0x3a, 0xa9, 0, 0x8d, 0x12, 0x3d,
                0xea, 0xea, 0xea, 0xea, 0xea, 0xea, 0xea, 0xea, 0x4c, 0x00, 0x20)   # busy most of the loop
    screen = Machine(vdc, toggling); mem = screen.m.memory
    vdc.regs[18], vdc.regs[19], vdc.select = 0x12, 0x34, 31
    capture = hw.HeldCapture(Monitor(screen), Path(tempfile.mkdtemp()))
    got = capture.capture('vdc', mode=1, address=0x0100, count=700)
    assert got == bytes(vdc.vram[0x100:0x100+700]), 'VDC payload'
    assert vdc.address() == 0x1234 and vdc.select == 31, ('update address and selection restored', hex(vdc.address()))
    record = capture.records[0]
    assert record['busy'] > 0, 'some attempts found the foreground busy and were retried'
    assert all(c['code'] == 1 and c['n_buffer_restored'] for c in record['chunks'])
    done(f"VDC memory: 700 bytes in {len(record['chunks'])} chunks, {record['busy']} busy retries, "
         f"update address and register selection restored")
    report['passed'] = True; args.report.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
