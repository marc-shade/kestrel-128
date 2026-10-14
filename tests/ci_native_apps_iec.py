#!/usr/bin/env python3
"""VICE twin of hw_ultimate_check.py --native-apps: Paint, the Claude landing
page, Ultimate controls and a verified Sheet save after the desktop workflow,
through real C128 IEC on 1541 drives 8 and 9.

VICE has no Ultimate cartridge, so the controls pages are checked against the
absent-cartridge replies (native_suite_workflow.absent_reference). The
hardware REST drive reference is checked here as an oracle only, on the
recorded reference-machine drive list.
"""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
import vice_harness as ci
from hw_native_desktop_check import run_native_workflow
from hw_native_apps_check import native_apps,rest_drive_reference,verify_data_disk,blank_data_disk
from hw_session import flatten
from native_capture import NativeCapture
from native_capture_transport import PausedViceMonitor
from native_suite_workflow import absent_reference,drive_body


def check_rest_reference(report,save):
    """The hardware drive oracle on the recorded reference-machine REST reply."""
    recorded=json.loads((ROOT/'docs/validation/2026-09-12-native-claude-lifecycle/hardware-readiness.json').read_text())
    drives=flatten(next(r['body'] for r in recorded['reads'] if r['label']=='drives'))
    body=drive_body(rest_drive_reference(drives))
    assert body==['ULTIMATE DRIVE INVENTORY','','PARTIAL REPLY: 2 OF 4 RECORDS','',
                  'SLOT 1  TYPE 00  IEC 8  ON','SLOT 2  TYPE 00  IEC 9  ON','',
                  'TYPES: 00=1541 01=1571 02=1581','OTHER TYPE CODES SHOWN AS REPORTED.'],body
    changed=dict(drives,b=dict(drives['b'],type='1581',enabled=False))
    assert drive_body(rest_drive_reference(changed))[4:6]==['SLOT 1  TYPE 00  IEC 8  ON','SLOT 2  TYPE 02  IEC 9  OFF']
    for broken in (dict(drives,a=dict(drives['a'],type='DOS emulation')),{k:drives[k] for k in ('b','a')}):
        try:rest_drive_reference(broken)
        except RuntimeError:continue
        raise AssertionError(('REST drive oracle accepted a drive list it cannot predict',list(broken)))
    report['rest_reference_oracle']=dict(source='docs/validation/2026-09-12-native-claude-lifecycle/hardware-readiness.json',body=body)
    save();print('PASS: REST drive-inventory oracle on the recorded reference-machine drive list',flush=True)


def main():
    work=Path(tempfile.mkdtemp(prefix='kestrel-native-apps-iec-'))
    print('Native apps IEC evidence:',work,flush=True)
    shutil.copy2(__file__,work/'run.py')
    disk=work/'suite.d64';shutil.copy2(ROOT/'target/native-desktop/kestrel.d64',disk)
    data=work/'data.d64';blank=blank_data_disk(data);(work/'initial-data.d64').write_bytes(blank)
    report=dict(passed=False,physical_hardware_io=False,events=[],desktops=[],screens=[],
        images={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ('target/native','target/native-desktop')
                for p in (ROOT/folder).iterdir() if p.suffix in ('.prg','.d64')})
    def save():(work/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    check_rest_reference(report,save)
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    mon=process=xv=None;log=(work/'vice.log').open('w')
    try:
        xv=ci.cbm.Xvfb()
        command=['x128','-default','-8',str(disk),'-drive8true','-drive8type','1541',
            '-9',str(data),'-drive9true','-drive9type','1541',
            '-sounddev','dummy','-jamaction','0','-warp','-binarymonitor','-binarymonitoraddress',f'ip4://127.0.0.1:{port}']
        report['emulator_command']=command;save()
        process=subprocess.Popen(command,env=dict(os.environ,DISPLAY=xv.display,__EGL_VENDOR_LIBRARY_FILENAMES=ci.cbm.MESA_EGL),stdout=log,stderr=subprocess.STDOUT)
        deadline=time.monotonic()+30
        while mon is None:
            assert process.poll() is None
            try:mon=ci.Monitor(port=port)
            except OSError:
                if time.monotonic()>deadline:raise
                time.sleep(.1)
        banks=mon.banks();mon.resume()
        class ObserverRAM:
            # Pin control traffic to bank-0 RAM (a pause inside a bank-1
            # INDFET would otherwise read bank 1), as ci_native_editor_gui_iec.
            def read_mem(self,start,end,bank=None):return mon.read_mem(start,end,bank=banks['ram00'] if bank is None else bank)
            def write_mem(self,start,data,bank=None):return mon.write_mem(start,data,bank=banks['ram00'] if bank is None else bank)
            def resume(self):mon.resume()
        paused=PausedViceMonitor(ObserverRAM())
        @contextmanager
        def stable_batch(label):
            if not label.endswith(('-before','-restore')):
                with paused.paused(label):yield
                return
            deadline=time.monotonic()+30;deferred=0
            while True:
                with paused.paused(label):
                    if bytes(paused.read_mem(0x3d11,0x3d12))==b'\0\1' and bytes(paused.read_mem(0xd0,0xd0))==b'\0':
                        report.setdefault('capture_admissions',[]).append(dict(label=label,deferred=deferred))
                        yield
                        return
                deferred+=1
                assert time.monotonic()<deadline,('idle capture admission',label)
                time.sleep(.01)
        report['capture_control_bank']='ram00'
        capture=NativeCapture(paused,work,quiet=.05,kernel_prefix='native-desktop',batch=stable_batch)
        report['captures']=capture.records;report['paused_capture_batches']=paused.batches
        extra=native_apps(paused,capture,work,report,save,controls_reference=absent_reference(),info_reference=True)
        run_native_workflow(paused,capture,work,disk,report,save,key_quiet=.1,key_poll=.1,additional_apps=extra)
        assert report.get('apps_passed') and report.get('native_checks_passed')
        mon.quit_emulator();mon.close();mon=None
        process.wait(timeout=15)
        assert hashlib.sha256(disk.read_bytes()).hexdigest()==report['images']['target/native-desktop/kestrel.d64']
        verify_data_disk(data.read_bytes(),blank,work,report,save)
        report.update(passed=True,system_disk_unchanged=True);save()
        print('PASS: Paint keyboard edits and discard, Claude landing and return, controls pages, '
              'Sheet save on device 9 with independent readback',flush=True)
    except BaseException as error:
        report['error']=dict(type=type(error).__name__,message=str(error));raise
    finally:
        if mon is not None:
            try:mon.quit_emulator()
            except (OSError,EOFError):pass
            mon.close()
        if process is not None:
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=5)
        if xv is not None:xv.stop()
        log.close();report['all_host_processes_terminal']=(process is None or process.poll() is not None) and (xv is None or xv.proc.poll() is not None);save()


if __name__=='__main__':main()
