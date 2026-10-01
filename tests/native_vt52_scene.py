"""Independent VT52 screen model (docs/NATIVE-VT52.md): 80x25 cells of ASCII
screen codes and VDC attributes (bit 7 alternate set, bit 6 reverse, colour)."""
ROWS, COLS = 25, 80


class VT52:
    def __init__(self):
        self.row = self.col = 0
        self.fg, self.bg, self.reverse = 15, 0, 0
        self.wrap = self.cursor = True
        self.saved = (0, 0)
        self.state = 0
        self.chars = bytearray(b' '*ROWS*COLS)
        self.attrs = bytearray([0x80 | 15])*(ROWS*COLS)

    def blank(self, start, count):
        self.chars[start:start+count] = b' '*count
        self.attrs[start:start+count] = bytes([0x80 | self.fg])*count

    def move_rows(self, src, dst, rows):
        a, b, n = src*COLS, dst*COLS, rows*COLS
        self.chars[b:b+n] = self.chars[a:a+n]
        self.attrs[b:b+n] = self.attrs[a:a+n]

    def scroll_up(self, top=0):
        self.move_rows(top+1, top, ROWS-1-top)
        self.blank((ROWS-1)*COLS, COLS)

    def open_line(self, top):
        for r in range(ROWS-2, top-1, -1):
            self.move_rows(r, r+1, 1)
        self.blank(top*COLS, COLS)

    def line_feed(self):
        if self.row < ROWS-1:
            self.row += 1
        else:
            self.scroll_up()

    def feed(self, data):
        for byte in data:
            self.put(byte)
        return self

    def put(self, c):
        s = self.state
        if s == 1:
            self.state = 0
            self.escape(c)
        elif s == 2:
            self.row = min(c-32 if c >= 32 else (c-32) & 255, ROWS-1); self.state = 3
        elif s == 3:
            self.col = min(c-32 if c >= 32 else (c-32) & 255, COLS-1); self.state = 0
        elif s == 4:
            self.fg = c & 15; self.state = 0
        elif s == 5:
            self.bg = c & 15; self.state = 0
        elif 32 <= c < 127:
            at = self.row*COLS+self.col
            self.chars[at] = c
            self.attrs[at] = 0x80 | self.reverse | self.fg
            self.col += 1
            if self.col == COLS:
                if self.wrap:
                    self.col = 0
                    self.line_feed()
                else:
                    self.col = COLS-1
        elif c == 27:
            self.state = 1
        elif c == 13:
            self.col = 0
        elif c == 8:
            self.col = max(0, self.col-1)
        elif c == 9:
            self.col = min((self.col | 7)+1, COLS-1)
        elif c in (10, 11, 12):
            self.line_feed()

    def escape(self, c):
        at = self.row*COLS+self.col
        ch = chr(c)
        if ch == 'A': self.row = max(0, self.row-1)
        elif ch == 'B': self.row = min(ROWS-1, self.row+1)
        elif ch == 'C': self.col = min(COLS-1, self.col+1)
        elif ch == 'D': self.col = max(0, self.col-1)
        elif ch == 'E': self.blank(0, ROWS*COLS); self.row = self.col = 0
        elif ch == 'H': self.row = self.col = 0
        elif ch == 'I':
            if self.row: self.row -= 1
            else: self.open_line(0)
        elif ch == 'J': self.blank(at, ROWS*COLS-at)
        elif ch == 'K': self.blank(at, COLS-self.col)
        elif ch == 'L': self.col = 0; self.open_line(self.row)
        elif ch == 'M':
            self.col = 0
            if self.row < ROWS-1: self.move_rows(self.row+1, self.row, ROWS-1-self.row)
            self.blank((ROWS-1)*COLS, COLS)
        elif ch == 'Y': self.state = 2
        elif ch == 'b': self.state = 4
        elif ch == 'c': self.state = 5
        elif ch == 'd': self.blank(0, at+1)
        elif ch == 'e': self.cursor = True
        elif ch == 'f': self.cursor = False
        elif ch == 'j': self.saved = (self.row, self.col)
        elif ch == 'k': self.row, self.col = self.saved
        elif ch == 'l': self.blank(self.row*COLS, COLS)
        elif ch == 'o': self.blank(self.row*COLS, self.col+1)
        elif ch == 'p': self.reverse = 0x40
        elif ch == 'q': self.reverse = 0
        elif ch == 'v': self.wrap = True
        elif ch == 'w': self.wrap = False


def key_bytes(key):
    """What the terminal sends for a PETSCII key (docs/NATIVE-VT52.md)."""
    cursor = {0x91: b'\x1bA', 0x11: b'\x1bB', 0x1d: b'\x1bC', 0x9d: b'\x1bD'}
    if key in cursor: return cursor[key]
    if key == 0x14: return b'\x08'
    if key < 0x41: return bytes([key])
    if key < 0x5b: return bytes([key | 0x20])
    if key < 0x60: return bytes([key])
    if 0xc1 <= key < 0xdb: return bytes([key & 0x7f])
    return b''
