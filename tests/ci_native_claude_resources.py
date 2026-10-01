#!/usr/bin/env python3
"""Claude component/model refusals and REU snapshot ownership."""
import argparse
import json
from pathlib import Path

import ci_native_claude as terminal
import ci_native_calc as calc
from ci_native_claude_gui import GraphicalClient
from ci_native_claude_vdc import Claude,TerminalVDC,heap

ROOT=Path(__file__).resolve().parents[1]


def run(case,size,kib):
    rows=[]
    def done(name,c,**extra):
        rows.append(dict(name=name,passed=True,instructions=c.instructions,keys=c.events,**extra))
        print('PASS:',name,flush=True)
    heap.Bus=type('PhysicalVDC',(TerminalVDC,),dict(size=size))
    if case=='fallback':
        corrupt=bytearray((ROOT/'target/native-desktop/vdsvc.prg').read_bytes());corrupt[-1]^=1
        for name,provider in (('missing',False),('bad CRC',corrupt)):
            c=Claude(vdc_component=provider);c.check()
            assert not c.value('cg_vdc_owned') and not c.value('bk_state') and not c.io.handles
            c.key(13);c.key(255);c.check()
            c.feed(bytes([3,24,79,15,1,65,5]));c.check();assert c.terminal()[0][-1:]==b'A'
            c.key(27);c.close();c.restored()
            done(name+' display service leaves VIC controls and complete text terminal usable',c)

        original=terminal.TerminalMachine
        class OccupiedFont(original):
            def __init__(self):
                # Leave the packer's four transient pages at $5000 available.
                # The last font page still prevents Claude's 16-page reserve.
                super().__init__();self.foreign=self.alloc(1,0,77,page=0x5f)
                self.saved=bytes(self.ram[0x5f00:0x6000])
        terminal.TerminalMachine=OccupiedFont
        try:c=Claude()
        finally:terminal.TerminalMachine=original
        GraphicalClient.check(c)
        assert not c.value('_tm_live') and not c.value('cg_font_ram') and c.value('_tm_error')==2
        assert not c.value('cg_vdc_owned') and not c.value('bk_state')
        c.key(13);c.feed(bytes([3,24,79,15,1,65,5]))
        assert c.bus.bytes(1999,1)==b'A' and bytes(c.ram[0x5f00:0x6000])==c.m.saved
        GraphicalClient.check(c)
        stack=bytes(c.ram[0x100:0x200]);c.m.select(c.m.foreign,77);c.m.invoke('free')
        c.ram[0x100:0x200]=stack;c.close();c.restored()
        done('foreign font allocation is preserved; clean model refusal retains the original terminal',c)

        class OccupiedBank(original):
            def __init__(self):
                super().__init__();self.foreign=self.alloc(251,1,77,page=4)
                self.saved=bytes(self.bus.ram[1][0x400:0xff00])
        terminal.TerminalMachine=OccupiedBank
        try:c=Claude()
        finally:terminal.TerminalMachine=original
        assert c.value('_tm_error')==2 and not c.value('_tm_live') and not c.value('tm_font')
        assert not c.value('tm_cells') and not c.value('cg_vdc_owned')
        GraphicalClient.check(c);c.key(13);c.feed(bytes([3,24,79,15,1,66,5]))
        assert c.bus.bytes(1999,1)==b'B' and bytes(c.bus.ram[1][0x400:0xff00])==c.m.saved
        stack=bytes(c.ram[0x100:0x200]);c.m.select(c.m.foreign,77);c.m.invoke('free')
        c.ram[0x100:0x200]=stack;c.close();c.restored()
        done('cell-allocation refusal releases the new font and preserves a full foreign bank',c)
    elif case=='source-close':
        original=calc.StreamIEC
        class UncertainClose(original):
            def stub(self,cpu):
                closing=self.handles.get(cpu.a) if cpu.pc==0xffc3 else None
                if closing and closing.get('key')==(8,b'VDSVC.PRG',b'P'):self.fail_close=cpu.a
                try:return super().stub(cpu)
                finally:self.fail_close=None
        calc.StreamIEC=UncertainClose
        try:c=Claude()
        finally:calc.StreamIEC=original
        assert c.value('bk_state')==c.value('vd_phase')==1
        assert c.value('cg_recovery') and c.value('cg_vdc_owned') and not c.value('vd_live')
        slot=c.value('bk_file');assert 1<=slot<=2
        record=0x3dc0+(slot-1)*16
        assert c.ram[record]==32 and c.ram[record+3]&4
        retained=c.m.stats();events=len(c.io.events)
        for key in (13,27,0x8c,27):
            c.key(key)
            assert c.m.stats()==retained and len(c.io.events)==events and not c.chip.serial_writes
            assert c.value('cg_keys_owned') and c.value('_tm_live') and c.value('cg_vdc_owned')
        done('uncertain source CLOSE retains file, component, controls and terminal; retries issue no new I/O',c,
             retained_until_external_recovery=True)
    elif case=='startup':
        heap.Bus=type('AbsentVDC',(TerminalVDC,),dict(size=size,present=False))
        c=Claude.__new__(Claude)
        try:c.__init__()
        except AssertionError as error:assert str(error)=='unexpected app exit',repr(error)
        else:raise AssertionError('absent VDC must return its bounded startup error')
        c.chip=c.m.bus;c.bus=c.chip.parent
        assert (c.cpu.pc,c.cpu.sp)==(0xb00,0xe0)
        assert c.ram[0x3d20]==0 and c.ram[0x3d23:0x3d25]==b'\0\10'
        assert c.m.stats()==(175,251,32) and not c.io.handles and not c.chip.serial_writes
        c.check_restored()
        done('absent VDC returns N_PLATFORM after a bounded wait and restores keys, mapping and all pages',c)
    elif case=='font':
        for operation,entry in (('read',0x1c26),('free',0x1c23)):
            c=Claude();c.key(13);c.check()
            token=bytes(c.ram[c.symbol('sf_token'):c.symbol('sf_token')+4])
            original=c.cpu.step;failed=[]
            def step():
                if c.cpu.pc==entry and bytes(c.ram[0x3d04:0x3d08])==token:
                    failed.append(c.cpu.pc);c.cpu.pc=(c.cpu.stPopWord()+1)&65535
                    c.cpu.a=9;c.cpu.p|=1;return
                original()
            c.cpu.step=step
            try:
                c.feed(bytes([9,0x5a]))
                assert c.value('cg_retiring') and c.value('cg_recovery') and not c.value('serialOwned')
                assert bytes(c.ram[c.symbol('sf_token'):c.symbol('sf_token')+4])==token
                retained=c.m.stats();c.key(27);assert c.m.stats()==retained
            finally:c.cpu.step=original
            assert failed
            c.key(27,exited=True);c.restored()
            done('original-font '+operation+' refusal retains its token and retries without stale reads',c)
    elif case=='reu':
        from native_reu_bus import REUBusMixin
        from ci_native_reu_calc import PROBE,component,COMPONENT_PAGES
        class REUTerminal(REUBusMixin,TerminalVDC):
            reu_configs=(0x0e,0x4e)
            def __init__(self):
                super().__init__();self.reu_bank1_hosts.append((PROBE,PROBE+2))
                self.reu_original=bytes(self.reu_ram)
        heap.Bus=type('ConfiguredREU',(REUTerminal,),dict(size=size,reu_kib=kib))
        c=Claude();c.check();assert c.value('vs_reu')==c.value('ru_active')==1
        pages=c.value('vd_pages');token=bytes(c.ram[c.symbol('vs_token'):c.symbol('vs_token')+8])
        assert component(c,'vs_token',8)==token and component(c,'ru_cookie',4)==token[4:]
        assert c.bus.reu_ram[pages*256:]==c.bus.reu_original[pages*256:]
        assert sum(c.m.stats()[:2])==426-c.image[12]-36-16-16-16-COMPONENT_PAGES
        c.key(13);c.check();c.key(255);c.check()
        c.feed(bytes([3,24,79,15,1,65,5]));c.check();assert c.terminal()[0][-1:]==b'A'
        # The serial receiver stays owned while failed screen reads are retried.
        c.bus.reu_fault_from=len(c.bus.reu_transactions)+1;c.key(27)
        assert c.value('cg_recovery') and c.value('cg_vdc_owned')
        retained=c.m.stats();c.key(27);assert c.m.stats()==retained and c.value('serialOwned')
        c.bus.reu_fault_from=None;c.key(27);c.check();c.close();c.restored()
        assert c.bus.reu_ram[pages*256:]==c.bus.reu_original[pages*256:]
        done(f'{size} KiB VDC / {kib} KiB REU: graphics reopen, live terminal, retained DMA fault and exact cleanup',c,
             dmas=len(c.bus.reu_transactions),snapshot_pages=pages)
    return rows


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=('fallback','source-close','startup','reu','font'),required=True)
    parser.add_argument('--size',type=int,choices=(16,64),default=64)
    parser.add_argument('--reu-kib',type=int,choices=(128,512,16384),default=512)
    parser.add_argument('--report',type=Path,required=True);args=parser.parse_args()
    result=dict(passed=False,physical_hardware_io=False,vdc_kib=args.size,reu_kib=args.reu_kib)
    try:result['cases']=run(args.case,args.size,args.reu_kib);result['passed']=True
    except BaseException as error:result['error']=repr(error);raise
    finally:args.report.write_text(json.dumps(result,indent=2)+'\n')
