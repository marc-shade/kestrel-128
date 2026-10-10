"""Bounded native C128 workspace observations for emulator/hardware tests."""
from contextlib import nullcontext
import hashlib
import json
from pathlib import Path
import subprocess
import time

from hwlib import lst_symbol

ROOT=Path(__file__).resolve().parent


def wait(predicate,label,seconds=30):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        if predicate():return
        time.sleep(.1)
    raise AssertionError(label)


def expected_screen(columns,bank,free=(175,251),slots=32,handle=b'\0'*4,result=0):
    lines=['KESTREL - NATIVE MEMORY WORKSPACE','',f'SELECTED BANK: {bank}',
           f'FREE 256-BYTE PAGES (HEX) 0/1: {free[0]:02X}/{free[1]:02X}',
           f'FREE HANDLES (HEX): {slots:02X}',f'SELECTED HANDLE: {int.from_bytes(handle,"little"):08X}',
           f'LAST RESULT: {result:02X}','','1/2 SELECT BANK  A ALLOCATE 8K',
           'W FILL  V VERIFY  F RELEASE','C CALCULATOR  B FILES AND APPS','00 OK  04 INVALID HANDLE  0A MISMATCH','',
           'NATIVE DESKTOP MIGRATION IN PROGRESS']
    lines+=['']*(25-len(lines))
    assert all(len(line)<=columns for line in lines)
    return bytes(ord(c)-64 if 'A'<=c<='Z' else ord(c) for line in lines for c in line.ljust(columns))


def calculator_screen(columns,result,history,view=0,save_prompt=None,save_status=None,*,usb=False,save_caret=None,save_view=None):
    from native_field_check import field_cells
    lines=['KESTREL CALCULATOR','',f'RESULT: {result}','','0-9 + - * / =  DEL  C CLEAR',
           'ESC RETURN   S SAVE   N/B HISTORY','','HISTORY (NEWEST FIRST, 32 RETAINED):']
    lines+=history[view:view+8] if history else ['NO RESULTS YET']
    if save_prompt is not None:
        field_row=len(lines)+2
        lines+=['','SAVE AS (BESIDE USB APP)' if usb else 'SAVE AS (SEQ FILE ON IEC DISK)',
                'NAME: '+' '*19,'ENTER SAVE   ESC CANCEL']
    elif save_status is not None:lines+=['',save_status]
    lines+=['']*(25-len(lines))
    screen=bytearray(ord(c)-64 if 'A'<=c<='Z' else ord(c) for line in lines for c in line.ljust(columns))
    if save_prompt is not None:
        at=field_row*columns+6
        screen[at:at+19]=field_cells(save_prompt,19,save_caret,save_view)
    return bytes(screen)


def verify_boot_layout(capture):
    """Compare the freshly relocated bytes before allocations modify heap state."""
    layout=json.loads((ROOT/'target/native/layout.json').read_text())
    image=(ROOT/'target/native/kestrel.prg').read_bytes()
    origin=int.from_bytes(image[:2],'little');size=layout['low_padded_end']-layout['low_start']
    start=2+layout['staging_start']-origin;expected=image[start:start+size]
    assert len(expected)==size and layout['load_end']==origin+len(image)-2
    observed=b''.join(capture.capture(f'resident-initial-{offset:04x}',address=layout['low_start']+offset,count=min(2000,size-offset))
                      for offset in range(0,size,2000))
    assert observed==expected,'cold-boot resident bytes differ from the staged image'
    service_size=layout['service_end']-layout['service_start']
    offset=2+layout['service_start']-origin
    service=b''.join(capture.capture(f'service-initial-{part:04x}',address=layout['service_start']+part,
                                    count=min(2000,service_size-part)) for part in range(0,service_size,2000))
    assert service==image[offset:offset+service_size],'resident Ultimate bytes differ from the boot image'
    return dict(layout=layout,bytes=size,sha256=hashlib.sha256(observed).hexdigest(),cpu_capture_matches_image=True,
                service_bytes=service_size,service_sha256=hashlib.sha256(service).hexdigest(),service_matches_image=True)


class ObservationChanged(AssertionError):
    """Native RAM the observer borrows or watches changed during a capture.

    Raised after the borrowed bytes were restored and the observer resumed, so
    a caller that can explain the changes (a pointer redraw) may retake."""
    def __init__(self, message, changes):
        super().__init__(message)
        self.changes = changes


