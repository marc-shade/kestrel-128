"""Shared picker controls and an independent complete bitmap/console oracle."""
from pathlib import Path
from launcher_scene import pointer_shape
from src.native.graphics.font import font
from native_browser_check import browser_screen,ultimate_browser_screen,screen_bytes
from native_field_check import field_cells
from native_editor_scene import decode

# Half-open cell rectangles; the surface renderer and hit tester use pixels.
CELLS=[(1,2,10,5),(11,2,19,5),(20,2,28,5),(29,2,38,5)]+[(1,y,39,y+1) for y in range(8,16)]+[
    (1,17,10,20),(11,17,19,20),(20,17,28,20),(29,17,38,20),
    (1,20,12,23),(14,20,27,23),(29,20,38,23),(1,10,39,11)]
RECTS=[tuple(n*8 for n in r) for r in CELLS]
LABELS=['REFRESH','DEVICE','FORMAT','DOS 1/2']+['']*8+['PARENT','PATH','PREV','NEXT','CHOOSE','USE HERE','CANCEL','']
KEYS=[ord('R'),ord('D'),ord('F'),9]+[0]*8+[ord('P'),ord('G'),ord('B'),ord('N'),13,ord('S'),27,0]


def enabled(index,*,fmt=0,mode=1,prompt=0,busy=False,count=0,selected=0):
    if index==18:return True
    if busy:return False
    if prompt:return index in (16,19) or index==3 and prompt==3
    if index==19:return False
    if index==17:return mode==2
    if 4<=index<12:return (0 if fmt==3 else selected//8*8)+index-4<count
    if index==16:return count>0
    if index in (1,3,12,13):return (index==1) == (fmt!=3)
    return 0<=index<20


def console(records=(),*,fmt=0,device=9,selected=0,path=b'/',entries=(),base=0,more=False,error=None,
            prompt=0,field='',caret=None,view=None,prompt_device=None,path_error=0,columns=80):
    assert columns in (40,80)
    if fmt==3:
        data=ultimate_browser_screen(columns,path,entries,base,selected,device,more,error,picker=True,
              path_prompt=field if prompt>=2 else None,prompt_device=prompt_device,field_caret=caret,field_view=view,path_error=path_error)
        lines={16:'TAB CONTROLS  ENTER ACTIVATE',17:'G PATH  P PARENT  F1 DOS  F FORMAT'}
        if prompt>=2 and not path_error:lines[21]='ENTER BROWSE F1 DOS CTRL-U CLR ESC'
    else:
        data=browser_screen(columns,records,selected,device,fmt,error,prompt=field if prompt==1 else None,picker=True,field_caret=caret,field_view=view)
        lines={15:'TAB CONTROLS  ENTER ACTIVATE'}
    data=bytearray(data)
    for row,line in lines.items():data[row*columns:(row+1)*columns]=screen_bytes(columns,[line])[:columns]
    return bytes(data)


def surface(records=(),*,focus=4,fmt=0,device=9,selected=0,path=b'/',entries=(),base=0,more=False,error=None,
            mode=1,prompt=0,field='',caret=None,view=None,prompt_device=None,path_error=0,busy=False):
    count=len(entries) if fmt==3 else len(records)
    if fmt==3:body=decode(ultimate_browser_screen(40,path,entries,base,selected,device,more,error,picker=True))
    else:body=decode(browser_screen(40,records,selected,device,fmt,error,picker=True))
    if fmt==3:
        body=bytearray(body)
        def safe(raw):return bytes(c if 32<=c<127 else 46 for c in raw)
        def tail(raw):return raw if len(raw)<=32 else b'<'+raw[-31:]
        rows={3:b'PATH: '+tail(safe(path))}
        rows.update({6+i:(b'>' if i==selected else b' ')+(b'D' if entry[0]&16 else b'F')+b' '+tail(safe(entry[1:])) for i,entry in enumerate(entries)})
        for row,data in rows.items():body[row*40:(row+1)*40]=data.ljust(40,b' ')

    target=bytearray(bytes(8192)+b'\x16'*1024);glyphs=font()
    def text(cx,cy,value):
        if isinstance(value,str):value=value.encode('ascii')
        for x,code in enumerate(value,cx):
            if x>=39:break
            inverse=bool(code&128);code &=127
            if not 32<=code<127:code=ord('.')
            at=cy*320+x*8
            target[at:at+8]=bytes(b^(255 if inverse else 0) for b in glyphs[(code-32)*8:(code-31)*8])
    def colors(rect,color):
        x0,y0,x1,y1=rect
        for y in range(y0,y1):target[8192+y*40+x0:8192+y*40+x1]=bytes([color])*(x1-x0)
    for source,dest in [(0,1),(2,5),(3,6),(4,7)]+[(row+(6 if fmt==3 else 5),8+row) for row in range(8)]+[(19,24)]:
        if prompt and dest>=7:continue
        if busy and 8<=dest<16:
            if fmt!=3 and dest==8:text(1,8,'READING DIRECTORY...')
            continue
        text(1,dest,body[source*40:source*40+38])
    text(1,16,'TAB CONTROLS  ENTER ACTIVATE')
    for index,rect in enumerate(CELLS):
        if not enabled(index,fmt=fmt,mode=mode,prompt=prompt,busy=busy,count=count,selected=selected):continue
        colors(rect,7 if index==focus else 0x16 if 4<=index<12 else 0x1b)
        if 4<=index<12 or index==19:continue
        x0,y0,x1,y1=rect
        for x in range(x0,x1):
            target[y0*320+x*8]=255;target[(y1-1)*320+x*8+7]=255
        for y in range(y0*8,y1*8):
            target[y//8*320+x0*8+y%8]|=128;target[y//8*320+(x1-1)*8+y%8]|=1
        text(x0+1,y0+1,('OK' if index==16 and prompt else LABELS[index])[:x1-x0-2])
    if prompt:
        text(1,7,'DEVICE (8-30):' if prompt==1 else f'PATH ON DOS {prompt_device or device}')
        text(1,14,'INPUT UNAVAILABLE; ESC RETURNS' if prompt>=2 and path_error==2 else
             'ABSOLUTE PATH REQUIRED' if prompt>=2 and path_error else 'ENTER OK  CTRL-U CLEAR  ESC CANCEL')
        text(1,10,decode(field_cells(field,38,caret,view)))
    target[8000:8128]=pointer_shape();target[0x23f8:0x23fa]=bytes([0x7d,0x7e])
    return bytes(target)


def write_assembly(directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    # Keep one pointer implementation. Unique emitted symbols let observers
    # distinguish the two app-bound Editor/Files modules in 64tass listings.
    source=(directory.parent/'input/pointer.inc').read_text()
    (directory/'pointer.inc').write_text('; Generated by native_picker_scene.py from input/pointer.inc.\n'+source.replace('pm_','pgm_'))
