#!/usr/bin/env python3
"""Cold-boot Kestrel, launch packaged Claude, run the real TCP/PTY bridge, return."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'tests'), str(ROOT/'apps/claude/host')]
import vice_harness as ci
from native_capture import NativeCapture, wait, expected_screen
from native_capture_transport import PausedViceMonitor
from native_claude_check import landing_screen,waiting_panel,capture_frame
from native_claude_scene import RECTS
from native_pointer_check import surface_pixels,check_canvas
from native_vdc_check import capture_frame as vdc_capture,saved_region as saved_vdc_region
from ci_native_pointer_iec import Mouse
from launcher_scene import surface, console
import font
import petscii


def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0)); return sock.getsockname()[1]


def main():
    p = argparse.ArgumentParser(); p.add_argument('--host-exit', action='store_true')
    p.add_argument('--cpu-capture', action='store_true', help='verify settled terminal through the physical IRQ observer')
    p.add_argument('--mouse', action='store_true', help='real 1351 session controls and ROM Ctrl+Help')
    p.add_argument('--80col', dest='eighty', action='store_true')
    p.add_argument('--vdc64', action='store_true'); args = p.parse_args()
    if args.cpu_capture and args.host_exit:
        p.error('--cpu-capture requires the stationary fixture without the updating status panel')
    work = Path(tempfile.mkdtemp(prefix='kestrel-native-claude-iec-'))
    print('Native Claude evidence:', work, flush=True)
    disk = work/'suite.d64'; shutil.copyfile(ROOT/'target/native-desktop/kestrel.d64', disk)
    hashes = {name: hashlib.sha256((ROOT/'target/native-desktop'/name).read_bytes()).hexdigest()
              for name in ('kestrel.prg','kestrel.d64','desktop.prg','controls.prg','claude.prg')}
    result = dict(passed=False, physical_hardware_io=False, options=vars(args), images=hashes, events=[])
    labels = {m[2]:int(m[1],16) for m in re.finditer(r'^al ([0-9A-Fa-f]+) \.(\S+)',
              (ROOT/'target/native-desktop/claude.lbl').read_text(), re.M)}
    for name in ('claude.prg','claude.lbl','desktop.prg'):
        shutil.copyfile(ROOT/'target/native-desktop'/name, work/name)
    shutil.copyfile(__file__, work/'run.py')
    xv = ci.cbm.Xvfb(geometry='1920x1200x24'); mon = emu = bridge = mouse = None
    result['private_x_display']=xv.display
    emulog = (work/'vice.log').open('w'); hostlog = (work/'bridge.log').open('w')
    try:
        linkport, monport = port(), port()
        fixture = ROOT/'tests/fixtures/claude-session.py'
        fixture_control=work/'fixture-control.txt'
        host = [sys.executable, '-B', str(ROOT/'apps/claude/run.py'), '--listen', str(linkport),
                '--command', shlex.join([sys.executable,'-B',str(fixture),str(fixture_control)]), '-v']
        if not args.host_exit or args.mouse: host.append('--no-panel')
        bridge = subprocess.Popen(host, stdout=hostlog, stderr=subprocess.STDOUT)
        # Readiness from the bridge's actual log, without consuming its one connection.
        wait(lambda:'listening on' in (work/'bridge.log').read_text(), 'bridge listening', 15)
        command = ['x128','-default','-80col' if args.eighty else '-40col','-8',str(disk),
            '-drive8true','-drive8type','1541','-VDC64KB' if args.vdc64 else '-VDC16KB','-sounddev','dummy','-jamaction','0','-warp',
            '-acia1','-acia1base','0xDE00','-acia1irq','1','-acia1mode','1','-myaciadev','0',
            '-rsdev1',f'127.0.0.1:{linkport}','-rsdev1baud','38400',
            '-binarymonitor','-binarymonitoraddress',f'ip4://127.0.0.1:{monport}']
        # GTK's initial 80-column window motion can move a live 1351 over a
        # launcher card before this test owns input. Enable host motion only
        # after checking the untouched cold boot and launching Claude.
        if args.mouse:command += ['-controlport1device','3','-controlport2device','0','+mouse']
        result.update(emulator_command=command, bridge_command=host)
        emu = subprocess.Popen(command, env=dict(os.environ, DISPLAY=xv.display,
            __EGL_VENDOR_LIBRARY_FILENAMES=ci.cbm.MESA_EGL), stdout=emulog, stderr=subprocess.STDOUT)
        deadline = time.monotonic()+30
        while mon is None:
            assert emu.poll() is None, 'VICE exited'
            try: mon = ci.Monitor(port=monport)
            except OSError:
                if time.monotonic()>deadline: raise
                time.sleep(.1)
        banks = mon.banks(); mon.resume()
        paused = PausedViceMonitor(mon)
        @contextmanager
        def stable_batch(label):
            if not label.endswith(('-before','-restore')):
                with paused.paused(label):yield
                return
            deadline=time.monotonic()+30
            while True:
                with paused.paused(label):
                    if bytes(paused.read_mem(0x3d11,0x3d12))==b'\0\1' and bytes(paused.read_mem(0xd0,0xd0))==b'\0':
                        yield
                        return
                assert time.monotonic()<deadline,('idle capture admission',label)
                time.sleep(.01)
        capture = NativeCapture(paused,work,quiet=.02,kernel_prefix='native-desktop',batch=stable_batch)
        result['cpu_captures']=capture.records;result['cpu_capture_batches']=paused.batches
        def read(address, count=1, bank=0):
            data = bytes(mon.read_mem(address,address+count-1,bank=bank)); mon.resume(); return data
        def ready(): return read(0x3d12)==b'\1' and read(0xd0,2)==bytes(2)
        def app_read(address,count=1):return read(address,count,banks['ram00'])
        def position():
            raw=app_read(labels['pm_x'],3)
            return int.from_bytes(raw[:2],'little'),raw[2]
        def move_to(tx,ty):
            deadline=time.monotonic()+90;samples=[]
            while time.monotonic()<deadline:
                x,y=position();samples.append([x,y])
                if abs(x-tx)<=2 and abs(y-ty)<=2:
                    wait(ready,'mouse destination idle',60);time.sleep(.2)
                    if position()==(x,y):
                        result.setdefault('mouse_routes',[]).append(dict(target=[tx,ty],samples=samples));return
                    continue
                mouse.move(max(-12,min(12,(tx-x)*2)),max(-12,min(12,(ty-y)*2)))
            raise AssertionError(('Claude mouse failed to reach target',position(),(tx,ty)))
        def click(index):
            x0,y0,x1,y1=RECTS[index];move_to((x0+x1)//2,(y0+y1)//2)
            before=int.from_bytes(read(0x3d13,2),'little')
            mouse.button(True);wait(lambda:app_read(labels['pm_arm'])==bytes([index]),'Claude button armed',30)
            mouse.button(False)
            wait(lambda:ready() and app_read(labels['pm_buttons'])==b'\0','Claude mouse action',60)
            assert int.from_bytes(read(0x3d13,2),'little')==before
            result.setdefault('mouse_events',[]).append(dict(button=index,keyboard_events=0))
        def right_click():
            wait(ready,'right-button readiness',120)
            before=int.from_bytes(read(0x3d13,2),'little');menu=app_read(labels['cg_menu'])[0]
            mouse.button(True,3)
            wait(lambda:ready() and app_read(labels['cg_menu'])==bytes([menu^1]),'right-button controls toggle',120)
            time.sleep(.2);assert app_read(labels['cg_menu'])==bytes([menu^1])
            mouse.button(False,3)
            wait(lambda:ready() and app_read(labels['pm_secondary_down'])==b'\0','right-button release',120)
            assert app_read(labels['cg_menu'])==bytes([menu^1])
            assert int.from_bytes(read(0x3d13,2),'little')==before,'right button leaked a ROM key'
            result.setdefault('mouse_events',[]).append(dict(button='right',menu=menu^1,keyboard_events=0))
        def rom_key(name,code):
            wait(ready,'ROM key readiness',120);before=int.from_bytes(read(0x3d13,2),'little')
            with mouse.held_key(name):
                wait(lambda:int.from_bytes(read(0x3d13,2),'little')!=before,'ROM consumed '+name,120)
            wait(ready,'ROM key completed',120)
            assert int.from_bytes(read(0x3d13,2),'little')==(before+1)&65535
            assert read(0x3d15)==bytes([code]),(name,'wrong ROM key',read(0x3d15))
            result.setdefault('rom_keys',[]).append(dict(name=name,code=code,before=before,after=(before+1)&65535))
        def frame(label,*,live=0,menu=0,top=0,focus=0,view=0,terminal_chars=None):
            panel=waiting_panel(connected=True) if live else landing_screen(40)
            actual,row=capture_frame(capture,app_read,labels,work,label,panel=panel,live=live,menu=menu,
                                    top=top,focus=focus,view=view,terminal_chars=terminal_chars)
            xy=position()
            error,raw=mon._recv(mon._send(0x84,bytes([1,0])));mon.resume();assert not error
            (work/(label+'-canvas.bin')).write_bytes(raw)
            row.update(position=xy,pointer_visible=bool(app_read(labels['pm_seen'])[0]),
                rectangle=check_canvas(raw,surface_pixels(actual,*xy,visible=bool(app_read(labels['pm_seen'])[0]))))
            result.setdefault('claude_frames',[]).append(row)
            graphics=(live!=1 or menu==1)
            assert app_read(labels['cg_vdc_owned'])==bytes([graphics])
            if graphics:
                def canvas():
                    error,raw=mon._recv(mon._send(0x84,bytes([0,0])));mon.resume();assert not error
                    return raw
                row['vdc']=vdc_capture(capture,app_read,canvas,work,label,0,color=args.vdc64,
                                      surface_data=actual,image_prefix='native-desktop/claude-gui')
            subprocess.run(['magick','import','-display',xv.display,'-window','root',str(work/(label+'.png'))],check=True,capture_output=True)
            print('PASS: Claude bitmap, live font and 64000 VIC pixels:',label,flush=True)
        def key(value):
            wait(ready,'native readiness',120)
            before = int.from_bytes(read(0x3d13,2),'little')
            mon.write_mem(0x3d12,b'\0'); mon.write_mem(0x34a,bytes([value]));mon.write_mem(0xd0,b'\1');mon.resume()
            wait(lambda:ready() and int.from_bytes(read(0x3d13,2),'little')==(before+1)&65535,
                 f'key {value:02x}',180)
            result['events'].append(value)
        def desktop(label, selected):
            wait(lambda:ready() and read(0xc000,9216,banks['ram00'])==surface(selected),label,180)
            (work/(label+'-surface.bin')).write_bytes(read(0xc000,9216,banks['ram00']))
            def vdc_canvas():
                error,raw=mon._recv(mon._send(0x84,bytes([0,0])));mon.resume();assert not error
                return raw
            result.setdefault('desktop_frames',[]).append(vdc_capture(capture,app_read,vdc_canvas,work,label,selected,color=args.vdc64))
            assert read(0x3d2f)==bytes([selected])
        desktop('boot-desktop',0)
        saved_keys=read(0x1000,256);saved_callback=read(0x33c,2);repeat=read(0xa22)
        if args.mouse:
            mon.write_mem(0xa22,b'\x40');mon.resume()
            mouse=Mouse(xv.display,vdc_window=args.eighty);result['private_x_windows']=mouse.windows
            assert len(mouse.windows)==2,'the private display must contain only this C128 pair'
        original_font,original_state = saved_vdc_region(capture,app_read,work,'before-claude-font')
        result['original_vdc_snapshot']=original_state
        (work/'font-before.bin').write_bytes(original_font)
        original_nmi = read(0x318,2); original_gate = read(0x3d3e,2)
        (work/'nmi-before.bin').write_bytes(original_nmi+original_gate)
        key(ord('A'))
        assert read(0x400,1000,banks['ram00'])==landing_screen(40)
        assert app_read(labels['cg_vdc_owned'])==b'\1'
        print('PASS: packaged app launch page',flush=True)
        if args.mouse:
            resource=b'Mouse'
            error,_=mon._recv(mon._send(0x52,bytes([1,len(resource)])+resource+bytes([4])+bytes([1,0,0,0])))
            mon.resume();assert not error
            result['mouse_enabled_after_claude_launch']=True
            wait(lambda:app_read(labels['pm_seen'])==b'\1','Claude mouse attached',20)
            move_to(160,100)
        frame('claude-landing',terminal_chars=landing_screen(80))
        if args.mouse:click(0)
        else:key(13)
        def row_text(row, text):
            expected = bytes(petscii.to_screen_code(c) for c in text)
            return read(row*80,len(expected),banks['vdc'])==expected
        wait(lambda:row_text(0,'KESTREL CLAUDE LINK READY'),'bridge rendered PTY output',90)
        wait(lambda:row_text(2,'Keyboard, glyphs and return test'),'complete initial frame',60)
        assert read(0x318,2)==b'\xf0\x1b'
        assert read(0x3d3e,2)==labels['nmiHandler'].to_bytes(2,'little')
        code = font.CODES['❯']
        expected_glyph = bytes(font.BITMAPS[code])+bytes(8)
        assert read(0x3000+16*code,16,banks['vdc'])==expected_glyph
        key(ord('P')); wait(lambda:row_text(3,'KEY RECEIVED: p'),'PTY keyboard delivery',60)
        key(27); wait(lambda:row_text(4,'ESCAPE RECEIVED'),'Escape delivered to PTY',60)
        previous_rx=int.from_bytes(read(labels['_rxCount'],2),'little')
        key(0x84)
        wait(lambda:int.from_bytes(read(labels['_rxCount'],2),'little')>previous_rx and
             read(labels['_framesSeen'])!=b'\0','HELP received a new frame',60)
        expected=bytearray(b' '*2000)
        for row,text in enumerate(['KESTREL CLAUDE LINK READY','❯ ✳ ⏺','Keyboard, glyphs and return test',
                                   'KEY RECEIVED: p','ESCAPE RECEIVED']):
            codes=bytes(petscii.to_screen_code(c) for c in text)
            expected[row*80:row*80+len(codes)]=codes
        wait(lambda:read(0,2000,banks['vdc'])==expected,'complete terminal repaint',60)

        if not args.host_exit or args.mouse:
            if args.mouse:move_to(160,100)
            frame('claude-connected',live=1,focus=1)
        if args.mouse:
            with mouse.held_key('Control_L'):
                time.sleep(.1)
                rom_key('End',255)
            assert app_read(labels['cg_menu'])==b'\1'
            frame('claude-controls',live=1,menu=1,focus=1,terminal_chars=expected)
            rom_key('F10',9);rom_key('F10',9);rom_key('Return',13)
            frame('claude-bottom-panel',live=1,menu=1,top=9,focus=3)
            rom_key('F9',27);assert app_read(labels['cg_menu'])==b'\0'
            click(3);frame('claude-top-panel',live=1,focus=4)
            before_rx=int.from_bytes(app_read(labels['_rxCount'],2),'little')
            click(1)
            wait(lambda:int.from_bytes(app_read(labels['_rxCount'],2),'little')!=before_rx and
                 read(0,2000,banks['vdc'])==expected,'mouse Repaint completed',90)
            frame('claude-mouse-repaint',live=1,focus=1)
            right_click()
            frame('claude-right-button-controls',live=1,menu=1,focus=1,terminal_chars=expected)
            click(5);frame('claude-left-terminal',live=1,menu=1,focus=5,view=1,terminal_chars=expected)
            expected[1997:]=bytes(petscii.to_screen_code(char) for char in 'X❯Y')
            token=app_read(labels['tm_cells'],4);record=app_read(0x3c00+(token[0]-1)*8,8)
            assert record[:2]==b'\x20\1' and record[4:7]==token[1:]
            fixture_control.write_text('update\n')
            wait(lambda:read(record[2]*256+1997,3,banks['ram01'])==expected[1997:] and ready(),
                 'PTY output retained while graphical controls cover the VDC',120)
            click(4);click(5)
            frame('claude-right-terminal-bottom',live=1,menu=1,top=9,focus=5,view=2,terminal_chars=expected)
            click(6)
            assert read(0,2000,banks['vdc'])==expected
            frame('claude-full-terminal-return',live=1,top=9,focus=6,view=2,terminal_chars=expected)
            right_click();right_click()
            assert read(0,2000,banks['vdc'])==expected

        if args.cpu_capture:
            # The fixture is now stationary and --no-panel emits no timer
            # updates. This observer borrows the VDC address/selected register;
            # it is not admitted as a concurrent drawing observer.
            time.sleep(.5)
            assert capture.capture('cpu-session-vdc', mode=1, count=2000) == expected
            assert capture.capture('cpu-session-vic', address=0x400, count=1000) == read(0x400,1000,banks['ram00'])
            assert capture.capture('cpu-session-nmi', address=0x318, count=2) == b'\xf0\x1b'
            assert capture.capture('cpu-session-gate', address=0x3d3e, count=2) == labels['nmiHandler'].to_bytes(2,'little')
            assert all(row['restored'] for row in capture.records)
            print('PASS: settled terminal CPU capture with serial NMI handler installed', flush=True)

        for name, address, count, bank in [('session-vdc',0,2000,banks['vdc']),
                ('session-attrs',0x800,2000,banks['vdc']),('session-vic',0x400,1000,banks['ram00']),
                ('font-during',0x3000,4096,banks['vdc'])]:
            (work/(name+'.bin')).write_bytes(read(address,count,bank))
        counters = {name:int.from_bytes(read(labels[name],size),'little') for name,size in
                    (('_rxCount',2),('_nmiCount',2),('_rxDropped',1),('_rxOverruns',1),('_kbCount',2))}
        result['serial_counters'] = counters
        assert counters['_rxCount']>=3+10*len(list(font.definitions()))
        assert counters['_nmiCount']>=counters['_rxCount']
        assert counters['_rxDropped']==counters['_rxOverruns']==0
        print('PASS: TCP/PTY output, custom glyph, input, Escape, HELP and NMI receive',flush=True)
        # Observe the outcome while Claude still owns its image. A growing
        # desktop may overwrite any freed terminal BSS on its next load.
        entry=labels['_native_video_end']
        error,checkpoint=mon._recv(mon._send(0x12,entry.to_bytes(2,'little')*2+bytes([1,1,4,0,0])))
        assert not error
        checkpoint_id=checkpoint[:4];mon.resume()
        wait(ready,'native ready before closing checkpoint',120)
        before=int.from_bytes(read(0x3d13,2),'little')
        closing_key=ord('Q') if args.host_exit else 0x8c
        mouse_close=args.mouse and not args.host_exit
        if mouse_close:
            x0,y0,x1,y1=RECTS[2];move_to((x0+x1)//2,(y0+y1)//2)
            mouse.button(True);wait(lambda:app_read(labels['pm_arm'])==b'\2','Desktop armed',30)
            mouse.button(False)
        else:
            mon.write_mem(0x3d12,b'\0');mon.write_mem(0x34a,bytes([closing_key]));mon.write_mem(0xd0,b'\1');mon.resume()
        deadline=time.monotonic()+90
        while True:
            error,checkpoint=mon._recv(mon._send(0x11,checkpoint_id));assert not error
            if int.from_bytes(checkpoint[13:17],'little'):break
            mon.resume();assert time.monotonic()<deadline,'native cleanup checkpoint not reached'
            time.sleep(.1)
        outcome=bytes(mon.read_mem(labels['_closeOutcome'],labels['_closeOutcome'],bank=banks['ram00']))
        (work/'close-outcome.bin').write_bytes(outcome)
        (work/'close-checkpoint.bin').write_bytes(checkpoint)
        result['close_outcome']=outcome[0]
        result['close_observation']=dict(address=labels['_closeOutcome'],cleanup_entry=entry,
            checkpoint_hex=checkpoint.hex(),lifetime='Claude allocation still live; before native_video_end')
        assert outcome==bytes([0 if args.host_exit else 2]),'client missed the shutdown acknowledgement'
        assert bytes(mon.read_mem(0x3d20,0x3d20))==b'\x20'
        assert int.from_bytes(bytes(mon.read_mem(0x3d13,0x3d14)),'little')==(before+(not mouse_close))&65535
        error,_=mon._recv(mon._send(0x13,checkpoint_id));assert not error
        mon.resume()
        if mouse_close:result.setdefault('mouse_events',[]).append(dict(button=2,keyboard_events=0))
        else:result['events'].append(closing_key)
        desktop('returned-desktop',4)
        assert read(0x1000,256)==saved_keys and read(0x33c,2)==saved_callback
        mon.write_mem(0xa22,repeat);mon.resume();assert read(0xa22)==repeat
        after_font,restored_state = saved_vdc_region(capture,app_read,work,'after-claude-font')
        result['restored_vdc_snapshot']=restored_state
        (work/'font-after.bin').write_bytes(after_font)
        assert after_font==original_font
        after_nmi = read(0x318,2)+read(0x3d3e,2)
        (work/'nmi-after.bin').write_bytes(after_nmi)
        assert after_nmi==original_nmi+original_gate
        assert bridge.wait(timeout=25)==0, 'host session did not close cleanly'
        result['host_exit_code'] = bridge.returncode
        key(27)
        assert read(0x400,1000,banks['ram00'])==expected_screen(40,0)
        assert read(0,2000,banks['vdc'])==expected_screen(80,0)
        heap = read(0x3800,512,banks['ram00']); (work/'final-heap.bin').write_bytes(heap)
        assert heap[0x50:0xff]==bytes(175) and heap[0x104:0x1ff]==bytes(251)
        assert hashlib.sha256(disk.read_bytes()).hexdigest()==hashes['kestrel.d64']
        result['passed'] = True
        print('PASS: original font/NMI restored, desktop selection retained, host reaped and all 426 pages free',flush=True)
    except BaseException as exc:
        result['error'] = repr(exc)
        if mon:
            try:
                result['failure_state']={hex(at):app_read(at,count).hex() for at,count in
                    ((0x3d11,24),(0x3d60,32),(0xd0,10),(0x33c,2))}
                for name,address,count,bank in (('surface',0xc000,9216,banks['ram00']),
                        ('panel',0x400,1000,banks['ram00']),('vdc',0,2000,banks['vdc'])):
                    (work/('failure-'+name+'.bin')).write_bytes(read(address,count,bank))
                subprocess.run(['magick','import','-display',xv.display,'-window','root',str(work/'failure.png')],check=True,capture_output=True)
            except BaseException as diagnostic:result['diagnostic_error']=repr(diagnostic)
        raise
    finally:
        if mouse:
            mouse.button(False);mouse.button(False,3);mouse.close()
        if mon:
            try: mon.quit_emulator()
            except (OSError,EOFError): pass
            mon.close()
        for proc in (emu,bridge):
            if proc:
                try: proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.terminate()
                    try: proc.wait(timeout=25)
                    except subprocess.TimeoutExpired: proc.kill();proc.wait()
        xv.stop();emulog.close();hostlog.close()
        (work/'report.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__ == '__main__': main()
