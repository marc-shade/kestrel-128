"""Native IEC and calculator export on C128; independent readback.

Drive A is recorded; two private D64s (the native disk for the calculator
export, then the file-client disk) are mounted on it read-write. Afterwards
drive A gets its original image and mode back, both images, now unmounted,
are retrieved over FTP before they are deleted and confirmed absent, and the
C128 is reset (hw_session.py). The retrieved images are the byte oracle.
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
from hwlib import lst_symbol
from native_capture import NativeCapture,calculator_screen,wait,ROOT
from native_files_check import NativeFiles,prepare,workflow,exact_d64_files


def run(ult,*,dos_contexts=False):
    work=Path(tempfile.mkdtemp(prefix='kestrel-hardware-native-files-'))
    print(f'Native file hardware evidence: {work}',flush=True)
    disk,fixtures=prepare(work,size=1557)
    mon=HardwareMonitor(ult);client=NativeFiles(mon,work,quiet=4,open_quiet=15)
    capture=NativeCapture(mon,work)
    report=dict(passed=False,build=hashes(),host=ult.host,
                captures=capture.records,quiet_seconds=dict(boot=60,app_load=30,open=15,transfer=4),
                uncertain_host_writes=ult.uncertain_writes,host_control_requests=ult.control_requests,
                host_upload_checks=ult.upload_checks)
    def save():(work/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    ult.record_event=save
    def read(address,count=1):return client.read_ram(address,count)
    session=HardwareSession(ult,work,report,save,drives=('a',),
        dos_contexts=DosContexts(ult,work) if dos_contexts else None)
    before=session.snapshot();assert before['a']['enabled'] and before['a']['bus_id']==8
    (work/'ultimate-version.json').write_text(ult.version())
    def body():
        try:
            report['calculator_disk_path']=session.upload((ROOT/'target/native/kestrel.d64').read_bytes(),
                                                          'a','d64','readwrite',retrieve=True);save()
            ult.reset();quiet_boot('Native calculator export boot')
            wait(lambda:read(0x1c13,6)==b'KES128' and read(0x3d12)==b'\1','native boot',120)
            print('Loading native calculator; 30 seconds without RAM DMA',flush=True)
            client.key(ord('C'),expected=None,quiet=30)
            for key in b'12+30=S':client.key(key,expected=None)
            for key in b'PHYSHIST':client.key(key,expected=None)
            client.key(13,expected=None,quiet=20)
            assert capture.capture('save-status',address=lst_symbol('native/calc','save_status'),count=1)==b'\1',read(0x3d80,32).hex()
            assert read(0x98)==b'\0' and read(0x3de0,4)==bytes(4)
            for label,status in [('calculator-saved','HISTORY SAVED AND VERIFIED'),
                                 ('calculator-existing','FILE EXISTS - CHOOSE ANOTHER NAME')]:
                if label=='calculator-existing':
                    for key in b'SPHYSHIST':client.key(key,expected=None)
                    client.key(13,expected=None,quiet=15)
                    assert capture.capture('existing-status',address=lst_symbol('native/calc','save_status'),count=1)==b'\3'
                vic=read(0x400,1000);(work/(label+'-vic.bin')).write_bytes(vic)
                vdc=capture.capture(label+'-vdc',mode=1)
                repeat=capture.capture(label+'-vdc-repeat',mode=1)
                assert vdc==repeat and vic==calculator_screen(40,'42',['42'],save_status=status)
                assert vdc==calculator_screen(80,'42',['42'],save_status=status)
                save()
            client.key(27,expected=None)
            assert read(0x3d0e,3)==bytes([175,251,32]) and read(0x98)==b'\0'
            report['calculator_save_reopen_compare_and_exclusive_rejection']=True;save()

            report['files_disk_path']=session.upload(disk.read_bytes(),'a','d64','readwrite',retrieve=True);save()
            print('Loading native file client; 30 seconds without RAM DMA',flush=True)
            client.key(ord('C'),expected=None,quiet=30)
            workflow(client,fixtures,report,save)
            report['native_checks_passed']=True
        except BaseException as error:
            report['error']=str(error)
            for label,address,count in [('files',0x3d80,0x64),('app',0x6000,4096),('kernel',0x1c00,0x1c00)]:
                try:(work/f'failure-{label}.bin').write_bytes(read(address,count))
                except Exception as diagnostic:report['diagnostic_error']=str(diagnostic)
            raise
    try:session.run(body)
    finally:report['images_unchanged']=report['build']==hashes();save()
    for label in ('calculator','files'):
        (work/(label+'-readback.d64')).write_bytes(session.retrieved[report[label+'_disk_path']])
    readback(work,report,fixtures,save)
    assert report['images_unchanged'] and not report['uncertain_host_writes']
    report['passed']=True;save()
    print(f'HW-NATIVE-FILES PASS; exported history and binary files independently verified; drives restored, uploads deleted; {work}',flush=True)


def readback(work,report,fixtures,save):
    """The native stream itself is not the byte oracle: the complete, closed
    D64s retrieved after unmounting are, with their linked sectors inspected
    independently and every nonempty file cross-checked with c1541."""
    assert report.get('native_checks_passed') and report['restore']['passed']
    try:
        for label,expected in [('calculator',{'physhist':b'42\r'}),
                               ('files',{**fixtures,'copy':fixtures['source']})]:
            verify_disk(work,label,expected,report)
            save()
    except BaseException as error:
        report['readback_error']=str(error)
        raise
    finally:save()


def verify_disk(work,label,expected,report):
    retrieved=work/(label+'-readback.d64');data=retrieved.read_bytes()
    files=exact_d64_files(data);c1541_matches=0
    for name,content in expected.items():
        kind='u' if name=='user' else 'p' if name=='program' else 's'
        assert files[name.upper().encode()]==({'s':1,'p':2,'u':3}[kind],content),(label,name,'linked sectors')
        out=work/(label+'-'+name+'-c1541.bin')
        subprocess.run(['c1541','-attach',str(retrieved),'-read',name+','+kind+',r',str(out)],check=True,capture_output=True)
        if content:
            assert out.read_bytes()==content,(label,name);c1541_matches+=1
        else:
            # c1541 itself returns padding for an empty SEQ. Retain its exact
            # output and independently require the stored sector extent=0.
            report['c1541_empty_extraction']=dict(stored_bytes=0,extracted_bytes=out.stat().st_size,
                sha256=hashlib.sha256(out.read_bytes()).hexdigest())
    report.setdefault('independent_readback',{})[label]=dict(bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),files_verified=len(expected),
        linked_sector_files=len(expected),c1541_nonempty_files=c1541_matches)
