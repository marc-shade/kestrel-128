#!/usr/bin/env python3
"""The native Ultimate/USB check's fixtures, upload and restoration.

hw_native_ultimate_check.run creates a private /Usb0 folder with fixtures
over FTP, uploads the native disk to drive A, and must always restore drive
A, retrieve every fixture and saved output, and delete them all with the
folder. Also: the USB browser needs an injected directory reference, the
retrieved-output comparison, and the Navigation page selection logic. Uses
Machine/FTP from ci_hardware_uploads; no hardware I/O."""
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
import hw_native_ultimate_check as workflow
import hw_session
from ci_hardware_uploads import Machine,FTP

ORIGINAL=bytes((i*5)&255 for i in range(174848))


def run_check(scenario,destination,**kwargs):
    work=destination/'evidence';work.mkdir(parents=True)
    machine=Machine(a=('/Temp/temp0001',''),files={'/Temp/temp0001':ORIGINAL},faults={'short-a'} if scenario=='short-a' else set())
    ftp=FTP(machine,faults={'short-put'} if scenario=='fixture-failure' else set())
    if scenario=='reset-uncertain':machine.faults.add('reset-lost')
    def boot_check(capture):
        machine.events.append('boot-check')
        report=json.loads((work/'report.json').read_text());folder=report['private_directory']
        assert machine.mounted('a')==report['native_disk_upload_path'] and machine.ram[0x1c13:0x1c19]==b'KES128'
        if scenario=='partial-output':machine.files[folder+'/A LONG SAVED DOCUMENT NAME.TXT']=b'ONE "!QUO'
        if scenario=='unexpected-file':machine.files[folder+'/STRAY.TMP']=b'?'
        raise AssertionError('simulated native boot observation failure')
    client=SimpleNamespace(read=lambda a,n=1:machine.read_mem(a,n),events=[],frames=[],
        capture=SimpleNamespace(records=[]),heaps=[],states=[],observations=[],modules=[])
    def wait(predicate,label,*args):
        if not predicate():raise AssertionError(label)
    def session(ult,work,report,save,drives,dos_contexts=None):
        return hw_session.HardwareSession(ult,work,report,save,drives=drives,ftp=ftp,dos_contexts=dos_contexts)
    with ExitStack() as stack:
        for name,value in [('hashes',lambda:{'test':'fixed'}),('wait',wait),('quiet_boot',lambda label:None),
                           ('USBEditorClient',lambda *args,**kwargs:client),('verify_boot_layout',boot_check),
                           ('HardwareSession',session)]:
            stack.enter_context(patch.object(workflow,name,value))
        stack.enter_context(patch.object(workflow.tempfile,'mkdtemp',return_value=str(work)))
        stack.enter_context(redirect_stdout(io.StringIO()))
        try:workflow.run(machine,**kwargs)
        except (AssertionError,RuntimeError,SystemExit) as error:failure=str(error)
        else:raise AssertionError('injected failure was ignored')
    return machine,ftp,work,failure


