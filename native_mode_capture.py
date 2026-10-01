"""CPU-observed native mode registers with the qualified IRQ borrower."""
import subprocess
from native_capture import NativeCapture, ROOT


FIELDS = ('foreground_mmu', 'mode', 'common', 'cpu_ddr', 'cpu_port',
          'vic_d011', 'vic_sprites', 'vic_d016', 'vic_d018', 'vic_irq_mask',
          'cia2_port', 'cia2_ddr', 'text_display', 'text_graphics', 'cpu_speed')


class NativeModeCapture(NativeCapture):
    def __init__(self, mon, work, quiet=2, *, kernel_prefix='native', batch=None):
        super().__init__(mon, work, quiet, kernel_prefix=kernel_prefix, batch=batch)
        path=work/'native-mode.prg'
        subprocess.run(['64tass','-a',str(ROOT/'probes/native-mode.asm'),'-o',str(path)],
                       check=True,capture_output=True)
        self.prg=path.read_bytes()
        assert self.prg[:2]==b'\0\x3e' and len(self.prg)-2<=0x1f0

    def snapshot(self, label):
        # The fixed observer reuses the borrow/restore protocol, not the RAM
        # reader. Give the record its explicit source before returning it.
        try:
            raw=super().capture(label,address=0,count=len(FIELDS))
        finally:
            if self.records and self.records[-1]['label']==label:
                self.records[-1].update(source='fixed CPU mode-register snapshot',fields=list(FIELDS))
        return dict(zip(FIELDS,raw))
