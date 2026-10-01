#!/usr/bin/env python3
"""Use shared field controls in real apps, including a live banked document."""
import argparse
import hashlib
import json
from pathlib import Path

from ci_native_calc import Calculator,ROOT
from ci_native_browser import Browser,expected
from ci_native_file_dialog import DialogEditor
from native_browser_check import browser_screen


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path)
    parser.add_argument('--case',choices=('all','small','large'),default='all');args=parser.parse_args()
    report=dict(passed=False,images={name:hashlib.sha256((ROOT/'target/native'/name).read_bytes()).hexdigest()
        for name in ('kestrel.prg','calc.prg','browse.prg','editor.prg')},cases={})
    try:
        if args.case in ('all','small'):
            calc=Calculator();calc.type('12+30=SABCD')
            calc.key(0x9d);calc.key(0x9d);calc.type('X');calc.key(4)
            calc.check_screens(save_prompt='ABXD')
            assert calc.value('save_cursor')==3
            calc.key(0x13);calc.type('Q');calc.key(5);calc.key(20)
            calc.check_screens(save_prompt='QABX');calc.key(13)
            calc.check_screens(save_status='HISTORY SAVED AND VERIFIED')
            assert bytes(calc.io.files[(8,b'QABX',b'S')])==b'42\r'
            calc.key(27,exited=True)
            report['cases']['calculator-middle-edit-and-verified-save']=True

            browser=Browser({(8,b'NOTE',b'S'):b'NOTE'})
            records=expected(browser.io.files,8);original=browser.original
            browser.type('LABCD');browser.key(0x9d);browser.key(0x9d)
            browser.type('X');browser.key(4)
            path='/Usb0/ABXD';assert browser.value('b_usb_cursor')==9
            for display,columns in enumerate((40,80)):
                want=browser_screen(columns,records,usb_prompt=path,field_caret=browser.value('b_usb_cursor'),
                    field_view=browser.ram[browser.symbol('b_usb_views')+display])
                assert browser.screens[display]==want
            browser.key(0x13);browser.key(0x94);browser.key(20)
            browser.key(5);browser.key(21);browser.type('/NEW')
            assert browser.value('b_usb_length')==4 and browser.value('b_usb_cursor')==4
            browser.key(27);browser.check(records)
            browser.type('D9');browser.key(0x13);browser.type('1');browser.key(4)
            for display,columns in enumerate((40,80)):
                want=browser_screen(columns,records,prompt='1',field_caret=1,
                    field_view=browser.ram[browser.symbol('b_device_views')+display])
                assert browser.screens[display]==want
            browser.key(27);browser.check(records);assert browser.original==original
            browser.key(27,exited=True)
            report['cases']['browser-path-and-device-fields-without-file-io']=True

            editor=DialogEditor({(9,b'NOTE',b'S'):b'KEPT\rDATA'})
            editor.prompt(0x85,'NOTE');editor.key(0x86);editor.type('ABCDE')
            editor.key(0x9d);editor.key(0x9d);editor.type('X');editor.key(4);editor.key(20)
            assert editor.string('ed_field')=='ABCE' and editor.value('ed_field_cursor')==3
            before=bytes(editor.ram[editor.symbol('ed_field_state'):editor.symbol('ed_field_state')+8])
            editor.key(9);assert editor.value('fd_active')
            editor.key(27);assert not editor.value('fd_active')
            assert bytes(editor.ram[editor.symbol('ed_field_state'):editor.symbol('ed_field_state')+8])==before
            editor.check(b'KEPT\rDATA',cursor=0,dirty=False,mode=2)
            editor.key(13);editor.check(b'KEPT\rDATA',status=1,name='ABCE')
            assert bytes(editor.io.files[(9,b'ABCE',b'S')])==b'KEPT\rDATA'
            editor.exit()
            report['cases']['editor-picker-cancel-restores-middle-caret-and-save']=True

            editor=DialogEditor(usb={},directories={b'/':[]},device=1,fmt=3)
            editor.type('UNCHANGED');editor.key(0x8c);editor.type('2')
            editor.check(b'UNCHANGED',dirty=True,mode=4)
            editor.key(0x13);editor.type('1');editor.key(4)
            assert editor.string('ed_field')=='1' and editor.value('ed_field_cursor')==1
            editor.check(b'UNCHANGED',dirty=True,mode=4);editor.key(13)
            editor.check(b'UNCHANGED',dirty=True);assert editor.value('ed_device')==1
            editor.key(0x88);editor.type('a0f');editor.key(0x9d);editor.key(4)
            editor.key(0x13);editor.type('1')
            assert editor.string('ed_field')=='1A0' and editor.value('ed_field_cursor')==1
            editor.check(b'UNCHANGED',dirty=True,mode=3)
            editor.key(27);editor.check(b'UNCHANGED',dirty=True);editor.exit(dirty=True)
            report['cases']['editor-numeric-fields-keep-both-rows-and-document']=True

        if args.case in ('all','large'):
            raw=(b'0123456789 ABCDEFGHIJKLMNOPQRSTUVWXYZ\r\n'*1800)[:66053]
            editor=DialogEditor(usb={b'/LARGE':raw},directories={b'/':[b'\0LARGE']},device=1,fmt=3)
            editor.keep_workspaces();editor.prompt(0x85,'/LARGE')
            editor.prompt(0x88,'010001');editor.type('C12')
            wanted=raw[:65537]+b'C12'+raw[65537:]
            editor.check(wanted,cursor=65540,dirty=True)
            editor.key(0x86);editor.type('/'+('R'*254))
            editor.key(0x13)
            for _ in range(5):editor.key(0x1d)
            editor.key(4);editor.type('Q')
            assert editor.value('ed_field_len')==255 and editor.value('ed_field_cursor')==6
            editor.check(wanted,cursor=65540,dirty=True,mode=2)
            editor.key(21);editor.type('/SAVD');editor.key(0x13)
            for _ in range(4):editor.key(0x1d)
            editor.type('E')
            assert editor.string('ed_field')=='/SAVED' and editor.value('ed_field_cursor')==5
            before=bytes(editor.ram[editor.symbol('ed_field_state'):editor.symbol('ed_field_state')+8])
            editor.key(9);assert editor.value('fd_active') and editor.contents()==wanted
            editor.key(27);assert not editor.value('fd_active')
            assert bytes(editor.ram[editor.symbol('ed_field_state'):editor.symbol('ed_field_state')+8])==before
            editor.check(wanted,cursor=65540,dirty=True,mode=2);editor.check_workspaces()
            editor.key(13);editor.check(wanted,status=1,name='/SAVED',dirty=False)
            assert bytes(editor.ultimate.files[b'/SAVED'])==wanted
            editor.release_workspaces();editor.exit()
            report['cases']['large-document-both-workspaces-long-field-cancel-and-save']=dict(
                bytes=len(wanted),sha256=hashlib.sha256(wanted).hexdigest())
        report['passed']=True
    finally:
        if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(f'PASS: {len(report["cases"])} shared-field application workflows')


if __name__=='__main__':main()
