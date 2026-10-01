"""Observe a shared picker inside its real caller; no direct picker entry calls."""
from ci_native_pointer import Pointer
from ci_native_calc import ROOT
from native_picker_scene import surface,console,RECTS

from native_picker_check import picker_symbol

class Picker:
    frame=Pointer.frame
    move=Pointer.move
    position=Pointer.position

    def __init__(self,app):self.app=app;self.checked=0
    def __getattr__(self,name):return getattr(self.app,name)
    def active(self):
        a=self.app
        return bool(a.value({'editor':'ed_module_kind','files':'fg_kind'}.get(a.image_name,'fd_active'))==
            {'editor':1,'files':2}.get(a.image_name,1) and self.value('fd_active'))
    def symbol(self,name):
        if name.startswith('pm_'):
            if not self.active() or self.app.image_name in ('paint','controls'):return self.app.symbol(name)
            name='pgm_'+name[3:]
        return picker_symbol(self.app.image_name,name)
    def value(self,name):return self.ram[self.symbol(name)]
    def data(self,name,length):return bytes(self.ram[self.symbol(name):self.symbol(name)+length])
    def number(self,name,length=2):return int.from_bytes(self.data(name,length),'little')
    def poll(self,exited=False):return self.app.poll(exited)
    def click(self,index):
        before=self.app.events
        x0,y0,x1,y1=RECTS[index];self.move((x0+x1)//2,(y0+y1)//2)
        self.frame(down=True);self.frame(down=False)
        assert self.app.events==before
        assert int.from_bytes(self.ram[0x3d13:0x3d15],'little')==before
    def preferences(self):return bytes(self.ram[0x3d29:0x3d35])+bytes(self.ram[0x4a00:0x4b00])+bytes(self.ram[0x3e00:0x3f00])
    def check(self,records=(),*,mode=1,prompt=0,field='',selected=0,fmt=0,device=9,focus=None,**kw):
        assert self.active() and self.value('pg_bitmap') and not self.value('pg_error')
        assert self.ram[0x3d29:0x3d2b]==bytes([device,fmt])
        assert self.value('b_prompt')==prompt and self.value('fd_mode')==mode
        assert (self.value('bu_row') if fmt==3 else self.number('b_selected'))==selected
        if focus is None:focus=self.value('pg_focus')
        assert self.value('pg_focus')==focus
        v0=v1=caret=None
        if prompt:
            descriptor=self.data('b_device_state' if prompt==1 else 'b_usb_state',8)
            length,caret=descriptor[:2];ptr=int.from_bytes(descriptor[3:5],'little');v0,v1=descriptor[5:7]
            assert bytes(self.ram[ptr:ptr+length])==field.encode('latin1')
        args=dict(fmt=fmt,device=device,selected=selected,prompt=prompt,field=field,caret=caret,**kw)
        want=surface(records,mode=mode,focus=focus,view=v0,**args);actual=bytes(self.ram[0xc000:0xe400])
        assert actual==want,('picker surface',[(i,a,b) for i,(a,b) in enumerate(zip(actual,want)) if a!=b][:24],args,focus)
        if self.app.image_name in ('controls','paint','files','editor') and self.app.value('vd_phase'):
            from native_vdc_mirror import bitmap,attributes
            assert self.app.value('vd_phase')==2 and self.app.value('vd_live')==1
            assert not self.app.value('vd_fault') and not self.app.value('vm_pending')
            chip=self.app.bus;x,y=self.position
            want=bitmap(actual,chip.size==64,x=x,y=y,pointer=bool(self.app.value('vd_pointer_visible')))
            assert chip.bytes(self.app.value('vd_base')*256,16000)==want,'complete picker VDC bitmap'
            if chip.size==64:assert chip.bytes(0x8000,2000)==attributes(actual),'complete picker VDC attributes'
        else:
            want=console(records,view=v1,**args)
            assert self.screens[1]==want,('picker VDC',[(i,a,b) for i,(a,b) in enumerate(zip(self.screens[1],want)) if a!=b][:24],args)
        self.checked+=1
        return actual