def check(scenario,destination,**kwargs):
    machine,ftp,work,failure=run_check(scenario,destination,**kwargs)
    report=json.loads((work/'report.json').read_text())
    folder=report['private_directory']
    assert not report['passed'] and report['restore']['drives_match'] and report['restore']['reset_after']
    assert machine.state['a']['image_file']=='/Temp/temp0001' and machine.state['a']['type']=='1541'
    uploads=[p for p in machine.files if p.startswith('/Temp/') and p!='/Temp/temp0001']
    restore=report['restore']
    if scenario=='unexpected-file':
        # A name the check did not create stops every deletion; the error
        # raised is still the check's own.
        assert failure=='simulated native boot observation failure'
        assert restore['unexpected_entries']=={folder:['STRAY.TMP']} and not restore['deletions']
        owned={folder,report['native_disk_upload_path']}|{folder+'/'+n for n in report['fixture_readbacks']}|\
              {folder+'/'+n for n in ('A LONG SAVED DOCUMENT NAME.TXT','LARGE COPY.TXT')}
        assert folder in machine.folders and set(restore['leftovers'])==owned
        return dict(passed=True,error=failure,events=machine.events)
    assert restore['passed'] and folder not in machine.folders and not uploads
    assert not any(p.startswith(folder) for p in machine.files)
    if scenario=='fixture-failure':
        assert 'read back differ' in report['preflight_error'] and 'upload-a' not in machine.events
        assert machine.events==['reset'] and not report['session']['uploads']
    else:
        names={'NOTE.TXT','EMPTY.TXT','LARGE.TXT'}
        if kwargs.get('usb_apps'):
            from hw_native_usb_apps import app_fixtures
            names|={n.decode() for n in app_fixtures()}
            assert folder+'/HISTORY' in restore['never_created']
        assert set(report['fixture_readbacks'])==names
        retrieved={p[len(folder)+1:] for p in restore['retrieved'] if p.startswith(folder+'/')}
        assert retrieved>={'NOTE.TXT','EMPTY.TXT','LARGE.TXT'}
    if scenario=='short-a':
        assert 'incomplete' in report['error'] and 'boot-check' not in machine.events and machine.events.count('reset')==1
    if scenario in ('native-failure','partial-output'):
        assert report['error']=='simulated native boot observation failure' and machine.events.count('boot-check')==1
        assert set(restore['never_created'])>={folder+'/LARGE COPY.TXT'}
    if scenario=='partial-output':
        assert restore['retrieved'][folder+'/A LONG SAVED DOCUMENT NAME.TXT']['bytes']==9
    if scenario=='reset-uncertain':
        # The boot reset's reply was lost: no observation, restoration still runs.
        assert 'reset response lost' in report['error'] and 'boot-check' not in machine.events
        resets=[r for r in machine.control_requests if r['path']=='/v1/machine:reset']
        assert len(resets)==2 and not resets[0]['response_received'] and resets[1]['response_received']
    return dict(passed=True,error=failure,events=machine.events)


def browser_reference(destination):
    """--native-usb-browser refuses without a reference; with one it uses it,
    creates EMPTY FOLDER and removes it with everything else."""
    work=destination/'refused';work.mkdir(parents=True)
    machine=Machine()
    with patch.object(workflow.tempfile,'mkdtemp',return_value=str(work)):
        try:workflow.run(machine,usb_browser=True)
        except SystemExit as error:assert 'not available' in str(error)
        else:raise AssertionError('usb browser ran without a reference')
    assert not machine.sent
    calls=[]
    def reference(path,offsets):
        calls.append((path,offsets))
        count={b'/':3,b'/Usb0/':2,workflow.LARGE_DIRECTORY:300}.get(path)
        if count is None:
            count=0 if path.endswith(workflow.EMPTY_FOLDER) else 9
        names=[b'NOTE.TXT',b'EMPTY.TXT',b'LARGE.TXT',workflow.EMPTY_FOLDER] if count==9 else [b'E%d'%i for i in range(count)]
        from hw_native_usb_apps import app_fixtures
        if count==9:names+=list(app_fixtures())
        # A READ_DIR reply after a skip holds every remaining packet.
        pages={str(o):dict(entries_hex=[(b'\x20'+n).hex() for n in names[o:]],count=count,full=False,clipped=False,status='')
               for o in offsets}
        return dict(path_hex=path.hex(),open_code=0 if count else 1,count=count,pages=pages)
    machine,ftp,work,failure=run_check('native-failure',destination/'reference',usb_browser=True,directory_reference=reference)
    report=json.loads((work/'report.json').read_text());folder=report['private_directory']
    assert failure=='simulated native boot observation failure' and report['private_subdirectory_created']
    assert [c[0] for c in calls]==[b'/',b'/Usb0/',workflow.LARGE_DIRECTORY,folder.encode(),folder.encode()+b'/EMPTY FOLDER']
    assert ('mkdir',folder+'/EMPTY FOLDER') in ftp.log and ('rmdir',folder+'/EMPTY FOLDER') in ftp.log
    assert report['restore']['passed'] and folder not in machine.folders
    return dict(passed=True,reference_calls=len(calls))


