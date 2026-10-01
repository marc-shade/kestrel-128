"""UCI register/FIFO model for running the assembled driver with Py65.

This models the public register handshake, not the driver's implementation.
Replies are sequences of (data, status) packets. DATA_ACC discards unread
bytes; the tests can detect that loss. BUSY separates successive packets.
Hardware verification is still required for electrical/timing behavior.
"""
from collections import deque
from pathlib import Path

from py65.devices.mpu6502 import MPU

ROOT = Path(__file__).resolve().parents[1]


class UCIBus:
    def __init__(self, packets=(), present=True, stuck=False):
        self.ram = bytearray(65536)
        self.present = present
        self.stuck = stuck
        self.packets = deque(packets)
        self.data = deque()
        self.status = deque()
        self.command = bytearray()
        self.commands = []
        self.state = 0
        self.busy = 0
        self.accepted = 0
        self.discarded = 0
        self.aborted = 0
        self.writes = []

    def __getitem__(self, address):
        if isinstance(address, slice):
            return self.ram[address]
        if address == 0xdf1d:
            return 0xc9 if self.present else 0xff
        if address == 0xdf1c:
            if self.stuck and self.state:
                return 0x10
            if self.busy:
                self.busy -= 1
                return 0x10
            return self.state | (0x80 if self.data else 0) | (0x40 if self.status else 0)
        if address == 0xdf1e:
            assert self.data, "Read from empty UCI data FIFO"
            return self.data.popleft()
        if address == 0xdf1f:
            assert self.status, "Read from empty UCI status FIFO"
            return self.status.popleft()
        return self.ram[address]

    def __setitem__(self, address, value):
        if isinstance(address, slice):
            self.ram[address] = value
            return
        if address == 0xdf1d:
            assert self.state == 0, "Command written while UCI is busy"
            self.command.append(value)
            return
        if address == 0xdf1c:
            if value == 1:
                assert self.state == 0 and len(self.command) >= 2
                self.commands.append(bytes(self.command))
                self.command.clear()
                self._next()
            elif value == 2:
                assert self.state in (0x20, 0x30), "ACK outside a response"
                self.discarded += len(self.data) + len(self.status)
                self.data.clear()
                self.status.clear()
                self.accepted += 1
                self._next()
            elif value == 4:
                self.aborted += 1
                self.state = self.busy = 0
                self.data.clear()
                self.status.clear()
                self.command.clear()
            elif value != 8:
                raise AssertionError(f"Unknown UCI control write: {value:#x}")
            return
        self.writes.append(address)
        self.ram[address] = value

    def _next(self):
        if not self.packets:
            self.state = self.busy = 0
            return
        data, status = self.packets.popleft()
        self.data = deque(data)
        self.status = deque(status)
        self.state = 0x30 if self.packets else 0x20
        self.busy = 3
