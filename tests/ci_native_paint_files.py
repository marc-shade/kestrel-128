#!/usr/bin/env python3
"""Paint UPNT streams: staged load, verified exclusive save and failure cleanup."""
import argparse
import hashlib
import json
from pathlib import Path

from ci_native_paint_document import Paint
from py65.devices.mpu6502 import MPU
from native_paint_format import encode,decode


def pattern(seed):
    return bytes((i*17+seed+(i//256))&255 for i in range(8000))+bytes(192)+bytes((i*13+seed)&255 for i in range(1000))+b'\x10'*24


class FilePaint(Paint):
    def install(self,data):
        tag=self.ram[self.symbol('pd_handles')];record=0x3c00+(tag-1)*8
        bank,page=self.ram[record+1:record+3]
        self.m.bus.ram[bank][page*256:(page+36)*256]=data
        self.set('pd_dirty',1)

    def name(self,name,*,device=8,fmt=0,kind=0):
        self.set('pf_device',device);self.set('pf_format',fmt);self.set('pf_type',kind)
        self.set('pf_length',len(name));at=self.symbol('pf_name');self.ram[at:at+len(name)]=name

    def operation(self,name,expected=0,hook=None):
        stack=bytes(self.ram[0x100:0x200]);cpu=MPU(memory=self.m.bus,pc=self.symbol(name));cpu.sp=0xe0;cpu.p=0x20;cpu.stPushWord(0xaff)
        try:
            for steps in range(18000000):
                if cpu.pc==0xb00 and cpu.sp==0xe0:break
                if hook:hook(self,cpu)
                if self.io.stub(cpu):continue
                if cpu.pc==0xffe4:
                    cpu.a=self.keys.pop(0) if self.keys else 0;cpu.FlagsNZ(cpu.a);cpu.pc=cpu.stPopWord()+1
                else:cpu.step()
            else:raise AssertionError((name,'operation timed out',hex(cpu.pc)))
            assert self.m.bus.config==0x0e and cpu.p&0x0c==0
            if expected is None:assert cpu.a and cpu.p&1
            else:assert (cpu.a,bool(cpu.p&1))==(expected,bool(expected)),(name,cpu.a,cpu.p,self.value('pf_error'))
            self.events=int.from_bytes(self.ram[0x3d13:0x3d15],'little')
            self.instructions+=steps
            return cpu.a
        finally:self.ram[0x100:0x200]=stack

    def clean(self):
        assert not self.io.handles and self.value('pf_handle')==0
        assert self.ram[self.symbol('pd_handles')+8]==0


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True);args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    report=dict(passed=False,scope='native Paint document/file engine; UI is in progress',cases=[],
        images={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
                (root/'target/native-desktop/paint.prg',root/'target/native/kestrel.prg')})
    def done(name,p):report['cases'].append(dict(name=name,instructions=p.instructions));print('PASS:',name,flush=True)
    try:
        for fmt in (0,1,2):
            p=FilePaint(fmt=fmt);image=pattern(fmt+17);p.install(image);p.name(b'PICTURE',fmt=fmt)
            p.operation('pf_save');p.clean();assert bytes(p.io.files[8,b'PICTURE',b'S'])==encode(image)
            assert not p.value('pd_dirty') and decode(bytes(p.io.files[8,b'PICTURE',b'S']))==image
            p.operation('pf_save',expected=0x11);p.clean();assert p.value('pf_dos')==63
            assert bytes(p.io.files[8,b'PICTURE',b'S'])==encode(image)
            p.install(pattern(111));old=p.document();p.operation('pf_load');p.clean()
            assert p.document()==image and p.document(1)==old and not p.value('pd_dirty')
            p.call('pd_undo');assert p.document()==old and p.value('pd_dirty')
            p.call('pd_undo');assert p.document()==image and not p.value('pd_dirty')
            p.close();done('complete file bytes, exclusive save, staged open and undo/redo on IEC format '+str(fmt),p)
        p=FilePaint();p.install(pattern(55));p.call('pd_snapshot');p.install(pattern(77))
        original,undo=p.document(),p.document(1);valid=encode(pattern(99))
        corrupt=bytearray(valid);corrupt[100]^=1
        badhead=bytearray(valid);badhead[6]=0
        reserved=bytearray(valid);reserved[14]=1
        for label,data,error in [('short-header',valid[:8],0x81),('short-body',valid[:-1],0x81),
            ('extra-data',valid+b'x',0x81),('bad-checksum',bytes(corrupt),0x82),
            ('wrong-dimensions',bytes(badhead),0x81),('reserved-header',bytes(reserved),0x81)]:
            p.io.files[8,b'BAD',b'S']=bytearray(data);p.name(b'BAD');p.operation('pf_load',expected=error)
            p.clean();assert p.document()==original and p.document(1)==undo and p.value('pd_dirty')
            done('rejected '+label+' preserves current image and undo',p)
        p.name(b'CANCEL');p.keys=[27];p.operation('pf_save',expected=0x80)
        assert (8,b'CANCEL',b'S') not in p.io.files;p.clean()
        p.io.files[8,b'LOAD',b'S']=bytearray(valid);p.name(b'LOAD');p.keys=[27];p.operation('pf_load',expected=0x80)
        p.clean();assert p.document()==original and p.document(1)==undo
        done('cancel before file creation and during staged load preserves both images',p)
        p.name(b'PARTIAL');p.io.fail_write=600;p.operation('pf_save',expected=0x11)
        p.clean();assert 0<len(p.io.files[8,b'PARTIAL',b'S'])<9016 and p.document()==original and p.value('pd_dirty')
        p.io.fail_write=None;done('write failure retains partial file without replay or clearing dirty state',p)
        p.name(b'MISMATCH');changed=False
        def corrupt_reopen(p,cpu):
            nonlocal changed
            if cpu.pc==0xffc0 and p.io.filename==b'MISMATCH,S,R' and not changed:
                p.io.files[8,b'MISMATCH',b'S'][64]^=1;changed=True
        p.operation('pf_save',expected=0x83,hook=corrupt_reopen);p.clean()
        assert changed and p.value('pd_dirty');done('reopened byte mismatch cannot be reported as a verified save',p)
        p.close()
        for context in (1,2):
            p=FilePaint(ultimate_files={});image=pattern(context+201);p.install(image)
            p.name(b'/Usb0/Pictures/'+b'P'*235+b'.UPNT',device=context,fmt=3)
            p.operation('pf_save',expected=1);p.clean();assert p.value('pd_dirty')
            name=b'/Usb0/'+b'P'*60+b'/'+b'Q'*60+b'/'+b'R'*60+b'/'+b'S'*61+b'.UPNT'
            assert len(name)==255
            p.name(name,device=context,fmt=3);p.operation('pf_save');p.clean()
            assert bytes(p.ultimate.files[name])==encode(image)
            p.install(pattern(32));old=p.document();p.operation('pf_load');p.clean()
            assert p.document()==image and p.document(1)==old and not p.value('pd_dirty')
            p.close();done('Ultimate context '+str(context)+' full 255-byte path and complete saved/reloaded image',p)
        report['passed']=True
    except BaseException as error:report['error']=repr(error);raise
    finally:args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
