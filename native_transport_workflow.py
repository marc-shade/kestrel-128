"""Focused native capture experiment shared by VICE and the physical lifecycle."""
import hashlib

from launcher_scene import surface
from native_vdc_check import capture_frame as vdc_frame
from native_capture import ROOT, wait
from native_mode_capture import NativeModeCapture
from native_running_layout import verify_running_layout


def run_transport_workflow(mon, capture, work, disk, report, save, *,
                           key_quiet=4, key_poll=2, kernel_prefix='native-desktop'):
    import time
    report['experiment'] = 'paused batches with exact write receipts; no full app workflow'
    report['transport_samples'] = []
    report['paused_capture_batches'] = mon.batches
    modes = NativeModeCapture(mon,work,quiet=capture.quiet,kernel_prefix=kernel_prefix,batch=mon.paused)
    report['mode_captures'] = modes.records
    def read(at,count=1):
        data=bytes(mon.read_mem(at,at+count-1));mon.resume();return data
    def ready():return read(0x3d12)==b'\1' and read(0xd0,2)==bytes(2)
    def check_mode(mode):
        assert mode['cpu_ddr']==0x2f and mode['cpu_port']==0x75 and mode['text_graphics']==255
        assert mode['foreground_mmu'] in (0,0x0e) and not mode['mode']&0x40 and mode['common']&15==4
        assert mode['vic_d011']&0x7f==0x3b and mode['vic_d016']&0x1f==8 and mode['vic_d018']&0xfe==0x80
        assert mode['vic_irq_mask']&15==1 and mode['vic_sprites']==0
        assert mode['cia2_port']&3==0 and mode['cia2_ddr']&3==3
        assert mode['text_display']&128 and not mode['cpu_speed']&1
    def observed(label,expected,*,mode=0,address=0):
        (work/(label+'-expected.bin')).write_bytes(expected)
        row = dict(label=label,mode=mode,address=address,bytes=len(expected),
                   expected_sha256=hashlib.sha256(expected).hexdigest(),matches=False,
                   capture_returned=False)
        report['transport_samples'].append(row);save()
        try:
            actual=capture.capture(label,mode=mode,address=address,count=len(expected))
            row['capture_returned']=True
            assert actual==expected,(label,'CPU capture differs from oracle')
        finally:
            path=work/(label+'.bin')
            if path.exists():
                actual=path.read_bytes()
                row.update(observed_bytes=len(actual),observed_sha256=hashlib.sha256(actual).hexdigest(),
                           matches=actual==expected,
                           different_offsets=[i for i,(a,b) in enumerate(zip(actual,expected)) if a!=b])
            save()
    wait(lambda:read(0x1c13,6)==b'KES128' and ready(),'native capture diagnostic boot',300)
    report['resident_boot']=verify_running_layout(capture,ROOT,'resident-boot',image_dir=ROOT/'target'/kernel_prefix);save()
    first_jiffy=read(0xa0,3)
    report['mode_before']=modes.snapshot('desktop-mode-before');save()
    check_mode(report['mode_before'])
    for offset in range(0,9216,2000):
        observed(f'boot-surface-{offset:04x}',surface()[offset:offset+2000],address=0xc000+offset)
    # Since 5d04173 the launcher's VDC is a bitmap scene, not 80-column text:
    # compare VDC state and the complete bitmap with native_vdc_scene.
    report['boot_vdc']=vdc_frame(capture,read,None,work,'boot-vdc',0);save()
    with mon.paused('select-editor'):
        assert ready()
        previous=int.from_bytes(read(0x3d13,2),'little')
        mon.write_mem(0x3d12,b'\0');mon.write_mem(0x34a,b'\t');mon.write_mem(0xd0,b'\1');mon.resume()
    time.sleep(key_quiet)
    wait(lambda:ready() and int.from_bytes(read(0x3d13,2),'little')==(previous+1)&65535,
         'native capture diagnostic selection',180)
    report['events'].append(dict(key=9));save()
    selected=surface(1)
    for trial in range(3):
        for address,count in ((0xc7d0,2000),(0xcdd0,464),(0xc000,512)):
            offset=address-0xc000
            observed(f'trial-{trial}-{address:04x}-{count}',selected[offset:offset+count],address=address)
        print(f'Capture transport: three strict selected-surface samples pass in trial {trial+1}/3',flush=True)
    report['selected_vdc']=vdc_frame(capture,read,None,work,'selected-vdc',1);save()
    report['mode_after']=modes.snapshot('desktop-mode-after');save()
    # Retain every raw field, but compare display control bits: D011 bit 7
    # is the live raster counter, and CIA2 input pins are not display state.
    check_mode(report['mode_after'])
    assert read(0xa0,3)!=first_jiffy and ready()
    assert read(0x3d20)==b'\x20' and read(0x3d23)==b'\2'
    assert all(r['restored'] for r in capture.records+modes.records)
    assert all(r['pause_acknowledged'] and r['resume_acknowledged'] for r in mon.batches)
    report['native_checks_passed']=True;save()
    print('PASS: focused capture samples and borrower restoration; this is not full desktop hardware qualification',flush=True)
