"""Independent expected character cells for the native Ultimate panel."""
TITLE = ['ULTIMATE II+', '', 'I INFO  D DRIVES  N NETWORK  T CLOCK', '']
FOOTER = ['', 'R REFRESH   ESC DESKTOP', 'LEFT/RIGHT: TARGET OR INTERFACE']


def absent_body(page):
    headings = [['HARDWARE','UNAVAILABLE','','TARGET 4'],
                ['ULTIMATE DRIVE INVENTORY',''], ['NETWORK INTERFACES: 0'], ['CARTRIDGE RTC','']]
    return headings[page]+['UNAVAILABLE: 11  DOS 00  LINK FE','']


def panel_screen(columns, body, *, page=0, focus=0, mode=0, selected=0, notice=0):
    from native_controls_scene import LABELS, NOTICES
    title = ['ULTIMATE II+', '', 'SET CARTRIDGE CLOCK' if mode==2 else 'CHANGE DRIVE MEDIA?', ''] if mode else TITLE
    footer = (['TAB CHOOSE  ENTER APPLIES', 'ESC CANCELS  CTRL-U CLEARS FIELD'] if mode==2 else
              ['TAB CHOOSE  ENTER CONFIRMS', 'ESC CANCELS'] if mode else
              (['UP/DOWN SELECT  M MOUNT  E EJECT'] if page==1 else [])+FOOTER)
    label = LABELS[focus].decode().upper() if focus<12 or focus>=16 else f'DRIVE {selected+1}'
    lines = title+body+['']+footer+['FOCUS: '+label, NOTICES[notice].upper()]
    assert columns in (40, 80) and len(lines) <= 25
    result = bytearray(b' '*(columns*25))
    for row, line in enumerate(lines):
        assert len(line) < 40, line
        for col, byte in enumerate(line.encode('ascii')):
            result[row*columns+col] = byte-64 if 64 <= byte < 96 else byte
    return bytes(result)
