"""Independent full-screen expectations for the native Claude launch page."""
LANDING = [
    'CLAUDE / KESTREL', '', 'CLAUDE CODE ON YOUR C128',
    '80-COLUMN TERMINAL + 40-COLUMN STATUS', '',
    'PRESS RETURN TO OPEN THE MODEM FIRST.',
    'THEN START THE CLAUDE BRIDGE ON LINUX', '',
    'ULTIMATE MODEM: DE00/NMI, 38400 BAUD', '',
    'RETURN: CONNECT', 'F8 OR ESC: DESKTOP', 'RIGHT CLICK: LOCAL CONTROLS / TERMINAL',
    'DURING SESSION: HELP REPAINTS',
    'F8 RETURNS; ESC GOES TO CLAUDE',
]


def landing_screen(columns, error=0):
    lines = LANDING.copy()
    if error:
        lines += ['', '', 'SERIAL PORT BUSY; CLOSE OTHER SESSION' if error == 1 else
                  'SERIAL PORT UNAVAILABLE; CHECK MODEM']
    result = bytearray(b' '*(columns*25))
    for row, line in enumerate(lines):
        for col, byte in enumerate(line.encode()):
            result[row*columns+col] = byte-64 if 64 <= byte < 96 else byte
    return bytes(result)


def waiting_panel(connected=False):
    result = bytearray(b' '*1000)
    for row,line in {0:'CLAUDE / KESTREL',2:'BRIDGE CONNECTED; TERMINAL READY' if connected else 'WAITING FOR THE LINUX BRIDGE',4:'80-COLUMN SCREEN: TERMINAL',
                     6:'HELP: REPAINT / RECONNECT',7:'F8: RETURN TO DESKTOP'}.items():
        data=bytes(code-64 if 64<=code<96 else code for code in line.encode())
        result[row*40:row*40+len(data)]=data
    return bytes(result)


def capture_frame(capture, read, labels, work, label, *, panel=None, live=0, menu=0, top=0, focus=0,
                  view=0,terminal_chars=None):
    """CPU-capture a stationary client-owned panel and all bitmap/font bytes."""
    import hashlib
    from native_capture import wait
    from native_claude_scene import surface
    if panel is None:panel=landing_screen(40)
    expected=dict(live=live,menu=menu,top=top,focus=focus,view=view)
    def settled():
        return (read(0x3d11,2)==b'\0\1' and read(0xd0)==b'\0' and
                read(labels['cg_bitmap'])==b'\1' and not any(read(labels['cg_dirty']+top,16)) and
                read(labels['cg_controls_dirty'])==b'\0' and
                (read(labels['cg_vdc_owned'])==b'\0' or read(labels['vm_pending'])==b'\0'))
    wait(settled,label+' complete companion',120)
    for name,value in expected.items():assert read(labels['cg_'+name])==bytes([value]),(label,name)
    def span(name,address,count,mode=0,bank=0):
        data=b''.join(capture.capture(label+'-'+name+f'-{offset:04x}',address=address+offset,
            count=min(2000,count-offset),mode=mode,bank=bank) for offset in range(0,count,2000))
        (work/(label+'-'+name+'.bin')).write_bytes(data);return data
    assert span('panel',0x400,1000)==panel,(label,'panel backing')
    font_address=read(labels['cg_font_hi'])[0]*256
    retained=read(labels['cg_font_ram'])==b'\1'
    glyphs=span('font',font_address,4096,0 if retained else 1)
    terminal=None;model_record=None
    if retained:
        token=read(labels['tm_cells'],4);assert 1<=token[0]<=32
        record=read(0x3c00+(token[0]-1)*8,8)
        assert record[:2]==bytes([32,1]) and record[3]==16 and record[4:7]==token[1:]
        data=span('terminal',record[2]*256,4048,bank=1)
        terminal=(data[:2000],data[2048:4048])
        if terminal_chars is not None:assert terminal[0]==terminal_chars,(label,'retained terminal')
        model_record=dict(handle=token.hex(),record=record.hex())
    cursor=(read(labels['cg_cursor_row'])[0],read(labels['cg_cursor_col'])[0])
    # The client's landing/waiting panels are entirely white on blue. Host
    # color protocol coverage uses the modeled chips and raw wire fixtures.
    wanted=surface(panel,b'\1'*1000,glyphs,model=retained,terminal=terminal,cursor=cursor,**expected)
    actual=span('surface',0xc000,9216)
    assert actual==wanted,(label,'graphical companion')
    return actual,dict(label=label,expected=expected,panel_hex=panel.hex(),font_address=font_address,
                      surface_sha256=hashlib.sha256(actual).hexdigest(),model=model_record,cursor=cursor)
