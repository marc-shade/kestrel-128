#!/usr/bin/env python3
"""Disk-load the Ultimate panel; compare both complete consoles and lifecycle."""
import argparse
from collections import deque
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ci_native_calc as calc
from native_controls_check import panel_screen
from ci_native_heap import Machine
from ci_native_ultimate import UltimateBus
from ci_native_query import QueryDOS
from uci_bus import UCIBus


class PanelDOS(QueryDOS):
    def __init__(self):
        super().__init__()
        self.model = b'Ultimate-II+L'
        self.identities = {1: b'ULTIMATE-II DOS V1.2\0', 2: b'ULTIMATE-II DOS V1.2\0',
            3: b'ULTIMATE-II NETWORK INTERFACE V1.0\0\0', 4: b'CONTROL TARGET V1.1\0'}
        self.inventory = bytes([4, 0, 8, 1, 1, 9, 0, 4, 10, 1, 5, 11, 0])
        self.interfaces = 2
        self.addresses = [bytes([192, 168, 1, 194, 255, 255, 255, 0, 192, 168, 1, 1]), bytes(12)]
        self.time = b'2026/09/12 13:00:00'
        self.faults = {}

    def __setitem__(self, address, value):
        if address == 0xdf1c and value == 1:
            command = bytes(self.command)
            if command in self.faults:
                reply = self.faults[command]
            elif len(command) == 2 and command[1] == 1:
                reply = [(self.identities.get(command[0], b'NO TARGET'), b'00,OK')]
            elif command == b'\x04\x28\x00': reply = [(self.model, b'00,OK')]
            elif command == b'\x04\x29\x01': reply = [(self.inventory, b'00,OK')]
            elif command == b'\x04\x34': reply = [(b'on', b'00,OK')]
            elif command == b'\x04\x35': reply = [(b'off', b'00,OK')]
            elif command == b'\x03\x02': reply = [(bytes([self.interfaces]), b'00,OK')]
            elif command[:2] == b'\x03\x05':
                assert len(command) == 3 and command[2] < self.interfaces
                reply = [(self.addresses[command[2]], b'00,OK')]
            elif command == b'\x01\x26': reply = [(self.time, b'00,OK')]
            else:
                return super().__setitem__(address, value)
            self.packets = deque(reply)
            return UCIBus.__setitem__(self, address, value)
        super().__setitem__(address, value)


class PanelMachine(Machine):
    configure = staticmethod(lambda device: None)

    def __init__(self):
        super().__init__()
        self.device = PanelDOS()
        self.configure(self.device)
        self.bus = UltimateBus(self.bus, self.device)


TITLE = ['ULTIMATE II+', '', 'I INFO  D DRIVES  N NETWORK  T CLOCK', '']
FOOTER = ['', 'R REFRESH   ESC DESKTOP', 'LEFT/RIGHT: TARGET OR INTERFACE']


class Panel(calc.Calculator):
    instruction_limit = 16000000

    def __init__(self, configure=lambda device: None):
        PanelMachine.configure = staticmethod(configure)
        calc.Machine = PanelMachine
        super().__init__('controls', loader_name=b'ULTIMATE', image_prefix='native-desktop')
        self.device = self.m.device

    def check(self, body):
        for display in ((1,) if self.value('ug_bitmap') else (0,1)):
            columns=(40,80)[display]
            expected = panel_screen(columns,body,page=self.value('uc_page'),focus=self.value('ui_selected'),
                mode=self.value('ug_mode'),selected=self.value('ud_selected'),notice=self.value('ug_notice'))
            actual = self.screens[display]
            if actual != expected:
                actual_lines = [bytes(actual[i:i+columns]).hex() for i in range(0, len(actual), columns)]
                raise AssertionError(('panel console mismatch', display, body, actual_lines))

    def exit(self):
        self.key(27, exited=True)
        assert not self.device.commands or all(command[1] not in (3, 5, 0x11, 0x23, 0x24, 0x25, 0x30, 0x31)
            or command[:2] == b'\x03\x05' for command in self.device.commands)
        assert self.device.paths == {1: b'/shell', 2: b'/browser'}
        assert not self.device.aborted


