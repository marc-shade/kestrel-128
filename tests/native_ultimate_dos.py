#!/usr/bin/env python3
"""The Ultimate II+ DOS as the CPU tests see it (docs/NATIVE-ULTIMATE.md):
the UCI command interface of UCIBus with a file model behind it that keeps
actual bytes and positions for both DOS contexts, including short writes,
fragmented reads and injected replies."""
from collections import deque

from uci_bus import UCIBus


class Files(UCIBus):
    def __init__(self, files=None):
        super().__init__([])
        self.ram[:] = bytes((i*17+91) & 255 for i in range(65536))
        self.files = {name: bytearray(data) for name, data in (files or {}).items()}
        self.handles = {1: None, 2: None}
        self.paths = {1: b'/shell', 2: b'/browser'}
        self.write_limit = None
        self.read_limit = None
        self.fragment = None
        self.read_status = b''
        self.direct_write_corruption = False
        self.inject = {}

    def __setitem__(self, address, value):
        if address == 0xdf1c and value == 1:
            command = bytes(self.command)
            assert command[0] in (1, 2), command
            reply = self.respond(command)
            override = self.inject.get(command[1])
            if override:
                reply = override(command, reply)
            self.packets = deque(reply)
        super().__setitem__(address, value)

    def respond(self, command):
        target, op = command[:2]
        handle = self.handles[target]
        if op == 7:
            if handle is None:
                return [(b'', b'85,NO FILE OPEN')]
            name = handle['name']
            metadata = len(self.files[name]).to_bytes(4, 'little') + bytes(7) + b'\x20'
            return [(metadata + name[:63], b'00,OK')]
        if op == 2:
            assert handle is None, 'OPEN overwrote an existing handle'
            mode, name = command[2], command[3:]
            if mode == 7:
                if name in self.files:
                    return [(b'', b'FILE EXISTS')]
                self.files[name] = bytearray()
            elif name not in self.files:
                return [(b'', b"FILE DOESN'T EXIST")]
            assert mode in (1, 7)
            self.handles[target] = dict(name=name, mode=mode, pos=0)
            return [(b'', b'00,OK')]
        if op == 3:
            self.handles[target] = None
            return [(b'', b'00,OK' if handle else b'84,NO FILE TO CLOSE')]
        assert handle is not None, ('operation without a handle', command)
        data = self.files[handle['name']]
        if op == 6:
            handle['pos'] = int.from_bytes(command[2:6], 'little')
            return [(b'', b'00,OK')]
        if op == 4:
            length = int.from_bytes(command[2:4], 'little')
            if self.read_limit is not None:
                length = min(length, self.read_limit)
            payload = bytes(data[handle['pos']:handle['pos']+length])
            handle['pos'] += len(payload)
            parts = [payload]
            if self.fragment:
                parts = [payload[i:i+self.fragment] for i in range(0, len(payload), self.fragment)] or [b'']
            return [(part, self.read_status if i == len(parts)-1 else b'')
                    for i, part in enumerate(parts)]
        if op == 5:
            assert handle['mode'] == 7 and command[2:4] == b'\0\0'
            payload = command[4:]
            if self.write_limit is not None:
                limit = (self.write_limit.get(len(payload),len(payload))
                         if isinstance(self.write_limit,dict) else self.write_limit)
                payload = payload[:limit]
            start = handle['pos']
            if self.direct_write_corruption and start % 512 == 0 and len(payload) >= 512:
                # Reference USB firmware's direct-sector DMA cannot reach the
                # command FIFO mapping. It reports OK but saves other bytes.
                payload = bytes(byte ^ 0xa5 for byte in payload)
            data[start:start+len(payload)] = payload
            handle['pos'] += len(payload)
            return [(b'', b'00,OK')]
        raise AssertionError(command)

