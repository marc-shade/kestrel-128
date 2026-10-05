#!/usr/bin/env python3
"""Actual VICE 1351 motion/buttons, ROM keyboard, app returns and VIC pixels."""
import ctypes as C
from contextlib import contextmanager
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import random
import struct
import time

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
import vice_harness as ci
from vice_keyboard import Keyboard, PrivateXvfb
from hwlib import lst_symbol
from native_capture import NativeCapture,wait,expected_screen,calculator_screen
from native_capture_transport import PausedViceMonitor
from native_mode_capture import NativeModeCapture
from native_running_layout import verify_running_layout
from launcher_scene import surface,console,CARDS
from native_pointer_check import pixels,surface_pixels,check_canvas
from native_calc_scene import surface as calc_surface, BUTTONS
from native_files_check import exact_d64_files,exact_disk_files
from native_editor_scene import surface as editor_surface,console as editor_console,RECTS as EDITOR_RECTS
from native_picker_scene import surface as picker_surface,console as picker_console,RECTS as PICKER_RECTS
from native_picker_check import picker_symbol
from native_browser_check import browser_screen,disk_records
from native_controls_check import panel_screen,absent_body
from native_controls_scene import surface as controls_surface,RECTS as CONTROLS_RECTS
from native_files_scene import (browser_surface as files_surface,
    copy_surface as files_copy_surface,RECTS as FILES_RECTS)
from native_files_find_check import bitmap as files_find_surface
from native_claude_check import landing_screen,capture_frame as claude_capture
from native_claude_scene import RECTS as CLAUDE_RECTS
from paint_scene import surface as paint_surface,console as paint_console,RECTS as PAINT_RECTS,MESSAGES as PAINT_MESSAGES
from native_paint_format import encode as paint_encode
from native_vdc_check import capture_frame as vdc_capture,capture_snapshot as vdc_snapshot


