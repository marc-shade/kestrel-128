#!/usr/bin/env python3
"""Boot the native C128 disk and exercise its memory workspace in x128."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time

import vice_harness as ci

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from native_capture import NativeCapture, expected_screen, calculator_screen, verify_boot_layout
from hwlib import lst_symbol
READY, KEYS, RESULT = 0x3d12, 0x3d13, 0x3d16


def main():
    work = Path(tempfile.mkdtemp(prefix='kestrel-native-x128-'))
    print(f'Native emulator evidence: {work}',flush=True)
    stock = ROOT/'target/native/kestrel.d64'
    disk = work/'native.d64'; shutil.copy2(stock,disk)
    report = dict(disk_sha256=hashlib.sha256(stock.read_bytes()).hexdigest(),passed=False)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    xv = ci.cbm.Xvfb()
    log = (work/'vice.log').open('w')
    process = subprocess.Popen(['x128','-default','-8',str(disk),'-drive8true',
                                '-drive8type','1541','-sounddev','dummy','-jamaction','0',
                                '-warp','-binarymonitor','-binarymonitoraddress',f'ip4://127.0.0.1:{port}'],
                               env=dict(os.environ,DISPLAY=xv.display,__EGL_VENDOR_LIBRARY_FILENAMES=ci.cbm.MESA_EGL),
                               stdout=log,stderr=subprocess.STDOUT)
    mon=None
    try:
        deadline=time.monotonic()+30
        while mon is None:
            assert process.poll() is None,'x128 exited'
            try:mon=ci.Monitor(port=port)
            except OSError:
                if time.monotonic()>deadline:raise
                time.sleep(.1)
        banks=mon.banks();mon.resume();report['monitor_banks']=banks

        def read(address,count=1,bank=0):
            data=bytes(mon.read_mem(address,address+count-1,bank=bank));mon.resume();return data

        def wait(predicate,label,seconds=30):
            deadline=time.monotonic()+seconds
            while time.monotonic()<deadline:
                if predicate():return
                time.sleep(.1)
            raise AssertionError(label)

        wait(lambda:read(0x1c13,6)==b'KES128' and read(READY)==b'\1','native boot marker',60)
        report['mmu']=read(0xd500,12).hex()
        report['mailbox']=read(0x3d00,32).hex()
        report['kernal_gateways']=read(0x2a2,0x5a).hex()
        for name in ('ram00','ram01'):
            (work/(name+'-vectors.bin')).write_bytes(read(0xff00,256,bank=banks[name]))
        (work/'vic-initial.bin').write_bytes(read(0x400,1000))
        assert read(0x3d0e,3)==bytes([175,251,32]),report
        assert not read(0xd505)[0]&0x40,'entered C64 mode'
        capture=NativeCapture(mon,work,quiet=.2)
        report['captures']=capture.records
        report['resident_boot']=verify_boot_layout(capture)

        def key(value):
            wait(lambda:read(READY)==b'\1' and read(0xd0)==b'\0','input ready')
            previous=int.from_bytes(read(KEYS,2),'little')
            mon.write_mem(READY,b'\0')
            mon.write_mem(0x34a,bytes([value]));mon.write_mem(0xd0,b'\1');mon.resume()
            wait(lambda:int.from_bytes(read(KEYS,2),'little')==previous+1 and read(READY)==b'\1',f'key {value:02x}',60)
            assert read(RESULT)==b'\0',read(0x3d00,32).hex()

        allocations=[]
        def check_blocks():
            for bank,page in allocations:
                expected=bytes((i&255)^(i>>8)^(0xa5 if bank else 0) for i in range(8192))
                actual=read(page*256,8192,bank=banks[f'ram0{bank}'])
                assert actual==expected,f'bank {bank} independent byte comparison'
                (work/f'bank-{bank}-data.bin').write_bytes(actual)

        for bank,keycode in ((0,ord('1')),(1,ord('2'))):
            key(keycode);key(ord('A'))
            allocations.append((bank,read(0x3d03)[0]))
            key(ord('W'));key(ord('V'));check_blocks()
            pages=read(0x3d0e,2)
            assert pages[bank]==(175 if bank==0 else 251)-32
            print(f'PASS: native bank {bank} allocation, 8192-byte write and verify',flush=True)
        # Both live blocks must retain their distinct contents across switches.
        key(ord('1'));key(ord('V'));check_blocks();key(ord('F'))
        key(ord('2'));key(ord('V'));key(ord('F'))
        assert read(0x3d0e,3)==bytes([175,251,32])
        vic=read(0x400,1000);vdc=read(0,2000,bank=banks['vdc'])
        (work/'vic-final.bin').write_bytes(vic);(work/'vdc-final.bin').write_bytes(vdc)
        assert vic==expected_screen(40,1) and vdc==expected_screen(80,1),'complete native screens differ'
        for bank,page in allocations:
            # Released bytes remain observable until the next allocation. Use
            # the independent capture path that will run on physical hardware.
            actual=capture.capture(f'probe-bank-{bank}',bank=bank,address=page*256,count=2000)
            assert actual==read(page*256,2000,bank=banks[f'ram0{bank}'])
        observed=capture.capture('probe-vdc',mode=1)
        assert observed==vdc,'native IRQ VDC capture differs from monitor memory'
        key(ord('1'));key(ord('2'))  # foreground still consumes keys after captures
        key(ord('C'))
        assert read(0x3d20)==bytes([32]) and read(0x3d23)==b'\2',read(0x3d20,8).hex()
        display=lst_symbol('native/calc','dispbuf')
        for value in b'12+30=':key(value)
        assert read(display,8).split(b'\0')[0]==b'42'
        assert read(0x3800,256).count(0)==159 and read(0x3900,256).count(0)==249
        assert sum(read(0x3c00,256)[i]==32 for i in range(0,256,8))==2
        (work/'calculator-vic.bin').write_bytes(read(0x400,1000))
        (work/'calculator-vdc.bin').write_bytes(read(0,2000,bank=banks['vdc']))
        assert read(0x400,1000)==calculator_screen(40,'42',['42'])
        assert read(0,2000,bank=banks['vdc'])==calculator_screen(80,'42',['42'])
        for value in b'SHISTORY':key(value)
        assert read(0x400,1000)==calculator_screen(40,'42',['42'],save_prompt='HISTORY')
        key(13)
        assert read(lst_symbol('native/calc','save_status'))==b'\1',read(0x3d80,32).hex()
        for cols,bank,label in ((40,0,'vic'),(80,banks['vdc'],'vdc')):
            screen=read(0x400 if cols==40 else 0,cols*25,bank=bank)
            (work/f'calculator-saved-{label}.bin').write_bytes(screen)
            assert screen==calculator_screen(cols,'42',['42'],save_status='HISTORY SAVED AND VERIFIED')
        for value in b'SHISTORY':key(value)
        key(13)
        assert read(lst_symbol('native/calc','save_status'))==b'\3'
        assert read(0x98)==b'\0' and read(0x3dc0)==b'\0' and read(0x3dd0)==b'\0'
        snapshot=work/'saved-history.d64';shutil.copy2(disk,snapshot)
        exported=work/'history.seq'
        subprocess.run(['c1541','-attach',str(snapshot),'-read','history,s,r',str(exported)],check=True,capture_output=True)
        assert exported.read_bytes()==b'42\r'
        report['native_history_saved_verified_and_exclusive']=True
        key(27)
        assert read(0x3d20)==b'\0' and read(0x3d23,2)==b'\0\0'
        assert read(0x3d0e,3)==bytes([175,251,32])
        assert read(0x98)==b'\0','native loader leaked a logical file'
        report['native_calculator_loaded_and_released']=True
        print('PASS: native checked app loading, calculator 12+30=42 and complete owner/channel cleanup',flush=True)
        assert hashlib.sha256(stock.read_bytes()).hexdigest()==report['disk_sha256']
        report.update(passed=True,native_mode=True,banks=2,bytes_per_bank=8192,
                      all_allocations_released=True,stock_disk_unchanged=True)
        print('PASS: native cold boot, both RAM banks, retained independent blocks and release',flush=True)
    except BaseException as error:
        report['error']=str(error)
        if mon:
            try:
                report['mmu_failure']=bytes(mon.read_mem(0xd500,0xd50b)).hex()
                report['mailbox_failure']=bytes(mon.read_mem(0x3d00,0x3d1f)).hex()
                (work/'vic-failure.bin').write_bytes(bytes(mon.read_mem(0x400,0x7e7)))
                report['registers_failure']=mon._recv(mon._send(0x31,b'\0'))[1].hex()
            except Exception as diagnostic_error:report['diagnostic_error']=str(diagnostic_error)
        raise
    finally:
        (work/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        process.terminate();process.wait(timeout=10);xv.stop();log.close()


if __name__=='__main__':main()
