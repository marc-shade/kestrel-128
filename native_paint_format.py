"""Kestrel Paint v1: checked, fixed-size hires bitmap and cell colors."""
import binascii

WIDTH, HEIGHT = 320, 200
BITMAP_BYTES, COLOR_BYTES = 8000, 1000
PAYLOAD_BYTES = BITMAP_BYTES+COLOR_BYTES
HEADER_BYTES = 16
PREFIX = b'UPNT\x01\x00'+WIDTH.to_bytes(2,'little')+HEIGHT.to_bytes(2,'little')+PAYLOAD_BYTES.to_bytes(2,'little')


def encode(surface):
    if len(surface)!=9216:raise ValueError('paint surface must contain 9216 bytes')
    payload=surface[:8000]+surface[8192:9192]
    return PREFIX+binascii.crc_hqx(payload,0xffff).to_bytes(2,'little')+bytes(2)+payload


def decode(data):
    if len(data)!=HEADER_BYTES+PAYLOAD_BYTES:raise ValueError('paint file length differs from v1 format')
    if data[:12]!=PREFIX or data[14:16]!=bytes(2):raise ValueError('unsupported paint header')
    payload=data[16:]
    if binascii.crc_hqx(payload,0xffff)!=int.from_bytes(data[12:14],'little'):raise ValueError('paint data checksum mismatch')
    return payload[:8000]+bytes(192)+payload[8000:]+b'\x10'*24
