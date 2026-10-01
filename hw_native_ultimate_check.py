"""Native editor/Ultimate USB workflow; private fixtures and FTP readback.

Drive A is recorded. A private folder /Usb0/kestrel-native-<random> is created
over FTP and the fixtures are stored in it and read back; a private copy of
the native disk is mounted read-only on A. Afterwards drive A gets its
original image and mode back; every fixture and every file the native apps
saved in the private folder, and the unmounted upload, are retrieved over FTP,
then deleted and confirmed absent with the folder; the C128 is reset
(hw_session.py). The retrieved files are the byte oracle for the saves.

Not replaced: the legacy harness also recorded both Ultimate DOS contexts'
current paths and open-file state through its C128-side UCI client and
compared them afterwards. The REST API does not expose DOS context state, so
this is no longer checked from outside; the native service's own CLOSE path
still verifies its restored CWD (docs/NATIVE-ULTIMATE.md).
"""
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
import time
import uuid

from hw_storage_check import HardwareMonitor
from hw_native_check import hashes,quiet_boot
from hw_session import HardwareSession
from hw_dos_context import DosContexts
from native_editor_check import EditorClient
from native_browser_check import disk_records,browser_screen
from native_capture import ROOT,wait,verify_boot_layout,expected_screen
from hw_native_usb_browser import EMPTY_FOLDER,LARGE_DIRECTORY


class USBEditorClient(EditorClient):
    def literal(self,text,quiet=None):
        data=text.encode();assert all(32<=value<127 for value in data)
        delay=self.quiet if quiet is None else quiet
        for offset in range(0,len(data),10):
            chunk=data[offset:offset+10]
            wait(lambda:self.read(0x3d12)==b'\1' and self.read(0xd0,2)==bytes(2),'native literal input ready',120)
            before=int.from_bytes(self.read(0x3d13,2),'little');started=time.monotonic()
            self.put(0x3d12,b'\0');self.put(0x34a,chunk);self.put(0xd0,bytes([len(chunk)]))
            time.sleep(delay)
            wait(lambda:self.read(0xd0,2)==bytes(2) and self.read(0x3d12)==b'\1' and
                 int.from_bytes(self.read(0x3d13,2),'little')==(before+len(chunk))&65535,
                 'complete native GETIN literal queue',120)
            self.events.append(dict(literal_hex=chunk.hex(),native_getin_queue=True,
                                    quiet_seconds=delay,
                                    elapsed_seconds=round(time.monotonic()-started,3)))

    def prompt(self,key,text,confirm=None):
        self.key(key);self.literal(text);self.key(13,quiet=self.scan_quiet)
        if confirm is not None:self.key(ord(confirm),quiet=self.scan_quiet)


FIXTURES={b'NOTE.TXT':b'ONE "QUOTED" LINE\r\nTWO\nTHREE\r'+bytes([0,255])+b' END\r\n',
          b'EMPTY.TXT':b'',b'LARGE.TXT':(b'0123456789 ABCDEFGHIJKLMNOPQRSTUVWXYZ\r\n'*1800)[:66053]}
# Every file the workflow may save in the private folder.
OUTPUTS=(b'A LONG SAVED DOCUMENT NAME.TXT',b'LARGE COPY.TXT')
USB_APP_OUTPUTS=(b'HISTORY',)


