"""Independent complete-screen expectations for the native file/app browser."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import time

from native_capture import ROOT,NativeCapture,calculator_screen,expected_screen,wait,verify_boot_layout
from native_image import seal
from native_field_check import field_cells


def safe_name(name):
    return ''.join(chr(c) if 32<=c<127 else ' ' if c==160 else '.' for c in name.ljust(16,b'\xa0'))


def screen_bytes(columns,lines):
    assert len(lines)<=25 and all(len(line)<=columns for line in lines),lines
    text=''.join(line.ljust(columns) for line in lines+['']*(25-len(lines)))
    return bytes(ord(c)-64 if 64<=ord(c)<96 else ord(c)-32 if 96<=ord(c)<128 else ord(c) for c in text)


def ultimate_browser_screen(columns,path,entries,base=0,selected=0,device=1,more=False,error=None,
                            *,path_prompt=None,prompt_device=None,directory_prompt=True,picker=False,
                            field_caret=None,field_view=None,path_error=0,files_app=False):
    def safe(raw):return ''.join(chr(value) if 32<=value<127 else '.' for value in raw)
    def tail(text,width):return text if len(text)<=width else '<'+text[-(width-1):]
    if isinstance(path,str):path=path.encode('latin1')
    lines=['KESTREL CHOOSE A FILE' if picker else 'KESTREL FILES AND APPS','',f'DOS: {device}   FORMAT: ULT',
           'PATH: '+tail(safe(path),columns-7),f'PAGE: {base//8+1}','  KIND NAME']
    for i in range(8):
        if i>=len(entries):lines.append('');continue
        entry=entries[i]
        lines.append(('>' if i==selected else ' ')+('D' if entry[0]&16 else 'F')+' '+tail(safe(entry[1:]),columns-7))
    lines+=['','UP/DOWN SELECT  N/B PAGE',
            'ENTER CHOOSE  P PARENT  R REFRESH' if picker else 'ENTER OPEN  I INSPECT  P PARENT',
            'G PATH  TAB DOS  F FORMAT' if picker else 'R REFRESH  G PATH  TAB DOS',
            'S USE FOLDER FOR SAVE AS  ESC CANCEL' if picker else 'F FORMAT  ESC WORKSPACE  L USB APP',
            error or ('MORE ENTRIES - N FOR NEXT PAGE' if more else 'END OF DIRECTORY')]
    if files_app:
        lines[17]='R REFRESH  G PATH  F1 DOS'
        lines[18]='C COPY  F FORMAT  ESC DESKTOP'
    if path_prompt is not None:
        lines+=[f'USB{device if prompt_device is None else prompt_device}: '+' '*(columns-8),
                'INPUT UNAVAILABLE; ESC RETURNS' if path_error==2 else 'ABSOLUTE PATH REQUIRED' if path_error else
                'ENTER BROWSE TAB DOS CTRL-U CLR ESC' if directory_prompt else 'ENTER RUN TAB DOS CTRL-U CLR ESC']
        if files_app:lines[-1]=lines[-1].replace('TAB DOS','F1 DOS')
    result=bytearray(screen_bytes(columns,lines))
    if path_prompt is not None:result[20*columns+6:21*columns-2]=field_cells(path_prompt,columns-8,field_caret,field_view)
    return bytes(result)


def browser_screen(columns,records,selected=0,device=8,fmt=0,error=None,prompt=None,*,usb_prompt=None,usb_device=1,usb_error=False,picker=False,
                   field_caret=None,field_view=None,files_app=False):
    lines=['KESTREL CHOOSE A FILE' if picker else 'KESTREL FILES AND APPS','',f'DEVICE: {device}   FORMAT: '+('D64','D71','D81')[fmt],
           f'FILES: {len(records)}',' NAME             TYPE   BLOCKS']
    for i in range(selected//8*8,selected//8*8+8):
        if i>=len(records):lines.append('NO FILES' if not records and i==0 else '');continue
        r=records[i];kind='APP' if r.get('app') else ('DEL','SEQ','PRG','USR','REL','CBM','???','???')[r['type']]
        flags=r.get('flags',128)
        lines.append(('>' if i==selected else ' ')+safe_name(r['name'])+' '+kind+
                     (' ' if flags&128 else '*')+('<' if flags&64 else ' ')+' '+str(r['blocks']))
    lines+=['','UP/DOWN SELECT  N/B PAGE' if picker else 'UP/DOWN SELECT  N/B PAGE  A NEXT APP',
            'ENTER CHOOSE  R REFRESH' if picker else 'ENTER OPEN  I INSPECT  R REFRESH',
            'D DEVICE  F FORMAT  ESC CANCEL' if picker else 'D DEVICE  F FORMAT  ESC WORKSPACE',
            'S USE DEVICE FOR SAVE AS' if picker else '* UNCLOSED  < LOCKED  L USB APP','',error or '']
    if files_app:
        lines[16]='D DEVICE  F FORMAT  ESC DESKTOP'
        lines[17]='C COPY  * UNCLOSED  < LOCKED'
    if prompt is not None:lines+=['DEVICE (8-30): '+' '*5]
    if usb_prompt is not None:
        limit=columns-8
        lines+=[f'USB{usb_device}: '+' '*limit,'INPUT UNAVAILABLE; ESC RETURNS' if usb_error==2 else 'ABSOLUTE PATH REQUIRED' if usb_error else 'ENTER RUN TAB DOS CTRL-U CLR ESC']
        if files_app:lines[-1]=lines[-1].replace('TAB DOS','F1 DOS')
    result=bytearray(screen_bytes(columns,lines))
    if prompt is not None:
        at=20*columns+len('DEVICE (8-30): ')
        result[at:at+5]=field_cells(prompt,5,field_caret,field_view)
    if usb_prompt is not None:result[20*columns+6:21*columns-2]=field_cells(usb_prompt,columns-8,field_caret,field_view)
    return bytes(result)


def preview_screen(columns,name,data,offset=0,eof=False,error=None):
    assert len(data)<=128
    lines=['FILE: '+safe_name(name),f'OFFSET: {offset:08X}  BYTES: {len(data)}','']
    for row in range(16):
        part=data[row*8:(row+1)*8]
        if not part:lines.append('');continue
        printable=''.join(chr(c) if 32<=c<127 else '.' for c in part)
        lines.append(f'{(offset+row*8)&65535:04X} '+
                     ' '.join(f'{c:02X}' for c in part).ljust(24)+' '+printable.ljust(8))
    lines+=['','ENTER/N NEXT PAGE  ESC FILE LIST']
    if eof and not error:lines.append('END OF FILE')
    if error:lines.append(error)
    return screen_bytes(columns,lines)


def disk_records(image,fmt=0):
    """Read the host fixture's native CBM directory independently of Kestrel."""
    sizes=([21]*17+[19]*7+[18]*6+[17]*5)*(2 if fmt==1 else 1) if fmt!=2 else [40]*80
    assert len(image)==sum(sizes)*256
    def sector(track,number):
        assert 1<=track<=len(sizes) and 0<=number<sizes[track-1]
        start=(sum(sizes[:track-1])+number)*256
        return image[start:start+256]
    link=(40,3) if fmt==2 else (18,1);visited=set();records=[]
    while link[0]:
        assert link not in visited and link[0]==(40 if fmt==2 else 18)
        visited.add(link);block=sector(*link)
        for index in range(0,256,32):
            tag=block[index+2];kind=tag&7
            if not kind:continue
            first=sector(*block[index+3:index+5])
            app=kind==2 and bool(tag&128) and (first[0] or first[1]>=35) and first[2:8]==b'\0\x60NAPP'
            records.append(dict(name=block[index+5:index+21].rstrip(b'\xa0'),type=kind,flags=tag&192,
                                blocks=int.from_bytes(block[index+30:index+32],'little'),app=bool(app)))
        link=tuple(block[:2])
    return records


