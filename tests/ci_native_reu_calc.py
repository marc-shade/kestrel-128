#!/usr/bin/env python3
"""Real loaded Calculator with REU snapshots, RAM fallback and retained faults."""
import argparse
import hashlib
import json
from functools import lru_cache
from pathlib import Path

from ci_native_vdc_calc import Calculator, VDCBus, heap
from native_reu_bus import REUBusMixin
from hwlib import lst_symbol

ROOT = Path(__file__).resolve().parents[1]
PROBE = lst_symbol('native-desktop/vdsvc','ru_probe_data')
COMPONENT_HEADER = (ROOT/'target/native-desktop/vdsvc.prg').read_bytes()[2:34]
COMPONENT_PAGES = COMPONENT_HEADER[10]

@lru_cache(maxsize=None)
def component_symbol(name):return lst_symbol('native-desktop/vdsvc',name)

def component(p,name,count=1,*,released=False):
    at=component_symbol(name)
    assert 0x6020 <= at < at+count <= 0x6000+int.from_bytes(COMPONENT_HEADER[8:10],'little')
    if released:
        assert p.value('bk_state')==p.value('bk_handle')==0
    else:
        assert p.value('bk_state')==2 and p.value('bk_busy')==0
        token=bytes(p.ram[p.symbol('bk_handle'):p.symbol('bk_handle')+4])
        assert 1<=token[0]<=32
        offset=0x3c00+(token[0]-1)*8
        record=bytes(p.ram[offset:offset+8])
        assert record[:4]==bytes([32,1,0x60,COMPONENT_PAGES]) and record[4:7]==token[1:]
        assert p.ram[0x3960:0x3960+COMPONENT_PAGES]==bytes([token[0]])*COMPONENT_PAGES
        header=bytearray(p.bus.ram[1][0x6000:0x6020])
        assert int.from_bytes(header[22:24],'little')==p.symbol('bk_callback')
        header[22:24]=bytes(2);assert header==COMPONENT_HEADER
    return bytes(p.bus.ram[1][at:at+count])


class CalculatorBus(REUBusMixin,VDCBus):
    reu_configs = (0x0e,0x4e)
    fault_start = None

    def __init__(self):
        super().__init__()
        self.reu_bank1_hosts.append((PROBE,PROBE+2))
        self.reu_fault_from = self.fault_start
        self.reu_fault_prefix = 1
        self.reu_original = bytes(self.reu_ram)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report',type=Path,required=True)
    args = parser.parse_args()
    report = dict(passed=False,physical_hardware_io=False,cases=[],images={
        str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (ROOT/'target/native-desktop/calc.prg',heap.IMAGE)})
    def start(**options):
        heap.Bus = type('ConfiguredBus',(CalculatorBus,),options)
        return Calculator()
    def check_backing(p):
        p.check()
        assert p.value('vs_reu') == p.value('ru_active') == 1
        pages = p.value('vd_pages')
        assert p.bus.reu_ram[:pages*256] == p.bus.original[0][p.value('vd_base')*256:(p.value('vd_base')+pages)*256]
        assert p.bus.reu_ram[pages*256:] == p.bus.reu_original[pages*256:]
        token_at = p.symbol('vs_token'); token = p.ram[token_at:token_at+8]
        assert component(p,'vs_token',8)==token and 1<=token[0]<=32
        assert component(p,'ru_cookie',4)==token[4:]
        records = component(p,'ru_records',256)
        desc = (token[0]-1)*8
        assert records[desc] == 32 and int.from_bytes(records[desc+3:desc+5],'little') == (pages+15)//16
        assert records[desc+5:desc+8]==token[1:4]
        app_pages = p.image[12]
        f0,f1,slots = p.m.stats()
        assert f0+f1 == 426-app_pages-COMPONENT_PAGES-36-2 and slots == 28
    def done(name,p,**extra):
        report['cases'].append(dict(name=name,instructions=p.instructions,frames=p.frames,keys=p.events,
                                   dmas=len(p.bus.reu_transactions),**extra))
        print('PASS:',name,flush=True)
    try:
        for size,kib in ((16,128),(64,256),(16,512),(64,16384)):
            p = start(size=size,reu_kib=kib); check_backing(p)
            free = sum(p.m.stats()[:2])
            p.type('12+30='); p.frame(); p.move(288,168); check_backing(p)
            p.type('SRESULT'); p.key(13); check_backing(p)
            assert bytes(p.io.files[8,b'RESULT',b'S']) == b'42\r'
            p.key(27,exited=True); p.restored()
            assert p.value('ru_active') == p.value('vs_reu') == 0
            released=component(p,'ru_records',256,released=True)
            assert all(released[i] == 0 for i in range(0,256,8))
            done(f'{size} KiB VDC / {kib} KiB REU: snapshot, arithmetic, pointer, verified save, exact restoration',p,free_pages=free)

        p = start(size=64,reu_present=False); p.check()
        assert not p.value('vs_reu') and not p.bus.reu_transactions
        free = sum(p.m.stats()[:2])
        assert free == 426-p.image[12]-COMPONENT_PAGES-36-2-72
        p.key(27,exited=True); p.restored()
        done('absent REU retains exact main-RAM VDC backing and normal exit',p,free_pages=free)

        p = start(size=64); check_backing(p)
        p.bus.reu_fault_from = len(p.bus.reu_transactions)+1
        owned = p.m.stats(); sp = p.cpu.sp
        for _ in range(2):
            p.key(27)
            assert p.value('vd_phase') == 2 and p.value('vd_fault') == 17
            assert p.m.stats() == owned and p.cpu.sp == sp and p.ram[0x3d20] == 32
        p.bus.reu_fault_from = None
        p.key(27,exited=True); p.restored()
        done('failed REU snapshot reads retain the VDC and every owner; Escape retries restoration',p)

        p = start(size=16,fault_start=2)
        assert p.value('vd_phase') == 1 and p.value('ru_probe_live')
        assert p.value('vs_reu') and not p.value('vd_handle')
        owned = p.m.stats()
        p.key(27); assert p.m.stats() == owned and p.value('ru_probe_live')
        p.bus.reu_fault_from = None
        p.key(27,exited=True); p.restored()
        assert p.bus.reu_ram == p.bus.reu_original and not p.value('ru_probe_live')
        done('failed capacity-probe restoration remains owned through exit retries; every REU byte recovered',p)
        report['passed'] = True
    finally:
        args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__ == '__main__': main()
