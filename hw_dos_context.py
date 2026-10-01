"""The Ultimate II+'s two DOS contexts, observed from outside the OS under test.

A file a DOS context holds open survives a C128 reset and a REST
machine:reboot (seen 2026-09-30: a failed CLOSE left a file open in context
2, its folder was then deleted, and the next checks were refused by the
native service, which claims a context only when FILE_INFO reports 85).

probes/hw-dos-context.asm sends one UCI command, [context, command], in C64
mode (REST run_prg) and leaves the reply in RAM. One command per run: a
later command in the same probe run has read a wrong identity byte from
$df1d on the reference cartridge. Reading the reply over DMA waits until
the probe has finished, so no DMA overlaps its interface accesses.
"""
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parent
PROBE = ROOT/'probes/hw-dos-context.asm'
FILE_INFO, CLOSE = 0x07, 0x03
CONTEXTS = (1, 2)
RESULTS = {0x01: 'complete', 0xff: 'no interface', 0xfe: 'interface not idle', 0xfd: 'timeout'}


def build(work, context, command):
    output = Path(work)/f'dos-context-{context}-{command:02x}.prg'
    subprocess.run(['64tass', '-q', '-D', f'TARGET={context}', '-D', f'COMMAND={command}', '-o', str(output), str(PROBE)],
                   check=True, capture_output=True)
    return output.read_bytes()


def settled(ult, address, length, attempts=8):
    previous = ult.read_mem(address, length)
    for _ in range(attempts):
        current = ult.read_mem(address, length)
        if current == previous:
            return current
        previous = current
    raise RuntimeError(f'DMA read of ${address:04x} never settled')


def send(ult, work, context, command, *, start_delay=3.0, timeout=30.0):
    """Run one probe; return its reply. The C128 is left in C64 mode."""
    assert context in CONTEXTS and command in (FILE_INFO, CLOSE)
    ult.run_prg(build(work, context, command))
    time.sleep(start_delay)
    deadline = time.monotonic()+timeout
    while settled(ult, 0xc000, 1)[0] != 0xaa:
        if time.monotonic() > deadline:
            raise RuntimeError(f'DOS context probe ({context}, ${command:02x}) did not finish')
        time.sleep(1)
    page = settled(ult, 0xc100, 256)
    return dict(context=context, command=command, result=RESULTS.get(page[0], f'unknown {page[0]:02x}'),
                status=page[0x80:0x80+min(page[2], 64)].decode('latin-1'),
                data_hex=page[0x10:0x10+min(page[1], 64)].hex(),
                registers_before=page[3:5].hex())


def idle(reply):
    return reply['result'] == 'complete' and reply['status'].startswith('85')


class DosContexts:
    """FILE_INFO and CLOSE for HardwareSession; every reply is recorded."""

    def __init__(self, ult, work):
        self.ult, self.work = ult, Path(work)
        self.replies = []

    def _send(self, context, command):
        reply = send(self.ult, self.work, context, command)
        self.replies.append(reply)
        return reply

    def info(self, context):
        return self._send(context, FILE_INFO)

    def close(self, context):
        return self._send(context, CLOSE)
