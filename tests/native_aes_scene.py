"""Independent expectation of an AES alert drawn over a 9216-byte surface.

Layout follows docs/NATIVE-AES.md#alerts: cells on the 40x25 grid, one-cell
margin, optional 16-pixel icon plus a gap column, lines, a blank row, a
two-row button bar and a bottom margin; buttons are label+2 cells wide, one
cell apart, centred in the inner width."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.native.graphics.font import font  # noqa: E402

PAPER, FOCUS = 0x61, 0x07
ICONS = {
    1: [0x0000, 0x03c0, 0x03c0, 0x03c0, 0x03c0, 0x03c0, 0x03c0, 0x03c0,
        0x0180, 0x0180, 0x0000, 0x0000, 0x03c0, 0x03c0, 0x0000, 0x0000],
    2: [0x07e0, 0x0ff0, 0x1c38, 0x1818, 0x0038, 0x0070, 0x00e0, 0x01c0,
        0x0180, 0x0180, 0x0000, 0x0000, 0x0180, 0x0180, 0x0000, 0x0000],
    3: [0x07e0, 0x0ff0, 0x1ff8, 0x3ffc, 0x7ffe, 0xffff, 0xffff, 0xc003,
        0xc003, 0xffff, 0xffff, 0x7ffe, 0x3ffc, 0x1ff8, 0x0ff0, 0x07e0],
}


def parse(text):
    """Return (icon, lines, buttons) for a valid string, else None."""
    if not (text.startswith(b'[') and len(text) > 3 and text[2:3] == b']'):
        return None
    if not 0x30 <= text[1] <= 0x33:
        return None
    rest = text[3:]
    parts = []
    for _ in range(2):
        if not rest.startswith(b'[') or b']' not in rest:
            return None
        end = rest.index(b']')
        parts.append(rest[1:end]); rest = rest[end+1:]
    if rest:
        return None
    lines, buttons = parts[0].split(b'|'), parts[1].split(b'|')
    if len(lines) > 5 or any(len(l) > 30 for l in lines):
        return None
    if not 1 <= len(buttons) <= 3 or any(not 1 <= len(b) <= 10 for b in buttons):
        return None
    if any(not 32 <= c < 127 for c in parts[0]+parts[1] if c != 0x7c):
        return None
    return text[1]-0x30, lines, buttons


def layout(icon, lines, buttons):
    tw = max(len(l) for l in lines)
    inner = tw + (3 if icon else 0)
    bw = sum(len(b)+2 for b in buttons) + len(buttons)-1
    inner = max(inner, bw)
    w, h = inner+2, len(lines)+5
    if w > 38 or w*h > 250:
        return None
    x, y = (40-w)//2, (25-h)//2
    bx = x+1+(inner-bw)//2
    positions = []
    for b in buttons:
        positions.append(bx); bx += len(b)+3
    return dict(x=x, y=y, w=w, h=h, button_y=y+len(lines)+2, button_x=positions)


class Surface:
    def __init__(self, data):
        self.data = bytearray(data)
        self.glyphs = font()

    clip = (0, 0, 320, 200)

    def rect(self, x0, y0, x1, y1, ink):
        cx0, cy0, cx1, cy1 = self.clip
        for y in range(max(cy0, y0), min(cy1, y1)):
            for x in range(max(cx0, x0), min(cx1, x1)):
                at = y//8*320+x//8*8+y % 8; mask = 128 >> (x % 8)
                if ink: self.data[at] |= mask
                else: self.data[at] &= 255 ^ mask

    def colors(self, x0, y0, x1, y1, value):
        for row in range(y0, y1):
            self.data[8192+row*40+x0:8192+row*40+x1] = bytes([value])*(x1-x0)

    def line_box(self, x0, y0, x1, y1):
        """A one-pixel frame: filled with ink, hollowed one pixel in."""
        self.rect(x0, y0, x1, y1, 1); self.rect(x0+1, y0+1, x1-1, y1-1, 0)

    def text(self, x, y, value):
        for column, code in enumerate(value):
            for dy, bits in enumerate(self.glyphs[(code-32)*8:][:8]):
                for dx in range(8):
                    if bits & (128 >> dx):
                        self.rect(x+column*8+dx, y+dy, x+column*8+dx+1, y+dy+1, 1)

    def glyph(self, cx, cy, rows):
        for dy, bits in enumerate(rows):
            self.data[cy*320+cx*8+dy] = bits


def draw(before, text, default, focus):
    parsed = parse(text)
    assert parsed is not None, text
    icon, lines, buttons = parsed
    geo = layout(icon, lines, buttons)
    assert geo is not None
    s = Surface(before)
    x, y, w, h = geo['x'], geo['y'], geo['w'], geo['h']
    X0, Y0, X1, Y1 = x*8, y*8, (x+w)*8, (y+h)*8
    s.rect(X0, Y0, X1, Y1, 0)
    s.line_box(X0+1, Y0+1, X1-1, Y1-1)
    s.rect(X0+2, Y0+2, X1-2, Y1-2, 0)
    s.line_box(X0+3, Y0+3, X1-3, Y1-3)
    s.colors(x, y, x+w, y+h, PAPER)
    if icon:
        rows = ICONS[icon]
        for g in range(4):
            half, column = g >> 1, g & 1
            bits = [(rows[half*8+r] >> (8 if column == 0 else 0)) & 255 for r in range(8)]
            s.glyph(x+1+column, y+1+half, bits)
    for i, line in enumerate(lines):
        if line:
            s.text((x+1+(3 if icon else 0))*8, (y+1+i)*8, line)
    by = geo['button_y']
    for i, (label, bx) in enumerate(zip(buttons, geo['button_x'])):
        b0, b1 = bx*8, (bx+len(label)+2)*8
        s.rect(b0, by*8, b1, by*8+16, 0)
        s.line_box(b0, by*8, b1, by*8+16)
        if default == i+1:
            s.line_box(b0+1, by*8+1, b1-1, by*8+15)
        s.text(b0+8, by*8+4, label)
        s.colors(bx, by, bx+len(label)+2, by+2, FOCUS if focus == i+1 else PAPER)
    return bytes(s.data), geo


def dirty_rows(first, count):
    mask = bytearray(4)
    for row in range(first, first+count):
        mask[row >> 3] |= 1 << (row & 7)
    return bytes(mask)


# ---- menu bar ----------------------------------------------------------------
GREY = 0xc1
CHECK = [0x00, 0x01, 0x03, 0x06, 0x8c, 0xd8, 0x70, 0x20]


def menu_parse(spec):
    """[(title, [(text, key, separator)])] or None, per docs/NATIVE-AES.md#menus."""
    if not spec:
        return []
    menus = []
    for part in spec.split(b';'):
        if part.count(b':') != 1:
            return None
        title, items = part.split(b':')
        if not 1 <= len(title) <= 18:
            return None
        parsed = []
        for item in items.split(b'|'):
            if item == b'-':
                parsed.append((b'', 0, True)); continue
            key = 0
            if len(item) >= 3 and item[-2:-1] == b'^':
                letter = item[-1] & 0xdf
                if not 0x41 <= letter <= 0x5a:
                    return None
                key, item = letter & 0x1f, item[:-2]
            if not 1 <= len(item) <= 16:
                return None
            parsed.append((item, key, False))
        if len(parsed) > 12:
            return None
        menus.append((title, parsed))
    if not 1 <= len(menus) <= 8:
        return None
    return menus


