#!/usr/bin/env python3
"""Execute the shared query entry against packet, filesystem and IRQ models."""
import argparse
from collections import deque
import copy
import hashlib
import json
from pathlib import Path

from ci_native_directory_ultimate import Client as DirectoryClient, DirectoryDOS
from ci_native_files import OWNER, RECORDS, BUFFER, ACTUAL, DOS, STATUS, BUSY, CLOSE
from ci_native_heap import IMAGE, symbol
from uci_bus import UCIBus

QUERY, OP, ARG = 0x1c6e, 0x3d3c, 0x3d3d
# Literal wire commands are independent of the assembled dispatch tables.
COMMANDS = (b'\x04\x01', b'\x04\x28\x00', b'\x04\x29\x01',
            b'\x04\x34', b'\x04\x35', b'\x03\x02',
            b'\x03\x04\x04', b'\x03\x05\x04', b'\x01\x26')


class QueryDOS(DirectoryDOS):
    def __init__(self):
        super().__init__([b'\x20ONE', b'\x20TWO'], {b'/kept': b'PRESERVED'})
        self.replies = {}
        self.delay = 0
        self.pending = False
        self.abort_reads = 0
        self.abort_requests = 0

    def __setitem__(self, address, value):
        if address == 0xdf1c and value == 1:
            command = bytes(self.command)
            if command in self.replies:
                self.packets = deque(self.replies[command])
                return UCIBus.__setitem__(self, address, value)
        if address == 0xdf1c and value == 4:
            self.abort_requests += 1
            self.pending = True
            if self.delay == 0:
                self.complete_abort()
            return
        super().__setitem__(address, value)

    def __getitem__(self, address):
        if address == 0xdf1c and self.pending:
            self.abort_reads += 1
            if self.delay is not None and self.abort_reads >= self.delay:
                self.complete_abort()
            return 4
        return super().__getitem__(address)

    def complete_abort(self):
        self.pending = False
        UCIBus.__setitem__(self, 0xdf1c, 4)


class Client(DirectoryClient):
    def __init__(self):
        super().__init__()
        self.ultimate = QueryDOS()
        self.m.bus.dos = self.ultimate

    def query(self, op=0, arg=4, expected=0, **kwargs):
        self.ram[OP], self.ram[ARG] = op, arg
        count = self.call(QUERY, expected, **kwargs)
        return bytes(self.ram[BUFFER:BUFFER+count])


