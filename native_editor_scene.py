"""Editor controls and an independent bitmap/console renderer."""
from launcher_scene import pointer_shape
from src.native.graphics.font import font
from native_editor_check import editor_screen, STATUS
from native_field_check import field_cells
from native_browser_check import screen_bytes

RECTS=[(288,8,312,24),(8,24,56,40),(64,24,136,40),(144,24,192,40),
       (200,24,264,40),(272,24,312,40),(0,56,320,184),
       (8,24,56,40),(64,24,120,40),(128,24,192,40),(200,24,264,40),
       (8,96,312,112),(176,144,232,160),(240,144,312,160),(8,144,88,160),
       (240,144,312,160),(144,144,232,160),(8,144,88,160),(96,144,168,160),
       (0,0,0,0),(240,144,312,160),(8,24,88,40),(96,24,168,40),(176,24,264,40),(8,24,88,40),(96,24,168,40),(176,24,264,40),(8,24,88,40),(96,24,168,40),(176,24,264,40)]
LABELS=['X','Open','Save As','Find','Replace','...','','New','Go To','Device','Format',
        '', 'OK','Cancel','Browse','Keep','Discard','One','All','','Cancel','Mark','All','Clear','Copy','Cut','Paste','Undo','Redo','Forget']
KEYS=[27,0x85,0x86,6,18,0,0,0x87,0x88,0x8c,0x8b,13,13,27,9,ord('N'),ord('Y'),ord('O'),ord('A'),0,27,2,1,7,3,24,22,26,25,21]
TITLES=['','Open a file','Save As a new file','Go to byte (hex)','Choose device / DOS',
        'Discard document changes?','Find text','Replace text','Replace with','Choose replacement',
        'File operation','Searching document']

def enabled(index,mode=0,more=False,busy=0):
    if busy:return index==20
    if not mode:return index in (0,5,6) or (27<=index<=29 if more==4 else 24<=index<=26 if more==3 else 21<=index<=23 if more==2 else 7<=index<=10 if more else 1<=index<=4)
    if mode==5:return index in (15,16)
    if mode==9:return index in (13,17,18)
    return index in (11,12,13) or index==14 and mode in (1,2,6,7)

def label(index,mode=0):return 'Case' if index==14 and mode in (6,7) else LABELS[index]

def decode(screen):
    def char(v):
        reverse=v&128;v &=127
        if v<32:v+=64
        elif v>=64:v+=32
        return v|reverse
    return bytes(map(char,screen))

def console(data,cursor,*,focus=6,**kwargs):
    mode=kwargs.get('mode',0);s=editor_screen(80,data,cursor,**kwargs)
    name='Document' if focus==6 else 'Name / value' if focus==11 else label(focus,mode)
    footer=screen_bytes(80,['']*23+['Tab controls  Enter activate  F7 file picker','Focus: '+name])
    return s[:23*80]+footer[23*80:]

def surface(data,cursor,*,focus=6,more=False,busy=0,phase=0,io_bytes=0,search_byte=0,help_text=b'Tab controls  Enter activate',**kwargs):
    mode=kwargs.get('mode',0);status=kwargs.get('status',0);field=kwargs.get('field','')
    plain={**kwargs,'mode':0};plain.pop('field_caret',None);plain.pop('field_view',None)
    body=bytearray(decode(editor_screen(40,data,cursor,**plain)))
    if mode and not status:body[240:280]=b' '*40
    if mode not in (0,5,9) or busy:
        cells=decode(field_cells(field,38,kwargs.get('field_caret'),kwargs.get('field_view')))
        body[960:998]=cells if focus==11 else bytes(c&127 for c in cells)
    if busy==1:body[240:280]=('BYTES: '+f'{io_bytes:06X}').encode().ljust(40,b' ')
    if busy==2:body[240:280]=('BYTE: '+f'{search_byte:06X}').encode().ljust(40,b' ')
    pixels=bytearray(bytes(8192)+b'\x16'*1024);glyphs=font()
    def rect(bounds,ink):
        x0,y0,x1,y1=bounds
        for y in range(y0,y1):
            for x in range(x0,x1):
                at=y//8*320+x//8*8+y%8;mask=128>>(x%8)
                if ink:pixels[at]|=mask
                else:pixels[at]&=255^mask
    def text(x,y,value):
        for col,code in enumerate(value):
            inverted=bool(code&128);code &=127
            assert 32<=code<127
            for dy,bits in enumerate(glyphs[(code-32)*8:][:8]):
                if inverted:bits ^=255
                for dx in range(8):
                    if bits&(128>>dx):rect((x+col*8+dx,y+dy,x+col*8+dx+1,y+dy+1),1)
    def row(source,target,*,start=0,count=40,x=0):text(x,target*8,body[source*40+start:source*40+start+count])
    row(1,1,start=5,count=34,x=8);row(2,5)
    for i in range(7,23):row(i,i)
    view=10 if busy==1 else 11 if busy else mode
    if view:
        rect((0,64,320,168),0)
        title=TITLES[view]
        if busy==1:title=['','Opening file','Saving new file','Verify saved file'][phase]
        text(16,72,title.encode())
    for i,bounds in enumerate(RECTS):
        if i==6 or not enabled(i,mode,more,busy):continue
        x0,y0,x1,y1=bounds
        for y in range(y0//8,y1//8):
            pixels[8192+y*40+x0//8:8192+y*40+x1//8]=bytes([7 if i==focus else 0x1b])*((x1-x0)//8)
        value=label(i,mode).encode()
        if not value:continue
        rect(bounds,1);rect((x0+1,y0+1,x1-1,y1-1),0)
        text((x0+x1-len(value)*8)//2,(y0+y1-8)//2,value)
    if view:
        row(6,15,start=0,count=38,x=8)
        if mode not in (5,9) or busy:row(24,12,start=0,count=38,x=8)
        if mode in (6,7):text(16,88,b'Ignore ASCII case' if kwargs.get('search_case',0) else b'Exact case')
    else:row(6,23)
    text(8,192,help_text)
    pixels[8000:8128]=pointer_shape();pixels[9208:9210]=b'\x7d\x7e'
    return bytes(pixels)

def write_assembly(directory):
    directory.mkdir(parents=True,exist_ok=True)
    lines=[f'ui_button_count={len(RECTS)}','ui_rects:']+['        .word '+','.join(map(str,r)) for r in RECTS]
    lines+=['ui_keys: .byte '+','.join(map(str,KEYS))]
    strings={**{'eg_label_'+str(i):v for i,v in enumerate(LABELS)},**{'eg_title_'+str(i):v for i,v in enumerate(TITLES)}}
    strings.update(eg_case='Case',eg_case_exact='Exact case',eg_case_any='Ignore ASCII case',
                   eg_help='Tab controls  Enter activate',eg_focus_caption='Focus: ',eg_document='Document',eg_field_label='Name / value',
                   eg_console_help='Tab controls  Enter activate  F7 file picker',eg_bytes='BYTES: ',eg_search_byte='BYTE: ',
                   eg_opening='Opening file',eg_saving='Saving new file',eg_verifying='Verify saved file')
    for name,value in strings.items():lines.append(name+': .byte '+','.join(map(str,value.encode()+b'\0')))
    for prefix,count in [('eg_label',len(LABELS)),('eg_title',len(TITLES))]:
        for suffix,op in [('lo','<'),('hi','>')]:lines.append(prefix+'_'+suffix+': .byte '+','.join(op+prefix+'_'+str(i) for i in range(count)))
    (directory/'buttons.inc').write_text('\n'.join(lines)+'\n')