def prepare_browser(work,fmt=0):
    disk=work/'native.d64';shutil.copy2(ROOT/'target/native/kestrel.d64',disk)
    data_disk=disk
    if fmt:
        extension=('d64','d71','d81')[fmt];data_disk=work/('data.'+extension)
        subprocess.run(['c1541','-format','browser test,01',extension,str(data_disk)],check=True,capture_output=True)
    else:
        subprocess.run(['c1541','-attach',str(disk),'-delete','calc'],check=True,capture_output=True)
    # The calculator's disk name deliberately differs from the fixed shortcut.
    subprocess.run(['c1541','-attach',str(data_disk),'-write',str(ROOT/'target/native/calc.prg'),'number,p'],check=True,capture_output=True)
    header=bytearray(32);header[:8]=b'NAPP'+bytes([1,1,2,0])
    body=bytes.fromhex('a9778d2f3d4c561c')
    header[8:10]=(32+len(body)).to_bytes(2,'little');header[10]=1;header[12:14]=b'\x20\0'
    header[16:23]=b'BAD APP';bad=bytearray(seal(b'\0\x60'+header+body));bad[16]^=1
    bad_path=work/'badapp.prg';bad_path.write_bytes(bad)
    subprocess.run(['c1541','-attach',str(data_disk),'-write',str(bad_path),'badapp,p'],check=True,capture_output=True)
    fixtures={'hexdata':bytes(range(256))+b'\0','zero':b'\0','empty':b''}
    fixtures.update({f'file{i:02}':bytes([i])*(i+1) for i in range(12)})
    for name,content in fixtures.items():
        source=work/(name+'.seq');source.write_bytes(content)
        subprocess.run(['c1541','-attach',str(data_disk),'-write',str(source),name+',s'],check=True,capture_output=True)
    return disk,data_disk,fixtures


