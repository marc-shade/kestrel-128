#!/usr/bin/env python3
"""Loaded VDC desktop: physical RAM aliasing, pixels, pointer and restore failures."""
import argparse
import hashlib
import json
from pathlib import Path

from ci_native_pointer import Pointer, PointerBus, heap, calc
from native_vdc_scene import bitmap, attributes, pointer_bitmap, pack, unpack
from launcher_scene import surface

ROOT = Path(__file__).resolve().parents[1]


class VDCBus(PointerBus):
    size = 64
    addressing = 16
    present = True
    columns = 80
    height = 7

    def __init__(self):
        super().__init__()
        self.video_ram = bytearray((i*37+(i>>8)*73+19)&255 for i in range(65536))
        self.reg = bytearray(64)
        self.reg[1], self.reg[6], self.reg[9] = self.columns, 25, 7
        self.reg[10], self.reg[18], self.reg[19] = 0x67, 0x2a, 0x4c
        self.reg[20], self.reg[22], self.reg[23] = 8, 0x78, self.height
        self.reg[25], self.reg[26], self.reg[28] = 0x47, 0xf0, 0x20|(16 if self.addressing == 64 else 0)
        self.reg[32], self.reg[33] = 0x5a, 0x32
        self.selected, self.busy, self.ready = 0, 0, False
        self.original = None
        self.stall = False
        self.stall_register = None
        self.data_writes = self.data_reads = self.block_copies = self.handshakes = 0

    def physical(self, address):
        address &= 65535
        if self.reg[28]&16:
            return address if self.size == 64 else (address&255)|((address&0x7e00)>>1)
        return ((address&0x80ff)|((address&0x3f00)<<1)|(address&0x100)) if self.size == 64 else address&0x3fff

    def vread(self, address): return self.video_ram[self.physical(address)]
    def vwrite(self, address, value): self.video_ram[self.physical(address)] = value
    def bytes(self, address, count): return bytes(self.vread(address+i) for i in range(count))

    def __getitem__(self, address):
        if not self.config&1 and address == 0xd600:
            if not self.present or self.stall: return 0
            if self.busy:
                self.busy -= 1
                return 0
            self.ready = True
            self.handshakes += 1
            return 0x80
        if not self.config&1 and address == 0xd601:
            assert self.ready, ('read before VDC ready', self.selected)
            self.ready, self.busy = False, 2
            if self.selected == 31:
                at = self.reg[18]*256+self.reg[19]
                value = self.vread(at)
                self.advance(at+1)
                self.data_reads += 1
                return value
            return self.reg[self.selected]
        return super().__getitem__(address)

    def __setitem__(self, address, value):
        if not self.config&1 and address == 0xd600:
            self.selected, self.ready, self.busy = value&63, False, 3
        elif not self.config&1 and address == 0xd601:
            assert self.ready, ('write before VDC ready', self.selected)
            self.ready, self.busy = False, 2
            if self.original is None:
                self.original = bytes(self.video_ram), bytes(self.reg)
            if self.selected == 31:
                at = self.reg[18]*256+self.reg[19]
                self.vwrite(at, value); self.advance(at+1)
                self.reg[31] = value
                self.data_writes += 1
            else:
                self.reg[self.selected] = value
                if self.selected == 30:
                    at = self.reg[18]*256+self.reg[19]
                    count = value or 256
                    if self.reg[24]&128:
                        source = self.reg[32]*256+self.reg[33]
                        assert source+count <= at, 'scene copy must not depend on overlapping VDC behavior'
                        data = self.bytes(source, count)
                        for i, byte in enumerate(data): self.vwrite(at+i, byte)
                        self.reg[32], self.reg[33] = (source+count)>>8, (source+count)&255
                        self.reg[31] = data[-1]
                        self.block_copies += 1
                    else:
                        for i in range(count): self.vwrite(at+i, self.reg[31])
                    self.advance(at+count)
                    self.busy = count*2
            if self.stall_register == (self.selected, value): self.stall = True
        else:
            super().__setitem__(address, value)

    def advance(self, address):
        address &= 65535
        self.reg[18], self.reg[19] = address>>8, address&255


