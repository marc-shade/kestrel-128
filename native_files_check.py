"""Shared host driver for the test-only native file client, with real IEC I/O."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

from native_capture import ROOT, wait
from native_image import seal


def exact_disk_files(image,fmt=0):
    """Independent host extraction from linked sectors, including zero bytes."""
    assert fmt in (0,1,2)
    sizes=([21]*17+[19]*7+[18]*6+[17]*5)*(2 if fmt==1 else 1) if fmt!=2 else [40]*80
    assert len(image)==sum(sizes)*256
    directory_track=40 if fmt==2 else 18
    def sector(track,number):
        assert 1<=track<=len(sizes) and 0<=number<sizes[track-1]
        start=(sum(sizes[:track-1])+number)*256
        return image[start:start+256]
    files={};directory=(40,3) if fmt==2 else (18,1);seen_directory=set()
    while directory[0]:
        assert directory not in seen_directory and directory[0]==directory_track
        seen_directory.add(directory);block=sector(*directory)
        for offset in range(0,256,32):
            kind=block[offset+2]
            if not kind&128:continue
            name=block[offset+5:offset+21].rstrip(b'\xa0')
            link=tuple(block[offset+3:offset+5]);chain=set();data=bytearray()
            while link[0]:
                assert link not in chain and link[0]!=directory_track
                chain.add(link);part=sector(*link)
                assert part[0] or part[1]>=1
                data+=part[2:] if part[0] else part[2:part[1]+1]
                link=tuple(part[:2])
            assert len(chain)==int.from_bytes(block[offset+30:offset+32],'little')
            assert name not in files
            files[name]=(kind&7,bytes(data))
        directory=tuple(block[:2])
    return files


def exact_d64_files(image):
    return exact_disk_files(image)


def prepare(work,size=66053,fmt=0):
    app=work/'files-client.prg'
    subprocess.run(['64tass','-a',str(ROOT/'probes/native-files.asm'),'-o',str(app)],check=True,capture_output=True)
    app.write_bytes(seal(app.read_bytes()))
    disk=work/'files.d64';shutil.copy2(ROOT/'target/native/kestrel.d64',disk)
    subprocess.run(['c1541','-attach',str(disk),'-delete','calc','-write',str(app),'calc'],check=True,capture_output=True)
    # This private disk only runs the stream client and returns to the workspace.
    # Keep the source and its full copy on D64 without unrelated app images
    # consuming their capacity as the product browser/editor grow.
    subprocess.run(['c1541','-attach',str(disk),'-delete','browse','-delete','editor'],
                   check=True,capture_output=True)
    data_disk=disk
    if fmt:
        extension=('d64','d71','d81')[fmt]
        data_disk=work/('data.'+extension)
        subprocess.run(['c1541','-format','native files,01',extension,str(data_disk)],check=True,capture_output=True)
    fixtures={
        'source':bytes((i*73+(i//256)*17+(i//65536)*29+11)&255 for i in range(size)),
        'zero':b'\0','cr':b'\r','empty':b'',
        'user':bytes(range(256))+b'\xff',
        'program':b'\1\x08'+bytes(range(256)),
    }
    for length in (2,253,254,255,256,508,509):
        fixtures[f'edge{length}']=bytes((i*97)&255 for i in range(length))
    for name,data in fixtures.items():
        path=work/(name+'.bin');path.write_bytes(data)
        kind='u' if name=='user' else 'p' if name=='program' else 's'
        subprocess.run(['c1541','-attach',str(data_disk),'-write',str(path),name+','+kind],check=True,capture_output=True)
    if not fmt:
        bam=disk.read_bytes()[357*256:358*256]
        free=sum(bam[track*4] for track in range(1,36) if track!=18)
        assert free>=(size+253)//254,'fixture disk cannot hold the complete copy'
    return disk,fixtures


class NativeFiles:
    def __init__(self,mon,work,quiet=.02,device=8,fmt=0,open_quiet=None):
        self.mon,self.work,self.quiet=mon,work,quiet;self.events=[]
        self.device,self.fmt,self.open_quiet=device,fmt,open_quiet

    def read_ram(self,addr,count=1):
        value=bytes(self.mon.read_mem(addr,addr+count-1));self.mon.resume();return value

    def put(self,addr,data):self.mon.write_mem(addr,data);self.mon.resume()

    def key(self,key,expected=0,quiet=None):
        wait(lambda:self.read_ram(0x3d12)==b'\1' and self.read_ram(0xd0)==b'\0','native file client ready',60)
        before=int.from_bytes(self.read_ram(0x3d13,2),'little')
        self.put(0x3d12,b'\0');self.put(0x34a,bytes([key]));self.put(0xd0,b'\1')
        time.sleep(self.quiet if quiet is None else quiet)
        wait(lambda:int.from_bytes(self.read_ram(0x3d13,2),'little')==(before+1)&65535 and self.read_ram(0x3d12)==b'\1',
             f'native file command {key:02x}',120)
        state=self.read_ram(0x3d80,0x64);result=state[0x1f]
        event=dict(key=key,result=result,mailbox=state.hex())
        self.events.append(event)
        if expected is not None:assert result==expected and state[14]==expected,event
        return result

    def open(self,name,mode=0,kind=0,device=None,owner=32,expected=0):
        device=self.device if device is None else device
        self.put(0x3d80,bytes([owner]));self.put(0x3d85,bytes([device,len(name),mode,kind]))
        self.put(0x3d96,bytes([self.fmt]))
        self.put(0x3da0,name)
        self.key(ord('O'),expected,quiet=self.open_quiet)
        return self.read_ram(0x3d81,4)

    def select(self,handle,owner=32):self.put(0x3d80,bytes([owner])+handle)

    def read(self,count=512,expected=0):
        self.put(0x3d89,count.to_bytes(2,'little'));self.key(ord('R'),expected)
        count=int.from_bytes(self.read_ram(0x3d8b,2),'little')
        assert count<=512,count
        return self.read_ram(0x3a00,count) if count else b''

    def write(self,data,expected=0):
        self.put(0x3a00,data);self.put(0x3d89,len(data).to_bytes(2,'little'));self.key(ord('W'),expected)
        if expected==0:assert int.from_bytes(self.read_ram(0x3d8b,2),'little')==len(data)

    def close(self):self.key(ord('C'))


def workflow(client,fixtures,report,save):
    report['file_events']=client.events
    source=client.open(b'SOURCE');destination=client.open(b'COPY',mode=1)
    actual=bytearray()
    for chunk in range(1000):
        client.select(source);data=client.read();actual.extend(data)
        assert data==fixtures['source'][len(actual)-len(data):len(actual)],chunk
        eof=client.read_ram(0x3d8d)[0]
        client.select(destination);client.write(data)
        if chunk%32==0:
            print(f'Native IEC copy: {len(actual)} bytes read and written',flush=True);save()
        if eof:break
    else:raise AssertionError('copy never reached EOF')
    assert bytes(actual)==fixtures['source']
    assert int.from_bytes(client.read_ram(0x3d92,4),'little')==len(actual)
    client.close();client.select(source);assert client.read()==b'';client.close()
    client.open(b'COPY',mode=1,expected=0x11)
    assert client.read_ram(0x3d8f)==bytes([63])
    client.open(b'COPY');reopened=bytearray()
    while True:
        data=client.read();reopened.extend(data)
        if client.read_ram(0x3d8d)==b'\1':break
    client.close();assert bytes(reopened)==fixtures['source']
    (client.work/'copied-native-readback.bin').write_bytes(reopened)
    report['native_copy_bytes']=len(actual);report['native_copy_sha256']=hashlib.sha256(actual).hexdigest();save()
    small=[('zero',0),('cr',0),('user',2),('program',1),('empty',0)]
    small += [(name,0) for name in fixtures if name.startswith('edge')]
    for name,kind in small:
        client.open(name.upper().encode(),kind=kind)
        data=client.read(expected=None)
        state=client.read_ram(0x3d80,0x64)
        report.setdefault('small_files',{})[name]=dict(result=state[14],eof=state[13],data=data.hex())
        save()
        assert state[14]==0 and state[13]==1 and data==fixtures[name],(name,report['small_files'][name])
        client.close()
    # Leave two live owned files for the real application return path.
    client.open(b'SOURCE');client.open(b'COPY')
    client.key(27,expected=None)
    assert client.read_ram(0x3d20)==b'\0' and client.read_ram(0x3d23,2)==b'\0\0'
    assert client.read_ram(0x3dc0)==b'\0' and client.read_ram(0x3dd0)==b'\0'
    assert client.read_ram(0x3de0,4)==bytes(4) and client.read_ram(0x98)==b'\0'
    assert client.read_ram(0x3d0e,3)==bytes([175,251,32])
    report['app_exit_closed_streams_and_released_memory']=True;save()
