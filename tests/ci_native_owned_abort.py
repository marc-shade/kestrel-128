#!/usr/bin/env python3
"""Model delayed completion of a native-owned UCI abort; no hardware I/O."""
import argparse
import hashlib
import json
from pathlib import Path

from ci_native_directory_ultimate import Client, DirectoryDOS
from ci_native_files import RECORDS, CLOSE, STATUS
from ci_native_heap import IMAGE, symbol


class DelayedAbort(DirectoryDOS):
    def __init__(self, op=0x13, occurrence=1, *, delay=100, phase='command', files=None):
        super().__init__([b'\x20NOTE', b'\x20SECOND'], files)
        self.fault_op = op
        self.occurrence = occurrence
        self.phase = phase
        self.delay = delay
        self.seen = 0
        self.inject_once = True
        self.blocked = False
        self.pending = False
        self.abort_reads = 0
        self.abort_requests = 0
        self.active_op = None

    def complete_abort(self):
        self.pending = False
        self.blocked = False
        super().__setitem__(0xdf1c, 4)

    def __setitem__(self, address, value):
        if address == 0xdf1c and value == 4:
            self.abort_requests += 1
            self.blocked = False
            self.pending = True
            self.abort_reads = 0
            if self.delay == 0:
                self.complete_abort()
            return
        if address == 0xdf1c and value == 1:
            self.active_op = bytes(self.command)[1]
            if self.active_op == self.fault_op:
                self.seen += 1
                if self.phase == 'command' and self.seen == self.occurrence and self.inject_once:
                    self.inject_once = False
                    self.blocked = True
        if address == 0xdf1c and value == 2 and self.active_op == self.fault_op:
            if self.phase in ('ack', 'ack-accepted') and self.seen == self.occurrence and self.inject_once:
                self.inject_once = False
                self.blocked = True
        super().__setitem__(address, value)

    def __getitem__(self, address):
        if address == 0xdf1c:
            if self.blocked:
                return 0x12 if self.phase == 'ack-accepted' else 0x10
            if self.pending:
                self.abort_reads += 1
                if self.delay is not None and self.abort_reads >= self.delay:
                    self.complete_abort()
                return 4
        return super().__getitem__(address)


def client(**kwargs):
    c = Client(files=kwargs.get('files'))
    c.ultimate = DelayedAbort(**kwargs)
    c.m.bus.dos = c.ultimate
    return c


def directory_fault(*, op=0x13, occurrence=1, context=2, delay=100, phase='command', with_irq=False):
    c = client(op=op, occurrence=occurrence, delay=delay, phase=phase)
    interrupts = []

    def interrupt(cpu, steps):
        if c.ultimate.pending and steps % 97 == 0 and not cpu.p & 4:
            cpu.irq()
            interrupts.append(steps)

    call_args = dict(flags=8 if with_irq else 0, interrupt=interrupt if with_irq else None,
                     max_steps=12000000)
    if op == 0x14:
        c.directory(device=context)
        c.read_u(expected=0x11, **call_args)
    else:
        c.directory(device=context, expected=0x11, **call_args)
    assert c.ram[STATUS] == 0xff
    assert c.ultimate.abort_requests == 1
    assert not c.ultimate.pending, 'owned abort returned before its delayed completion'
    assert c.ultimate.state == 0
    if with_irq:
        assert interrupts, 'interrupts must execute during the abort wait'
    assert c.ram[RECORDS] == 32 and c.ram[RECORDS+3] & 4
    commands = list(c.ultimate.commands)
    assert sum(cmd[1] == op for cmd in commands) == occurrence
    c.call(CLOSE)
    assert c.ultimate.commands[len(commands):] == [bytes([context, 0x11]) +
        (b'/shell' if context == 1 else b'/browser'), bytes([context, 0x12])]
    assert not c.ram[RECORDS] and c.ultimate.abort_requests == 1
    c.clean()
    return dict(first_status=0xff, abort_requests=1, abort_status_reads=c.ultimate.abort_reads,
                no_command_replay=True, immediate_explicit_close_passed=True,
                instructions=c.instructions, abort_wait_interrupts=len(interrupts))


def run():
    cases = {}
    # This first case is also run on the frozen unmodified kernel as the
    # regression's negative control.
    cases['open-directory-delayed-abort'] = directory_fault()
    for delay in (0, 1, 1000):
        cases[f'delay-{delay}'] = directory_fault(context=1, delay=delay)
    for op, occurrence in ((0x11, 1), (0x12, 2), (0x14, 1)):
        cases[f'command-{op:02x}'] = directory_fault(op=op, occurrence=occurrence)
    for phase in ('ack', 'ack-accepted'):
        cases[phase] = directory_fault(phase=phase)
    cases['abort-wait-irqs-and-decimal'] = directory_fault(delay=1000, with_irq=True)
    c = client(phase='protocol')
    c.directory(device=2)
    c.ultimate.inject[0x14] = lambda command, reply: [(bytes(513), b'00,OK')]
    c.read_u(expected=0x11)
    assert c.ram[STATUS] == 0xfc and c.ultimate.abort_requests == 1 and not c.ultimate.pending
    commands = len(c.ultimate.commands)
    c.call(CLOSE)
    assert len(c.ultimate.commands) == commands+2
    c.clean()
    cases['malformed-packet'] = dict(first_status=0xfc, immediate_explicit_close_passed=True)
    c = client(delay=None)
    c.directory(device=2, expected=0x11, max_steps=12000000)
    assert c.ultimate.pending and c.ultimate.abort_requests == 1 and c.ram[STATUS] == 0xff
    assert c.ram[RECORDS] == 32 and c.ram[RECORDS+3] & 4
    assert c.ram[symbol('nd_active')] == 0
    commands = len(c.ultimate.commands)
    c.call(CLOSE, 0x15)
    assert len(c.ultimate.commands) == commands and c.ultimate.abort_requests == 1
    assert c.ram[RECORDS] == 32
    c.ultimate.complete_abort()
    c.call(CLOSE)
    c.clean()
    cases['abort-never-completes'] = dict(bounded_return=True, owner_retained=True,
        abort_requests=1, no_implicit_replay=True, external_completion_then_explicit_close=True,
        status_reads=c.ultimate.abort_reads, instructions=c.instructions)
    c = client()
    c.ultimate.state = 0x10
    c.ultimate.stuck = True
    c.directory(expected=0x15)
    assert not c.ultimate.commands and not c.ultimate.abort_requests
    assert c.ram[STATUS] == 0xe2
    cases['foreign-transaction'] = dict(no_command=True, no_abort=True)
    c = client(files={b'/kept': b'PRESERVED'})
    other = c.open_u(b'/kept', device=1)
    c.directory(device=2, expected=0x11, max_steps=12000000)
    assert c.ultimate.handles[1]['pos'] == 0 and not c.ultimate.pending
    c.call(CLOSE)
    c.select(other)
    assert c.read_u() == b'PRESERVED'
    c.clean()
    cases['other-context-file'] = dict(contents_preserved=True, stream_preserved=True, all_released=True)
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    report = dict(passed=False, hardware_io=False,
                  kernel_sha256=hashlib.sha256(IMAGE.read_bytes()).hexdigest(),
                  physical_initiating_failure_proven=False,
                  model_limit='Synthetic status-read delays, not measured cartridge timing.')
    try:
        report['cases'] = run()
        report['passed'] = True
        print(f"PASS: {len(report['cases'])} owned-abort completion workflows")
    except BaseException as error:
        report['error'] = str(error)
        raise
    finally:
        if args.report:
            args.report.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
