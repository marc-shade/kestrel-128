#!/usr/bin/env python3
"""Native IEC stream integration through a disk-loaded client in x128."""
import hashlib
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

import vice_harness as ci
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from native_files_check import NativeFiles,prepare,workflow
from native_capture import wait


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--format',choices=('d64','d71','d81'),default='d64')
    args=parser.parse_args();fmt=('d64','d71','d81').index(args.format)
    work=Path(tempfile.mkdtemp(prefix='kestrel-native-files-iec-'))
    print(f'Native IEC evidence: {work}',flush=True)
    disk,fixtures=prepare(work,fmt=fmt)
    data_disk=work/('data.'+args.format) if fmt else disk
    quiet=.5 if fmt else .02
    open_quiet=5 if fmt else .02
    report=dict(passed=False,kernel_sha256=hashlib.sha256((ROOT/'target/native/kestrel.prg').read_bytes()).hexdigest(),
                test_disk_sha256=hashlib.sha256(disk.read_bytes()).hexdigest(),format=args.format,
                data_disk_sha256=hashlib.sha256(data_disk.read_bytes()).hexdigest(),
                observation_quiet_seconds=dict(transfer=quiet,open=open_quiet))
    def save():(work/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    xv=ci.cbm.Xvfb();log=(work/'vice.log').open('w')
    extra=['-9',str(data_disk),'-drive9true','-drive9type',('1541','1571','1581')[fmt]] if fmt else []
    if not fmt:
        full=work/'nearly-full.d64';filler=work/'filler.seq'
        filler.write_bytes(bytes((i*29)&255 for i in range(662*254)))
        subprocess.run(['c1541','-format','full test,01','d64',str(full),
                        '-write',str(filler),'filler,s'],check=True,capture_output=True)
        extra=['-9',str(full),'-drive9true','-drive9type','1541']
    process=subprocess.Popen(['x128','-default','-8',str(disk),'-drive8true','-drive8type','1541',*extra,
                              '-sounddev','dummy','-jamaction','0','-warp','-binarymonitor',
                              '-binarymonitoraddress',f'ip4://127.0.0.1:{port}'],
                             env=dict(os.environ,DISPLAY=xv.display,__EGL_VENDOR_LIBRARY_FILENAMES=ci.cbm.MESA_EGL),
                             stdout=log,stderr=subprocess.STDOUT)
    mon=None
    try:
        deadline=time.monotonic()+30
        while mon is None:
            assert process.poll() is None
            try:mon=ci.Monitor(port=port)
            except OSError:
                if time.monotonic()>deadline:raise
                time.sleep(.1)
        client=NativeFiles(mon,work,device=9 if fmt else 8,fmt=fmt,quiet=quiet,open_quiet=open_quiet)
        wait(lambda:client.read_ram(0x1c13,6)==b'KES128' and client.read_ram(0x3d12)==b'\1','native file boot',60)
        client.key(ord('C'),expected=None)
        assert client.read_ram(0x3d20)==bytes([32]) and client.read_ram(0x3d23)==b'\2'
        workflow(client,fixtures,report,save)
        if not fmt:
            client.key(ord('C'),expected=None)
            client.open(b'OVERFLOW',mode=1,device=9)
            outcomes=[]
            for _ in range(3):
                client.write(bytes(range(256))*2,expected=None)
                state=client.read_ram(0x3d80,0x64)
                outcomes.append(dict(operation='write',code=state[14],dos=state[15],status=state[16],
                                     accepted=int.from_bytes(state[11:13],'little')))
                if state[14]:break
            client.key(ord('C'),expected=None)
            state=client.read_ram(0x3d80,0x64)
            outcomes.append(dict(operation='close',code=state[14],dos=state[15],status=state[16]))
            report['disk_full_outcomes']=outcomes;save()
            assert any(event['code']==0x11 for event in outcomes),outcomes
            client.key(27,expected=None)
            assert client.read_ram(0x3d23)[0] in (0,4)
            untouched=work/'filler-c1541.seq'
            subprocess.run(['c1541','-attach',str(full),'-read','filler,s,r',str(untouched)],check=True,capture_output=True)
            assert untouched.read_bytes()==filler.read_bytes()
            report['disk_full_detected_and_existing_file_preserved']=True
        out=work/'copied-c1541.seq'
        subprocess.run(['c1541','-attach',str(data_disk),'-read','copy,s,r',str(out)],check=True,capture_output=True)
        assert out.read_bytes()==fixtures['source']
        report.update(passed=True,c1541_copy_matches=True)
        print('PASS: native IEC copy over 64 KiB, file types, EOF, exclusive create and app cleanup',flush=True)
    except BaseException as error:
        report['error']=str(error)
        if mon:
            try:
                (work/'failure-files.bin').write_bytes(bytes(mon.read_mem(0x3d80,0x3de3)))
                (work/'failure-app.bin').write_bytes(bytes(mon.read_mem(0x6000,0x6fff)))
                (work/'failure-kernel.bin').write_bytes(bytes(mon.read_mem(0x1c00,0x37ff)))
            except Exception as diagnostic:report['diagnostic_error']=str(diagnostic)
        raise
    finally:
        save();process.terminate();process.wait(timeout=10);xv.stop();log.close()


if __name__=='__main__':main()
