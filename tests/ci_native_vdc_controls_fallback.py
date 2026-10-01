#!/usr/bin/env python3
"""Ultimate display refusal and picker scratch pressure retain usable controls."""
import argparse
import json
from pathlib import Path
import ci_native_calc as calc
from ci_native_vdc_controls import Panel, GraphicalPanel, heap, VDCBus


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--group',choices=('all','setup','surface','memory'),default='all')
    args=parser.parse_args();original_bus,original_stream=heap.Bus,calc.StreamIEC
    report=dict(passed=False,physical_hardware_io=False,cases=[])

    def start(**options):
        heap.Bus=type('FallbackVDC',(VDCBus,),options)
        return Panel()

    def done(name,p):
        report['cases'].append(dict(name=name,passed=True,instructions=p.instructions,keys=p.events))
        args.report.write_text(json.dumps(report,indent=2)+'\n')
        print('PASS:',name,flush=True)

    try:
        for absent in (('hardware','component','corrupt') if args.group in ('all','setup') else ()):
            class Source(original_stream):
                def stub(self,cpu):
                    if not getattr(self,'altered',False):
                        name=(8,b'VDSVC.PRG',b'P')
                        if absent=='component':self.files.pop(name,None)
                        if absent=='corrupt':
                            data=bytearray(self.files[name]);data[-1]^=1;self.files[name]=data
                        self.altered=True
                    return super().stub(cpu)
            calc.StreamIEC=Source
            p=start(present=absent!='hardware')
            assert p.value('vd_phase')==p.value('bk_state')==0 and p.value('ug_bitmap')==1
            GraphicalPanel.check(p)
            assert p.bus.original is None and not p.bus.data_writes
            p.key(ord('D'));p.key(0x11);p.key(ord('E'));GraphicalPanel.check(p)
            p.key(27);p.key(27,exited=True);p.restored()
            done(absent+' refusal leaves VIC controls and both console fallback paths usable',p)
        calc.StreamIEC=original_stream

        if args.group in ('all','surface'):
            p=start();p.key(ord('D'));p.key(0x11);p.check()
            active=p.symbol('ug_picker_active');original=p.io.stub;injected=[]
            def bad_fill(cpu):
                if p.ram[active] and cpu.pc==0x1c2c and not injected:
                    p.ram[0x3d05]^=128;injected.append(True)
                return original(cpu)
            p.io.stub=bad_fill
            output=p.output;restored=[]
            def observe(value):
                if not restored and injected and p.ram[0xd7]&128:
                    assert p.bus.video_ram==p.bus.original[0], 'VDC restored before text fallback'
                    restored.append(True)
                output(value)
            p.output=observe
            p.key(ord('M'))
            assert injected and restored and p.value('ug_picker_active')
            assert p.value('vd_phase')==p.value('bk_state')==0
            assert not p.value('pg_bitmap') and not p.device.mutations
            p.io.stub=original
            p.key(27);GraphicalPanel.check(p)
            p.output=output
            p.bus.original=None      # Refresh starts a new lifetime over the current text screen
            p.key(ord('R'));p.check()
            p.key(27,exited=True);p.restored()
            done('failed picker surface restores the VDC before text fallback; Refresh reacquires graphics',p)
        if args.group in ('all','memory'):
            p=start();p.key(ord('D'));p.key(0x11);p.check()
            stack=bytes(p.ram[0x100:0x200])
            ranges=[(0x5b00,0x6000),(0x6000+p.image[12]*256,0xc000),(0xe400,0xff00)]
            handles=[p.m.alloc((end-start)//256,0,owner=77,page=start//256) for start,end in ranges if end>start]
            p.ram[0x100:0x200]=stack
            before=[bytes(p.ram[start:end]) for start,end in ranges]
            p.key(ord('M'));p.check()
            assert p.value('ug_notice')==12 and not p.value('ug_picker_active') and not p.value('ug_scratch_handle')
            assert before==[bytes(p.ram[start:end]) for start,end in ranges]
            assert not p.device.mutations
            stack=bytes(p.ram[0x100:0x200])
            for token in handles:p.m.select(token,77);p.m.invoke('free')
            p.ram[0x100:0x200]=stack
            p.key(ord('M'));assert p.value('ug_picker_active');p.mirror()
            p.key(27);p.check();assert not p.value('ug_scratch_handle')
            p.key(27,exited=True);p.restored()
            done('full bank-0 heap refuses the picker without foreign writes; retry succeeds after memory is freed',p)
        report['passed']=True
    finally:
        heap.Bus,calc.StreamIEC=original_bus,original_stream
        args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