def info_body(target=4, identity='CONTROL TARGET V1.1', model='ULTIMATE-II+L'):
    return ['HARDWARE', model, '', f'TARGET {target}', identity]


def run():
    cases = []
    p = Panel(); p.check(info_body())
    assert p.device.commands == [b'\x04\x28\x00', b'\x04\x01']
    p.key(ord('?')); p.check(info_body())
    assert len(p.device.commands) == 2
    p.key(0x9d); p.check(info_body(3, 'ULTIMATE-II NETWORK INTERFACE V1.0'))
    for _ in range(3): p.key(0x9d)
    p.check(info_body(15, 'NO TARGET'))
    p.key(0x1d); p.check(info_body(1, 'ULTIMATE-II DOS V1.2'))
    p.exit(); cases.append('identification, bounded target navigation and unused target')

    p = Panel(); p.key(ord('D'))
    p.check(['ULTIMATE DRIVE INVENTORY', '', 'SLOT 1  TYPE 00  IEC 8  ON',
        'SLOT 2  TYPE 01  IEC 9  OFF', 'SLOT 3  TYPE 04  IEC 10  ON',
        'SLOT 4  TYPE 05  IEC 11  OFF', '', 'TYPES: 00=1541 01=1571 02=1581',
        'OTHER TYPE CODES SHOWN AS REPORTED.'])
    p.device.inventory = bytes([4, 0, 8, 1, 1, 9, 0]); p.key(ord('R'))
    p.check(['ULTIMATE DRIVE INVENTORY', '', 'PARTIAL REPLY: 2 OF 4 RECORDS', '',
        'SLOT 1  TYPE 00  IEC 8  ON', 'SLOT 2  TYPE 01  IEC 9  OFF', '',
        'TYPES: 00=1541 01=1571 02=1581', 'OTHER TYPE CODES SHOWN AS REPORTED.'])
    p.device.inventory = b'\0'; p.key(ord('R'))
    p.check(['ULTIMATE DRIVE INVENTORY', '', 'NO DRIVE RECORDS'])
    p.exit(); cases.append('complete, explicitly partial and empty drive inventory')

    for payload in (b'', bytes([5]), bytes([2, 0, 8, 1]), bytes([4, 0, 8, 1]),
                    bytes([1, 0, 31, 1]), bytes([1, 0, 8, 2]), bytes(257)):
        p = Panel(); p.device.inventory = payload; p.key(ord('D'))
        assert p.value('uc_error') == 9 and not p.value('uc_valid')
        p.check(['ULTIMATE DRIVE INVENTORY', '', 'UNAVAILABLE: 09  DOS 00  LINK 00',
            'INVALID REPLY; R RETRIES THE QUERY.'])
        p.exit()
    cases.append('seven malformed inventories hide stale records')

    p = Panel(); p.key(ord('N'))
    network = ['NETWORK INTERFACES: 2', 'INTERFACE 0', '', 'IP:      192.168.1.194',
        'MASK:    255.255.255.0', 'GATEWAY: 192.168.1.1', '',
        'CONFIGURED ADDRESSES; LINK UNTESTED.']
    p.check(network)
    p.key(0x1d)
    p.check(['NETWORK INTERFACES: 2', 'INTERFACE 1', '', 'IP:      0.0.0.0',
        'MASK:    0.0.0.0', 'GATEWAY: 0.0.0.0', '', 'CONFIGURED ADDRESSES; LINK UNTESTED.'])
    p.key(0x1d); p.check(network)
    p.key(0x9d); assert p.value('uc_interface') == 1
    p.device.interfaces = 1; p.key(ord('R')); assert p.value('uc_interface') == 0
    p.device.interfaces = 0; p.key(ord('R'))
    p.check(['NETWORK INTERFACES: 0', 'NO INTERFACES AVAILABLE'])
    before = len(p.device.commands); p.key(0x1d); assert len(p.device.commands) == before
    p.exit(); cases.append('network addresses, interface wrap, removal and no interfaces')

    for command, payload in ((b'\x03\x02', b''), (b'\x03\x02', b'\x01\0'),
            (b'\x03\x05\0', bytes(11)), (b'\x03\x05\0', bytes(13))):
        p = Panel(); p.device.faults[command] = [(payload, b'00,OK')]; p.key(ord('N'))
        assert p.value('uc_error') == 9 and not p.value('uc_valid')
        p.exit()
    cases.append('network lengths checked before interpreting addresses')

    p = Panel(); p.key(ord('T'))
    p.check(['CARTRIDGE RTC', '', '2026/09/12 13:00:00', 'S SET TIME  R REFRESH CLOCK READING.'])
    for valid in (b'2000/02/29 23:59:59', b'2024/02/29 00:00:00', b'2100/02/28 00:00:00',
                  b'2026/04/30 01:02:03', b'2026/12/31 23:59:59'):
        p.device.time = valid; p.key(ord('R'))
        assert p.value('uc_error') == 0 and p.value('uc_valid') == 1
    for invalid in (b'', b'2026/09/12 13:00:00\0', b'2026-09/12 13:00:00',
            b'2026/00/12 13:00:00', b'2026/13/12 13:00:00', b'2026/04/31 13:00:00',
            b'2026/02/29 13:00:00', b'2100/02/29 13:00:00', b'2200/02/29 13:00:00',
            b'2026/09/00 13:00:00', b'2026/09/12 24:00:00', b'2026/09/12 13:60:00',
            b'2026/09/12 13:00:60', b'2026/09/12 1A:00:00'):
        p.device.time = invalid; p.key(ord('R'))
        assert p.value('uc_error') == 9 and not p.value('uc_valid'), invalid
        p.check(['CARTRIDGE RTC', '', 'UNAVAILABLE: 09  DOS 00  LINK 00',
            'INVALID REPLY; R RETRIES THE QUERY.'])
    p.exit(); cases.append('RTC snapshots, refresh, leap years, field and calendar validation')

    p = Panel(lambda d: setattr(d, 'present', False))
    p.check(['HARDWARE', 'UNAVAILABLE', '', 'TARGET 4', 'UNAVAILABLE: 11  DOS 00  LINK FE', ''])
    assert not p.device.commands
    p.device.present = True; p.key(ord('R')); p.check(info_body())
    p.device.faults[b'\x04\x29\x01'] = [(b'OLD DATA', b'99,NOT IMPLEMENTED')]
    p.key(ord('D'))
    p.check(['ULTIMATE DRIVE INVENTORY', '', 'UNAVAILABLE: 11  DOS 63  LINK 00', '99,NOT IMPLEMENTED'])
    assert not p.value('uc_valid')
    p.exit(); cases.append('absent interface, refresh recovery and unsupported command')

    p = Panel(lambda d: setattr(d, 'model', b'A'*80))
    p.check(['HARDWARE', 'A'*36, '...', '', 'TARGET 4', 'CONTROL TARGET V1.1'])
    p.device.identities[4] = b'B'*200; p.key(ord('R'))
    p.check(['HARDWARE', 'A'*36, '...', '', 'TARGET 4']+['B'*36]*4+['...'])
    p.device.identities[4] = b'a\x93b\xffc'; p.key(ord('R'))
    p.check(['HARDWARE', 'A'*36, '...', '', 'TARGET 4', 'A.B.C'])
    p.device.model = b'A'*36+b'\0'; p.device.identities[4] = b'B'*144+b'\0'; p.key(ord('R'))
    p.check(['HARDWARE', 'A'*36, '', 'TARGET 4']+['B'*36]*4)
    p.exit(); cases.append('bounded multiline identification and control-byte sanitizing')
    return cases


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    report = dict(passed=False, physical_hardware_io=False,
        panel_sha256=hashlib.sha256((ROOT/'target/native-desktop/controls.prg').read_bytes()).hexdigest())
    try:
        report['cases'] = run(); report['passed'] = True
        print(f"PASS: {len(report['cases'])} complete Ultimate-panel workflows")
    except BaseException as error:
        report['error'] = str(error); raise
    finally:
        args.report.write_text(json.dumps(report, indent=2)+'\n')
