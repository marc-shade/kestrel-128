#!/usr/bin/env python3
"""Run the standalone module SDK example through the assembled native kernel.

Uses the existing CPU/MMU, KERNAL file and Ultimate register models. It does
not rebuild system images, contact hardware or claim physical qualification.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import tempfile

from py65.devices.mpu6502 import MPU
from ci_native_calc import Calculator
from ci_native_heap import Machine, ROOT, IMAGE
from ci_native_files import StreamIEC
from ci_native_ultimate import DOSFiles, UltimateBus

EXAMPLE = ROOT / 'examples/native-module'
APP_NAME = b'MODULEDEMO.PRG'
MODULE_NAME = b'COUNTER.PRG'
APP_PATH = b'/Usb0/SDK/' + APP_NAME
MODULE_PATH = b'/Usb0/SDK/' + MODULE_NAME


class Demo(Calculator):
    def __init__(self, output, *, fmt=0, context=1, module='valid', close_failure=False):
        self.m = Machine()
        self.ram = self.m.ram
        self.image_name = 'sdk-module'
        self.image = (output / 'MODULEDEMO.PRG').read_bytes()
        self.module = (output / 'COUNTER.PRG').read_bytes()
        self.symbols = {
            name: int(value, 16) for name, value in re.findall(
                r'^(\w+)\s*=\s*\$([0-9a-fA-F]+)', (output / 'parent.sym').read_text(), re.M)
        }
        image = self.module
        if module == 'checksum':
            image = image[:-1] + bytes([image[-1] ^ 1])
        elif module == 'parent':
            image = image[:12] + bytes([image[12] ^ 1]) + image[13:]
        elif module == 'short':
            image = image[:-1]
        files = {(8, APP_NAME, b'P'): self.image}
        if module != 'missing':
            files[8, MODULE_NAME, b'P'] = image
        self.io = StreamIEC(self.m, files)
        self.io.formats[8] = fmt if fmt < 3 else 0
        self.ram[0x3d21:0x3d23] = bytes([8, len(APP_NAME)])
        self.ram[0x3d40:0x3d40+len(APP_NAME)] = APP_NAME
        self.ram[0x3d29:0x3d2b] = bytes([8, fmt])
        self.ram[0x3d2c:0x3d2e] = bytes([fmt, 8])
        if fmt == 3:
            files = {APP_PATH: self.image}
            if module != 'missing':
                files[MODULE_PATH] = image
            self.ultimate = DOSFiles(files)
            self.ultimate.fragment = 7
            self.m.bus = UltimateBus(self.m.bus, self.ultimate)
            self.ram[0x3d21:0x3d23] = bytes([context, len(APP_PATH)])
            self.ram[0x4e00:0x4e00+len(APP_PATH)] = APP_PATH
            if close_failure:
                closes = []

                def fail_module_close(command, reply):
                    closes.append(command)
                    return reply if len(closes) == 1 else [(b'', b'71,CLOSE ERROR')]

                self.ultimate.inject[3] = fail_module_close
        self.cpu = MPU(memory=self.m.bus, pc=0x1c38)
        self.cpu.sp = 0xe0
        self.cpu.p = 0x20
        self.cpu.stPushWord(0xaff)
        self.screens = [bytearray(b' '*1000), bytearray(b' '*2000)]
        self.reverse = [False, False]
        self.row = [0, 0]
        self.col = [0, 0]
        self.keys = []
        self.events = self.instructions = 0
        self.observation_target = None
        self.observation_done = False
        self.loop()
        assert self.ram[0x3d20] == 32 and self.ram[0x3d23] == 2
        assert self.m.stats() == (171, 251, 31)
        assert not self.io.handles

    def symbol(self, name):
        return self.symbols['input_loop' if name == 'cloop' else name]

    def token(self):
        start = self.symbol('token')
        return bytes(self.ram[start:start+3])

    def io_counts(self):
        return len(self.io.events), len(self.ultimate.commands) if hasattr(self, 'ultimate') else 0

    def repair_module(self):
        self.io.files[8, MODULE_NAME, b'P'] = bytearray(self.module)
        if hasattr(self, 'ultimate'):
            self.ultimate.files[MODULE_PATH] = bytearray(self.module)

    def check(self, value=0, status=0, error=0, carry=0):
        assert (self.value('result'), self.value('status'), self.value('error'),
                self.value('module_carry')) == (value, status, error, carry)
        message = ('READY', f'LOAD ERROR ${error:02X}',
                   f'CALL ERROR ${error:02X}', 'COUNTER WRAPPED')[status]
        lines = ['MODULE DEMO', f'COUNTER (HEX): ${value:02X}', message, '',
                 'RETURN: CALL LOADED MODULE', 'R: RELOAD COUNTER.PRG',
                 'ESC: EXIT']
        for screen, columns in zip(self.screens, (40, 80)):
            expected = bytearray(b' ' * (columns*25))
            for row, line in enumerate(lines):
                expected[row*columns:row*columns+len(line)] = bytes(
                    value-64 if 64 <= value < 96 else value for value in line.encode())
            assert screen == expected, (columns, lines)

    def exit(self):
        self.key(27, exited=True)
        if hasattr(self, 'ultimate'):
            assert self.ultimate.handles == {1: None, 2: None}
        assert self.ram[0x3d1b] == 0 and self.ram[0x3d17:0x3d1a] == bytes(3)


def check_example(output):
    results = {}
    for fmt, context in ((0, 1), (1, 1), (2, 1), (3, 1), (3, 2)):
        demo = Demo(output, fmt=fmt, context=context)
        demo.check()
        token, counts = demo.token(), demo.io_counts()
        assert token != bytes(3) and demo.ram[0x3d1b] == 2
        calls = 256 if fmt == 0 else 3
        for number in range(1, calls+1):
            demo.key(13)
            wrapped = int(number == 256)
            demo.check(number & 255, 3 if wrapped else 0, carry=wrapped)
            assert demo.token() == token and demo.io_counts() == counts
        # File argument buffers and browser preferences are scratch; none
        # may redirect the module away from its captured app source.
        demo.ram[0x3d85] = 2 if context == 1 else 1
        demo.ram[0x3d29:0x3d2b] = bytes([9, 2])
        demo.ram[0x4e00:0x4e00+8] = b'/changed'
        if fmt == 3:
            demo.ultimate.paths = {1: b'/changed-one', 2: b'/changed-two'}
        demo.key(ord('R'))
        demo.check()
        assert demo.token() != token and demo.token() != bytes(3)
        if fmt == 3:
            assert demo.ultimate.paths == {1: b'/changed-one', 2: b'/changed-two'}
            opens = [command for command in demo.ultimate.commands if command[1] == 2]
            assert opens[-1] == bytes([context, 2, 1]) + MODULE_PATH
        demo.key(13)
        demo.check(1)
        demo.exit()
        results[f'source-{fmt}-context-{context}'] = dict(
            warm_calls=calls, warm_calls_have_no_io=True, reload_resets_state=True,
            original_source_preserved=True, both_complete_screens=True, exit_releases_all=True,
        )
    for kind, error in (('missing', 0x11), ('checksum', 0x14), ('parent', 0x10), ('short', 0x12)):
        for fmt in (0, 3):
            demo = Demo(output, fmt=fmt, module=kind)
            demo.check(status=1, error=error)
            assert demo.token() == bytes(3) and demo.ram[0x3d1b] == 0
            counts = demo.io_counts()
            demo.key(13)
            demo.check(status=1, error=error)
            assert demo.io_counts() == counts
            demo.repair_module()
            demo.key(ord('R'))
            demo.check()
            demo.key(13)
            demo.check(1)
            demo.exit()
            results[f'{kind}-source-{fmt}'] = dict(
                error=error, no_implicit_io_retry=True, explicit_retry_passed=True,
                both_complete_screens=True, exit_releases_all=True,
            )
    demo = Demo(output)
    demo.key(13)
    demo.check(1)
    demo.ram[demo.symbol('token')] ^= 0x80
    demo.key(13)
    demo.check(value=1, status=2, error=4)
    assert demo.token() == bytes(3)
    counts = demo.io_counts()
    demo.key(13)
    assert demo.io_counts() == counts
    demo.key(ord('R'))
    demo.check()
    demo.key(13)
    demo.check(1)
    demo.exit()
    results['stale-call-token'] = dict(gate_error_distinct=True, explicit_retry_passed=True)
    demo = Demo(output, fmt=3, close_failure=True)
    demo.check(status=1, error=0x11)
    assert demo.ram[0x3d1b] == 4 and demo.token() == bytes(3)
    counts = demo.io_counts()
    demo.key(13)
    assert demo.io_counts() == counts
    del demo.ultimate.inject[3]
    demo.key(ord('R'))
    demo.check()
    assert demo.ram[0x3d1b] == 2
    demo.key(13)
    demo.check(1)
    demo.exit()
    results['ultimate-retained-close'] = dict(no_implicit_io_retry=True, explicit_checked_cleanup=True)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='retain the example build in this separate directory')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    report = dict(passed=False, hardware_io=False,
                  kernel_sha256=hashlib.sha256(IMAGE.read_bytes()).hexdigest())
    try:
        spec = importlib.util.spec_from_file_location('sdk_module_build', EXAMPLE / 'build.py')
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        with tempfile.TemporaryDirectory(prefix='kestrel-sdk-module-') as scratch:
            output = args.output or Path(scratch)
            report['build'] = builder.build(output)
            report['cases'] = check_example(output)
        report['passed'] = True
        print(f"PASS: module SDK example, {len(report['cases'])} CPU workflows, both screens, source and retry lifecycle")
    except BaseException as error:
        report['error'] = str(error)
        raise
    finally:
        if args.report:
            args.report.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
