"""Claude's session frame and retained terminal viewport."""
from pathlib import Path
from launcher_scene import pointer_shape
from src.native.graphics.font import font

CELLS = [(1,1,12,4),(14,1,25,4),(27,1,39,4),(1,21,11,24),(29,21,39,24),(12,21,28,24),(27,0,39,1)]
RECTS = [tuple(n*8 for n in rect) for rect in CELLS]
LABELS = ['Connect','Repaint','Desktop','Prev','Next','Panel','Terminal']
ICONS = [bytes([0,64,96,112,120,112,96,64]),
         bytes([0,60,66,130,158,128,66,60]),
         bytes([0,16,56,124,254,68,84,124]),
         bytes([0,4,12,28,60,28,12,4]),
         bytes([0,32,48,56,60,56,48,32]),
         bytes([0,126,66,90,90,66,126,0]),
         bytes([0,16,48,126,48,16,0,0])]
VIEW_NAMES = ['Panel','Left','Right']
VDC_COLORS = [0,11,6,14,5,13,3,3,2,10,4,4,9,7,15,1]
STATUS = ['Tab selects; Enter activates.', 'Terminal input / Help repaints',
          'Closing... F8 forces return', 'Controls: Tab/Enter; Esc terminal',
          'Display paused; Esc/Desktop retries',
          'Copied to clipboard', 'Pasting; Esc cancels', 'Paste accepted',
          'Clipboard unavailable', 'Paste rejected: unsupported text', 'Paste cancelled',
          'Bridge needs update', 'Paste unconfirmed']


def text(data, x, y, value):
    glyphs = font()
    for col, code in enumerate(value.encode('ascii'), x):
        assert 0 <= col < 40
        at = y*320+col*8
        data[at:at+8] = glyphs[(code-32)*8:(code-31)*8]


def enabled(index, live=0, top=0, model=True, menu=0):
    return index == 2 or index == 0 and (live == 0 or live == 1 and menu and model) or index == 1 and live == 1 or index == 3 and top == 9 or index == 4 and top == 0 or index == 5 and model or index == 6 and live == 1 and menu


def surface(panel=None, colors=None, glyphs=None, *, live=0, menu=0, top=0, focus=0,
            view=0, model=True, terminal=None, cursor=(255,255),recovery=False,clip_status=0):
    """All 9,216 owned bytes, using actual terminal glyphs for raw panel codes."""
    assert top in (0,9) and live in (0,1,2) and view in (0,1,2)
    data = bytearray(bytes(8192)+b'\x16'*1024)
    text(data,1,0,'Kestrel / Claude')
    text(data,1,4,STATUS[4 if recovery else clip_status if menu and clip_status else 3 if live == 1 and menu else live])
    text(data,1,24,'Ctrl+Help / right-click: controls')
    for index, (x0,y0,x1,y1) in enumerate(CELLS):
        color = 7 if index == focus and enabled(index,live,top,model,menu) else 0x1b if enabled(index,live,top,model,menu) else 0xb6
        for y in range(y0,y1):
            data[8192+y*40+x0:8192+y*40+x1] = bytes([color])*(x1-x0)
            if index == 6:continue
            for x in range(x0,x1):
                at = y*320+x*8
                if y == y0:data[at] = 255
                if y == y1-1:data[at+7] = 255
                for line in range(8):
                    if x == x0:data[at+line] |= 128
                    if x == x1-1:data[at+line] |= 1
        label_row = y0 if index == 6 else y0+1
        at = label_row*320+(x0+1)*8
        data[at:at+8] = ICONS[index]
        label = VIEW_NAMES[view]+' '+('10-25' if top else '01-16') if index == 5 else ('Copy' if index==0 else 'Paste') if menu and index<2 else LABELS[index]
        text(data,x0+3,label_row,label)
    if panel is not None:
        assert len(panel) == len(colors) == 1000 and len(glyphs) == 4096
        for row in range(16):
            for col in range(40):
                source = (row+top)*40+col
                at = (row+5)*320+col*8
                if view:
                    assert terminal is not None and len(terminal[0]) == len(terminal[1]) == 2000
                    source = (row+top)*80+col+(40 if view==2 else 0)
                    code,attr = terminal[0][source],terminal[1][source]
                    ink = bytearray(glyphs[code*16:code*16+8])
                    if attr&32:ink[7]=255
                    reverse = bool(attr&64) ^ (cursor==(row+top,col+(40 if view==2 else 0)))
                    data[at:at+8] = bytes(v^(255 if reverse else 0) for v in ink)
                    data[8192+(row+5)*40+col] = VDC_COLORS[attr&15]*16
                else:
                    code = panel[source]
                    data[at:at+8] = glyphs[code*16:code*16+8]
                    data[8192+(row+5)*40+col] = (colors[source]&15)*16+6
    data[8000:8128] = pointer_shape()
    data[9208:9210] = b'\x7d\x7e'
    return bytes(data)


def packed(data):
    result = bytearray()
    index = 0
    while index < len(data):
        end = index+1
        while end < min(index+127,len(data)) and data[end] == data[index]:end += 1
        if end-index >= 3:
            result += bytes([end-index,data[index]])
        else:
            end=index
            while end < min(index+128,len(data)):
                if end+2 < len(data) and data[end] == data[end+1] == data[end+2]:break
                end += 1
            result.append(128+end-index-1)
            result += data[index:end]
        index = end
    return bytes(result)


def write_assembly(directory):
    directory = Path(directory)
    blocks = [('cg_scene',surface())]
    for mode in (0,1):
        blocks.append((f'cg_header_{mode}',surface(live=1,menu=mode)[320:1280]))
    for index, value in enumerate(STATUS):
        data = bytearray(320);text(data,1,0,value)
        blocks.append((f'cg_status_{index}',bytes(data)))
    for view in range(3):
        for page in (0,9):
            full = surface(top=page,view=view)
            blocks.append((f'cg_page_{view}_{page}',full[22*320+12*8:22*320+28*8]))
    lines = ['; Generated by native_claude_scene.py. Runs 1..127; $80|(count-1) introduces literal bytes.']
    for name, data in blocks:
        lines.append(name+':')
        data = packed(data)
        for at in range(0,len(data),24):lines.append(' .byte '+','.join(map(str,data[at:at+24])))
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parent/'apps/claude/host'))
    import petscii
    inverse=petscii.inverse_map()
    table=bytes(ord(inverse[i]) if i in inverse and len(inverse[i])==1 and 32<=ord(inverse[i])<=126 else 63 for i in range(256))
    (directory/'clipboard-ascii.inc').write_text('; Generated from the bridge glyph map; non-ASCII cells become question marks.\ncg_clip_ascii:\n'+''.join(' .byte '+','.join(map(str,table[i:i+16]))+'\n' for i in range(0,256,16)))
    (directory/'scene.inc').write_text('\n'.join(lines)+'\n')
