#!/usr/bin/env python3
"""Uploads and the hardware session's snapshot/restore, without hardware I/O.

Part 1 fault-injects the REST client (VerifiedUltimate): an accepted but
incomplete upload must block the boot, failed controls are recorded without
replay, and an existing image is size-checked before it is mounted.

Part 2 runs hw_session.HardwareSession against Machine and FTP below: a
simulated Ultimate (REST drives, mounts, modes, reset, file metadata, RAM) and
its FTP server sharing one file store. Machine and FTP are also used by the
other tests/ci_hardware_*.py and ci_native_transport_lifecycle.py.

Part 3 runs the DOS context probe (probes/hw-dos-context.asm) in py65 against
a simulated command interface, and the session's DOS context guard against
Contexts below. Part 4 checks the hardware desktop's idle capture admission.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from urllib.parse import parse_qs,unquote,urlsplit

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from hw_ultimate_check import VerifiedUltimate
from hw_session import HardwareSession,RestorationError
import hw_dos_context


class Machine(VerifiedUltimate):
    """A simulated Ultimate II+ with drives a, b and a listed non-IEC device.
    files: path -> bytes (the cartridge filesystem); folders: set of paths."""
    def __init__(self,*,a=('',''),b=('',''),mode_a='1541',mode_b='1541',files=None,folders=None,faults=()):
        super().__init__(host='reference.invalid',timeout=60)
        self.faults=set(faults);self.events=[];self.sent=[];self.counter=0x40
        self.ram=bytearray(65536)
        self.files={k:bytes(v) for k,v in (files or {}).items()}
        self.folders=set(folders or ())|{'/','/Temp','/Usb0'}
        self.state={'a':dict(enabled=True,bus_id=8,type=mode_a,rom=mode_a+'.rom',image_file=a[0],image_path=a[1]),
                    'b':dict(enabled=True,bus_id=9,type=mode_b,rom=mode_b+'.rom',image_file=b[0],image_path=b[1]),
                    'IEC Drive':dict(enabled=False,bus_id=11,type='DOS emulation',last_error='73,U64IEC ULTIMATE DOS V1.1,00,00',partitions=[])}

    def read_mem(self,address,length):return bytes(self.ram[address:address+length])
    def write_mem(self,address,data):self.ram[address:address+len(data)]=data

    def _call(self,method,path,data=None):
        self.sent.append((method,path))
        route=urlsplit(path);query={k:v[0] for k,v in parse_qs(route.query).items()}
        body={'errors':[]};status=200
        if method=='GET' and route.path=='/v1/version':body['version']='0.1'
        elif method=='GET' and route.path=='/v1/drives':body['drives']=[{k:dict(v)} for k,v in self.state.items()]
        elif method=='GET' and route.path.endswith(':info'):
            name=unquote(route.path[len('/v1/files'):-len(':info')])
            if name in self.files:body['files']=dict(path=name,size=len(self.files[name]))
            else:status,body=404,{'errors':['file not found']}
        elif method=='POST' and route.path.endswith(':mount'):
            drive=route.path.split('/')[3].split(':')[0]
            name=f'/Temp/temp{self.counter:04X}';self.counter+=1
            stored=bytes(data)
            if 'short-'+drive in self.faults:stored=stored[:63488]
            self.files[name]=stored
            self.state[drive].update(image_file=name,image_path='')
            self.events.append('upload-'+drive)
        elif method=='PUT' and route.path.endswith(':mount'):
            drive=route.path.split('/')[3].split(':')[0];name=query['image']
            if name not in self.files:status,body=404,{'errors':['image not found']}
            elif name.startswith('/Temp/'):self.state[drive].update(image_file=name,image_path='')
            else:
                folder,base=name.rsplit('/',1);self.state[drive].update(image_file=base,image_path=folder+'/')
            self.events.append(f'remount-{drive}:{name}:{query["type"]}')
        elif method=='PUT' and route.path.endswith(':remove'):
            drive=route.path.split('/')[3].split(':')[0];self.state[drive].update(image_file='',image_path='')
            self.events.append('unmount-'+drive)
        elif method=='PUT' and route.path.endswith(':set_mode'):
            drive=route.path.split('/')[3].split(':')[0]
            if 'ignore-mode-'+drive not in self.faults:self.state[drive].update(type=query['mode'],rom=query['mode']+'.rom')
            self.events.append(f'mode-{drive}:{query["mode"]}')
        elif method=='PUT' and route.path=='/v1/machine:reset':
            self.events.append('reset')
            if 'reset-lost' in self.faults:
                self.faults.discard('reset-lost');raise SystemExit('reset response lost after request')
            self.on_reset()
        else:raise AssertionError((method,path))
        return status,json.dumps(body).encode()

    def on_reset(self):
        """A reset boots the native kernel if drive A holds an upload."""
        self.ram[0x1c13:0x1c19]=b'KES128';self.ram[0x3d12]=1

    def mounted(self,drive):
        record=self.state[drive];image=record['image_file']
        return image if not image or image.startswith('/') else record['image_path'].rstrip('/')+'/'+image


class FTP:
    """The FTP server of a Machine (shares its file store)."""
    def __init__(self,machine,faults=()):
        self.m=machine;self.faults=set(faults);self.log=[]

    def names(self,folder):
        folder=folder.rstrip('/') or '/'
        assert folder in self.m.folders,('no such folder',folder)
        prefix=folder.rstrip('/')+'/'
        return sorted(p[len(prefix):] for p in list(self.m.files)+list(self.m.folders)
                      if p.startswith(prefix) and p!=folder and '/' not in p[len(prefix):])

    def exists(self,path):
        self.log.append(('exists',path))
        if 'exists-fails' in self.faults:raise RuntimeError('FTP listing failed')
        return path in self.m.files or path in self.m.folders

    def get(self,path):
        self.log.append(('get',path))
        assert path in self.m.files,('no such file',path)
        return self.m.files[path]

    def put(self,path,data):
        self.log.append(('put',path))
        assert path.rsplit('/',1)[0] in self.m.folders
        self.m.files[path]=bytes(data)[:-1] if 'short-put' in self.faults and len(data)>1 else bytes(data)

    def delete(self,path):
        self.log.append(('delete',path))
        assert path in self.m.files,('no such file',path)
        if 'delete-ignored' not in self.faults:del self.m.files[path]
        if 'lost-delete-reply' in self.faults:raise TimeoutError('reply lost')

    def mkdir(self,path):
        self.log.append(('mkdir',path))
        assert path.rsplit('/',1)[0] in self.m.folders and path not in self.m.folders
        self.m.folders.add(path)

    def rmdir(self,path):
        self.log.append(('rmdir',path))
        assert not self.names(path),('folder not empty',path)
        self.m.folders.discard(path)


def session_for(machine,folder,drives=('a',),ftp=None,dos_contexts=None):
    report={};saves=[]
    def save():saves.append(copy.deepcopy(report))
    session=HardwareSession(machine,folder,report,save,drives=drives,ftp=ftp or FTP(machine),dos_contexts=dos_contexts)
    return session,report,saves


class Cartridge(VerifiedUltimate):
    def __init__(self,*,stored=174848,post_error=None,post_reply=None):
        super().__init__(host='reference.invalid',timeout=60)
        self.stored=stored;self.post_error=post_error;self.post_reply=post_reply
        self.sent=[];self.persisted=[]
        self.record_event=lambda:self.persisted.append(copy.deepcopy((self.control_requests,self.upload_checks)))

    def _call(self,method,path,data=None):
        self.sent.append((method,path,data))
        if method=='POST':
            assert self.persisted[-1][0][-1]['request_started']
            assert not self.persisted[-1][0][-1]['response_received']
            if self.post_error:raise self.post_error
            if self.post_reply:return self.post_reply
        if method=='GET' and path=='/v1/drives':
            body=dict(drives=[dict(a=dict(enabled=True,bus_id=8,image_file='/Temp/test',image_path=''))],errors=[])
        elif method=='GET' and path.endswith(':info'):body=dict(files=dict(size=self.stored),errors=[])
        else:body=dict(errors=[])
        return 200,json.dumps(body).encode()


def client_cases(cases):
    disk=bytes((i*73+i//251)&255 for i in range(174848))
    for label,size in [('zero-byte',0),('truncated',63488),('oversized',174849)]:
        device=Cartridge(stored=size)
        try:device.mount(disk);device.reset()
        except RuntimeError as error:assert 'upload is incomplete' in str(error)
        else:raise AssertionError('incomplete upload allowed a boot')
        assert len([r for r in device.sent if r[0]=='POST'])==1
        assert not any(':reset' in r[1] for r in device.sent)
        assert device.upload_checks==[dict(path='/Temp/test',drive='a',expected_bytes=len(disk),
                                           size_verified=False,stored_bytes=size)]
        assert device.persisted[-1][1]==device.upload_checks
        cases[label+'-success-response-blocks-boot']=True

    device=Cartridge();device.mount(disk);device.reset()
    assert device.upload_checks[0]['size_verified']
    assert device.sent[0]==('POST','/v1/drives/a:mount?type=d64&mode=readwrite',disk)
    assert device.control_requests[0]['sent_sha256']==hashlib.sha256(disk).hexdigest()
    assert device.sent[-1][:2]==('PUT','/v1/machine:reset')
    cases['full-size-upload-allows-one-boot']=True

    for label,reply in [('json-error',(200,b'{"errors":["disk full"]}')),
                        ('http-error',(503,b'{"errors":["unavailable"]}')),
                        ('invalid-json',(200,b'broken'))]:
        device=Cartridge(post_reply=reply)
        try:device.mount(disk);device.reset()
        except (RuntimeError,ValueError):pass
        else:raise AssertionError('failed control allowed a boot')
        assert len(device.sent)==1 and len(device.control_requests)==1
        record=device.control_requests[0]
        assert record['response_received'] and record['status']==reply[0] and record['body_hex']==reply[1].hex()
        assert device.persisted[-1][0]==device.control_requests
        cases[label+'-recorded-without-replay']=True

    device=Cartridge(post_error=SystemExit('response lost after sending'))
    try:device.mount(disk)
    except SystemExit:pass
    else:raise AssertionError('lost response accepted')
    assert len(device.sent)==1 and not device.control_requests[0]['response_received']
    assert device.persisted[-1][0]==device.control_requests
    cases['unknown-acceptance-persisted-without-replay']=True

    device=Cartridge(stored=0)
    try:device.mount_existing('/Temp/test',expected_bytes=174848)
    except AssertionError:pass
    else:raise AssertionError('empty original image accepted')
    assert len(device.sent)==1 and device.sent[0][0]=='GET' and not device.control_requests
    cases['changed-original-refused-before-control']=True

    device=Cartridge(stored=174848)
    device.mounted_path=lambda drive:'/Usb0/disks/boot disk.d64'
    device.mount_existing('/Usb0/disks/boot disk.d64',drive='a',img_type='d64',expected_bytes=174848)
    assert device.sent==[('GET','/v1/files/Usb0/disks/boot%20disk.d64:info',None),
                         ('PUT','/v1/drives/a:mount?image=%2FUsb0%2Fdisks%2Fboot%20disk.d64&type=d64&mode=readwrite',None)]
    cases['original-outside-temp-remounted-by-path']=True

    device=Cartridge()
    for bad in ('/Usb0/../Temp/x','Usb0/x.d64'):
        try:device.path_info(bad)
        except AssertionError:pass
        else:raise AssertionError('unsafe path accepted')
    try:device.file_info('/Usb0/x.d64')
    except AssertionError:pass
    else:raise AssertionError('upload metadata outside /Temp accepted')
    assert not device.sent
    cases['unsafe-paths-refused-before-request']=True


def session_cases(cases,root):
    d81=bytes((i*7)&255 for i in range(819200));d64=bytes((i*3)&255 for i in range(174848))

    def work(label):
        path=Path(root)/label;path.mkdir();return path

    # An empty 1541 drive A: upload a read-only D81 (mode 1581), then restore.
    m=Machine();ftp=FTP(m);s,report,saves=session_for(m,work('empty'),ftp=ftp)
    before=s.snapshot()
    def body():
        path=s.upload(d81,'a','d81','readonly',retrieve=True)
        assert m.state['a']['type']=='1581' and m.mounted('a')==path
        m.reset()
    s.run(body)
    r=report['restore']
    assert r['passed'] and r['drives_match'] and r['cleanup_complete'] and r['reset_after'] and not r['leftovers']
    assert m.state['a']==before['a'] and not any(p.startswith('/Temp/') for p in m.files)
    assert r['retrieved'][report['session']['uploads'][0]['path']]['sha256']==hashlib.sha256(d81).hexdigest()
    assert [d['kind'] for d in r['deletions']]==['upload'] and r['deletions'][0]['confirmed']
    assert m.events==['upload-a','mode-a:1581','reset','unmount-a','mode-a:1541','reset']
    assert saves[0]['session']['drives_before']==before and not saves[0]['session']['uploads']
    cases['session-empty-drive-upload-mode-restored-upload-deleted']=True

    # An original image without an extension (/Temp/tempNNNN): its type comes
    # from its size; drive B (unused) must be untouched.
    m=Machine(a=('/Temp/temp0001',''),b=('boot.d71','/Usb0/disks/'),mode_b='1571',
              files={'/Temp/temp0001':d64,'/Usb0/disks/boot.d71':bytes(349696)},folders={'/Usb0/disks'})
    s,report,_=session_for(m,work('original'))
    before=s.snapshot()
    assert report['session']['restore_plan']['a']==dict(path='/Temp/temp0001',mode='1541',bytes=174848,image_type='d64')
    s.run(lambda:s.upload(d81,'a','d81','readonly'))
    assert m.state==dict((k,dict(v)) for k,v in before.items()) and '/Temp/temp0001' in m.files
    assert 'remount-a:/Temp/temp0001:d64' in m.events and not any(e.endswith('-b') for e in m.events)
    cases['session-original-image-type-from-size-remounted']=True

    # The check's own error is raised after a complete restoration.
    m=Machine();s,report,_=session_for(m,work('raises'))
    s.snapshot()
    def failing():
        s.upload(d64,'a','d64','readonly');raise KeyError('native check failed')
    try:s.run(failing)
    except KeyError as error:assert 'native check failed' in str(error)
    else:raise AssertionError('check error swallowed')
    assert report['restore']['passed'] and not any(p.startswith('/Temp/') for p in m.files)
    cases['session-exception-restores-then-reraises']=True

    # A mode the Ultimate does not take back is a reported mismatch; the
    # upload is kept (leftover) and no reset hides it.
    m=Machine(faults={'ignore-mode-a'},mode_a='1581');s,report,_=session_for(m,work('mismatch'))
    s.snapshot()
    m.faults.discard('ignore-mode-a')
    def switch():
        s.upload(d64,'a','d64','readonly');m.faults.add('ignore-mode-a')
    try:s.run(switch)
    except RestorationError as error:assert 'differ' in str(error)
    else:raise AssertionError('mismatch not reported')
    r=report['restore']
    assert not r['passed'] and not r['drives_match'] and r['drive_differences']=={'a':{'rom':['1581.rom','1541.rom'],'type':['1581','1541']}}
    assert not r['deletions'] and r['leftovers']==[report['session']['uploads'][0]['path']] and not r['reset_after']
    cases['session-restoration-mismatch-reported-upload-kept']=True

    # The original image vanished during the run: every drive is still
    # attempted, the failure is raised, and nothing is deleted.
    m=Machine(a=('/Temp/temp0001',''),files={'/Temp/temp0001':d64});s,report,_=session_for(m,work('vanished'),drives=('a','b'))
    s.snapshot()
    def lose():
        s.upload(d81,'a','d81','readonly');s.upload(d64,'b','d64','readwrite');del m.files['/Temp/temp0001']
    try:s.run(lose)
    except RuntimeError as error:assert 'metadata' in str(error)
    else:raise AssertionError('lost original accepted')
    r=report['restore']
    assert set(r['drive_errors'])=={'a'} and m.state['b']['image_file']=='' and not r['deletions'] and len(r['leftovers'])==2
    cases['session-lost-original-other-drives-restored-files-kept']=True

    # An original that could not be mounted again refuses the run up front.
    m=Machine(a=('/Temp/temp0001',''),files={'/Temp/temp0001':bytes(1000)});s,report,_=session_for(m,work('unknown'))
    try:s.snapshot()
    except RestorationError as error:assert 'image type' in str(error)
    else:raise AssertionError('unrestorable original accepted')
    assert not any(method!='GET' for method,_ in m.sent)
    cases['session-unrestorable-original-refused-before-changes']=True

    # A truncated upload blocks the boot; its stored file is still deleted.
    m=Machine(faults={'short-a'});s,report,_=session_for(m,work('short'))
    s.snapshot()
    def boot():
        s.upload(d64,'a','d64','readonly');m.reset()
    try:s.run(boot)
    except RuntimeError as error:assert 'incomplete' in str(error)
    else:raise AssertionError('short upload accepted')
    assert m.events.count('reset')==1 and m.events[-1]=='reset' and report['restore']['passed']
    assert report['session']['uploads'][0]['path'] and not any(p.startswith('/Temp/') for p in m.files)
    cases['session-short-upload-no-boot-file-deleted']=True

    # A read-only upload that changed is kept for inspection.
    m=Machine();s,report,_=session_for(m,work('changed'))
    s.snapshot()
    def change():
        path=s.upload(d64,'a','d64','readonly',retrieve=True);m.files[path]=b'!'+m.files[path][1:]
    try:s.run(change)
    except RestorationError as error:assert 'changed' in str(error)
    else:raise AssertionError('changed read-only upload deleted')
    r=report['restore']
    assert r['drives_match'] and r['reset_after'] and not r['deletions'] and len(r['leftovers'])==1
    cases['session-changed-readonly-upload-kept']=True

    # A deletion the server acknowledges but does not perform is not confirmed.
    m=Machine();ftp=FTP(m,faults={'delete-ignored'});s,report,_=session_for(m,work('ignored'),ftp=ftp)
    s.snapshot()
    try:s.run(lambda:s.upload(d64,'a','d64','readonly'))
    except RestorationError as error:assert 'still present' in str(error)
    else:raise AssertionError('unconfirmed deletion accepted')
    action=report['restore']['deletions'][0]
    assert action['acknowledged'] and not action['confirmed'] and report['restore']['leftovers']
    cases['session-unconfirmed-deletion-reported']=True

    # Private folder: fixtures read back, claimed outputs retrieved, optional
    # claims may be absent, everything deleted, folder removed.
    m=Machine();s,report,_=session_for(m,work('private'))
    s.snapshot()
    usb='/Usb0/kestrel-native-000000000001'
    def private():
        s.private_dir(usb)
        assert s.private_file(usb+'/NOTE.TXT',b'NOTE')==dict(bytes=4,sha256=hashlib.sha256(b'NOTE').hexdigest(),path=usb+'/NOTE.TXT')
        s.private_file(usb+'/EMPTY.TXT',b'')
        s.claim(usb+'/SAVED.TXT',optional=True);s.claim(usb+'/HISTORY',optional=True)
        m.files[usb+'/SAVED.TXT']=b'SAVED BY THE NATIVE EDITOR'
    s.run(private)
    r=report['restore']
    assert set(s.retrieved)=={usb+'/NOTE.TXT',usb+'/EMPTY.TXT',usb+'/SAVED.TXT'}
    assert s.retrieved[usb+'/SAVED.TXT']==b'SAVED BY THE NATIVE EDITOR' and r['never_created']==[usb+'/HISTORY']
    assert usb not in m.folders and not any(p.startswith(usb) for p in m.files) and r['passed']
    assert [d['kind'] for d in r['deletions']]==['file']*3+['folder']
    cases['session-private-files-retrieved-deleted-folder-removed']=True

    # Only this session's names may be in its folder; otherwise nothing is deleted.
    m=Machine();s,report,_=session_for(m,work('scope'))
    s.snapshot()
    def foreign():
        s.private_dir(usb);s.private_file(usb+'/NOTE.TXT',b'NOTE');m.files[usb+'/OTHER']=b'?'
    try:s.run(foreign)
    except RestorationError as error:assert 'did not create' in str(error)
    else:raise AssertionError('unexpected entry deleted')
    assert report['restore']['unexpected_entries']=={usb:['OTHER']} and not report['restore']['deletions']
    assert usb+'/NOTE.TXT' in m.files and report['restore']['reset_after']
    cases['session-foreign-entry-stops-deletion']=True

    # A fixture that reads back differently fails the check; the partial file
    # is still retrieved and deleted.
    m=Machine();s,report,_=session_for(m,work('fixture'),ftp=None)
    s.ftp=FTP(m,faults={'short-put'})
    s.snapshot()
    def fixture():
        s.private_dir(usb);s.private_file(usb+'/NOTE.TXT',b'NOTE')
    try:s.run(fixture)
    except RuntimeError as error:assert 'read back differ' in str(error)
    else:raise AssertionError('short fixture accepted')
    assert report['restore']['passed'] and usb not in m.folders
    cases['session-fixture-readback-mismatch-cleaned']=True

    # A folder that already exists is never adopted.
    m=Machine(folders={usb});s,report,_=session_for(m,work('exists'))
    s.snapshot()
    try:s.run(lambda:s.private_dir(usb))
    except RuntimeError as error:assert 'already exists' in str(error)
    else:raise AssertionError('existing folder adopted')
    assert usb in m.folders and not report['restore']['deletions'] and not report['session']['private_dirs']
    cases['session-existing-folder-refused-and-kept']=True


class Contexts:
    """DosContexts stand-in: open[c] is the name of the file context c holds."""
    def __init__(self,machine,open=None,*,close_fails=(),silent=()):
        self.m=machine;self.open=dict(open or {});self.close_fails=set(close_fails);self.silent=set(silent);self.log=[]
    def info(self,context):
        self.log.append(('info',context));self.m.events.append(f'dos-info-{context}')
        if context in self.silent:return dict(context=context,command=7,result='no interface',status='',data_hex='',registers_before='0000')
        status='00,OK' if context in self.open else '85,NO FILE OPEN'
        return dict(context=context,command=7,result='complete',status=status,data_hex='',registers_before='00c9')
    def close(self,context):
        self.log.append(('close',context));self.m.events.append(f'dos-close-{context}')
        if context in self.open and context not in self.close_fails:
            del self.open[context];status='00,OK'
        else:status='84,NO FILE TO CLOSE' if context not in self.open else '70,NO CHANNEL'
        return dict(context=context,command=3,result='complete',status=status,data_hex='',registers_before='00c9')


def dos_context_cases(cases,work,d64):
    # Both contexts idle before; the check leaves context 2 holding a file
    # (a failed native CLOSE): restore closes it before deleting files.
    m=Machine();ctx=Contexts(m);s,report,_=session_for(m,work('dos-closed'),dos_contexts=ctx)
    s.snapshot()
    assert [r['status'] for r in report['session']['dos_contexts_before'].values()]==['85,NO FILE OPEN']*2
    def body():
        s.upload(d64,'a','d64','readonly');ctx.open[2]='LARGE COPY.TXT'
    s.run(body)
    r=report['restore']
    assert r['passed'] and r['dos_contexts_idle'] and 2 not in ctx.open
    closed=[e for e in r['dos_contexts'] if 'close' in e]
    assert [e['context'] for e in closed]==[2] and closed[0]['close']['status']=='00,OK'
    assert closed[0]['info_after']['status'].startswith('85')
    assert m.events[-1]=='reset' and m.events.index('dos-close-2')<len(m.events)-1
    cases['session-dos-context-opened-by-check-closed-on-restore']=True

    # A context that already holds a file before the check: refuse, change nothing.
    m=Machine();ctx=Contexts(m,{1:'FOREIGN'});s,report,_=session_for(m,work('dos-busy'),dos_contexts=ctx)
    try:s.snapshot()
    except RuntimeError as error:assert 'DOS context 1' in str(error) and '--close-dos-context 1' in str(error)
    else:raise AssertionError('busy DOS context accepted')
    assert ctx.open=={1:'FOREIGN'} and not any(e.startswith(('upload','mode','unmount')) for e in m.events)
    assert ('close',1) not in ctx.log
    cases['session-dos-context-busy-before-refused-untouched']=True

    # A probe that gets no answer is not taken as idle.
    m=Machine();ctx=Contexts(m,silent={2});s,report,_=session_for(m,work('dos-silent'),dos_contexts=ctx)
    try:s.snapshot()
    except RuntimeError as error:assert 'DOS context 2' in str(error)
    else:raise AssertionError('unanswered DOS context accepted')
    cases['session-dos-context-no-answer-refused']=True

    # CLOSE that does not free the context fails restoration; files are still cleaned.
    m=Machine();ctx=Contexts(m,close_fails={2});s,report,_=session_for(m,work('dos-stuck'),dos_contexts=ctx)
    s.snapshot()
    def stuck():
        s.upload(d64,'a','d64','readonly');ctx.open[2]='LARGE COPY.TXT'
    try:s.run(stuck)
    except RuntimeError as error:assert 'DOS context 2 still holds a file' in str(error)
    else:raise AssertionError('stuck DOS context accepted')
    r=report['restore']
    assert not r['passed'] and not r.get('dos_contexts_idle') and r['cleanup_complete'] and r['reset_after']
    cases['session-dos-context-close-failure-reported']=True


class Interface:
    """The command interface registers ($df1c-$df1f) for the probe in py65."""
    def __init__(self,open_file,busy=False):
        self.state=0x10 if busy else 0;self.cmd=[];self.data=b'';self.status=b'';self.open=open_file
    def r1c(self,_):return self.state|(0x80 if self.data else 0)|(0x40 if self.status else 0)
    def w1c(self,_,value):
        if value&1:
            target,command=self.cmd
            if command==7:
                self.status=b'82,FILE NOT FOUND' if self.open else b'85,NO FILE OPEN'
                self.data=b'\x10\x00\x00\x00ABC' if self.open else b''
            if command==3:
                self.status=b'00,OK' if self.open else b'84,NO FILE TO CLOSE';self.open=False
            self.state=0x20
        if value&2:self.state=0
    def pop(self,name):
        value=getattr(self,name);setattr(self,name,value[1:]);return value[0]


def probe_cases(cases,root):
    from py65.devices.mpu6502 import MPU
    from py65.memory import ObservableMemory
    def run(context,command,interface):
        prg=hw_dos_context.build(root,context,command);base=prg[0]|prg[1]<<8
        mem=ObservableMemory()
        for i,b in enumerate(prg[2:]):mem[base+i]=b
        mem.subscribe_to_read([0xdf1c],interface.r1c);mem.subscribe_to_write([0xdf1c],interface.w1c)
        mem.subscribe_to_read([0xdf1d],lambda _:0xc9);mem.subscribe_to_write([0xdf1d],lambda _,v:interface.cmd.append(v))
        mem.subscribe_to_read([0xdf1e],lambda _:interface.pop('data'))
        mem.subscribe_to_read([0xdf1f],lambda _:interface.pop('status'))
        cpu=MPU(memory=mem,pc=0x0810)
        for _ in range(300000):
            cpu.step()
            if mem[0xc000]==0xaa:break
        else:raise AssertionError('probe did not finish')
        page=bytes(mem[0xc100:0xc200])
        return page[0],page[0x10:0x10+page[1]],page[0x80:0x80+page[2]].decode('latin-1')
    held=Interface(True)
    assert run(2,hw_dos_context.FILE_INFO,held)==(1,b'\x10\x00\x00\x00ABC','82,FILE NOT FOUND') and held.cmd==[2,7]
    held.cmd=[]
    assert run(2,hw_dos_context.CLOSE,held)==(1,b'','00,OK') and held.cmd==[2,3]
    held.cmd=[]
    assert run(2,hw_dos_context.FILE_INFO,held)==(1,b'','85,NO FILE OPEN')
    cases['probe-file-info-close-file-info']=True
    busy=Interface(False,busy=True)
    assert run(1,hw_dos_context.FILE_INFO,busy)==(0xfe,b'','') and busy.cmd==[]
    cases['probe-busy-interface-untouched']=True
    assert hw_dos_context.idle(dict(result='complete',status='85,NO FILE OPEN'))
    assert not hw_dos_context.idle(dict(result='complete',status='82,FILE NOT FOUND'))
    assert not hw_dos_context.idle(dict(result='no interface',status=''))
    cases['probe-idle-only-on-85']=True


def admission_cases(cases):
    from contextlib import contextmanager
    from hw_native_desktop_check import idle_admission
    pauses=[];states=[]
    @contextmanager
    def paused(label):
        pauses.append(label);yield
    def read(address,count):
        state=states[0] if len(states)==1 else states.pop(0)
        return {(0x3d11,2):b'\0\1' if state=='idle' else b'\0\0',(0xd0,1):b'\0'}[(address,count)]
    admissions=[];batch=idle_admission(paused,read,admissions)
    states[:]=['sampling','sampling','idle'];entered=[]
    with batch('frame-before'):entered.append(states[0])
    assert entered==['idle'] and admissions==[dict(label='frame-before',deferred=2)] and len(pauses)==3
    cases['admission-skips-pointer-samples']=True
    pauses.clear();states[:]=['sampling']
    with batch('key-0d'):pass
    assert pauses==['key-0d'] and len(admissions)==1
    cases['admission-other-batches-pause-once']=True
    states[:]=['sampling'];bounded=idle_admission(paused,read,admissions,bound=.05)
    try:
        with bounded('frame-restore'):raise AssertionError('entered while sampling')
    except AssertionError as error:assert error.args[0][0]=='idle capture admission',error
    else:raise AssertionError('never-idle workspace admitted')
    cases['admission-bounded']=True


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path);args=parser.parse_args()
    report=dict(passed=False,hardware_io=False,cases={})
    try:
        client_cases(report['cases'])
        with tempfile.TemporaryDirectory(prefix='kestrel-session-tests-') as folder:
            session_cases(report['cases'],folder)
            probe_cases(report['cases'],folder)
            d64=bytes((i*3)&255 for i in range(174848))
            def work(label):
                path=Path(folder)/label;path.mkdir();return path
            dos_context_cases(report['cases'],work,d64)
        admission_cases(report['cases'])
        report['passed']=True
    finally:
        if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(f'PASS: {len(report["cases"])} upload and session restoration cases; no hardware I/O')


if __name__=='__main__':main()
