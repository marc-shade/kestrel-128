"""Independent expectation of the GEM desktop (docs/GEM-DESKTOP.md)."""
import native_aes_scene as scene
import native_forms_scene as forms

MENU = (b'Desk:About Kestrel...|-|Control Panel...;File:Open^O|Show Info^I|-|Delete^D|Format...|New Folder...|-|Close^W;View:Name|Type|Size|Unsorted;'
        b'Options:Preferences...|Save Desktop|Print Screen|Launcher^L')
ICONS = [(2, b'Boot', 0), (6, b'Drive 9', 0), (20, b'Trash', 1)]
DESK, ICON_SELECTED, PAPER, SELECTED = 0x16, 0x61, 0x61, 0x16
ART = [
    [0x7ffffffe, 0x40000002, 0x40000002, 0x47ffffe2, 0x40000002, 0x40000002, 0x40000002, 0x40000002,
     0x40000002, 0x40000002, 0x40000002, 0x4000001a, 0x4000001a, 0x40000002, 0x7ffffffe, 0],
    [0x000ff000, 0x3ffffffc, 0x3ffffffc, 0x10000008] + [0x12492488]*9 + [0x10000008, 0x1ffffff8, 0],
    [0x00ffff00, 0x00800100, 0x00800100, 0x0ffffff0, 0x10000008, 0x10000008, 0x1000003a, 0x10000008,
     0x1ffffff8, 0x10000008, 0x13ffffc8, 0x10000008, 0x1ffffff8, 0x00800100, 0x00ffff00, 0],
]
KIND = (scene.WK['NAME'] | scene.WK['CLOSER'] | scene.WK['FULLER'] | scene.WK['MOVER'] |
        scene.WK['SIZER'] | scene.WK['UP'] | scene.WK['DN'] | scene.WK['VSLIDE'])
TYPES = [b'DEL', b'SEQ', b'PRG', b'USR', b'REL', b'DIR', b'   ']   # 5, 6: USB folder, file


USB_ICON = (10, b'USB', 0)
PRINTER_ICON = (14, b'Printer', 2)     # when IEC device 4 answers


def draw_icons(s, selected=None, color=DESK, usb=False, printer=False):
    shown = list(enumerate(ICONS)) + ([(3, USB_ICON)] if usb else []) + ([(4, PRINTER_ICON)] if printer else [])
    for index, (y, label, art) in shown:
        for g in range(8):
            column, half = g & 3, g >> 2
            rows = [(ART[art][half*8+r] >> (24-8*column)) & 255 for r in range(8)]
            s.glyph(34+column, y+half, rows)
        s.colors(34, y, 38, y+2, ICON_SELECTED if selected == index else color)
        s.rect(31*8, (y+2)*8, 320, (y+2)*8+8, 0)
        s.text(288-len(label)*4, (y+2)*8, label)


def desktop(selected=None, color=DESK, usb=False, printer=False):
    # The 24 bytes after the 1,000 cells keep GEMDESK's start-up fill: the AES
    # repaints only visible desktop cells when the colour changes.
    s = scene.Surface(bytes(8192)+bytes([color])*1000+bytes([DESK])*24)
    draw_icons(s, selected, color, usb, printer)
    return scene.menu_draw(bytes(s.data), MENU)[0]


def name_key(entry):
    """GEMDESK's name order: the $a0 padding sorts below every character."""
    return bytes(0 if c == 0xa0 else c & 0x7f for c in entry['name'].ljust(16, b'\xa0'))


def ordered(entries, view):
    """entries in directory order -> View order (0 name, 1 type, 2 size, 3 unsorted)."""
    keys = [lambda i: (name_key(entries[i]), i),
            lambda i: (entries[i]['type'], name_key(entries[i]), i),
            lambda i: (-entries[i]['blocks'], name_key(entries[i]), i),
            lambda i: i]
    return [entries[i] for i in sorted(range(len(entries)), key=keys[view])]


def printable(raw):
    """GEMDESK's alert text: controls become spaces; [ ] | and DEL become '?'."""
    out = (32 if (c & 0x7f) < 32 else c & 0x7f for c in raw)
    return bytes(0x3f if c in b'[]|\x7f' else c for c in out)


