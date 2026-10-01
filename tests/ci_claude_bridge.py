#!/usr/bin/env python3
"""Check host stream backpressure and explicit native session shutdown."""
import argparse
import json
from pathlib import Path
import sys
from unittest.mock import Mock, patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'apps/claude/host'))
import bridge
import protocol


def run():
    proc = bridge.PtyProcess.__new__(bridge.PtyProcess)
    proc.fd = 42; proc.pending = bytearray(); received = bytearray()
    limits = iter((2, None, 1, 3))
    def writer(fd, data):
        assert fd == 42
        limit = next(limits)
        if limit is None: raise BlockingIOError
        received.extend(data[:limit]); return min(limit,len(data))
    with patch.object(bridge.os,'write',writer):
        proc.write(b'abc'); assert received==b'ab' and proc.pending==b'c'
        proc.write(b'def'); assert proc.pending==b'cdef'
        proc.flush(); proc.flush()
    assert received==b'abcdef' and not proc.pending
    proc.reaped=True;proc.pid=123
    with patch.object(bridge.os,'killpg') as signal, patch.object(bridge.os,'close') as close:
        proc.close();signal.assert_not_called();close.assert_called_once_with(42)
    b=bridge.Bridge.__new__(bridge.Bridge);b.pending_escape=False;b.client_closed=False
    assert b._take_control(b'p\0')==b'p'
    assert b._take_control(bytes([protocol.CLIENT_BYE]))==b'' and b.client_closed
    class Link:
        credits=17
    class Differ:
        def reset(self): self.reset_called=True
    b.link=Link();b.differ=Differ();b.client_ready=True;b.verbose=False;b.client_closed=False
    b._control(protocol.CLIENT_RESYNC)
    assert b.link.credits==17 and b.differ.reset_called and b.dirty
    cases = ['partial and blocked PTY writes preserve all input in order',
            'reaped child is never signaled', 'split native BYE is a normal close',
            'RESYNC leaves receive credits unchanged']

    class Socket:
        def __init__(self):
            self.sent = bytearray()
            self.received = 0
            self.closed = False
        def setblocking(self, value): pass
        def send(self, data):
            count = min(len(data), 7)
            self.sent.extend(data[:count])
            return count
        def recv(self, count):
            if self.received == 0:
                self.received += 1
                # The credit after BYE must survive control parsing.
                return b'\0\2\0\3'
            self.received += 1
            return b'\0\3'
        def close(self): self.closed = True

    sock = Socket()
    link = bridge.SerialLink(sock, byte_rate=1000000)
    with patch.object(bridge, 'PtyProcess') as spawn:
        b = bridge.Bridge(link, ['selected-command'], cwd='/selected/project', panel=False)
        b._take_control(b'Modem Software is currently not running...\n')
        spawn.assert_not_called()
        b._take_control(b'\0\1')
        spawn.assert_called_once_with(['selected-command'], 80, 25, '/selected/project')
        b._take_control(b'\0\1')
        assert spawn.call_count == 1
    cases.append('modem chatter cannot start a PTY; the first RESYNC starts the selected command exactly once')

    # Exercise the real shutdown loop with a full queue, short writes, exhausted
    # credits, and returned credits. Its first bytes are a RUN payload suffix,
    # so losing the queue would make the following BYE undecodable by the C128.
    pending = b'A'*72 + (b'\x03\0\0\x0e\x50\x20')*5449 + b'\x05\x05'
    assert len(pending) == bridge.BACKLOG_LIMIT
    link.out[:] = pending
    link.credits = 0
    proc = Mock(fd=99, pending=bytearray())
    proc.alive.return_value = True
    b.proc = proc
    b.dirty = False
    def ready(reads, writes, errors, timeout):
        if not b.client_closed:
            return [link], [], []
        return ([link] if link.credits <= 128 else []), [], []
    with patch.object(bridge.select, 'select', ready):
        assert b.run()
    assert sock.sent == pending + b'\x09\x5a', 'shutdown truncated the queued protocol stream'
    assert sock.closed and proc.close.call_count == 1
    cases.append('F8 acknowledgement follows the entire full backlog despite short writes and zero initial credits')

    sock = Socket(); link = bridge.SerialLink(sock)
    with patch.object(bridge, 'PtyProcess') as spawn:
        b = bridge.Bridge(link, ['never-started'], panel=False)
        with patch.object(bridge.select, 'select', lambda *args: ([link], [], [])):
            assert b.run()
        spawn.assert_not_called()
    assert sock.sent == b'\x09\x5a' and sock.closed
    cases.append('BYE before RESYNC receives acknowledgement without starting a host process')

    class OfflineSocket(Socket):
        def recv(self, count):
            self.received += 1
            return b'Modem Software is currently not running...\n' if self.received == 1 else b''
    sock = OfflineSocket(); link = bridge.SerialLink(sock)
    with patch.object(bridge, 'PtyProcess') as spawn:
        b = bridge.Bridge(link, ['never-started'], panel=False)
        with patch.object(bridge.select, 'select', lambda *args: ([link], [], [])):
            assert not b.run()
        spawn.assert_not_called()
    assert not sock.sent and sock.closed
    cases.append('offline modem banner and disconnect close the transport without launching the selected command')

    sock = Socket(); link = bridge.SerialLink(sock)
    b = bridge.Bridge(link, ['already-exited'], panel=False)
    b.client_ready = True
    b.proc = Mock(fd=99, pending=bytearray())
    b.proc.alive.return_value = False
    b.proc.read.return_value = None
    with patch.object(bridge.select, 'select') as select:
        assert b.run()
        select.assert_not_called()
    assert sock.sent == b'\x09\x5a' and sock.received == 0 and sock.closed
    cases.append('host exit finishes after sending BYE without waiting for an unnecessary peer read')
    return cases


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    result=dict(passed=False,physical_hardware_io=False)
    try:
        result['cases']=run();result['passed']=True;print('PASS:',len(result['cases']),'host bridge controls')
    except BaseException as exc: result['error']=repr(exc);raise
    finally:a.report.write_text(json.dumps(result,indent=2)+'\n')
