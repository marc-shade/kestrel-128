"""Bounded LZSA2 and CRC16 container for the disk's native BASIC boot file."""
import binascii
import os
import subprocess
from pathlib import Path


from native_lzsa import pack, unpack


def build(root, out):
    root, out = Path(root), Path(out)
    raw = (out/'kestrel.prg').read_bytes()
    assert raw[:2] == b'\x01\x1c'
    data = raw[2:]
    packed = pack(data)
    assert unpack(packed, len(data)) == data
    payload = out/'kestrel-packed.bin'
    payload.write_bytes(packed)
    try:
        subprocess.run(['64tass', '-a', '-B',
                        '-D', f'BOOT_PACKED_FILE="{os.path.relpath(payload, root/"src/native")}"',
                        '-D', f'BOOT_LENGTH={len(packed)}',
                        '-D', f'BOOT_END={0x1c01+len(data)}',
                        '-D', f'BOOT_EXPECTED_CRC={binascii.crc_hqx(data,0xffff)}',
                        str(root/'src/native/boot-unpack.asm'),
                        '-o', str(out/'kestrel-boot.prg'),
                        '-l', str(out/'kestrel-boot.sym'),
                        '-L', str(out/'kestrel-boot.lst')], check=True)
    finally:
        payload.unlink()
    return dict(codec='lzsa2-crc16', unpacked_bytes=len(data), packed_bytes=len(packed),
                boot_file='kestrel-boot.prg', decoder_start=0x1300, scratch_start=0x6000)
