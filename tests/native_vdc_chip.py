#!/usr/bin/env python3
"""The VDC (8563) as the CPU tests see it: 64 KiB of video RAM behind the
selected-register handshake at $d600/$d601, which a read or write before
the ready bit makes an error; CaptureBus can also make the update address
drift, as a capture that must resynchronise sees it."""
from py65.devices.mpu6502 import MPU


class VDC:
    def __init__(self, present=True):
        self.ram = bytearray(65536)
        self.video = bytearray([0xa5])*65536
        self.reg = bytearray(64)
        self.reg[1],self.reg[6],self.reg[28] = 80,25,32
        self.present = present
        self.selected,self.busy,self.ready = 0,0,False

    def __getitem__(self, a):
        if a == 0xd600:
            if not self.present:
                return 0
            if self.busy:
                self.busy -= 1
                return 0
            self.ready = True
            return 0x80
        if a == 0xd601:
            assert self.ready, f'Read register {self.selected} before ready'
            self.ready,self.busy = False,2
            if self.selected == 31:
                address = self.reg[18]<<8|self.reg[19]
                value = self.video[address]
                self.advance(address)
                return value
            return self.reg[self.selected]
        return self.ram[a]

    def __setitem__(self, a, value):
        if a == 0xd600:
            self.selected,self.busy,self.ready = value&63,3,False
        elif a == 0xd601:
            assert self.ready, f'Write register {self.selected} before ready'
            self.ready,self.busy = False,2
            if self.selected == 31:
                address = self.reg[18]<<8|self.reg[19]
                self.video[address] = value
                self.advance(address)
            else:
                self.reg[self.selected] = value
        else:
            self.ram[a] = value

    def advance(self,address):
        address = (address+1)&65535
        self.reg[18],self.reg[19] = address>>8,address&255

    def call(self, pc, a=0, x=0):
        c = MPU(memory=self,pc=pc)
        c.a,c.x,c.y = a,x,0x69
        c.stPushWord(0x02ff)
        for _ in range(200000):
            if c.pc == 0x0300:
                return c
            c.step()
        raise AssertionError('Driver call did not return')



class CaptureBus(VDC):
    def __init__(self, fault=None, present=True):
        super().__init__(present)
        self.fault = fault
        self.reads = 0

    def __getitem__(self, address):
        data_read = address == 0xd601 and self.selected == 31
        value = super().__getitem__(address)
        if data_read:
            if self.fault == 'always' or self.reads == self.fault:
                next_address = self.reg[18] << 8 | self.reg[19]
                self.advance(next_address + 1)
            self.reads += 1
        return value

