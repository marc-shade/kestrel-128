"""Native Ultimate controls, fixed rectangles and independent bitmap oracle."""
from launcher_scene import pointer_shape
from src.native.graphics.font import font

LABELS=[b'Info',b'Drives',b'Network',b'Clock',b'X',b'Prev',b'Next',b'Refresh',b'Mount',b'Eject',b'Confirm',b'Cancel']
RECTS=[(8,32,80,48),(88,32,160,48),(168,32,240,48),(248,32,312,48),
       (272,8,312,24),(8,160,72,176),(80,160,144,176),(152,160,248,176),
       (8,136,112,152),(120,136,224,152),(40,160,152,184),(168,160,280,184)]
RECTS += [(8,72+16*i,312,88+16*i) for i in range(4)]
LABELS += [b'']*4+[b'Set time',b'Date/time']
RECTS += [(8,136,112,152),(8,72,232,96)]
NOTICES=['Tab controls  Enter activate','Request accepted; R checks inventory',
         'Cancelled','System disk remains protected','Drive is off',
         'Drive unavailable or ambiguous','Inventory changed; choose again',
         'Choose an Ultimate disk image','Close open files to change media',
         'Command failed; R refreshes','Picker cleanup failed; R retries',
         '80-col paused; Esc retries return','Not enough memory for the picker',
         'Enter a valid date/time, 1980-2079','Clock result unknown; R reads again',
         'Clock readback differs; R refreshes','Clock readback confirmed']


def enabled(index,page,mode,count):
    if mode:return index in (10,11) or (mode==2 and index==17)
    if index>=16:return index==16 and page==3
    if index<8:return not (page==3 and index in (5,6))
    return page==1 and (index in (8,9) or 12<=index<12+count)


def drive_body(console_body,selected=0):
    """Render an independently decoded inventory or error in the blue list."""
    import re
    if console_body[2:3] and console_body[2].startswith('UNAVAILABLE:'):
        return console_body[2:],0
    partial=any(row.startswith('PARTIAL REPLY:') for row in console_body)
    result=['SLOT TYPE   IEC   POWER','PARTIAL: A/B CHECKED; OTHERS UNKNOWN' if partial else '']
    count=0
    for row in console_body:
        match=re.fullmatch(r'SLOT (\d)  TYPE ([0-9A-F]{2})  IEC (\d+)  (ON|OFF)',row)
        if match:
            slot,kind,device,power=match.groups()
            result += [f'{">" if int(slot)==selected+1 else " "} {slot}   {kind}     {device}     {power}','']
            count+=1
    return result,count


def surface(body,*,page=0,focus=0,mode=0,count=0,notice=0):
    assert len(body)<=12 and all(len(row)<=36 for row in body)
    data=bytearray(bytes(8192)+b'\x16'*1024);glyphs=font()
    def rect(bounds,ink):
        x0,y0,x1,y1=bounds
        for y in range(y0,y1):
            for x in range(x0,x1):
                at=y//8*320+x//8*8+y%8;mask=128>>(x%8)
                if ink:data[at]|=mask
                else:data[at]&=255^mask
    def text(x,y,label):
        for column,code in enumerate(label):
            assert 32<=code<127
            for dy,bits in enumerate(glyphs[(code-32)*8:][:8]):
                for dx in range(8):
                    if bits&(128>>dx):rect((x+column*8+dx,y+dy,x+column*8+dx+1,y+dy+1),1)
    text(8,8,b'Ultimate II+')
    for index,bounds in enumerate(RECTS):
        if not enabled(index,page,mode,count):continue
        x0,y0,x1,y1=bounds
        for y in range(y0//8,y1//8):
            data[8192+y*40+x0//8:8192+y*40+x1//8]=bytes([7 if index==focus else 0x1b])*((x1-x0)//8)
        if 12<=index<16 or index==17:continue
        rect(bounds,1);rect((x0+1,y0+1,x1-1,y1-1),0)
        label=LABELS[index];text((x0+x1-len(label)*8)//2,(y0+y1-8)//2,label)
    for row,line in enumerate(body):text(16,56+row*8,line.encode('ascii'))
    if mode:text(16,32,b'Set cartridge clock' if mode==2 else b'Change drive media?')
    text(8,192,NOTICES[notice].encode('ascii'))
    data[8000:8128]=pointer_shape();data[9208:9210]=b'\x7d\x7e'
    return bytes(data)


def write_assembly(directory):
    directory.mkdir(parents=True,exist_ok=True)
    lines=['ui_button_count=18','ui_rects:']
    lines+=['        .word '+','.join(map(str,bounds)) for bounds in RECTS]
    for prefix,values in [('ug_labels',[s.decode() for s in LABELS]),('ug_notices',NOTICES)]:
        for index,value in enumerate(values):
            assert len(value)<=38
            lines += [f'{prefix}_{index}: .byte '+','.join(map(str,value.encode()+b'\0'))]
        for suffix,op in [('lo','<'),('hi','>')]:
            lines += [f'{prefix}_{suffix}: .byte '+','.join(f'{op}{prefix}_{i}' for i in range(len(values)))]
    for name,value in [('ug_title',b'Ultimate II+'),('ug_question',b'Change drive media?'),('ut_question',b'Set cartridge clock')]:
        lines += [name+': .byte '+','.join(map(str,value+b'\0'))]
    lines+=['ug_label_x: .word '+','.join(str((x0+x1-len(label)*8)//2) for (x0,y0,x1,y1),label in zip(RECTS,LABELS)),
            'ug_label_y: .byte '+','.join(str((y0+y1-8)//2) for (x0,y0,x1,y1) in RECTS)]
    (directory/'buttons.inc').write_text('\n'.join(lines)+'\n')
