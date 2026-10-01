#!/usr/bin/env python3
"""Reclaim after a restoration that stopped partway (e.g. a lost DELE reply
during an interrupted editor save's cleanup), without hardware.

The session's own restore() drives the Machine/FTP of ci_hardware_uploads
until a deletion fails; reclaim must skip what the report confirms deleted,
never re-delete a path whose earlier DELE was sent, compare every remaining
file with the check's own earlier retrieval, and delete the rest."""
import argparse
import json
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from hw_session import HardwareSession,RestorationError
import hw_native_usb_recovery as recovery
from ci_hardware_uploads import Machine,FTP

FOLDER='/Usb0/kestrel-native-0000000reopen'
DISK=bytes((i*11)&255 for i in range(174848))
LARGE=(b'0123456789 ABCDEFGHIJKLMNOPQRSTUVWXYZ\r\n'*1800)[:66053]
SAVED=LARGE[:65537]+b'C12'+LARGE[65537:]


class StopAfter(FTP):
    """Loses the reply of the n-th DELE (the file is deleted server-side)."""
    def __init__(self,machine,n):
        super().__init__(machine);self.n=n;self.dele=0
    def delete(self,path):
        self.dele+=1
        super().delete(path)
        if self.dele==self.n:raise TimeoutError('DELE reply lost')


def interrupted(work,*,lose_at):
    machine=Machine(a=('/Temp/temp0001',''),files={'/Temp/temp0001':bytes(174848)})
    ftp=StopAfter(machine,lose_at);report={}
    def save():(work/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    session=HardwareSession(machine,work,report,save,drives=('a',),ftp=ftp)
    session.snapshot()
    def body():
        session.private_dir(FOLDER)
        session.private_file(FOLDER+'/LARGE.TXT',LARGE)
        session.private_file(FOLDER+'/NOTE.TXT',b'NOTE')
        session.claim(FOLDER+'/LARGE COPY.TXT',optional=True)
        session.upload(DISK,'a','d64','readwrite',retrieve=True)
        machine.files[FOLDER+'/LARGE COPY.TXT']=SAVED           # the native editor's save
        raise AssertionError('native reopen in the second DOS context failed')
    try:session.run(body)
    except AssertionError as error:assert 'second DOS context' in str(error)
    else:raise AssertionError('check error lost')
    return machine,ftp,report


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path);args=parser.parse_args()
    cases={}
    with tempfile.TemporaryDirectory(prefix='kestrel-reopen-reclaim-') as temporary:
        root=Path(temporary)
        # The second DELE's reply is lost: restore() stops there.
        w=root/'resume';w.mkdir()
        machine,ftp,report=interrupted(w,lose_at=2)
        restore=report['restore']
        assert restore['drives_match'] and restore['reset_after'] and not restore['passed']
        assert [d['confirmed'] for d in restore['deletions']]==[True,False]
        assert restore['retrieved'][FOLDER+'/LARGE COPY.TXT']['bytes']==66056
        first,second=(d['path'] for d in restore['deletions'])
        assert (first,second)==(FOLDER+'/LARGE COPY.TXT',FOLDER+'/NOTE.TXT') and second not in machine.files
        ftp.log.clear();machine.sent.clear()
        journal=recovery.reclaim(machine,w/'report.json',ftp=FTP(machine))
        assert journal['passed'] and not journal['drives_put_back'] and journal['skipped_confirmed']==[first]
        deleted=[d['path'] for d in journal['deletions']]
        assert first not in deleted and second not in deleted,'a deletion was replayed'
        assert journal['absent']==[second]
        upload=report['session']['uploads'][0]['path']
        assert deleted==[FOLDER+'/LARGE.TXT',upload,FOLDER] and all(d['confirmed'] for d in journal['deletions'])
        assert FOLDER not in machine.folders and upload not in machine.files
        assert not any(method!='GET' for method,_ in machine.sent),'drive A was touched although it was restored'
        cases['resume-skips-confirmed-and-sent-deletions']=True

        # A saved output that changed after the check retrieved it is not deleted.
        w=root/'changed';w.mkdir()
        machine,ftp,report=interrupted(w,lose_at=1)
        assert report['restore']['deletions'][0]['path']==FOLDER+'/LARGE COPY.TXT'
        machine.files[FOLDER+'/LARGE COPY.TXT']=SAVED[:-1]      # someone rewrote it since
        try:recovery.reclaim(machine,w/'report.json',ftp=FTP(machine))
        except RestorationError as error:assert "check's own retrieval" in str(error)
        else:raise AssertionError('changed output deleted')
        journal=json.loads((w/'reclaim.json').read_text())
        assert not journal['deletions'] and FOLDER+'/LARGE.TXT' in machine.files
        cases['output-changed-since-retrieval-refused']=True

        # A read-write upload may legitimately differ from what was uploaded.
        w=root/'readwrite';w.mkdir()
        machine,ftp,report=interrupted(w,lose_at=1)
        upload=report['session']['uploads'][0]['path']
        assert machine.files[upload]==DISK
        machine.files[upload]=b'W'+DISK[1:]
        assert upload in report['restore']['retrieved']
        try:recovery.reclaim(machine,w/'report.json',ftp=FTP(machine))
        except RestorationError as error:assert "check's own retrieval" in str(error)
        else:raise AssertionError('upload changed after retrieval was deleted')
        cases['readwrite-upload-compared-with-own-retrieval']=True
    report=dict(passed=True,hardware_io=False,cases=cases)
    if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(f'PASS: {len(cases)} interrupted-restoration reclaim checks; no hardware I/O')


if __name__=='__main__':main()