def menu_layout(menus):
    xs, x = [], 1
    for title, _ in menus:
        xs.append(x); x += len(title)+1
        if x >= 41:
            return None
    drops = []
    for (title, items), tx in zip(menus, xs):
        w = max(len(t) for t, _, _ in items)+3+(3 if any(k for _, k, _ in items) else 0)
        dx = tx-1
        if dx+w > 40:
            dx = 40-w
        if w > 38 or w*(len(items)+2) > 250:
            return None
        drops.append(dict(x=dx, w=w, h=len(items)))
    return xs, drops


def menu_draw(before, spec, *, open_title=None, hover=None, flags=None):
    """Surface after installing spec, optionally with a drop-down open."""
    menus = menu_parse(spec)
    xs, drops = menu_layout(menus)
    flags = flags or {}
    s = Surface(before)
    s.rect(0, 0, 320, 8, 0)
    for (title, _), x in zip(menus, xs):
        s.text(x*8, 0, title)
    s.colors(0, 0, 40, 1, PAPER)
    if open_title is not None:
        title, items = menus[open_title]
        tx = xs[open_title]
        s.colors(tx, 0, tx+len(title), 1, FOCUS)
        d = drops[open_title]
        dx, w, h = d['x'], d['w'], d['h']
        X0, Y0, X1, Y1 = dx*8, 8, (dx+w)*8, (h+3)*8
        s.rect(X0, Y0, X1, Y1, 0)
        s.line_box(X0+1, Y0+1, X1-1, Y1-1)
        s.colors(dx, 1, dx+w, h+3, PAPER)
        for row, (text, key, separator) in enumerate(items):
            y = (row+2)*8
            state = flags.get((open_title, row), 2 if separator else 0)
            if separator:
                s.rect((dx+1)*8, y+3, (dx+w-1)*8, y+4, 1)
            else:
                s.rect((dx+1)*8, y, (dx+w-1)*8, y+8, 0)
                if state & 1:
                    for dy, bits in enumerate(CHECK):
                        for dxp in range(8):
                            if bits & (128 >> dxp):
                                s.rect((dx+1)*8+dxp, y+dy, (dx+1)*8+dxp+1, y+dy+1, 1)
                s.text((dx+2)*8, y, text)
                if key:
                    s.text((dx+w-3)*8, y, bytes([0x5e, key | 0x40]))
            color = GREY if state >= 2 or separator else FOCUS if hover == row else PAPER
            s.colors(dx, row+2, dx+w, row+3, color)
    return bytes(s.data), (xs, drops)


