#!/usr/bin/env python3
"""Qualify the native key boundary with actual VICE keyboard/joystick input."""
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'tests')]
import vice_harness as ci
from native_capture import NativeCapture, wait
from native_capture_transport import PausedViceMonitor
from native_running_layout import verify_running_layout, RunningLayout
from launcher_scene import surface, console
from vice_keyboard import Keyboard
from hwlib import lst_symbol
from native_vdc_check import capture_frame as vdc_capture


def main():
    work = Path(tempfile.mkdtemp(prefix='kestrel-native-keyboard-iec-'))
    print('Native keyboard VICE:', work, flush=True)
    report = dict(passed=False, physical_hardware_io=False, events=[],
        kernel_sha256=hashlib.sha256((ROOT/'target/native-desktop/kestrel.prg').read_bytes()).hexdigest())
    def save(): (work/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
    xv = ci.cbm.Xvfb()
    emu = mon = keyboard = None
    log = (work/'vice.log').open('w')
    try:
        command = ['x128','-default','-40col','-8',str(ROOT/'target/native-desktop/kestrel.d64'),
            '-drive8true','-drive8type','1541','-VDC16KB','-sounddev','dummy','-jamaction','0','-warp',
            '-controlport1device','1','-joydev1','2','-joydev2','0','-keyset',
            '-binarymonitor','-binarymonitoraddress',f'ip4://127.0.0.1:{port}']
        report['emulator_command'] = command; save()
        emu = subprocess.Popen(command, env=dict(os.environ, DISPLAY=xv.display,
            __EGL_VENDOR_LIBRARY_FILENAMES=ci.cbm.MESA_EGL), stdout=log, stderr=subprocess.STDOUT)
        deadline = time.monotonic()+30
        while mon is None:
            assert emu.poll() is None
            try: mon = ci.Monitor(port=port)
            except OSError:
                if time.monotonic() > deadline: raise
                time.sleep(.1)
        mon.resume()
        name = b'KeySet1South'
        error, _ = mon._recv(mon._send(0x52, bytes([1, len(name)])+name+bytes([4])+(106).to_bytes(4,'little')))
        assert error == 0, ('set emulator joystick key', error)
        mon.resume()
        report['joystick_fixture'] = dict(port=1, device='Joystick', source='Keyset 1', south_keysym=106, host_key='j')
        paused = PausedViceMonitor(mon)
        def read(address, count=1):
            data = bytes(paused.read_mem(address, address+count-1)); paused.resume(); return data
        wait(lambda:read(0x1c13,6) == b'KES128' and read(0x3d12) == b'\1', 'native keyboard boot', 90)
        layout = RunningLayout(ROOT, image_dir=ROOT/'target/native-desktop')
        guard = layout.syms['native_keycheck'].to_bytes(2, 'little')
        # Since f5d9b9a the desktop is a pointer client: its shared filter at
        # pk_entry ($1014) owns KEYCHK and chains the resident guard, which
        # retains the ROM callback (docs/NATIVE-KEYBOARD.md, Pointer clients).
        pointer = lst_symbol('native-desktop/desktop','pk_entry').to_bytes(2, 'little')
        assert read(0x33c,2) == pointer and read(0x3d1c,2) == b'\xad\xc6'
        assert read(lst_symbol('native-desktop/desktop','pk_next'),2) == guard
        assert read(0x3d1e,2) == bytes(2)
        repeat = read(0xa22)
        # Isolate single X presses from VICE's accelerated clock; restored below.
        with paused.paused('keyboard-fixture-repeat'): paused.write_mem(0xa22,b'\x40')
        report['repeat_before_hex'] = repeat.hex()
        keyboard = Keyboard(xv.display)
        report['private_x_windows'] = keyboard.windows
        def event(name, selected, *, reject=False):
            before = int.from_bytes(read(0x3d13,2),'little')
            rejected = int.from_bytes(read(0x3d1e,2),'little')
            keyboard.press(name)
            report['pending_event'] = dict(key=name, keys_before=before,
                keys_after=int.from_bytes(read(0x3d13,2),'little'),
                rejects_before=rejected,rejects_after=int.from_bytes(read(0x3d1e,2),'little'),
                last_key=read(0x3d15)[0], scan_index=read(0xd4)[0])
            save()
            if reject:
                wait(lambda:int.from_bytes(read(0x3d1e,2),'little') > rejected, 'joystick row rejected', 10)
                assert int.from_bytes(read(0x3d13,2),'little') == before
            else:
                wait(lambda:int.from_bytes(read(0x3d13,2),'little') == before+1, 'real keyboard consumed', 10)
            wait(lambda:read(0x3d12) == b'\1' and read(0x3d2f) == bytes([selected]), 'desktop selection settled', 10)
            row = dict(key=name, selected=selected, keys_before=before,
                keys_after=int.from_bytes(read(0x3d13,2),'little'),
                rejects_before=rejected, rejects_after=int.from_bytes(read(0x3d1e,2),'little'),
                last_key=read(0x3d15)[0], guard_enabled=read(0x33c,2) == pointer)
            report['events'].append(row); save()
            return row
        assert event('Down',1)['last_key'] == 17
        assert event('Up',0)['last_key'] == 145
        event('j',0,reject=True)
        print('PASS: real cursors navigate; emulated port-1 Down increments rejection count without consuming a key', flush=True)

        # Negative control on this disposable emulator: the original callback
        # receives the same joystick signal and publishes Insert.
        with paused.paused('keyboard-original-callback'): paused.write_mem(0x33c,b'\xad\xc6')
        row = event('j',0)
        assert row['last_key'] == 148 and row['rejects_before'] == row['rejects_after']
        with paused.paused('keyboard-guard-restore'): paused.write_mem(0x33c,pointer)
        assert read(0x33c,2) == pointer
        event('j',0,reject=True)
        assert event('Down',1)['last_key'] == 17
        with paused.paused('keyboard-repeat-restore'): paused.write_mem(0xa22,repeat)
        assert read(0xa22) == repeat
        print('PASS: original callback produces Insert; reinstalling guard blocks it and retains normal keyboard navigation', flush=True)
        capture = NativeCapture(paused,work,quiet=.05,kernel_prefix='native-desktop',batch=paused.paused)
        report['captures'] = capture.records; report['paused_capture_batches'] = paused.batches
        report['resident'] = verify_running_layout(capture,ROOT,'keyboard-resident',image_dir=ROOT/'target/native-desktop')
        frame = b''.join(capture.capture(f'keyboard-surface-{i:04x}',bank=0,address=0xc000+i,count=min(2000,9216-i)) for i in range(0,9216,2000))
        assert frame == surface(1); (work/'keyboard-surface.bin').write_bytes(frame)
        # Since 5d04173 the desktop's VDC is its bitmap scene, not 80-column text.
        def canvas():
            error,raw = mon._recv(mon._send(0x84,bytes([0,0]))); mon.resume(); assert not error
            return raw
        report['vdc'] = vdc_capture(capture,read,canvas,work,'keyboard-vdc',1,color=False)
        report['passed'] = True
        print('PASS: complete resident bytes and both desktop displays after keyboard/joystick controls', flush=True)
    except BaseException as error:
        report['error'] = repr(error); raise
    finally:
        if keyboard is not None: keyboard.close()
        if mon is not None:
            try: mon.quit_emulator()
            except (OSError,EOFError): pass
            mon.close()
        if emu is not None:
            try: emu.wait(timeout=2)
            except subprocess.TimeoutExpired:
                emu.terminate(); emu.wait(timeout=5)
        xv.stop(); log.close(); save()


if __name__ == '__main__': main()
