#!/usr/bin/env python3
"""Cold native boots, actual REC DMA and independent whole-REU VICE snapshots."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time

import vice_harness as ci

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from native_image import seal
from native_reu_check import initial_memory,snapshot
from native_capture_transport import PausedViceMonitor


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sizes',type=int,nargs='+',default=[128,256,512,1024,2048,4096,8192,16384])
    parser.add_argument('--report',type=Path,required=True)
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix='kestrel-reu-vice-'))
    print('REU VICE evidence:',work,flush=True)
    subprocess.run(['64tass','-a','-B',str(ROOT/'tests/fixtures/native-reu-app.asm'),
                    '-o',str(work/'check.prg'),'-l',str(work/'check.sym')],check=True,capture_output=True)
    app = seal((work/'check.prg').read_bytes()); (work/'check.prg').write_bytes(app)
    symbols = {m[1]:int(m[2],16) for m in re.finditer(r'^(\w+)\s*=\s*\$([a-fA-F0-9]+)$',
                                                    (work/'check.sym').read_text(),re.M)}
    report = dict(passed=False,physical_hardware_io=False,work=str(work),cases=[],
                  fixture_sha256=hashlib.sha256(app).hexdigest())
    for kib in args.sizes:
        case = dict(kib=kib,passed=False,operations=[],snapshots=[])
        report['cases'].append(case)
        folder = work/str(kib); folder.mkdir()
        disk = folder/'test.d64'; shutil.copy2(ROOT/'target/native/kestrel.d64',disk)
        subprocess.run(['c1541','-attach',str(disk),'-delete','calc','-write',str(work/'check.prg'),'calc'],
                       check=True,capture_output=True)
        original = initial_memory(kib); expected = bytearray(original)
        reu = folder/'initial.reu'; reu.write_bytes(original)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0)); port = sock.getsockname()[1]
        xv = ci.cbm.Xvfb(); log = (folder/'vice.log').open('w'); mon = None
        command = ['x128','-default','-8',str(disk),'-drive8true','-drive8type','1541',
                   '-reu','-reusize',str(kib),'-reuimage',str(reu),'+reuimagerw',
                   '-sounddev','dummy','-jamaction','0','-warp',
                   '-binarymonitor','-binarymonitoraddress',f'ip4://127.0.0.1:{port}']
        case['command'] = command
        emu = subprocess.Popen(command,env=dict(os.environ,DISPLAY=xv.display,
                              __EGL_VENDOR_LIBRARY_FILENAMES=ci.cbm.MESA_EGL),stdout=log,stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic()+30
            while mon is None:
                assert emu.poll() is None
                try: mon = ci.Monitor(port=port)
                except OSError:
                    assert time.monotonic() < deadline
                    time.sleep(.1)
            banks = mon.banks(); mon.resume(); paused = PausedViceMonitor(mon)
            def read(at,n=1):
                result = bytes(paused.read_mem(at,at+n-1,bank=banks['ram00']))
                paused.resume(); return result
            def write(at,data):
                paused.write_mem(at,data); paused.resume()
            def wait(predicate,label,seconds=90):
                deadline = time.monotonic()+seconds
                while time.monotonic() < deadline:
                    if predicate(): return
                    assert emu.poll() is None
                    time.sleep(.03)
                raise AssertionError(label)
            def ready(): return read(0x3d12) == b'\1' and read(0xd0) == b'\0'
            def key(value):
                wait(ready,'input ready')
                before = int.from_bytes(read(0x3d13,2),'little')
                with paused.paused('key'):
                    paused.write_mem(0x3d12,b'\0'); paused.write_mem(0x34a,bytes([value])); paused.write_mem(0xd0,b'\1')
                wait(lambda: int.from_bytes(read(0x3d13,2),'little') == before+1 and ready(),'key completed')
            wait(lambda:read(0x1c13,6)==b'KES128' and ready(),'native boot')
            key(ord('C'))
            assert read(0x3d60,32) == app[2:34] and read(0x3d20,4) == bytes([32,8,4,2])
            def set_arg(name,value,size=1):
                write(symbols['ru_'+name],value.to_bytes(size,'little'))
            def get_arg(name,size=1): return int.from_bytes(read(symbols['ru_'+name],size),'little')
            def call(name,error=0,flags=0):
                names = ['open','close','alloc','reserve','free','read','write','stats','release']
                serial = read(symbols['check_serial'])[0]
                write(symbols['check_operation'],bytes([names.index(name),flags]))
                key(32)
                status = read(symbols['check_result'],3)
                assert status[0] == error and status[1]&1 == bool(error), (name,status.hex(),error)
                assert status[1]&12 == flags&12 and status[2] == (serial+1)&255
                case['operations'].append(dict(name=name,error=error,flags=flags,actual=get_arg('actual',2)))
            def check_snapshot(label):
                with paused.paused(label):
                    memory,info = snapshot(mon,folder/(label+'.vsf'))
                assert memory == expected, (label,'whole REU comparison')
                case['snapshots'].append(info)
            # Change the VIC/DMA bank and CPU speed before calling the library.
            # The wrapper must restore both; DMA must still select physical bank 0.
            mmu_before = bytes(mon.read_mem(0xd506,0xd506)); mon.resume()
            speed_before = bytes(mon.read_mem(0xd030,0xd030)); mon.resume()
            write(0xd506,bytes([mmu_before[0]|64])); write(0xd030,bytes([speed_before[0]|1]))
            bank1 = bytes(mon.read_mem(0x400,0xfeff,bank=banks['ram01'])); mon.resume()
            call('open',flags=8)
            assert get_arg('total',2) == kib//4
            check_snapshot('probe-restored')
            set_arg('pages',kib//4,2); call('alloc'); token = get_arg('handle',8)
            for offset,count in ((0,512),(0xff80,512),(kib*1024-512,512)):
                data = bytes((i*51+(i>>3)*7+(offset>>16))&255 for i in range(count))
                set_arg('offset',offset,3); set_arg('count',count,2)
                write(0x3a00,data); call('write',flags=12)
                expected[offset:offset+count] = data
                write(0x3a00,bytes(count)); call('read',flags=8)
                assert read(0x3a00,count) == data and get_arg('actual',2) == count
            if kib >= 1024:
                offset,count = 0x7ff80,512
                data = bytes((i*93+61)&255 for i in range(count))
                set_arg('offset',offset,3); set_arg('count',count,2)
                write(0x3a00,data); call('write'); expected[offset:offset+count] = data
                write(0x3a00,bytes(count)); call('read'); assert read(0x3a00,count) == data
            set_arg('offset',kib*1024-1,3); set_arg('count',2,2); call('write',6)
            assert get_arg('actual',2) == 0
            call('free'); call('free',4); call('stats')
            assert get_arg('available',2) == kib//4 and get_arg('slots') == 32
            call('close'); call('open'); set_arg('pages',1,2); call('alloc')
            newer = get_arg('handle',8); assert token != newer
            set_arg('handle',token,8); call('free',4)
            set_arg('handle',newer,8); call('free'); call('close')
            check_snapshot('transfers-and-lifetimes')
            assert bytes(mon.read_mem(0x400,0xfeff,bank=banks['ram01'])) == bank1; mon.resume()
            assert bytes(mon.read_mem(0xd506,0xd506)) == bytes([mmu_before[0]|64]); mon.resume()
            assert bytes(mon.read_mem(0xd030,0xd030)) == bytes([speed_before[0]|1]); mon.resume()
            write(0xd506,mmu_before); write(0xd030,speed_before)
            key(27)
            assert read(0x3d20) == b'\0' and read(0x3d0e,3) == bytes([175,251,32])
            case['passed'] = True
            print('PASS:',kib,'KiB actual DMA, all REU bytes, bank-1 guard, D/I and owner lifetimes',flush=True)
        finally:
            args.report.write_text(json.dumps(report,indent=2)+'\n')
            if mon: mon.quit_emulator()
            else: emu.terminate()
            emu.wait(timeout=15); xv.stop(); log.close()
    report['passed'] = True
    args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__ == '__main__': main()