def info_text(entry):
    name = printable(entry['name'].split(b'\xa0')[0])
    return (b'[1][Name: '+name+b'|Type: '+TYPES[entry['type'] if entry['type'] < 5 else 0] +
            b'  Blocks: '+str(entry['blocks']).encode()+b'][OK]')


def row_text(entry):
    name = bytes(32 if c == 0xa0 or (c & 0x7f) < 32 else c & 0x7f for c in entry['name'].ljust(16, b'\xa0'))
    kind = entry['type'] if entry['type'] < 7 else 0
    blocks = b'    ' if kind >= 5 else str(entry['blocks']).rjust(4).encode()   # USB: no size
    return name+b' '+TYPES[kind]+b' '+blocks


def listing(entries, window):
    """content callback: rows from window['top'], selection inverted ('selected',
    the anchor, and 'selection', any further selected rows)."""
    def draw(s, win, g):
        s.clip = (g['wx']*8, g['wy']*8, (g['wx']+g['ww'])*8, (g['wy']+g['wh'])*8)
        for i in range(g['wh']):
            n = window['top']+i
            if n >= len(entries):
                break
            s.text(g['wx']*8, (g['wy']+i)*8, row_text(entries[n]))
            if n == window.get('selected') or n in window.get('selection', ()):
                s.colors(g['wx'], g['wy']+i, g['wx']+g['ww'], g['wy']+i+1, SELECTED)
        s.clip = (0, 0, 320, 200)
    return draw


