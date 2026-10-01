"""Build a standard NAPP containing a checked, transient LZSA2 startup."""
import binascii
import hashlib
from pathlib import Path
import struct
import subprocess
import tempfile

from native_image import seal, validate
from native_lzsa import pack, unpack

ROOT = Path(__file__).resolve().parent


def build(image, *, runtime_end=None, listing=None, symbols=None):
    info = validate(image)
    raw_end = 0x6000 + info['bytes']
    runtime_end = raw_end if runtime_end is None else runtime_end
    cleanup = 0x6000 + info['pages'] * 256 - 48
    if not raw_end <= runtime_end <= cleanup:
        raise ValueError('app requires 48 unused tail bytes for startup cleanup')
    body = image[34:]
    packed = pack(body)
    with tempfile.TemporaryDirectory(prefix='kestrel-app-pack-') as temporary:
        temporary = Path(temporary)
        header_file, packed_file = temporary/'header.bin', temporary/'body.lzsa'
        header_file.write_bytes(image[2:34]);packed_file.write_bytes(packed)
        output = temporary/'app.prg'
        definitions = dict(PK_ABI=image[8], PK_WINDOW=(info['window']-0x6000) if info['window'] else 0,
                           PK_PAGES=info['pages'], PK_RUNTIME_END=runtime_end, PK_CLEANUP_BASE=cleanup,
                           PK_RAW_END=raw_end, PK_RAW_ENTRY=info['entry'], PK_PACKED_LENGTH=len(packed),
                           PK_BODY_CRC=binascii.crc_hqx(body, 0xffff),
                           PK_HEADER_FILE='"'+str(header_file)+'"', PK_PACKED_FILE='"'+str(packed_file)+'"')
        command = ['64tass', '-a', '-B']
        for key,value in definitions.items(): command += ['-D',f'{key}={value}']
        if listing is not None: command += ['-L',str(listing)]
        if symbols is not None: command += ['-l',str(symbols)]
        command += [str(ROOT/'src/native/app-unpack.asm'),'-o',str(output)]
        subprocess.run(command, check=True, capture_output=True)
        result = seal(output.read_bytes())
    if len(result) >= len(image):
        raise ValueError('packed startup would not reduce the file size')
    assert decode(result) == image
    return result


def decode(image):
    validate(image)
    if image[34:38] != b'NPZ2' or len(image) < 82:
        raise ValueError('not a packed native app')
    header = image[38:70]
    runtime_end,cleanup,source,length,code,code_length = struct.unpack_from('<6H',image,70)
    raw_end = 0x6000 + int.from_bytes(header[8:10],'little')
    if not raw_end <= runtime_end <= cleanup or cleanup + 48 != 0x6000 + header[10]*256:
        raise ValueError('invalid packed app runtime bounds')
    if not 0x6050 <= code < code+code_length <= source < 0x6000+len(image)-2:
        raise ValueError('invalid packed app code/payload bounds')
    at = source-0x6000+2
    if at+length != len(image):
        raise ValueError('packed payload extent differs from the file')
    result = b'\0\x60'+header+unpack(image[at:],raw_end-0x6020)
    original = validate(result)
    outer = validate(image)
    if (original['pages'],original['window'],original['title']) != (outer['pages'],outer['window'],outer['title']):
        raise ValueError('packed app allocation, module window or title changed')
    if outer['entry'] != 0x6050 or image[8] != header[6] or len(image)-2+0x6000 > cleanup:
        raise ValueError('packed startup entry, ABI or file bounds changed')
    return result


def information(image):
    raw = decode(image)
    runtime_end,cleanup,source,length,code,code_length = struct.unpack_from('<6H',image,70)
    return dict(codec='napp-lzsa2-startup', raw_file_bytes=len(raw), raw_runtime_bytes=len(raw)-2,
                raw_sha256=hashlib.sha256(raw).hexdigest(), packed_file_bytes=len(image),
                packed_sha256=hashlib.sha256(image).hexdigest(), packed_body_bytes=length,
                runtime_end=runtime_end, cleanup_address=cleanup, cleanup_bytes=48,
                temporary_code_base=0x5000, temporary_code_pages=(code_length+255)//256,
                temporary_input_pages=(length+255)//256, temporary_input_bank='automatic')
