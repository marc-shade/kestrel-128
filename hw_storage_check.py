"""RAM access to the reference C128 through the Ultimate II+ REST API, in the
shape of the VICE monitor client the native capture code expects."""


class HardwareMonitor:
    def __init__(self, ultimate):
        self.ultimate = ultimate

    def read_mem(self, start, end, bank=0, memspace=0):
        return self.ultimate.read_mem(start, end - start + 1)

    def write_mem(self, start, data, bank=0, memspace=0):
        for i in range(0, len(data), 128):
            self.ultimate.write_mem(start + i, data[i:i + 128])

    def resume(self):
        pass  # The firmware resumes the CPU itself after DMA observations.