def slider(count, wh, top):
    size = 255 if count <= wh else wh*255//count
    most = max(0, count-wh)
    return size, (0 if most == 0 else top*255//most)


def picture(windows, entries_of, selected_icon=None, color=DESK, usb=False, printer=False):
    """windows: list (bottom->top) of dicts id/x/y/w/h/title/top/selected/entries."""
    base = desktop(selected_icon, color, usb, printer)
    out = []
    for w in windows:
        g = scene.geometry(dict(kind=KIND, **{k: w[k] for k in ('x', 'y', 'w', 'h')}))
        size, pos = slider(len(entries_of[w['id']]), g['wh'], w['top'])
        out.append(dict(id=w['id'], kind=KIND, x=w['x'], y=w['y'], w=w['w'], h=w['h'],
                        title=w['title'], vsize=size, vpos=pos))
    fills = {w['id']: (0, PAPER) for w in windows}
    def content(s, win, g):
        w = next(v for v in windows if v['id'] == win['id'])
        listing(entries_of[w['id']], w)(s, win, g)
    return scene.windows_draw(out, fills, base=base, content=content, markers=False)


def info_objects(entry, locked=False, value=None, caret=None):
    """GEMDESK's Show Info dialog for an entry; value/caret: the name field."""
    name = entry['name'].split(b'\xa0')[0]
    value = name if value is None else value
    line = (b'Type: '+TYPES[entry['type'] if entry['type'] < 5 else 0]+b'  Blocks: ' +
            str(entry['blocks']).encode())
    f = forms
    return [f.obj(f.TEXT, 2, 1, 20, b'Item Information'),
            f.obj(f.TEXT, 2, 3, 5, b'Name:'),
            f.obj(f.FIELD, 8, 3, 17, field=dict(value=value, caret=len(value) if caret is None else caret)),
            f.obj(f.TEXT, 2, 4, 26, line),
            f.obj(f.CHECK, 2, 5, 12, b'Read-only', state=f.SELECTED if locked else 0),
            f.obj(f.BUTTON, 8, 7, 8, b'OK', flags=f.DEFAULT | f.EXIT),
            f.obj(f.BUTTON, 18, 7, 8, b'Cancel', flags=f.CANCEL | f.EXIT)]


def usb_info_objects(name, line, readonly=False, value=None, caret=None):
    """GEMDESK's USB Show Info dialog (GDUSB): the name field (26 shown of 63), the
    FILE_STAT line ("Folder" / "File, N bytes") and read-only."""
    value = name[:63] if value is None else value
    f = forms
    return [f.obj(f.TEXT, 2, 1, 20, b'Item Information'),
            f.obj(f.FIELD, 2, 3, 26, field=dict(value=value, caret=len(value) if caret is None else caret)),
            f.obj(f.TEXT, 2, 4, 26, line),
            f.obj(f.CHECK, 2, 5, 12, b'Read-only', state=f.DISABLED | (f.SELECTED if readonly else 0)),
            f.obj(f.BUTTON, 8, 7, 8, b'OK', flags=f.DEFAULT | f.EXIT),
            f.obj(f.BUTTON, 18, 7, 8, b'Cancel', flags=f.CANCEL | f.EXIT)]


def usb_info_dialog(before, name, line, focus=1, **kw):
    return forms.draw(before, 30, 10, usb_info_objects(name, line, **kw), focus)


def info_dialog(before, entry, focus=2, **kw):
    return forms.draw(before, 30, 10, info_objects(entry, **kw), focus)


COLORS = [0x16, 0x1c, 0x10]


def prefs_objects(confirm, view, color=DESK, copies=True, overwrites=True):
    f = forms
    radios = [(4, 6, 8, b'Name'), (14, 6, 8, b'Type'), (4, 7, 8, b'Size'), (14, 7, 12, b'Unsorted')]
    return ([f.obj(f.TEXT, 2, 1, 20, b'Preferences'),
             f.obj(f.CHECK, 2, 2, 18, b'Confirm deletes', state=f.SELECTED if confirm else 0),
             f.obj(f.CHECK, 2, 3, 18, b'Confirm copies', state=f.SELECTED if copies else 0),
             f.obj(f.CHECK, 2, 4, 20, b'Confirm overwrites', state=f.SELECTED if overwrites else 0),
             f.obj(f.TEXT, 2, 5, 18, b'Sort windows by:')] +
            [f.obj(f.RADIO, x, y, w, t, flags=0x10, state=f.SELECTED if view == i else 0)
             for i, (x, y, w, t) in enumerate(radios)] +
            [f.obj(f.TEXT, 2, 8, 9, b'Desktop:')] +
            [f.obj(f.RADIO, x, 9, w, t, flags=0x20, state=f.SELECTED if COLORS[i] == color else 0)
             for i, (x, w, t) in enumerate([(4, 7, b'Blue'), (12, 7, b'Grey'), (20, 8, b'Black')])] +
            [f.obj(f.BUTTON, 8, 11, 8, b'OK', flags=f.DEFAULT | f.EXIT),
             f.obj(f.BUTTON, 18, 11, 8, b'Cancel', flags=f.CANCEL | f.EXIT)])


def prefs_dialog(before, confirm, view, focus=1, color=DESK, copies=True, overwrites=True):
    """Centred 30x14: the frame's top row is 5, so object row y is screen row 5+y."""
    return forms.draw(before, 30, 14, prefs_objects(confirm, view, color, copies, overwrites), focus)


def record(confirm, view, color, windows, repeat=0, dclick=2, printer=(4, 7)):
    """The 64-byte desktop record, version 2 (GEMDESK: session and DESKTOP.INF);
    bytes 60 and 61: the printer's device and secondary address."""
    out = bytearray(b'GDS\x02'+bytes([confirm, view, color, repeat, dclick, len(windows)]))
    for w in windows:
        out += bytes([w['dev'], w['fmt'], w['x'], w['y'], w['w'], w['h'], w['top'],
                      255 if w.get('selected') is None else w['selected']])
    out = out.ljust(64, b'\0')
    out[60:62] = bytes(printer)
    return bytes(out)


def format_objects(drive8=True, name=b'', ident=b''):
    f = forms
    return [f.obj(f.TEXT, 2, 1, 20, b'Format disk'),
            f.obj(f.TEXT, 2, 3, 6, b'Drive:'),
            f.obj(f.RADIO, 9, 3, 5, b'8', flags=0x10, state=f.SELECTED if drive8 else 0),
            f.obj(f.RADIO, 15, 3, 5, b'9', flags=0x10, state=0 if drive8 else f.SELECTED),
            f.obj(f.TEXT, 2, 4, 5, b'Name:'),
            f.obj(f.FIELD, 9, 4, 17, field=dict(value=name, caret=len(name))),
            f.obj(f.TEXT, 2, 5, 3, b'ID:'),
            f.obj(f.FIELD, 9, 5, 3, field=dict(value=ident, caret=len(ident))),
            f.obj(f.BUTTON, 6, 8, 10, b'Format', flags=f.DEFAULT | f.EXIT),
            f.obj(f.BUTTON, 18, 8, 8, b'Cancel', flags=f.CANCEL | f.EXIT)]


def format_dialog(before, focus, **kw):
    return forms.draw(before, 30, 11, format_objects(**kw), focus)


def newfolder_objects(name=b''):
    f = forms
    return [f.obj(f.TEXT, 2, 1, 20, b'New Folder'),
            f.obj(f.FIELD, 2, 3, 26, field=dict(value=name, caret=len(name))),
            f.obj(f.BUTTON, 6, 6, 10, b'Create', flags=f.DEFAULT | f.EXIT),
            f.obj(f.BUTTON, 18, 6, 8, b'Cancel', flags=f.CANCEL | f.EXIT)]


def newfolder_dialog(before, focus=1, **kw):
    return forms.draw(before, 30, 9, newfolder_objects(**kw), focus)


REPEAT = [0x80, 0x00, 0x40]          # all keys, cursor keys only, none (KERNAL RPTFLG)


def control_objects(repeat, speed, click=False, printer=4, lower=True, bell=False):
    f = forms
    chosen = REPEAT.index(repeat) if repeat in REPEAT else 1
    return ([f.obj(f.TEXT, 2, 1, 20, b'Control Panel'),
             f.obj(f.TEXT, 2, 3, 12, b'Key repeat:')] +
            [f.obj(f.RADIO, x, 4, w, t, flags=0x10, state=f.SELECTED if chosen == i else 0)
             for i, (x, w, t) in enumerate([(4, 6, b'All'), (11, 9, b'Cursor'), (21, 7, b'None')])] +
            [f.obj(f.TEXT, 2, 5, 26, b'Double-click (slow-fast):')] +
            [f.obj(f.RADIO, 4+5*i, 6, 4, str(i+1).encode(), flags=0x20, state=f.SELECTED if speed == i else 0)
             for i in range(5)] +
            [f.obj(f.CHECK, 2, 7, 12, b'Key click', state=f.SELECTED if click else 0),
             f.obj(f.CHECK, 16, 7, 10, b'Bell', state=f.SELECTED if bell else 0),
             f.obj(f.TEXT, 2, 8, 8, b'Printer:'),
             f.obj(f.RADIO, 11, 8, 4, b'4', flags=0x30, state=f.SELECTED if printer == 4 else 0),
             f.obj(f.RADIO, 16, 8, 4, b'5', flags=0x30, state=f.SELECTED if printer == 5 else 0),
             f.obj(f.CHECK, 2, 9, 16, b'Lowercase', state=f.SELECTED if lower else 0)] +
            [f.obj(f.BUTTON, 6, 10, 8, b'OK', flags=f.DEFAULT | f.EXIT),
             f.obj(f.BUTTON, 18, 10, 8, b'Cancel', flags=f.CANCEL | f.EXIT)])


def control_dialog(before, repeat, speed, focus=2, click=False, printer=4, lower=True, bell=False):
    """Centred 30x13: the frame's top row is 6, so object row y is screen row 6+y."""
    return forms.draw(before, 30, 13, control_objects(repeat, speed, click, printer, lower, bell), focus)


def usb_entries(packets):
    """Directory packets (attribute + name) as GEMDESK records them, in order."""
    return [dict(name=p[1:17], type=5 if p[0] & 0x10 else 6, blocks=0) for p in packets]


def progress(before, title, top):
    """before with a module's progress window on top (title only, at x7 y10
    w26 h3); top, the window that was on top, has its title band unfocused."""
    after = bytearray(scene.windows_draw([dict(id=1, kind=1, x=7, y=10, w=26, h=3, title=title)],
                                         {1: (0, PAPER)}, base=before, markers=False))
    at = 8192+top['y']*40+top['x']
    after[at:at+top['w']] = bytes([PAPER])*top['w']
    return bytes(after)
