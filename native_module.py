#!/usr/bin/env python3
"""Seal and validate an app-bound, fixed-window native module PRG."""
import binascii
from native_image import validate as validate_app


def validate(image, app, check_crc=True):
    parent=validate_app(app)
    if parent['window'] is None:
        raise ValueError('parent app has no module window')
    if len(image)<19 or int.from_bytes(image[:2],'little')!=parent['window']:
        raise ValueError('module origin must match the parent window')
    h=image[2:18]
    if h[:6]!=b'NMOD'+bytes([1,1]) or not 7<=h[6]<=14 or h[7]:
        raise ValueError('unsupported module format, ABI or flags')
    size=int.from_bytes(h[8:10],'little')
    if size<17 or len(image)!=size+2 or parent['window']+size>0x6000+parent['pages']*256:
        raise ValueError('module extent exceeds the file or window')
    if int.from_bytes(h[10:12],'little')!=parent['crc16']:
        raise ValueError('module belongs to a different app core')
    entry=int.from_bytes(h[12:14],'little')
    if not 16<=entry<size:
        raise ValueError('module entry must be within executable image bytes')
    payload=bytearray(image[2:]);payload[14:16]=bytes(2)
    crc=binascii.crc_hqx(payload,0xffff)
    if check_crc and int.from_bytes(h[14:16],'little')!=crc:
        raise ValueError('module CRC16 does not match')
    return dict(bytes=size,origin=parent['window'],entry=parent['window']+entry,crc16=crc,parent_crc16=parent['crc16'])


def seal(image, app):
    output=bytearray(image)
    if len(output)<18:
        raise ValueError('module has no complete header')
    output[12:14]=validate_app(app)['crc16'].to_bytes(2,'little')
    info=validate(output,app,check_crc=False)
    output[16:18]=info['crc16'].to_bytes(2,'little')
    validate(output,app)
    return bytes(output)
