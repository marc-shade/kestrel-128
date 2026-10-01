#!/usr/bin/env python3
"""Execute native restart initialization with stale selection and directory state."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import ci_native_heap as heap
from native_display_bus import DisplayBus
from py65.devices.mpu6502 import MPU

parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True)
args=parser.parse_args()
report=dict(passed=False,physical_hardware_io=False,scope='real startup instructions through desktop/workspace dispatch; display and IEC boot verified separately in VICE',cases=[])
heap.Bus=DisplayBus
for prefix in ('native','native-desktop','native/d81','native-desktop/d81'):
    heap.IMAGE=ROOT/'target'/prefix/'kestrel.prg'
    for saved in (2,255):
        machine=heap.Machine();ram=machine.ram
        machine.bus.video[0xd030]=1
        ram[0x3d2f]=saved;ram[0x3d30:0x3d34]=bytes.fromhex('12345678')
        ram[0x3d13:0x3d15]=bytes.fromhex('ffff')
        boot_format=2 if prefix.endswith('/d81') else 0
        ram[0x3de4]=255;ram[0x3d2a]=3;ram[0x3d2c]=3
        ram[0xba]=8
        cpu=MPU(memory=machine.bus,pc=heap.symbol('native_start'));cpu.sp=0xf0;cpu.p=0x20
        target=heap.symbol('native_browser' if prefix.startswith('native-desktop') else 'native_draw')
        for steps in range(100000):
            if cpu.pc==target:break
            cpu.step()
        else:raise AssertionError('native restart did not reach dispatch')
        assert ram[0x3de4]==ram[0x3d2a]==ram[0x3d2c]==boot_format
        assert ram[0x3d21]==ram[0x3d29]==ram[0x3d2d]==8
        assert cpu.sp==0xf0 and machine.bus.config==0x0e
        assert ram[0x3d2f:0x3d34]==bytes(5)
        assert ram[0x3d13:0x3d15]==bytes(2) and ram[0x3d12]==0
        assert ram[0x3d2e]==1 and ram[0x4a00]==ord('/')
        assert ram[0x3d0e:0x3d11]==bytes([175,251,32])
        assert machine.bus.video[0xd030]==0
        report['cases'].append(dict(kernel=prefix,saved_selection=saved,reset_selection=0,
            browser_position_reset=True,keys_reset=True,free_pages=426,instructions=steps,
            boot_format=boot_format,
            kernel_sha256=hashlib.sha256(heap.IMAGE.read_bytes()).hexdigest()))
        # Workspace shortcuts must not borrow a data-volume or Ultimate format.
        for entry,target,name in [('native_browser','native_dispatch',b'BROWSE'),
                                  ('native_calculator','app_launch',b'CALC')]:
            ram[0x3d29:0x3d2b]=bytes([9,0]);ram[0x3d21]=1;ram[0x3d2c]=3
            cpu=MPU(memory=machine.bus,pc=heap.symbol(entry));cpu.sp=0xf0;cpu.p=0x20
            stop=heap.symbol(target)
            for _ in range(100):
                if cpu.pc==stop:break
                cpu.step()
            else:raise AssertionError(entry+' did not reach launch')
            assert ram[0x3d21]==8 and ram[0x3d2c]==ram[0x3de4]==boot_format
            assert ram[0x3d29:0x3d2b]==bytes([9,0])
            assert bytes(ram[0x3d40:0x3d40+ram[0x3d22]])==name
        # Execute both masked bank keys and the actual allocation/pattern paths.
        draw=heap.symbol('native_draw');workspace_steps=[]
        for bank in (0,1):
            for key in (str(bank+1),'a','w','v','f'):
                cpu=MPU(memory=machine.bus,pc=heap.symbol('native_key_counted'))
                cpu.sp=0xf0;cpu.p=0x20;cpu.a=ord(key)
                for steps in range(2000000):
                    if cpu.pc==draw:break
                    cpu.step()
                else:raise AssertionError(('workspace key did not return',key,hex(cpu.pc),ram[0x3d08:0x3d0a].hex()))
                workspace_steps.append(dict(bank=bank,key=key,instructions=steps))
                assert ram[heap.symbol('ui_bank')]==bank
                assert ram[heap.symbol('ui_status')]==0,(prefix,bank,key)
            assert machine.stats()==(175,251,32)
        report['cases'][-1].update(system_shortcuts=2,workspace_banks=[0,1],
            pattern_bytes_per_bank=8192,final_free_pages=426,workspace_steps=workspace_steps)
report['passed']=True;args.report.write_text(json.dumps(report,indent=2)+'\n')
print('PASS: eight D64/D81 restart cases, system-volume shortcuts and both workspace bank patterns')
