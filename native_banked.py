#!/usr/bin/env python3
"""Validate/seal the fixed bank-1 NBK1 PRG format used by banked-load.inc."""
import argparse
import binascii
from pathlib import Path

BASE = 0x6000
LIMIT = 0xc000
STUB = bytes.fromhex('a2 0e 4c ab 02 00 00 00 00 00 00 00 00 00 00 00')


def validate(image, check_crc=True, base=BASE):
    """base selects the executor instance: $6000 per-app, $9000 persistent AES."""
    if len(image) < 35 or image[:8] != base.to_bytes(2, 'little')+b'NBK1\x01\x01':
        raise ValueError(f'expected a complete NBK1 PRG at bank-1 ${base:04x}')
    header = image[2:34]
    if header[6] > 14 or header[7] or header[11] != 1 or header[16:] != STUB:
        raise ValueError('unsupported ABI, bank, flags, exit stub or callback import')
    size = int.from_bytes(header[8:10], 'little')
    entry = int.from_bytes(header[12:14], 'little')
    if not 33 <= size <= LIMIT-base or len(image) != size+2 or header[10] != (size+255)//256:
        raise ValueError('file length or page extent is invalid')
    if not 32 <= entry < size:
        raise ValueError('entry must follow the header inside the image')
    payload = bytearray(image[2:])
    payload[14:16] = bytes(2)
    crc = binascii.crc_hqx(payload, 0xffff)
    if check_crc and int.from_bytes(header[14:16], 'little') != crc:
        raise ValueError('banked image CRC16 does not match')
    return dict(bytes=size, pages=header[10], bank=1, entry=base+entry, crc16=crc)


def seal(image, base=BASE):
    info = validate(image, check_crc=False, base=base)
    result = bytearray(image)
    result[16:18] = info['crc16'].to_bytes(2, 'little')
    validate(result, base=base)
    return bytes(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path, nargs='?')
    args = parser.parse_args()
    try:
        image = args.input.read_bytes()
        if args.output:
            image = seal(image)
            args.output.write_bytes(image)
        print(validate(image))
    except (OSError, ValueError) as error:
        parser.exit(1, str(error)+'\n')


if __name__ == '__main__':
    main()