class NativeCapture:
    def __init__(self,mon,work,quiet=2,*,kernel_prefix='native',batch=None):
        self.mon,self.work,self.quiet=mon,work,quiet
        self.batch=batch if batch is not None else lambda label:nullcontext()
        self.kernel_prefix=kernel_prefix
        assert lst_symbol(kernel_prefix+'/kestrel','native_code_end')<=0x3800
        output=work/'native-read.prg'
        subprocess.run(['64tass','-a',str(ROOT/'probes/native-read.asm'),'-o',str(output)],check=True,capture_output=True)
        self.prg=output.read_bytes()
        assert self.prg[:2]==b'\0\x3e' and len(self.prg)-2<=0x1f0
        self.records=[]

    def control(self):
        # Every address this class touches is bank-0 RAM. A VICE pause inside
        # the probe's bank-1 INDFET would otherwise read bank 1 there.
        bank=getattr(self.mon,'control_bank',None)
        return {} if bank is None else dict(bank=bank)

    def read(self,address,count=1):
        data=bytes(self.mon.read_mem(address,address+count-1,**self.control()));self.mon.resume();return data

    def write(self,address,data):
        self.mon.write_mem(address,data,**self.control())

    def capture(self,label,*,mode=0,bank=0,address=0,count=2000):
        assert mode in (0,1) and bank in (0,1) and 1<=count<=2000 and address+count<=65536
        if mode==0 and bank==0:
            assert all(address+count<=start or address>=end for start,end in ((0x3a00,0x3c00),(0x3e00,0x4000))), 'capture source overlaps borrowed scratch'
        with self.batch(label+'-before'):
            assert self.read(0x1c13,6)==b'KES128'
            assert self.read(0x3d11,2)==b'\0\1' and self.read(0xd0)==b'\0','native workspace must be idle'
            assert self.read(0x3d91)==b'\0','native file service must be idle before borrowing its buffer'
            oldirq=self.read(0x314,2);assert oldirq!=b'\0\x3e'
            output=self.read(0x3a00,512);scratch=self.read(0x3e00,512)
            metadata=self.read(0x3800,0x600)
            resident=self.read(0x1300,0x900)
        record=dict(label=label,mode=mode,bank=bank,address=address,count=count,
                    probe_sha256=hashlib.sha256(self.prg).hexdigest(),restored=False,
                    output_address=0x3a00,chunk_limit=512,chunks=[],address_resyncs=0,
                    control_bank=self.control().get('bank'))
        self.records.append(record)
        observed_before={'output':(0x3a00,output),'scratch':(0x3e00,scratch),
                         'metadata':(0x3800,metadata),'resident':(0x1300,resident)}
        record['borrower_checks']={}
        for name,(start,before) in observed_before.items():
            filename=f'{label}-borrower-{name}-before.bin'
            (self.work/filename).write_bytes(before)
            record['borrower_checks'][name]=dict(address=start,bytes=len(before),
                before_file=filename,before_sha256=hashlib.sha256(before).hexdigest(),
                source='host observation; not CPU-authoritative metadata')
        result=bytearray()
        armed=False
        try:
            with self.batch(label+'-install'):
                self.write(0x3e00,self.prg[2:])
            for offset in range(0,count,512):
                size=min(512,count-offset)
                # $3fee skip count, then the command; release and hold flag clear.
                command=b'\0\0'+oldirq+b'\0'+bytes([mode,bank])+(address+offset).to_bytes(2,'little')+size.to_bytes(2,'little')+bytes(7)
                with self.batch(label+f'-command-{offset:04x}'):
                    self.write(0x3fee,command)
                    self.write(0x314,b'\0\x3e');armed=True;self.mon.resume()
                time.sleep(self.quiet)
                # IRQs that find the foreground busy pass through and leave the hook armed.
                wait(lambda:self.read(0x3ff2)!=b'\0','native capture chunk complete',60)
                with self.batch(label+f'-result-{offset:04x}'):
                    status=self.read(0x3ff2,12)
                    status_file=f'{label}-chunk-{offset:04x}-status.bin'
                    (self.work/status_file).write_bytes(status)
                    chunk=dict(address=address+offset,count=size,status_file=status_file,
                               status_sha256=hashlib.sha256(status).hexdigest())
                    record['chunks'].append(chunk)
                    assert len(status)==12,'native capture status length differs'
                    chunk.update(code=status[0],
                               address_resyncs=int.from_bytes(status[7:9],'little'),
                               mode_register=status[9],common_register=status[10],foreground_mmu=status[11])
                    record.update({k:chunk[k] for k in ('code','mode_register','common_register','foreground_mmu')})
                    record['address_resyncs']+=chunk['address_resyncs']
                    # Retain the first payload even if a status guard rejects it.
                    # A raw host read is evidence, not an accepted CPU result.
                    payload=self.read(0x3a00,size)
                    payload_file=f'{label}-chunk-{offset:04x}-payload.bin'
                    (self.work/payload_file).write_bytes(payload)
                    chunk.update(payload_file=payload_file,payload_bytes=len(payload),
                                 payload_sha256=hashlib.sha256(payload).hexdigest())
                    # The probe still holds the IRQ: put N_BUFFER back before the
                    # foreground can run, then release it.
                    self.write(0x3a00,output[:size])
                    chunk['output_restored']=self.read(0x3a00,size)==output[:size]
                    chunk['busy_irqs']=self.read(0x3fee)[0]
                    self.write(0x3ffe,b'\1')
                    assert chunk['output_restored'],('native output buffer not restored while held',record)
                    assert status[0]==1,record
                    # The native ROM IRQ entry saves the mapping then selects
                    # $00. Its CLI permits a nested IRQ to save $00 legitimately.
                    # The historical foreground_mmu field is the interrupted
                    # context's mapping, not necessarily the app's mapping.
                    assert not status[9]&0x40 and status[10]&15==4 and status[11] in (0,0x0e),record
                    assert len(payload)==size,'native capture payload length differs'
                    result.extend(payload)
                wait(lambda:self.read(0x314,2)==oldirq,'native IRQ vector restored after chunk',20)
                armed=False
                assert self.read(0x3fff)==b'\0',('native capture hold gave up before the release',record)
            (self.work/(label+'.bin')).write_bytes(result)
            return bytes(result)
        except BaseException as error:
            record['capture_error']=dict(type=type(error).__name__,message=str(error))
            raise
        finally:
            if armed:
                # A failed host step: disarm a probe that never ran and release
                # one that holds; $3a00 is put back below once it has returned.
                with self.batch(label+'-disarm'):
                    self.write(0x314,oldirq);self.write(0x3ffe,b'\1');self.mon.resume()
            wait(lambda:self.read(0x314,2)==oldirq,'native IRQ vector restored',20)
            time.sleep(.1)
            failures=[]
            with self.batch(label+'-restore'):
                if armed:self.write(0x3a00,output)
                self.write(0x3e00,scratch);self.mon.resume()
                for name,(start,before) in observed_before.items():
                    after=self.read(start,len(before))
                    filename=f'{label}-borrower-{name}-after.bin'
                    (self.work/filename).write_bytes(after)
                    differences=[i for i,(left,right) in enumerate(zip(before,after)) if left!=right]
                    record['borrower_checks'][name].update(after_file=filename,
                        after_sha256=hashlib.sha256(after).hexdigest(),matches=after==before,
                        different_offsets=differences,observed_bytes=len(after))
                    # Observe every remaining region once even after a mismatch.
                    # These are first readbacks, never replacement/retry evidence.
                    fields={0x3d0c:'N_VALUE',0x3d13:'N_KEYS',0x3d14:'N_KEYS+1',
                            0x3d15:'N_LASTKEY',0x3d2f:'N_DESKTOPSEL'}
                    changes=[dict(address=start+i,before=before[i],after=after[i],
                                  field=fields.get(start+i)) for i in differences]
                    record['borrower_checks'][name]['changes']=changes
                    if name=='metadata' and len(after)==len(before):
                        record['input_observation']=dict(
                            keys_before=int.from_bytes(before[0x513:0x515],'little'),
                            keys_after=int.from_bytes(after[0x513:0x515],'little'),
                            last_key_before=before[0x515],last_key_after=after[0x515],
                            source='host snapshot; input origin is not established')
                    message={'output':'native output buffer differs after restoration',
                             'scratch':'native observer scratch differs after restoration',
                             'metadata':'native metadata/ABI changed during observation',
                             'resident':'resident low kernel changed during observation'}[name]
                    if after!=before:
                        failures.append(dict(region=name,message=message,changes=changes,
                                             expected_bytes=len(before),observed_bytes=len(after)))
                    record['borrower_failures']=failures
            if failures:
                details=[]
                for failure in failures:
                    changed=', '.join(f'${c["address"]:04x}'+(' '+c['field'] if c['field'] else '')
                                      for c in failure['changes'][:8])
                    if failure['observed_bytes']!=failure['expected_bytes']:
                        changed+=f' length {failure["observed_bytes"]}/{failure["expected_bytes"]}'
                    details.append(failure['message']+' ('+changed.strip()+')')
                raise ObservationChanged('; '.join(details),[c['address'] for f in failures for c in f['changes']])
            record['restored']=True
