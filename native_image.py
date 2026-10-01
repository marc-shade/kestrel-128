#!/usr/bin/env python3
"""Validate/seal a native Kestrel app PRG assembled with its 32-byte manifest."""
import argparse
import binascii
from pathlib import Path


def validate(image,check_crc=True):
    if len(image)<35 or image[:6]!=b'\0\x60NAPP':
        raise ValueError('expected a native NAPP PRG at $6000 with a complete manifest')
    header=image[2:34]
    if header[4]!=1 or header[5]!=1 or header[6]>14:
        raise ValueError('unsupported native image format, ABI or flags')
    size=int.from_bytes(header[8:10],'little')
    pages=header[10];entry=int.from_bytes(header[12:14],'little')
    if not 1<=pages<=96 or not 33<=size<=pages*256 or len(image)!=size+2:
        raise ValueError('file length or declared memory extent is invalid')
    if not 32<=entry<size:
        raise ValueError('entry point must be inside executable image bytes after the manifest')
    window=header[7]|header[11]<<8
    if window and (header[6]<7 or not size<=window<pages*256):
        raise ValueError('module window must follow the loaded core inside its allocation')
    if any(value and not 32<=value<127 for value in header[16:32]):
        raise ValueError('title must contain printable PETSCII/ASCII bytes or zero padding')
    payload=bytearray(image[2:]);payload[14:16]=bytes(2)
    crc=binascii.crc_hqx(payload,0xffff)
    if check_crc and int.from_bytes(header[14:16],'little')!=crc:
        raise ValueError('native image CRC16 does not match')
    return dict(bytes=size,pages=pages,entry=0x6000+entry,crc16=crc,window=0x6000+window if window else None,
                title=header[16:32].split(b'\0')[0].decode('ascii'))


def seal(image):
    info=validate(image,check_crc=False)
    output=bytearray(image);output[16:18]=info['crc16'].to_bytes(2,'little')
    validate(output)
    return bytes(output)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input',type=Path)
    parser.add_argument('output',type=Path,nargs='?',help='sealed output PRG; omit to validate without writing')
    args=parser.parse_args()
    try:
        image=args.input.read_bytes()
        if args.output:
            image=seal(image);args.output.write_bytes(image)
        info=validate(image)
    except (OSError,ValueError) as error:parser.exit(1,f'{error}\n')
    print(f"Native app {info['title']}: {info['bytes']} bytes, {info['pages']} pages, entry ${info['entry']:04x}, CRC ${info['crc16']:04x}")


if __name__=='__main__':main()
