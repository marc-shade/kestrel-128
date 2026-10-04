#!/usr/bin/env python3
"""Execute boot relocation, IRQ interleaving and reuse of the staging pages."""
import argparse
import hashlib
import json
from pathlib import Path

from py65.devices.mpu6502 import MPU
from ci_native_heap import Bus,Machine,ROOT,IMAGE,symbol,VALUE


def copy_case(flags,interrupts):
    bus=Bus();ram=bus.ram[0]
    start=symbol('native_low_start');end=symbol('native_low_padded_end')
    source=symbol('native_low_image');size=end-start
    expected=bytes(ram[source:source+size])
    ram[start:end]=b'\xa5'*size
    guards=bytes(ram[start-32:start]),bytes(ram[end:end+32])
    resident=bytes(ram[0x1c01:0x3e00]);other_bank=bytes(bus.ram[1])
    entries=[]
    for repeat in range(2):
        cpu=MPU(memory=bus,pc=symbol('native_relocate'));cpu.sp=0xe0;cpu.p=flags|0x20
        cpu.stPushWord(0xaff);attempts=0
        for steps in range(100000):
            if cpu.pc==0xb00 and cpu.sp==0xe0:break
            if interrupts and steps%43==0 and not cpu.p&4:
                cpu.irq();attempts+=1
            cpu.step()
        else:raise AssertionError('relocation did not return')
        assert bytes(ram[start:end])==expected
        assert guards==(bytes(ram[start-32:start]),bytes(ram[end:end+32]))
        assert bytes(ram[0x1c01:0x3e00])==resident and bytes(bus.ram[1])==other_bank
        assert cpu.p&12==flags&12 and bus.config==0x0e
        # Only the routine's own operands change outside the low section; it runs from staging.
        own=range(symbol('native_relocate'),symbol('native_keyboard_init'))
        assert not bus.io_reads and not bus.io_writes and all(bank==0 and address in own for bank,address,_ in bus.far_writes)
        entries.append(dict(instructions=steps,irq_attempts=attempts))
    return dict(bytes=size,runs=entries)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path);args=parser.parse_args()
    report=dict(passed=False,kernel_sha256=hashlib.sha256(IMAGE.read_bytes()).hexdigest(),cases={})
    try:
        layout=json.loads((ROOT/'target/native/layout.json').read_text())
        assert layout['low_start']==0x1300 and 0x1300<layout['low_end']<=layout['low_padded_end']<=0x1c00
        assert layout['main_end']<=0x3800 and 0x4000<layout['load_end']<=layout['staging_limit']==0x8000
        assert symbol('heap_enter')==0x1300 and 0x1300<=symbol('hbyte')<layout['low_end']
        assert layout['boot_start']<=symbol('heap_init')<symbol('sys_install')<layout['boot_end']
        for flags in (0,4,8,12):
            for interrupts in (False,True):
                report['cases'][f'flags-{flags}-irq-{interrupts}']=copy_case(flags,interrupts)
        # The system section: copied from staging to $0c00 with D/I preserved,
        # writing only $0c00..$0fff and the routine's own operands, IRQs or not.
        for flags in (0,4,8,12):
            for interrupts in (False,True):
                bus=Bus();ram=bus.ram[0];ram[0xc00:0x1000]=b'\x5a'*0x400
                image=bytes(ram[layout['sys_image_start']:layout['sys_image_start']+layout['sys_end']-layout['sys_start']])
                outside=bytes(ram[0x200:0xc00])+bytes(ram[0x1000:0x4000])
                cpu=MPU(memory=bus,pc=symbol('sys_install'));cpu.sp=0xe0;cpu.p=flags|0x20;cpu.stPushWord(0xaff)
                for steps in range(100000):
                    if cpu.pc==0xb00 and cpu.sp==0xe0:break
                    if interrupts and steps%43==0 and not cpu.p&4:cpu.irq()
                    cpu.step()
                else:raise AssertionError('sys_install did not return')
                assert bytes(ram[layout['sys_start']:layout['sys_end']])==image and cpu.p&12==flags&12
                assert bytes(ram[0x200:0xc00])[:0x900]==outside[:0x900] and bytes(ram[0x1000:0x4000])==outside[0xa00:]
                own=range(symbol('sys_install'),layout['boot_end'])
                assert all(bank==0 and address in own for bank,address,_ in bus.far_writes)
                report['cases'][f'system-section-flags-{flags}-irq-{interrupts}']=dict(bytes=len(image),instructions=steps)
        m=Machine();source=layout['staging_start']
        service=bytes(m.ram[0x4000:0x5000])
        reused=(layout['load_end']-source+255)//256*256
        m.ram[source:source+reused]=b'\xa5'*reused
        handle=m.alloc(reused//256,0,page=source//256);m.select(handle);m.set(VALUE,0x66)
        for offset in range(0,reused,512):m.transfer('fill',offset,min(512,reused-offset))
        assert m.ram[source:source+reused]==b'\x66'*reused
        assert bytes(m.ram[0x4000:0x5000])==service
        m.invoke('free');assert m.stats()==(175,251,32)
        report['cases']['staging-reused-by-heap']=dict(bytes=reused,all_pages_released=True)
        report.update(passed=True,layout=layout)
        print(f"PASS: {len(report['cases'])} relocation/IRQ/staging cases; public ABI and 426-page capacity retained",flush=True)
    except BaseException as error:report['error']=str(error);raise
    finally:
        if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