def run():
    cases = {}
    for op, command in enumerate(COMMANDS):
        c = Client()
        payload = bytes([0, 128, 255, op])
        c.ultimate.replies[command] = [(payload, b'00,OK')]
        paths = copy.deepcopy(c.ultimate.paths)
        assert c.query(op) == payload
        assert c.ultimate.commands == [command] and c.ultimate.paths == paths
        assert not c.ram[BUSY] and not c.ram[DOS] and not c.ram[STATUS]
        cases[f'query-{op}'] = dict(command=command.hex(), bytes=len(payload))

    c = Client()
    for target in range(1, 16):
        command = bytes([target, 1])
        c.ultimate.replies[command] = [(b'IDENTIFICATION', b'00,OK')]
        assert c.query(0, target) == b'IDENTIFICATION'
        assert c.ultimate.commands[-1] == command
    cases['all-identify-targets'] = dict(targets=15)

    c = Client()
    for op in range(9, 256):
        c.query(op, expected=1)
    for arg in (0, 16, 127, 128, 255):
        c.query(0, arg, expected=1)
    assert not c.ultimate.command and not c.ultimate.commands and not c.ultimate.aborted
    cases['invalid-operation-and-target'] = dict(rejected=252, no_device_writes=True)

    for index in (0, 255):
        c = Client()
        for op, wire in ((6, 4), (7, 5)):
            command = bytes([3, wire, index])
            c.ultimate.replies[command] = [(b'ADDR', b'00,OK')]
            assert c.query(op, index) == b'ADDR'
            assert c.ultimate.commands[-1] == command
    cases['interface-index-range'] = dict(indices=[0, 255])

    for label, setup, expected in (
            ('absent', lambda c: setattr(c.ultimate, 'present', False), 0x11),
            ('foreign-command', lambda c: setattr(c.ultimate, 'state', 0x10), 0x15),
            ('file-lock', lambda c: c.ram.__setitem__(BUSY, 1), 7),
            ('heap-lock', lambda c: c.ram.__setitem__(0x3d11, 1), 7),
            ('owner-zero', lambda c: c.ram.__setitem__(OWNER, 0), 1),
            ('owner-retired', lambda c: c.ram.__setitem__(OWNER, 255), 1)):
        c = Client(); setup(c)
        c.query(expected=expected)
        assert not c.ultimate.commands and not c.ultimate.command and not c.ultimate.aborted
        cases[label] = dict(error=expected, no_device_writes=True)
    c = Client(); c.query(expected=8, flags=4)
    assert not c.ultimate.commands
    cases['masked-irq'] = dict(error=8, no_device_writes=True)

    for size in (0, 1, 255, 256, 511, 512):
        c = Client(); payload = bytes((i*73)&255 for i in range(size))
        c.ultimate.replies[COMMANDS[0]] = [(payload[:73], b''), (payload[73:], b'00,OK')]
        tail = bytes(c.ram[BUFFER+size:BUFFER+512]); before = bytes(c.ram[:256])
        interrupts = []
        def irq(cpu, steps):
            if steps % 101 == 0 and not cpu.p&4:
                cpu.irq(); interrupts.append(steps)
        assert c.query(flags=8, interrupt=irq) == payload
        assert bytes(c.ram[BUFFER+size:BUFFER+512]) == tail and bytes(c.ram[:256]) == before
        assert interrupts and not c.ultimate.discarded
    cases['bounded-multipart-binary-irq'] = dict(sizes=[0, 1, 255, 256, 511, 512], decimal_preserved=True)

    for label, packets, actual, status in (
            ('target-error', [(b'PREFIX', b'81,INVALID PARAMS')], b'PREFIX', 0),
            ('first-error', [(b'A', b'71,ERROR'), (b'B', b'00,OK')], b'AB', 0),
            ('missing-status', [(b'X', b'')], b'X', 0),
            ('non-numeric-status', [(b'X', b'UNAVAILABLE')], b'X', 0),
            ('overlong-status', [(b'X', b'00,'+b'X'*29)], b'X', 0xfc),
            ('overlong-data', [(b'X'*513, b'00,OK')], b'X'*512, 0xfc)):
        c = Client(); c.ultimate.replies[COMMANDS[0]] = packets
        assert c.query(expected=0x11) == actual
        assert c.ram[STATUS] == status and not c.ram[BUSY]
        assert c.ultimate.commands == [COMMANDS[0]]
        if label == 'first-error': assert c.ram[DOS] == 71
        cases[label] = dict(prefix_bytes=len(actual), transport_status=status)

    for delay in (100, None):
        c = Client(); c.ultimate.replies[COMMANDS[0]] = [(b'X', b'00,OK')]
        c.ultimate.stuck = True; c.ultimate.delay = delay
        c.query(expected=0x11, max_steps=12000000)
        assert c.ram[STATUS] == 255 and c.ultimate.abort_requests == 1
        assert c.ultimate.commands == [COMMANDS[0]] and not c.ram[BUSY]
        if delay is None:
            c.query(expected=0x15)
            assert c.ultimate.abort_requests == 1 and c.ultimate.commands == [COMMANDS[0]]
            c.ultimate.complete_abort()
        assert not c.ultimate.pending
        c.ultimate.stuck = False
        assert c.query() == b'X'
        cases[f'abort-delay-{delay}'] = dict(single_abort=True, no_implicit_replay=True, explicit_reuse=True)

    c = Client(); file_handle = c.open_u(b'/kept', device=2)
    cursor = c.directory()
    c.ultimate.replies[COMMANDS[0]] = [(b'ID', b'00,OK')]
    records = bytes(c.ram[RECORDS:RECORDS+32])
    paths = copy.deepcopy(c.ultimate.paths); snapshots = copy.deepcopy(c.ultimate.snapshots)
    handles = copy.deepcopy(c.ultimate.handles)
    assert c.query() == b'ID'
    assert bytes(c.ram[RECORDS:RECORDS+32]) == records
    assert (c.ultimate.paths, c.ultimate.snapshots, c.ultimate.handles) == (paths, snapshots, handles)
    assert c.read_u() == b'\x20ONE'
    records = bytes(c.ram[RECORDS:RECORDS+32]); sent = len(c.ultimate.commands)
    c.query(expected=0x15)
    assert len(c.ultimate.commands) == sent and not c.ultimate.aborted
    assert bytes(c.ram[RECORDS:RECORDS+32]) == records
    assert c.read_u() == b'\x20TWO'
    assert c.query() == b'ID'
    c.call(CLOSE); c.select(file_handle)
    assert c.read_u() == b'PRESERVED'
    c.clean()
    cases['owned-file-and-directory-lifetimes'] = dict(idle_snapshot_preserved=True,
        pending_cursor_refused=True, completed_cursor_preserved=True, file_readback=True)

    c = Client(); c.ultimate.handles[1] = dict(name=b'/foreign', mode=1, pos=123)
    c.ultimate.replies[COMMANDS[0]] = [(b'ID', b'00,OK')]
    before = copy.deepcopy(c.ultimate.handles)
    assert c.query() == b'ID' and c.ultimate.handles == before
    cases['foreign-file-untouched'] = dict(no_close_or_seek=True)
    return cases


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    report = dict(passed=False, physical_hardware_io=False,
        kernel_sha256=hashlib.sha256(IMAGE.read_bytes()).hexdigest())
    try:
        report['cases'] = run(); report['passed'] = True
        print(f"PASS: {len(report['cases'])} native query workflows")
    except BaseException as error:
        report['error'] = str(error); raise
    finally:
        args.report.write_text(json.dumps(report, indent=2)+'\n')
