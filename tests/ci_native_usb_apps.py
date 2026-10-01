#!/usr/bin/env python3
"""Qualify USB launch fields, the real dispatcher, and USB calculator saves."""
import argparse
import hashlib
import json
from pathlib import Path

from ci_native_apps import fixture
from ci_native_browser import Browser,expected
from ci_native_calc import Calculator,ROOT
from ci_native_heap import symbol
from native_browser_check import browser_screen


class DispatchBrowser(Browser):
    def symbol(self,name):
        if self.image_name=='workspace' and name=='cloop':return symbol('native_loop')
        return super().symbol(name)

    def dispatch_return(self):
        # Route the initially loaded browser's return through the actual
        # workspace dispatcher. Subsequent launches use its real JSR frames.
        saved=symbol('native_dispatch')+2
        self.ram[0x1df:0x1e1]=saved.to_bytes(2,'little')
        self.ram[symbol('ui_browser_stage')]=1
        self.ram[symbol('ui_system_device')]=8


def heap_state(app):
    # Observe the live app without invoking a second CPU on its saved stack.
    pages=app.ram[0x3800:0x3a00];handles=app.ram[0x3c00:0x3d00]
    return (pages[:256].count(0),pages[256:].count(0),
            sum(handles[i]==0 and handles[i+4:i+7]!=b'\xff'*3 for i in range(0,256,8)))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path);args=parser.parse_args()
    report=dict(passed=False,images={name:hashlib.sha256((ROOT/'target/native'/name).read_bytes()).hexdigest()
                                   for name in ('kestrel.prg','browse.prg','calc.prg')},cases={},checked_frames=0)
    try:
        b=Browser();records=expected(b.io.files,8)
        cache=b.records();io=list(b.io.events);heap=heap_state(b)
        def field(text,device=1,error=False):
            for bank,columns in enumerate((40,80)):
                assert b.screens[bank]==browser_screen(columns,records,usb_prompt=text,usb_device=device,usb_error=error)
                report['checked_frames']+=1
            assert b.io.events==io and b.records()==cache and heap_state(b)==heap
        b.type('L');field('/Usb0/')
        b.key(21);field('')
        b.type('relative');b.key(13);field('relative',error=True)
        for _ in range(8):b.key(20)
        b.key(13);field('',error=True)
        path='/Usb0/'+('Q"'*60)+'/'+('R'*120)+'/END.TXT';assert len(path)==255
        for i,key in enumerate(path.encode()):b.key(key);field(path[:i+1])
        b.type('X');field(path)
        b.key(9);field(path,device=2)
        for i in range(240):b.key(20);field(path[:254-i],device=2)
        b.key(27);b.check(records);assert b.io.events==io
        b.key(27,exited=True)
        report['cases']['bounded-path-field']=dict(maximum_bytes=255,field_frames=report['checked_frames'],
            no_directory_or_file_io=True,cancel_preserves_selection_and_cache=True,quoted_path=True)

        calc=(ROOT/'target/native/calc.prg').read_bytes();path=b'/Usb0/Tools/Calculator.prg'
        bad=bytearray(fixture(bytes.fromhex('a9778d2f3d60')));bad[16]^=1
        b=DispatchBrowser(ultimate_files={path:calc,b'/Usb0/BAD.PRG':bytes(bad)})
        records=expected(b.io.files,8);b.dispatch_return()
        b.type('LTools/Calculator.prg');b.key(9);b.image_name='calc';b.key(13)
        Calculator.check_screens(b)
        assert (b.ram[0x3d21],b.ram[0x3d2c])==(2,3)
        assert b.ultimate.handles=={1:None,2:None}
        b.type('12+30=SHISTORY');Calculator.check_screens(b,save_prompt='HISTORY');b.key(13)
        Calculator.check_screens(b,save_status='HISTORY SAVED AND VERIFIED')
        assert b.ultimate.files[b'/Usb0/Tools/HISTORY']==b'42\r'
        b.type('SHISTORY');b.key(13);Calculator.check_screens(b,save_status='FILE EXISTS - CHOOSE ANOTHER NAME')
        assert b.ultimate.handles=={1:None,2:None}
        b.image_name='browse';b.key(27);b.check(records)
        assert (b.ram[0x3d21],b.ram[0x3d2c])==(8,0)
        assert heap_state(b)==(175-(ROOT/'target/native/browse.prg').read_bytes()[12],214,30)
        b.type('LMISSING.PRG');b.key(13);b.check(records,error='DISK I/O ERROR')
        assert b.ultimate.handles=={1:None,2:None}
        b.ram[0x3d2f]=0xc3;b.type('LBAD.PRG');b.key(13)
        b.check(records,error='APPLICATION CHECKSUM FAILED');assert b.ram[0x3d2f]==0xc3
        b.image_name='workspace';b.key(27)
        assert heap_state(b)==(175,251,32) and b.ram[0x3d20:0x3d21]==b'\0'
        assert b.ultimate.paths=={1:b'/shell',2:b'/browser'}
        report['cases']['browser-usb-calculator-dispatch']=dict(second_context=True,verified_history_bytes=3,
            boot_browser_restored=True,missing_and_corrupt_images_rejected=True,workspace_return=True)

        c=Calculator(source_path=path);c.type('1+1=')
        c.ultimate.write_limit=1;c.type('SPARTIAL');c.key(13)
        c.check_screens(save_status='DISK ERROR; FILE MAY BE PARTIAL')
        assert len(c.ultimate.files[b'/Usb0/Tools/PARTIAL'])==1
        assert c.ultimate.handles=={1:None,2:None}
        c.ultimate.write_limit=None
        def change_reopen(command,reply):
            if command[2]==1 and command[3:]==b'/Usb0/Tools/DIFFERENT':
                c.ultimate.files[command[3:]][-1]^=1
            return reply
        c.ultimate.inject[2]=change_reopen;c.type('SDIFFERENT');c.key(13)
        c.check_screens(save_status='DISK ERROR; FILE MAY BE PARTIAL')
        c.ultimate.inject.clear()
        c.ultimate.inject[3]=lambda command,reply:[(b'',b'71,CLOSE ERROR')]
        c.type('SUNCERTAIN');c.key(13);assert c.value('save_open')
        c.check_screens(save_status='DISK ERROR; FILE MAY BE PARTIAL')
        count=len(c.ultimate.commands);c.type('S')
        assert [command[1] for command in c.ultimate.commands[count:]]==[3]
        assert c.value('save_open') and not c.value('save_mode')
        c.ultimate.inject.clear();c.type('SRECOVER');c.key(13)
        c.check_screens(save_status='HISTORY SAVED AND VERIFIED')
        assert c.ultimate.files[b'/Usb0/Tools/RECOVER']==b'2\r'
        assert c.ultimate.handles=={1:None,2:None};c.key(27,exited=True)
        report['cases']['calculator-error-recovery']=dict(short_write=True,reopen_comparison=True,
            uncertain_close_retained=True,no_new_open_until_checked_close=True,verified_recovery=True)

        long=b'/'+b'A'*126+b'/'+b'B'*125+b'/X';assert len(long)==255
        c=Calculator(source_path=long);c.type('2+2=');count=len(c.ultimate.commands)
        c.type('STWO');c.key(13);c.check_screens(save_status='PATH TOO LONG; SHORTEN NAME')
        assert len(c.ultimate.commands)==count
        c.type('SZ');c.key(13);c.check_screens(save_status='HISTORY SAVED AND VERIFIED')
        assert c.ultimate.files[long[:-1]+b'Z']==b'4\r';c.key(27,exited=True)
        report['cases']['calculator-255-byte-source']=dict(overlong_output_rejected_before_io=True,
            longest_output_bytes=255,complete_verified_history=True)
        report['passed']=True
        print(f"PASS: {report['checked_frames']} field frames; USB dispatcher, calculator saves and cleanup recovery",flush=True)
    except BaseException as error:report['error']=str(error);raise
    finally:
        if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
