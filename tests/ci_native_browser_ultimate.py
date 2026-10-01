#!/usr/bin/env python3
"""Execute native USB directory navigation and real application handoffs."""
import argparse
import hashlib
import json
from pathlib import Path

from ci_native_usb_apps import DispatchBrowser,heap_state
from ci_native_calc import Calculator,ROOT
from ci_native_directory_ultimate import DirectoryDOS
from ci_native_apps import fixture
from native_browser_check import ultimate_browser_screen,preview_screen


class Browser(DispatchBrowser):
    def __init__(self,entries=None,files=None,directories=None,*,trailing_paths=False):
        super().__init__(ultimate_files=files or {})
        self.ultimate=DirectoryDOS(entries,files)
        self.ultimate.trailing_paths=trailing_paths
        self.ultimate.directories[b'/']=[b'\x10Usb0']
        self.ultimate.directories.update(directories or {})
        self.m.bus.dos=self.ultimate
        self.frames=0
        self.type('FFF')

    def current_path(self):return bytes(self.ram[0x4a00:0x4a00+self.ram[0x3d2e]])
    def base(self):return int.from_bytes(self.ram[self.symbol('bu_base'):self.symbol('bu_base')+4],'little')
    def page(self):
        handle=bytes(self.ram[self.symbol('b_cache'):self.symbol('b_cache')+4])
        descriptor=bytes(self.ram[0x3c00+(handle[0]-1)*8:0x3c00+handle[0]*8])
        assert descriptor[0:2]==bytes([32,1]) and descriptor[4:7]==handle[1:]
        start=(descriptor[2]+self.value('bu_side'))*256
        memory=self.m.bus.ram[1]
        result=[]
        for i in range(self.value('bu_count')):
            record=memory[start+i*512:start+(i+1)*512]
            size=record[510];assert 1<=size<=255
            result.append(bytes(record[:size+1]))
        return result
    def check(self,path,entries,base=0,selected=0,device=1,more=False,error=None,**kwargs):
        assert self.current_path()==path and self.base()==base
        assert self.value('bu_row')==selected and self.value('bu_more')==int(more)
        assert self.page()==entries and self.ram[0x3d29:0x3d2b]==bytes([device,3])
        assert int.from_bytes(self.ram[0x3d30:0x3d34],'little')==base+selected
        name=entries[selected][1:] if entries else b''
        assert bytes(self.ram[0x3e00:0x3e00+self.ram[0x3d34]])==name
        for screen,columns in zip(self.screens,(40,80)):
            want=ultimate_browser_screen(columns,path,entries,base,selected,device,more,error,**kwargs)
            assert screen==want,('screen',columns,[(i,a,b) for i,(a,b) in enumerate(zip(screen,want)) if a!=b][:12])
            self.frames+=1
    def path(self,path):
        self.type('G');self.key(21);self.type(path.decode('ascii'));self.key(13)
    def queue(self,keys):
        self.observation_target=self.events+len(keys);self.observation_done=False
        self.keys.extend(keys);self.loop();assert self.observation_done
        self.events+=len(keys)
        assert int.from_bytes(self.ram[0x3d13:0x3d15],'little')==self.events


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path);args=parser.parse_args()
    report=dict(passed=False,images={name:hashlib.sha256((ROOT/'target/native'/name).read_bytes()).hexdigest()
                                   for name in ('kestrel.prg','browse.prg','calc.prg')},cases={},frames=0)
    def done(label,b):
        report['cases'][label]=dict(events=b.events,instructions=b.instructions,frames=b.frames,
            directory_reads=sum(cmd[1]==0x14 for cmd in b.ultimate.commands),aborts=b.ultimate.cancel_attempts)
        report['frames']+=b.frames
    try:
        entries=[b'\x20'+f'FILE {i:04d}'.encode() for i in range(300)]
        b=Browser(entries);b.check(b'/',[b'\x10Usb0'])
        b.key(13);b.check(b'/Usb0',entries[:8],more=True)
        for base in range(8,296,8):
            b.type('N');b.check(b'/Usb0',entries[base:base+8],base=base,more=True)
        b.type('N');b.check(b'/Usb0',entries[296:],base=296)
        assert b.ultimate.paths=={1:b'/shell',2:b'/browser'}
        assert sum(cmd[1]==0x14 for cmd in b.ultimate.commands)==2
        b.type('B');b.check(b'/Usb0',entries[288:296],base=288,more=True)
        b.type('FFFF');b.check(b'/Usb0',entries[288:296],base=288,more=True)
        b.type('P');b.check(b'/',[b'\x10Usb0']);b.key(27,exited=True)
        done('300-entries-forward-back-parent',b)

        names=[b'\x20'+b'Q"'*127+b'Z',b'\x20'+b'A'*40+b' FIRST',b'\x20'+b'A'*40+b' SECOND']
        files={b'/Usb0/'+names[1][1:]:b'FIRST FILE',b'/Usb0/'+names[2][1:]:b'SECOND FILE'}
        b=Browser(names,files);b.key(13);b.check(b'/Usb0',names)
        before=len(b.ultimate.commands);b.key(13)
        b.check(b'/Usb0',names,error='PATH TOO LONG; CANNOT OPEN THIS NAME')
        assert len(b.ultimate.commands)==before
        b.key(0x11);b.key(0x11);b.type('I')
        assert bytes(b.ram[b.symbol('b_view_data'):b.symbol('b_view_data')+b.value('b_view_count')])==b'SECOND FILE'
        b.key(27);b.check(b'/Usb0',names,selected=2)
        assert b.ultimate.paths=={1:b'/shell',2:b'/browser'}
        b.key(27,exited=True);done('complete-names-and-exact-file-selection',b)

        b=Browser(entries,directories={b'/Usb0/EMPTY':[]})
        b.key(13);b.type('N');old=b.page()
        b.queue([ord('N'),27]);b.check(b'/Usb0',old,base=8,more=True,error='SCAN CANCELLED; PREVIOUS PAGE RETAINED')
        assert b.ultimate.paths=={1:b'/shell',2:b'/browser'}
        b.type('N');b.check(b'/Usb0',entries[16:24],base=16,more=True)
        b.path(b'/Usb0/MISSING');b.check(b'/Usb0',entries[16:24],base=16,more=True,error='DISK I/O ERROR')
        b.path(b'/Usb0/EMPTY');b.check(b'/Usb0/EMPTY',[])
        b.type('G');b.check(b'/Usb0/EMPTY',[],path_prompt='/Usb0/EMPTY')
        b.key(27);b.check(b'/Usb0/EMPTY',[])
        b.type('P');b.check(b'/Usb0',entries[:8],more=True)
        b.path(b'/Usb0/EMPTY/../');b.check(b'/Usb0',entries[:8],more=True)
        b.key(9);b.check(b'/Usb0',entries[:8],device=2,more=True)
        b.key(27,exited=True);done('cancel-failure-empty-and-context',b)

        b=Browser(entries);b.key(13)
        b.queue([ord('N'),ord('N')]);b.check(b'/Usb0',entries[16:24],base=16,more=True)
        assert not b.value('bu_pending_key')
        b.ultimate.directories[b'/Usb0']=entries[:3]
        b.type('B');b.check(b'/Usb0',entries[:3])
        b.key(0x11);b.ultimate.directories[b'/Usb0']=entries[2:3]
        b.type('FFFF');b.check(b'/Usb0',entries[2:3])
        b.ultimate.directories[b'/Usb0']=[]
        b.type('FFFF');b.check(b'/Usb0',[])
        b.key(27,exited=True);done('queued-input-and-stale-selection',b)

        real_shape=[b'\x10CHILD',b'\x20NOTE']
        b=Browser(real_shape,{b'/Usb0/NOTE':b'CANONICAL'},directories={b'/Usb0/CHILD':[]},trailing_paths=True)
        b.key(13);b.check(b'/Usb0/',real_shape)
        b.key(13);b.check(b'/Usb0/CHILD/',[])
        b.type('P');b.check(b'/Usb0/',real_shape)
        b.key(0x11);b.type('I')
        assert bytes(b.ram[b.symbol('b_view_data'):b.symbol('b_view_data')+b.value('b_view_count')])==b'CANONICAL'
        b.key(27);b.check(b'/Usb0/',real_shape,selected=1)
        b.path(b'/Usb0/CHILD/../');b.check(b'/Usb0/',real_shape)
        b.key(27,exited=True)
        assert b.ultimate.paths=={1:b'/shell',2:b'/browser'}
        done('firmware-canonical-trailing-slashes',b)

        calc=(ROOT/'target/native/calc.prg').read_bytes()
        bad=bytearray(fixture(bytes.fromhex('a9778d2f3d60')));bad[16]^=1
        folder=b'/Usb0/Apps "Test"'
        apps=[b'\x20'+f'ROW {i:02d}'.encode() for i in range(9)]
        calc_name=b'CALCULATOR LONG NAME.PRG'
        apps += [b'\x20'+calc_name,b'\x20BAD.PRG',b'\x20README']
        files={folder+b'/README':b'NOT AN APP',folder+b'/'+calc_name:calc,folder+b'/BAD.PRG':bytes(bad)}
        b=Browser(files=files,directories={folder:apps});b.dispatch_return();b.path(folder)
        b.type('N');b.key(0x11);b.image_name='calc';b.key(13)
        Calculator.check_screens(b);assert (b.ram[0x3d21],b.ram[0x3d2c])==(1,3)
        b.image_name='browse';b.key(27);b.check(folder,apps[8:],base=8,selected=1)
        b.image_name='calc';b.key(13)
        b.type('6*7=SHISTORY');b.key(13);Calculator.check_screens(b,save_status='HISTORY SAVED AND VERIFIED')
        assert b.ultimate.files[folder+b'/HISTORY']==b'42\r'
        changed=b.ultimate.directories[folder]
        assert len(changed)==13 and changed[1]==b'\x20'+calc_name
        b.image_name='browse';b.key(27);b.check(folder,changed[:8],selected=1,more=True)
        b.ram[0x3d2f]=0xc3;b.key(0x91);b.key(13)
        b.check(folder,changed[:8],more=True,error='APPLICATION CHECKSUM FAILED');assert b.ram[0x3d2f]==0xc3
        b.image_name='workspace';b.key(27)
        assert heap_state(b)==(175,251,32) and b.ultimate.paths=={1:b'/shell',2:b'/browser'}
        done('directory-to-app-save-and-return',b)

        report['passed']=True
        print(f"PASS: {len(report['cases'])} native USB browser workflows; {report['frames']} complete frames",flush=True)
    except BaseException as error:report['error']=str(error);raise
    finally:
        if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
