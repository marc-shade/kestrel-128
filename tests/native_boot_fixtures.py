"""Explicit LZSA2 commands for exercising decoder boundaries, not compression."""
import binascii
import os
from pathlib import Path
import subprocess


class Block:
    def __init__(self):
        self.data = bytearray()
        self.decoded = bytearray()
        self.pending = None
        self.previous = None

    def nibble(self, value):
        assert 0 <= value < 16
        if self.pending is None:
            self.pending = len(self.data)
            self.data.append(value << 4)
        else:
            self.data[self.pending] |= value
            self.pending = None

    def extension(self, count, short, base):
        if count < short + base:
            return
        self.nibble(min(15, count-short-base))
        if count >= short + base + 15:
            if count < 256:
                self.data.append(count-short-base-15)
            else:
                self.data.append(257-short-base-15)
                self.data += count.to_bytes(2, 'little')

    def command(self, literals=b'', distance=None, count=0, bits=9):
        if distance is None:
            kind, offset = 2, 0
        elif bits == 'repeat':
            assert distance == self.previous
            kind, offset = 7, 0
        else:
            offset = (-distance) & 65535
            if bits == 5:
                assert 1 <= distance <= 32
                kind = (~offset) & 1
            elif bits == 9:
                assert 1 <= distance <= 512
                kind = 2 | ((~offset >> 8) & 1)
            elif bits == 13:
                assert 513 <= distance <= 8704
                offset = (offset+512) & 65535
                kind = 4 | ((~offset >> 8) & 1)
            else:
                assert bits == 16 and 1 <= distance <= 65535
                kind = 6
        self.data.append(kind << 5 | min(3, len(literals)) << 3 |
                         (7 if distance is None else min(7, count-2)))
        self.extension(len(literals), 3, 0)
        self.data += literals
        self.decoded += literals
        if kind < 2:
            self.nibble((offset >> 1) & 15)
        elif kind < 4:
            self.data.append(offset & 255)
        elif kind < 6:
            self.nibble((offset >> 9) & 15)
            self.data.append(offset & 255)
        elif kind == 6:
            self.data += offset.to_bytes(2, 'big')
        if distance is None:
            self.nibble(15)
            self.data.append(232)
        else:
            assert 2 <= count <= 65535 and distance <= len(self.decoded)
            self.extension(count, 7, 2)
            for _ in range(count):
                self.decoded.append(self.decoded[-distance])
            self.previous = distance
        return self


def assemble(root, work, name, encoded, decoded):
    from ci_native_boot_pack import symbols
    payload = work/(name+'.bin')
    payload.write_bytes(encoded)
    subprocess.run(['64tass', '-a', '-B',
                    '-D', f'BOOT_PACKED_FILE="{os.path.relpath(payload, root/"src/native")}"',
                    '-D', f'BOOT_LENGTH={len(encoded)}',
                    '-D', f'BOOT_END={0x1c01+len(decoded)}',
                    '-D', f'BOOT_EXPECTED_CRC={binascii.crc_hqx(decoded, 0xffff)}',
                    str(root/'src/native/boot-unpack.asm'),
                    '-o', str(work/(name+'.prg')), '-l', str(work/(name+'.sym'))],
                   check=True, capture_output=True)
    return (work/(name+'.prg')).read_bytes(), symbols(work/(name+'.sym'))


def valid_blocks():
    # Both Z values for every small offset, plus page carries and overlapping runs.
    block = Block().command(bytes(range(256))*35, 1, 2, 5)
    for distance, bits in ((2,5),(31,5),(32,5),(33,9),(255,9),(256,9),(257,9),(512,9),
                           (513,13),(768,13),(8192,13),(8704,13),(8705,16),(8950,16)):
        block.command(distance=distance, count=17, bits=bits)
    block.command(distance=8950, count=257, bits='repeat').command(b'end')
    yield 'all-offsets', block
    for literal in (1,2,3,17,18,255,256,257):
        block = Block()
        data = bytes((i*37+literal) & 255 for i in range(literal))
        for count in (2,8,9,23,24,255,256,257,512):
            block.command(data, 1, count, 5)
        block.command()
        yield f'lengths-literal-{literal}', block
    yield 'maximum-kernel-size', Block().command(b'z',1,17406,5).command()
