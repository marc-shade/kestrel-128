"""Cold-boot the native disk on the reference C128; restore the drives.

Invoked by hw_ultimate_check.py --native. This is a bounded memory-workspace
test, with no cartridge-file commands. Drive A is recorded, private images are
mounted on it read-only, and afterwards it gets its original image and mode
back, every upload is deleted and confirmed absent, and the C128 is reset
(hw_session.py). Host RAM DMA leaves a full minute for boot IEC traffic
before observations.
"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

from hw_session import HardwareSession
from hw_dos_context import DosContexts
from hw_storage_check import HardwareMonitor
from hwlib import lst_symbol
from native_capture import NativeCapture, expected_screen, calculator_screen, wait, ROOT, verify_boot_layout
from native_image import seal


def hashes():
    files=sorted((ROOT/'target/native').glob('*.prg'))+[ROOT/'target/native/kestrel.d64']
    files+=sorted((ROOT/'target/native-desktop').glob('*.prg'))+sorted((ROOT/'target/native-desktop').glob('*.d64'))
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def quiet_boot(label,seconds=60):
    # A RAM DMA read stalls the CPU and can corrupt a bit-timed IEC load.
    print(f'{label}: waiting {seconds} seconds for IEC before any RAM DMA',flush=True)
    time.sleep(seconds/2)
    print(f'{label}: continuing quiet boot interval',flush=True)
    time.sleep(seconds-seconds/2)


def run(ult,*,dos_contexts=False):
    work=Path(tempfile.mkdtemp(prefix='kestrel-hardware-native-'))
    print(f'Native hardware evidence: {work}',flush=True)
    mon=HardwareMonitor(ult)
    report=dict(build=hashes(),passed=False,checks=[],boot_quiet_seconds=60,
                host=ult.host)
    capture=NativeCapture(mon,work);report['captures']=capture.records

    def save():
        (work/'report.json').write_text(json.dumps(report,indent=2)+'\n')

    def read(address,count=1):return bytes(mon.read_mem(address,address+count-1))

    def settled_read(address,count,attempts=8):
        # The Ultimate's REST memory read occasionally answers with
        # other bytes (seen on the reference machine: 1 of 24 reads);
        # a value counts once two consecutive reads agree.
        previous=read(address,count)
        for _ in range(attempts):
            current=read(address,count)
            if current==previous:return current
            report.setdefault('unsettled_reads',[]).append(dict(address=address,first=previous.hex(),second=current.hex()))
            previous=current
        raise AssertionError(('direct read never settled',hex(address)))

    session=HardwareSession(ult,work,report,save,drives=('a',),
        dos_contexts=DosContexts(ult,work) if dos_contexts else None)
    before=session.snapshot();assert before['a']['enabled'] and before['a']['bus_id']==8
    (work/'ultimate-version.json').write_text(ult.version())

    def body():
        try:
            session.upload((ROOT/'target/native/kestrel.d64').read_bytes(),'a','d64','readonly')
            ult.reset();quiet_boot('Native C128 boot')
            wait(lambda:read(0x1c13,6)==b'KES128' and read(0x3d12)==b'\1','native cold boot',120)
            assert read(0x3d0e,3)==bytes([175,251,32]),read(0x3d00,32).hex()
            report['resident_boot']=verify_boot_layout(capture)

            def key(value,expected=0,quiet=2):
                wait(lambda:read(0x3d12)==b'\1' and read(0xd0)==b'\0','native input ready',30)
                previous=int.from_bytes(read(0x3d13,2),'little')
                mon.write_mem(0x3d12,b'\0')
                mon.write_mem(0x34a,bytes([value]));mon.write_mem(0xd0,b'\1')
                time.sleep(quiet)
                wait(lambda:int.from_bytes(read(0x3d13,2),'little')==(previous+1)&65535 and read(0x3d12)==b'\1',
                     f'native key {value:02x}',60)
                active=read(0x3d20)[0]
                actual=read(0x3d27 if active else 0x3d16)[0]
                assert actual==expected,(active,actual,expected,read(0x3d20,8).hex())
                report.setdefault('key_events',[]).append(dict(key=value,result=actual,event=previous+1,owner=active))
                save()

            def screens(label,bank,free=(175,251),slots=32,handle=b'\0'*4,result=0):
                vic=settled_read(0x400,1000);(work/f'{label}-vic.bin').write_bytes(vic)
                first=capture.capture(label+'-vdc',mode=1)
                second=capture.capture(label+'-vdc-repeat',mode=1)
                assert first==second,'native VDC captures disagree'
                assert vic==expected_screen(40,bank,free,slots,handle,result),'native VIC screen differs'
                assert first==expected_screen(80,bank,free,slots,handle,result),'native VDC screen differs'
                (work/f'{label}.txt').write_text('\n'.join(''.join(chr(c+64) if c<32 else chr(c) for c in first[row*80:(row+1)*80]).rstrip() for row in range(25))+'\n')
                save()

            screens('initial',0)
            report['checks'].append('native disk cold boot; both complete text screens; native MMU/common RAM confirmed by CPU probe')
            key(ord('V'),4)  # no allocation: the workspace must expose the error
            allocations=[]
            for bank,keycode in ((0,ord('1')),(1,ord('2'))):
                key(keycode,4 if bank==0 else 0);key(ord('A'))
                page=read(0x3d03)[0];handle=read(0x3d04,4)
                assert page==(0xdf if bank==0 else 4)
                allocations.append((bank,page,handle))
                key(ord('W'));key(ord('V'))
                assert read(0x3d0e+bank)[0]==(175 if bank==0 else 251)-32
                print(f'PASS: physical native bank {bank} allocated, filled and verified 8192 bytes',flush=True)
            for bank,page,handle in allocations:
                expected=bytes((i&255)^(i>>8)^(0xa5 if bank else 0) for i in range(8192))
                actual=b''.join(
                    capture.capture(f'bank-{bank}-{offset:04x}',bank=bank,address=page*256+offset,count=min(2000,8192-offset))
                    for offset in range(0,8192,2000))
                assert actual==expected,f'independent native bank {bank} bytes differ'
                (work/f'bank-{bank}-all.bin').write_bytes(actual)
            report['checks'].append('16,384 bytes independently compared; native ROM observers in both banks agree with host patterns')
            screens('allocated',1,(143,219),30,allocations[1][2])
            display=lst_symbol('native/calc','dispbuf')
            history_handle=lst_symbol('native/calc','history_handle')

            def calculator_capture(label,result,history):
                direct=settled_read(display,8);(work/(label+'-display-direct.bin')).write_bytes(direct)
                observed=capture.capture(label+'-display-cpu',bank=0,address=display,count=8)
                assert direct==observed,(label,'display reads disagree',direct.hex(),observed.hex())
                assert observed.split(b'\0')[0]==result.encode(),(label,result,observed.hex())
                vic=settled_read(0x400,1000);(work/(label+'-vic.bin')).write_bytes(vic)
                vdc=capture.capture(label+'-vdc',mode=1)
                repeat=capture.capture(label+'-vdc-repeat',mode=1)
                assert vdc==repeat and vic==calculator_screen(40,result,history) and vdc==calculator_screen(80,result,history)
                save()

            print('Loading the native calculator; leaving 30 seconds for IEC before observations',flush=True)
            key(ord('C'),quiet=30)
            assert read(0x3d20)==bytes([32]) and read(0x3d23)==b'\2'
            assert read(0x3800,256).count(0)==127 and read(0x3900,256).count(0)==217
            for code in b'12+30=':key(code)
            calculator_capture('calculator-result','42',['42'])
            for code in b'C65535+1=':key(code)
            calculator_capture('calculator-overflow','OVF',['OVF','42'])
            for code in b'C1/0=':key(code)
            calculator_capture('calculator-errors','DIV/0',['DIV/0','OVF','42'])
            slot=read(history_handle)[0]-1
            record=read(0x3c00+slot*8,8)
            assert record[:2]==bytes([32,1]) and record[3]==2
            history=capture.capture('calculator-history',bank=1,address=record[2]*256,count=48)
            assert history==b''.join(word.ljust(16,b' ') for word in (b'42',b'OVF',b'DIV/0'))
            key(27)                 # exit remains available while DIV/0 is latched
            assert read(0x3d20)==b'\0' and read(0x3d23,2)==b'\0\0'
            assert read(0x3d0e,3)==bytes([143,219,30]) and read(0x98)==b'\0'
            report['checks'].append('native calculator loads while both workspace blocks remain owned; arithmetic/errors and complete screens match; independent bank-1 history matches; exit releases only app resources')

            # A private disk changes one payload byte without resealing the CRC.
            # The kernel itself and the mounted good distribution stay unchanged.
            damaged=bytearray((ROOT/'target/native/calc.prg').read_bytes());damaged[-1]^=1
            bad_prg=work/'damaged-calc.prg';bad_prg.write_bytes(damaged)
            bad_disk=work/'damaged-app.d64';shutil.copy2(ROOT/'target/native/kestrel.d64',bad_disk)
            subprocess.run(['c1541','-attach',str(bad_disk),'-delete','calc','-write',str(bad_prg),'calc'],check=True,capture_output=True)
            session.upload(bad_disk.read_bytes(),'a','d64','readonly')
            print('Checking a damaged native app; leaving 30 seconds for IEC',flush=True)
            key(ord('C'),expected=0x14,quiet=30)
            assert read(0x3d27)==bytes([0x14]) and read(0x3d20)==b'\0' and read(0x98)==b'\0'
            screens('rejected-app',1,(143,219),30,allocations[1][2],result=0x14)
            returned=bytearray((ROOT/'target/native/calc.prg').read_bytes())
            entry=int.from_bytes(returned[14:16],'little')
            returned[2+entry:5+entry]=bytes([0xa9,2,0x60])
            exit_prg=work/'return-error.prg';exit_prg.write_bytes(seal(returned))
            exit_disk=work/'return-error.d64';shutil.copy2(ROOT/'target/native/kestrel.d64',exit_disk)
            subprocess.run(['c1541','-attach',str(exit_disk),'-delete','calc','-write',str(exit_prg),'calc'],check=True,capture_output=True)
            session.upload(exit_disk.read_bytes(),'a','d64','readonly')
            print('Checking native app return-code reporting; leaving 30 seconds for IEC',flush=True)
            key(ord('C'),expected=2,quiet=30)
            assert read(0x3d27)==b'\0' and read(0x3d24)==b'\2' and read(0x3d20)==b'\0'
            screens('app-return-error',1,(143,219),30,allocations[1][2],result=2)
            report['checks'].append('a valid app returning an error is closed and released; the workspace displays its exit result separately from load errors')
            session.upload((ROOT/'target/native/kestrel.d64').read_bytes(),'a','d64','readonly')
            print('Reloading the valid native app after rejection; leaving 30 seconds for IEC',flush=True)
            key(ord('C'),quiet=30)
            assert read(0x3d20)==bytes([32]) and read(0x3d23)==b'\2'
            assert read(display,8).split(b'\0')[0]==b'0'
            key(27)
            assert read(0x3d0e,3)==bytes([143,219,30]) and read(0x98)==b'\0'
            report['checks'].append('one-byte damaged app is rejected with CRC error before entry; caller allocations and IEC channels survive; valid calculator can launch and return afterward')
            for bank,keycode in ((0,ord('1')),(1,ord('2'))):
                key(keycode);key(ord('V'));key(ord('F'))
            assert read(0x3d0e,3)==bytes([175,251,32])
            screens('released',1)
            key(ord('1'));key(ord('2'))
            report['checks'].append('both blocks survive switches and observations; all pages/handles released; native input remains live')
            after_native=session.drives('native')
            assert {k:v for k,v in before.items() if k!='a'}=={k:v for k,v in after_native.items() if k!='a'}
            report.update(native_checks_passed=True,bytes_independently_verified=16384)
        except BaseException as error:
            report['error']=str(error)
            try:
                (work/'failure-mailbox.bin').write_bytes(read(0x3d00,32))
                (work/'failure-vic.bin').write_bytes(read(0x400,1000))
                (work/'failure-app-slot.bin').write_bytes(read(0x6000,4096))
                (work/'failure-app-state.bin').write_bytes(read(0x3d20,96))
            except Exception as diagnostic_error:report['diagnostic_error']=str(diagnostic_error)
            raise

    try:session.run(body)
    finally:
        report['images_unchanged']=report['build']==hashes();save()
    assert report['images_unchanged']
    report['passed']=True;save()
    print(f'HW-NATIVE PASS; native RAM/screens verified; drives restored, uploads deleted; evidence {work}',flush=True)
