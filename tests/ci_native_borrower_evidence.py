#!/usr/bin/env python3
"""Fault the host readback and require exact retained borrower differences."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_capture import NativeCapture

REGIONS = dict(output=(0x3a00,512,17),scratch=(0x3e00,512,23),
               metadata=(0x3800,1536,1024),resident=(0x1300,2304,43))


class Monitor:
    def __init__(self, fault=None, short=None):
        self.ram = bytearray((i*37+83)&255 for i in range(65536))
        self.ram[0x1c13:0x1c19] = b'KES128'
        self.ram[0x3d11:0x3d13] = b'\0\1'
        self.ram[0xd0] = self.ram[0x3d91] = 0
        self.ram[0x314:0x316] = b'\x65\xfa'
        self.faults = set(fault if isinstance(fault,tuple) else [fault] if fault else [])
        self.short = short; self.completed = self.restoring = False
        self.injected = set()

    def read_mem(self, start, end):
        data = bytearray(self.ram[start:end+1])
        if self.restoring:
            for fault in self.faults-self.injected:
                address, count, offset = REGIONS[fault]
                if start == address and len(data) == count:
                    data[offset] ^= 0x80
                    self.injected.add(fault)
                    break
            if self.short:
                address,count,_ = REGIONS[self.short]
                if start == address and len(data) == count:
                    self.injected.add(self.short)
                    return bytes(data[:-1])
        return bytes(data)

    def write_mem(self, start, data):
        self.ram[start:start+len(data)] = data
        if start == 0x314 and data == b'\0\x3e':
            # Only model the host/probe exchange here; CPU instructions are
            # executed separately by the VICE preflight.
            command = self.ram[0x3ff0:0x4000]
            address = int.from_bytes(command[5:7], 'little')
            count = int.from_bytes(command[7:9], 'little')
            self.ram[0x3a00:0x3a00+count] = self.ram[address:address+count]
            self.ram[0x3ff2] = 1
            self.ram[0x3ffb:0x3ffe] = bytes([0x37,4,0x0e])
            self.ram[0x314:0x316] = command[:2]
            self.completed = True
        if start == 0x3e00 and len(data) == 512 and self.completed:
            self.restoring = True

    def resume(self):
        pass


parser = argparse.ArgumentParser()
parser.add_argument('--report', type=Path, required=True)
args = parser.parse_args()
report = dict(passed=False, physical_hardware_io=False, probe_instructions_executed=False, cases=[])
for fault,short in [(x,None) for x in (None,*REGIONS,('metadata','resident'))]+[(None,'resident')]:
    with tempfile.TemporaryDirectory(prefix='kestrel-borrower-host-fault-') as temporary:
        work = Path(temporary); mon = Monitor(fault,short)
        faulty = mon.faults | ({short} if short else set())
        initial = bytes(mon.ram)
        capture = NativeCapture(mon,work,quiet=0)
        try:
            data = capture.capture('sample',address=0x6000,count=32)
        except AssertionError as error:
            assert faulty and mon.injected == faulty
            message = str(error)
        else:
            assert not faulty and data == initial[0x6000:0x6020]
            message = None
        row = capture.records[0]
        assert row['restored'] == (not faulty)
        assert {item['region'] for item in row['borrower_failures']} == faulty
        assert mon.ram[0x314:0x316] == initial[0x314:0x316]
        # The injected bad read did not alter actual RAM. The observer must
        # still fail and retain what it observed, without treating it as proof
        # of a RAM fault or accepting a subsequent matching reread.
        for name,(address,count,offset) in REGIONS.items():
            assert mon.ram[address:address+count] == initial[address:address+count]
            record = row['borrower_checks'][name]
            before = (work/record['before_file']).read_bytes()
            assert before == initial[address:address+count]
            assert hashlib.sha256(before).hexdigest() == record['before_sha256']
            after = (work/record['after_file']).read_bytes()
            assert hashlib.sha256(after).hexdigest() == record['after_sha256']
            assert record['matches'] == (name not in faulty)
            assert record['different_offsets'] == ([offset] if name in mon.faults else [])
            assert record['observed_bytes'] == count-int(name==short)
            if name in mon.faults:
                assert after[offset] == before[offset]^0x80
                assert after[:offset]+after[offset+1:] == before[:offset]+before[offset+1:]
            elif name==short:assert after==before[:-1]
            else:assert after==before
        report['cases'].append(dict(fault=fault,short=short,failed=message is not None,error=message,
                                   retained_exact_observations=True,all_first_readbacks_retained=True,
                                   actual_borrowed_ram_restored=True))
report['passed'] = True
args.report.write_text(json.dumps(report,indent=2)+'\n')
print('PASS: good restoration, four region faults, simultaneous faults and a short read retain every first readback; no failure accepted')
