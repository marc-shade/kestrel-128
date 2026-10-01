#!/usr/bin/env python3
"""Exercise the complete physical suite workflow through VICE and CPU capture."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT),str(ROOT/'tests')]
import vice_harness as ci
from native_capture import NativeCapture, wait
from native_capture_transport import PausedViceMonitor
from native_suite_workflow import run_suite_workflow, absent_reference, close_bridges


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0))
        return sock.getsockname()[1]


class ViceBridge:
    def __init__(self, port):
        self.port = port
        self.prepared = {}
        self.processes = []

    def prepare(self, label, work, row):
        if label not in self.prepared:
            path = work/(label+'-bridge.log')
            log = path.open('w')
            command = [sys.executable,'-B',str(ROOT/'apps/claude/run.py'),'--listen',str(self.port),
                '--command',shlex.join([sys.executable,'-B',str(ROOT/'tests/fixtures/claude-session.py')]),
                '--no-panel','-v']
            proc = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
            self.processes.append((proc,log))
            self.prepared[label] = (proc,log,command)
            wait(lambda:'listening on' in path.read_text(), 'VICE serial bridge listening', 15)
        row['bridge_command'] = self.prepared[label][2]

    def __call__(self, label, work, row):
        return self.prepared[label][:2]

    def close_session(self,mon,work,row,labels,closing_key,report):
        """Stop before video cleanup and observe still-owned terminal BSS."""
        monitor=mon.monitor
        entry=labels['_native_video_end'];at=labels['_closeOutcome']
        error,checkpoint=monitor._recv(monitor._send(0x12,entry.to_bytes(2,'little')*2+bytes([1,1,4,0,0])))
        assert not error
        checkpoint_id=checkpoint[:4];monitor.resume();started=time.monotonic()
        def read(address,count=1):
            data=bytes(monitor.read_mem(address,address+count-1));monitor.resume();return data
        wait(lambda:read(0x3d12)==b'\1' and read(0xd0,2)==bytes(2),'ready before Claude close',120)
        before=int.from_bytes(read(0x3d13,2),'little')
        try:
            monitor.write_mem(0x3d12,b'\0');monitor.write_mem(0x34a,bytes([closing_key]));monitor.write_mem(0xd0,b'\1');monitor.resume()
            deadline=time.monotonic()+90
            while True:
                error,checkpoint=monitor._recv(monitor._send(0x11,checkpoint_id));assert not error
                if int.from_bytes(checkpoint[13:17],'little'):break
                monitor.resume();assert time.monotonic()<deadline,'Claude close checkpoint not reached'
                time.sleep(.1)
            outcome=bytes(monitor.read_mem(at,at,bank=monitor.banks()['ram00']))
            label=row['label'];(work/(label+'-close-outcome.bin')).write_bytes(outcome)
            (work/(label+'-close-checkpoint.bin')).write_bytes(checkpoint)
            assert bytes(monitor.read_mem(0x3d20,0x3d20))==b'\x20'
            assert int.from_bytes(bytes(monitor.read_mem(0x3d13,0x3d14)),'little')==(before+1)&65535
            row['close_observation']=dict(address=at,cleanup_entry=entry,checkpoint_hex=checkpoint.hex(),
                lifetime='Claude allocation still live; before native_video_end')
            report['events'].append(dict(key=closing_key,elapsed_seconds=round(time.monotonic()-started,3),live_close_checkpoint=True))
            return outcome
        finally:
            error,_=monitor._recv(monitor._send(0x13,checkpoint_id));assert not error
            monitor.resume()


def main():
    work = Path(tempfile.mkdtemp(prefix='kestrel-native-suite-iec-'))
    print('Native suite CPU workflow:',work,flush=True)
    shutil.copy2(__file__,work/'run.py')
    disk = work/'suite.d64'
    shutil.copyfile(ROOT/'target/native-desktop/kestrel.d64',disk)
    report = dict(passed=False,physical_hardware_io=False,events=[],desktops=[],screens=[],
        suite_reference=absent_reference(),images={path.name:hashlib.sha256(path.read_bytes()).hexdigest()
             for path in (ROOT/'target/native-desktop').iterdir() if path.suffix in ('.prg','.d64')})
    def save(): (work/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    save()
    linkport, monport = free_port(), free_port()
    factory = ViceBridge(linkport)
    xv = None; mon = emu = None
    log = (work/'vice.log').open('w')
    try:
        factory.prepare('claude-f8',work,{})
        xv = ci.cbm.Xvfb()
        command = ['x128','-default','-40col','-8',str(disk),'-drive8true','-drive8type','1541',
            '-VDC16KB','-sounddev','dummy','-jamaction','0','-warp',
            '-acia1','-acia1base','0xDE00','-acia1irq','1','-acia1mode','1','-myaciadev','0',
            '-rsdev1',f'127.0.0.1:{linkport}','-rsdev1baud','38400',
            '-binarymonitor','-binarymonitoraddress',f'ip4://127.0.0.1:{monport}']
        report['emulator_command'] = command; save()
        emu = subprocess.Popen(command,env=dict(os.environ,DISPLAY=xv.display,
            __EGL_VENDOR_LIBRARY_FILENAMES=ci.cbm.MESA_EGL),stdout=log,stderr=subprocess.STDOUT)
        deadline = time.monotonic()+30
        while mon is None:
            assert emu.poll() is None, 'VICE exited during startup'
            try: mon = ci.Monitor(port=monport)
            except OSError:
                if time.monotonic() >= deadline: raise
                time.sleep(.1)
        mon.resume()
        paused = PausedViceMonitor(mon)
        @contextmanager
        def stable_batch(label):
            # Pointer clients (desktop, Editor, Files, Ultimate, Claude) clear
            # N_READY during each pointer sample; admit a capture at an idle
            # instant, as ci_native_editor_gui_iec does. Readbacks never retry.
            if not label.endswith(('-before','-restore')):
                with paused.paused(label): yield
                return
            deadline = time.monotonic()+30
            while True:
                with paused.paused(label):
                    if bytes(paused.read_mem(0x3d11,0x3d12)) == b'\0\1' and bytes(paused.read_mem(0xd0,0xd0)) == b'\0':
                        yield
                        return
                assert time.monotonic() < deadline, ('idle capture admission', label)
                time.sleep(.01)
        capture = NativeCapture(paused,work,quiet=.05,kernel_prefix='native-desktop',batch=stable_batch)
        report['captures'] = capture.records
        report['paused_capture_batches'] = paused.batches
        run_suite_workflow(paused,capture,work,disk,report,save,bridge_factory=factory,key_quiet=.1,key_poll=.1)
        assert hashlib.sha256(disk.read_bytes()).hexdigest() == report['images']['kestrel.d64']
        report['passed'] = True
        print('PASS: full shared suite workflow, two serial lifetimes, resident preservation and 426 free pages',flush=True)
    except BaseException as error:
        report['error'] = dict(type=type(error).__name__,message=str(error))
        raise
    finally:
        if mon is not None:
            try: mon.quit_emulator()
            except (OSError,EOFError): pass
            mon.close()
        if emu is not None:
            try: emu.wait(timeout=2)
            except subprocess.TimeoutExpired:
                emu.terminate()
                try: emu.wait(timeout=5)
                except subprocess.TimeoutExpired: emu.kill(); emu.wait()
        close_bridges(factory)
        if xv is not None: xv.stop()
        log.close()
        report['all_host_processes_terminal'] = all(proc.poll() is not None for proc,_ in factory.processes)
        save()


if __name__ == '__main__': main()
