"""Calculator layout and independent bitmap oracle for the native suite."""
from src.native.graphics.font import font
from launcher_scene import pointer_shape

BUTTONS = []
for row, keys in enumerate(('789/', '456*', '123-', 'C0=+')):
    for col, key in enumerate(keys):
        x, y = 16+col*40, 72+row*24
        BUTTONS.append(((x, y, x+32, y+16), key.encode(), ord(key)))
BUTTONS += [((16,168,64,184), b'Del', 20),
            ((72,168,128,184), b'Save', ord('S')),
            ((192,168,240,184), b'Older', ord('N')),
            ((248,168,296,184), b'Newer', ord('B')),
            ((272,8,304,24), b'X', 27),
            ((64,120,144,144), b'Save', 13),
            ((176,120,256,144), b'Cancel', 27)]


def scene(dialog=False):
    ops = [(0, (8,32,312,188), 1), (0, (9,33,311,187), 0)]
    text = [(16,12,1,b'Calculator')]
    if dialog:
        text += [(24,48,1,b'Save history as a new SEQ file'),
                 (24,72,1,b'Name:'), (24,104,1,b'Tab selects; Enter confirms')]
        ops += [(0,(24,84,296,100),1),(0,(25,85,295,99),0)]
        active = range(21,23)
    else:
        ops += [(0,(16,40,176,64),1),(0,(17,41,175,63),0)]
        text += [(192,48,1,b'History'),(192,60,1,b'Newest first')]
        active = range(21)
    for index in active:
        (x0,y0,x1,y1),label,key = BUTTONS[index]
        ops += [(0,(x0,y0,x1,y1),1),(0,(x0+1,y0+1,x1-1,y1-1),0)]
        text.append(((x0+x1-len(label)*8)//2,(y0+y1-8)//2,1,label))
    return ops, text


def surface(display='0', history=(), view=0, selected=14, *, dialog=False,
            name='', cursor=0, status=0):
    data = bytearray(bytes(8192)+b'\x16'*1000+bytes(24))
    glyphs = font()
    def rect(bounds, pen):
        x0,y0,x1,y1=bounds
        for y in range(max(0,y0),min(200,y1)):
            for x in range(max(0,x0),min(320,x1)):
                at=y//8*320+x//8*8+y%8;mask=128>>(x%8)
                if pen==2:data[at]^=mask
                elif pen:data[at]|=mask
                else:data[at]&=255^mask
    def text(x0,y0,label):
        for col,code in enumerate(label):
            for dy,bits in enumerate(glyphs[(code-32)*8:][:8]):
                for dx in range(8):
                    if bits&(128>>dx):rect((x0+col*8+dx,y0+dy,x0+col*8+dx+1,y0+dy+1),1)
    ops, labels=scene(dialog)
    for _,bounds,pen in ops:rect(bounds,pen)
    for x,y,_,label in labels:text(x,y,label)
    for index in (range(21,23) if dialog else range(21)):
        (x0,y0,x1,y1),_,_=BUTTONS[index]
        for y in range(y0//8,y1//8):
            data[8192+y*40+x0//8:8192+y*40+x1//8]=bytes([7 if index==selected else 0x1b])*((x1-x0)//8)
    if dialog:
        text(32,88,name.encode())
        rect((32+cursor*8,88,40+cursor*8,96),2)
        message=b'Enter saves   Esc cancels'
    else:
        text(24,48,display.encode())
        if history:
            for row,result in enumerate(history[view:view+8]):text(192,76+row*10,result.encode())
        else:text(192,80,b'No results')
        message=[b'Tab/arrows move  Space presses', b'HISTORY SAVED AND VERIFIED',
                 b'DISK ERROR; FILE MAY BE PARTIAL', b'FILE EXISTS - CHOOSE ANOTHER NAME',
                 b'NO RESULTS TO SAVE',b'PATH TOO LONG; SHORTEN NAME',
                 b'INPUT UNAVAILABLE; ESC RETURNS'][status]
    text(8,192,message)
    data[8000:8128]=pointer_shape();data[9208:9210]=b'\x7d\x7e'
    return bytes(data)


def write_assembly(directory):
    directory.mkdir(parents=True,exist_ok=True)
    for dialog, name in ((False,'main'),(True,'save')):
        ops,text=scene(dialog)
        lines=[f'scene_commands_count={len(ops)}','scene_commands:']
        for mode,bounds,pen in ops:
            lines += ['        .sint '+','.join(map(str,bounds)),f'        .byte {mode},{pen}']
        lines += [f'text_commands_count={len(text)}','text_commands:']
        for x,y,pen,label in text:
            lines += [f'        .word {x},{y}',f'        .byte {pen},{len(label)}',
                      '        .byte '+','.join(map(str,label))]
        (directory/(name+'-scene.inc')).write_text('\n'.join(lines)+'\n')
    lines=['ui_button_count=23','ui_rects:']
    lines += ['        .word '+','.join(map(str,bounds)) for bounds,_,_ in BUTTONS]
    lines += ['ui_keys:','        .byte '+','.join(str(key) for _,_,key in BUTTONS)]
    (directory/'buttons.inc').write_text('\n'.join(lines)+'\n')
