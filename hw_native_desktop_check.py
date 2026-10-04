"""Observe the sealed native desktop on hardware, then restore the drives.

Drive A is recorded, a private copy of the native desktop disk is mounted on
it read-only, and afterwards drive A gets its original image and mode back,
the upload is read back (it must be unchanged), deleted and confirmed absent,
and the C128 is reset (hw_session.py)."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
import time

from hw_storage_check import HardwareMonitor
from hw_native_check import hashes,quiet_boot
from hw_session import HardwareSession
from hw_dos_context import DosContexts
from native_capture import ROOT,NativeCapture,wait,expected_screen,calculator_screen
from native_running_layout import verify_running_layout
from native_mode_capture import NativeModeCapture
from native_browser_check import disk_records,browser_screen
from native_editor_scene import surface as editor_surface,console as editor_console
from launcher_scene import surface,console
from native_calc_scene import surface as calc_surface
from native_files_scene import browser_surface as files_surface,browser_console as files_console
from hwlib import lst_symbol
from native_vdc_check import capture_frame as vdc_frame


def run_native_workflow(mon,capture,work,disk,report,save,*,key_quiet=4,key_poll=2,kernel_prefix='native-desktop',additional_apps=None):
    """Shared CPU workflow; caller owns boot, restoration and temporary files."""
    modes=NativeModeCapture(mon,work,quiet=capture.quiet,kernel_prefix=kernel_prefix,batch=capture.batch)
    report['mode_captures']=modes.records
    def read(address,count=1):
        data=bytes(mon.read_mem(address,address+count-1));mon.resume();return data
    def ready():return read(0x3d12)==b'\1' and read(0xd0,2)==bytes(2)
    def key(value):
        wait(ready,'native desktop/app idle',180)
        start=time.monotonic();notice=start;previous=None
        # Pointer clients clear N_READY during each pointer sample; inject
        # only at a paused idle instant, retrying admission within a bound.
        while previous is None:
            with capture.batch(f'key-{value:02x}'):
                if ready():
                    previous=int.from_bytes(read(0x3d13,2),'little')
                    mon.write_mem(0x3d12,b'\0');mon.write_mem(0x34a,bytes([value]));mon.write_mem(0xd0,b'\1');mon.resume()
            if previous is None:
                assert time.monotonic()-start<180,'native input never idle for key injection'
                time.sleep(.01)
        time.sleep(key_quiet)
        while not (ready() and int.from_bytes(read(0x3d13,2),'little')==(previous+1)&65535):
            elapsed=time.monotonic()-start;assert elapsed<900,('native desktop key timeout',value,elapsed)
            if time.monotonic()-notice>=30:
                print(f'Native desktop key {value:02X}: waiting for complete operation ({elapsed:.0f}s)',flush=True);notice=time.monotonic()
            time.sleep(key_poll)
        report['events'].append(dict(key=value,elapsed_seconds=round(time.monotonic()-start,3)));save()
    def screens(label,oracle):
        for mode,columns,address in ((0,40,0x400),(1,80,0)):
            actual=capture.capture(label+('-vic' if mode==0 else '-vdc'),mode=mode,address=address,count=columns*25)
            assert actual==oracle(columns),(label,columns)
        report['screens'].append(label);save();print('Verified native screens:',label,flush=True)
    # Since 5d04173 (launcher) and c4647f7 (apps) the VDC shows a bitmap:
    # the launcher's own VDC scene, or a doubled mirror of the verified VIC
    # surface. No emulator canvas here, so only VDC state and RAM are compared.
    def vdc(label,selected,wanted=None,app='desktop'):
        return vdc_frame(capture,read,None,work,label,selected,surface_data=wanted,image_prefix='native-desktop/'+app)
    def calculator(label,result,history):
        assert read(lst_symbol('native-desktop/calc','cg_bitmap'))==b'\1'
        actual=b''.join(capture.capture(label+f'-surface-{offset:04x}',address=0xc000+offset,
                       count=min(2000,9216-offset)) for offset in range(0,9216,2000))
        (work/(label+'-surface.bin')).write_bytes(actual)
        assert actual==calc_surface(result,history),(label,'calculator bitmap')
        mirror=vdc(label,0,actual,'calc')
        registers=modes.snapshot(label+'-mode')
        assert registers['vic_d011']&0x7f==0x3b
        assert registers['vic_sprites']==(3 if read(lst_symbol('native-desktop/calc','pm_seen'))==b'\1' else 0)
        report.setdefault('calculator_frames',[]).append(dict(label=label,result=result,history=history,registers=registers,vdc=mirror))
        save();print('Verified graphical calculator RAM and VDC:',label,flush=True)
    def editor(label,data,cursor,**expected):
        assert capture.capture(label+'-bitmap-active',address=lst_symbol('native-desktop/editor','eg_bitmap'),count=1)==b'\1'
        wanted=editor_surface(data,cursor,**expected)
        actual=b''.join(capture.capture(label+f'-surface-{offset:04x}',address=0xc000+offset,
            count=min(2000,9216-offset)) for offset in range(0,9216,2000))
        (work/(label+'-surface.bin')).write_bytes(actual);assert actual==wanted,(label,'editor bitmap')
        mirror=vdc(label,0,actual,'editor')
        registers=modes.snapshot(label+'-mode');assert registers['vic_d011']&0x7f==0x3b
        seen=capture.capture(label+'-pointer-seen',address=lst_symbol('native-desktop/editor','pm_seen'),count=1)
        assert registers['vic_sprites']==(3 if seen==b'\1' else 0)
        report.setdefault('editor_frames',[]).append(dict(label=label,data_hex=data.hex(),cursor=cursor,expected=expected,registers=registers,
            surface_sha256=hashlib.sha256(actual).hexdigest(),vdc=mirror))
        save();print('Verified graphical editor RAM and VDC:',label,flush=True)
    def files(label):
        assert read(lst_symbol('native-desktop/files','fg_bitmap'))==b'\1'
        entries=disk_records(disk.read_bytes())
        actual=b''.join(capture.capture(label+f'-surface-{offset:04x}',address=0xc000+offset,
            count=min(2000,9216-offset)) for offset in range(0,9216,2000))
        (work/(label+'-surface.bin')).write_bytes(actual)
        assert actual==files_surface(entries),(label,'Files bitmap')
        mirror=vdc(label,0,actual,'files')
        registers=modes.snapshot(label+'-mode')
        assert registers['vic_d011']&0x7f==0x3b
        assert registers['vic_sprites']==(3 if read(lst_symbol('native-desktop/files','pm_seen'))==b'\1' else 0)
        report.setdefault('files_frames',[]).append(dict(label=label,selected=0,focus=11,registers=registers,
            surface_sha256=hashlib.sha256(actual).hexdigest(),vdc=mirror))
        save();print('Verified graphical Files RAM and VDC:',label,flush=True)
    def desktop(label,selected=0):
        assert read(0x3d2f)==bytes([selected]),'saved native desktop selection differs'
        assert read(0x3d60,32)==(ROOT/'target/native-desktop/desktop.prg').read_bytes()[2:34]
        assert read(0x3d20)==b'\x20' and read(0x3d23)==b'\2'
        before_jiffy=read(0xa0,3)
        actual=b''.join(capture.capture(label+f'-surface-{offset:04x}',address=0xc000+offset,
                         count=min(2000,9216-offset)) for offset in range(0,9216,2000))
        (work/(label+'-surface.bin')).write_bytes(actual);assert actual==surface(selected)
        scene=vdc(label,selected)
        registers=modes.snapshot(label+'-mode')
        assert registers['vic_d011']&0x7f==0x3b and registers['vic_d016']&0x1f==8 and registers['vic_d018']&0xfe==0x80
        assert registers['vic_irq_mask']&15==1 and registers['vic_sprites']==(3 if read(lst_symbol('native-desktop/desktop','pm_seen'))==b'\1' else 0)
        assert registers['cia2_port']&3==0 and registers['cia2_ddr']&3==3
        assert registers['foreground_mmu'] in (0,0x0e) and not registers['mode']&0x40 and registers['common']&15==4
        assert (registers['cpu_ddr'],registers['cpu_port'])==(0x2f,0x75) and registers['text_graphics']==255
        assert registers['text_display']&128 and not registers['cpu_speed']&1
        assert read(0xa0,3)!=before_jiffy
        heap=read(0x3800,0x600);(work/(label+'-heap.bin')).write_bytes(heap)
        app_pages=(ROOT/'target/native-desktop/desktop.prg').read_bytes()[12]
        # Since c4647f7 the desktop also owns the VDSVC component and, unless
        # the REU backs it, the main-RAM VDC snapshot (64 mono / 72 colour pages).
        service_pages=(ROOT/'target/native-desktop/vdsvc.prg').read_bytes()[12]
        snapshot_pages=0 if read(lst_symbol('native-desktop/desktop','vs_reu'))==b'\1' else scene['snapshot_pages']
        assert heap[0x50:0xff].count(0)+heap[0x104:0x1ff].count(0)==426-36-app_pages-service_pages-snapshot_pages
        report['desktops'].append(dict(label=label,selected=selected,surface_bytes=9216,
            surface_sha256=hashlib.sha256(actual).hexdigest(),vdc=scene,irq_advanced=True,registers=registers,
            qualification='CPU-captured display RAM and mode registers; no physical video pixel capture'))
        save();print('Verified native desktop RAM, VDC and display mode:',label,flush=True)
    wait(lambda:read(0x1c13,6)==b'KES128' and ready(),'native graphical desktop boot',300)
    report['resident_boot']=verify_running_layout(capture,ROOT,'resident-boot',image_dir=ROOT/'target'/kernel_prefix);save()
    desktop('desktop-boot')
    key(9);desktop('desktop-editor-selected',1)
    key(ord('C'));calculator('calculator-new','0',[])
    for value in b'12+30=':key(value)
    calculator('calculator-result','42',['42'])
    key(27);desktop('desktop-after-calculator')
    key(ord('E'));editor('editor-new',b'',0)
    document=b'C128'
    for value in document:key(value)
    editor('editor-typed',document,4,dirty=True)
    key(27);key(ord('Y'));desktop('desktop-after-editor',1)
    key(ord('F'));files('files')
    key(27);desktop('desktop-after-files',2)
    if additional_apps is not None:
        additional_apps(key=key,screens=screens,desktop=desktop,read=read)
    key(27);screens('workspace-returned',lambda cols:expected_screen(cols,0))
    report['resident_return']=verify_running_layout(capture,ROOT,'resident-return',image_dir=ROOT/'target'/kernel_prefix);save()
    final_mode=modes.snapshot('workspace-returned-mode');report['final_mode']=final_mode;save()
    heap=read(0x3800,0x600);(work/'final-native-heap.bin').write_bytes(heap)
    assert heap[0x50:0xff]==bytes(175) and heap[0x104:0x1ff]==bytes(251)
    assert all(heap[0x400+i*8]==0 for i in range(32))
    assert read(0x3d20)==b'\0' and read(0x3d23)==b'\0'
    assert final_mode['cpu_ddr']==0x2f and final_mode['cpu_port']==0x73 and final_mode['text_graphics']==0
    assert all(item['restored'] for item in capture.records)
    assert all(item['restored'] for item in modes.records)
    report['native_checks_passed']=True;save()


def idle_admission(paused, read, admissions, bound=30):
    """A capture batch that takes a capture's before/restore snapshots only at
    a paused instant where the workspace is idle. Pointer clients clear
    N_READY while they sample the 1351 every frame, so a pause can land
    inside a sample; that instant is skipped, not asserted on (as the VICE
    workflows' stable_batch does)."""
    @contextmanager
    def batch(label):
        if not label.endswith(('-before', '-restore')):
            with paused(label):
                yield
            return
        deadline = time.monotonic()+bound
        deferred = 0
        while True:
            with paused(label):
                if read(0x3d11, 2) == b'\0\1' and read(0xd0, 1) == b'\0':
                    admissions.append(dict(label=label, deferred=deferred))
                    yield
                    return
            deferred += 1
            assert time.monotonic() < deadline, ('idle capture admission', label, deferred)
            time.sleep(.01)
    return batch


def run(ult, *, workflow=run_native_workflow, monitor_class=HardwareMonitor,
        paused_capture=False, cleanup_after_failure=True, expected_images=None,
        preflight=None, full_desktop_workflow=None, dos_contexts=False):
    """preflight(ult, mon, work, report, save), if given, runs after the drive
    snapshot and before anything changes. cleanup_after_failure=False keeps a
    failed run's upload (report['restore']['leftovers']) for inspection; the
    drives are restored either way."""
    focused=(workflow is not run_native_workflow) if full_desktop_workflow is None else not full_desktop_workflow
    work=Path(tempfile.mkdtemp(prefix='kestrel-hardware-native-transport-' if focused else 'kestrel-hardware-native-desktop-'))
    print(f'Native {"capture transport" if focused else "desktop"} hardware evidence: {work}',flush=True)
    disk=work/'native.d64';shutil.copyfile(ROOT/'target/native-desktop/kestrel.d64',disk)
    if expected_images is None:
        expected_images=dict(disk='7d4d5b9bd31ad8d616f8f682ba16cf0342bf44dc776cb006b6cefcf20e8da28a',
                             kernel='3cdd7b73d6980d9685611c66ee0e20706b0f39a458ca3a5e9b1b3f8021fc3cf9')
    assert set(expected_images)=={'disk','kernel'} and all(re.fullmatch(r'[0-9a-f]{64}',v) for v in expected_images.values())
    assert hashlib.sha256(disk.read_bytes()).hexdigest()==expected_images['disk']
    assert hashlib.sha256((ROOT/'target/native-desktop/kestrel.prg').read_bytes()).hexdigest()==expected_images['kernel']
    report=dict(passed=False,physical_hardware_io=True,build=hashes(),events=[],desktops=[],screens=[],
                uncertain_host_writes=ult.uncertain_writes,
                host_connect_failures=ult.connect_failures,host_control_requests=ult.control_requests,
                host_upload_checks=ult.upload_checks)
    report['full_desktop_workflow']=not focused
    report['image_admission']=dict(expected_images)
    def save():(work/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    ult.record_event=save;save()
    mon=monitor_class(ult)
    def paused_read(address,count):
        data=bytes(mon.read_mem(address,address+count-1));mon.resume();return data
    capture=NativeCapture(mon,work,quiet=2,kernel_prefix='native-desktop',
                          batch=idle_admission(mon.paused,paused_read,report.setdefault('capture_admissions',[]))
                          if paused_capture else None)
    report['paused_capture_batches']=getattr(mon,'batches',[])
    report['ram_write_receipts']=getattr(ult,'ram_write_receipts',[])
    report['captures']=capture.records
    session=HardwareSession(ult,work,report,save,drives=('a',),
        dos_contexts=DosContexts(ult,work) if dos_contexts else None)
    report['stage']='preflight';save()
    try:
        before=session.snapshot();assert before['a']['enabled'] and before['a']['bus_id']==8
        (work/'ultimate-version.json').write_text(ult.version())
        if preflight is not None:
            preflight(ult,mon,work,report,save)
    except BaseException as error:
        report['preflight_error']=dict(type=type(error).__name__,message=str(error));save()
        raise
    def body():
        report['stage']='native-boot';save()
        try:
            path=session.upload(disk.read_bytes(),'a','d64','readonly',retrieve=True)
            assert re.fullmatch(r'/Temp/temp[0-9a-fA-F]{4}',path),path
            report['native_disk_upload_path']=path;save()
            ult.reset();quiet_boot('Native desktop boot')
            workflow(mon,capture,work,disk,report,save)
        except BaseException as error:
            report['native_error']=str(error);save()
            raise
    try:session.run(body,cleanup_on_failure=cleanup_after_failure)
    finally:report['images_unchanged']=report['build']==hashes();save()
    assert report['images_unchanged'] and not report['uncertain_host_writes']
    report['cleanup_complete']=report['restore']['cleanup_complete'];save()
    report['passed']=True;save()
    print(f'HW-NATIVE-{"TRANSPORT" if focused else "DESKTOP"} PASS; bounded workflow; drives restored, upload deleted; {work}',flush=True)