class Desktop(Pointer):
    # Include the larger checked VDC/history component load in startup.
    # Keep the same finite budget as the shared graphical Calculator fixture.
    instruction_limit = 16000000

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.checked = 0

    def output(self, value):
        screen = self.ram[0xd7]>>7
        row, col = self.row[screen], self.col[screen]
        super().output(value)
        if screen:
            chip = self.m.bus
            if value == 0x93:
                for i in range(2000): chip.vwrite(i, 32); chip.vwrite(0x800+i, 15)
            elif 32 <= value < 128:
                chip.vwrite(row*80+col, self.screens[1][row*80+col])
                chip.vwrite(0x800+row*80+col, 15)

    def check(self, selected):
        assert self.value('vd_phase') == 2 and self.value('vd_live') == 1
        assert self.value('vd_fault') == 0
        assert self.value('vd_color') == (self.bus.size == 64)
        error = self.value('gd_launch_error')
        assert self.value('gd_selected') == selected
        assert bytes(self.ram[0xc000:0xe400]) == surface(selected, error)
        x, y = self.position
        visible = bool(self.value('vd_pointer_visible'))
        expected = pointer_bitmap(bitmap(selected, error), x*2, y, visible)
        actual = self.bus.bytes(self.value('vd_base')*256, 16000)
        assert actual == expected, ('bitmap', [(i,a,b) for i,(a,b) in enumerate(zip(actual,expected)) if a != b][:16])
        if self.bus.size == 64:
            assert self.bus.bytes(0x8000, 2000) == attributes(selected)
            assert self.bus.reg[25] == 0xc7
            assert self.bus.video_ram[:0x4000] == self.bus.original[0][:0x4000]
            assert self.bus.video_ram[0x8800:] == self.bus.original[0][0x8800:]
        else:
            assert self.bus.reg[25] == 0x87
            assert self.bus.video_ram[0x4000:] == self.bus.original[0][0x4000:]
        assert self.bus.reg[26] == 0xf2
        self.checked += 1

    def restored(self):
        super().restored()
        assert self.value('vd_phase') == self.value('vd_live') == self.value('vd_handle') == 0
        if self.bus.original is None:
            assert self.bus.data_writes == 0, 'refused component never borrowed the VDC'
            return
        assert self.bus.video_ram == self.bus.original[0], 'all physical VDC RAM must return exactly'
        for register in (1,6,8,9,10,12,13,14,15,18,19,20,21,22,23,24,25,26,27,28,32,33):
            assert self.bus.reg[register] == self.bus.original[1][register], ('register restoration', register)


