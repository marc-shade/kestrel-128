"""Shared Files control rectangles and an independent palette-frame renderer."""
from launcher_scene import pointer_shape
from src.native.graphics.font import font

RECTS=[(288,8,312,24),(8,24,64,40),(72,24,136,40),(144,24,192,40),
       (200,24,256,40),(264,24,312,40),(8,144,64,160),(72,144,128,160),
       (136,144,184,160),(192,144,240,160),(248,144,312,160)]
RECTS += [(8,64+8*i,312,72+8*i) for i in range(8)]
RECTS += [(8,24,72,40),(80,24,144,40),(152,24,216,40),(224,24,280,40),
          (192,144,248,160),(256,144,312,160),(8,104,312,120),
          (192,144,248,160),(256,144,312,160)]
RECTS += [(184,8,224,24),(232,8,280,24),(104,8,176,24),(56,8,96,24)]
LABELS=['X','Device','Format','Path','Parent','R','Prev','Next','Open','View','Copy']
LABELS += ['']*8+['Device','Format','Type','Browse','Copy','Back','','OK','Cancel']
LABELS += ['Edit','Paint','New dir','Find']
ROWS={0:[(2,48),(3,56)]+[(5+i,64+8*i) for i in range(8)]+[(19,168),(20,176),(21,184)],
      1:[(2,48),(3,56),(5,80),(7,104),(14,128),(15,136),(16,168),(17,176),(18,184)],
      2:[(0,48),(1,56),(7,104),(9,168)],
      5:[(0,32),(1,40)]+[(3+i,48+8*i) for i in range(16)]+[(21,184)],
      6:[(2,48),(3,56)]+[(6+i,64+8*i) for i in range(8)]+[(4,128),(19,168),(20,176),(21,184)],
      7:[(0,48),(1,64),(2,72),(7,104),(9,168),(10,176),(11,184)]}
TITLES=['Files','Copy a file','Choose device','Directory path','Copy device','File bytes','','New folder','Find filename','Rename','Delete']
ROWS[8]=ROWS[9]=ROWS[10]=ROWS[7]

def enabled(index,view,*,count=0,ultimate=False,phase=0,folder_sent=False,searching=False):
    if view==0:
        if index==31:return True
        if index==30:return ultimate
        if index in (28,29):return count>0
        if index in (3,4):return ultimate
        return index<11 or 11<=index<11+count
    if view==1:return index==24 if phase else index==0 or 19<=index<=25
    if view==5:return index in (0,22)
    if view in (7,8,9,10):return index in (0,27) or not (folder_sent or searching) and index in (25,26)
    return 25<=index<=27 or view==3 and index==19

def label(index,view,phase=0):
    if view in (7,8,9,10) and index in (26,27):
        return {8:'Find',9:'Rename',10:'Delete'}.get(view,'Create') if index==26 else 'Back'
    if view==5 and index==22:return 'Next'
    if view==3 and index==19:return 'DOS'
    if view==1 and index==24 and phase:return 'Cancel'
    return LABELS[index]

def ascii_rows(screen):
    """Decode a text-console expectation into bounded uppercase bitmap labels."""
    assert len(screen)==1000
    def value(code):
        code &= 127
        if code<32:code+=64
        elif code>=64:code+=32
        if 97<=code<=122:code-=32
        return code
    return [bytes(map(value,screen[i:i+40])) for i in range(0,1000,40)]

def focus_console(screen,focus,*,view=0,phase=0):
    from native_browser_check import screen_bytes
    assert len(screen)==2000
    text='File row' if 11<=focus<19 else 'Name / value' if focus==25 else label(focus,view,phase)
    ending=screen_bytes(80,['']*23+['TAB CONTROLS  ENTER ACTIVATE','FOCUS: '+text.upper()])
    return bytes(screen[:23*80])+ending[23*80:]

