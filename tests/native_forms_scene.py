"""Independent expectation of a native form (docs/NATIVE-FORMS.md) drawn over
a 9216-byte surface: frame like an AES alert, then each object in order."""
import native_aes_scene as scene

TEXT, BUTTON, CHECK, RADIO, FIELD = 1, 2, 3, 4, 5
DEFAULT, EXIT, CANCEL = 1, 2, 4
SELECTED, DISABLED = 1, 2
PAPER, FOCUS, GREY = 0x61, 0x07, 0xc1
GLYPHS = {
    (CHECK, 0): [0xff, 0x81, 0x81, 0x81, 0x81, 0x81, 0x81, 0xff],
    (CHECK, 1): [0xff, 0xc3, 0xa5, 0x99, 0x99, 0xa5, 0xc3, 0xff],
    (RADIO, 0): [0x3c, 0x42, 0x81, 0x81, 0x81, 0x81, 0x42, 0x3c],
    (RADIO, 1): [0x3c, 0x42, 0x99, 0xbd, 0xbd, 0x99, 0x42, 0x3c],
}


def obj(kind, x, y, w, text=b'', flags=0, state=0, field=None):
    """field: dict(value=bytes, caret=int, view=int) for FIELD objects."""
    return dict(kind=kind, x=x, y=y, w=w, text=text, flags=flags, state=state, field=field)


def place(w, h, x=None, y=None):
    if x is None:
        return (40-w)//2, max(1, (25-h)//2)
    return x, y


def view_of(field, w):
    view = field.get('view', 0)
    caret = field['caret']
    if caret < view:
        view = caret
    if caret-view >= w:
        view = caret-w+1
    return view


def printable(raw):
    return bytes(c if 32 <= c < 127 else 0x3f for c in raw)


def draw(before, w, h, objects, focus, x=None, y=None):
    fx, fy = place(w, h, x, y)
    s = scene.Surface(before)
    X0, Y0, X1, Y1 = fx*8, fy*8, (fx+w)*8, (fy+h)*8
    for inset in range(5):
        s.rect(X0+inset, Y0+inset, X1-inset, Y1-inset, inset & 1)
    s.colors(fx, fy, fx+w, fy+h, PAPER)
    for i, o in enumerate(objects):
        ax, ay = fx+o['x'], fy+o['y']
        rows = 2 if o['kind'] == BUTTON else 1
        color = PAPER
        if o['state'] & DISABLED:
            color = GREY
        elif i == focus and o['kind'] != FIELD:
            color = FOCUS
        s.rect(ax*8, ay*8, (ax+o['w'])*8, (ay+rows)*8, 0)
        label = o['text'][:min(o['w'], 38)]
        if o['kind'] == TEXT:
            s.text(ax*8, ay*8, printable(label))
        elif o['kind'] == BUTTON:
            b0, b1 = ax*8, (ax+o['w'])*8
            s.line_box(b0, ay*8, b1, ay*8+16)
            if o['flags'] & DEFAULT:
                s.line_box(b0+1, ay*8+1, b1-1, ay*8+15)
            s.text((ax+(o['w']-len(label))//2)*8, ay*8+4, printable(label))
        elif o['kind'] in (CHECK, RADIO):
            s.glyph(ax, ay, GLYPHS[o['kind'], o['state'] & SELECTED])
            s.text((ax+2)*8, ay*8, printable(label))
        elif o['kind'] == FIELD:
            f = o['field']
            view = view_of(f, o['w'])
            s.text(ax*8, ay*8, printable(f['value'][view:view+o['w']]))
            s.rect(ax*8, ay*8+7, (ax+o['w'])*8, ay*8+8, 1)
            s.colors(ax, ay, ax+o['w'], ay+1, color)
            if i == focus:
                cx = ax+f['caret']-view
                s.colors(cx, ay, cx+1, ay+1, FOCUS)
            continue
        s.colors(ax, ay, ax+o['w'], ay+rows, color)
    return bytes(s.data)
