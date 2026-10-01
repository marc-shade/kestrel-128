#!/usr/bin/env python3
"""Ultimate II+ REST clients for the reference-C128 hardware checks, and the
command line that starts each native check.

Every check records the Ultimate's drives, works only with private uploads and
files, and restores the drives exactly afterwards (hw_session.py). The
Ultimate's address comes from --host or the KESTREL_ULTIMATE_HOST environment
variable; there is no default.
"""
import argparse
import hashlib
import http.client
import json
from pathlib import Path
import sys
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT/'tests')]
from cbm_tools import DEFAULT_HOST, Ultimate  # noqa: E402


def resolve_host(host=None):
    host = host or DEFAULT_HOST
    if not host:
        raise SystemExit('FAIL: no Ultimate address: pass --host or set KESTREL_ULTIMATE_HOST')
    return host


class ObservingUltimate(Ultimate):
    """Retry read-only observations; never replay navigation/DMA writes."""
    read_retries = 0

    def __init__(self,host=None,timeout=25.0):
        super().__init__(resolve_host(host),timeout)
        self.uncertain_writes=[]

    def write_mem(self,address,data):
        assert len(data)<=128
        try:return super().write_mem(address,data)
        except SystemExit as error:
            self.uncertain_writes.append(dict(address=address,bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest(),replayed=False))
            raise RuntimeError(f'Host RAM write at ${address:04x} ({len(data)} bytes) failed; acceptance unknown; not replayed') from error

    def read_mem(self, address, length):
        url = f'http://{self.host}/v1/machine:readmem?address={address:04X}&length={length}'
        for attempt in range(3):
            try:
                with urllib.request.urlopen(url, timeout=self.timeout) as response:
                    data = response.read()
                assert len(data) >= length, f'Short RAM observation at {address:#x}'
                return data[:length]
            except OSError as error:
                if attempt == 2:
                    raise RuntimeError(f'RAM observation at {address:#x} failed after three attempts') from error
                self.read_retries += 1
                print(f'Retrying RAM observation at ${address:04x}: {error}', flush=True)
                time.sleep(1)


class ConnectingUltimate(ObservingUltimate):
    """Retry TCP establishment only, before sending any HTTP request bytes."""
    connect_attempts=3

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.connect_failures=[]

    def _call(self,method,path,data=None):
        endpoint=urllib.parse.urlsplit(path).path
        for attempt in range(self.connect_attempts):
            connection=http.client.HTTPConnection(self.host,timeout=self.timeout)
            try:connection.connect()
            except OSError as error:
                connection.close()
                self.connect_failures.append(dict(method=method,endpoint=endpoint,
                    attempt=attempt+1,request_sent=False,error=str(error)))
                if attempt+1==self.connect_attempts:
                    raise RuntimeError(f'Ultimate TCP connection failed before {method} {endpoint}; no request sent') from error
                print(f'Retrying TCP connection before {method} {endpoint}; no request sent',flush=True)
                time.sleep(1)
                continue
            break
        # No hidden reconnect or replay is allowed once request sending starts.
        connection.auto_open=0
        headers={'Connection':'close'}
        if data is not None:headers['Content-Type']='application/octet-stream'
        try:
            connection.request(method,path,body=data,headers=headers)
            response=connection.getresponse()
            return response.status,response.read()
        except (OSError,http.client.HTTPException) as error:
            # ObservingUltimate.write_mem records these as uncertain writes.
            raise SystemExit(f'Ultimate {method} {endpoint} failed after send began: {error}') from error
        finally:connection.close()


class VerifiedUltimate(ConnectingUltimate):
    """Journal controls and reject truncated temporary disk uploads."""
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.control_requests=[]
        self.upload_checks=[]
        self.record_event=lambda:None

    def control(self,method,path,data=None):
        record=dict(method=method,path=path,request_started=True,response_received=False,replayed=False)
        if data is not None:record.update(sent_bytes=len(data),sent_sha256=hashlib.sha256(data).hexdigest())
        self.control_requests.append(record)
        self.record_event()
        status,body=self._call(method,path,data)
        record.update(response_received=True,status=status,body_hex=body.hex())
        self.record_event()
        reply=json.loads(body)
        if status!=200 or reply.get('errors')!=[]:
            raise RuntimeError(f'Ultimate control rejected: {method} {path}: {status} {reply}')
        return reply

    def path_info(self,path):
        """REST metadata of any absolute path (no '..')."""
        assert path.startswith('/') and '..' not in path,path
        status,body=self._call('GET','/v1/files'+urllib.parse.quote(path,safe='/')+':info')
        reply=json.loads(body)
        if status!=200 or reply.get('errors')!=[]:
            raise RuntimeError(f'Ultimate file metadata failed: {path}: {status} {reply}')
        return reply['files']

    def file_info(self,path):
        """Metadata of a temporary upload (only /Temp is accepted)."""
        assert path.startswith('/Temp/') and '..' not in path
        return self.path_info(path)

    def mounted_path(self,drive):
        snapshot=json.loads(self.drives());assert not snapshot['errors']
        mounted={k:v for item in snapshot['drives'] for k,v in item.items()}[drive]
        path=mounted['image_file']
        if not path.startswith('/'):path=mounted['image_path'].rstrip('/')+'/'+path
        return path

    def mount(self,image_bytes,drive='a',img_type='d64',mode='readwrite'):
        self.control('POST',f'/v1/drives/{drive}:mount?type={img_type}&mode={mode}',image_bytes)
        path=self.mounted_path(drive)
        record=dict(path=path,drive=drive,expected_bytes=len(image_bytes),size_verified=False)
        self.upload_checks.append(record)
        self.record_event()
        record['stored_bytes']=self.file_info(path)['size']
        self.record_event()
        if record['stored_bytes']!=record['expected_bytes']:
            raise RuntimeError(f'Ultimate upload is incomplete: {path}: expected {len(image_bytes)} bytes, '
                               f'stored {record["stored_bytes"]}; boot withheld')
        record['size_verified']=True
        self.record_event()

    def mount_existing(self,path,*,drive='a',img_type='d64',mode='readwrite',expected_bytes):
        """Mount an image already on the Ultimate (a snapshot's original)."""
        assert self.path_info(path)['size']==expected_bytes,'existing image size differs from the snapshot'
        self.control('PUT',f'/v1/drives/{drive}:mount?image='+urllib.parse.quote(path,safe='')+
                     f'&type={img_type}&mode={mode}')
        assert self.mounted_path(drive)==path

    def reset(self):self.control('PUT','/v1/machine:reset')
    def unmount(self,drive='a'):self.control('PUT',f'/v1/drives/{drive}:remove')