# ---- windows -------------------------------------------------------------------
WK = dict(NAME=1, CLOSER=2, FULLER=4, MOVER=8, INFO=16, SIZER=32, UP=64, DN=128,
          VSLIDE=256, LF=512, RT=1024, HSLIDE=2048)
DESKTOP = 0x16
GADGETS = [
    [0xff, 0x81, 0xa5, 0x99, 0x99, 0xa5, 0x81, 0xff],   # close
    [0xff, 0x81, 0xbd, 0xa5, 0xa5, 0xbd, 0x81, 0xff],   # full
    [0xff, 0x81, 0x99, 0xbd, 0xff, 0x99, 0x81, 0xff],   # up
    [0xff, 0x81, 0x99, 0xff, 0xbd, 0x99, 0x81, 0xff],   # down
    [0xff, 0x89, 0x99, 0xbf, 0xbf, 0x99, 0x89, 0xff],   # left
    [0xff, 0x91, 0x99, 0xfd, 0xfd, 0x99, 0x91, 0xff],   # right
    [0xff, 0x81, 0xbd, 0xa1, 0xa1, 0xa1, 0x81, 0xff],   # size
    [0xaa, 0x55, 0xaa, 0x55, 0xaa, 0x55, 0xaa, 0x55],   # track
    [0xff]*8,                                             # thumb
]


def geometry(win):
    k = win['kind']
    title = bool(k & (WK['NAME'] | WK['CLOSER'] | WK['FULLER'] | WK['MOVER']))
    info = bool(k & WK['INFO'])
    vbar = bool(k & (WK['UP'] | WK['DN'] | WK['VSLIDE']))
    hbar = bool(k & (WK['LF'] | WK['RT'] | WK['HSLIDE'])) or (bool(k & WK['SIZER']) and not vbar)
    wx, wy = win['x'], win['y']+title+info
    return dict(title=title, info=info, vbar=vbar, hbar=hbar, wx=wx, wy=wy,
                ww=win['w']-vbar, wh=win['h']-title-info-hbar)


def thumb(track, size, pos):
    if track == 0:
        return 0, 0
    prod = track*size
    length = (prod >> 8)+(1 if prod & 255 else 0)
    length = min(max(length, 1), track)
    return (pos*(track-length)+128) >> 8, length


def cell_map(windows):
    """windows bottom->top; returns 25x40 owner map (0 desktop)."""
    owner = [[0]*40 for _ in range(25)]
    for win in windows:
        for r in range(win['y'], win['y']+win['h']):
            for c in range(win['x'], win['x']+win['w']):
                owner[r][c] = win['id']
    return owner


