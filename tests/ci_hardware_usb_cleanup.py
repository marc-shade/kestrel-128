#!/usr/bin/env python3
"""Reclaiming a failed check's private files: exact scope and no replay.

hw_native_usb_recovery.reclaim reads a check's report.json. Here the reports
come from real hw_session.HardwareSession runs against Machine/FTP
(ci_hardware_uploads) that stopped before or during their restoration.
No hardware I/O."""
import argparse
import copy
import json
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from hw_session import HardwareSession,RestorationError
import hw_native_usb_recovery as recovery
from ci_hardware_uploads import Machine,FTP

FOLDER='/Usb0/kestrel-native-00000000abcd'
DISK=bytes((i*11)&255 for i in range(174848))


def crashed_run(work,*,faults=()):
    """A check that uploaded to A and stored fixtures, then died before restore()."""
    machine=Machine(faults=faults);ftp=FTP(machine)
    report={}
    def save():(work/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    session=HardwareSession(machine,work,report,save,drives=('a',),ftp=ftp)
    before=session.snapshot()
    session.private_dir(FOLDER)
    session.private_file(FOLDER+'/NOTE.TXT',b'NOTE BYTES')
    session.private_file(FOLDER+'/EMPTY.TXT',b'')
    session.claim(FOLDER+'/HISTORY',optional=True)
    upload=session.upload(DISK,'a','d64','readonly',retrieve=True)
    machine.reset()
    machine.files[FOLDER+'/HISTORY']=b'42\r'                 # saved by the native app
    machine.events.clear();machine.sent.clear();ftp.log.clear()
    return machine,ftp,before,upload


def reclaim(machine,ftp,work):
    return recovery.reclaim(machine,work/'report.json',ftp=ftp)


def expect_refusal(action,text,errors=(AssertionError,RestorationError)):
    try:action()
    except errors as error:
        assert text in str(error),(text,str(error));return str(error)
    raise AssertionError('accepted: '+text)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path);args=parser.parse_args()
    cases={}
    with tempfile.TemporaryDirectory(prefix='kestrel-reclaim-tests-') as temporary:
        root=Path(temporary)
        def work(label):
            path=root/label;path.mkdir();return path

        # A crashed run: drive A still holds the upload. It is put back, the
        # C128 reset, every file retrieved and compared, then deleted.
        w=work('crashed');machine,ftp,before,upload=crashed_run(w)
        journal=reclaim(machine,ftp,w)
        assert journal['passed'] and journal['drives_put_back']==['a'] and journal['reset_after']
        assert machine.state['a']==before['a'] and machine.events==['unmount-a','reset']
        assert set(journal['retrieved'])=={FOLDER+'/NOTE.TXT',FOLDER+'/EMPTY.TXT',FOLDER+'/HISTORY',upload}
        assert [d['path'] for d in journal['deletions']]==[FOLDER+'/HISTORY',FOLDER+'/EMPTY.TXT',FOLDER+'/NOTE.TXT',upload,FOLDER]
        assert all(d['confirmed'] for d in journal['deletions'])
        assert FOLDER not in machine.folders and upload not in machine.files
        assert json.loads((w/'reclaim.json').read_text())==journal
        cases['crashed-run-drive-put-back-files-retrieved-and-deleted']=True

        # A second attempt is refused before any request.
        deletes=[entry for entry in ftp.log if entry[0]=='delete'];machine.sent.clear()
        expect_refusal(lambda:reclaim(machine,ftp,w),'already attempted')
        assert not machine.sent and [entry for entry in ftp.log if entry[0]=='delete']==deletes
        cases['second-reclaim-refused-no-replay']=True

        # Reports that are not a failed session run are refused.
        w=work('scope');machine,ftp,before,upload=crashed_run(w)
        original=json.loads((w/'report.json').read_text())
        for label,change,text in (
                ('restore-passed',lambda r:r.update(restore=dict(passed=True)),'nothing to reclaim'),
                ('no-session',lambda r:r.pop('session'),'no hardware session'),
                ('upload-outside-temp',lambda r:r['session']['uploads'][0].update(path='/Usb0/disk.d64'),'outside /Temp'),
                ('folder-outside-usb',lambda r:r['session']['private_dirs'][0].update(path='/Flash/x'),'outside /Usb0'),
                ('file-outside-folder',lambda r:r['session']['private_files'][0].update(path='/Usb0/NOTE.TXT'),'outside the private folders')):
            altered=copy.deepcopy(original);change(altered)
            (w/'report.json').write_text(json.dumps(altered))
            expect_refusal(lambda:reclaim(machine,ftp,w),text)
            assert not (w/'reclaim.json').exists() and not machine.sent
            cases['refuse-'+label]=True

        # A name the check did not record: nothing is deleted.
        w=work('foreign');machine,ftp,before,upload=crashed_run(w)
        machine.files[FOLDER+'/OWNER.TXT']=b'not ours'
        expect_refusal(lambda:reclaim(machine,ftp,w),'did not record')
        journal=json.loads((w/'reclaim.json').read_text())
        assert not journal['passed'] and not journal['deletions'] and FOLDER+'/OWNER.TXT' in machine.files
        cases['refuse-unrecorded-entry-nothing-deleted']=True

        # A fixture that no longer has its stored bytes: nothing is deleted.
        w=work('changed');machine,ftp,before,upload=crashed_run(w)
        machine.files[FOLDER+'/NOTE.TXT']=b'NOTE BYTEX'
        expect_refusal(lambda:reclaim(machine,ftp,w),'differs from what was stored')
        assert not json.loads((w/'reclaim.json').read_text())['deletions'] and upload in machine.files
        cases['refuse-changed-fixture-nothing-deleted']=True

        # The owner has since mounted another image on A: it is left alone.
        w=work('owner');machine,ftp,before,upload=crashed_run(w)
        machine.files['/Usb0/mine.d64']=bytes(174848);machine.state['a'].update(image_file='mine.d64',image_path='/Usb0/')
        journal=reclaim(machine,ftp,w)
        assert journal['passed'] and not journal['drives_put_back'] and 'reset' not in machine.events
        assert machine.mounted('a')=='/Usb0/mine.d64' and upload not in machine.files
        cases['drive-with-owner-image-left-alone']=True

        # A lost DELE reply leaves that deletion unacknowledged; the run stops.
        w=work('lost');machine,ftp,before,upload=crashed_run(w)
        ftp.faults.add('lost-delete-reply')
        expect_refusal(lambda:reclaim(machine,ftp,w),'reply lost',TimeoutError)
        journal=json.loads((w/'reclaim.json').read_text())
        assert len(journal['deletions'])==1 and journal['deletions'][0]['started'] and not journal['deletions'][0]['acknowledged']
        assert 'reply lost' in journal['error']
        ftp.faults.clear()
        expect_refusal(lambda:reclaim(machine,ftp,w),'already attempted')
        cases['lost-delete-reply-recorded-not-replayed']=True
    report=dict(passed=True,hardware_io=False,cases=cases)
    if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(f'PASS: {len(cases)} reclaim scope and acknowledgement checks; no hardware I/O')


if __name__=='__main__':main()