class BrowserClient:
    def __init__(self,mon,work,quiet=.2,scan_quiet=2,capture_quiet=.2):
        self.mon,self.work,self.quiet,self.scan_quiet=mon,work,quiet,scan_quiet
        self.capture=NativeCapture(mon,work,quiet=capture_quiet)
        self.events=[];self.frames=[];self.heaps=[];self.selected=0

    def read(self,address,count=1):
        data=bytes(self.mon.read_mem(address,address+count-1));self.mon.resume();return data

    def put(self,address,data):self.mon.write_mem(address,data);self.mon.resume()

    def key(self,value,quiet=None):
        wait(lambda:self.read(0x3d12)==b'\1' and self.read(0xd0)==b'\0','native browser ready',120)
        before=int.from_bytes(self.read(0x3d13,2),'little');started=time.monotonic()
        self.put(0x3d12,b'\0');self.put(0x34a,bytes([value]));self.put(0xd0,b'\1')
        time.sleep(self.quiet if quiet is None else quiet)
        wait(lambda:int.from_bytes(self.read(0x3d13,2),'little')==(before+1)&65535 and self.read(0x3d12)==b'\1',
             f'native browser key {value:02x}',180)
        self.events.append(dict(key=value,elapsed_seconds=round(time.monotonic()-started,3),
                                app_state=self.read(0x3d20,13).hex(),files=self.read(0x3d80,0x64).hex()))

    def select(self,index):
        while self.selected!=index:
            difference=index-self.selected
            key,step=(ord('N'),8) if difference>=8 else (ord('B'),-8) if difference<=-8 else (0x11,1) if difference>0 else (0x91,-1)
            self.key(key);self.selected+=step

    def frames_equal(self,label,expect):
        vic=self.read(0x400,1000);vdc=self.capture.capture(label+'-vdc',mode=1)
        (self.work/(label+'-vic.bin')).write_bytes(vic)
        assert vic==expect(40),(label,'VIC complete screen')
        assert vdc==expect(80),(label,'VDC complete screen')
        self.frames.append(label)
        print(f'Verified both native screens: {label}',flush=True)

    def heap_equal(self,label,expected):
        # N_FREE* is a snapshot published by N_STATS, not a live counter.
        # Read the bank-0 allocation tables independently of that mailbox.
        pages=self.read(0x3800,512);handles=self.read(0x3c00,256)
        records=[handles[i:i+8] for i in range(0,256,8)]
        actual=(pages[:256].count(0),pages[256:].count(0),
                sum(r[0]==0 and r[4:7]!=b'\xff'*3 for r in records))
        self.heaps.append(dict(label=label,free=list(actual),pages=pages.hex(),handles=handles.hex()))
        assert actual==expected,(label,actual,expected)


