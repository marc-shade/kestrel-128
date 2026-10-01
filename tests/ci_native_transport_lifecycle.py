#!/usr/bin/env python3
"""A failed focused capture must restore the drives and clean up before its
error returns; failed restoration or a changed upload keeps the upload.

hw_native_desktop_check.run against the simulated Ultimate and FTP server of
ci_hardware_uploads (no hardware I/O)."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tests'))
import hw_native_desktop_check as lifecycle
import hw_session
from ci_hardware_uploads import Machine,FTP


class Capture:
    def __init__(self,*args,**kwargs):self.records=[]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args();result=dict(passed=False,physical_hardware_io=False,cases=[])
    # The hardware script pins the images it was qualified with; this offline
    # lifecycle check exercises the current build's images instead.
    images={name:hashlib.sha256((ROOT/'target/native-desktop'/f).read_bytes()).hexdigest()
            for name,f in (('disk','kestrel.d64'),('kernel','kestrel.prg'))}
    disk=(ROOT/'target/native-desktop/kestrel.d64').read_bytes()
    original=bytes((i*5)&255 for i in range(174848))
    for fault in (None,'workflow','restore','readback','keep-on-failure','preflight'):
        with tempfile.TemporaryDirectory(prefix='kestrel-transport-lifecycle-') as temporary:
            work=Path(temporary)
            m=Machine(a=('/Temp/temp0098',''),files={'/Temp/temp0098':original})
            ftp=FTP(m)
            def workflow(mon,capture,work,disk,report,save):
                m.events.append('workflow')
                assert m.ram[0x1c13:0x1c19]==b'KES128','workflow ran before the reset'
                upload=report['native_disk_upload_path']
                assert m.files[upload]==disk.read_bytes() and m.mounted('a')==upload
                if fault=='restore':del m.files['/Temp/temp0098']
                if fault=='readback':m.files[upload]=b'!'+m.files[upload][1:]
                if fault in ('workflow','keep-on-failure'):raise RuntimeError('original capture failure')
                report['native_checks_passed']=True;save()
            def preflight(ult,mon,work,report,save):
                m.events.append('preflight')
                if fault=='preflight':raise RuntimeError('preflight refused')
            def session(ult,work,report,save,drives,dos_contexts=None):
                return hw_session.HardwareSession(ult,work,report,save,drives=drives,ftp=ftp,dos_contexts=dos_contexts)
            with patch.object(lifecycle.tempfile,'mkdtemp',return_value=str(work)), \
                 patch.object(lifecycle,'NativeCapture',Capture), \
                 patch.object(lifecycle,'HardwareSession',session), \
                 patch.object(lifecycle,'quiet_boot',lambda _:None):
                try:lifecycle.run(m,workflow=workflow,cleanup_after_failure=fault!='keep-on-failure',
                                  expected_images=images,preflight=preflight)
                except (RuntimeError,AssertionError) as error:
                    assert fault is not None,error
                    message=str(error)
                else:assert fault is None;message=None
            report=json.loads((work/'report.json').read_text())
            assert report['passed']==(fault is None)
            uploads=[p for p in m.files if p.startswith('/Temp/') and p!='/Temp/temp0098']
            if fault=='preflight':
                assert message=='preflight refused' and report['preflight_error']['message']==message
                assert m.events==['preflight'] and 'restore' not in report and not uploads
                assert not any(method!='GET' for method,_ in m.sent)
                result['cases'].append(dict(fault=fault,error=message,events=m.events,passed=True));continue
            assert m.events[:5]==['preflight','upload-a','reset','workflow','remount-a:/Temp/temp0098:d64'] or \
                   (fault=='restore' and m.events[:4]==['preflight','upload-a','reset','workflow'])
            restore=report['restore']
            if fault in (None,'workflow'):
                assert restore['passed'] and restore['cleanup_complete'] and not uploads
                assert m.state['a']['image_file']=='/Temp/temp0098' and m.events[-1]=='reset'
                assert restore['retrieved'][report['native_disk_upload_path']]['sha256']==hashlib.sha256(disk).hexdigest()
                assert all(d['confirmed'] for d in restore['deletions']) and report['images_unchanged']
                if fault=='workflow':assert message=='original capture failure' and report['native_error']==message
                else:assert report['cleanup_complete']
            elif fault=='keep-on-failure':
                assert message=='original capture failure' and restore['drives_match'] and restore['reset_after']
                assert not restore['cleanup_requested'] and uploads==restore['leftovers'] and not restore['deletions']
            else:
                assert not restore['passed'] and uploads==restore['leftovers'] and not restore['deletions']
                if fault=='restore':
                    assert 'metadata' in restore['drives_error'] and not restore['reset_after']
                    assert m.mounted('a')==report['native_disk_upload_path']
                if fault=='readback':
                    assert 'changed' in restore['cleanup_error'] and restore['drives_match'] and restore['reset_after']
            result['cases'].append(dict(fault=fault,error=message,events=m.events,
                cleanup_complete=restore['cleanup_complete'],leftovers=restore['leftovers'],passed=True))
    result['passed']=True;args.report.write_text(json.dumps(result,indent=2)+'\n')
    print(f'PASS: {len(result["cases"])} lifecycle cases: successful and failed workflows restore and clean up; '
          'failed restoration or a changed upload keeps the upload; no hardware I/O')


if __name__=='__main__':main()
