"""VICE for Kestrel 128's emulator tests: the binary monitor (with
banked memory writes and reads) and the helpers in cbm_tools (an Xvfb
display, MESA_EGL for VICE under Xvfb on NVIDIA hosts)."""
import struct

import cbm_tools as cbm


class Monitor(cbm.ViceMonitor):
    def write_mem(self, start, data, bank=0, memspace=0):
        # binary monitor SET uses an INCLUSIVE end address: 1+EA-SA bytes
        body = struct.pack("<BHHBH", 0, start, start + len(data) - 1,
                           memspace, bank) + data
        err, _ = self._recv(self._send(0x02, body))
        if err:
            raise RuntimeError(f"MEM_SET {start:#06x} failed, error {err}")

    def read_zp(self, addr):
        got = self.read_mem(addr, addr, memspace=0)
        self.resume()
        return got[0]