def run(ult,*,redraw=False,usb_apps=False,usb_browser=False,directory_reference=None,dos_contexts=False):
    """directory_reference: see hw_native_usb_browser (required by usb_browser)."""
    if usb_browser:
        from hw_native_usb_browser import UNAVAILABLE,prepare_oracles
        if directory_reference is None:raise SystemExit(UNAVAILABLE)
        usb_apps=True
    prefix='kestrel-hardware-native-directories-' if usb_browser else 'kestrel-hardware-native-usb-apps-' if usb_apps else 'kestrel-hardware-native-redraw-' if redraw else 'kestrel-hardware-native-ultimate-'
    work=Path(tempfile.mkdtemp(prefix=prefix))
    print(f'Native Ultimate hardware evidence: {work}',flush=True)
    disk=work/'native.d64';shutil.copyfile(ROOT/'target/native/kestrel.d64',disk)
    mon=HardwareMonitor(ult)
    client=USBEditorClient(mon,work,quiet=4,scan_quiet=30,capture_quiet=2,poll=2,key_timeout=1800)
    read=client.read;directory=('/Usb0/kestrel-native-'+uuid.uuid4().hex[:12]).encode()
    assert re.fullmatch(rb'/Usb0/kestrel-native-[0-9a-f]{12}',directory)
    fixtures=dict(FIXTURES)
    if usb_apps:
        from hw_native_usb_apps import app_fixtures
        fixtures.update(app_fixtures())
    report=dict(passed=False,build=hashes(),host=ult.host,private_directory=directory.decode(),
                native_disk_sha256=hashlib.sha256(disk.read_bytes()).hexdigest(),
                events=client.events,frames=client.frames,captures=client.capture.records,
                heap_observations=client.heaps,editor_states=client.states,ram_observations=client.observations,
                modules=client.modules,
                quiet_seconds=dict(boot=60,key_or_literal_queue=4,io_initial=30,capture=2,poll=2),
                host_request_timeout_seconds=ult.timeout,uncertain_host_writes=ult.uncertain_writes,
                host_connect_attempts=ult.connect_attempts,host_connect_failures=ult.connect_failures,
                host_control_requests=ult.control_requests,host_upload_checks=ult.upload_checks,
                fixture_readbacks={},output_readbacks={})
    if redraw:report['redraw_timings']={}
    def save():(work/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    ult.record_event=save
    save()
    session=HardwareSession(ult,work,report,save,drives=('a',),
        dos_contexts=DosContexts(ult,work) if dos_contexts else None)
    before=session.snapshot();assert before['a']['enabled'] and before['a']['bus_id']==8
    (work/'ultimate-version.json').write_text(ult.version())
    outputs={};navigation=None;editor_navigation=None
    def body():
        nonlocal navigation,editor_navigation
        try:
            session.private_dir(directory.decode())
            report['private_directory_created']=True;save()
            for name,data in fixtures.items():
                print(f'Preparing private USB fixture {name.decode()}: {len(data)} bytes',flush=True)
                (work/('fixture-'+name.decode()+'.bin')).write_bytes(data)
                report['fixture_readbacks'][name.decode()]=session.private_file((directory+b'/'+name).decode(),data)
                save()
            for name in OUTPUTS+(USB_APP_OUTPUTS if usb_apps else ()):
                session.claim((directory+b'/'+name).decode(),optional=True)
            if usb_browser:
                session.private_dir((directory+b'/'+EMPTY_FOLDER).decode())
                report['private_subdirectory_created']=True;save()
                report['usb_browser']=dict(oracles=prepare_oracles(directory_reference,directory,
                    expected_names=set(fixtures)|{EMPTY_FOLDER}));save()
        except BaseException as error:
            report['preflight_error']=str(error)
            raise
        try:
            report['native_disk_upload_path']=session.upload(disk.read_bytes(),'a','d64','readonly',retrieve=True);save()
            ult.reset();quiet_boot('Native Ultimate boot')
            wait(lambda:read(0x1c13,6)==b'KES128' and read(0x3d12)==b'\1','native Ultimate boot',120)
            report['resident_boot']=verify_boot_layout(client.capture);save()
            protected=[]
            for bank in (0,1):
                client.key(ord('1')+bank);client.key(ord('A'));page=read(0x3d03)[0]
                assert page==(0xdf if bank==0 else 4)
                client.key(ord('W'));client.key(ord('V'));assert read(0x3d16)==b'\0'
                protected.append((bank,page))
            original_keys=read(0x1000,256);(work/'function-keys-before.bin').write_bytes(original_keys)
            client.key(ord('B'),quiet=30)
            records=disk_records(disk.read_bytes())
            if usb_browser:
                from hw_native_usb_browser import Navigation
                navigation=Navigation(client,work,report,directory,outputs,save)
                navigation.start(records,fixtures[b'NOTE.TXT'])
            if usb_apps:
                from hw_native_usb_apps import workflow
                workflow(client,work,report,records,directory,outputs,save,navigation)
            else:
                client.select([r['name'] for r in records].index(b'EDITOR'))
                client.key(13,quiet=30)
            client.editor_active=True
            assert client.cpu_read('editor-saved-function-keys',client.addresses['ed_saved_keys'],256)==original_keys
            client.heap_equal('empty-editor-with-workspace',(143-(ROOT/'target/native/editor.prg').read_bytes()[12],219,29))
            current_format=client.cpu_read('editor-initial-format',client.addresses['ed_format'],1)[0]
            assert current_format in range(4)
            for _ in range((3-current_format)%4):client.key(0x8b)
            device=1
            if navigation:
                report['usb_dialogs']=dict(oracles=report['usb_browser']['oracles'])
                editor_navigation=Navigation(client,work,report,directory,outputs,save,
                                             image='editor',report_key='usb_dialogs')
            def check(label,data,cursor,**kw):
                client.check(label,data,cursor,device=device,fmt=3,**kw);save()
            def path(name):return (directory+b'/'+name).decode()
            def timing(label,count,delay):
                report['redraw_timings'][label]=dict(event_index=len(client.events)-1,characters=count,
                    quiet_seconds=delay,elapsed_seconds=client.events[-1]['elapsed_seconds'])
            def field_check(label,data,cursor,**kw):
                client.key(0x86)
                client.literal('/Usb0/Note',quiet=.1);timing(label+'-ten-characters',10,.1)
                check(label+'-field',data,cursor,mode=2,**kw)
                client.key(20,quiet=.1);check(label+'-shortened',data,cursor,mode=2,**kw)
                client.key(27,quiet=.1);check(label+'-cancelled',data,cursor,**kw)
            check('ultimate-editor-new',b'',0)
            client.module_state('ultimate-module-empty',0);save()
            raw=fixtures[b'NOTE.TXT']
            if editor_navigation:
                client.key(0x85);client.literal(path(b'NOTE.TXT'),quiet=.1);client.key(9,quiet=1)
                client.module_state('ultimate-module-cold-picker',3)
                report['module_cold_picker_seconds']=client.events[-1]['elapsed_seconds'];save()
                editor_navigation.selected_name=EMPTY_FOLDER
                editor_navigation.returned('ultimate-open-file-picker')
                editor_navigation.select(b'NOTE.TXT');editor_navigation.check('ultimate-picker-note-selected')
                client.key(13,quiet=.1);check('ultimate-picker-note-returned',b'',0,mode=1)
                client.module_state('ultimate-module-returned',2);save()
                client.key(13,quiet=30)
            else:client.prompt(0x85,path(b'NOTE.TXT'))
            check('ultimate-open-mixed',raw,0,name=path(b'NOTE.TXT'))
            if redraw:field_check('redraw-small',raw,0,name=path(b'NOTE.TXT'))
            client.prompt(0x88,'000005');client.key(ord('!'));want=raw[:5]+b'!'+raw[5:]
            check('ultimate-edited-quote',want,6,dirty=True,name=path(b'NOTE.TXT'))
            name=b'A LONG SAVED DOCUMENT NAME.TXT';client.prompt(0x86,path(name));outputs[name]=want
            check('ultimate-saved-long-path',want,6,name=path(name),status=1)
            client.prompt(0x85,path(b'MISSING.TXT'));check('ultimate-open-failure-keeps-document',want,6,name=path(name),status=2)
            client.prompt(0x85,path(b'EMPTY.TXT'));check('ultimate-open-empty',b'',0,name=path(b'EMPTY.TXT'))
            raw=fixtures[b'LARGE.TXT']
            print('Opening 66,053 bytes through the native Ultimate backend',flush=True)
            client.prompt(0x85,path(b'LARGE.TXT'));report['large_open_seconds']=client.events[-1]['elapsed_seconds']
            check('ultimate-large-open',raw,0,name=path(b'LARGE.TXT'))
            client.prompt(0x88,'010001')
            if redraw:
                check('redraw-large-cursor',raw,65537,name=path(b'LARGE.TXT'))
                client.key(0x1d,quiet=.1);timing('large-cursor-right',1,.1)
                check('redraw-large-right',raw,65538,name=path(b'LARGE.TXT'))
                client.key(0x9d,quiet=.1);timing('large-cursor-left',1,.1)
                check('redraw-large-left',raw,65537,name=path(b'LARGE.TXT'))
                field_check('redraw-large',raw,65537,name=path(b'LARGE.TXT'))
            client.literal('C128')
            if redraw:timing('large-insert-queue',4,4)
            client.key(20,quiet=.1 if redraw else None)
            if redraw:timing('large-backspace',1,.1)
            want=raw[:65537]+b'C12'+raw[65537:]
            check('ultimate-large-edited',want,65540,dirty=True,name=path(b'LARGE.TXT'))
            name=b'LARGE COPY.TXT';(work/'saved-expected.bin').write_bytes(want)
            if editor_navigation:
                client.key(0x86);client.literal(path(name),quiet=.1)
                for key in (0x9d,0x9d,0x9d,0x9d,4,ord('.')):client.key(key,quiet=.1)
                caret=len(path(name))-3
                check('ultimate-save-field-middle',want,65540,dirty=True,name=path(b'LARGE.TXT'),mode=2,
                      field=path(name),field_caret=caret)
                field_before=client.cpu_read('ultimate-field-before-picker',client.addresses['ed_field_len'],8)
                client.key(9,quiet=1)
                editor_navigation.selected_name=EMPTY_FOLDER
                editor_navigation.returned('ultimate-save-file-picker')
                editor_navigation.go(LARGE_DIRECTORY,'ultimate-picker-large-first','large')
                for index in range(32):
                    client.key(ord('N'),quiet=1)
                    editor_navigation.details['next_seconds'].append(client.events[-1]['elapsed_seconds'])
                    if (index+1)%8==0:
                        print(f'Editor file picker reached ordinal {(index+1)*8} with the document retained',flush=True);save()
                editor_navigation.view('large',256);editor_navigation.check('ultimate-picker-ordinal-256')
                editor_navigation.details['document_during_dialog']=client.dialog_document('ultimate-picker-document',want);save()
                client.key(ord('B'),quiet=1)
                editor_navigation.view('large',248);editor_navigation.check('ultimate-picker-back-248')
                client.key(27,quiet=.1)
                check('ultimate-picker-cancel-keeps-document',want,65540,dirty=True,name=path(b'LARGE.TXT'),mode=2,
                      field=path(name),field_caret=caret)
                client.module_state('ultimate-module-large-cancel',2);save()
                field_after=client.cpu_read('ultimate-field-after-picker',client.addresses['ed_field_len'],8)
                assert field_before==field_after
                report['field_dialog_retention']=dict(before_hex=field_before.hex(),after_hex=field_after.hex(),
                                                     text=path(name),caret=caret,identical=True);save()
                client.key(9,quiet=1);editor_navigation.selected_name=EMPTY_FOLDER
                editor_navigation.returned('ultimate-picker-save-folder')
                client.key(ord('S'),quiet=.1)
                check('ultimate-picker-folder-returned',want,65540,dirty=True,name=path(b'LARGE.TXT'),mode=2)
            print('Saving, closing, reopening and verifying all 66,056 bytes',flush=True)
            if editor_navigation:client.key(13,quiet=30)
            else:client.prompt(0x86,path(name))
            report['large_save_seconds']=client.events[-1]['elapsed_seconds'];outputs[name]=want
            check('ultimate-large-save-verified',want,65540,name=path(name),status=1)
            client.prompt(0x86,path(name));check('ultimate-existing-file-rejected',want,65540,name=path(name),status=7)
            client.key(0x87);check('ultimate-new-after-save',b'',0)
            client.prompt(0x8c,'2');device=2
            client.prompt(0x85,path(name));report['large_reopen_seconds']=client.events[-1]['elapsed_seconds']
            check('ultimate-reopen-second-context',want,0,name=path(name))
            client.prompt(0x88,'010001');check('ultimate-reopened-edit',want,65537,name=path(name))
            client.key(27,quiet=30);client.editor_active=False;client.selected=0
            assert read(0x1000,256)==original_keys
            (work/'function-keys-after.bin').write_bytes(read(0x1000,256))
            if navigation:
                navigation.device=2
                navigation.returned('usb-browser-after-editor')
            else:
                # The editor retains its Ultimate data preference on return.
                assert read(0x3d2a)==b'\3'
            client.key(ord('F'),quiet=30)
            client.frames_equal('browser-after-ultimate-editor',lambda cols:browser_screen(cols,records))
            client.key(27);client.heap_equal('workspace-after-ultimate-editor',(143,219,30))
            for bank,page in protected:
                client.key(ord('1')+bank);client.key(ord('V'));assert read(0x3d16)==b'\0'
                data=b''.join(client.capture.capture(f'workspace-{bank}-{offset:04x}',bank=bank,address=page*256+offset,
                                                    count=min(2000,8192-offset)) for offset in range(0,8192,2000))
                assert data==bytes((i&255)^(i>>8)^(0xa5 if bank else 0) for i in range(8192))
                (work/f'workspace-{bank}-all.bin').write_bytes(data);client.key(ord('F'))
            client.heap_equal('all-memory-released',(175,251,32))
            client.frames_equal('workspace-restored',lambda cols:expected_screen(cols,1))
            assert read(0x98)==b'\0' and read(0x3de0,4)==bytes(4) and read(0x3dc0)==b'\0' and read(0x3dd0)==b'\0'
            if navigation:navigation.verify_final(directory_reference)
            if editor_navigation:editor_navigation.verify_final(directory_reference)
            report.update(native_checks_passed=True,saved_bytes=len(want),saved_sha256=hashlib.sha256(want).hexdigest(),
                          all_owned_memory_and_files_released=True,function_key_bytes_restored=256,independent_workspace_bytes=16384)
        except BaseException as error:
            report['error']=str(error)
            try:
                (work/'failure-context.bin').write_bytes(read(0x3d00,0xe4))
                (work/'failure-vic.bin').write_bytes(read(0x400,1000))
                (work/'failure-ultimate-status.bin').write_bytes(read(0x4f00,32))
                (work/'failure-uci-registers-direct.bin').write_bytes(read(0xdf1c,2))
                if report.get('resident_boot') and read(0x3d12)==b'\1' and read(0x3d91)==b'\0':
                    from hwlib import lst_symbol
                    for label,start,end in (('transport','nu_high','nu_code_end'),('directory','nd_slot','nd_path')):
                        first=lst_symbol('native/kestrel',start);last=lst_symbol('native/kestrel',end)
                        client.cpu_read('failure-'+label+'-state',first,last-first+(256 if label=='directory' else 0))
            except Exception as diagnostic:report['diagnostic_error']=str(diagnostic)
            raise
    try:session.run(body)
    finally:report['images_unchanged']=report['build']==hashes();save()
    verify_outputs(session,work,report,directory,{**fixtures,**outputs},save)
    assert report['images_unchanged'] and not report['uncertain_host_writes']
    report['passed']=True;save()
    print(f'HW-NATIVE-ULTIMATE PASS; all USB bytes verified; drives restored, private files deleted; {work}',flush=True)


def verify_outputs(session,work,report,directory,expected,save):
    """The retrieved private folder must hold exactly the fixtures (unchanged)
    and the saved outputs, byte for byte."""
    assert report.get('native_checks_passed') and report['restore']['passed']
    folder=directory.decode()+'/'
    retrieved={path[len(folder):].encode():data for path,data in session.retrieved.items() if path.startswith(folder)}
    try:
        assert set(retrieved)==set(expected),('private folder contents',sorted(retrieved),sorted(expected))
        for name,data in expected.items():
            (work/('final-readback-'+name.decode()+'.bin')).write_bytes(retrieved[name])
            assert retrieved[name]==data,(name,'retrieved bytes differ')
            report['output_readbacks'][name.decode()]=dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),
                                                          path=folder+name.decode())
        upload=report['native_disk_upload_path']
        report['temporary_input_readbacks']={upload:report['restore']['retrieved'][upload]}
        report['private_files_removed']=True
    except BaseException as error:
        report['readback_error']=str(error)
        raise
    finally:save()
