"""Physical native editor on system/data D64s, with independent data readback.

Drives A and B are recorded. B must be enabled as a 1541 on IEC 9 with no
image (the workflow's data drive). A private native disk is mounted on A and a
private data disk on B, both read-write. Afterwards both drives get their
original image and mode back; both images, now unmounted, are retrieved over
FTP before they are deleted and confirmed absent; the C128 is reset
(hw_session.py). The retrieved data disk is the byte oracle.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from hw_storage_check import HardwareMonitor
from hw_native_check import hashes,quiet_boot
from hw_session import HardwareSession
from hw_dos_context import DosContexts
from native_editor_check import EditorClient,prepare_editor,editor_workflow
from native_capture import wait
from native_files_check import exact_d64_files


def run(ult,*,dos_contexts=False):
    work=Path(tempfile.mkdtemp(prefix='kestrel-hardware-native-editor-'))
    print(f'Native editor hardware evidence: {work}',flush=True)
    disk,data_disk,fixtures=prepare_editor(work)
    mon=HardwareMonitor(ult);client=EditorClient(mon,work,quiet=4,scan_quiet=30,capture_quiet=2,poll=2,key_timeout=1800)
    read=client.read
    report=dict(passed=False,build=hashes(),host=ult.host,
                native_disk_sha256=hashlib.sha256(disk.read_bytes()).hexdigest(),
                data_disk_sha256=hashlib.sha256(data_disk.read_bytes()).hexdigest(),
                host_request_timeout_seconds=ult.timeout,uncertain_host_writes=ult.uncertain_writes,
                host_connect_attempts=ult.connect_attempts,host_connect_failures=ult.connect_failures,
                host_control_requests=ult.control_requests,host_upload_checks=ult.upload_checks,
                quiet_seconds=dict(boot=60,scan_or_app=30,key=4,capture=2,poll=2),key_timeout_seconds=1800)
    def save():(work/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    ult.record_event=save
    save()
    session=HardwareSession(ult,work,report,save,drives=('a','b'),
        dos_contexts=DosContexts(ult,work) if dos_contexts else None)
    before=session.snapshot();assert before['a']['enabled'] and before['a']['bus_id']==8
    assert before['b']['enabled'] and before['b']['bus_id']==9 and before['b']['type']=='1541'
    assert not before['b']['image_file'],'native editor workflow requires an initially empty drive B'
    (work/'ultimate-version.json').write_text(json.dumps(json.loads(ult.version()),indent=2)+'\n')
    def body():
        try:
            report['data_disk_path']=session.upload(data_disk.read_bytes(),'b','d64','readwrite',retrieve=True);save()
            report['native_disk_path']=session.upload(disk.read_bytes(),'a','d64','readwrite',retrieve=True);save()
            ult.reset();quiet_boot('Native editor boot')
            wait(lambda:read(0x1c13,6)==b'KES128' and read(0x3d12)==b'\1','native editor boot',120)
            editor_workflow(client,disk,data_disk,fixtures,0,report,save)
        except BaseException as error:
            report['error']=str(error)
            try:
                (work/'failure-context.bin').write_bytes(read(0x3d00,0xe4))
                (work/'failure-vic.bin').write_bytes(read(0x400,1000))
            except Exception as diagnostic:report['diagnostic_error']=str(diagnostic)
            raise
    try:session.run(body)
    finally:report['images_unchanged']=report['build']==hashes();save()
    (work/'editor-readback.d64').write_bytes(session.retrieved[report['data_disk_path']])
    verify_readback(work,report,save)
    assert report['images_unchanged'] and not report['uncertain_host_writes']
    report['passed']=True;save()
    print(f'HW-NATIVE-EDITOR PASS; files independently verified; drives restored, uploads deleted; {work}',flush=True)


def verify_readback(work,report,save):
    """Compare the retrieved, closed data D64 with the fixtures plus SAVED."""
    assert report.get('native_checks_passed') and report['restore']['passed']
    separate='data_disk_path' in report
    original_disk=(work/('documents.d64' if separate else 'native.d64')).read_bytes()
    assert hashlib.sha256(original_disk).hexdigest()==report['data_disk_sha256' if separate else 'native_disk_sha256']
    wanted=(work/'saved-expected.seq').read_bytes()
    assert len(wanted)==report['saved_bytes'] and hashlib.sha256(wanted).hexdigest()==report['saved_sha256']
    expected=exact_d64_files(original_disk);expected[b'SAVED']=(1,wanted)
    output=work/'editor-readback.d64'
    try:
        data=output.read_bytes();actual=exact_d64_files(data)
        assert actual==expected,'stored files differ from fixtures plus verified edited document'
        sector_zero_unchanged=data[:256]==original_disk[:256]
        # Sector zero is reserved only on the older combined system/data
        # fixture. The separate document disk may legitimately allocate it.
        if not separate:assert sector_zero_unchanged,'native boot block changed'
        comparisons=0
        for name,(kind,content) in expected.items():
            if not content:continue
            destination=work/('readback-'+name.decode()+'.bin')
            spec=name.decode().lower()+','+{1:'s',2:'p',3:'u'}[kind]+',r'
            subprocess.run(['c1541','-attach',str(output),'-read',spec,str(destination)],check=True,capture_output=True)
            assert destination.read_bytes()==content,name
            comparisons+=1
        report['independent_readback']=dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),
                                           exact_files=len(actual),c1541_nonempty_files=comparisons,
                                           empty_stored_bytes=len(actual[b'EMPTY'][1]),initial_sector_zero_unchanged=sector_zero_unchanged,
                                           data_disk_on_device_9=separate,
                                           saved_bytes=len(wanted),saved_sha256=hashlib.sha256(wanted).hexdigest(),
                                           source='FTP retrieval of the unmounted private upload')
    except BaseException as error:
        report['readback_error']=str(error)
        raise
    finally:save()