def browser_surface(records,*,selected=0,device=8,fmt=0,focus=11,error=None):
    from native_browser_check import browser_screen
    body=browser_screen(40,records,selected,device,fmt,error,files_app=True)
    count=min(8,max(0,len(records)-selected//8*8))
    return surface(ascii_rows(body),focus=focus,count=count)

def browser_console(records,*,selected=0,device=8,fmt=0,focus=11,error=None):
    from native_browser_check import browser_screen
    return focus_console(browser_screen(80,records,selected,device,fmt,error,files_app=True),focus)

def copy_surface(source,name,*,focus=25,caret=None,field_view=None,**kwargs):
    from native_files_copy_check import copy_screen
    from native_field_check import viewport
    if caret is None:caret=len(name)
    if field_view is None:field_view=viewport(len(name),caret,32)
    body=copy_screen(40,source,name,caret=caret,view=field_view,graphical=True,**kwargs)
    return surface(ascii_rows(body),view=1,focus=focus,phase=kwargs.get('phase',0),caret=caret-field_view+7)

def copy_console(source,name,*,focus=25,caret=None,field_view=None,**kwargs):
    from native_files_copy_check import copy_screen
    body=copy_screen(80,source,name,caret=caret,view=field_view,graphical_controls=True,**kwargs)
    return focus_console(body,focus,view=1,phase=kwargs.get('phase',0))

def surface(rows,*,view=0,focus=11,count=0,ultimate=False,phase=0,caret=None,help_text=b'Tab controls  Enter activate',folder_sent=False,searching=False):
    assert len(rows)==25 and all(len(row)==40 for row in rows)
    data=bytearray(bytes(8192)+b'\x16'*1024);glyphs=font()
    def rect(bounds,ink):
        x0,y0,x1,y1=bounds
        for y in range(y0,y1):
            for x in range(x0,x1):
                at=y//8*320+x//8*8+y%8;mask=128>>(x%8)
                if ink:data[at]|=mask
                else:data[at]&=255^mask
    def text(x,y,value):
        for column,code in enumerate(value):
            assert 32<=code<127
            for dy,bits in enumerate(glyphs[(code-32)*8:][:8]):
                for dx in range(8):
                    if bits&(128>>dx):rect((x+column*8+dx,y+dy,x+column*8+dx+1,y+dy+1),1)
    title=TITLES[view]
    text(8,8,title.encode())
    for index,bounds in enumerate(RECTS):
        if not enabled(index,view,count=count,ultimate=ultimate,phase=phase,folder_sent=folder_sent,searching=searching):continue
        x0,y0,x1,y1=bounds
        for y in range(y0//8,y1//8):
            data[8192+y*40+x0//8:8192+y*40+x1//8]=bytes([7 if index==focus else 0x1b])*((x1-x0)//8)
        value=label(index,view,phase).encode()
        if not value:continue
        rect(bounds,1);rect((x0+1,y0+1,x1-1,y1-1),0)
        text((x0+x1-len(value)*8)//2,(y0+y1-8)//2,value)
    mapped=6 if view==0 and ultimate else view
    for source,y in ROWS.get(mapped,ROWS[2]):text(8,y,rows[source][:38].rstrip(b' '))
    if caret is not None and focus==25 and not phase:
        rect((8+caret*8,111,16+caret*8,112),1)
    text(8,192,help_text)
    data[8000:8128]=pointer_shape();data[9208:9210]=b'\x7d\x7e'
    return bytes(data)

def write_assembly(directory):
    directory.mkdir(parents=True,exist_ok=True)
    lines=['ui_button_count=32','ui_rects:']
    lines+=['        .word '+','.join(map(str,r)) for r in RECTS]
    strings={'fv_title_'+str(i):s for i,s in enumerate(TITLES)}
    strings.update({'fv_label_'+str(i):s for i,s in enumerate(LABELS)})
    strings.update(fv_next='Next',fv_dos='DOS',fv_cancel='Cancel',fv_help='Tab controls  Enter activate',
                   fv_focus='Focus: ',fv_row_label='File row',fv_field_label='Name / value',
                   fv_device_caption='DEVICE: 8 TO 30',fv_copy_device_caption='DEVICE / DOS CONTEXT',
                   fv_path_caption='DIRECTORY PATH; F1 CHANGES DOS',fv_dos_caption='DOS: ')
    for name,s in strings.items():lines += [name+': .byte '+','.join(map(str,s.encode()+b'\0'))]
    for prefix,count in [('fv_title',len(TITLES)),('fv_label',32)]:
        for suffix,op in [('lo','<'),('hi','>')]:lines += [prefix+'_'+suffix+': .byte '+','.join(op+prefix+'_'+str(i) for i in range(count))]
    for view,values in ROWS.items():lines += ['fv_rows_'+str(view)+': .byte '+','.join(str(n) for pair in values for n in pair)+',255']
    for suffix,op in [('lo','<'),('hi','>')]:lines += ['fv_rows_'+suffix+': .byte '+','.join(op+'fv_rows_'+str(v if v in ROWS else 2) for v in range(len(TITLES)))]
    (directory/'buttons.inc').write_text('\n'.join(lines)+'\n')
