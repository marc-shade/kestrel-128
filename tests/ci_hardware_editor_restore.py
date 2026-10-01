#!/usr/bin/env python3
"""The native editor check's two-drive restoration, with a simulated Ultimate.

hw_native_editor_check.run records drives A and B, uploads a native disk to A
and a data disk to B, and must always put both drives back, retrieve both
uploads (the data disk is the byte oracle) and delete them, whatever fails.
Uses Machine/FTP from ci_hardware_uploads; no hardware I/O."""
import argparse
from contextlib import ExitStack,redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
import hw_native_editor_check as workflow
import hw_session
from ci_hardware_uploads import Machine,FTP

NATIVE=bytes((i*11)&255 for i in range(174848))
DATA=bytes((i*13)&255 for i in range(174848))
ORIGINAL=bytes((i*5)&255 for i in range(174848))


def check(scenario,destination):
    work=destination/'evidence';work.mkdir(parents=True)
    faults={'short-a'} if scenario=='short-a' else {'short-b'} if scenario=='short-b' else set()
    b=('data.d64','/Usb0/disks/') if scenario=='b-not-empty' else ('','')
    machine=Machine(a=('/Temp/temp0001',''),b=b,files={'/Temp/temp0001':ORIGINAL,'/Usb0/disks/data.d64':DATA},
                    folders={'/Usb0/disks'},faults=faults)
    ftp=FTP(machine);seen={}
    def prepare(folder):
        disk=folder/'native.d64';disk.write_bytes(NATIVE)
        data=folder/'documents.d64';data.write_bytes(DATA)
        return disk,data,{}
    def editor(client,disk,data_disk,fixtures,index,report,save):
        machine.events.append('editor')
        assert machine.mounted('a')==report['native_disk_path'] and machine.mounted('b')==report['data_disk_path']
        assert machine.files[report['data_disk_path']]==DATA and machine.state['b']['type']=='1541'
        machine.files[report['data_disk_path']]=b'SAVED'+DATA[5:]      # the editor writes to drive 9
        if scenario=='original-lost':del machine.files['/Temp/temp0001']
        if scenario=='editor-failure':raise AssertionError('simulated editor failure')
        report['native_checks_passed']=True;save()
    def verify(work,report,save):
        seen['readback']=(work/'editor-readback.d64').read_bytes()
        report['independent_readback']=dict(verified_by='test double')
    def wait(predicate,label,*args):assert predicate(),label
    def session(ult,work,report,save,drives,dos_contexts=None):
        return hw_session.HardwareSession(ult,work,report,save,drives=drives,ftp=ftp,dos_contexts=dos_contexts)
    with ExitStack() as stack:
        for name,value in [('hashes',lambda:{'test':'fixed'}),('prepare_editor',prepare),('wait',wait),
                           ('quiet_boot',lambda label:None),('editor_workflow',editor),('verify_readback',verify),
                           ('HardwareSession',session),
                           ('EditorClient',lambda mon,*args,**kwargs:SimpleNamespace(read=lambda a,n=1:machine.read_mem(a,n)))]:
            stack.enter_context(patch.object(workflow,name,value))
        stack.enter_context(patch.object(workflow.tempfile,'mkdtemp',return_value=str(work)))
        stack.enter_context(redirect_stdout(io.StringIO()))
        try:workflow.run(machine)
        except (AssertionError,RuntimeError) as error:failure=str(error)
        else:failure=None
    report=json.loads((work/'report.json').read_text())
    uploads=sorted(p for p in machine.files if p.startswith('/Temp/') and p!='/Temp/temp0001')
    assert report['passed']==(scenario=='success')
    if scenario=='b-not-empty':
        assert 'initially empty drive B' in failure and 'restore' not in report
        assert not any(method!='GET' for method,_ in machine.sent) and not uploads
        return dict(passed=True,error=failure,events=machine.events)
    restore=report['restore']
    assert machine.state['b']['image_file']=='' and machine.state['b']['type']=='1541'
    if scenario=='original-lost':
        # Drive B is still restored; nothing is deleted; the failure is raised.
        assert 'metadata' in failure and 'a' in restore['drive_errors'] and not restore['deletions']
        assert uploads==restore['leftovers'] and len(uploads)==2 and not restore['reset_after']
        return dict(passed=True,error=failure,events=machine.events)
    assert machine.state['a']['image_file']=='/Temp/temp0001' and restore['drives_match'] and restore['reset_after']
    assert not uploads and not restore['leftovers'] and all(d['confirmed'] for d in restore['deletions'])
    assert machine.events.count('reset')==(1 if scenario.startswith('short') else 2)
    assert 'editor' not in machine.events if scenario.startswith('short') else 'editor' in machine.events
    if scenario=='short-b':assert len(report['session']['uploads'])==1 and 'incomplete' in failure
    if scenario=='short-a':assert len(report['session']['uploads'])==2 and 'incomplete' in failure
    if scenario=='editor-failure':
        assert failure=='simulated editor failure' and report['error']==failure
        assert restore['retrieved'][report['data_disk_path']]['bytes']==174848
    if scenario=='success':
        assert failure is None and seen['readback']==b'SAVED'+DATA[5:] and report['images_unchanged']
    return dict(passed=True,error=failure,events=machine.events)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path);args=parser.parse_args()
    report=dict(passed=False,hardware_io=False,cases={})
    try:
        with tempfile.TemporaryDirectory(prefix='kestrel-editor-restore-tests-') as folder:
            for scenario in ('success','b-not-empty','short-b','short-a','editor-failure','original-lost'):
                report['cases'][scenario]=check(scenario,Path(folder)/scenario)
        report['passed']=True
    finally:
        if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(f'PASS: {len(report["cases"])} editor two-drive restoration scenarios; no hardware I/O')


if __name__=='__main__':main()