class Mouse(Keyboard):
    def __init__(self,display,*,vdc_window=False):
        super().__init__(display)
        self.t.XTestFakeRelativeMotionEvent.argtypes=[C.c_void_p,C.c_int,C.c_int,C.c_ulong]
        self.t.XTestFakeButtonEvent.argtypes=[C.c_void_p,C.c_uint,C.c_int,C.c_ulong]
        self.x.XWarpPointer.argtypes=[C.c_void_p,C.c_ulong,C.c_ulong,C.c_int,C.c_int,C.c_uint,C.c_uint,C.c_int,C.c_int]
        self.x.XGetGeometry.argtypes=[C.c_void_p,C.c_ulong,C.POINTER(C.c_ulong),C.POINTER(C.c_int),C.POINTER(C.c_int),
            C.POINTER(C.c_uint),C.POINTER(C.c_uint),C.POINTER(C.c_uint),C.POINTER(C.c_uint)]
        self.x.XRaiseWindow.argtypes=[C.c_void_p,C.c_ulong]
        # Target the requested monitor explicitly; stacking order depends on
        # the initial console. The private X screen must contain its grab center.
        def width(window):
            root=C.c_ulong();x=C.c_int();y=C.c_int();w=C.c_uint();h=C.c_uint();border=C.c_uint();depth=C.c_uint()
            assert self.x.XGetGeometry(self.display,window,C.byref(root),C.byref(x),C.byref(y),C.byref(w),C.byref(h),C.byref(border),C.byref(depth))
            return w.value
        self.window=(max if vdc_window else min)(self.windows,key=lambda row:width(row[0]))[0]
        self.x.XRaiseWindow(self.display,self.window)
        self.x.XSetInputFocus(self.display,self.window,2,0)
        self.x.XWarpPointer(self.display,0,self.window,0,0,0,0,150,150)
        self.x.XFlush(self.display);time.sleep(.3)

    def move(self,dx,dy):
        self.t.XTestFakeRelativeMotionEvent(self.display,dx,dy,0)
        self.x.XFlush(self.display);time.sleep(.12)

    def button(self,down,button=1):
        self.t.XTestFakeButtonEvent(self.display,button,int(down),0)
        self.x.XFlush(self.display);time.sleep(.15)

    @contextmanager
    def held_key(self,name):
        key=self.x.XKeysymToKeycode(self.display,self.x.XStringToKeysym(name.encode()))
        assert key
        self.t.XTestFakeKeyEvent(self.display,key,1,0);self.x.XFlush(self.display)
        try:yield
        finally:
            self.t.XTestFakeKeyEvent(self.display,key,0,0);self.x.XFlush(self.display)
            time.sleep(.12)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--80col',dest='eighty',action='store_true')
    parser.add_argument('--vdc64',action='store_true')
    parser.add_argument('--d81',action='store_true')
    parser.add_argument('--reu-kib',type=int,choices=(128,256,512,1024,2048,4096,8192,16384))
    parser.add_argument('--boot-frame-only',action='store_true')
    parser.add_argument('--calc-only',action='store_true')
    parser.add_argument('--paint-only',action='store_true')
    parser.add_argument('--controls-only',action='store_true')
    parser.add_argument('--controls-clock',action='store_true',help='exercise manual clock fields without a physical cartridge')
    parser.add_argument('--files-only',action='store_true')
    parser.add_argument('--files-open-with',action='store_true',help='open private text/UPNT fixtures from Files and return to their selection')
    parser.add_argument('--files-find',action='store_true',help='find private documents beyond the visible page, wrap and preserve a missing match')
    parser.add_argument('--editor-only',action='store_true')
    parser.add_argument('--editor-clipboard',action='store_true',help='exercise shared Copy/Cut/Paste/Clear with ROM modifier keys')
    parser.add_argument('--editor-history',action='store_true',help='add keyboard and retained-toolbar Undo/Redo to the clipboard workflow')
    parser.add_argument('--editor-selection',action='store_true',help='exercise text selection and replacement with ROM keyboard and 1351 input')
    parser.add_argument('--editor-large',action='store_true',help='edit/save/reopen a 128 KiB REU document on the private D81')
    parser.add_argument('--claude-only',action='store_true');args=parser.parse_args()
    assert sum((args.calc_only,args.paint_only,args.controls_only,args.files_only,args.editor_only,args.claude_only))<=1
    if args.controls_clock:assert args.controls_only
    if args.files_open_with:assert args.files_only and not args.reu_kib
    if args.files_find:assert args.files_only and args.files_open_with
    if args.editor_selection or args.editor_clipboard:assert args.editor_only
    if args.editor_history:assert args.editor_only and args.editor_clipboard
    if args.editor_large:
        assert args.editor_only and args.d81 and args.reu_kib and args.reu_kib>=512
    work=Path(tempfile.mkdtemp(prefix='kestrel-native-pointer-iec-'))
    print('Native pointer VICE:',work,flush=True)
    shutil.copy2(__file__,work/'run.py')
    boot_format=2 if args.d81 else 0
    disk_name='kestrel.d81' if args.d81 else 'kestrel.d64'
    kernel_prefix='native-desktop/d81' if args.d81 else 'native-desktop'
    disk=work/('suite.d81' if args.d81 else 'suite.d64')
    shutil.copy2(ROOT/'target/native-desktop'/disk_name,disk)
    if args.editor_large:
        editor_large=(b'0123456789ABCDEF\r\n'*8000)[:131113]
        source=work/'large-input.seq';source.write_bytes(editor_large)
        subprocess.run(['c1541','-attach',str(disk),'-write',str(source),'large,s'],check=True,capture_output=True)
    if args.files_open_with:
        open_text=b'Files opens this document.\r\nExact name and device.\r\n'
        open_picture=bytes((i*19+i//256)&255 for i in range(8000))+bytes(192)+b'\x10'*1024
        for name,data in (('doc.txt',open_text),('draw.upnt',paint_encode(open_picture))):
            source=work/name;source.write_bytes(data)
            subprocess.run(['c1541','-attach',str(disk),'-write',str(source),name+',s'],check=True,capture_output=True)
    data_disk=work/'data-9.d64'
    subprocess.run(['c1541','-format','picker data,09','d64',str(data_disk)],check=True,capture_output=True)
    shutil.copy2(data_disk,work/'initial-data-9.d64')
    image=ROOT/'target/native-desktop'
    report=dict(passed=False,physical_hardware_io=False,options=vars(args),events=[],desktops=[],screens=[],calculator_frames=[],paint_frames=[],controls_frames=[],files_frames=[],editor_frames=[],
        kernel_prefix=kernel_prefix,boot_format=boot_format,
        images={p.relative_to(image).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in image.rglob('*') if p.suffix in ('.prg','.d64','.d81')})
    def save():(work/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    pointer_app='desktop'
    editor_selection_expected=None
    claude_labels={m[2]:int(m[1],16) for m in re.finditer(r'^al ([0-9A-Fa-f]+) \.(\S+)',(image/'claude.lbl').read_text(),re.M)}
    def symbol(name):
        if pointer_app=='claude':return claude_labels[name]
        if name.startswith('pm_') and pointer_app in ('editor','files'):
            kind,active={'editor':('ed_module_kind',1),'files':('fg_kind',2)}[pointer_app]
            if app_read(lst_symbol('native-desktop/'+pointer_app,kind))==bytes([active]) and app_read(picker_symbol(pointer_app,'fd_active'))==b'\1':
                return picker_symbol(pointer_app,'pgm_'+name[3:])
        return lst_symbol('native-desktop/'+pointer_app,name)
    with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    xv=PrivateXvfb(geometry='1920x1200x24',env=dict(os.environ,__EGL_VENDOR_LIBRARY_FILENAMES=ci.cbm.MESA_EGL));emu=mon=mouse=None;log=(work/'vice.log').open('w')
    report['private_x_display']=xv.display
    report['private_x_pid']=xv.proc.pid
    report['private_x_geometry']='1920x1200x24'
    try:
        command=['x128','-default','-80col' if args.eighty else '-40col','-8',str(disk),'-drive8true','-drive8type','1581' if args.d81 else '1541',
            '-9',str(data_disk),'-drive9true','-drive9type','1541',
            '-VDC64KB' if args.vdc64 else '-VDC16KB','-sounddev','dummy','-soundwarpmode','1','-jamaction','0','-warp','-controlport1device','3',
            '-controlport2device','0','+mouse','-binarymonitor','-binarymonitoraddress',f'ip4://127.0.0.1:{port}']
        if args.reu_kib:
            from native_reu_check import initial_memory,module_cache,snapshot as reu_dump
            reu_initial=initial_memory(args.reu_kib)
            from native_reu_document_check import ReuDocumentOracle
            reu_documents=ReuDocumentOracle(reu_initial,history=True)
            (work/'initial.reu').write_bytes(reu_initial)
            command.extend(['-reu','-reusize',str(args.reu_kib),'-reuimage',str(work/'initial.reu'),'+reuimagerw'])
        report['command']=command;save()
        emu=subprocess.Popen(command,env=dict(os.environ,DISPLAY=xv.display,
            __EGL_VENDOR_LIBRARY_FILENAMES=ci.cbm.MESA_EGL),stdout=log,stderr=subprocess.STDOUT)
        deadline=time.monotonic()+30
        while mon is None:
            assert emu.poll() is None
            try:mon=ci.Monitor(port=port)
            except OSError:
                if time.monotonic()>deadline:raise
                time.sleep(.1)
        banks=mon.banks();mon.resume();paused=PausedViceMonitor(mon,signature_bank=banks['ram00'])
        def read(at,n=1,bank=None):
            # Progress polls can interrupt a far heap transfer during app
            # cleanup/loading. Kernel metadata belongs to physical bank 0,
            # regardless of the CPU's temporary mapping.
            if bank is None:bank=banks['ram00']
            data=bytes(paused.read_mem(at,at+n-1,bank=bank));paused.resume();return data
        def app_read(at,n=1):
            # ROM IRQ/GETIN can hide high application RAM while ready is set.
            # The checked app allocation lives in physical bank 0 throughout.
            return read(at,n,bank=banks['ram00'])
        def ready():return read(0x3d12)==b'\1' and read(0xd0,2)==bytes(2)
        def unphase():
            # VICE answers the monitor at a fixed point of its frame. Apps that
            # sample the 1351 each frame clear N_READY around the same point, so
            # a poll there never sees them idle; step a random part of a frame
            # (binary monitor ADVANCE_INSTRUCTIONS) before sampling.
            error,_=mon._recv(mon._send(0x71,struct.pack('<BH',0,random.randint(1,6000))));assert not error
        def value(name):return app_read(symbol(name))[0]
        def ready_unphased():
            # ready() at a random point of the frame: while a drag holds the
            # button the Editor samples the 1351 every frame, and a monitor
            # read at its fixed point can keep landing where N_READY is 0.
            with paused.paused('ready'):
                unphase()
                return (bytes(paused.read_mem(0x3d12,0x3d12,bank=banks['ram00']))==b'\1' and
                        bytes(paused.read_mem(0xd0,0xd1,bank=banks['ram00']))==bytes(2))
        def position():
            assert symbol('pm_y')==symbol('pm_x')+2
            point=app_read(symbol('pm_x'),3)
            return int.from_bytes(point[:2],'little'),point[2]
        def header(name):return read(0x3d60,32)==(image/(name+'.prg')).read_bytes()[2:34]
        def wait_loaded_app(name):
            if name!='files':
                wait(lambda:header(name) and ready(),'click opens '+name,120)
                return
            # Files validates directory entries and their PRG metadata before
            # publishing readiness. A busy host can run the emulated 1541 near
            # real time. Bound both total time and time without file/list progress.
            expected=(image/'files.prg').read_bytes()[2:34]
            total_at=lst_symbol('native-desktop/files','b_total')
            start=last_progress=time.monotonic();previous=None;progress=[]
            report['files_load_progress']=progress
            while True:
                with paused.paused('files-load-progress'):
                    state=bytes(paused.read_mem(0x3d10,0x3d97,bank=banks['ram00']))
                    busy=bytes(paused.read_mem(0xd0,0xd1,bank=banks['ram00']))
                    loaded=state[0x50:0x70]==expected
                    total=bytes(paused.read_mem(total_at,total_at+1,bank=banks['ram00'])) if loaded else b''
                now=time.monotonic()
                if loaded and state[2]==1 and busy==bytes(2):
                    report['files_load_seconds']=now-start;save();return
                signature=state[0x10:0x14]+state[0x28:0x30]+state[0x71:0x75]+state[0x82:0x86]+total
                if signature!=previous:
                    previous=signature;last_progress=now
                    progress.append(dict(seconds=now-start,state=signature.hex(),loaded=loaded,
                        entries=int.from_bytes(total,'little') if loaded else None))
                    save()
                assert now-start<600,'Files did not become ready within ten minutes'
                assert now-last_progress<120,'Files loading made no file/list progress for two minutes'
                time.sleep(.25)
        @contextmanager
        def stable_batch(label):
            # N_READY is briefly zero during a foreground pointer sample.
            # Admit an idle snapshot while already paused; never replace a
            # first readback after the observer has touched its scratch.
            if not label.endswith(('-before','-restore')):
                with paused.paused(label):yield
                return
            deadline=time.monotonic()+30;deferred=0
            while True:
                with paused.paused(label):
                    unphase()
                    idle=bytes(paused.read_mem(0x3d11,0x3d12,bank=banks['ram00']))==b'\0\1' and bytes(paused.read_mem(0xd0,0xd0,bank=banks['ram00']))==b'\0'
                    if idle:
                        report.setdefault('capture_admissions',[]).append(dict(label=label,deferred=deferred))
                        yield
                        return
                deferred+=1
                assert time.monotonic()<deadline,('idle capture admission',label)
                time.sleep(.01)
        wait(lambda:read(0x1c13,6)==b'KES128' and header('desktop') and ready(),'desktop boot',90)
        assert read(0x3de4)==bytes([boot_format]) and read(0x3d2c,2)==bytes([boot_format,8])
        report['initial_pointer_state']=app_read(symbol('pm_active'),40).hex();save()
        capture=NativeCapture(paused,work,quiet=.05,kernel_prefix=kernel_prefix,batch=stable_batch)
        modes=NativeModeCapture(paused,work,quiet=.05,kernel_prefix=kernel_prefix,batch=stable_batch)
        report.update(captures=capture.records,mode_captures=modes.records,paused_capture_batches=paused.batches)
        report['resident_boot']=verify_running_layout(capture,ROOT,'resident-boot',image_dir=ROOT/'target'/kernel_prefix);save()
        saved_registers=app_read(symbol('pm_saved'),12);saved_init=app_read(symbol('pm_init_saved'))
        saved_keys=capture.capture('keys-before',address=0x1000,count=256)
        saved_callback=read(0x033c,2);report['saved_keycheck']=saved_callback.hex()
        report['saved_sprite_registers']=saved_registers.hex();report['saved_init']=saved_init.hex()
        repeat=read(0xa22)
        with paused.paused('disable-accelerated-repeat'):paused.write_mem(0xa22,b'\x40')
        mouse=Mouse(xv.display,vdc_window=args.eighty);report['private_x_windows']=mouse.windows;save()
        assert len(mouse.windows)==2,'the private X display must contain only this C128 pair'
        resource=b'Mouse'
        error,_=mon._recv(mon._send(0x52,bytes([1,len(resource)])+resource+bytes([4])+bytes([1,0,0,0])))
        mon.resume();assert not error
        report['mouse_enabled_after_boot']=True
        wait(lambda:value('pm_seen')==1,'1351 attached',15)
        time.sleep(1)
        def move_to(tx,ty):
            samples=[]
            deadline=time.monotonic()+90
            while time.monotonic()<deadline:
                x,y=position();samples.append([x,y])
                if abs(x-tx)<=2 and abs(y-ty)<=2:
                    # Let the foreground finish handling this position before
                    # sending another host delta. Steering again during its
                    # brief N_READY=0 interval can keep the pointer oscillating.
                    wait(ready_unphased,'mouse destination idle',60)
                    # Finish the input gesture before taking the first capture.
                    # A single position read can precede queued host deltas.
                    time.sleep(.2)
                    settled=position();samples.append(list(settled))
                    # Readiness was observed above. A second separate sample
                    # can miss its brief pulse as VDC drawing resumes, even
                    # though the pointer has settled inside the target.
                    if settled==(x,y):
                        report.setdefault('mouse_routes',[]).append(dict(app=pointer_app,target=[tx,ty],samples=samples));save()
                        return x,y
                    continue
                mouse.move(max(-12,min(12,(tx-x)*2)),max(-12,min(12,(ty-y)*2)))
            report.setdefault('failed_mouse_routes',[]).append(dict(app=pointer_app,target=[tx,ty],samples=samples));save()
            raise AssertionError(('host mouse failed to reach target',position(),(tx,ty)))
        def desktop(label,selected):
            wait(lambda:header('desktop') and ready() and value('gd_selected')==selected,label,90)
            assert read(0x3de4)==bytes([boot_format]) and read(0x3d2c,2)==bytes([boot_format,8])
            assert read(0x3d21)==b'\x08'
            actual=b''.join(capture.capture(label+f'-surface-{offset:04x}',address=0xc000+offset,count=min(2000,9216-offset)) for offset in range(0,9216,2000))
            (work/(label+'-surface.bin')).write_bytes(actual);assert actual==surface(selected)
            mode=modes.snapshot(label+'-mode');assert mode['vic_sprites']==3 and not mode['cpu_speed']&1
            # Host mouse deltas may still be draining when the large RAM
            # capture begins. Pair the canvas with settled current coordinates.
            for _ in range(20):
                xy=position();time.sleep(.2)
                if position()==xy:break
            else:raise AssertionError('pointer never settled for rendered frame')
            state=app_read(symbol('pm_active'),40);(work/(label+'-state.bin')).write_bytes(state)
            error,raw=mon._recv(mon._send(0x84,bytes([1,0])));mon.resume();assert not error
            (work/(label+'-canvas.bin')).write_bytes(raw)
            rectangle=check_canvas(raw,pixels(selected,*xy))
            def vdc_canvas():
                error,raw=mon._recv(mon._send(0x84,bytes([0,0])));mon.resume();assert not error
                return raw
            vdc=vdc_capture(capture,app_read,vdc_canvas,work,label,selected,color=args.vdc64)
            report['desktops'].append(dict(label=label,selected=selected,position=xy,rectangle=rectangle,mode=mode,vdc=vdc));save()
            if label=='claude-returned':
                subprocess.run(['magick','import','-display',xv.display,'-window','root',str(work/'desktop.png')],check=True,capture_output=True)
            print('PASS: complete VIC/VDC graphics and 192000 pixels including both pointers:',label,flush=True)
        def key(name,target,after_key=None,*,reload=False):
            before=int.from_bytes(read(0x3d13,2),'little')
            # A short host press can begin and end between emulated keyboard
            # scans under load. Keep it down until the ROM-fed native counter
            # acknowledges it, then release even when an assertion fails.
            with mouse.held_key(name):
                if after_key is None:
                    wait(lambda:int.from_bytes(read(0x3d13,2),'little')!=before,
                        name+' sampled by native keyboard',120)
                else:
                    # Counter polling resumes the CPU and can run past the
                    # requested checkpoint. Capture first, then release the
                    # host key while the callback still holds the CPU stopped.
                    after_key()
            if after_key is not None:mon.resume()
            # A document close reloads and rescans Files. Keep the same
            # bounded file/list-progress checks used for its initial launch.
            if reload:wait_loaded_app(target)
            def key_finished():
                with paused.paused('key-progress'):
                    unphase()
                    after=int.from_bytes(read(0x3d13,2),'little')
                    if after not in (before,(before+1)&65535):
                        raw=bytes(mon.read_mem(0,0x10ff,bank=banks['ram00']))
                        (work/'unexpected-key-input.bin').write_bytes(raw)
                        error,regs=mon._recv(mon._send(0x31,b'\0'));assert not error
                        report['unexpected_key_input']=dict(key=name,before=before,after=after,
                            input_device=raw[0x99],queue=raw[0xd0:0xd6].hex(),
                            keys=raw[0x34a:0x354].hex(),definitions=raw[0x1000:0x1100].hex(),
                            last_key=read(0x3d15)[0],registers_hex=regs.hex(),sha256=hashlib.sha256(raw).hexdigest())
                        save();raise AssertionError((name,'extra ROM key',before,after))
                    return (read(0x3d20)==b'\0' if target=='workspace' else header(target)) and ready() and after!=before
            wait(key_finished,name+' reaches '+target,120)
            after=int.from_bytes(read(0x3d13,2),'little')
            assert after==(before+1)&65535,(name,'extra or missing ROM key',before,after)
            report['events'].append(dict(key=name,target=target,keys_before=before,keys_after=after));save()
        def reu_snapshot(label):
            with paused.paused(label+'-reu'):
                memory,info=reu_dump(mon,work/(label+'-reu.vsf'))
            top=len(memory)-65536 if args.reu_kib>=512 else len(memory)  # the kernel module cache bank
            assert memory[72*256:top]==reu_documents.expected[72*256:top], 'complete REU bytes outside VDC backups, including document data and unused capacity'
            if top<len(memory):
                info['module_cache']=module_cache(memory,reu_initial,ROOT/'target/native-desktop')
            return memory,info
        def editor_reu_document(label,logical,*,loaded=False):
            if not args.reu_kib:return
            evidence=reu_documents.capture(capture,app_read,work,label,reu_snapshot,logical,loaded=loaded)
            report.setdefault('editor_reu_documents',[]).append(evidence);save()
            print('PASS: independent REU document and every unrelated byte:',label,len(logical),flush=True)
        def restore_checkpoint():
            entry=lst_symbol('native-desktop/vdsvc','vd_restore_registers')
            error,checkpoint=mon._recv(mon._send(0x12,entry.to_bytes(2,'little')*2+bytes([1,1,4,0,0])))
            assert not error
            checkpoint_id=checkpoint[:4]
            # A bank-0 app can execute at the same numeric address. Use the
            # MMU configuration register through the monitor's I/O bank.
            # https://vice-emu.sourceforge.io/vice_13.html (condition set 0x22)
            condition=b'@io:$d500 == $4e'
            error,_=mon._recv(mon._send(0x22,checkpoint_id+bytes([len(condition)])+condition))
            assert not error
            mon.resume()
            return entry,checkpoint_id
        def await_restore_checkpoint(entry,checkpoint_id,label):
            # Hit counts persist after a resume. Read the actual PC and MMU
            # while stopped before accepting a banked restoration checkpoint.
            # Register catalogs/responses: https://vice-emu.sourceforge.io/vice_13.html
            error,catalog=mon._recv(mon._send(0x83,b'\0'));assert not error
            at=2;pc_id=None
            for _ in range(int.from_bytes(catalog[:2],'little')):
                size=catalog[at];item=catalog[at+1:at+1+size];at+=size+1
                if item[3:3+item[2]]==b'PC':pc_id=item[0]
            assert pc_id is not None
            deadline=time.monotonic()+120
            while True:
                error,checkpoint=mon._recv(mon._send(0x11,checkpoint_id));assert not error
                error,registers=mon._recv(mon._send(0x31,b'\0'));assert not error
                at=2;pc=None
                for _ in range(int.from_bytes(registers[:2],'little')):
                    size=registers[at];item=registers[at+1:at+1+size];at+=size+1
                    if item[0]==pc_id:pc=int.from_bytes(item[1:],'little')
                mmu=bytes(mon.read_mem(0xd500,0xd500,bank=banks['io']))[0]
                observation=dict(pc=pc,mmu=mmu,checkpoint_hex=checkpoint.hex(),
                    register_catalog_hex=catalog.hex(),registers_hex=registers.hex())
                (work/(label+'-restore-observation.json')).write_text(json.dumps(observation,indent=2)+'\n')
                if pc==entry and mmu==0x4e:
                    assert int.from_bytes(checkpoint[13:17],'little')>0
                    return checkpoint
                assert time.monotonic()<deadline,('VDC restore checkpoint was not reached',observation)
                mon.resume();time.sleep(.1)
        def watch_app_vdc_restore(app,label):
            snapshot,restore=vdc_snapshot(capture,app_read,work,label,image_prefix='native-desktop/'+app,
                reu_snapshot=reu_snapshot if args.reu_kib else None)
            entry,checkpoint_id=restore_checkpoint()
            def finish():
                checkpoint=await_restore_checkpoint(entry,checkpoint_id,label)
                base=restore['base']
                restored=bytes(mon.read_mem(base,base+len(snapshot)-1,bank=banks['vdc']))
                (work/(label+'-restored-vram.bin')).write_bytes(restored)
                (work/(label+'-restore-checkpoint.bin')).write_bytes(checkpoint)
                assert restored==snapshot,'app VDC RAM was not restored before desktop handoff'
                assert bytes(mon.read_mem(0x3d20,0x3d20,bank=banks['ram00']))==b'\x20'
                restore.update(app=app,checkpoint_address=entry,checkpoint_hex=checkpoint.hex(),
                    lifetime='app snapshot still owned; VRAM restored before register restoration')
                report.setdefault('vdc_app_restores',[]).append(restore);save()
                error,_=mon._recv(mon._send(0x13,checkpoint_id));assert not error
                # key() releases the host key before resuming the app.
            return finish
        def screens(label,oracle):
            for mode,columns,address in ((0,40,0x400),(1,80,0)):
                actual=capture.capture(label+('-vic' if mode==0 else '-vdc'),mode=mode,address=address,count=columns*25)
                assert actual==oracle(columns),(label,columns)
            report['screens'].append(label);save()
        def claude_view(label,*,top=0,focus=0,error=0):
            # Since 331a881 the VDC mirrors the graphical launch page; the
            # 80-column landing text is the retained terminal model.
            actual,record=claude_capture(capture,app_read,claude_labels,work,label,
                panel=landing_screen(40,error),top=top,focus=focus,terminal_chars=landing_screen(80,error))
            assert value('cg_vdc_owned')==1
            def vdc_canvas():
                error,raw=mon._recv(mon._send(0x84,bytes([0,0])));mon.resume();assert not error
                return raw
            record['vdc']=vdc_capture(capture,app_read,vdc_canvas,work,label,focus,color=args.vdc64,
                                      surface_data=actual,image_prefix='native-desktop/claude-gui')
            xy=position();mode=modes.snapshot(label+'-mode');assert mode['vic_sprites']==3
            error,raw=mon._recv(mon._send(0x84,bytes([1,0])));mon.resume();assert not error
            (work/(label+'-canvas.bin')).write_bytes(raw)
            record.update(position=xy,mode=mode,rectangle=check_canvas(raw,surface_pixels(actual,*xy)))
            report.setdefault('claude_frames',[]).append(record);save()
            subprocess.run(['magick','import','-display',xv.display,'-window','root',str(work/(label+'.png'))],check=True,capture_output=True)
            print('PASS: Claude companion, VDC and 64000 mouse pixels:',label,flush=True)
        def claude_click(index):
            x0,y0,x1,y1=CLAUDE_RECTS[index];move_to((x0+x1)//2,(y0+y1)//2)
            before=int.from_bytes(read(0x3d13,2),'little')
            mouse.button(True);wait(lambda:value('pm_arm')==index,'Claude button armed',30)
            mouse.button(False);wait(lambda:ready() and value('pm_buttons')==0,'Claude click completed',120)
            assert int.from_bytes(read(0x3d13,2),'little')==before
            report['events'].append(dict(claude_button=index,keyboard_events_during_click=0));save()
        def calculator_view(label,display,history,selected,*,dialog=False,name='',cursor=0,status=0):
            wait(lambda:header('calc') and ready(),label,60)
            expected=dict(display=display,history=history,selected=selected,dialog=dialog,name=name,cursor=cursor,status=status)
            wanted=calc_surface(**expected)
            actual=b''.join(capture.capture(label+f'-surface-{offset:04x}',address=0xc000+offset,count=min(2000,9216-offset)) for offset in range(0,9216,2000))
            (work/(label+'-surface.bin')).write_bytes(actual);assert actual==wanted,(label,'calculator bitmap')
            for _ in range(20):
                xy=position();time.sleep(.2)
                if position()==xy:break
            else:raise AssertionError('calculator pointer did not settle')
            mode=modes.snapshot(label+'-mode');assert mode['vic_sprites']==3
            error,raw=mon._recv(mon._send(0x84,bytes([1,0])));mon.resume();assert not error
            (work/(label+'-canvas.bin')).write_bytes(raw)
            rectangle=check_canvas(raw,surface_pixels(wanted,*xy))
            def vdc_canvas():
                error,raw=mon._recv(mon._send(0x84,bytes([0,0])));mon.resume();assert not error
                return raw
            vdc=vdc_capture(capture,app_read,vdc_canvas,work,label,selected,color=args.vdc64,
                            surface_data=wanted,image_prefix='native-desktop/calc')
            report['calculator_frames'].append(dict(label=label,expected=expected,position=xy,rectangle=rectangle,mode=mode,vdc=vdc));save()
            subprocess.run(['magick','import','-display',xv.display,'-window','root',str(work/(label+'.png'))],check=True,capture_output=True)
            print('PASS: Calculator VIC/VDC graphics and 192000 pixels including both pointers:',label,flush=True)
        def calc_click(index):
            (x0,y0,x1,y1),_,_=BUTTONS[index]
            move_to((x0+x1)//2,(y0+y1)//2)
            before=int.from_bytes(read(0x3d13,2),'little')
            mouse.button(True);assert value('pm_arm')==index
            mouse.button(False)
            wait(ready,'calculator click ready',60)
            assert int.from_bytes(read(0x3d13,2),'little')==before
            report['events'].append(dict(calculator_button=index,keyboard_events_during_click=0));save()
        def mirrored_vdc(label,wanted,focus):
            def canvas():
                error,raw=mon._recv(mon._send(0x84,bytes([0,0])));mon.resume();assert not error
                return raw
            return vdc_capture(capture,app_read,canvas,work,label,focus,color=args.vdc64,
                               surface_data=wanted,image_prefix='native-desktop/'+pointer_app)
        def picker_view(label,entries,*,selected=0,mode=1,device=8,fmt=0):
            wait(lambda:ready() and app_read(picker_symbol(pointer_app,'pg_bitmap'))==b'\1',label,90)
            wait(lambda:value('pm_seen')==1,'picker pointer attached',20)
            def pv(name,count=1):return int.from_bytes(app_read(picker_symbol(pointer_app,name),count),'little')
            assert pv('fd_active')==1 and pv('b_selected',2)==selected and pv('fd_mode')==mode
            assert not pv('b_prompt') and not pv('pg_error')
            expected=dict(selected=selected,mode=mode,device=device,fmt=fmt,focus=pv('pg_focus'))
            entries=[dict(entry,app=False) for entry in entries]
            wanted=picker_surface(entries,**expected)
            actual=b''.join(capture.capture(label+f'-surface-{offset:04x}',address=0xc000+offset,count=min(2000,9216-offset)) for offset in range(0,9216,2000))
            (work/(label+'-surface.bin')).write_bytes(actual);assert actual==wanted,(label,'picker bitmap')
            vdc=None
            if pointer_app not in ('paint','controls','files','editor'):
                text_vdc=capture.capture(label+'-vdc',mode=1,address=0,count=2000)
                assert text_vdc==picker_console(entries,selected=selected,device=device,fmt=fmt),(label,'picker VDC')
            for _ in range(20):
                xy=position();time.sleep(.2)
                if position()==xy:break
            else:raise AssertionError('picker pointer did not settle')
            display=modes.snapshot(label+'-mode');assert display['vic_sprites']==3
            error,raw=mon._recv(mon._send(0x84,bytes([1,0])));mon.resume();assert not error
            (work/(label+'-canvas.bin')).write_bytes(raw);rectangle=check_canvas(raw,surface_pixels(wanted,*xy))
            if pointer_app in ('paint','controls','files','editor'):vdc=mirrored_vdc(label,wanted,pv('pg_focus'))
            report.setdefault('picker_frames',[]).append(dict(label=label,app=pointer_app,expected=expected,vdc=vdc,
                entries=[dict(name_hex=row['name'].hex(),type=row['type'],blocks=row['blocks'],flags=row.get('flags',128)) for row in entries],
                position=xy,rectangle=rectangle,mode=display));save()
            subprocess.run(['magick','import','-display',xv.display,'-window','root',str(work/(label+'.png'))],check=True,capture_output=True)
            print('PASS: shared picker bitmap, VDC and 64000 pointer pixels:',label,flush=True)
        def picker_click(index):
            x0,y0,x1,y1=PICKER_RECTS[index];move_to((x0+x1)//2,(y0+y1)//2)
            before=int.from_bytes(read(0x3d13,2),'little')
            mouse.button(True);wait(lambda:value('pm_arm')==index,'picker button armed',30)
            # The picker samples the 1351 every frame; poll readiness at a
            # random point of the frame, as move_to does.
            mouse.button(False);wait(lambda:value('pm_buttons')==0 and ready_unphased(),'picker click completed',120)
            after=int.from_bytes(read(0x3d13,2),'little');assert after==before
            report['events'].append(dict(picker_button=index,app=pointer_app,keyboard_events_during_click=after-before));save()

        def editor_view(label,data,cursor,*,focus=6,**expected):
            expected.setdefault('selection',editor_selection_expected)
            wait(lambda:header('editor') and ready(),label,90)
            state={name:value(name) for name in ('eg_bitmap','eg_error','ed_module_kind','ed_mode','ed_status','ui_selected','eg_more')}
            assert (state['eg_bitmap'],state['ed_module_kind'],state['ui_selected'])==(1,2,focus),(label,state)
            state['cursor']=int.from_bytes(app_read(symbol('ed_cursor'),3),'little')
            state['selection']=(tuple(int.from_bytes(app_read(symbol(name),3),'little')
                                      for name in ('es_first','es_limit')) if value('es_active') else None)
            assert state['selection']==expected['selection'],(label,state,expected['selection'])
            report.setdefault('editor_states',[]).append(dict(label=label,**state));save()
            assert state['cursor']==cursor,(label,state,cursor)
            assert state['ed_mode']==expected.get('mode',0) and state['ed_status']==expected.get('status',0),(label,state)
            assert state['eg_more']==expected.get('more',0),(label,'toolbar page',state)
            kwargs=dict(focus=focus,fmt=boot_format,**expected)
            kwargs.setdefault('view',int.from_bytes(app_read(symbol('ed_view'),3),'little'))
            kwargs.setdefault('horizontal',int.from_bytes(app_read(symbol('ed_horizontal'),3),'little'))
            wanted=editor_surface(data,cursor,**kwargs)
            actual=b''.join(capture.capture(label+f'-surface-{offset:04x}',address=0xc000+offset,count=min(2000,9216-offset)) for offset in range(0,9216,2000))
            (work/(label+'-surface.bin')).write_bytes(actual);assert actual==wanted,(label,'editor bitmap')
            for _ in range(20):
                xy=position();time.sleep(.2)
                if position()==xy:break
            else:raise AssertionError('editor pointer did not settle')
            mode=modes.snapshot(label+'-mode');assert mode['vic_sprites']==3
            error,raw=mon._recv(mon._send(0x84,bytes([1,0])));mon.resume();assert not error
            (work/(label+'-canvas.bin')).write_bytes(raw);rectangle=check_canvas(raw,surface_pixels(wanted,*xy))
            vdc=mirrored_vdc(label,wanted,focus)
            report['editor_frames'].append(dict(label=label,data_hex=data.hex(),cursor=cursor,expected=kwargs,position=xy,rectangle=rectangle,mode=mode,vdc=vdc));save()
            subprocess.run(['magick','import','-display',xv.display,'-window','root',str(work/(label+'.png'))],check=True,capture_output=True)
            print('PASS: Editor VIC/VDC graphics and 192000 pixels including both pointers:',label,flush=True)
        def editor_click(index,point=None,*,timeout=120):
            x0,y0,x1,y1=EDITOR_RECTS[index]
            move_to(*(point or ((x0+x1)//2,(y0+y1)//2)))
            before=int.from_bytes(read(0x3d13,2),'little')
            mouse.button(True);wait(lambda:value('pm_arm')==index,'editor button armed',30)
            mouse.button(False)
            # VICE services monitor requests at frame boundaries. A short
            # N_READY pulse between VDC presents can fall between every poll.
            # Stop at the real input loop, then inspect one CPU context; this
            # also distinguishes a completed click from a still-held button.
            entry=symbol('ed_get_key')
            error,checkpoint=mon._recv(mon._send(0x12,entry.to_bytes(2,'little')*2+bytes([1,1,4,0,0])))
            assert not error
            checkpoint_id=checkpoint[:4];deadline=time.monotonic()+timeout
            try:
                # The bank-1 REU transfer code can have the same numeric PC.
                # Restrict this stop to the foreground Editor's bank-0 map.
                condition=b'@io:$d500 == $0e'
                error,_=mon._recv(mon._send(0x22,checkpoint_id+bytes([len(condition)])+condition))
                assert not error
                while True:
                    with paused.paused('editor-click-idle'):
                        idle=ready()
                        released=value('ed_module_kind')!=2 or not value('eg_bitmap') or value('pm_buttons')==0
                        if idle and released:
                            error,registers=mon._recv(mon._send(0x31,b'\0'));assert not error
                            report.setdefault('editor_click_checkpoints',[]).append(dict(
                                button=index,address=entry,condition=condition.decode(),registers_hex=registers.hex()))
                            break
                    assert time.monotonic()<deadline,'editor click ready'
                    time.sleep(.2 if timeout>120 else .02)
            finally:
                error,_=mon._recv(mon._send(0x13,checkpoint_id));mon.resume();assert not error
            after=int.from_bytes(read(0x3d13,2),'little')
            report['events'].append(dict(editor_button=index,point=point,keyboard_events_during_click=after-before));save();assert after==before
        def controls_view(label,page,focus,notice=0,*,clock_text=None,caret=0):
            wait(lambda:header('controls') and ready(),label,60)
            state={name:value(name) for name in ('ug_bitmap','ug_error','uc_page','ui_selected','ug_mode','ug_notice')}
            report.setdefault('controls_states',[]).append(dict(label=label,**state));save()
            assert (state['ug_bitmap'],state['uc_page'],state['ui_selected'])==(1,page,focus),state
            dialog=2 if clock_text is not None else 0
            assert value('ug_mode')==dialog and value('ug_notice')==notice
            body=absent_body(page)
            if dialog:
                expected=clock_text.encode()
                assert app_read(symbol('ut_field'))==bytes([len(expected)])
                assert app_read(symbol('ut_edit'),len(expected))==expected
                assert app_read(symbol('ut_field')+1)==bytes([caret])
                body=['YYYY/MM/DD HH:MM:SS  (1980-2079)','',clock_text]
                if focus==17:body.append(' '*caret+'^')
            wanted=controls_surface(body[2:] if page==1 else body,page=page,focus=focus,notice=notice,mode=dialog)
            actual=b''.join(capture.capture(label+f'-surface-{offset:04x}',address=0xc000+offset,count=min(2000,9216-offset)) for offset in range(0,9216,2000))
            (work/(label+'-surface.bin')).write_bytes(actual);assert actual==wanted,(label,'Ultimate bitmap')
            for _ in range(20):
                xy=position();time.sleep(.2)
                if position()==xy:break
            else:raise AssertionError('Ultimate pointer did not settle')
            mode=modes.snapshot(label+'-mode');assert mode['vic_sprites']==3
            error,raw=mon._recv(mon._send(0x84,bytes([1,0])));mon.resume();assert not error
            (work/(label+'-canvas.bin')).write_bytes(raw)
            rectangle=check_canvas(raw,surface_pixels(wanted,*xy))
            def vdc_canvas():
                error,raw=mon._recv(mon._send(0x84,bytes([0,0])));mon.resume();assert not error
                return raw
            vdc=vdc_capture(capture,app_read,vdc_canvas,work,label,focus,color=args.vdc64,
                            surface_data=wanted,image_prefix='native-desktop/controls')
            report['controls_frames'].append(dict(label=label,page=page,focus=focus,notice=notice,position=xy,rectangle=rectangle,mode=mode,vdc=vdc));save()
            subprocess.run(['magick','import','-display',xv.display,'-window','root',str(work/(label+'.png'))],check=True,capture_output=True)
            print('PASS: Ultimate VIC/VDC graphics and 192000 pixels including both pointers:',label,flush=True)
        def controls_click(index):
            x0,y0,x1,y1=CONTROLS_RECTS[index]
            move_to((x0+x1)//2,(y0+y1)//2)
            before=int.from_bytes(read(0x3d13,2),'little')
            mouse.button(True);wait(lambda:value('pm_arm')==index,'Ultimate button armed',30)
            mouse.button(False);wait(ready,'Ultimate click ready',60)
            after=int.from_bytes(read(0x3d13,2),'little')
            report['events'].append(dict(controls_button=index,keyboard_events_during_click=after-before));save()
            assert after==before
        def files_state(label):
            with paused.paused(label+'-files-state'):
                state={name:value(name) for name in ('b_selected','b_busy','fg_key','fg_kind','fg_bitmap','fg_error')}
                if state['fg_kind']==1 and state['fg_bitmap']:
                    state.update({name:value(name) for name in ('ui_selected','fv_follow','fv_view','fv_previous_view',
                        'pm_hit','pm_event','pm_arm','pm_buttons')})
                    state['position']=position()
                state.update(ready=read(0x3d12)[0],module_state=read(0x3d1b)[0])
            report.setdefault('files_states',[]).append(dict(label=label,**state));save()
            return state
        def files_view(label,*,selected=0,focus=11,source=None,name=None,search_query=None,search_result=7,**kwargs):
            wait(lambda:header('files') and ready(),label,120)
            state=files_state(label)
            assert value('fg_kind')==1 and value('fg_bitmap')==1
            if state['ui_selected']!=focus:
                (work/(label+'-unexpected-surface.bin')).write_bytes(app_read(0xc000,9216))
                (work/(label+'-unexpected-vdc.bin')).write_bytes(read(0,2000,bank=banks['vdc']))
                raise AssertionError((label,'Files focus',state,focus))
            if search_query is not None:
                assert value('fm_active')==2 and value('fm_result')==search_result
                assert read(0x3d1b)==b'\x03', 'search modal remains inside the checked module'
                assert value('fm_length')==len(search_query)
                if search_query:
                    assert app_read(symbol('fm_name'),len(search_query))==search_query
                assert app_read(symbol('fm_state')+1)==bytes([len(search_query)])
                expected=dict(query_hex=search_query.hex(),focus=focus,result=search_result,device=8)
                wanted=files_find_surface(search_query,focus=focus,result=search_result,device=8)
            elif source is None:
                entries=disk_records(disk.read_bytes(),boot_format)
                expected=dict(selected=selected,focus=focus,fmt=boot_format,**kwargs)
                wanted=files_surface(entries,**expected)
                expected['records']=[dict(e,name=e['name'].hex()) for e in entries]
            else:
                expected=dict(source_device=8,source_format=boot_format,device=8,fmt=boot_format,kind=1,focus=focus);expected.update(kwargs)
                if expected['device']==9:expected['fmt']=0
                wanted=files_copy_surface(source,name,**expected)
                assert value('fc_source_device')==expected['source_device'] and value('fc_device')==expected['device']
                assert value('fc_length')==len(name) and app_read(symbol('fc_name'),len(name))==name
                for counter in ('copied','verified'):
                    assert int.from_bytes(app_read(symbol('fc_'+counter),4),'little')==kwargs.get(counter,0)
                assert value('fc_status')==kwargs.get('status',0)
                expected.update(source=source.hex(),name=name.hex())
            actual=b''.join(capture.capture(label+f'-surface-{offset:04x}',address=0xc000+offset,
                count=min(2000,9216-offset)) for offset in range(0,9216,2000))
            (work/(label+'-surface.bin')).write_bytes(actual);assert actual==wanted,(label,'Files bitmap')
            for _ in range(20):
                xy=position();time.sleep(.2)
                if position()==xy:break
            else:raise AssertionError('Files pointer did not settle')
            mode=modes.snapshot(label+'-mode');assert mode['vic_sprites']==3
            error,raw=mon._recv(mon._send(0x84,bytes([1,0])));mon.resume();assert not error
            (work/(label+'-canvas.bin')).write_bytes(raw)
            rectangle=check_canvas(raw,surface_pixels(wanted,*xy))
            vdc=mirrored_vdc(label,wanted,focus)
            report['files_frames'].append(dict(label=label,expected=expected,position=xy,rectangle=rectangle,mode=mode,vdc=vdc));save()
            subprocess.run(['magick','import','-display',xv.display,'-window','root',str(work/(label+'.png'))],check=True,capture_output=True)
            print('PASS: Files VIC/VDC graphics and 192000 pixels including both pointers:',label,flush=True)
        def files_click(index):
            x0,y0,x1,y1=FILES_RECTS[index];move_to((x0+x1)//2,(y0+y1)//2)
            before=int.from_bytes(read(0x3d13,2),'little')
            files_state(f'files-button-{index}-before')
            mouse.button(True);wait(lambda:value('pm_arm')==index,'Files button armed',30)
            files_state(f'files-button-{index}-armed')
            mouse.button(False)
            wait(lambda:ready() and (value('fg_kind')!=1 or not value('fg_bitmap') or
                value('pm_buttons')==0 and value('pm_arm')==255),'Files click ready',120)
            files_state(f'files-button-{index}-released')
            after=int.from_bytes(read(0x3d13,2),'little')
            report['events'].append(dict(files_button=index,keyboard_events_during_click=after-before));save()
            assert after==before
        def paint_view(label,document,*,dirty,mode=0,status=0):
            wait(lambda:header('paint') and ready(),label,120)
            assert value('pd_dirty')==dirty and value('pa_mode')==mode and value('pa_status')==status
            name=app_read(symbol('pf_name'),value('pf_length')) if value('pf_length') else b''
            expected=dict(view_x=value('pa_view_x'),view_y=value('pa_view_y'),focus=value('ui_selected'),
                x=int.from_bytes(app_read(symbol('pd_x'),2),'little'),y=value('pd_y'),pen=value('pd_pen'),color=value('pd_color'),
                dirty=bool(dirty),mode=mode,action=value('pa_action'),name=name.decode('latin1'),caret=value('pa_field_caret'),
                field_view=value('pa_field_view'),device=value('pf_device'),fmt=value('pf_format'))
            wanted=paint_surface(document,message=PAINT_MESSAGES[status],**dict(expected,name=name))
            tag=value('pd_handles');allocation=read(0x3c00+(tag-1)*8,8)
            assert allocation[:2]==bytes([32,1]) and allocation[3]==36
            page=allocation[2]
            observed=b''.join(capture.capture(label+f'-document-{offset:04x}',bank=1,address=page*256+offset,
                count=min(2000,9216-offset)) for offset in range(0,9216,2000))
            assert observed==document,(label,'banked document');(work/(label+'-document.bin')).write_bytes(observed)
            actual=b''.join(capture.capture(label+f'-surface-{offset:04x}',address=0xc000+offset,
                count=min(2000,9216-offset)) for offset in range(0,9216,2000))
            (work/(label+'-surface.bin')).write_bytes(actual);assert actual==wanted,(label,'Paint bitmap')
            field_view=app_read(symbol('pa_field')+6)[0]
            for _ in range(20):
                xy=position();time.sleep(.2)
                if position()==xy:break
            else:raise AssertionError('Paint pointer did not settle')
            display=modes.snapshot(label+'-mode');assert display['vic_sprites']==3
            error,raw=mon._recv(mon._send(0x84,bytes([1,0])));mon.resume();assert not error
            (work/(label+'-canvas.bin')).write_bytes(raw)
            rectangle=check_canvas(raw,surface_pixels(wanted,*xy))
            vdc=mirrored_vdc(label,wanted,value('ui_selected'))
            report['paint_frames'].append(dict(label=label,expected=expected,status=status,console_field_view=field_view,
                document_sha256=hashlib.sha256(document).hexdigest(),position=xy,rectangle=rectangle,mode=display,vdc=vdc));save()
            subprocess.run(['magick','import','-display',xv.display,'-window','root',str(work/(label+'.png'))],check=True,capture_output=True)
            print('PASS: complete Paint document, VIC/VDC graphics and 192000 pointer pixels:',label,flush=True)
        def paint_click(index):
            x0,y0,x1,y1=PAINT_RECTS[index];move_to((x0+x1)//2,(y0+y1)//2)
            before=int.from_bytes(read(0x3d13,2),'little')
            state=dict(before_keys=before,before_keyboard=read(0xd0,5).hex(),key_table=read(0x1000,20).hex())
            mouse.button(True);wait(lambda:value('pm_arm')==index,'Paint button armed',30)
            mouse.button(False);wait(ready,'Paint click ready',120)
            after=int.from_bytes(read(0x3d13,2),'little')
            state.update(after_keys=after,after_keyboard=read(0xd0,5).hex(),last_key=read(0x3d15).hex(),
                mode=value('pa_mode'),name_length=value('pf_length'),name=app_read(symbol('pf_name'),16).hex())
            report['events'].append(dict(paint_button=index,keyboard_events_during_click=after-before,input_state=state));save()
            assert after==before,state
        # Drain the window grab/warp through real relative input before the
        # first long capture. End in the margin, outside every app button.
        move_to(310,180)
        time.sleep(.5)
        key('Home','desktop')
        desktop('attached',0)
        if args.boot_frame_only:
            subprocess.run(['magick','import','-display',xv.display,'-window','root',str(work/'vdc-desktop.png')],check=True,capture_output=True)
            report['passed']=True;save()
            return
        # Seven 16-pixel cards since Sheet (f99fa51); aim at each card's centre row.
        move_to(100,CARDS[0]+8);desktop('calculator-hover',0)
        key('Down','desktop');desktop('keyboard-selection',1)
        time.sleep(.3);assert value('gd_selected')==1
        mouse.move(4,0);desktop('mouse-resumes',0)
        mouse.button(True);move_to(100,CARDS[1]+8);mouse.button(False);desktop('cancelled-drag',1)
        paint_document=bytearray(bytes(8192)+b'\x10'*1024)
        ran_apps=set()
        for index,name in enumerate(('calc','editor','files','controls','claude','paint')):
            if args.calc_only and name!='calc':continue
            if args.paint_only and name!='paint':continue
            if args.controls_only and name!='controls':continue
            if args.files_only and name!='files':continue
            if args.editor_only and name!='editor':continue
            if args.claude_only and name!='claude':continue
            ran_apps.add(name)
            move_to(100,CARDS[index]+8);desktop(name+'-hover',index)
            snapshot,restore=vdc_snapshot(capture,app_read,work,name+'-close',
                reu_snapshot=reu_snapshot if args.reu_kib else None)
            entry,checkpoint_id=restore_checkpoint()
            before=int.from_bytes(read(0x3d13,2),'little')
            mouse.button(True);assert header('desktop') and value('pm_arm')==index
            mouse.button(False)
            checkpoint=await_restore_checkpoint(entry,checkpoint_id,name+'-close')
            base=restore['base']
            restored=bytes(mon.read_mem(base,base+len(snapshot)-1,bank=banks['vdc']))
            (work/(name+'-restored-vram.bin')).write_bytes(restored)
            (work/(name+'-restore-checkpoint.bin')).write_bytes(checkpoint)
            assert restored==snapshot,'VDC snapshot was not fully restored before app handoff'
            assert bytes(mon.read_mem(0x3d20,0x3d20,bank=banks['ram00']))==b'\x20'
            restore.update(checkpoint_address=entry,checkpoint_hex=checkpoint.hex(),lifetime='desktop snapshot still owned; VRAM restored before register restoration')
            report.setdefault('vdc_restores',[]).append(restore);save()
            error,_=mon._recv(mon._send(0x13,checkpoint_id));assert not error
            mon.resume()
            wait_loaded_app(name)
            assert int.from_bytes(read(0x3d13,2),'little')==before,'mouse generated a keyboard shortcut'
            assert read(0x3d2c,2)==bytes([boot_format,8]) and read(0x3de4)==bytes([boot_format])
            if name=='editor':
                pointer_app='editor'
                assert app_read(symbol('pm_saved'),12)==saved_registers and app_read(symbol('pm_init_saved'))==saved_init
                wait(lambda:value('pm_seen')==1,'editor 1351 attached',15)
                move_to(164,172);editor_view('editor-open',b'',0)
                for char in ('c','1','2','8','space','t','e','x','t'):key(char,'editor')
                document=b'C128 TEXT';editor_view('editor-typed',document,len(document),dirty=True)
                if args.reu_kib:
                    for offset,char in enumerate(document):reu_documents.history.edit(offset,b'',bytes([char]))
                editor_reu_document('editor-typed-reu',document,loaded=True)
                if args.editor_clipboard:
                    def editor_control(letter):
                        # Pause immediately after the ROM-fed event counter
                        # increments, so a slow module read cannot turn a held
                        # host shortcut into an unintended repeated command.
                        before=int.from_bytes(read(0x3d13,2),'little')
                        entry=lst_symbol(kernel_prefix+'/kestrel','native_key_done')
                        error,checkpoint=mon._recv(mon._send(0x12,entry.to_bytes(2,'little')*2+bytes([1,1,4,0,0])))
                        assert not error
                        checkpoint_id=checkpoint[:4]
                        def sampled():
                            deadline=time.monotonic()+120
                            while True:
                                count=int.from_bytes(mon.read_mem(0x3d13,0x3d14,bank=banks['ram00']),'little')
                                if count!=before:break
                                assert time.monotonic()<deadline,'clipboard ROM shortcut sampled'
                                mon.resume();time.sleep(.01)
                            assert count==(before+1)&65535
                            report.setdefault('clipboard_key_checkpoints',[]).append(dict(key=letter,address=entry,before=before,after=count))
                        try:
                            with mouse.held_key('Control_L'):key(letter,'editor',after_key=sampled)
                        finally:
                            error,_=mon._recv(mon._send(0x13,checkpoint_id));mon.resume()
                    editor_control('a');editor_selection_expected=(0,len(document))
                    editor_control('c')
                    editor_view('editor-clipboard-copy',document,len(document),dirty=True,status=20)
                    meta=capture.capture('clipboard-metadata',address=0x3de5,count=27)
                    token=meta[6:10];assert meta[:3]==bytes([1,0,1]) and 1<=token[0]<=32
                    record=capture.capture('clipboard-record',address=0x3c00+(token[0]-1)*8,count=8)
                    assert record[:2]==bytes([31,1]) and record[4:7]==token[1:]
                    assert capture.capture('clipboard-text',address=record[2]*256,count=len(document),bank=1)==document
                    editor_control('g');editor_selection_expected=None
                    original=document
                    editor_control('v');document+=original
                    if args.reu_kib:reu_documents.insert(len(original),original)
                    editor_view('editor-clipboard-paste',document,len(document),dirty=True,status=21)
                    editor_control('a');editor_selection_expected=(0,len(document))
                    editor_control('v')
                    if args.reu_kib:reu_documents.replace(0,len(document),original)
                    document=original;editor_selection_expected=None
                    editor_view('editor-clipboard-replace',document,len(document),dirty=True,status=21)
                    editor_control('a');editor_selection_expected=(0,len(document))
                    editor_control('x')
                    if args.reu_kib:reu_documents.replace(0,len(document),b'')
                    editor_selection_expected=None
                    editor_view('editor-clipboard-cut',b'',0,dirty=True,status=20)
                    editor_control('v')
                    if args.reu_kib:reu_documents.insert(0,document)
                    editor_view('editor-clipboard-restored',document,len(document),dirty=True,status=21)
                    editor_control('k')
                    editor_view('editor-clipboard-cleared',document,len(document),dirty=True,status=26)
                    assert capture.capture('clipboard-cleared',address=0x3de7,count=8)[:5]==bytes(5)
                    report['editor_clipboard']=True;save()
                if args.editor_history:
                    editor_control('z')
                    if args.reu_kib:reu_documents.replace(*reu_documents.history.replay(),record=False)
                    editor_view('editor-history-key-undo',b'',0,dirty=True,status=27)
                    editor_reu_document('editor-history-key-undo-reu',b'')
                    editor_control('y')
                    if args.reu_kib:reu_documents.replace(*reu_documents.history.replay(True),record=False)
                    editor_view('editor-history-key-redo',document,len(document),dirty=True,status=28)
                    editor_reu_document('editor-history-key-redo-reu',document)
                    for _ in range(4):editor_click(5)
                    editor_view('editor-history-toolbar',document,len(document),dirty=True,focus=5,more=4,status=28)
                    editor_click(27)
                    if args.reu_kib:reu_documents.replace(*reu_documents.history.replay(),record=False)
                    editor_view('editor-history-mouse-undo',b'',0,dirty=True,status=27,more=4)
                    editor_reu_document('editor-history-mouse-undo-reu',b'')
                    editor_click(28)
                    if args.reu_kib:reu_documents.replace(*reu_documents.history.replay(True),record=False)
                    editor_view('editor-history-mouse-redo',document,len(document),dirty=True,status=28,more=4)
                    editor_reu_document('editor-history-mouse-redo-reu',document)
                    editor_click(5);editor_click(6,(84,60))
                    editor_view('editor-history-return',document,len(document),dirty=True)
                    report['editor_history']=True;save()
                if args.editor_selection:
                    with mouse.held_key('Control_L'):key('b','editor')
                    for _ in range(3):key('Left','editor')
                    editor_selection_expected=(6,9)
                    editor_view('editor-keyboard-selection',document,6,dirty=True)
                    key('e','editor');editor_selection_expected=None
                    document=b'C128 TE'
                    if args.reu_kib:reu_documents.replace(6,3,b'E')
                    editor_view('editor-selection-replaced',document,7,dirty=True)
                    editor_reu_document('editor-selection-replaced-reu',document)
                    for char in 'xt':
                        if args.reu_kib:reu_documents.insert(len(document),char.upper().encode())
                        key(char,'editor');document+=char.upper().encode()
                    editor_view('editor-selection-continued',document,9,dirty=True)
                    editor_reu_document('editor-selection-continued-reu',document)
                editor_click(6,(28,60));editor_view('editor-caret',document,2,dirty=True)
                key('x','editor');document=b'C1X28 TEXT';editor_view('editor-insert',document,3,dirty=True)
                if args.reu_kib:reu_documents.insert(2,b'X')
                editor_reu_document('editor-insert-reu',document)
                if args.editor_selection:
                    move_to(8,60);mouse.button(True)
                    wait(lambda:value('es_drag')==1,'document drag armed',30)
                    # move_to accepts a two-pixel tolerance; aim inside the
                    # fourth cell, not at its boundary with the third cell.
                    move_to(36,60);mouse.button(False)
                    wait(lambda:ready() and value('es_drag')==0 and value('pm_buttons')==0,'document drag completed',90)
                    editor_selection_expected=(0,3)
                    editor_view('editor-mouse-selection',document,3,dirty=True)
                editor_click(2)
                for char in 'guinote':key(char,'editor')
                field=dict(mode=2,field='GUINOTE',field_caret=7,field_view=0,dirty=True)
                editor_view('editor-save-dialog',document,3,focus=11,**field)
                editor_click(14)
                assert value('ed_module_kind')==1 and value('fd_active')==1 and not value('eg_bitmap')
                entries=disk_records(disk.read_bytes(),boot_format)
                for entry in entries:entry['app']=False
                picker_view('editor-destination-picker',entries,mode=2,fmt=boot_format)
                picker_click(18);wait(lambda:value('pm_seen')==1,'editor pointer after picker',15)
                editor_view('editor-picker-return',document,3,focus=11,**field)
                editor_device=8 if args.d81 else 9
                if editor_device==9:
                    # Select a separate data disk through the real picker while the
                    # app, its modules and the desktop keep their system source.
                    editor_click(14);picker_click(1)
                    key('9','editor');key('Return','editor')
                    picker_view('editor-data-picker',[],mode=2,device=9)
                    picker_click(17);wait(lambda:value('pm_seen')==1,'editor pointer after data selection',15)
                    field['device']=9
                    editor_view('editor-data-destination',document,3,focus=11,**field)
                editor_click(12);editor_view('editor-saved',document,3,name='GUINOTE',status=1,device=editor_device)
                if args.reu_kib:reu_documents.history.save()
                editor_click(3);key('x','editor')
                editor_view('editor-find',document,3,name='GUINOTE',mode=6,field='X',field_caret=1,field_view=0,focus=11,device=editor_device)
                editor_click(12);editor_selection_expected=None
                editor_view('editor-found',document,8,name='GUINOTE',status=13,device=editor_device)
                report['editor_destination_device']=editor_device
                report['editor_saved_hex']=document.hex();save()
                if args.editor_large:
                    report['editor_large_io_deadline_seconds']=600;save()
                    # Host F5 maps to native New; host F7 maps to Go To.
                    key('F5','editor')
                    reu_documents.history.clear()
                    editor_click(1)
                    for char in 'large':key(char,'editor')
                    editor_click(12,timeout=600)
                    editor_view('editor-large-open',editor_large,0,name='LARGE')
                    editor_reu_document('editor-large-input-reu',editor_large,loaded=True)
                    key('F7','editor')
                    for char in '018001':key(char,'editor')
                    key('Return','editor')
                    edit_at=98305+(editor_large[98304:98306]==b'\r\n')
                    for char in 'reu96':key(char,'editor')
                    for offset,char in enumerate(b'REU96'):reu_documents.insert(edit_at+offset,bytes([char]))
                    edited=editor_large[:edit_at]+b'REU96'+editor_large[edit_at:]
                    editor_view('editor-large-edited',edited,edit_at+5,name='LARGE',dirty=True)
                    editor_reu_document('editor-large-edit-reu',edited)
                    editor_click(2)
                    for char in 'reucopy':key(char,'editor')
                    editor_click(14)
                    entries=disk_records(disk.read_bytes(),boot_format)
                    for entry in entries:entry['app']=False
                    picker_view('editor-large-picker',entries,mode=2,fmt=boot_format)
                    editor_reu_document('editor-large-picker-reu',edited)
                    picker_click(18)
                    editor_click(12,timeout=600)
                    editor_view('editor-large-saved',edited,edit_at+5,name='REUCOPY',status=1)
                    reu_documents.history.save()
                    editor_reu_document('editor-large-saved-reu',edited)
                    key('F5','editor')
                    reu_documents.history.clear()
                    editor_click(1)
                    for char in 'reucopy':key(char,'editor')
                    editor_click(12,timeout=600)
                    editor_view('editor-large-reopened',edited,0,name='REUCOPY')
                    editor_reu_document('editor-large-reopened-reu',edited,loaded=True)
                    (work/'expected-reu-copy.seq').write_bytes(edited)
                    report['editor_large_bytes']=len(edited)
                    report['editor_large_sha256']=hashlib.sha256(edited).hexdigest();save()
            elif name=='calc':
                pointer_app='calc'
                assert app_read(symbol('pm_saved'),12)==saved_registers and app_read(symbol('pm_init_saved'))==saved_init
                wait(lambda:value('pm_seen')==1,'calculator 1351 attached',15)
                move_to(112,152)
                wait(lambda:value('ui_selected')==14,'calculator equals focus',15)
                calculator_view('calculator-open','0',[],14)
                for button in (8,9,15,10,13,14):calc_click(button)
                calculator_view('calculator-result','42',['42'],14)
                calc_click(17)
                for char in 'guihist':key(char,'calc')
                calculator_view('calculator-save','42',['42'],21,dialog=True,name='GUIHIST',cursor=7)
                calc_click(21)
                wait(lambda:value('save_status')==1,'history saved and verified',60)
                calculator_view('calculator-saved','42',['42'],17,status=1)
                calc_click(17)
                for char in 'cancel':key(char,'calc')
                calc_click(22)
                calculator_view('calculator-cancelled','42',['42'],17)
            elif name=='files':
                pointer_app='files'
                assert app_read(symbol('pm_saved'),12)==saved_registers and app_read(symbol('pm_init_saved'))==saved_init
                wait(lambda:value('pm_seen')==1,'Files 1351 attached',15)
                move_to(310,180);key('Home','files');files_view('files-open')
                files_click(7);files_view('files-next-page',selected=8,focus=7)
                files_click(6);files_view('files-previous-page',focus=6)
                if args.files_find:
                    entries=disk_records(disk.read_bytes(),boot_format)
                    doc=next(i for i,e in enumerate(entries) if e['name'].rstrip(b'\xa0')==b'DOC.TXT')
                    browse=next(i for i,e in enumerate(entries) if e['name'].rstrip(b'\xa0')==b'BROWSE')
                    assert doc>=8 and browse<8
                    files_click(31);files_view('files-find-dialog',search_query=b'',focus=25)
                    for char in 'doc':key(char,'files')
                    files_view('files-find-query',search_query=b'DOC',focus=25)
                    files_click(26);files_view('files-found-document',selected=doc,focus=11+doc%8)
                    files_click(31)
                    for _ in range(3):key('BackSpace','files')
                    for char in 'browse':key(char,'files')
                    files_click(26);files_view('files-find-wrapped',selected=browse,focus=11+browse)
                    files_click(31)
                    for _ in range(6):key('BackSpace','files')
                    for char in 'zznomatch':key(char,'files')
                    files_click(26)
                    files_view('files-find-missing',search_query=b'ZZNOMATCH',search_result=8,focus=25)
                    files_click(27);files_view('files-find-kept-selection',selected=browse,focus=11+browse)
                    report['filename_search']=dict(document=b'DOC.TXT'.hex(),document_ordinal=doc,
                        wrapped_to=b'BROWSE'.hex(),wrapped_ordinal=browse,missing_kept_selection=True)
                    save()
                entries=disk_records(disk.read_bytes(),boot_format);source=b'EDFIND.PRG'
                chosen=next(i for i,e in enumerate(entries) if e['name'].rstrip(b'\xa0')==source)
                assert chosen<8
                files_click(11+chosen);files_view('files-selected',selected=chosen,focus=11+chosen)
                files_click(10);files_view('files-copy-dialog',source=source,name=source,focus=25)
                for _ in source:key('BackSpace','files')
                for char in 'fscopy':key(char,'files')
                files_view('files-copy-name',source=source,name=b'FSCOPY',focus=25)
                files_click(22)
                assert value('fg_kind')==2 and value('fc_picker_active') and not value('fg_bitmap')
                picker_view('files-copy-picker',entries,mode=2,fmt=boot_format)
                picker_click(18);move_to(310,180)
                for _ in range(28):
                    if value('ui_selected')==25:break
                    key('F10','files')
                else:raise AssertionError('Files field focus unavailable after picker')
                files_view('files-picker-return',source=source,name=b'FSCOPY',focus=25)
                # Keep a separate data disk: the complete suite plus history,
                # an Editor file, this module copy and a Paint image exceed a
                # single D64. Exercise mouse Device and Use Here in the picker.
                files_click(22)
                if args.d81:
                    picker_click(2);picker_click(2)  # D81 -> Ultimate -> D64
                picker_click(1)
                key('9','files');key('Return','files')
                picker_view('files-data-picker',disk_records(data_disk.read_bytes(),0),mode=2,device=9)
                picker_click(17);move_to(310,180)
                for _ in range(28):
                    if value('ui_selected')==25:break
                    key('F10','files')
                else:raise AssertionError('Files field focus unavailable after destination selection')
                files_view('files-data-destination',source=source,name=b'FSCOPY',focus=25,device=9)
                files_click(23)
                copied_source=exact_disk_files((image/disk_name).read_bytes(),boot_format)[source]
                assert copied_source[0]==2
                files_view('files-copy-verified',source=source,name=b'FSCOPY',focus=23,device=9,
                    copied=len(copied_source[1]),verified=len(copied_source[1]),status=1)
                files_click(24);move_to(310,180)
                key('Up','files');key('Down','files')
                files_view('files-copy-return',selected=chosen,focus=11+chosen)
                if args.files_open_with:
                    for document,target,button in ((b'DOC.TXT','editor',28),(b'DRAW.UPNT','paint',29)):
                        entries=disk_records(disk.read_bytes(),boot_format)
                        selected=next(i for i,e in enumerate(entries) if e['name'].rstrip(b'\xa0')==document)
                        while value('b_selected')//8<selected//8:files_click(7)
                        while value('b_selected')//8>selected//8:files_click(6)
                        files_click(11+selected%8)
                        files_view('open-with-'+target+'-selected',selected=selected,focus=11+selected%8)
                        x0,y0,x1,y1=FILES_RECTS[button];move_to((x0+x1)//2,(y0+y1)//2)
                        before=int.from_bytes(read(0x3d13,2),'little')
                        mouse.button(True);wait(lambda:value('pm_arm')==button,'Open With button armed',30)
                        mouse.button(False);wait_loaded_app(target);pointer_app=target
                        assert int.from_bytes(read(0x3d13,2),'little')==before
                        assert read(0x3d9a)==b'\0' and read(0x3d9d)==b'\1'
                        assert read(0x3d29,2)==bytes([8,boot_format])
                        assert read(0x3e00,len(document))==document
                        if target=='editor':
                            editor_view('open-with-editor',open_text,0,name='DOC.TXT',device=8,dirty=False,field='DOC.TXT')
                        else:
                            paint_view('open-with-paint',open_picture,dirty=0,status=2)
                        key('F9','files',reload=True);pointer_app='files'
                        assert read(0x3d9a)==b'\0' and read(0x3d9d,2)==b'\0\0'
                        move_to(310,180)
                        files_view('open-with-'+target+'-returned',selected=selected,focus=11+selected%8)
                        report.setdefault('open_with',[]).append(dict(app=target,name_hex=document.hex(),button=button,selected=selected,keyboard_events_during_click=0))
                        save()
            elif name=='controls':
                pointer_app='controls'
                assert app_read(symbol('pm_saved'),12)==saved_registers and app_read(symbol('pm_init_saved'))==saved_init
                wait(lambda:value('pm_seen')==1,'Ultimate 1351 attached',15)
                move_to(44,40);controls_view('ultimate-open',0,0)
                controls_click(1);controls_view('ultimate-drives',1,1)
                controls_click(8);controls_view('ultimate-missing-drive',1,8,5)
                controls_click(2);controls_view('ultimate-network',2,2)
                controls_click(3);controls_view('ultimate-clock',3,3)
                controls_click(7);controls_view('ultimate-refresh',3,7)
                if args.controls_clock:
                    controls_click(16)
                    controls_view('ultimate-clock-edit',3,17,clock_text='2000/01/01 00:00:00')
                    key('Right','controls');key('BackSpace','controls');key('9','controls');key('Return','controls')
                    controls_view('ultimate-clock-invalid',3,17,13,clock_text='9000/01/01 00:00:00',caret=1)
                    key('F10','controls')
                    controls_view('ultimate-clock-confirm-focus',3,10,13,clock_text='9000/01/01 00:00:00',caret=1)
                    controls_click(11);controls_view('ultimate-clock-cancelled',3,16,2)
                    controls_click(16);controls_click(10)
                    controls_view('ultimate-clock-unavailable',3,16,14)
                # Stock GTK symbolic mapping: host F10 is the C128 Tab key.
                controls_click(0);key('F10','controls');controls_view('ultimate-tab',0,1)
                key('Return','controls');controls_view('ultimate-enter',1,1)
            elif name=='claude':
                pointer_app='claude'
                assert app_read(symbol('pm_saved'),12)==saved_registers and app_read(symbol('pm_init_saved'))==saved_init
                wait(lambda:value('pm_seen')==1,'Claude 1351 attached',15)
                # 331a881 put the view selector between Prev and Next; rest the
                # pointer outside every Claude button, as ci_native_claude_iec does.
                move_to(160,100);claude_view('claude-open')
                claude_click(4);claude_view('claude-next-page',top=9,focus=3)
                claude_click(3);claude_view('claude-previous-page',focus=4)
                claude_click(0);claude_view('claude-port-unavailable',top=9,focus=0,error=2)
            elif name=='paint':
                pointer_app='paint'
                assert read(0x033c,2)==symbol('pk_entry').to_bytes(2,'little')
                assert app_read(symbol('pm_saved'),12)==saved_registers and app_read(symbol('pm_init_saved'))==saved_init
                wait(lambda:value('pm_seen')==1,'Paint 1351 attached',15)
                move_to(310,180);paint_view('paint-open',paint_document,dirty=0)
                versions=[]
                for tx,ty,color in ((48,56,1),(88,80,2)):
                    if color!=1:paint_click(7+color)
                    move_to(tx,ty);wait(ready,'Paint brush move',60);time.sleep(.3)
                    x,y=position();assert abs(x-tx)<=2 and abs(y-ty)<=2,('Paint pointer moved after settling',(x,y),(tx,ty))
                    versions.append(bytes(paint_document));xx,yy=x-8,y-32
                    paint_document[yy//8*320+xx//8*8+yy%8]|=128>>(xx%8)
                    paint_document[8192+yy//8*40+xx//8]=color*16
                    before=int.from_bytes(read(0x3d13,2),'little')
                    mouse.button(True);wait(lambda:value('pd_dirty')==1 and ready(),'Paint draws point',60)
                    mouse.button(False);wait(ready,'Paint stroke released',60)
                    after=int.from_bytes(read(0x3d13,2),'little')
                    report['events'].append(dict(paint_point=[xx,yy],color=color,keyboard_events_during_click=after-before,
                        before_keys=before,after_keys=after,last_key=read(0x3d15).hex()));save()
                    assert after==before,report['events'][-1]
                paint_view('paint-drawing',paint_document,dirty=1)
                paint_click(2);paint_view('paint-undo',versions[-1],dirty=1)
                paint_click(2);paint_view('paint-redo',paint_document,dirty=1)
                paint_click(4)
                for char in 'paintpic':key(char,'paint')
                key('F10','paint')
                paint_device,paint_format,paint_disk=(8,2,disk) if args.d81 else (9,0,data_disk)
                # Files retained data-drive preferences. Select this volume explicitly.
                if args.d81:
                    for _ in range((paint_format-read(0x3d2a)[0])%4):picker_click(2)
                picker_click(1)
                key(str(paint_device),'paint');key('Return','paint')
                picker_view('paint-save-destination',disk_records(paint_disk.read_bytes(),paint_format),mode=2,device=paint_device,fmt=paint_format)
                picker_click(17)
                paint_view('paint-save-dialog',paint_document,dirty=1,mode=2)
                paint_click(24);wait(lambda:value('pa_status')==1,'Paint save verified',120)
                paint_view('paint-saved',paint_document,dirty=0,status=1)
                paint_click(4);paint_click(24);assert value('pa_status')==4
                paint_view('paint-collision',paint_document,dirty=0,status=4)
                paint_click(4)
                for char in 'cancel':key(char,'paint')
                paint_click(25);paint_view('paint-cancelled',paint_document,dirty=0)
                paint_click(3);assert value('pd_dirty')==1
                paint_click(5);paint_view('paint-open-confirm',bytes(8192)+b'\x10'*1024,dirty=1,mode=1)
                paint_click(24);assert value('pa_picker_active')==1 and not value('pa_bitmap')
                entries=disk_records(paint_disk.read_bytes(),paint_format)
                for entry in entries:entry['app']=False
                chosen=next(i for i,entry in enumerate(entries) if entry['name'].rstrip(b'\xa0')==b'PAINTPIC')
                key('Home','paint')
                for _ in range(chosen):key('Down','paint')
                picker_view('paint-file-picker',entries,selected=chosen,device=paint_device,fmt=paint_format)
                picker_click(16);paint_view('paint-loaded',paint_document,dirty=0,status=2)
                report['paint_filtered_line_samples']=int.from_bytes(app_read(symbol('pk_rejects'),2),'little');save()
            else:
                current=bytes(read(0xd000+at,bank=banks['io'])[0] for at in (0,1,2,3,0x10,0x15,0x17,0x1b,0x1c,0x1d,0x27,0x28))
                assert current==saved_registers,(name,'sprite register leak',current.hex(),saved_registers.hex())
                assert read(0xa04)==saved_init,(name,'BASIC sprite hook leak')
            # Stock GTK symbolic mapping: host F9 is the C128 Escape key.
            restore_labels={'calc':'calculator-close','controls':'ultimate-close','paint':'paint-app-close','files':'files-app-close','editor':'editor-app-close'}
            after_key=watch_app_vdc_restore(name,restore_labels[name]) if name in restore_labels else None
            key('F8' if name=='claude' else 'F9','desktop',after_key=after_key)
            pointer_app='desktop'
            desktop(name+'-returned',index)
            assert capture.capture(name+'-keys-restored',address=0x1000,count=256)==saved_keys
            assert read(0x033c,2)==saved_callback
            report['events'].append(dict(mouse_app=name,keyboard_events_during_click=0));save()
        before=int.from_bytes(read(0x3d13,2),'little');mouse.press('F9')
        wait(lambda:read(0x3d20)==b'\0' and ready(),'workspace exit',60)
        assert int.from_bytes(read(0x3d13,2),'little')==before+1
        if args.d81:
            key('c','calc')
            assert read(0x3d21)==b'\x08' and read(0x3d2c,2)==bytes([2,8])
            key('F9','workspace')
            key('b','desktop');pointer_app='desktop'
            desktop('workspace-shortcut-return',value('gd_selected'))
            key('F9','workspace')
            report['workspace_system_shortcuts']=True
        with paused.paused('restore-repeat'):paused.write_mem(0xa22,repeat)
        assert read(0xa22)==repeat
        screens('workspace',lambda cols:expected_screen(cols,0))
        report['final_mode']=modes.snapshot('workspace-mode');assert report['final_mode']['vic_sprites']==0
        heap=capture.capture('final-page-table',address=0x3800,count=0x200)
        records=capture.capture('final-records',address=0x3c00,count=0x100)
        assert heap[0x50:0xff]==bytes(175) and heap[0x104:0x1ff]==bytes(251)
        assert all(records[i*8]==0 for i in range(32))
        report['resident_return']=verify_running_layout(capture,ROOT,'resident-return',image_dir=ROOT/'target'/kernel_prefix)
        # Independently export each created file and preserve every shipped file.
        contents=exact_disk_files(disk.read_bytes(),boot_format)
        before_files=exact_disk_files((image/disk_name).read_bytes(),boot_format)
        if args.editor_large:
            assert contents.pop(b'LARGE')==(1,editor_large)
            assert contents.pop(b'REUCOPY')==(1,(work/'expected-reu-copy.seq').read_bytes())
            exported=work/'exported-reu-copy.seq'
            subprocess.run(['c1541','-attach',str(disk),'-read','reucopy,s,r',str(exported)],check=True,capture_output=True)
            assert exported.read_bytes()==(work/'expected-reu-copy.seq').read_bytes()
            report['editor_large_independent_export_matches']=True
        if 'calc' in ran_apps:assert contents.pop(b'GUIHIST')==(1,b'42\r')
        if args.files_open_with:
            assert contents.pop(b'DOC.TXT')==(1,open_text)
            assert contents.pop(b'DRAW.UPNT')==(1,paint_encode(open_picture))
        data_contents=exact_d64_files(data_disk.read_bytes())
        if 'editor' in ran_apps:
            assert (contents if editor_device==8 else data_contents).pop(b'GUINOTE')==(1,bytes.fromhex(report['editor_saved_hex']))
        if 'paint' in ran_apps:assert (contents if args.d81 else data_contents).pop(b'PAINTPIC')==(1,paint_encode(paint_document))
        assert exact_d64_files((work/'initial-data-9.d64').read_bytes())=={}
        assert data_contents==({b'FSCOPY':copied_source} if 'files' in ran_apps else {})
        assert contents==before_files
        if 'paint' in ran_apps:
            report['paint_file_sha256']=hashlib.sha256(paint_encode(paint_document)).hexdigest()
            report['paint_destination_device']=paint_device
        if 'calc' in ran_apps:report['calculator_history_export_hex']=b'42\r'.hex()
        if 'files' in ran_apps:
            report['files_copy_sha256']=hashlib.sha256(copied_source[1]).hexdigest()
            report['files_copy_destination_device']=9
        report['system_disk_files_preserved']=True
        report['passed']=True;save()
    except BaseException as error:
        report['error']=repr(error)
        if mon is not None:
            try:
                # Keep one stopped CPU context when diagnosing a timeout. A
                # header alone cannot distinguish a loader from directory I/O.
                with paused.paused('failure-diagnostic'):
                    error_code,registers=mon._recv(mon._send(0x31,b'\0'))
                    assert not error_code
                    report['failure_registers_hex']=registers.hex()
                    report['failure_state']={hex(at):bytes(paused.read_mem(at,at+count-1)).hex()
                        for at,count in ((0xd0,8),(0xa20,16),(0x3d00,256),(0x100,256),(0xdc00,16),(0xdd00,16),(0xd02f,1),(0xd419,2))}
                    for name in ('desktop','calc','editor','files','controls','claude','paint'):
                        if bytes(paused.read_mem(0x3d60,0x3d7f))==(image/(name+'.prg')).read_bytes()[2:34]:
                            data=bytes(paused.read_mem(0x6000,0xbfff,bank=banks['ram00']))
                            (work/('failure-'+name+'-ram.bin')).write_bytes(data)
                            workspace=bytes(paused.read_mem(0x5000,0x5fff,bank=banks['ram00']))
                            (work/('failure-'+name+'-workspace.bin')).write_bytes(workspace)
                            report['failure_app']=name
                            break
            except BaseException as diagnostic:report['diagnostic_error']=repr(diagnostic)
            try:subprocess.run(['magick','import','-display',xv.display,'-window','root',str(work/'failure.png')],check=True,capture_output=True)
            except BaseException as diagnostic:report['screenshot_error']=repr(diagnostic)
        raise
    finally:
        if mouse is not None:
            mouse.button(False);mouse.close()
        if mon is not None:
            try:mon.quit_emulator()
            except (OSError,EOFError):pass
            mon.close()
        if emu is not None:
            try:emu.wait(timeout=2)
            except subprocess.TimeoutExpired:emu.terminate();emu.wait(timeout=5)
        xv.stop();log.close()
        report['xvfb_terminal']=xv.proc.poll() is not None
        report['all_host_processes_terminal']=(emu is None or emu.poll() is not None) and report['xvfb_terminal']
        report['system_disk_unchanged']=disk.read_bytes()==(image/disk_name).read_bytes()
        save()


if __name__=='__main__':main()
