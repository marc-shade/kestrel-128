#!/usr/bin/env python3
"""Cold boot all six shipped disks and check usable workspace/desktop frames."""
import argparse
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

import vice_harness as ci
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from launcher_scene import surface
from native_capture_transport import PausedViceMonitor
from native_pointer_check import check_canvas, surface_pixels
from native_vdc_scene import pixels as vdc_pixels


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix='kestrel-boot-vice-'))
    report = dict(passed=False, physical_hardware_io=False, work=str(work), cases=[])
    print('Boot VICE evidence:', work, flush=True)
    try:
        for prefix, stem in (('native','kestrel'),('native-desktop','kestrel'),
                             ('native-desktop','workspace')):
            for fmt in ('d64','d81'):
                name = prefix+'-'+stem+'-'+fmt
                folder = work/name
                folder.mkdir()
                source = ROOT/'target'/prefix/(stem+'.'+fmt)
                disk = folder/('boot.'+fmt)
                shutil.copyfile(source,disk)
                case = dict(name=name, passed=False, frames=[], keys=[],
                            disk_sha256=hashlib.sha256(disk.read_bytes()).hexdigest())
                report['cases'].append(case)
                with socket.socket() as sock:
                    sock.bind(('127.0.0.1',0))
                    port = sock.getsockname()[1]
                color = fmt == 'd81'
                kernel = ROOT/'target'/('native' if stem == 'workspace' else prefix)
                if color: kernel /= 'd81'
                symbols = {n:int(v,16) for n,v in re.findall(r'^(\w+)\s*=\s*\$([\da-fA-F]+)',
                           (kernel/'kestrel.sym').read_text(),re.M)}
                command = ['x128','-default','-80col' if color else '-40col',
                           '-8',str(disk),'-drive8true','-drive8type','1581' if color else '1541',
                           '-VDC64KB' if color else '-VDC16KB','-sounddev','dummy',
                           '-jamaction','0','-warp','-binarymonitor',
                           '-binarymonitoraddress',f'ip4://127.0.0.1:{port}']
                case['command'] = command
                xv = ci.cbm.Xvfb()
                log = (folder/'vice.log').open('w')
                mon = None
                emu = subprocess.Popen(command,env=dict(os.environ,DISPLAY=xv.display,
                                       __EGL_VENDOR_LIBRARY_FILENAMES=ci.cbm.MESA_EGL),
                                       stdout=log,stderr=subprocess.STDOUT)
                try:
                    deadline = time.monotonic()+30
                    while mon is None:
                        assert emu.poll() is None
                        try: mon = ci.Monitor(port=port)
                        except OSError:
                            assert time.monotonic() < deadline
                            time.sleep(.1)
                    banks = mon.banks()
                    mon.resume()
                    paused = PausedViceMonitor(mon)
                    def read(at,n=1):
                        data = bytes(paused.read_mem(at,at+n-1,bank=banks['ram00']))
                        paused.resume()
                        return data
                    def wait(predicate,label):
                        deadline = time.monotonic()+120
                        while time.monotonic() < deadline:
                            if predicate(): return
                            assert emu.poll() is None
                            time.sleep(.03)
                        raise AssertionError(label)
                    def ready(): return read(0x3d12)==b'\1' and read(0xd0,2)==bytes(2)
                    def key(value):
                        wait(ready,'input ready')
                        before = int.from_bytes(read(0x3d13,2),'little')
                        with paused.paused('keyboard'):
                            paused.write_mem(0x3d12,b'\0')
                            paused.write_mem(0x34a,bytes([value]))
                            paused.write_mem(0xd0,b'\1')
                        wait(lambda: ready() and int.from_bytes(read(0x3d13,2),'little') ==
                             (before+1)&65535,'key completed')
                        case['keys'].append(value)
                    def workspace(label):
                        assert read(0x3d20)==b'\0' and read(0x3d0e,3)==bytes([175,251,32])
                        (folder/(label+'-workspace.bin')).write_bytes(read(0x400,1000))
                        key(ord('2'))
                        assert read(symbols['ui_bank'])==b'\1'
                    def desktop(label,selected):
                        assert read(0x3d20)==b'\x20' and read(0x3d2f)==bytes([selected])
                        raw = read(0xc000,9216)
                        assert raw == surface(selected), ('VIC surface',name,label)
                        (folder/(label+'-surface.bin')).write_bytes(raw)
                        time.sleep(.15)
                        rows = surface_pixels(raw,0,0,visible=False)
                        pixels = vdc_pixels(selected,color=color,visible=False)
                        vdc_rows = [pixels[at:at+640] for at in range(0,128000,640)]
                        frames = []
                        for chip, expected in ((1,rows),(0,vdc_rows)):
                            error, canvas = mon._recv(mon._send(0x84,bytes([chip,0])))
                            mon.resume()
                            assert not error
                            rectangle = check_canvas(canvas,expected)
                            filename = label+('-vic.bin' if chip else '-vdc.bin')
                            (folder/filename).write_bytes(canvas)
                            frames.append(dict(file=filename,rectangle=rectangle,
                                               sha256=hashlib.sha256(canvas).hexdigest()))
                        case['frames'].append(dict(label=label,selected=selected,canvases=frames))
                    wait(lambda: read(0x1c13,6)==b'KES128' and ready(),'cold boot')
                    assert read(0x3de4)==bytes([2 if color else 0])
                    if prefix == 'native':
                        workspace('cold')
                    else:
                        if stem == 'workspace':
                            workspace('cold')
                            key(ord('B'))
                        desktop('cold',0)
                        key(0x11)
                        desktop('selected',1)
                        key(27)
                        workspace('returned')
                        key(ord('B'))
                        desktop('reopened',1)
                    assert disk.read_bytes() == source.read_bytes()
                    case['passed'] = True
                    print('PASS: cold boot and input:',name,flush=True)
                finally:
                    args.report.write_text(json.dumps(report,indent=2)+'\n')
                    if mon: mon.quit_emulator()
                    else: emu.terminate()
                    emu.wait(timeout=15)
                    xv.stop()
                    log.close()
        report['passed'] = True
    finally:
        args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__ == '__main__': main()
