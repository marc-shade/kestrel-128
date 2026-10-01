"""USB app fixtures and native browser/dispatcher checks for the C128 harness."""
import hashlib

from hwlib import lst_symbol
from native_capture import ROOT,calculator_screen
from native_browser_check import browser_screen
from native_image import seal

CALCULATOR=b'USB CALCULATOR LONG NAME.PRG'
EDITOR=b'TEXT EDITOR.PRG'
PICKER=b'EDPICK.PRG'
SEARCH=b'EDFIND.PRG'
BAD=b'BAD APP.PRG'


def app_fixtures():
    header=bytearray(32);header[:8]=b'NAPP'+bytes([1,1,4,0])
    body=bytes.fromhex('a9778d2f3da9004c3e1c')
    header[8:10]=(32+len(body)).to_bytes(2,'little');header[10]=1;header[12]=32
    header[16:25]=b'REJECT ME'
    bad=bytearray(seal(b'\0\x60'+header+body));bad[16]^=1
    return {CALCULATOR:(ROOT/'target/native/calc.prg').read_bytes(),
            EDITOR:(ROOT/'target/native/editor.prg').read_bytes(),
            PICKER:(ROOT/'target/native/edpick.prg').read_bytes(),
            SEARCH:(ROOT/'target/native/edfind.prg').read_bytes(),BAD:bytes(bad)}


