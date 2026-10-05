#!/usr/bin/env python3
"""Cold-boot Sheet from the desktop and round-trip a workbook through VICE IEC."""
import argparse
import binascii
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'tests')]
import vice_harness as ci
from native_capture import wait
from native_vdc_mirror import bitmap, attributes, pixels
from native_vdc_scene import bitmap as desktop_bitmap, attributes as desktop_attributes
from launcher_scene import surface, pointer_shape
from native_pointer_check import check_canvas, surface_pixels
from src.native.graphics.font import font


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--80col', dest='eighty', action='store_true')
    parser.add_argument('--vdc64', action='store_true')
    parser.add_argument('--clipboard', action='store_true')
    parser.add_argument('--reu-kib', type=int, choices=(512,), help='attach an REU: the module cache runs')
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix='kestrel-sheet-vice-'))
    print('Sheet VICE evidence:', work, flush=True)
    disk = work/'suite.d81'; shutil.copy2(ROOT/'target/native-desktop/kestrel.d81', disk)
    data_disk = work/'data.d81'
    subprocess.run(['c1541', '-format', 'sheet,02', 'd81', str(data_disk)], check=True, capture_output=True)
    labels = {name:int(value,16) for value,name in re.findall(
        r'^al ([0-9a-fA-F]+) \.(\S+)', (ROOT/'target/native-desktop/sheet.lbl').read_text(), re.M)}
    ds = {name:int(value,16) for name,value in re.findall(
        r'^(\w+)\s*=\s*\$([0-9a-fA-F]+)', (ROOT/'target/native-desktop/desktop.sym').read_text(), re.M)}
    report = dict(passed=False, physical_hardware_io=False, options=vars(args), events=[], frames=[],
                  inputs={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (
                      ROOT/'target/native-desktop/kestrel.d81', ROOT/'target/native-desktop/sheet.prg',
                      ROOT/'target/native-desktop/shfont.prg', ROOT/'target/native-desktop/shcalc.prg',
                      ROOT/'target/native-desktop/shclip.prg',
                      ROOT/'target/native-desktop/desktop.prg', ROOT/'target/native-desktop/vdsvc.prg')})
    (work/'initial-suite.d81').write_bytes(disk.read_bytes())
    shutil.copy2(__file__, work/'run.py')
    def save(): (work/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
    mon = process = xv = None
    log = (work/'vice.log').open('w')
    if args.reu_kib:
        from native_reu_check import initial_memory
        reu_initial = initial_memory(args.reu_kib)
        (work/'initial.reu').write_bytes(reu_initial)
    try:
        xv = ci.cbm.Xvfb()
        command = ['x128', '-default', '-80col' if args.eighty else '-40col',
                   '-8', str(disk), '-drive8true', '-drive8type', '1581',
                   '-9', str(data_disk), '-drive9true', '-drive9type', '1581',
                   '-VDC64KB' if args.vdc64 else '-VDC16KB', '-sounddev', 'dummy',
                   *(['-reu', '-reusize', str(args.reu_kib), '-reuimage', str(work/'initial.reu'), '+reuimagerw']
                     if args.reu_kib else []),
                   '-jamaction', '0', '-warp', '-binarymonitor', '-binarymonitoraddress', f'ip4://127.0.0.1:{port}']
        report['command'] = command; save()
        process = subprocess.Popen(command, env=dict(os.environ, DISPLAY=xv.display,
            __EGL_VENDOR_LIBRARY_FILENAMES=ci.cbm.MESA_EGL), stdout=log, stderr=subprocess.STDOUT)
        deadline = time.monotonic()+30
        while mon is None:
            assert process.poll() is None, 'VICE exited'
            try: mon = ci.Monitor(port=port)
            except OSError:
                if time.monotonic() > deadline: raise
                time.sleep(.1)
        banks = mon.banks(); mon.resume()
        def read(at, count=1, bank=None):
            raw = bytes(mon.read_mem(at, at+count-1, bank=banks['ram00'] if bank is None else bank))
            mon.resume(); return raw
        def sym(name): return labels[name] if name in labels else labels['_'+name]
        def value(name): return read(sym(name))[0]
        def ready(): return read(0x3d12) == b'\1' and read(0xd0,2) == bytes(2)
        def key(code):
            wait(ready, 'Sheet input readiness', 180)
            before = int.from_bytes(read(0x3d13,2),'little'); start = time.monotonic()
            mon.write_mem(0x3d12,b'\0',bank=banks['ram00'])
            mon.write_mem(0x34a,bytes([code]),bank=banks['ram00'])
            mon.write_mem(0xd0,b'\1',bank=banks['ram00']);mon.resume()
            wait(lambda:ready() and int.from_bytes(read(0x3d13,2),'little')==(before+1)&65535,
                 f'Sheet key {code:02x}', 180)
            report['events'].append(dict(key=code,seconds=round(time.monotonic()-start,3)));save()
        def canvas(index):
            error, raw = mon._recv(mon._send(0x84,bytes([0 if index else 1,0])));mon.resume()
            assert not error;return raw
        def capture(label, desktop=None):
            wait(ready, label+' idle', 180)
            vic = read(0xc000,9216)
            if desktop is None:
                chars=read(sym('sg_chars'),1000);colors=read(sym('sg_colors'),1000)
                (work/(label+'-chars.bin')).write_bytes(chars)
                (work/(label+'-colors.bin')).write_bytes(colors)
                expected=bytearray(9216);glyphs=font()
                for cell,code in enumerate(chars): expected[cell*8:cell*8+8]=glyphs[(code-32)*8:(code-31)*8]
                expected[8192:9192]=colors;expected[8000:8128]=pointer_shape();expected[9208:9210]=b'\x7d\x7e'
                assert vic==expected, label+' VIC'
                assert value('vd_live')==1 and value('vd_fault')==0
                expected_vdc=bitmap(vic,args.vdc64);expected_attrs=attributes(vic)
                expected_pixels=pixels(vic,args.vdc64)
            else:
                assert read(ds['gd_selected'])==bytes([desktop])
                assert vic==surface(desktop),label+' desktop VIC'
                expected_vdc=desktop_bitmap(desktop);expected_attrs=desktop_attributes(desktop)
                expected_pixels=None
            base=0x4000 if args.vdc64 else 0
            vdc=read(base,16000,banks['vdc']);assert vdc==expected_vdc,label+' VDC'
            (work/(label+'-vic.bin')).write_bytes(vic);(work/(label+'-vdc.bin')).write_bytes(vdc)
            if args.vdc64: assert read(0x8000,2000,banks['vdc'])==expected_attrs
            # Let the emulator produce a video frame after the last memory update.
            time.sleep(.1)
            raw=canvas(0);(work/(label+'-vic-canvas.bin')).write_bytes(raw)
            vic_rect=check_canvas(raw,surface_pixels(vic,0,0,visible=False))
            if expected_pixels is not None:
                raw=canvas(1);(work/(label+'-vdc-canvas.bin')).write_bytes(raw)
                vdc_rect=check_canvas(raw,expected_pixels)
            else: vdc_rect=None
            report['frames'].append(dict(label=label,vic_rectangle=vic_rect,vdc_rectangle=vdc_rect));save()
            print('PASS: both displays:',label,flush=True)
        def sources():
            token=read(sym('wb_handle'),4);desc=read(0x3c00+(token[0]-1)*8,8)
            assert desc[:2]==bytes([32,1]) and desc[3]==32 and desc[4:7]==token[1:]
            return read(desc[2]*256,8192,banks['ram01'])
        wait(lambda:read(0x1c13,6)==b'KES128' and ready(),'D81 desktop cold boot',180)
        capture('desktop',0);key(ord('S'));capture('blank-sheet')
        for code in b'12\r\x1d30\r\x1d=A1+B1\r':key(code)
        values=read(sym('sh_values'),12)
        assert values==b''.join(n.to_bytes(4,'little') for n in (12,30,42))
        records=bytearray(8192)
        for index,text in {0:b'12',1:b'30',2:b'=a1+b1'}.items():records[index*32:index*32+len(text)]=text
        assert sources()==records
        capture('calculated-sheet')
        if args.clipboard:
            key(3);key(0x1d);key(22)
            assert read(sym('sh_values')+12,4)==(42).to_bytes(4,'little')
            assert sources()[96:128]==records[64:96]
            capture('clipboard-paste')
            key(24);assert read(sym('sh_values')+12,4)==bytes(4)
            key(26);assert read(sym('sh_values')+12,4)==(42).to_bytes(4,'little')
            key(0x14);key(0x9d);assert sources()==records
            capture('clipboard-cut-undo-clear')
        key(0x87);key(0x86)  # Save As; data drive 8 -> 9, system D81 geometry retained.
        for code in b'BUDGET':key(code)
        key(13);assert not value('wb_dirty') and not value('wb_error');capture('verified-save')
        key(0x85);key(0x86)  # New then Open on the retained data device.
        key(13);assert sources()==records and not value('wb_error');capture('reopened-workbook')
        key(27);capture('desktop-return',6)
        assert read(0x3d2d)==b'\10' and read(0x3de4)==b'\2'
        if args.reu_kib:
            # The module cache owns the REU's top bank. Repeated loads that hit
            # add no entries, so each name appears once, sealed to Sheet's core,
            # with a byte-exact image.
            assert read(0x3d9f)==b'\x10'
            from native_reu_check import module_cache,snapshot
            loads=int.from_bytes(read(0x3db0,3),'little')  # module generation: one per load
            mon.read_mem(0x3d12,0x3d12)  # binary monitor commands leave the emulator stopped
            memory,info=snapshot(mon,work/'final.vsf');mon.resume()
            top=len(memory)-65536
            # The first 72 pages hold the VDC service's screen backups.
            assert memory[72*256:top]==reu_initial[72*256:top],'REU bytes changed between the VDC backups and the cache bank'
            names=module_cache(memory,reu_initial,ROOT/'target/native-desktop')
            assert names,names
            # Every miss appends an entry (no reset happened with three names), so
            # the remaining loads were served from the REU.
            hits=loads-len(names);assert hits>0,(loads,names)
            report['module_cache']=dict(entries=names,loads=loads,hits=hits,snapshot=info)
            print('PASS: REU module cache holds',names,'and served',hits,'of',loads,'loads',flush=True)
        mon.quit_emulator();mon.close();mon=None
        process.wait(timeout=15)
        out=work/'budget.usht'
        subprocess.run(['c1541','-attach',str(data_disk),'-read','budget,s',str(out)],check=True,capture_output=True)
        expected=b'USHT\1\10\40\40\0\40'+binascii.crc_hqx(records,65535).to_bytes(2,'little')+bytes(4)+records
        assert out.read_bytes()==expected
        report.update(passed=True,saved_bytes=len(expected),saved_sha256=hashlib.sha256(expected).hexdigest())
        print('PASS: cold boot, desktop launch, edit/recalc, independent IEC save/readback, reopen and desktop return',flush=True)
    except BaseException as error:
        report['error']=repr(error);raise
    finally:
        if mon:
            try:mon.quit_emulator()
            except (EOFError,OSError):pass
            mon.close()
        if process and process.poll() is None:
            process.terminate();process.wait(timeout=15)
        if xv:xv.stop()
        log.close();save()


if __name__=='__main__':main()
