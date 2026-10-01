"""Independent pixel oracle for the VIC surface presented on the VDC."""
from native_vdc_scene import pointer_bitmap

PALETTE = (0, 15, 8, 7, 10, 4, 2, 13, 12, 12, 9, 1, 14, 5, 3, 14)
RGBI = ((0,0,0), (85,85,85), (0,0,170), (85,85,255),
        (0,170,0), (85,255,85), (0,170,170), (85,255,255),
        (170,0,0), (255,85,85), (170,0,170), (255,85,255),
        (170,85,0), (255,255,85), (170,170,170), (255,255,255))


def brighter(index):
    r, g, b = RGBI[PALETTE[index]]
    return 299*r + 587*g + 114*b


def bitmap(surface, color=True, *, x=0, y=0, pointer=False):
    assert len(surface) == 9216
    out = bytearray(16000)
    for row in range(200):
        for cell in range(40):
            ink = surface[(row//8)*320+cell*8+row%8]
            attr = surface[8192+(row//8)*40+cell]
            reverse = not color and brighter(attr>>4) < brighter(attr&15)
            for bit in range(8):
                if bool(ink & (128>>bit)) != reverse:
                    col = cell*16+bit*2
                    out[row*80+col//8] |= 0xc0>>(col%8)
    return pointer_bitmap(bytes(out), x*2, y, pointer)


def attributes(surface):
    out = bytearray()
    for attr in surface[8192:9192]:
        out += bytes([(PALETTE[attr&15]<<4)|PALETTE[attr>>4]])*2
    return bytes(out)


def pixels(surface, color=True, *, x=0, y=0, pointer=False):
    bits = bitmap(surface, color, x=x, y=y, pointer=pointer)
    attrs = attributes(surface) if color else bytes([0x2f])*2000
    return [bytes((attrs[(row//8)*80+col//8]&15) if bits[row*80+col//8]&(128>>(col%8))
                  else attrs[(row//8)*80+col//8]>>4 for col in range(640))
            for row in range(200)]