def run(group):
    cases = []
    original = heap.Bus
    def start(size=64, addressing=16, **options):
        heap.Bus = type('ConfiguredVDC', (VDCBus,), dict(size=size, addressing=addressing, **options))
        return Desktop()
    def done(name, desktop):
        cases.append(dict(name=name,frames=desktop.frames,complete_surfaces=desktop.checked,
                          block_copies=desktop.bus.block_copies,instructions=desktop.instructions))
        print('PASS:', name, flush=True)
    try:
        if group in ('all', 'core'):
            assert unpack(pack(bitmap())) == bitmap()
            for size in (16, 64):
                for addressing in (16, 64):
                    p = start(size, addressing); p.check(0)
                    for selected in range(1, 7): p.key(9); p.check(selected)
                    p.key(9); p.check(0)
                    p.frame(); p.check(0)
                    for x, y in ((0,0),(319,199),(319,0),(0,199),(99,40),(103,64),(117,88)):
                        p.move(x,y); p.check(p.value('gd_selected'))
                    # A move within one byte column reuses the saved background of
                    # the rows both pointers cover; only the other rows are read.
                    # Steps stay under 6 pixels, which the 1351 jump filter holds.
                    for origin, steps in (((305,100),((0,3),(0,-5),(1,2),(-1,-1),(2,0),(5,1))),
                                         ((305,190),((0,4),(0,-3),(1,5))),
                                         ((318,100),((0,2),(1,-3),(-5,1)))):
                        p.move(*origin); p.check(p.value('gd_selected'))
                        for dx, dy in steps:
                            (ox, oy), reads = p.position, p.bus.data_reads
                            p.frame(dx, dy); p.check(p.value('gd_selected'))
                            (nx, ny) = p.position
                            assert (nx-ox, ny-oy) == (dx, dy)
                            kept = range(oy, min(200, oy+16)) if nx//4 == ox//4 else ()
                            fresh = [row for row in range(ny, min(200, ny+16)) if row not in kept]
                            assert p.bus.data_reads-reads == len(fresh)*(1+min(2, 80-nx//4)), ((ox,oy),(nx,ny),p.bus.data_reads-reads,len(fresh))
                    p.bus.pots = [255,255]; p.frame(); p.check(p.value('gd_selected'))
                    assert not p.value('vd_pointer_visible')
                    p.key(27, exited=True); p.restored()
                    done(f'{size} KiB physical RAM, {addressing} KiB initial addressing, seven selections, pointer edges and exact restore',p)
        if group in ('all', 'launch'):
            for size in (16, 64):
                for index, name in enumerate((b'CALC',b'EDITOR',b'FILES',b'ULTIMATE',b'CLAUDE',b'PAINT',b'SHEET')):
                    p = start(size); p.frame(); p.move(100,44+index*16); p.check(index)
                    before = p.events
                    p.frame(down=True); p.frame(down=False, exited=True); p.restored()
                    assert int.from_bytes(p.ram[0x3d13:0x3d15],'little') == before
                    assert bytes(p.ram[0x3d40:0x3d40+len(name)]) == name
                    done(f'{size} KiB mouse launch and restore: {name.decode()}',p)
        if group in ('all', 'fault'):
            p = start(); p.frame(); p.check(0)
            p.bus.stall = True
            p.frame(dx=4)
            assert p.value('vd_fault') == 0x11 and p.value('vd_phase') == 2
            p.key(ord('C'))
            assert p.ram[0x3d20] == 32 and p.value('vd_handle') and p.value('gd_launch_error') == 0x11
            p.bus.stall = False
            p.key(ord('C'),exited=True); p.restored()
            done('stalled pointer and failed close retain the full snapshot; a later launch retries restoration',p)

            p = start(); p.check(0)
            p.bus.stall_register = (28, p.bus.original[1][28])
            p.key(ord('C'))
            assert p.value('vd_phase') == 2 and p.bus.stall
            p.bus.stall_register = None; p.bus.stall = False
            p.key(ord('C'),exited=True); p.restored()
            done('restore retry reinstates the bitmap addressing mode after a stall partway through register restoration',p)

            for options in (dict(present=False),dict(columns=79),dict(height=6)):
                p = start(**options)
                assert not p.value('vd_phase') and not p.value('vd_live') and not p.value('vd_handle')
                assert p.value('bk_state') == p.value('bp_started') == 0
                assert p.bus.original is None and not p.bus.data_writes
                p.key(9); assert p.value('gd_selected') == 1
                p.key(27,exited=True); Pointer.restored(p)
                done('absent or unsupported VDC retains native VIC/text controls without video-memory writes',p)

            machine = calc.Machine
            class Occupied(machine):
                def __init__(self):
                    super().__init__()
                    end=0x60+(ROOT/'target/native-desktop/vdsvc.prg').read_bytes()[12]
                    self.foreign = [self.alloc(0x60-4,1,77,page=4),
                                    self.alloc(0xff-end,1,77,page=end)]
            calc.Machine = Occupied
            try: p = start()
            finally: calc.Machine = machine
            assert p.value('vd_phase') == p.value('vd_live') == p.value('vd_handle') == 0
            assert p.value('bk_state') == p.value('bp_started') == 0
            assert p.bus.video_ram == p.bus.original[0]
            Pointer.check(p,0)
            stack = bytes(p.ram[0x100:0x200])
            for handle in p.m.foreign:
                p.m.select(handle,77); p.m.invoke('free')
            p.ram[0x100:0x200] = stack
            p.key(27,exited=True); p.restored()
            done('snapshot allocation refusal restores the probe/registers and retains working VIC/text controls',p)

            class LaunchError(machine):
                def __init__(self):
                    super().__init__()
                    self.ram[0x3d2b] = 0x14
            calc.Machine = LaunchError
            try: p = start()
            finally: calc.Machine = machine
            p.check(0); p.key(9); p.check(1)
            p.key(27,exited=True); p.restored()
            done('failed app launch appears completely on both graphical desktops',p)
    finally:
        heap.Bus = original
    return cases


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=('all','core','launch','fault'), default='all')
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    report = dict(passed=False, physical_hardware_io=False, cases=[], images={
        str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (ROOT/'target/native/kestrel.prg',ROOT/'target/native-desktop/desktop.prg')})
    try:
        report['cases'] = run(args.case)
        report['passed'] = True
    finally:
        args.report.write_text(json.dumps(report,indent=2)+'\n')