def rectangles(owner, h, area):
    """Row runs merged downward, in the AES's order (docs/NATIVE-AES.md)."""
    ax, ay, aw, ah = area
    x1, y1 = ax+aw, ay+ah
    def run_at(row, start, end):
        if any(owner[row][c] != h for c in range(start, end)):
            return False
        if start > ax and owner[row][start-1] == h:
            return False
        if end < x1 and owner[row][end] == h:
            return False
        return True
    out = []
    for r in range(ay, y1):
        c = ax
        while c < x1:
            if owner[r][c] != h:
                c += 1; continue
            s = c
            while c < x1 and owner[r][c] == h:
                c += 1
            if r > ay and run_at(r-1, s, c):
                continue
            d = r+1
            while d < y1 and run_at(d, s, c):
                d += 1
            out.append((s, r, c-s, d-r))
    return out


def windows_draw(windows, fills, base=None, content=None, markers=True):
    """Painter's algorithm: desktop (or base), then each window bottom->top,
    frame and work fill (plus content(surface, win, geometry)); the last
    window is on top."""
    if base is None:
        s = Surface(bytes(8192)+bytes([DESKTOP])*1024)
        s.colors(0, 0, 40, 25, DESKTOP)
    else:
        s = Surface(base)
    for n, win in enumerate(windows):
        top = n == len(windows)-1
        g = geometry(win)
        x, y, w, h, k = win['x'], win['y'], win['w'], win['h'], win['kind']
        def band(row, focus):
            s.rect(x*8, row*8, (x+w)*8, row*8+8, 0)
            s.rect(x*8, row*8+7, (x+w)*8, row*8+8, 1)
            s.colors(x, row, x+w, row+1, FOCUS if focus else PAPER)
        def gadget(index, cx, cy):
            s.glyph(cx, cy, GADGETS[index])
        if g['title']:
            band(y, top)
            if k & WK['CLOSER']:
                gadget(0, x, y)
            if k & WK['FULLER']:
                gadget(1, x+w-1, y)
            title = win.get('title', b'')
            if title:
                shown = title[:w-2]
                s.text((x+(w-len(shown))//2)*8, y*8, shown)
        if g['info']:
            band(y+g['title'], False)
        if g['vbar']:
            cx = x+w-1
            track, ty = g['wh'], g['wy']
            if not g['hbar'] and k & WK['SIZER']:
                track -= 1
            if k & WK['UP']:
                gadget(2, cx, ty); ty += 1; track -= 1
            if k & WK['DN']:
                gadget(3, cx, ty+track-1); track -= 1
            at, length = thumb(track, win.get('vsize', 255), win.get('vpos', 0))
            for i in range(track):
                gadget(8 if at <= i < at+length else 7, cx, ty+i)
            s.colors(cx, g['wy'], cx+1, g['wy']+g['wh'], PAPER)
        if g['hbar']:
            cy = y+h-1
            track, tx = g['ww'], g['wx']
            if not g['vbar'] and k & WK['SIZER']:
                track -= 1
            if k & WK['LF']:
                gadget(4, tx, cy); tx += 1; track -= 1
            if k & WK['RT']:
                gadget(5, tx+track-1, cy); track -= 1
            at, length = thumb(track, win.get('hsize', 255), win.get('hpos', 0))
            for i in range(track):
                gadget(8 if at <= i < at+length else 7, tx+i, cy)
            s.colors(x, cy, x+w, cy+1, PAPER)
        if k & WK['SIZER']:
            gadget(6, x+w-1, y+h-1)
        pen, color = fills[win['id']]
        s.rect(g['wx']*8, g['wy']*8, (g['wx']+g['ww'])*8, (g['wy']+g['wh'])*8, pen)
        s.colors(g['wx'], g['wy'], g['wx']+g['ww'], g['wy']+g['wh'], color)
        if content:
            content(s, win, g)
        for (cx, cy), marker in () if not markers else (((g['wx'], g['wy']), 0xf2),
                                 ((g['wx']+g['ww']-1, g['wy']+g['wh']-1), 0x2f)):
            s.rect(cx*8, cy*8, cx*8+8, cy*8+8, 1)    # the demo's position markers
            s.colors(cx, cy, cx+1, cy+1, marker)
    return bytes(s.data)