def browser_workflow(client,records,fixtures,fmt,report,save):
    report['events']=client.events;report['frames']=client.frames;report['captures']=client.capture.records
    report['heap_observations']=client.heaps
    report['resident_boot']=verify_boot_layout(client.capture)
    # Preserve two unrelated workspace allocations across browser/target switches.
    protected=[]
    for bank in (0,1):
        client.key(ord('1')+bank);client.key(ord('A'));page=client.read(0x3d03)[0]
        client.key(ord('W'));client.key(ord('V'))
        assert client.read(0x3d16)==b'\0'
        protected.append((bank,page))
    report['workspace_allocations']=[dict(bank=bank,page=page,bytes=8192) for bank,page in protected]
    client.key(ord('B'),quiet=client.scan_quiet)
    if fmt:
        for _ in range(fmt):client.key(ord('F'),quiet=client.scan_quiet)
        for key in b'D9':client.key(key)
        client.key(13,quiet=client.scan_quiet)
    device=9 if fmt else 8
    def listing(label,error=None):
        client.frames_equal(label,lambda columns:browser_screen(columns,records,client.selected,device,fmt,error=error));save()
    listing('browser-initial')
    client.heap_equal('browser-cache',(143-(ROOT/'target/native/browse.prg').read_bytes()[12],182,28))
    names=[r['name'] for r in records]
    client.select(len(records)-1);listing('browser-last-page')
    for name in ('hexdata','zero','empty'):
        client.select(names.index(name.upper().encode()));client.key(13,quiet=client.scan_quiet)
        content=fixtures[name]
        for offset in range(0,max(1,len(content)),128):
            if offset:client.key(ord('N'))
            data=content[offset:offset+128];eof=offset+len(data)==len(content)
            client.frames_equal(f'preview-{name}-{offset}',lambda columns:preview_screen(columns,name.upper().encode(),data,offset,eof));save()
        assert client.read(0x98)==b'\0' and client.read(0x3de0,4)==bytes(4)
        client.key(ord('N'))
        client.key(27)
    client.select(names.index(b'BADAPP'));client.put(0x3d2f,b'\xa5')
    client.key(13,quiet=client.scan_quiet);client.selected=0
    assert client.read(0x3d2f)==b'\xa5','rejected image executed'
    listing('bad-app-rejected',error='APPLICATION CHECKSUM FAILED')
    target=names.index(b'NUMBER')
    if target>0 and not any(r['app'] for r in records[1:target]):
        client.key(ord('A'));client.selected=target
    else:client.select(target)
    client.key(13,quiet=client.scan_quiet)
    assert client.read(0x3d21)==bytes([device]) and client.read(0x3d2c)==bytes([fmt])
    client.heap_equal('calculator-after-browser-handoff',(127,217,28))
    for key in b'12+30=':client.key(key)
    client.frames_equal('discovered-calculator',lambda columns:calculator_screen(columns,'42',['42']));save()
    for key in b'SBROWSAVE':client.key(key)
    client.key(13,quiet=client.scan_quiet)
    client.frames_equal('calculator-saved',lambda columns:calculator_screen(columns,'42',['42'],save_status='HISTORY SAVED AND VERIFIED'));save()
    client.key(27,quiet=client.scan_quiet);client.selected=0
    records.append(dict(name=b'BROWSAVE',type=1,flags=128,blocks=1,app=False))
    listing('browser-after-app-return')
    assert client.read(0x3d21)==b'\x08' and client.read(0x3d2c)==b'\0','system app source was not restored'
    client.key(27)
    assert client.read(0x3d20)==b'\0' and client.read(0x3d23,2)==bytes(2)
    client.heap_equal('workspace-after-apps',(143,219,30))
    assert client.read(0x98)==b'\0'
    for bank,page in protected:
        client.key(ord('1')+bank);client.key(ord('V'))
        assert client.read(0x3d16)==b'\0'
        actual=client.capture.capture(f'workspace-bank-{bank}',bank=bank,address=page*256,count=2000)
        assert actual==bytes((i&255)^(i>>8)^(0xa5 if bank else 0) for i in range(2000))
        client.key(ord('F'))
    client.frames_equal('workspace-restored',lambda columns:expected_screen(columns,1));save()
    client.heap_equal('all-memory-released',(175,251,32))
    assert client.read(0x3de0,4)==bytes(4)
    report.update(native_checks_passed=True,directory_entries=len(records),data_device=device,format=fmt,
                  independent_workspace_prefix_bytes=2000,native_workspace_verify_bytes=8192,
                  rejected_image_did_not_execute=True,renamed_app_loaded=True,source_format_preserved=True,
                  browser_cache_released_before_target=True,all_owned_memory_and_files_released=True)
    save()
