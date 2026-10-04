#!/usr/bin/env python3
"""Execute C128 ROM scanning and the native key-check boundary guard."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ci_native_heap as heap
from py65.devices.mpu6502 import MPU


class KeyboardBus(heap.Bus):
    def __init__(self):
        super().__init__()
        self.basic = Path('/usr/share/vice/C128/basiclo-318018-04.bin').read_bytes()
        self.pressed = set()
        self.row_signal = 0xff
        self.ports = {0xdc00: 0x7f, 0xdc02: 255, 0xdc03: 0, 0xd02f: 255}
        self.reads = []
        self.writes = []
        self.callback = []

    def __getitem__(self, address):
        if self.config == 0 and 0x4000 <= address < 0x8000:
            return self.basic[address-0x4000]
        if not self.config & 1 and address in self.ports:
            return self.ports[address]
        if not self.config & 1 and address == 0xd484:
            # ROM's .byte $2c skips STY $d4 as BIT $d484 for modifier keys.
            return 0xff
        if not self.config & 1 and address == 0xdc01:
            result = self.row_signal
            for index in self.pressed:
                assert 0 <= index < 88
                column, row = divmod(index, 8)
                selected = self.ports[0xdc00] if column < 8 else self.ports[0xd02f]
                bit = column if column < 8 else column-8
                if not selected & (1 << bit):
                    result &= ~(1 << row)
            self.reads.append((self.ports[0xdc00], self.ports[0xd02f], result))
            return result
        return super().__getitem__(address)

    def __setitem__(self, address, value):
        if not self.config & 1 and address in self.ports:
            self.ports[address] = value
            self.writes.append((address, value))
            return
        return super().__setitem__(address, value)


def invoke(bus, pc, *, a=0, x=0, y=0, flags=0x20, observe=None):
    cpu = MPU(memory=bus, pc=pc)
    cpu.sp = 0xc0
    cpu.a, cpu.x, cpu.y, cpu.p = a, x, y, flags
    cpu.stPushWord(0xb7f)
    for _ in range(30000):
        if cpu.pc == 0xb80:
            assert cpu.sp == 0xc0
            return cpu
        if observe:
            observe(cpu)
        cpu.step()
    raise AssertionError(('keyboard did not return', hex(cpu.pc), bus.config))


def machine(*, guard=True):
    bus = KeyboardBus()
    ram = bus.ram[0]
    invoke(bus, 0xff8a)  # Actual RESTOR installs KERNAL vectors.
    # CINT copies these editor vectors and decode pointers from the ROM;
    # avoid its unrelated screen initialization in this limited bus model.
    ram[0x334:0x34a] = bus.rom[0x65:0x7b]
    ram[1] = 0x77  # CAPS LOCK released.
    ram[0x99] = 0
    ram[0xd0:0xd6] = bytes([0, 0, 0, 0, 88, 88])
    ram[0x34a:0x354] = bytes(10)
    ram[0xa20:0xa26] = bytes([10, 0, 0, 4, 16, 0])
    ram[0x3d12:0x3d16] = bytes([1, 0, 0, 0])
    ram[0x1000:0x100a] = bytes([1]*10)
    ram[0x100a:0x1014] = bytes([0x85, 0x89, 0x86, 0x8a, 0x87, 0x8b, 0x88, 0x8c, 0x83, 0x84])
    original = int.from_bytes(ram[0x33c:0x33e], 'little')
    assert original == 0xc6ad
    if guard:
        invoke(bus, heap.symbol('native_keyboard_init'))
        assert int.from_bytes(ram[0x33c:0x33e], 'little') == heap.symbol('native_keycheck')
    return bus


def scan(bus, *, mmu=0, pressed=(), row_signal=255):
    bus.config = mmu
    bus.pressed = set(pressed)
    bus.row_signal = row_signal
    guard = heap.symbol('native_keycheck')
    def observe(cpu):
        if cpu.pc in (guard, 0xc6ad):
            bus.callback.append(dict(pc=cpu.pc, key=cpu.a, index=cpu.y, modifiers=cpu.x))
    invoke(bus, 0xff9f, observe=observe)  # Actual SCNKEY, including debounce and lookup.
    assert bus.config == mmu and bus.ports[0xdc00] == 0x7f
    bus.config = 14
    result = invoke(bus, 0x1c3b).a
    assert bus.config == 14
    return result


def run():
    cases = []
    images = {}
    for prefix in ('native', 'native-desktop'):
        heap.IMAGE = ROOT/'target'/prefix/'kestrel.prg'
        images[prefix] = hashlib.sha256(heap.IMAGE.read_bytes()).hexdigest()
        guard = heap.symbol('native_keycheck')
        saved = heap.symbol('native_keycheck_saved')
        init = heap.symbol('native_keyboard_init')
        # The guard stays resident below $4000; installing it is boot-only staging code.
        assert guard < 0x3800 and heap.symbol('native_boot_image') <= init < heap.symbol('native_boot_end')
        for mmu in (0, 14):
            unguarded = machine(guard=False)
            guarded = machine()
            assert scan(unguarded, mmu=mmu, row_signal=0xfd) == 0x94
            assert unguarded.callback[-1]['index'] == 89
            assert scan(guarded, mmu=mmu, row_signal=0xfd) == 0
            assert guarded.callback[-1] == dict(pc=guard, key=0x94, index=89, modifiers=0)
            assert guarded.ram[0][0x3d13:0x3d15] == bytes(2)
            assert guarded.ram[0][0x3d1e:0x3d20] == b'\x01\0'
            assert guarded.ram[0][0xd0:0xd3] == bytes(3)
            # Releasing the modeled signal leaves normal key detection intact.
            assert scan(guarded, mmu=mmu) == 0
            assert scan(guarded, mmu=mmu, pressed=(7,)) == 17
        cases.append(prefix+': real ROM produces index 89/Insert for a modeled low row signal; guard rejects it; valid Down still works')

        fixtures = [('a', (10,), 65), ('w', (9,), 87), ('shift-insert', (0,15), 148),
            ('shift-up', (7,15), 145), ('dedicated-up', (83,), 145), ('dedicated-down', (84,), 17),
            ('dedicated-left', (85,), 157), ('dedicated-right', (86,), 29), ('tab', (67,), 9),
            ('escape', (72,), 27), ('keypad-enter', (76,), 13), ('control-a', (10,58), 1),
            ('f1', (4,), 133), ('f8', (3,15), 140), ('help', (64,), 132)]
        for mmu in (0, 14):
            for name, pressed, expected in fixtures:
                left, right = machine(guard=False), machine()
                assert scan(left, mmu=mmu, pressed=pressed) == expected, (prefix, name, 'ROM')
                assert scan(right, mmu=mmu, pressed=pressed) == expected, (prefix, name, 'guard')
                for start, end in ((0xcc, 0xd6), (0x34a, 0x354), (0x3d12, 0x3d16)):
                    assert left.ram[0][start:end] == right.ram[0][start:end], (name, hex(start))
        cases.append(prefix+': 15 real-ROM letter/modifier/cursor/function/keypad cases match unguarded queue and native accounting in both mappings')

        for flags in (0x20, 0x29, 0x64, 0xe8):
            for mmu in (0, 14):
                bus = machine()
                ram = bus.ram[0]
                ram[saved:saved+2] = b'\x60\x0b'
                ram[0xb60] = 0x60
                bus.config = mmu
                for index in range(256):
                    entered = []
                    def observe(cpu):
                        if cpu.pc == 0xb60:
                            entered.append((cpu.a,cpu.x,cpu.y,cpu.p & 0xcf))
                    invoke(bus, guard, a=148, x=0xa5, y=index, flags=flags, observe=observe)
                    assert entered == ([(148,0xa5,index,flags & 0xcf)] if index < 88 else [])
                    assert bus.config == mmu
                assert int.from_bytes(ram[0x3d1e:0x3d20], 'little') == 168
        cases.append(prefix+': all 256 callback indices, both mappings and four flag combinations; valid callbacks preserve A/X/Y/P and invalid callbacks do not chain')

        bus = machine(guard=False)
        ram = bus.ram[0]
        ram[0x33c:0x33e] = b'\x60\x0b'
        for flags in (0x20, 0x29, 0x64, 0xe8):
            ram[0x3d1e:0x3d20] = b'\xff\x12'
            cpu = invoke(bus, init, flags=flags)
            assert cpu.p & 0xcf == flags & 0xcf
            assert ram[saved:saved+2] == b'\x60\x0b'
            assert int.from_bytes(ram[0x33c:0x33e], 'little') == guard
            assert ram[0x3d1e:0x3d20] == bytes(2)
        cases.append(prefix+': existing callback retained; repeated startup is idempotent and preserves flags')

        for count in (0x12ff, 0xffff):
            ram[0x3d1e:0x3d20] = count.to_bytes(2, 'little')
            invoke(bus, guard, a=148, y=89)
            assert int.from_bytes(ram[0x3d1e:0x3d20], 'little') == (count+1)&65535
        left, right = machine(guard=False), machine()
        for _ in range(36):
            assert scan(left, pressed=(7,)) == scan(right, pressed=(7,))
            assert left.ram[0][0xa20:0xa26] == right.ram[0][0xa20:0xa26]
        for flags in (0x20, 0x29, 0x64, 0xe8):
            bus = machine()
            ram = bus.ram[0]
            ram[0x3d13:0x3d15] = b'\xff\x12'
            ram[0x100a:0x100d] = b'ABC'
            ram[0xd1] = 3
            for expected in b'ABC':
                cpu = invoke(bus, 0x1c3b, flags=flags)
                # ROM's function-string GETIN executes CLI; retain that
                # existing behavior when relocating the native wrapper.
                assert cpu.a == expected and cpu.p & 0x0c == flags & 0x08
            assert ram[0x3d13:0x3d15] == b'\x02\x13' and ram[0xd1] == 0
            assert invoke(bus, 0x1c3b, flags=flags).a == 0
        cases.append(prefix+': rejection counter carry/wrap; 36 scans retain ROM repeat policy; queued function text and native counter carry survive moved GETIN')
    return dict(passed=True, physical_hardware_io=False, cases=cases, images=images,
        reference_rom_sha256=hashlib.sha256(heap.ROM.read_bytes()).hexdigest(),
        scope='Real ROM scanner on a limited CIA matrix model; modeled row signal is not proof of the physical input source')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    result = dict(passed=False, physical_hardware_io=False)
    try:
        result = run()
        print('PASS:', len(result['cases']), 'native keyboard groups', flush=True)
    except BaseException as error:
        result['error'] = repr(error)
        raise
    finally:
        args.report.write_text(json.dumps(result, indent=2)+'\n')
