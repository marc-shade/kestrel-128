"""The machine object native_aes_workflow and native_gemdesk_workflow drive,
over a running x128's binary monitor (PausedViceMonitor): direct reads of
either RAM bank, keys through the native keyboard buffer while the CPU is
paused. VICE has no IEC timing to protect, so key io hints are ignored."""
import time


class ViceMachine:
    scale = 1
    min_attempts = 1

    def __init__(self, paused, banks, emu, work):
        self.paused, self.banks, self.emu, self.work = paused, banks, emu, work

    def value(self, at, n=1, bank=0):
        result = bytes(self.paused.read_mem(at, at+n-1, bank=self.banks[f'ram0{bank}']))
        self.paused.resume()
        return result

    def read(self, at, n=1):
        assert at+n <= 0x4000, 'common RAM only'
        return self.value(at, n)

    def surface(self, label):
        return self.value(0xc000, 0x2400)

    def wait(self, predicate, label, seconds=300):
        deadline = time.monotonic()+seconds
        while time.monotonic() < deadline:
            if predicate():
                return
            assert self.emu.poll() is None
            time.sleep(.05)
        raise AssertionError(label)

    def pause(self):
        time.sleep(.2)

    def key(self, value, io=None):
        self.wait(lambda: self.read(0x3d12) == b'\1' and self.read(0xd0) == b'\0', 'input ready')
        before = int.from_bytes(self.read(0x3d13, 2), 'little')
        with self.paused.paused('key'):
            self.paused.write_mem(0x3d12, b'\0'); self.paused.write_mem(0x34a, bytes([value]))
            self.paused.write_mem(0xd0, b'\1')
        self.wait(lambda: int.from_bytes(self.read(0x3d13, 2), 'little') == (before+1) & 65535
                  and self.read(0x3d12) == b'\1' and self.read(0xd0) == b'\0', f'key {value:#x}')


class ViceDma:
    """hw_storage_check.HardwareMonitor's interface (bank-0 reads and writes,
    the CPU running between them) over x128's monitor, so a hardware
    runner's own code (HeldMachine, HeldCapture) can be rehearsed in VICE."""

    def __init__(self, monitor, bank):
        self.monitor, self.bank = monitor, bank

    def read_mem(self, start, end, bank=0, memspace=0):
        data = bytes(self.monitor.read_mem(start, end, bank=self.bank))
        self.monitor.resume()
        return data

    def write_mem(self, start, data, bank=0, memspace=0):
        self.monitor.write_mem(start, bytes(data), bank=self.bank)
        self.monitor.resume()

    def resume(self):
        pass
