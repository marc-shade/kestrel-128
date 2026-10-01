"""Diagnostic transport: retain write receipts and pause only bounded DMA batches."""
from contextlib import contextmanager
import hashlib
import json

from hw_storage_check import HardwareMonitor
from hw_ultimate_check import VerifiedUltimate


class ReceiptUltimate(VerifiedUltimate):
    """An acknowledged address range is evidence of parsing, not a RAM readback."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ram_write_receipts = []

    def write_mem(self, address, data):
        data = bytes(data)
        if not (0 <= address < 65536 and 1 <= len(data) <= 128
                and address + len(data) <= 65536):
            raise ValueError('RAM writes require 1..128 bytes within $0000..$ffff')
        expected = f'{address:04x}-{address+len(data)-1:04x}'
        row = dict(address=address, bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                   expected_range=expected, request_started=True, response_received=False,
                   range_acknowledged=False, replayed=False)
        self.ram_write_receipts.append(row)
        self.record_event()
        try:
            status, body = self._call('PUT',
                f'/v1/machine:writemem?address={address:04X}&data={data.hex().upper()}')
            row.update(response_received=True, status=status, body_hex=body.hex())
            self.record_event()
            reply = json.loads(body)
            if not isinstance(reply, dict) or status != 200 or reply.get('errors') != []:
                raise RuntimeError('RAM write response reports an error')
            accepted = reply.get('address')
            row['reported_range'] = accepted
            if not isinstance(accepted, str) or accepted.lower() != expected:
                raise RuntimeError(f'RAM write range differs: expected {expected}, got {accepted!r}')
            row['range_acknowledged'] = True
        except BaseException as error:
            row['error'] = dict(type=type(error).__name__, message=str(error))
            self.uncertain_writes.append(dict(address=address, bytes=len(data),
                sha256=row['sha256'], replayed=False, reason='exact RAM write acknowledgement missing'))
            self.record_event()
            raise
        self.record_event()


class PausedHardwareMonitor(HardwareMonitor):
    """Used only after the diagnostic proves the initial desktop is running."""
    def __init__(self, ultimate):
        super().__init__(ultimate)
        self.batches = []
        self.in_batch = False

    @contextmanager
    def paused(self, label):
        if self.in_batch:
            raise RuntimeError('nested hardware capture batch')
        self.in_batch = True
        row = dict(label=label, pause_acknowledged=False, resume_attempted=False,
                   resume_acknowledged=False)
        self.batches.append(row)
        try:
            self.ultimate.control('PUT', '/v1/machine:pause')
            row['pause_acknowledged'] = True
            self.ultimate.record_event()
            yield
        except BaseException as error:
            row['error'] = dict(type=type(error).__name__, message=str(error))
            raise
        finally:
            # One compensating resume is necessary even if the pause reply
            # was lost. Never replay the pause or silently retry a failed batch.
            row['resume_attempted'] = True
            try:
                self.ultimate.control('PUT', '/v1/machine:resume')
                row['resume_acknowledged'] = True
            finally:
                self.in_batch = False
                self.ultimate.record_event()


_UNRESOLVED = object()


class PausedViceMonitor:
    """VICE monitor reads stop the CPU; suppress inner resumes until batch exit."""
    def __init__(self, monitor, *, signature_bank=None):
        self.monitor = monitor
        self.signature_bank = signature_bank
        self.batches = []
        self.in_batch = False
        self._control_bank = _UNRESOLVED

    @property
    def control_bank(self):
        """VICE bank id of physical RAM bank 0, or None for a monitor without banks.

        A monitor pause can land inside the ROM's INDFET while the IRQ probe
        reads bank 1. The CPU view then shows bank 1 at $3a00..$3fff, where a
        nonzero byte at $3ff2 looks like a finished chunk. The capture's own
        control traffic lives in bank 0 and is read there."""
        if self._control_bank is _UNRESOLVED:
            banks = getattr(self.monitor, 'banks', None)
            self._control_bank = None
            if banks is not None:
                self._control_bank = banks()['ram00']
                self.resume()
        return self._control_bank

    def read_mem(self, *args, **kwargs):
        return self.monitor.read_mem(*args, **kwargs)

    def write_mem(self, *args, **kwargs):
        return self.monitor.write_mem(*args, **kwargs)

    def resume(self):
        if not self.in_batch:
            self.monitor.resume()

    @contextmanager
    def paused(self, label):
        if self.in_batch:
            raise RuntimeError('nested emulator capture batch')
        row = dict(label=label, pause_acknowledged=False, resume_attempted=False,
                   resume_acknowledged=False)
        self.batches.append(row)
        self.in_batch = True
        try:
            # Read-only progress observations may stop inside a bank-1
            # transfer. The caller can identify the kernel's physical bank;
            # its presence does not imply that the CPU is idle or safe to borrow.
            options={} if self.signature_bank is None else {'bank':self.signature_bank}
            signature=bytes(self.monitor.read_mem(0x1c13,0x1c18,**options))
            row.update(signature_bank=self.signature_bank,signature_hex=signature.hex())
            assert signature==b'KES128'
            row['pause_acknowledged'] = True
            yield
        finally:
            row['resume_attempted'] = True
            try:
                self.monitor.resume()
                row['resume_acknowledged'] = True
            finally:
                self.in_batch = False
