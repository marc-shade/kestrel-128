#!/usr/bin/env python3
"""Native suite copy through real C128 ROM, two IEC data drives and CPU capture."""
import hashlib
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import vice_harness as ci
from hwlib import lst_symbol
from hw_native_desktop_check import run_native_workflow
from native_capture import NativeCapture,wait
from native_capture_transport import PausedViceMonitor
from native_browser_check import disk_records,browser_screen
from native_files_copy_check import copy_screen
from native_files_scene import browser_surface,browser_console,copy_surface,copy_console
from native_vdc_check import capture_frame as vdc_capture


def main():
    work=Path(tempfile.mkdtemp(prefix='kestrel-native-files-copy-iec-'))
    print('Native Files copy emulator evidence:',work,flush=True)
    shutil.copy2(__file__,work/'run.py')
    disk=work/'suite.d64';shutil.copyfile(ROOT/'target/native-desktop/kestrel.d64',disk)
    disks={device:work/f'data-{device}.d81' for device in (9,10)}
    for device,path in disks.items():
        subprocess.run(['c1541','-format',f'copy{device},02','d81',str(path)],check=True,capture_output=True)
    fixtures={'large':(b's',bytes((i*73+19)&255 for i in range(66058))),
              'empty':(b's',b''),'program':(b'p',b'\x01\x1cEXACT\0PRG\xff')}
    for name,(kind,data) in fixtures.items():
        path=work/(name+'.bin');path.write_bytes(data)
        subprocess.run(['c1541','-attach',str(disks[9]),'-write',str(path),name+','+kind.decode()],check=True,capture_output=True)
    originals={device:path.read_bytes() for device,path in disks.items()}
    for device,data in originals.items():(work/f'initial-{device}.d81').write_bytes(data)
    report=dict(passed=False,physical_hardware_io=False,events=[],desktops=[],screens=[],copies=[],
        images=json.loads((ROOT/'target/native-desktop/images.json').read_text()))
    def save():(work/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    names=('fc_active','fc_status','fc_caret','fc_views','fc_copied','fc_verified','fc_handles','fc_name','fc_length',
        'fg_bitmap','fg_kind','ui_selected')
    addresses={name:lst_symbol('native-desktop/files',name) for name in names}
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    mon=process=xv=None;log=(work/'vice.log').open('w')
    try:
        xv=ci.cbm.Xvfb()
        command=['x128','-default','-8',str(disk),'-drive8true','-drive8type','1541',
            '-9',str(disks[9]),'-drive9true','-drive9type','1581',
            '-10',str(disks[10]),'-drive10true','-drive10type','1581',
            '-sounddev','dummy','-jamaction','0','-warp','-binarymonitor',
            '-binarymonitoraddress',f'ip4://127.0.0.1:{port}']
        report['emulator_command']=command;save()
        process=subprocess.Popen(command,env=dict(os.environ,DISPLAY=xv.display,
            __EGL_VENDOR_LIBRARY_FILENAMES=ci.cbm.MESA_EGL),stdout=log,stderr=subprocess.STDOUT)
        deadline=time.monotonic()+30
        while mon is None:
            assert process.poll() is None,'VICE exited during startup'
            try:mon=ci.Monitor(port=port)
            except OSError:
                if time.monotonic()>deadline:raise
                time.sleep(.1)
        mon.resume();paused=PausedViceMonitor(mon)
        @contextmanager
        def stable_batch(label):
            # Pointer clients (desktop, Files, Editor) clear N_READY during each
            # pointer sample; admit a capture at an idle instant, as
            # ci_native_editor_gui_iec does. First readbacks are never retried.
            if not label.endswith(('-before','-restore')):
                with paused.paused(label):yield
                return
            deadline=time.monotonic()+30
            while True:
                with paused.paused(label):
                    if bytes(paused.read_mem(0x3d11,0x3d12))==b'\0\1' and bytes(paused.read_mem(0xd0,0xd0))==b'\0':
                        report.setdefault('capture_admissions',[]).append(label)
                        yield
                        return
                assert time.monotonic()<deadline,('idle capture admission',label)
                time.sleep(.01)
        capture=NativeCapture(paused,work,quiet=.05,kernel_prefix='native-desktop',batch=stable_batch)
        report['captures']=capture.records;report['paused_capture_batches']=paused.batches

        def workflow(*,key,screens,desktop,read):
            key(ord('F'))
            table=capture.capture('files-key-table-before',address=0x1000,count=256)
            def frame(label,wanted,**expected):
                assert read(addresses['fg_kind'])==b'\1' and read(addresses['fg_bitmap'])==b'\1'
                actual=b''.join(capture.capture(label+f'-surface-{offset:04x}',address=0xc000+offset,
                    count=min(2000,9216-offset)) for offset in range(0,9216,2000))
                (work/(label+'-surface.bin')).write_bytes(actual)
                assert actual==wanted,(label,'Files complete bitmap')
                # Since c4647f7/0e1704f Files mirrors its VIC surface on the VDC.
                def canvas():
                    error,raw=mon._recv(mon._send(0x84,bytes([0,0])));mon.resume();assert not error
                    return raw
                vdc=vdc_capture(capture,read,canvas,work,label,expected['focus'],surface_data=wanted,image_prefix='native-desktop/files')
                report.setdefault('files_copy_frames',[]).append(dict(label=label,expected=expected,
                    surface_sha256=hashlib.sha256(actual).hexdigest(),vdc=vdc));save()
            for value in b'D9\rFF':key(value)
            entries=disk_records(originals[9],2)
            frame('source-d81',browser_surface(entries,device=9,fmt=2),selected=0,focus=11,device=9,fmt=2)
            def function_key(value):
                codes=bytes.fromhex('8589868a878b888c8384')
                assert read(0x1000,20)==bytes([1]*10)+codes
                previous=None;deadline=time.monotonic()+120
                # Files clears N_READY during each pointer sample (8d2086c);
                # inject only at a paused idle instant, within a bound.
                while previous is None:
                    with paused.paused('copy-rom-function-key'):
                        if read(0x3d12)==b'\1' and read(0xd0,2)==bytes(2):
                            previous=int.from_bytes(read(0x3d13,2),'little')
                            paused.write_mem(0x3d12,b'\0');paused.write_mem(0xd1,bytes([1,codes.index(value)]));paused.resume()
                    if previous is None:
                        assert time.monotonic()<deadline,'Files never idle for function-key injection'
                        time.sleep(.01)
                wait(lambda:read(0x3d12)==b'\1' and int.from_bytes(read(0x3d13,2),'little')==(previous+1)&65535,
                     'copy function-key expansion',30)
                assert read(0xd0,2)==bytes(2)
                paused.write_mem(0xd2,b'\0');paused.resume()
                report['events'].append(dict(key=value,rom_expansion=True));save()
            def check(label,source,name,kind,device=9,copied=0,verified=0,status=0,error=0,dos=0):
                start=addresses['fc_active'];end=addresses['fc_verified']+4
                state=capture.capture(label+'-state',address=start,count=end-start)
                def data(symbol,size=1):return state[addresses[symbol]-start:addresses[symbol]-start+size]
                assert data('fc_active')==b'\1' and data('fc_status')==bytes([status])
                assert int.from_bytes(data('fc_copied',4),'little')==copied
                assert int.from_bytes(data('fc_verified',4),'little')==verified
                assert data('fc_handles',8)[::4]==bytes(2)
                views=data('fc_views',2)
                focus=read(addresses['ui_selected'])[0]
                assert focus==25 and data('fc_caret')[0]==len(name)
                expected=dict(source_format=2,fmt=2,kind=kind,device=device,copied=copied,verified=verified,
                    status=status,error=error,dos=dos,caret=len(name),focus=25)
                frame(label,copy_surface(source,name,field_view=views[0],**expected),source=source.hex(),name=name.hex(),**expected)
            for index,(name,(kind,data)) in enumerate(fixtures.items()):
                if index:key(0x11)
                key(ord('C'));source=name.upper().encode();target=b'COPIED '+source
                check(name+'-initial',source,source,0 if kind==b's' else 1)
                key(21)
                for value in target:key(value)
                if index==0:
                    function_key(0x88)
                    for value in b'D10\rS':key(value)
                else:
                    function_key(0x85)
                    for value in b'10\r':key(value)
                check(name+'-destination',source,target,0 if kind==b's' else 1,device=10)
                key(13)
                check(name+('-verified' if data else '-unsupported'),source,target,0 if kind==b's' else 1,
                    device=10,copied=len(data),verified=len(data),status=1 if data else 13)
                if index==0:
                    key(13)
                    check(name+'-exclusive',source,target,0,device=10,status=4,error=0x11,dos=63)
                key(27)
                assert capture.capture(name+'-keys-restored',address=0x1000,count=256)==table
                report['copies'].append(dict(source=name,destination=target.decode(),kind=kind.decode(),
                    bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),function_keys_restored=True,
                    outcome='verified' if data else 'unsupported-before-create'));save()
            key(27);desktop('desktop-after-file-copies',2)

        run_native_workflow(paused,capture,work,disk,report,save,key_quiet=.1,key_poll=.1,additional_apps=workflow)
        assert disks[9].read_bytes()==originals[9],'source disk changed'
        assert hashlib.sha256(disk.read_bytes()).hexdigest()==report['images']['kestrel.d64']['sha256']
        for name,(kind,data) in fixtures.items():
            path=work/('copied-'+name+'.bin')
            if data:
                subprocess.run(['c1541','-attach',str(disks[10]),'-read','copied '+name+','+kind.decode()+',r',str(path)],
                    check=True,capture_output=True)
                assert path.read_bytes()==data,'independent c1541 export differs'
        records=disk_records(disks[10].read_bytes(),2)
        assert [(r['name'],r['type']) for r in records]==[(b'COPIED '+n.upper().encode(),1 if k==b's' else 2) for n,(k,d) in fixtures.items() if d]
        report.update(passed=True,source_disk_unchanged=True,system_disk_unchanged=True,nonempty_exports_match=True)
        print('PASS: native Files copies, real ROM input, both screens, independent exports and 426 free pages',flush=True)
    except BaseException as error:
        report['error']=dict(type=type(error).__name__,message=str(error));raise
    finally:
        if mon is not None:
            try:mon.quit_emulator()
            except (OSError,EOFError):pass
            mon.close()
        if process is not None:
            try:process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:process.kill();process.wait()
        if xv is not None:xv.stop()
        log.close();report['all_host_processes_terminal']=(process is None or process.poll() is not None) and (xv is None or xv.proc.poll() is not None)
        save()


if __name__=='__main__':main()
