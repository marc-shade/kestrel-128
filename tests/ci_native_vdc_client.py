#!/usr/bin/env python3
"""App-level VDC component loading from the original source and clean refusals."""
import argparse
import json
from pathlib import Path

from ci_native_vdc_calc import Calculator,calc,heap
from ci_native_vdc_desktop import Desktop,VDCBus

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--group',choices=('all','source','fault'),default='all')
    parser.add_argument('--app',choices=('both','desktop','calc'),default='both')
    args=parser.parse_args();report=dict(passed=False,physical_hardware_io=False,cases=[])
    original_bus,original_machine,original_stream=heap.Bus,calc.Machine,calc.StreamIEC
    image=(ROOT/'target/native-desktop/vdsvc.prg').read_bytes()
    try:
        for kind,cls in (('desktop',Desktop),('calc',Calculator)):
            if args.app not in ('both',kind):continue
            def start(**kwargs):
                heap.Bus=type('Bus',(VDCBus,),dict(size=64))
                return cls(**kwargs)
            def check(p):
                if kind=='desktop':p.check(0)
                else:p.check()
            def done(name,p):
                p.key(27,exited=True);p.restored()
                report['cases'].append(dict(app=kind,name=name,instructions=p.instructions,keys=p.events))
                print('PASS:',kind,name,flush=True)
            if args.group in ('all','source'):
                for fmt in (0,1,2):
                    p=start(fmt=fmt);check(p)
                    assert p.value('bk_state')==2 and not p.value('bk_file') and not p.io.handles
                    done('IEC component and complete graphics, format '+str(fmt),p)
                p=start(device=9,fmt=2);check(p)
                assert p.ram[0x3d29:0x3d2b]==bytes([9,2])
                assert not p.io.handles and p.value('bk_state')==2
                done('original device 8 component with device 9 D81 data preferences',p)
                for context in (1,2):
                    path=b'/Usb0/My Apps/LOCALAPP'
                    p=start(source_path=path,source_context=context);check(p)
                    assert not any(p.ultimate.handles.values()) and not p.io.handles
                    assert p.value('bk_state')==2
                    done('Ultimate component beside original app, context '+str(context),p)
            if args.group in ('all','fault'):
                corrupt=bytearray(image);corrupt[-1]^=1
                for name,component in (('missing component',False),('damaged component CRC',corrupt)):
                    p=start(vdc_component=component)
                    assert p.value('vd_phase')==p.value('vd_live')==p.value('bk_state')==p.value('bp_started')==0
                    assert p.value('vd_fault') and p.bus.original is None
                    assert not p.io.handles
                    expected=426-p.image[12]-36-(2 if kind=='calc' else 0)
                    assert sum(p.m.stats()[:2])==expected
                    p.key(9)
                    done(name+' leaves input live and no component allocation',p)
                path=b'/'+b'A'*246+b'/APP'
                p=start(source_path=path)
                assert p.value('vd_phase')==p.value('bk_state')==0 and p.value('vd_fault')==1
                assert p.bus.original is None and not any(p.ultimate.handles.values())
                done('component path beyond 255 bytes is refused before VDC ownership',p)
                # Leave the Calculator's two history pages, but no room at the
                # component's fixed executable extent. No VDC state may be touched.
                class Occupied(original_machine):
                    def __init__(self):
                        super().__init__()
                        first=6 if kind=='calc' else 4
                        self.foreign=self.alloc(0xff-first,1,77,page=first)
                calc.Machine=Occupied
                try:p=start()
                finally:calc.Machine=original_machine
                assert p.value('vd_phase')==p.value('bk_state')==0 and p.value('vd_fault')
                assert p.bus.original is None and not p.io.handles
                stack=bytes(p.ram[0x100:0x200]);p.m.select(p.m.foreign,77);p.m.invoke('free')
                p.ram[0x100:0x200]=stack
                done('occupied bank-1 code region leaves VIC/text controls usable',p)

                class UncertainClose(original_stream):
                    def stub(self,cpu):
                        closing=self.handles.get(cpu.a) if cpu.pc==0xffc3 else None
                        if closing and closing.get('key')==(8,b'VDSVC.PRG',b'P'):
                            self.fail_close=cpu.a
                        try:return super().stub(cpu)
                        finally:self.fail_close=None
                calc.StreamIEC=UncertainClose
                try:p=start()
                finally:calc.StreamIEC=original_stream
                assert p.value('bk_state')==p.value('vd_phase')==1
                assert p.value('bp_started')==p.value('vd_live')==0 and p.value('vd_fault')==17
                assert p.bus.original is None and not p.io.handles
                file_slot=p.value('bk_file');assert 1<=file_slot<=2
                record=0x3dc0+(file_slot-1)*16
                assert p.ram[record]==32 and p.ram[record+3]&4
                code=p.value('bk_handle');assert code and p.ram[0x3c00+(code-1)*8]==32
                owned=p.m.stats();events=len(p.io.events)
                for _ in range(2):
                    p.key(27)
                    assert p.value('bk_state')==p.value('vd_phase')==1
                    assert p.ram[0x3d20]==32 and p.m.stats()==owned and len(p.io.events)==events
                name='uncertain component close retains file, code and app ownership; repeated exits issue no I/O'
                report['cases'].append(dict(app=kind,name=name,instructions=p.instructions,keys=p.events))
                print('PASS:',kind,name,flush=True)
        report['passed']=True
    finally:
        heap.Bus,calc.Machine,calc.StreamIEC=original_bus,original_machine,original_stream
        args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
