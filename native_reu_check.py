"""Independent VICE snapshot decoding for REU qualification; no target DMA."""
import hashlib
from pathlib import Path


def initial_memory(kib):
    block = bytes((i*37+(i>>8)*73+19)&255 for i in range(65536))
    return b''.join(block.translate(bytes((i+b*53)&255 for i in range(256))) for b in range(kib//64))


def decode_snapshot(data):
    assert data[:19] == b'VICE Snapshot File\x1a'
    assert data[21:37].rstrip(b'\0') == b'C128'
    assert data[37:50] == b'VICE Version\x1a'
    at, found = 58, None
    while at < len(data):
        assert at+22 <= len(data)
        name = data[at:at+16].rstrip(b'\0')
        length = int.from_bytes(data[at+18:at+22],'little')
        assert 22 <= length <= len(data)-at
        if name == b'REU1764':
            assert found is None and data[at+16:at+18] == bytes(2)
            payload = data[at+22:at+length]
            kib = int.from_bytes(payload[:4],'little')
            assert kib in (128,256,512,1024,2048,4096,8192,16384)
            assert len(payload) == 20+kib*1024
            found = payload[20:],dict(kib=kib,registers=payload[4:20].hex(),
                                      sha256=hashlib.sha256(payload[20:]).hexdigest())
        at += length
    assert at == len(data) and found is not None
    return found


def snapshot(mon, path):
    """Caller holds the emulator paused; saving has no REC register side effects."""
    path = Path(path).resolve()
    name = str(path).encode()
    assert len(name) < 256
    error,_ = mon._recv(mon._send(0x41,bytes([0,0,len(name)])+name))
    assert not error, ('VICE snapshot',error)
    raw = path.read_bytes()
    memory,info = decode_snapshot(raw)
    info.update(snapshot=path.name,snapshot_sha256=hashlib.sha256(raw).hexdigest())
    return memory,info