def workflow(client,work,report,records,directory,outputs,save,navigation=None):
    """Start in the boot browser; finish in the USB-loaded editor."""
    details=dict(passed=False,fields=[],calculator_states=[],browser_returns=[],launch_seconds={})
    report['usb_apps']=details
    browser_error=None
    def addr(app,name):return lst_symbol('native/'+app,name)
    def absolute(name):return (directory+b'/'+name).decode()
    def context(label,app,device,fmt):
        raw=client.cpu_read(label+'-app-context',0x3d20,14)
        assert (raw[0],raw[1],raw[3],raw[12],raw[13])==(32,device,2,fmt,8)
        header=client.cpu_read(label+'-app-header',0x3d60,32)
        assert header==(ROOT/'target/native'/f'{app}.prg').read_bytes()[2:34]
        return dict(device=device,format=fmt,boot_device=raw[13],header_sha256=hashlib.sha256(header).hexdigest())
    def field(label,want,device=1,caret=None):
        start=addr('browse','b_usb_length');end=addr('browse','b_usb_path')+256
        raw=client.cpu_read(label+'-field-state',start,end-start)
        length=raw[0];actual_device=raw[addr('browse','b_usb_device')-start]
        at=addr('browse','b_usb_path')-start
        assert length==len(want) and actual_device==device and raw[at:at+length]==want.encode()
        if caret is None:caret=length
        assert raw[1]==caret
        views=list(raw[5:7])
        assert client.cpu_read(label+'-mode',addr('browse','b_prompt'),1)==b'\2'
        if navigation:navigation.frame(label,path_prompt=want,prompt_device=device,directory_prompt=False,
                                       field_caret=caret,field_views=views)
        else:client.frames_equal(label,lambda cols:browser_screen(cols,records,error=browser_error,usb_prompt=want,
                                      usb_device=device,field_caret=caret,field_view=views[int(cols==80)]))
        details['fields'].append(dict(label=label,path=want,device=device,bytes=length,browser_error=browser_error,
                                      caret=caret,views=views));save()
    def browser(label,error=None):
        nonlocal browser_error
        client.selected=0
        record=context(label,'browse',8,0)
        if navigation:navigation.returned(label,error)
        else:client.frames_equal(label,lambda cols:browser_screen(cols,records,error=error))
        browser_error=error
        details['browser_returns'].append(dict(label=label,error=error,**record));save()
    def launch(name,label,device=1):
        if navigation and name in (CALCULATOR,EDITOR,BAD):
            navigation.launch(name,label,device)
            details['launch_seconds'][label]=client.events[-1]['elapsed_seconds'];save()
            return
        client.key(ord('L'));client.key(21,quiet=.1)
        current=client.cpu_read(label+'-initial-context',addr('browse','b_usb_device'),1)[0]
        assert current in (1,2)
        if current!=device:client.key(9,quiet=.1)
        path=absolute(name);client.literal(path,quiet=.1);field(label+'-path',path,device)
        client.key(13,quiet=1)
        details['launch_seconds'][label]=client.events[-1]['elapsed_seconds']
        save()
    def calculator(label,result,history,*,prompt=None,status=None,caret=None):
        start=addr('calc','owner');end=addr('calc','dispbuf')+8
        raw=client.cpu_read(label+'-calculator-state',start,end-start)
        def byte(name):return raw[addr('calc',name)-start]
        at=addr('calc','dispbuf')-start
        assert raw[at:at+8].split(b'\0')[0]==result.encode()
        assert byte('owner')==32 and byte('history_count')==byte('history_head')==len(history)
        assert byte('history_view')==0
        at=addr('calc','history_handle')-start;handle=raw[at:at+4]
        descriptor=client.cpu_read(label+'-history-descriptor',0x3c00+(handle[0]-1)*8,8)
        assert descriptor[:2]==bytes([32,1]) and descriptor[3]==2 and descriptor[4:7]==handle[1:]
        data=(client.capture.capture(label+'-history',bank=1,address=descriptor[2]*256,count=len(history)*16)
              if history else b'')
        if not history:(work/(label+'-history.bin')).write_bytes(data)
        assert data==b''.join(word.encode().ljust(16,b' ') for word in reversed(history))
        views=None
        if prompt is not None:
            field=client.cpu_read(label+'-save-field',addr('calc','save_field'),8)
            value=client.cpu_read(label+'-save-name',addr('calc','save_name'),17)
            if caret is None:caret=len(prompt)
            assert field[0]==len(prompt) and field[1]==caret and value[:len(prompt)+1]==prompt.encode()+b'\0'
            views=list(field[5:7])
        client.frames_equal(label,lambda cols:calculator_screen(cols,result,history,save_prompt=prompt,save_status=status,
            usb=True,save_caret=caret,save_view=None if views is None else views[int(cols==80)]))
        details['calculator_states'].append(dict(label=label,result=result,history=history,prompt=prompt,status=status,
            history_page=descriptor[2],history_sha256=hashlib.sha256(data).hexdigest(),caret=caret,views=views));save()

    if navigation:navigation.check('usb-browser-initial')
    else:client.frames_equal('usb-browser-initial',lambda cols:browser_screen(cols,records))
    client.key(ord('L'));client.key(21,quiet=.1)
    long='/Usb0/'+('Q"'*60)+'/'+('R'*120)+'/END.TXT';assert len(long)==255
    client.literal(long,quiet=.1);field('usb-long-field',long)
    for key in (0x13,0x1d,0x1d,0x1d,0x1d,0x1d,0x1d,4,ord('Z')):client.key(key,quiet=.1)
    long=long[:6]+'Z'+long[7:];field('usb-long-field-middle',long,caret=7)
    client.key(5,quiet=.1)
    client.key(20,quiet=.1);field('usb-shortened-field',long[:-1])
    client.key(21,quiet=.1);field('usb-cleared-field','')
    client.key(27,quiet=.1);browser('usb-cancelled-field')

    launch(CALCULATOR,'usb-calculator',2)
    details['calculator_source']=context('usb-calculator-source','calc',2,3)
    client.heap_equal('usb-calculator-with-workspaces',(127,217,28))
    calculator('usb-calculator-new','0',[])
    client.literal('12+30=');calculator('usb-calculator-result','42',['42'])
    client.literal('SHISTXRY')
    for key in (0x13,0x1d,0x1d,0x1d,0x1d,4,ord('O')):client.key(key,quiet=.1)
    calculator('usb-history-prompt','42',['42'],prompt='HISTORY',caret=5)
    client.key(13,quiet=1);outputs[b'HISTORY']=b'42\r'
    calculator('usb-history-saved','42',['42'],status='HISTORY SAVED AND VERIFIED')
    client.literal('SHISTORY');client.key(13,quiet=1)
    calculator('usb-history-existing','42',['42'],status='FILE EXISTS - CHOOSE ANOTHER NAME')
    client.key(27,quiet=30);browser('usb-browser-after-calculator')
    launch(b'MISSING.PRG','usb-missing')
    browser('usb-browser-after-missing','DISK I/O ERROR')
    sentinel=client.read(0x3d2f);client.put(0x3d2f,b'\xc3')
    try:
        launch(BAD,'usb-corrupt')
        browser('usb-browser-after-corrupt','APPLICATION CHECKSUM FAILED')
        assert client.read(0x3d2f)==b'\xc3','rejected application executed'
    finally:client.put(0x3d2f,sentinel)
    launch(EDITOR,'usb-editor')
    details['editor_source']=context('usb-editor-source','editor',1,3)
    details['passed']=True;save()
