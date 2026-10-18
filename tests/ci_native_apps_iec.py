#!/usr/bin/env python3
"""VICE twin of hw_ultimate_check.py --native-apps: Paint with a verified
picture save and its Open, the Claude landing page, all four Ultimate controls pages and a
verified Sheet save after the desktop workflow,
through real C128 IEC on 1541 drives 8 and 9.

VICE has no Ultimate cartridge, so the four controls pages are checked
against the absent-cartridge replies (native_suite_workflow.absent_reference).
The hardware references are checked here as oracles only: the REST drive
reference on the recorded reference-machine drive list, and the Info,
Network and Clock reference on a fake Ultimate.

--apps-only is the twin of --native-apps-only (no Calculator, Editor or Files
steps); --vdc64 gives VICE a 64 KiB VDC, as on the reference C128.
"""
import argparse
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
from native_suite_workflow import absent_reference,drive_body,info_body,network_body,rtc_observation


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
    return drives


def check_controls_reference(drives,report,save):
    """The hardware Info, Network and Clock oracle (ultimate_reference) on a
    fake Ultimate: FTP greeting and MLSD, REST network settings."""
    import hw_native_apps_check as apps
    class FakeFTP:
        greeting='220 Ultimate-II FTP: IP = 192.0.2.37. Hello 192.0.2.38:40000'
        def __init__(self,host,timeout):assert host=='192.0.2.37'
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def getwelcome(self):return self.greeting
        def login(self):pass
        def mlsd(self,folder):
            assert folder=='/Temp'
            return iter([('temp0002',dict(type='file',modify='20261016135422'))])
    class FakeUltimate:
        host='192.0.2.37'
        def __init__(self,settings):self.settings=settings
        def control(self,method,path):
            assert (method,path)==('GET','/v1/configs/Network%20settings')
            return {'Network settings':self.settings,'errors':[]}
    static={'Use DHCP':'Disabled','Static IP':'192.0.2.37','Static Netmask':'255.255.255.0','Static Gateway':'192.0.2.1'}
    upload=dict(path='/Temp/temp0002',started=100.0,finished=104.0)
    real_ftp,real_route=apps.ftplib.FTP,apps.lan_route
    try:
        apps.ftplib.FTP=FakeFTP
        replies,sources=apps.ultimate_reference(FakeUltimate(static),drives,upload)
        assert info_body(replies)==['HARDWARE','1541 ULTIMATE II','','TARGET 4','CONTROL TARGET V1.1'],info_body(replies)
        network=['NETWORK INTERFACES: 1','INTERFACE 0','','IP:      192.0.2.37','MASK:    255.255.255.0',
                 'GATEWAY: 192.0.2.1','','CONFIGURED ADDRESSES; LINK UNTESTED.']
        assert network_body(replies)==network,network_body(replies)
        assert bytes.fromhex(replies['rtc']['data_hex'])==b'2026/10/16 13:54:22'
        # Read 3600 s of host time after the upload: 14:54:22 fits, a minute off does not.
        rtc_observation('2026/10/16 14:54:22',replies['rtc'],3700.0,3702.0,0)
        for wrong in ('2026/10/16 14:55:22','2026/10/16 14:53:22'):
            try:rtc_observation(wrong,replies['rtc'],3700.0,3702.0,0)
            except AssertionError:continue
            raise AssertionError(('RTC oracle accepted',wrong))
        apps.lan_route=lambda address:('255.255.255.0','192.0.2.1',dict(dev='test'))
        dhcp,_=apps.ultimate_reference(FakeUltimate(dict(static,**{'Use DHCP':'Enabled','Static IP':'192.0.2.99'})),drives,upload)
        assert network_body(dhcp)==network
        for settings,greeting in ((dict(static,**{'Static IP':'192.0.2.99'}),FakeFTP.greeting),
                                  (static,'220 1541Ultimate-II FTP Server ready.')):
            FakeFTP.greeting=greeting
            try:apps.ultimate_reference(FakeUltimate(settings),drives,upload)
            except RuntimeError:continue
            raise AssertionError(('controls oracle accepted',settings,greeting))
    finally:
        apps.ftplib.FTP,apps.lan_route=real_ftp,real_route
    report['controls_reference_oracle']=dict(info=info_body(replies),network=network,sources=sources)
    save();print('PASS: Info, Network and Clock oracles on a fake Ultimate',flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--apps-only',action='store_true')
    parser.add_argument('--vdc64',action='store_true')
    args=parser.parse_args()
    work=Path(tempfile.mkdtemp(prefix='kestrel-native-apps-iec-'))
    print('Native apps IEC evidence:',work,flush=True)
    shutil.copy2(__file__,work/'run.py')
    disk=work/'suite.d64';shutil.copy2(ROOT/'target/native-desktop/kestrel.d64',disk)
    data=work/'data.d64';blank=blank_data_disk(data);(work/'initial-data.d64').write_bytes(blank)
    report=dict(passed=False,physical_hardware_io=False,events=[],desktops=[],screens=[],
        images={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ('target/native','target/native-desktop')
                for p in (ROOT/folder).iterdir() if p.suffix in ('.prg','.d64')})
    report.update(apps_only=args.apps_only,vdc64=args.vdc64)
    def save():(work/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    check_controls_reference(check_rest_reference(report,save),report,save)
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    mon=process=xv=None;log=(work/'vice.log').open('w')
    try:
        xv=ci.cbm.Xvfb()
        command=['x128','-default','-8',str(disk),'-drive8true','-drive8type','1541',
            '-9',str(data),'-drive9true','-drive9type','1541',
            *(['-VDC64KB'] if args.vdc64 else []),'-sounddev','dummy','-jamaction','0','-warp','-binarymonitor','-binarymonitoraddress',f'ip4://127.0.0.1:{port}']
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
        extra=native_apps(paused,capture,work,report,save,controls_reference=absent_reference())
        run_native_workflow(paused,capture,work,disk,report,save,key_quiet=.1,key_poll=.1,additional_apps=extra,
                            prelude=not args.apps_only)
        assert report.get('apps_passed') and report.get('native_checks_passed')
        # VICE's 8563 never drifts, so a nonzero count means the readback
        # itself is wrong and the service is rewriting good runs.
        assert report['vdc_rewrites'] and not any(report['vdc_rewrites'].values()),report['vdc_rewrites']
        mon.quit_emulator();mon.close();mon=None
        process.wait(timeout=15)
        assert hashlib.sha256(disk.read_bytes()).hexdigest()==report['images']['target/native-desktop/kestrel.d64']
        verify_data_disk(data.read_bytes(),blank,work,report,save)
        report.update(passed=True,system_disk_unchanged=True);save()
        print('PASS: Paint keyboard edits, picture save, open and discard, Claude landing and return, four controls pages, '
              'Paint and Sheet saves on device 9 with independent readback',flush=True)
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
