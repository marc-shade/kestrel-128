#!/usr/bin/env python3
"""Execute native directory pages against independent CBM sectors and faults."""
import argparse
import hashlib
import json
from pathlib import Path

from ci_native_files import Files,OWNER,HANDLE,DEVICE,FORMAT,MODE,BUFFER,RECORDS,RELEASE,CLOSE
from ci_native_heap import IMAGE

DIRPAGE=0x1c50;PAGE=0x3d97;NEXT=0x3d98;COUNT=0x3d99


def page(f,index=0,fmt=0,device=8,expected=0):
    f.ram[OWNER]=32;f.ram[DEVICE]=device;f.ram[FORMAT]=fmt;f.ram[PAGE]=index
    f.call(DIRPAGE,expected)
    if expected:return []
    assert f.handle()==bytes(4)
    assert f.ram[COUNT] in (0,8)
    records=[]
    for i in range(f.ram[COUNT]):
        record=bytes(f.ram[BUFFER+i*32:BUFFER+(i+1)*32])
        if record[0]:records.append((record[0],record[1],record[2:18].rstrip(b'\xa0'),int.from_bytes(record[18:20],'little')))
    return records


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path);args=parser.parse_args()
    report=dict(passed=False,kernel_sha256=hashlib.sha256(IMAGE.read_bytes()).hexdigest(),cases={})
    cases=report['cases']
    def done(name,f):cases[name]=dict(calls=f.calls,instructions=f.instructions,events=f.io.events)
    try:
        for fmt in range(3):
            files={(8,f'FILE{i:02}'.encode(),(b'S',b'P',b'U')[i%3]):bytes(i*35) for i in range(17)}
            f=Files(files);f.io.formats[8]=fmt;actual=[]
            for index in range(3):
                actual+=page(f,index,fmt)
                assert f.ram[NEXT]==(index+1 if index<2 else 255)
                assert not f.io.handles and f.ram[0x3de0:0x3de4]==bytes(4)
            expected=[(i%3+1,128,f'FILE{i:02}'.encode(),max(1,(i*35+253)//254)) for i in range(17)]
            assert actual==expected
            assert page(f,3,fmt)==[] and f.ram[NEXT]==255 and f.ram[COUNT]==0
            done(f'format-{fmt}-three-pages',f)
        f=Files();assert page(f)==[] and f.ram[COUNT]==8 and f.ram[NEXT]==255
        done('empty-directory',f)
        f=Files({(8,b'SIXTEENCHARACTER',b'S'):b'abc'})
        f.io.edit_blocks=lambda blocks:blocks[18,1].__setitem__(2,0xc1)
        assert page(f)==[(1,0xc0,b'SIXTEENCHARACTER',1)]
        done('locked-and-sixteen-byte-name',f)
        f=Files({(8,b'NOTE',b'S'):b'data'});handle=f.open(owner=33)
        assert page(f)==[(1,128,b'NOTE',1)] and set(f.io.handles)=={122,124}
        f.ram[OWNER]=33;f.ram[HANDLE:HANDLE+4]=handle;f.call(CLOSE)
        assert not f.io.handles;done('shared-command-and-foreign-owner',f)
        for fmt,limit in enumerate((18,18,37)):
            f=Files();page(f,limit,fmt,expected=1)
            assert not f.io.events;done(f'page-bound-{fmt}',f)
        for address,value in ((0,19),(1,0),(1,19)):
            f=Files({(8,b'NOTE',b'S'):b'x'})
            def corrupt(blocks,address=address,value=value):
                blocks[18,1][:2]=b'\x12\x02';blocks[18,1][address]=value
            f.io.edit_blocks=corrupt;page(f,expected=9)
            assert not f.io.handles;done(f'bad-next-{address}-{value}',f)
        f=Files({(8,b'NOTE',b'S'):b'x'})
        f.io.edit_blocks=lambda blocks:blocks[18,1].__setitem__(slice(0,2),b'\x12\x01')
        page(f,17,expected=9)
        assert sum(event[0]=='block-read' for event in f.io.events)==18
        done('cycle-bounded-by-page-capacity',f)
        for lfn in (126,124):
            f=Files();f.io.fail_close=lfn;page(f,expected=0x11)
            assert f.ram[RECORDS]==32 and f.ram[RECORDS+2]==2 and f.ram[RECORDS+3]&4
            before=list(f.io.events);f.call(RELEASE,0x11);assert f.io.events==before
            done(f'uncertain-close-{lfn}-retains-owner',f)
        f=Files();f.io.add(126,9,10);page(f,expected=0x15)
        assert not f.io.events and 126 in f.io.handles;done('foreign-metadata-channel',f)
        for lock in (0x3d11,0x3d91):
            f=Files();f.ram[lock]=1;f.ram[MODE]=0x7a
            before=bytes(f.ram[0x3d80:0x3da0]);f.call(DIRPAGE,7)
            assert bytes(f.ram[0x3d80:0x3da0])==before and not f.io.events
            done(f'reentry-preserves-active-arguments-{lock:04x}',f)
        report['passed']=True
        print(f'PASS: {len(cases)} native directory page/ownership/fault cases',flush=True)
    except BaseException as error:report['error']=str(error);raise
    finally:
        if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
