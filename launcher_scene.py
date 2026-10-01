"""Desktop layout data and an independent per-pixel surface oracle."""
from src.native.graphics.font import font

CARDS = (40, 56, 72, 88, 104, 120, 136)
LABELS = (
    (b'Calculator', b'Numbers and saved history'),
    (b'Text editor', b'Documents on disk and USB'),
    (b'Files', b'Drives, USB folders and apps'),
    (b'Ultimate', b'Drives, network and clock'),
    (b'Claude', b'Claude Code terminal'),
    (b'Paint', b'Pictures, colors and undo'),
    (b'Sheet', b'Cells, formulas and workbooks'),
)
OPS = [(0, (16, 27, 304, 28), 1)]
TEXT = [(16, 8, 1, b'Kestrel'), (184, 8, 1, b'Desktop')]
for index, (top, (name, description)) in enumerate(zip(CARDS, LABELS)):
    OPS.extend([(0, (16, top, 304, top+16), 1),
                (0, (17, top+1, 303, top+15), 0)])
    TEXT.extend([(32, top+4, 1, str(index+1).encode()), (64, top+4, 1, name)])
TEXT.extend([(8, 164, 1, b'Cells, documents, pictures and tools'),
             (8, 176, 1, b'Mouse opens   C/E/F/U/A/P/S apps'),
             (8, 188, 1, b'Arrows/Tab/Enter   Esc workspace')])


# Two single-color sprites: white interior (0) over black outline (1).
# Each ASCII pixel is independently translated into the VIC's 24x21 format.
POINTER = [
    'B', 'BB', 'BWB', 'BWWB', 'BWWWB', 'BWWWWB', 'BWWWWWB',
    'BWWWWWWB', 'BWWWWWWWB', 'BWWWWBBBBB', 'BWWBWWB',
    'BWB BWWB', 'BB  BWWB', 'B    BWWB', '     BWWB', '      BB',
]


def pointer_shape():
    output = bytearray()
    for ink in ('W', 'B'):
        for y in range(21):
            row = POINTER[y] if y < len(POINTER) else ''
            bits = sum(1 << (23-x) for x, pixel in enumerate(row) if pixel == ink)
            output.extend(bits.to_bytes(3, 'big'))
        output.append(0)
    return bytes(output)


def surface(selected=0, error=0):
    assert 0 <= selected < len(CARDS) and 0 <= error <= 255
    data = bytearray(bytes(8192) + b'\x16' * 1024)
    for mode, (x0, y0, x1, y1), value in OPS:
        assert mode == 0 and value in (0, 1)
        for y in range(max(0, y0), min(200, y1)):
            for x in range(max(0, x0), min(320, x1)):
                at = y//8*320 + x//8*8 + y%8
                mask = 128 >> (x%8)
                if value: data[at] |= mask
                else: data[at] &= mask ^ 255
    labels = ([label for label in TEXT if label[1]!=176]+[(8, 176, 1, f'App could not open: {error:02X}'.encode())]
              if error else TEXT)
    glyphs = font()
    for x0, y0, pen, label in labels:
        assert pen == 1
        for column, code in enumerate(label):
            for dy, row in enumerate(glyphs[(code-32)*8:][:8]):
                for dx in range(8):
                    x, y = x0+column*8+dx, y0+dy
                    if 0 <= x < 320 and 0 <= y < 200 and row & (128 >> dx):
                        data[y//8*320+x//8*8+y%8] |= 128 >> (x%8)
    for index, top in enumerate(top//8 for top in CARDS):
        for y in range(top, top+2):
            for x in range(2, 38):
                data[8192+y*40+x] = 0x07 if index == selected else 0x1b
    data[8000:8128] = pointer_shape()
    data[9208:9210] = bytes([0x7d, 0x7e])
    return bytes(data)


def console(columns, selected=0, error=0, fallback=False):
    lines = ['KESTREL 128', '']
    for index, (name, description) in enumerate([
        ('C  CALCULATOR', 'NUMBERS AND SAVED HISTORY'),
        ('E  TEXT EDITOR', 'DOCUMENTS ON DISK AND USB'),
        ('F  FILES', 'DRIVES, USB FOLDERS AND APPS'),
        ('U  ULTIMATE', 'DRIVES, NETWORK AND CLOCK'),
        ('A  CLAUDE', 'CLAUDE CODE TERMINAL'),
        ('P  PAINT', 'PICTURES, COLORS AND UNDO'),
        ('S  SHEET', 'CELLS, FORMULAS AND WORKBOOKS'),
    ]):
        lines.extend([('>' if selected == index else ' ') + ' ' + name, '    '+description])
    lines.extend(['ARROWS/TAB SELECT. ENTER OPENS.', 'C/E/F/U/A/P/S APPS. ESC WORKSPACE.', ''])
    # Assembly prints no newline after the error value unless the fallback follows.
    lines.append(f'APP COULD NOT OPEN: {error:02X}' if error else '')
    if fallback:
        lines.extend(['GRAPHICS UNAVAILABLE.', 'TEXT CONTROLS REMAIN ACTIVE.'])
    result = bytearray(b' ' * (columns*25))
    for y, line in enumerate(lines):
        for x, char in enumerate(line.encode()):
            result[y*columns+x] = char-64 if 64 <= char < 96 else char
    return bytes(result)


def write_assembly(directory):
    """Generate the assembler's static commands from the reviewed layout."""
    shape = pointer_shape()
    (directory/'pointer-shape.inc').write_text('\n'.join(
        '        .byte '+','.join('$%02x'%v for v in shape[i:i+16])
        for i in range(0, len(shape), 16))+'\n')
    scene = [f'scene_commands_count={len(OPS)}']
    for mode, rect, value in OPS:
        scene.extend(['        .sint '+','.join(map(str, rect)), f'        .byte {mode},{value}'])
    (directory/'scene-commands.inc').write_text('\n'.join(scene)+'\n')
    text = [f'text_commands_count={len(TEXT)}']
    for x, y, pen, label in TEXT:
        text.extend([f'        .word {x},{y}', f'        .byte {pen},{len(label)}',
                     '        .byte '+','.join(map(str, label))])
    (directory/'text-commands.inc').write_text('\n'.join(text)+'\n')
