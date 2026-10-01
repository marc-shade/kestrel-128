#!/usr/bin/env python3
"""Graphical editor, banked documents and verified saves through real C128 IEC."""
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
from native_editor_scene import surface,console
from native_picker_scene import surface as picker_surface,console as picker_console
from native_picker_check import picker_symbol
from native_browser_check import browser_screen,disk_records
from native_pointer_check import surface_pixels,check_canvas
from native_vdc_check import capture_frame as vdc_capture


def main():
    work=Path(tempfile.mkdtemp(prefix='kestrel-native-editor-gui-iec-'))
    print('Native graphical editor IEC evidence:',work,flush=True)
    shutil.copy2(__file__,work/'run.py')
    disk=work/'suite.d64';shutil.copy2(ROOT/'target/native-desktop/kestrel.d64',disk)
    disks={d:work/f'data-{d}.d81' for d in (9,10)}
    for device,path in disks.items():subprocess.run(['c1541','-format',f'editor{device},02','d81',str(path)],check=True,capture_output=True)
    fixtures=dict(note=b'ONE "QUOTED"\r\nTWO\nTHREE\r'+bytes([0,255])+b' END',
                  large=(b'0123456789 ABCDEFGHIJKLMNOPQRSTUVWXYZ\r\n'*1800)[:66053],
                  fits=(b'0123456789 ABCDEFGHIJKLMNOPQRSTUVWXYZ\r\n'*900)[:32000])
    for name,data in fixtures.items():
        p=work/(name+'.bin');p.write_bytes(data)
        subprocess.run(['c1541','-attach',str(disks[9]),'-write',str(p),name+',s'],check=True,capture_output=True)
    filler=work/'entry.bin';filler.write_bytes(b'F')
    for index in range(293):
        subprocess.run(['c1541','-attach',str(disks[9]),'-write',str(filler),f'entry{index:03},s'],check=True,capture_output=True)
    originals={d:p.read_bytes() for d,p in disks.items()}
    for d,raw in originals.items():(work/f'initial-{d}.d81').write_bytes(raw)
    report=dict(passed=False,physical_hardware_io=False,events=[],desktops=[],screens=[],editor_documents=[],editor_io_frames=[],
        images={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ('target/native','target/native-desktop') for p in (ROOT/folder).iterdir() if p.suffix in ('.prg','.d64')})
    def save():(work/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    names=('ed_active','ed_cursor','ed_view','ed_horizontal','ed_mode','ed_status','ed_device','ed_format','ed_name',
           'ed_field','ed_field_len','ed_field_cursor','ed_field_views','ed_field_filter','d_states','eg_bitmap','ed_module_kind','ui_selected')
    addresses={n:lst_symbol('native-desktop/editor',n) for n in names}
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    mon=process=xv=None;log=(work/'vice.log').open('w')
    try:
        xv=ci.cbm.Xvfb()
        command=['x128','-default','-8',str(disk),'-drive8true','-drive8type','1541',
            '-9',str(disks[9]),'-drive9true','-drive9type','1581','-10',str(disks[10]),'-drive10true','-drive10type','1581',
            '-sounddev','dummy','-jamaction','0','-warp','-binarymonitor','-binarymonitoraddress',f'ip4://127.0.0.1:{port}']
        report['emulator_command']=command;save()
        process=subprocess.Popen(command,env=dict(os.environ,DISPLAY=xv.display,__EGL_VENDOR_LIBRARY_FILENAMES=ci.cbm.MESA_EGL),stdout=log,stderr=subprocess.STDOUT)
        deadline=time.monotonic()+30
        while mon is None:
            assert process.poll() is None
            try:mon=ci.Monitor(port=port)
            except OSError:
                if time.monotonic()>deadline:raise
                time.sleep(.1)
        banks=mon.banks();mon.resume()
        class ObserverRAM:
            # The IRQ probe calls the ROM's banked reader. A monitor poll of
            # the CPU view can see document RAM instead of the bank-0 status
            # byte while that reader temporarily selects bank 1. Pin control
            # traffic; requested document data still comes from the CPU probe.
            def read_mem(self,start,end,bank=None):
                raw=mon.read_mem(start,end,bank=banks['ram00'] if bank is None else bank)
                if start==end==0x3ff2 and bank is None:
                    logical=mon.read_mem(start,end)
                    if bytes(logical)!=bytes(raw):
                        report.setdefault('bank_poll_differences',[]).append(dict(
                            cpu_view=bytes(logical).hex(),control_ram=bytes(raw).hex()))
                return raw
            def write_mem(self,start,data,bank=None):
                return mon.write_mem(start,data,bank=banks['ram00'] if bank is None else bank)
            def resume(self):mon.resume()
        paused=PausedViceMonitor(ObserverRAM())
        @contextmanager
        def stable_batch(label):
            if not label.endswith(('-before','-restore')):
                with paused.paused(label):yield
                return
            deadline=time.monotonic()+30;deferred=0
            while True:
                with paused.paused(label):
                    idle=bytes(paused.read_mem(0x3d11,0x3d12))==b'\0\1' and bytes(paused.read_mem(0xd0,0xd0))==b'\0'
                    if idle:
                        report.setdefault('capture_admissions',[]).append(dict(label=label,deferred=deferred))
                        yield
                        return
                deferred+=1
                assert time.monotonic()<deadline,('idle capture admission',label)
                time.sleep(.01)
        report['capture_control_bank']='ram00'
        capture=NativeCapture(paused,work,quiet=.05,kernel_prefix='native-desktop',batch=stable_batch)
        report['captures']=capture.records;report['paused_capture_batches']=paused.batches
        def app_read(name,count=1):
            at=addresses[name];raw=bytes(paused.read_mem(at,at+count-1,bank=banks['ram00']));paused.resume();return raw
        def document(label,wanted):
            active=capture.capture(label+'-active',address=addresses['ed_active'],count=1)[0]
            state=capture.capture(label+'-context',address=addresses['d_states']+active,count=128)
            records=capture.capture(label+'-handles',address=0x3c00,count=256)
            physical=bytearray();handles=[]
            for index in range(state[13]):
                handle=state[16+index*4:20+index*4];record=records[(handle[0]-1)*8:handle[0]*8]
                # Complete 4 KiB chunks, except that the last may be 1..15 pages (DOC_PARTIAL).
                last=index==state[13]-1;size=record[3]*256
                assert record[0]==32 and (record[3]==16 or (last and 1<=record[3]<16)) and record[4:7]==handle[1:]
                prefix=label+f'-chunk-{index:02}'
                raw=b''.join(capture.capture(prefix+f'-part-{offset:04x}',bank=record[1],address=record[2]*256+offset,
                    count=min(2000,size-offset)) for offset in range(0,size,2000))
                (work/(prefix+'.bin')).write_bytes(raw);physical.extend(raw)
                handles.append(dict(handle_hex=handle.hex(),bank=record[1],page=record[2],sha256=hashlib.sha256(raw).hexdigest()))
            length=int.from_bytes(state[:3],'little');gap=int.from_bytes(state[3:6],'little');end=int.from_bytes(state[6:9],'little');capacity=int.from_bytes(state[9:12],'little')
            assert 0<=gap<=end<=capacity==len(physical)
            actual=bytes(physical[:gap]+physical[end:capacity])
            assert actual==wanted and length==len(wanted) and not state[14],label
            if len(wanted)>65536:assert {h['bank'] for h in handles}=={0,1}
            report['editor_documents'].append(dict(label=label,bytes=length,sha256=hashlib.sha256(actual).hexdigest(),gap=gap,gap_end=end,capacity=capacity,handles=handles));save()

        def mirror(label,wanted,focus):
            # Since c4647f7/d334b47 Editor and its picker mirror the VIC surface
            # on the VDC; compare the whole VDC bitmap and frame with that surface.
            def vread(at,count):
                raw=bytes(paused.read_mem(at,at+count-1,bank=banks['ram00']));paused.resume();return raw
            def canvas():
                error,raw=mon._recv(mon._send(0x84,bytes([0,0])));mon.resume();assert not error
                return raw
            return vdc_capture(capture,vread,canvas,work,label,focus,surface_data=wanted,image_prefix='native-desktop/editor')
        def workflow(*,key,screens,desktop,read):
            table=capture.capture('editor-key-table-before',address=0x1000,count=256)
            key(ord('E'))
            def function_key(value):
                codes=bytes.fromhex('8589868a878b888c8384');assert read(0x1000,20)==bytes([1]*10)+codes
                before=None;deadline=time.monotonic()+120
                # Editor clears N_READY during each pointer sample (e632b33);
                # inject only at a paused idle instant, within a bound.
                while before is None:
                    with paused.paused('editor-rom-function-key'):
                        if read(0x3d12)==b'\1' and read(0xd0,2)==bytes(2):
                            before=int.from_bytes(read(0x3d13,2),'little')
                            paused.write_mem(0x3d12,b'\0');paused.write_mem(0xd1,bytes([1,codes.index(value)]));paused.resume()
                    if before is None:
                        assert time.monotonic()<deadline,'editor never idle for function-key injection'
                        time.sleep(.01)
                wait(lambda:read(0x3d12)==b'\1' and int.from_bytes(read(0x3d13,2),'little')==(before+1)&65535,'editor function-key expansion',60)
                assert read(0xd0,2)==bytes(2);paused.write_mem(0xd2,b'\0');paused.resume()
                report['events'].append(dict(key=value,rom_expansion=True));save()
            def prompt(code,value):
                function_key(code)
                for char in value.encode():key(char)
                key(13)
            def check(label,data,cursor,*,device=9,fmt=2,dirty=False,name='',status=0,mode=0,field='',field_caret=None,focus=6):
                start=addresses['ed_active'];state=capture.capture(label+'-state',address=start,count=addresses['ed_field_filter']-start+1)
                def number(n,size=1):return int.from_bytes(state[addresses[n]-start:addresses[n]-start+size],'little')
                def string(n):return state[addresses[n]-start:addresses[n]-start+256].split(b'\0')[0].decode('latin1')
                assert number('ed_cursor',3)==cursor and string('ed_name')==name
                assert (number('ed_status'),number('ed_mode'),number('ed_device'),number('ed_format'))==(status,mode,device,fmt)
                assert app_read('eg_bitmap')==b'\1' and app_read('ed_module_kind')==b'\2' and app_read('ui_selected')==bytes([focus])
                context=capture.capture(label+'-document-flags',address=addresses['d_states']+number('ed_active'),count=16)
                assert int.from_bytes(context[:3],'little')==len(data) and context[12]==int(dirty) and not context[14]
                if mode:assert string('ed_field')==field
                if field_caret is not None:assert number('ed_field_cursor')==field_caret
                expected=dict(name=name,dirty=dirty,device=device,fmt=fmt,status=status,mode=mode,field=string('ed_field'),
                    field_caret=number('ed_field_cursor'),view=number('ed_view',3),horizontal=number('ed_horizontal',3),focus=focus)
                views=[number('ed_field_views'),state[addresses['ed_field_views']-start+1]]
                wanted=surface(data,cursor,field_view=views[0],**expected)
                actual=b''.join(capture.capture(label+f'-surface-{offset:04x}',address=0xc000+offset,count=min(2000,9216-offset)) for offset in range(0,9216,2000))
                (work/(label+'-surface.bin')).write_bytes(actual);assert actual==wanted,(label,'editor bitmap')
                vdc=mirror(label,wanted,focus)
                error,raw=mon._recv(mon._send(0x84,bytes([1,0])));mon.resume();assert not error
                (work/(label+'-canvas.bin')).write_bytes(raw);rectangle=check_canvas(raw,surface_pixels(wanted,0,0,visible=False))
                report['editor_io_frames'].append(dict(label=label,data_sha256=hashlib.sha256(data).hexdigest(),cursor=cursor,expected=expected,field_views=views,rectangle=rectangle,vdc=vdc));save()
                print('PASS: graphical editor state, complete bitmap/VDC and VIC pixels:',label,flush=True)
            prompt(0x8c,'9');function_key(0x8b);function_key(0x8b)
            prompt(0x85,'NOTE');check('mixed-newlines',fixtures['note'],0,name='NOTE');document('mixed-document',fixtures['note'])
            function_key(0x87);check('new-document',b'',0)
            # This machine has a VDC and no REU: the Editor's 80-column mirror keeps
            # its snapshot in RAM (175/167 free pages, NATIVE-EDITOR-GUI.md), so a
            # 66,053-byte RAM document is refused and the current one kept. The
            # rest of the workflow uses a document that fits beside the picker.
            prompt(0x85,'LARGE');check('large-refused',b'',0,status=3);document('large-refused-kept',b'')
            prompt(0x85,'FITS');data=fixtures['fits'];check('large-opened',data,0,name='FITS');document('large-input',data)
            prompt(0x88,'004001');at=16385
            if data[at-1:at+1]==b'\r\n':at+=1
            check('large-position',data,at,name='FITS')
            for char in b'C128':key(char)
            wanted=data[:at]+b'C128'+data[at:];check('large-edited',wanted,at+4,name='FITS',dirty=True);document('large-edit',wanted)
            function_key(0x86)
            for char in b'COPY':key(char)
            check('save-field',wanted,at+4,name='FITS',dirty=True,mode=2,field='COPY',field_caret=4,focus=11)
            function_key(0x88);assert app_read('ed_module_kind')==b'\1' and app_read('eg_bitmap')==b'\0'
            entries=disk_records(originals[9],2)
            assert len(entries)==296
            def picker_check(label,selected):
                pg={n:picker_symbol('editor',n) for n in ('fd_active','pg_bitmap','pg_focus','b_selected','b_cache')}
                flags={n:capture.capture(label+'-'+n,address=at,count=2 if n=='b_selected' else 1) for n,at in pg.items() if n!='b_cache'}
                assert flags['fd_active']==flags['pg_bitmap']==b'\1' and int.from_bytes(flags['b_selected'],'little')==selected
                expected=dict(focus=flags['pg_focus'][0],selected=selected,device=9,fmt=2,mode=2)
                wanted=picker_surface(entries,**expected)
                actual=b''.join(capture.capture(label+f'-surface-{offset:04x}',address=0xc000+offset,count=min(2000,9216-offset)) for offset in range(0,9216,2000))
                (work/(label+'-surface.bin')).write_bytes(actual);assert actual==wanted,(label,'picker bitmap')
                vdc=mirror(label,wanted,expected['focus'])
                cache=capture.capture(label+'-cache',address=pg['b_cache'],count=40)
                descriptors=capture.capture(label+'-descriptors',address=0x3c00,count=256)
                pages=0
                for at in range(0,40,4):
                    handle=cache[at:at+4]
                    if not handle[0]:continue
                    descriptor=descriptors[(handle[0]-1)*8:handle[0]*8]
                    assert descriptor[0]==32 and descriptor[4:7]==handle[1:]
                    pages+=descriptor[3]
                assert pages==19
                error,raw=mon._recv(mon._send(0x84,bytes([1,0])));mon.resume();assert not error
                (work/(label+'-canvas.bin')).write_bytes(raw);rectangle=check_canvas(raw,surface_pixels(wanted,0,0,visible=False))
                report.setdefault('picker_io_frames',[]).append(dict(label=label,expected=expected,entries=296,banked_cache_pages=pages,rectangle=rectangle,vdc=vdc));save()
                print('PASS: full D81 graphical picker beside banked document:',label,flush=True)
            picker_check('large-picker-first',0)
            for _ in range(36):key(ord('N'))
            picker_check('large-picker-last',288)
            document('large-document-during-picker',wanted)
            for char in b'D10\rS':key(char)
            check('save-destination',wanted,at+4,name='FITS',dirty=True,device=10,mode=2,field='COPY',field_caret=4,focus=11)
            key(13);check('large-saved',wanted,at+4,name='COPY',device=10,status=1);document('large-after-save',wanted)
            prompt(0x86,'COPY');check('existing-refused',wanted,at+4,name='COPY',device=10,status=6)
            function_key(0x87);prompt(0x85,'COPY');check('copy-reopened',wanted,0,name='COPY',device=10);document('large-reopened',wanted)
            key(27);desktop('desktop-after-large-editor',1)
            assert capture.capture('editor-key-table-restored',address=0x1000,count=256)==table
            report.update(saved_bytes=len(wanted),saved_sha256=hashlib.sha256(wanted).hexdigest(),edit_offset=at)
            (work/'expected-copy.bin').write_bytes(wanted);save()
        run_native_workflow(paused,capture,work,disk,report,save,key_quiet=.1,key_poll=.1,additional_apps=workflow)
        assert disks[9].read_bytes()==originals[9]
        assert hashlib.sha256(disk.read_bytes()).hexdigest()==report['images']['target/native-desktop/kestrel.d64']
        exported=work/'exported-copy.bin';subprocess.run(['c1541','-attach',str(disks[10]),'-read','copy,s,r',str(exported)],check=True,capture_output=True)
        assert exported.read_bytes()==(work/'expected-copy.bin').read_bytes()
        records=disk_records(disks[10].read_bytes(),2);assert [(r['name'],r['type']) for r in records]==[(b'COPY',1)]
        report.update(passed=True,source_disk_unchanged=True,system_disk_unchanged=True,independent_export_matches=True);save()
        print('PASS: 66 KiB RAM document refused beside the RAM VDC snapshot; 32 KB document edited across chunks, picker retention, reopened save and independent export',flush=True)
    except BaseException as error:
        report['error']=dict(type=type(error).__name__,message=str(error));raise
    finally:
        if mon is not None:
            try:mon.quit_emulator()
            except (OSError,EOFError):pass
            mon.close()
        if process is not None:
            try:process.wait(timeout=2)
            except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=5)
        if xv is not None:xv.stop()
        log.close();report['all_host_processes_terminal']=(process is None or process.poll() is not None) and (xv is None or xv.proc.poll() is not None);save()

if __name__=='__main__':main()
