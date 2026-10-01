#!/usr/bin/env python3
"""Check accepted mappings and retain first raw bytes on rejected status/length."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ci_native_capture_transport import CpuExchange
from native_capture import NativeCapture
from native_capture_transport import PausedViceMonitor


class Exchange(CpuExchange):
    def __init__(self,field,value):
        super().__init__();self.field,self.value=field,value
    def resume(self):
        pending=self.pending;super().resume()
        if pending and self.field in ('code','mode','common','mmu'):
            at=dict(code=0x3ff2,mode=0x3ffb,common=0x3ffc,mmu=0x3ffd)[self.field]
            self.ram[at]=self.value
    def read_mem(self,start,end):
        data=super().read_mem(start,end)
        if self.starts and not self.restoring:
            if self.field=='short-status' and (start,end)==(0x3ff2,0x3ffd):return data[:-1]
            if self.field=='short-payload' and (start,end)==(0x3a00,0x3a1f):return data[:-1]
        return data


parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True)
args=parser.parse_args();report=dict(passed=False,physical_hardware_io=False,probe_instructions_executed=False,cases=[])
for field,value,accepted in (('mmu',14,True),('mmu',0,True),('mmu',1,False),('mmu',63,False),
        ('mmu',127,False),('mode',0x40,False),('common',5,False),('code',2,False),
        ('short-status',0,False),('short-payload',0,False)):
    with tempfile.TemporaryDirectory(prefix='kestrel-native-status-') as temporary:
        work=Path(temporary);cpu=Exchange(field,value);before=bytes(cpu.ram)
        mon=PausedViceMonitor(cpu);capture=NativeCapture(mon,work,quiet=0,batch=mon.paused)
        try:actual=capture.capture('sample',address=0xc7d0,count=32)
        except AssertionError:assert not accepted
        else:assert accepted and actual==before[0xc7d0:0xc7f0]
        row=capture.records[0];chunk=row['chunks'][0]
        status=(work/chunk['status_file']).read_bytes()
        assert hashlib.sha256(status).hexdigest()==chunk['status_sha256']
        assert len(status)==(11 if field=='short-status' else 12)
        if field!='short-status':
            payload=(work/chunk['payload_file']).read_bytes()
            assert hashlib.sha256(payload).hexdigest()==chunk['payload_sha256']
            size=31 if field=='short-payload' else 32
            assert payload==before[0xc7d0:0xc7d0+size] and chunk['payload_bytes']==size
            if field in ('code','mode','common','mmu'):
                offset=dict(code=0,mode=9,common=10,mmu=11)[field]
                assert status[offset]==value
        assert row['restored'] and not cpu.stopped and not mon.in_batch
        assert cpu.ram[0x3800:0x4000]==before[0x3800:0x4000]
        assert cpu.ram[0x1300:0x1c00]==before[0x1300:0x1c00]
        assert all(x['resume_acknowledged'] for x in mon.batches)
        assert (work/'sample.bin').exists()==accepted
        report['cases'].append(dict(field=field,value=value,accepted=accepted,raw_status_retained=True,
            raw_payload_retained=field!='short-status',restored=True))
report['passed']=True;args.report.write_text(json.dumps(report,indent=2)+'\n')
print('PASS: two supported mappings, eight rejected status/length cases, first raw bytes and exact restoration')
