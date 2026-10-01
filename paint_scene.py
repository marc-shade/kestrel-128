"""Paint's full-image viewport, controls and independent VIC bitmap oracle."""
from launcher_scene import pointer_shape
from src.native.graphics.font import font

BUTTONS=[((272,32+i*24,312,48+i*24),label,key) for i,(label,key) in
         enumerate([(b'Pen',ord('P')),(b'Eras',ord('E')),(b'Undo',ord('U')),
                   (b'Clr',ord('C')),(b'Save',ord('S')),(b'Open',ord('O'))])]
BUTTONS.append(((272,8,312,24),b'X',27))
RECTS=[bounds for bounds,_,_ in BUTTONS]
RECTS += [(8+i*16,184,24+i*16,200) for i in range(16)]
RECTS += [(8,32,264,176),(48,96,144,120),(176,96,272,120)]
OPS=[(0,(0,0,320,200),0),(1,(0,0,40,25),0x16),
     (0,(7,31,265,177),1),(0,(8,32,264,176),0)]
TEXT=[(8,8,1,b'Paint')]
for (x0,y0,x1,y1),label,key in BUTTONS:
    OPS += [(0,(x0,y0,x1,y1),1),(0,(x0+1,y0+1,x1-1,y1-1),0)]
    TEXT.append(((x0+x1-len(label)*8)//2,(y0+y1-8)//2,1,label))

MESSAGES=['Arrows move Space draw R refresh','Saved and verified',
          'Opened; Undo restores old image','Cancelled','File exists; choose another name',
          'Invalid picture; picture kept','Checksum wrong; picture kept','Readback differs; file kept',
          'File error; file may be partial','Drawing unavailable',
          'Saving... Esc cancels','Opening... Esc cancels','File picker unavailable',
          'Close failed; S/O/X retries','VDC paused; Esc restores']
STRINGS={'pa_help':MESSAGES[0], 'pa_discard':'Discard','pa_open_label':'Open',
         'pa_close_question':'Discard changes and close?', 'pa_open_question':'Open another picture?',
         'pa_destination_template':'Device:000 D64','pa_formats':'D64 D71 D81 ULT '}
FOCUS=['Pen','Eraser','Undo','Clear','Save','Open','Close']+[f'Color {i:X}' for i in range(16)]+['Canvas','Accept','Keep / Cancel']
CONFIRM_OPS=[(0,(0,0,320,200),0),(1,(0,0,40,25),0x16)]
for bounds in [(24,32,296,136),RECTS[24],RECTS[25]]:
    x0,y0,x1,y1=bounds
    CONFIRM_OPS += [(0,bounds,1),(0,(x0+1,y0+1,x1-1,y1-1),0)]
CONFIRM_TEXT=[(8,8,1,b'Paint'),(32,48,1,b'Unsaved picture'),(208,104,1,b'Keep'),
              (32,152,1,b'Tab choose Enter confirm')]
SAVE_OPS=CONFIRM_OPS+[(0,(24,64,296,88),1),(0,(25,65,295,87),0)]
SAVE_TEXT=[(8,8,1,b'Paint'),(32,40,1,b'Save As (new file)'),(80,104,1,b'Save'),
           (200,104,1,b'Cancel'),(32,152,1,b'Tab browse Enter save Esc cancel')]


def status(x,y,pen,color,dirty):
    return f'X:{x:03d} Y:{y:03d} '+('Pen ' if pen else 'Eras')+f' Ink:{color:X}'+(' *' if dirty else '')


def console(columns,*,x=0,y=0,pen=1,color=1,dirty=False,focus=23,bitmap=True,mode=0,
            action=1,message=0,name=b'',caret=0,view=0,device=8,fmt=0):
    from native_field_check import field_cells
    text='PAINT - 320 X 200 HIRES\r\r'
    if mode==0:
        text+=status(x,y,pen,color,dirty).upper()+'\r\r'
        text+='P PENCIL E ERASER U UNDO C CLEAR\rS SAVE O OPEN ESC CLOSE\r'
        text+='ARROWS MOVE SPACE DRAW +/- INK\rTAB CONTROLS ENTER ACTIVATE\r'
        if not bitmap:text+='\rBITMAP DISPLAY UNAVAILABLE\r'
    elif mode==1:
        text+='UNSAVED PICTURE\r\r'+STRINGS['pa_close_question' if action==1 else 'pa_open_question'].upper()
        text+='\r\rTAB/ARROWS CHOOSE ENTER CONFIRMS\rESC KEEPS PICTURE\r'
    else:
        text+='SAVE AS (NEW FILE)\r'+f'Device:{device:03d} '.upper()+('D64','D71','D81','ULT')[fmt]+'\r\r'
        text+=' '*34+'\r\rTAB BROWSE ENTER SAVE ESC CANCEL\rCTRL-U CLEARS NAME\r'
    text+='\rFOCUS: '+FOCUS[focus].upper()+'\r\r'+MESSAGES[message].upper()
    lines=text.split('\r');assert len(lines)<=25 and all(len(line)<=columns for line in lines)
    lines+=['']*(25-len(lines))
    data=bytearray(ord(c)-64 if 'A'<=c<='Z' else ord(c) for line in lines for c in line.ljust(columns))
    if mode==2:data[5*columns:5*columns+34]=field_cells(name,34,caret,view)
    return bytes(data)


def surface(document,view_x=0,view_y=0,focus=23,x=0,y=0,pen=1,color=1,dirty=False,message=None,
            mode=0,action=1,name=b'',caret=0,field_view=0,device=8,fmt=0):
    assert len(document)==9216 and 0<=view_x<=8 and 0<=view_y<=7
    data=bytearray(bytes(8192)+b'\x16'*1024);glyphs=font()
    def rect(bounds,ink):
        x0,y0,x1,y1=bounds
        for yy in range(y0,y1):
            for xx in range(x0,x1):
                at=yy//8*320+xx//8*8+yy%8;mask=128>>(xx%8)
                if ink:data[at]|=mask
                else:data[at]&=255^mask
    def text(xx,yy,label):
        for col,code in enumerate(label):
            for dy,bits in enumerate(glyphs[(code-32)*8:][:8]):
                for dx in range(8):
                    if bits&(128>>dx):rect((xx+col*8+dx,yy+dy,xx+col*8+dx+1,yy+dy+1),1)
    def commands(ops,labels):
        for kind,bounds,value in ops:
            if kind==0:rect(bounds,value)
        for xx,yy,_,label in labels:text(xx,yy,label)
    if mode:
        commands(CONFIRM_OPS if mode==1 else SAVE_OPS,CONFIRM_TEXT if mode==1 else SAVE_TEXT)
        for index in (24,25):
            x0,y0,x1,y1=RECTS[index]
            for yy in range(y0//8,y1//8):
                data[8192+yy*40+x0//8:8192+yy*40+x1//8]=bytes([7 if index==focus else 0x1b])*((x1-x0)//8)
        if mode==1:
            text(68 if action==1 else 80,104,b'Discard' if action==1 else b'Open')
            text(32,72,STRINGS['pa_close_question' if action==1 else 'pa_open_question'].encode())
        else:
            text(32,48,(f'Device:{device:03d} '+('D64','D71','D81','ULT')[fmt]).encode())
            text(32,72,bytes(c if 32<=c<127 else 46 for c in name[field_view:field_view+32]))
            xx=32+8*(caret-field_view)
            for yy in range(72,80):
                for px in range(xx,xx+8):
                    at=yy//8*320+px//8*8+yy%8;data[at]^=128>>(px%8)
        text(8,176,(message or MESSAGES[0]).encode())
        data[8000:8128]=pointer_shape();data[9208:9210]=b'\x7d\x7e'
        return bytes(data)
    commands(OPS,TEXT)
    for index,((x0,y0,x1,y1),_,_) in enumerate(BUTTONS):
        for yy in range(y0//8,y1//8):
            data[8192+yy*40+x0//8:8192+yy*40+x1//8]=bytes([7 if index==focus else 0x1b])*((x1-x0)//8)
    for index in range(16):
        x0=8+index*16;attribute=(0 if index==1 else 16)|index
        for yy in (23,24):data[8192+yy*40+x0//8:8192+yy*40+x0//8+2]=bytes([attribute])*2
        if focus==7+index:
            rect((x0,184,x0+16,200),1);rect((x0+1,185,x0+15,199),0)
    # Copy each visible pixel and its complete cell color independently.
    for yy in range(144):
        for xx in range(256):
            sx,sy=view_x*8+xx,view_y*8+yy
            ink=document[sy//8*320+sx//8*8+sy%8]&(128>>(sx%8))
            rect((8+xx,32+yy,9+xx,33+yy),bool(ink))
    for yy in range(18):
        for xx in range(32):
            data[8192+(yy+4)*40+xx+1]=document[8192+(view_y+yy)*40+view_x+xx]
    text(8,20,status(x,y,pen,color,dirty).encode())
    rect((8,176,264,184),0)
    text(8,176,(message or MESSAGES[0]).encode())
    data[8000:8128]=pointer_shape();data[9208:9210]=b'\x7d\x7e'
    return bytes(data)


def write_assembly(directory):
    directory.mkdir(parents=True,exist_ok=True)
    for path,ops,labels in [('scene.inc',OPS,TEXT),('confirm-scene.inc',CONFIRM_OPS,CONFIRM_TEXT),
                            ('save-scene.inc',SAVE_OPS,SAVE_TEXT)]:
        lines=[f'scene_commands_count={len(ops)}','scene_commands:']
        for mode,bounds,value in ops:
            lines += ['        .word '+','.join(map(str,bounds)),f'        .byte {mode},{value}']
        lines += [f'text_commands_count={len(labels)}','text_commands:']
        for x,y,pen,label in labels:
            lines += [f'        .word {x},{y}',f'        .byte {pen},{len(label)}',
                      '        .byte '+','.join(map(str,label))]
        (directory/path).write_text('\n'.join(lines)+'\n')
    lines=['ui_button_count=26','ui_rects:']
    lines += ['        .word '+','.join(map(str,bounds)) for bounds in RECTS]
    lines += ['pa_button_keys:','        .byte '+','.join(str(key) for _,_,key in BUTTONS)]
    (directory/'buttons.inc').write_text('\n'.join(lines)+'\n')
    lines=[]
    for key,value in STRINGS.items():
        lines += [key+': .byte '+','.join(map(str,value.encode()+b'\0'))]
    for prefix,values in [('pa_messages',MESSAGES),('pa_focus',FOCUS)]:
        assert all(len(value)<=32 for value in values)
        for index,value in enumerate(values):
            lines += [f'{prefix}_{index}: .byte '+','.join(map(str,value.encode()+b'\0'))]
        for suffix,operator in [('lo','<'),('hi','>')]:
            lines += [f'{prefix}_{suffix}: .byte '+','.join(f'{operator}{prefix}_{index}' for index in range(len(values)))]
    (directory/'messages.inc').write_text('\n'.join(lines)+'\n')