def outputs_comparison():
    """verify_outputs: the retrieved folder must equal fixtures plus outputs."""
    folder=b'/Usb0/kestrel-native-000000000001'
    expected={b'NOTE.TXT':b'NOTE',b'LARGE COPY.TXT':b'COPY'}
    upload='/Temp/temp0042'
    def attempt(retrieved):
        report=dict(native_checks_passed=True,native_disk_upload_path=upload,output_readbacks={},
                    restore=dict(passed=True,retrieved={upload:dict(bytes=1,sha256='0'*64)}))
        session=SimpleNamespace(retrieved={folder.decode()+'/'+k.decode():v for k,v in retrieved.items()})
        with tempfile.TemporaryDirectory(prefix='kestrel-outputs-') as temporary:
            try:workflow.verify_outputs(session,Path(temporary),report,folder,expected,lambda:None)
            except AssertionError:return False,report
            return True,report
    ok,report=attempt(dict(expected))
    assert ok and report['private_files_removed'] and set(report['output_readbacks'])=={'NOTE.TXT','LARGE COPY.TXT'}
    assert not attempt({b'NOTE.TXT':b'NOTE'})[0],'a missing output was accepted'
    assert not attempt({**expected,b'EXTRA':b''})[0],'an unexpected file was accepted'
    assert not attempt({**expected,b'LARGE COPY.TXT':b'COPX'})[0],'changed bytes were accepted'
    return dict(passed=True)


def navigation_pages():
    from hw_native_usb_browser import Navigation
    n=Navigation.__new__(Navigation)
    rows=[b' '+f'FILE {i}'.encode() for i in range(11)]
    state=dict(base=0,row=0,device=1,keys=[])
    def key(k,**kwargs):
        state['keys'].append(k)
        if k==ord('N'):state['base']+=8;state['row']=0
        elif k==ord('B'):state['base']-=8;state['row']=0
        elif k==9:state['device']=3-state['device'];state['base']=state['row']=0
        elif k==17:state['row']+=1
        elif k==145:state['row']-=1
    n.client=SimpleNamespace(key=key);n.private_path=n.path=b'/PRIVATE/'
    n.device=1;n.base=n.row=0;n.error=None
    n.private_entries=rows[:8];n.outputs={r[1:]:b'' for r in rows[8:]}
    n.entries=rows[:8];n.more=True;n.selected_name=rows[0][1:]
    n.details={'pages':[]};n.frame=lambda *a,**k:None;n.save=lambda:None
    n.raw_page=lambda label:(dict(path_hex=n.path.hex(),base=state['base'],selected=state['row'],
        device=state['device'],more=state['base']+8<len(rows)),rows[state['base']:state['base']+8])
    n.select(rows[10][1:]);assert (state['base'],state['row'])==(8,2)
    n.check('selected-last')
    n.select(rows[1][1:]);assert (state['base'],state['row'])==(0,1)
    n.check('selected-first-page')
    n.select(rows[10][1:]);n.launch(rows[9][1:],'context-reload',2)
    assert (state['base'],state['row'],state['device'])==(8,1,2)
    assert len(n.details['pages'])>=5
    return dict(passed=True,observations=n.details,keys=state['keys'])


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path);args=parser.parse_args()
    report=dict(passed=False,hardware_io=False,cases={})
    try:
        with tempfile.TemporaryDirectory(prefix='kestrel-usb-restore-tests-') as folder:
            for scenario in ('fixture-failure','short-a','native-failure','partial-output','unexpected-file','reset-uncertain'):
                report['cases'][scenario]=check(scenario,Path(folder)/scenario)
            report['cases']['usb-apps-fixtures-cleaned']=check('native-failure',Path(folder)/'apps',usb_apps=True)
            report['cases']['usb-browser-reference-required-and-used']=browser_reference(Path(folder)/'browser')
        report['cases']['retrieved-folder-equals-fixtures-and-outputs']=outputs_comparison()
        report['cases']['private-list-over-eight-and-context-refresh']=navigation_pages()
        report['passed']=True
    finally:
        if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(f'PASS: {len(report["cases"])} USB fixture/restoration cases; no hardware I/O')


if __name__=='__main__':main()
