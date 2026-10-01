#!/usr/bin/env python3
"""Check complete editor frames and bound the work done by incremental input."""
import argparse
import hashlib
import json
from pathlib import Path

from ci_native_editor_ultimate import UltimateEditor,ROOT
from native_editor_check import document_lines


class ObservedEditor(UltimateEditor):
    def __init__(self,files):
        self.outputs=[0,0];self.clears=[0,0];self.rows=[set(),set()]
        self.reads=0;self.locates=0
        super().__init__(files)
        read,locate=self.symbol('doc_read'),self.symbol('ed_locate')
        original=self.io.stub
        def observe(cpu):
            self.reads+=cpu.pc==read;self.locates+=cpu.pc==locate
            return original(cpu)
        self.io.stub=observe

    def output(self,value):
        screen=self.ram[0xd7]>>7
        self.outputs[screen]+=1;self.clears[screen]+=value==0x93
        if 32<=value<128:self.rows[screen].add(self.row[screen])
        return super().output(value)


def visible_row(data,cursor,view):
    lines=document_lines(data);first=next(i for i,line in enumerate(lines) if line[0]==view)
    for index,(start,body,separator) in enumerate(lines):
        end=start+len(body)
        if start<=cursor<end+len(separator) or not separator and start<=cursor<=end:
            return index-first
    raise AssertionError('cursor has no logical line')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path);args=parser.parse_args()
    images={name:hashlib.sha256((ROOT/'target/native'/name).read_bytes()).hexdigest()
            for name in ('kestrel.prg','editor.prg')}
    report=dict(passed=False,images=images,measurements={},checked_frames=0,field_events=0)
    small=b'ONE "QUOTED" LINE\r\nTWO\nTHREE\r'
    large=(b'0123456789 ABCDEFGHIJKLMNOPQRSTUVWXYZ\r\n'*1800)[:66053]
    edges=b'"'+b'X'*110+b'"\r\n'+b'SHORT\r\n'+b'Y'*90+b'\r\n'+b'LINE\n'*25
    carry=b'LINE\n'*13106+b'ABCD\nTAIL\n'
    assert carry[65535:]==b'TAIL\n'
    try:
        e=ObservedEditor({b'/SMALL':small,b'/LARGE':large,b'/EDGES':edges,b'/CARRY':carry})
        def check(data,**kwargs):
            e.check(data,**kwargs);report['checked_frames']+=2
        def measure(label,action,data,*,kind,cursor=None,**kwargs):
            old=e.contents();old_cursor=e.number('ed_cursor');old_view=e.number('ed_view')
            before=e.instructions,e.reads,e.locates,len(e.ultimate.commands)
            outputs=list(e.outputs);clears=list(e.clears);e.rows=[set(),set()]
            action();check(data,cursor=cursor,**kwargs)
            record=dict(cpu_instructions=e.instructions-before[0],document_reads=e.reads-before[1],
                        locate_calls=e.locates-before[2],chrout_calls=[a-b for a,b in zip(e.outputs,outputs)],
                        screen_clears=[a-b for a,b in zip(e.clears,clears)],
                        written_rows=[sorted(rows) for rows in e.rows])
            if kind=='field':
                assert not record['document_reads'] and not record['locate_calls'],(label,record)
                assert len(e.ultimate.commands)==before[3],label
                assert record['screen_clears']==[0,0] and all(rows<={6} for rows in e.rows),(label,record)
                report['field_events']+=1
            elif kind=='partial':
                allowed={1,2,6,7+visible_row(old,old_cursor,old_view),
                         7+visible_row(data,e.number('ed_cursor'),e.number('ed_view'))}
                assert record['screen_clears']==[0,0] and all(rows<=allowed for rows in e.rows),(label,record,allowed)
                assert sum(record['chrout_calls'])<=600,(label,record)
            else:assert kind=='full' and record['screen_clears']==[1,1],(label,record)
            if label:report['measurements'][label]=record
            return record
        def field(key,data,cursor,**kwargs):
            record=measure('',lambda:e.key(key),data,kind='field',cursor=cursor,**kwargs)
            # 39+79 row cells plus reverse-off/on/off on each focused field.
            # The caret adds six console controls, with no document repaint.
            assert sum(record['chrout_calls'])<=124,record

        e.prompt(0x85,'/SMALL');check(small,cursor=0,dirty=False)
        field(0x86,small,0,mode=2)
        measure('small-field-ten-characters',lambda:e.type('/Usb0/Note'),small,kind='field',cursor=0,mode=2)
        field(27,small,0,mode=0)
        measure('small-insert-character',lambda:e.type('!'),b'!'+small,kind='partial',cursor=1,dirty=True)
        measure('small-backspace-character',lambda:e.key(20),small,kind='partial',cursor=0,dirty=True)
        measure('small-cursor-right',lambda:e.key(0x1d),small,kind='partial',cursor=1)

        # Every intermediate long-path frame must retain the document and erase
        # shortened tails, including the limits of both displays and the field.
        e.prompt(0x88,'000005');check(small,cursor=5)
        field(0x86,small,5,mode=2)
        path='/Usb0/'+('Q"'*60)+'/'+('R'*120)+'/END.TXT'
        assert len(path)==255
        for key in path.encode():field(key,small,5,mode=2)
        assert e.string('ed_field')==path
        field(ord('X'),small,5,mode=2);assert e.string('ed_field')==path
        for _ in range(240):field(20,small,5,mode=2)
        assert e.string('ed_field')==path[:15]
        field(27,small,5,mode=0)
        field(0x88,small,5,mode=3)
        for key in b'FFFFFF':field(key,small,5,mode=3)
        field(13,small,5,status=4,mode=3)
        field(20,small,5,status=0,mode=3)
        field(27,small,5,mode=0)
        field(27,small,5,mode=5);field(ord('N'),small,5,mode=0)

        # Imported CRLF, lone CR/LF, quote controls and clipped long rows remain
        # correct across partial caret moves and complete structural redraws.
        measure('split-crlf-line',lambda:e.key(13),small[:5]+b'\r\n'+small[5:],kind='full',cursor=7)
        measure('join-crlf-line',lambda:e.key(20),small,kind='full',cursor=5)
        measure('cursor-down',lambda:e.key(0x11),small,kind='partial',cursor=22)
        measure('cursor-up',lambda:e.key(0x91),small,kind='partial',cursor=5)
        e.prompt(0x85,'/EDGES',confirm='Y');check(edges,cursor=0,dirty=False)
        measure('horizontal-scroll',lambda:e.prompt(0x88,'000050'),edges,kind='full',cursor=80)
        measure('long-line-insert',lambda:e.type('!'),edges[:80]+b'!'+edges[80:],kind='full',cursor=81)
        changed=edges[:80]+b'!'+edges[80:]
        measure('vertical-scroll',lambda:e.key(0x8a),changed,kind='full',cursor=len(changed))
        measure('return-to-top',lambda:e.key(0x89),changed,kind='full',cursor=0)
        e.key(0x87);e.type('Y');check(b'',cursor=0,dirty=False)

        e.prompt(0x85,'/LARGE');e.prompt(0x88,'010001');check(large,cursor=65537,dirty=False)
        field(0x86,large,65537,mode=2)
        measure('large-field-ten-characters',lambda:e.type('/Usb0/Note'),large,kind='field',cursor=65537,mode=2)
        field(27,large,65537,mode=0)
        inserted=large[:65537]+b'!'+large[65537:]
        record=measure('large-insert-character',lambda:e.type('!'),inserted,kind='partial',cursor=65538,dirty=True)
        assert record['document_reads']<=2,record
        record=measure('large-backspace-character',lambda:e.key(20),large,kind='partial',cursor=65537,dirty=True)
        assert record['document_reads']<=2,record
        record=measure('large-cursor-right',lambda:e.key(0x1d),large,kind='partial',cursor=65538)
        assert record['document_reads']==0,record
        e.prompt(0x86,'/LARGE COPY');check(large,cursor=65538,dirty=False,status=1,name='/LARGE COPY')
        assert e.ultimate.files[b'/LARGE COPY']==large
        e.key(0x87);e.prompt(0x85,'/LARGE COPY');check(large,cursor=0,dirty=False)
        e.key(0x87);e.prompt(0x85,'/CARRY')
        e.prompt(0x88,'00FFFF');e.prompt(0x88,'00FFFC');check(carry,cursor=65532,dirty=False)
        shifted=carry[:65532]+b'!'+carry[65532:]
        measure('line-offset-carry',lambda:e.type('!'),shifted,kind='partial',cursor=65533,dirty=True)
        measure('down-after-offset-carry',lambda:e.key(0x11),shifted,kind='partial',cursor=65539)
        measure('up-before-offset-borrow',lambda:e.key(0x91),shifted,kind='partial',cursor=65533)
        measure('line-offset-borrow',lambda:e.key(20),carry,kind='partial',cursor=65532)
        measure('down-after-offset-borrow',lambda:e.key(0x11),carry,kind='partial',cursor=65537)
        e.exit(dirty=True)
        assert images=={name:hashlib.sha256((ROOT/'target/native'/name).read_bytes()).hexdigest() for name in images}
        report['passed']=True
        print(f"PASS: {report['checked_frames']} complete frames; {report['field_events']} field events without document reads; bounded partial rows and stored bytes",flush=True)
    except BaseException as error:report['error']=str(error);raise
    finally:
        if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
