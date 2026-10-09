"""Native 640×200 launcher pixels, VDC attributes and lossless build packing."""
from launcher_scene import OPS, POINTER, CARDS, LABELS
from src.native.graphics.font import font

WIDTH, HEIGHT = 640, 200
ARROW = bytes((0x00, 0x40, 0x60, 0x70, 0x78, 0x70, 0x60, 0x40))


def bitmap(selected=None, error=0):
    data = bytearray(16000)
    def rect(x0, y0, x1, y1, value):
        for y in range(y0, y1):
            for x in range(x0, x1):
                at, mask = y*80+x//8, 128>>(x&7)
                if value: data[at] |= mask
                else: data[at] &= mask^255
    for _, (x0, y0, x1, y1), value in OPS:
        rect(x0*2, y0, x1*2, y1, value)
    glyphs = font()
    def text(x, y, message):
        assert x%8 == 0 and x+len(message)*8 <= WIDTH and y+8 <= HEIGHT
        for column, code in enumerate(message):
            for dy, bits in enumerate(glyphs[(code-32)*8:][:8]):
                data[(y+dy)*80+x//8+column] = bits
    text(32, 8, b'Kestrel')
    text(496, 8, b'Desktop')
    for y, (name, description) in zip(CARDS, LABELS):
        text(128, y+4, name)
        text(280, y+4, description)
    text(32, 176, f'App could not open: {error:02X}'.encode() if error else
         b'Mouse opens apps.  Arrows/Tab select.  Enter opens.')
    text(32, 188, b'C Calc  E Editor  F Files  U Ultimate  A Claude  P Paint  S Sheet  Esc back')
    if selected is not None:
        assert 0 <= selected < len(CARDS)
        for dy, bits in enumerate(ARROW):
            data[(CARDS[selected]+4+dy)*80+13] = bits
    return bytes(data)


def attributes(selected=0):
    assert 0 <= selected < len(CARDS)
    data = bytearray(b'\x2f'*2000)  # VDC bitmap: background high, foreground low.
    for index, top in enumerate(CARDS):
        for row in range(top//8, top//8+2):
            data[row*80+4:row*80+76] = bytes([0xd0 if index == selected else 0x1f])*72
    return bytes(data)


def pointer_bitmap(data, x, y, visible=True):
    """The VDC pointer XORs a clipped arrow and leaves the attribute plane alone."""
    assert len(data) == 16000 and 0 <= x < 640 and 0 <= y < 200
    result = bytearray(data)
    if visible:
        for dy, row in enumerate(POINTER):
            for dx, pixel in enumerate(row):
                if pixel != ' ' and x+dx < 640 and y+dy < 200:
                    result[(y+dy)*80+(x+dx)//8] ^= 128>>((x+dx)&7)
    return bytes(result)


def pixels(selected=0, *, color=True, x=0, y=0, visible=False, error=0):
    data = pointer_bitmap(bitmap(selected, error), x, y, visible)
    attrs = attributes(selected)
    return bytes(
        ((attrs[row//8*80+column//8]&15) if bit else (attrs[row//8*80+column//8]>>4))
        if color else (15 if bit else 2)
        for row in range(200) for column in range(640)
        for bit in [data[row*80+column//8] & (128>>(column&7))]
    )


def pack(data):
    """Zero ends; literals 1..63; fills 64..127; prior-block copies 128..255.

    An optimal parse (fewest packed bytes) over the longest earlier match at
    each position; a copy never overlaps its source, as the VDC block copy needs.
    """
    size = len(data); matches = [(0, 0)]*size; seen = {}
    for at in range(size-2):
        length = distance = 0
        for prior in reversed(seen.get(data[at:at+3], [])[-512:]):
            if at-prior > 16384: break
            limit = min(130, at-prior, size-at)
            if limit <= length: continue
            count = 3
            while count < limit and data[prior+count] == data[at+count]: count += 1
            if count > length: length, distance = count, at-prior
            if length == 130: break
        matches[at] = (length, distance)
        seen.setdefault(data[at:at+3], []).append(at)
    run = [1]*size
    for at in range(size-2, -1, -1):
        if data[at] == data[at+1]: run[at] = run[at+1]+1
    cost = [0]*(size+1); step = [None]*size
    for at in range(size-1, -1, -1):
        options = [(1+count+cost[at+count], 'literal', count) for count in range(1, min(63, size-at)+1)]
        options += [(2+cost[at+count], 'fill', count) for count in range(1, min(64, run[at])+1)]
        length, distance = matches[at]
        options += [(3+cost[at+count], 'copy', count) for count in range(3, length+1)]
        cost[at], kind, count = min(options, key=lambda option: option[0])
        step[at] = kind, count
    out = bytearray(); at = 0
    while at < size:
        kind, count = step[at]
        if kind == 'literal': out.append(count); out += data[at:at+count]
        elif kind == 'fill': out += bytes((63+count, data[at]))
        else: out += bytes((125+count, matches[at][1]&255, matches[at][1]>>8))
        at += count
    return bytes(out)+b'\0'


def unpack(data):
    out = bytearray(); at = 0
    while data[at]:
        code = data[at]; at += 1
        if code >= 128:
            count = code-125
            distance = int.from_bytes(data[at:at+2], 'little'); at += 2
            assert count <= distance <= len(out)
            start = len(out)-distance
            out += out[start:start+count]
        elif code >= 64:
            out += data[at:at+1]*(code-63); at += 1
        else:
            out += data[at:at+code]; at += code
    assert at == len(data)-1
    return bytes(out)


def write_assembly(directory):
    packed = pack(bitmap())
    assert unpack(packed) == bitmap()
    rows = ['; Generated by native_vdc_scene.py; full native 640×200 bitmap.', 'vd_scene:']
    rows += ['        .byte '+','.join(f'${v:02x}' for v in packed[at:at+16])
             for at in range(0, len(packed), 16)]
    rows += ['vd_scene_end:', 'vd_arrow: .byte '+','.join(f'${v:02x}' for v in ARROW)]
    pointer = [sum(1<<(15-x) for x, value in enumerate(row) if value != ' ') for row in POINTER]
    # graphics/vdc-pointer.inc redraws two bytes per row: its shifts are 0, 2, 4
    # or 6 VDC pixels, so the low six bits of each 16-pixel row must stay clear.
    assert all(v & 0x3f == 0 for v in pointer)
    (directory/'vdc-scene.inc').write_text('\n'.join(rows)+'\n')
    shape = ['; Generated from the shared launcher pointer.',
             'vd_pointer_hi: .byte '+','.join(f'${v>>8:02x}' for v in pointer),
             'vd_pointer_lo: .byte '+','.join(f'${v&255:02x}' for v in pointer)]
    (directory.parent/'graphics/vdc-pointer-shape.inc').write_text('\n'.join(shape)+'\n')


if __name__ == '__main__':
    print('Bitmap bytes:', len(bitmap()), 'packed:', len(pack(bitmap())))
