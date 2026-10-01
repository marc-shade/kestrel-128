"""Physical native browser workflow on a private D64, with independent readback.

Drive A is recorded and the private disk is mounted on it read-write. After
the workflow drive A gets its original image and mode back, and the private
disk, now unmounted, is retrieved over FTP before it is deleted and confirmed
absent; the C128 is reset (hw_session.py). The retrieved image is the byte
oracle: its linked sectors and every nonempty file (through c1541) must equal
the fixtures plus the exported history.
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
from native_browser_check import BrowserClient,prepare_browser,disk_records,browser_workflow
from native_capture import wait
from native_files_check import exact_d64_files


def run(ult,*,dos_contexts=False):
    work=Path(tempfile.mkdtemp(prefix='kestrel-hardware-native-browser-'))
    print(f'Native browser hardware evidence: {work}',flush=True)
    disk,data_disk,fixtures=prepare_browser(work)
    records=disk_records(data_disk.read_bytes())
    mon=HardwareMonitor(ult);client=BrowserClient(mon,work,quiet=4,scan_quiet=30,capture_quiet=2)
    read=client.read
    report=dict(passed=False,build=hashes(),host=ult.host,
                native_disk_sha256=hashlib.sha256(disk.read_bytes()).hexdigest(),
                quiet_seconds=dict(boot=60,scan_or_app=30,key=4,capture=2),
                uncertain_host_writes=ult.uncertain_writes,host_control_requests=ult.control_requests,
                host_upload_checks=ult.upload_checks)
    def save():(work/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    ult.record_event=save
    session=HardwareSession(ult,work,report,save,drives=('a',),
        dos_contexts=DosContexts(ult,work) if dos_contexts else None)
    before=session.snapshot();assert before['a']['enabled'] and before['a']['bus_id']==8
    (work/'ultimate-version.json').write_text(json.dumps(json.loads(ult.version()),indent=2)+'\n')
    def body():
        try:
            report['native_disk_path']=session.upload(disk.read_bytes(),'a','d64','readwrite',retrieve=True);save()
            ult.reset();quiet_boot('Native browser boot')
            wait(lambda:read(0x1c13,6)==b'KES128' and read(0x3d12)==b'\1','native browser boot',120)
            browser_workflow(client,records,fixtures,0,report,save)
        except BaseException as error:
            report['error']=str(error)
            try:
                (work/'failure-context.bin').write_bytes(read(0x3d00,0xe4))
                (work/'failure-vic.bin').write_bytes(read(0x400,1000))
            except Exception as diagnostic:report['diagnostic_error']=str(diagnostic)
            raise
    try:session.run(body)
    finally:report['images_unchanged']=report['build']==hashes();save()
    output=work/'browser-readback.d64'
    output.write_bytes(session.retrieved[report['native_disk_path']])
    verify_readback(work,report,save)
    assert report['images_unchanged'] and not report['uncertain_host_writes']
    report['passed']=True;save()
    print(f'HW-NATIVE-BROWSER PASS; files independently verified; drives restored, upload deleted; {work}',flush=True)


def verify_readback(work,report,save):
    """Compare the retrieved, closed D64 with the fixtures plus BROWSAVE."""
    assert report.get('native_checks_passed') and report['restore']['passed']
    original_disk=(work/'native.d64').read_bytes()
    assert hashlib.sha256(original_disk).hexdigest()==report['native_disk_sha256']
    expected=exact_d64_files(original_disk);expected[b'BROWSAVE']=(1,b'42\r')
    output=work/'browser-readback.d64'
    try:
        data=output.read_bytes();actual=exact_d64_files(data)
        assert actual==expected,'stored files differ from fixtures plus verified history export'
        assert data[:256]==original_disk[:256],'native boot block changed'
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
                                           empty_stored_bytes=len(actual[b'EMPTY'][1]),boot_block_unchanged=True,
                                           source='FTP retrieval of the unmounted private upload')
    except BaseException as error:
        report['readback_error']=str(error)
        raise
    finally:save()
