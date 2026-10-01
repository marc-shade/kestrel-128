#!/usr/bin/env python3
"""Cold-boot the native browser, launch a renamed app, inspect and save files."""
import argparse
import hashlib
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
from native_browser_check import BrowserClient,prepare_browser,disk_records,browser_workflow
from native_capture import wait


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--format',choices=('d64','d71','d81'),default='d64')
    args=parser.parse_args();fmt=('d64','d71','d81').index(args.format)
    work=Path(tempfile.mkdtemp(prefix='kestrel-native-browser-iec-'))
    print(f'Native browser emulator evidence: {work}',flush=True)
    disk,data_disk,fixtures=prepare_browser(work,fmt)
    records=disk_records(data_disk.read_bytes(),fmt)
    report=dict(passed=False,build=json.loads((ROOT/'target/native/images.json').read_text()),format=args.format,
                initial_disk_sha256=hashlib.sha256(data_disk.read_bytes()).hexdigest())
    def save():(work/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    xv=ci.cbm.Xvfb();log=(work/'vice.log').open('w')
    extra=['-9',str(data_disk),'-drive9true','-drive9type',('1541','1571','1581')[fmt]] if fmt else []
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
        client=BrowserClient(mon,work)
        wait(lambda:client.read(0x1c13,6)==b'KES128' and client.read(0x3d12)==b'\1','native browser boot',60)
        browser_workflow(client,records,fixtures,fmt,report,save)
        out=work/'browsave.seq'
        subprocess.run(['c1541','-attach',str(data_disk),'-read','browsave,s,r',str(out)],check=True,capture_output=True)
        assert out.read_bytes()==b'42\r'
        assert disk_records(data_disk.read_bytes(),fmt)==records
        for name,data in fixtures.items():
            if not data:continue
            out=work/(name+'-c1541.seq')
            subprocess.run(['c1541','-attach',str(data_disk),'-read',name+',s,r',str(out)],check=True,capture_output=True)
            assert out.read_bytes()==data
        assert report['build']==json.loads((ROOT/'target/native/images.json').read_text())
        report.update(passed=True,independent_export_matches=True,nonempty_fixtures_unchanged=True)
        print('PASS: native browser, renamed-app dispatch, source-format save, byte previews and complete cleanup',flush=True)
    except BaseException as error:
        report['error']=str(error)
        report['emulator_exit_at_failure']=process.poll()
        report['display']=xv.display
        report['display_exit_at_failure']=xv.proc.poll()
        if mon:
            try:
                (work/'failure-vic.bin').write_bytes(bytes(mon.read_mem(0x400,0x7e7)))
                (work/'failure-app.bin').write_bytes(bytes(mon.read_mem(0x6000,0x6fff)))
                (work/'failure-context.bin').write_bytes(bytes(mon.read_mem(0x3d00,0x3de3)))
            except Exception as diagnostic:report['diagnostic_error']=str(diagnostic)
        raise
    finally:
        save();process.terminate();process.wait(timeout=10);xv.stop();log.close()


if __name__=='__main__':main()