def close_dos_context(ult,context):
    import tempfile
    from hw_dos_context import DosContexts,idle
    work=Path(tempfile.mkdtemp(prefix='kestrel-dos-context-'))
    contexts=DosContexts(ult,work)
    try:
        before=contexts.info(context)
        print(f'DOS context {context}: {before["result"]}, {before["status"]!r}',flush=True)
        if not idle(before):
            closed=contexts.close(context)
            print(f'CLOSE: {closed["result"]}, {closed["status"]!r}',flush=True)
            after=contexts.info(context)
            print(f'DOS context {context}: {after["result"]}, {after["status"]!r}',flush=True)
            before=after
    finally:
        (work/'replies.json').write_text(json.dumps(contexts.replies,indent=2)+'\n')
        ult.reset()
    if not idle(before):
        raise SystemExit(f'DOS context {context} is still not idle; replies in {work}')
    print(f'DOS context {context} is idle; replies in {work}',flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--host', help='the Ultimate II+ address (default: $KESTREL_ULTIMATE_HOST)')
    checks = parser.add_mutually_exclusive_group(required=True)
    checks.add_argument('--native', action='store_true',
                        help='cold-boot the native disk; memory workspace, calculator, damaged/erroring apps')
    checks.add_argument('--native-files', action='store_true',
                        help='native IEC streams and calculator export on private D64s; retrieved-image readback')
    checks.add_argument('--native-browser', action='store_true',
                        help='native directory browser, app handoff and byte viewer on a private D64; retrieved-image readback')
    checks.add_argument('--native-editor', action='store_true',
                        help='native banked editor, over-64-KiB edit/save on a private D64 on drive B; readback')
    checks.add_argument('--native-ultimate', action='store_true',
                        help='native editor with private Ultimate USB files; FTP readback of fixtures and outputs')
    checks.add_argument('--native-redraw', action='store_true',
                        help='native editor redraw timings and the complete Ultimate file workflow')
    checks.add_argument('--native-usb-apps', action='store_true',
                        help='load USB apps from the native browser, verify saves and failures')
    checks.add_argument('--native-usb-browser', action='store_true',
                        help='(not available: needs an independent UCI directory reference; see hw_native_usb_browser.py)')
    checks.add_argument('--native-desktop', action='store_true',
                        help='qualify the native graphical desktop and app handoffs')
    checks.add_argument('--native-reclaim', type=Path, metavar='REPORT',
                        help='retrieve and delete the private files a failed check left behind (its report.json)')
    checks.add_argument('--close-dos-context', type=int, choices=(1, 2), metavar='N',
                        help='report Ultimate DOS context N (1 or 2) and close a file it holds open; '
                             'the checks refuse to start while either context holds one')
    args = parser.parse_args()
    host = resolve_host(args.host)
    if args.native_desktop:
        from hw_native_desktop_check import run
        from native_capture_transport import ReceiptUltimate,PausedHardwareMonitor
        run(ReceiptUltimate(host,timeout=60),monitor_class=PausedHardwareMonitor,paused_capture=True,dos_contexts=True)
    elif args.close_dos_context:
        close_dos_context(VerifiedUltimate(host,timeout=60),args.close_dos_context)
    elif args.native_reclaim:
        from hw_native_usb_recovery import reclaim
        reclaim(VerifiedUltimate(host,timeout=60),args.native_reclaim)
    elif args.native_usb_browser:
        from hw_native_usb_browser import UNAVAILABLE
        raise SystemExit(UNAVAILABLE)
    elif args.native_usb_apps or args.native_redraw or args.native_ultimate:
        from hw_native_ultimate_check import run
        run(VerifiedUltimate(host,timeout=60),usb_apps=args.native_usb_apps,redraw=args.native_redraw,dos_contexts=True)
    elif args.native_editor:
        from hw_native_editor_check import run
        run(VerifiedUltimate(host,timeout=60),dos_contexts=True)
    elif args.native_browser:
        from hw_native_browser_check import run
        run(VerifiedUltimate(host,timeout=60),dos_contexts=True)
    elif args.native_files:
        from hw_native_files_check import run
        run(VerifiedUltimate(host,timeout=60),dos_contexts=True)
    elif args.native:
        from hw_native_check import run
        run(VerifiedUltimate(host,timeout=60),dos_contexts=True)


if __name__ == '__main__':
    main()
