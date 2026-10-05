#!/usr/bin/env python3
"""Cold-boot C128 bank-1 execution, native callbacks and complete REU snapshots."""
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
from native_image import seal as app_seal
from native_banked import seal as banked_seal
from native_reu_check import initial_memory,snapshot
from native_capture_transport import PausedViceMonitor


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--sizes',type=int,nargs='+',default=[128,256,16384])
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    work=Path(tempfile.mkdtemp(prefix='kestrel-banked-vice-'))
    print('Banked VICE evidence:',work,flush=True)
    symbols={};images={}
    for name,source,sealer in (('parent','tests/fixtures/native-banked-app.asm',app_seal),
                               ('provider','examples/native-banked/provider.asm',banked_seal)):
        subprocess.run(['64tass','-a','-B','-I',str(ROOT/'src/native'),str(ROOT/source),
                        '-o',str(work/(name+'.prg')),'-l',str(work/(name+'.sym'))],check=True,capture_output=True)
        image=sealer((work/(name+'.prg')).read_bytes());(work/(name+'.prg')).write_bytes(image)
        images[name]=image
        symbols[name]={n:int(v,16) for n,v in re.findall(r'^(\w+)\s*=\s*\$([\da-fA-F]+)',
                                                       (work/(name+'.sym')).read_text(),re.M)}
    ps,bs=symbols['parent'],symbols['provider']
    report=dict(passed=False,physical_hardware_io=False,work=str(work),cases=[],
                images={name:hashlib.sha256(image).hexdigest() for name,image in images.items()})
    try:
        for kib in args.sizes:
            case=dict(kib=kib,passed=False,operations=[],snapshots=[]);report['cases'].append(case)
            folder=work/str(kib);folder.mkdir()
            disk=folder/'test.d64';shutil.copy2(ROOT/'target/native/kestrel.d64',disk)
            subprocess.run(['c1541','-attach',str(disk),'-delete','calc',
                            '-write',str(work/'parent.prg'),'calc',
                            '-write',str(work/'provider.prg'),'bkreu.prg'],check=True,capture_output=True)
            expected=bytearray(initial_memory(kib));reu=folder/'initial.reu';reu.write_bytes(expected)
            # 512 KiB or more: the kernel module cache owns the top 64 KiB bank
            # and boot writes its empty directory there.
            usable=kib//4-(16 if kib>=512 else 0)
            if kib>=512:expected[usable*4096:usable*4096+2]=b'\0\1'
            with socket.socket() as sock:
                sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            xv=ci.cbm.Xvfb();log=(folder/'vice.log').open('w');mon=None
            command=['x128','-default','-8',str(disk),'-drive8true','-drive8type','1541',
                     '-reu','-reusize',str(kib),'-reuimage',str(reu),'+reuimagerw',
                     '-sounddev','dummy','-jamaction','0','-warp',
                     '-binarymonitor','-binarymonitoraddress',f'ip4://127.0.0.1:{port}']
            case['command']=command
            emu=subprocess.Popen(command,env=dict(os.environ,DISPLAY=xv.display,
                                __EGL_VENDOR_LIBRARY_FILENAMES=ci.cbm.MESA_EGL),stdout=log,stderr=subprocess.STDOUT)
            try:
                deadline=time.monotonic()+30
                while mon is None:
                    assert emu.poll() is None
                    try: mon=ci.Monitor(port=port)
                    except OSError:
                        assert time.monotonic()<deadline
                        time.sleep(.1)
                banks=mon.banks();mon.resume();paused=PausedViceMonitor(mon)
                def read(at,n=1,bank='ram00'):
                    result=bytes(paused.read_mem(at,at+n-1,bank=banks[bank]));paused.resume();return result
                def write(at,data): paused.write_mem(at,data);paused.resume()
                def wait(predicate,label,seconds=90):
                    deadline=time.monotonic()+seconds
                    while time.monotonic()<deadline:
                        if predicate():return
                        assert emu.poll() is None
                        time.sleep(.03)
                    raise AssertionError(label)
                def ready():return read(0x3d12)==b'\1' and read(0xd0)==b'\0'
                def key(value):
                    wait(ready,'input ready')
                    before=int.from_bytes(read(0x3d13,2),'little')
                    with paused.paused('key'):
                        paused.write_mem(0x3d12,b'\0');paused.write_mem(0x34a,bytes([value]));paused.write_mem(0xd0,b'\1')
                    wait(lambda:int.from_bytes(read(0x3d13,2),'little')==before+1 and ready(),'key completed')
                def call(op,error=0,flags=0):
                    serial=read(ps['check_serial'])[0]
                    write(ps['check_operation'],bytes([op,flags]));key(32)
                    result=read(ps['check_result'],3)
                    assert result[0]==error and result[1]&1==bool(error),(op,result.hex(),error)
                    assert result[1]&12==flags&12 and result[2]==(serial+1)&255
                    case['operations'].append(dict(operation=op,error=error,flags=flags))
                def config(pages=0,page=0,token=0,offset=0,count=0):
                    data=(b'\x20'+pages.to_bytes(2,'little')+page.to_bytes(2,'little')+token.to_bytes(8,'little')+
                          offset.to_bytes(3,'little')+count.to_bytes(2,'little'))
                    write(0x3a00,data);call(9)
                def status():
                    call(10);return read(0x3a00,29)
                def snap(label):
                    with paused.paused(label): memory,info=snapshot(mon,folder/(label+'.vsf'))
                    assert memory==expected,(label,'whole REU memory')
                    case['snapshots'].append(info)
                wait(lambda:read(0x1c13,6)==b'KES128' and ready(),'native boot')
                key(ord('C'))
                assert read(ps['check_load_error'])==b'\0' and read(ps['bk_state'])==b'\2'
                loaded=bytearray(images['provider'][2:]);loaded[22:24]=ps['bk_callback'].to_bytes(2,'little')
                assert read(0x6000,len(loaded),'ram01')==loaded
                (folder/'provider-loaded.bin').write_bytes(read(0x6000,len(loaded),'ram01'))
                low=read(0x400,0x5c00,'ram01')
                (folder/'bank1-low-before.bin').write_bytes(low)
                shadow=read(bs['ru_probe_data'],2)
                registers=read(6,3)
                mmu=bytes(mon.read_mem(0xd506,0xd506));mon.resume()
                speed=bytes(mon.read_mem(0xd030,0xd030));mon.resume()
                write(0xd506,bytes([mmu[0]|64]));write(0xd030,bytes([speed[0]|1]))
                config();call(0,flags=8)
                assert int.from_bytes(status()[21:23],'little')==usable
                snap('probe-restored')
                config(pages=usable);call(2);token=int.from_bytes(status()[5:13],'little')
                for offset in (0xff80,usable*4096-512,0x7ff80 if kib>=1024 else 0):
                    data=bytes((i*93+(offset>>16)*11)&255 for i in range(512))
                    config(token=token,offset=offset,count=512)
                    write(0x3a00,data);call(6,flags=8);expected[offset:offset+512]=data
                    write(0x3a00,bytes(512));call(5)
                    assert read(0x3a00,512)==data and int.from_bytes(status()[18:20],'little')==512
                config(token=token,offset=usable*4096-1,count=2);call(6,6)
                call(4);call(4,4);call(1)
                after_reu=read(0x400,0x5c00,'ram01')
                assert after_reu==low
                (folder/'bank1-low-after-reu.bin').write_bytes(after_reu)
                # Real native callbacks allocate/read/write/free low bank-1 data.
                write(0x3d00,bytes([32,2,1,4]));write(0x3a00,b'\7');call(11)
                handle=read(0x3d04,4)
                write(0x3d08,bytes([0,0,0,2]))
                data=b'\3'+bytes((i*41+13)&255 for i in range(511))
                write(0x3a00,data);call(11,flags=8)
                assert read(0x400,512,'ram01')==data
                write(0x3a00,b'\2'+bytes(511));call(11);assert read(0x3a00,512)==data
                write(0x3a00,b'\1');call(11)
                assert read(0x600,0x5a00,'ram01')==low[512:]
                (folder/'bank1-low-after-callbacks.bin').write_bytes(read(0x400,0x5c00,'ram01'))
                for op in (6,8,9,10,17,18,21,22,23,255):
                    write(0x3a00,bytes([op]));call(11,1)
                call(0,8,flags=4)
                assert read(bs['ru_probe_data'],2)==shadow and read(6,3)==registers
                case['borrowed_registers']=dict(before=registers.hex(),after=read(6,3).hex())
                case['probe_shadow']=dict(address=bs['ru_probe_data'],before=shadow.hex(),after=read(bs['ru_probe_data'],2).hex())
                assert bytes(mon.read_mem(0xd506,0xd506))==bytes([mmu[0]|64]);mon.resume()
                assert bytes(mon.read_mem(0xd030,0xd030))==bytes([speed[0]|1]);mon.resume()
                snap('banked-transfers-and-callbacks')
                write(0xd506,mmu);write(0xd030,speed)
                key(27)
                assert read(0x3d20)==b'\0' and read(0x3d0e,3)==bytes([175,251,32])
                case['passed']=True
                case['bank0_probe_shadow_preserved']=True
                case['low_bank1_document_bytes_checked']=len(low)
                print('PASS:',kib,'KiB cold banked load, real callbacks/DMA and complete REU comparison',flush=True)
            finally:
                args.report.write_text(json.dumps(report,indent=2)+'\n')
                if mon:mon.quit_emulator()
                else:emu.terminate()
                emu.wait(timeout=15);xv.stop();log.close()
        report['passed']=True
    finally:
        args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
