"""Wire protocol between the Linux bridge and the C128 client.

The C128 is on the far end of a 6551 ACIA, so bandwidth is the binding
constraint: a full 80x25 repaint is ~2KB, which is about half a second at
38400 baud. Claude Code repaints its whole screen constantly, so the bridge
diffs frames and sends only changed cell runs. Typical streaming output touches
one or two lines, i.e. under 100 bytes per frame.

An attribute byte is a VDC attribute directly: bits 0-3 colour, bit 5
underline, bit 6 reverse. The client writes it straight into VDC attribute RAM.
"""
import struct

CMD_CLEAR = 0x01     # attr
CMD_RUN = 0x02       # row, col, attr, len, <len screen codes>
CMD_FILL = 0x03      # row, col, attr, len, char
CMD_CURSOR = 0x04    # row, col   (0xFF,0xFF hides it)
CMD_FRAME = 0x05     # end of frame
CMD_BELL = 0x06
CMD_PANEL = 0x07     # row, colour, len, <len screen codes> -> VIC-II panel
CMD_HELLO = 0x08     # cols, rows
CMD_BYE = 0x09       # followed by BYE_MAGIC

# A bare opcode is one bit-flip away from ending the session, so shutting the
# client down takes a second byte that is unlikely to occur by accident.
BYE_MAGIC = 0x5A
CMD_GLYPH = 0x0A     # code, 8 bitmap bytes -> redefine a VDC character
CMD_SCROLL = 0x0B    # top, bot, n -> shift rows top..bot by n & $7F rows;
                     # bit 7 of n set means downward. See Encoder.scroll.

SCROLL_DOWN = 0x80   # direction flag inside the SCROLL count byte
CMD_CAPABILITIES = 0x0D  # one feature byte; sent only after CLIENT_CAPABILITIES
CMD_PASTE_RESULT = 0x0E  # 0 accepted; 1 rejected; only after a negotiated paste

ATTR_UNDERLINE = 0x20
ATTR_REVERSE = 0x40
ATTR_COLOR_MASK = 0x0F

# Client -> server. A keystroke is never $00, so $00 introduces a control byte.
# The client cannot rely on catching the start of the stream: the link is open
# before the C128 has finished loading, and on real hardware the operator
# starts the client whenever they like. So the client announces itself and asks
# for a full repaint rather than assuming it saw frame one.
CLIENT_ESCAPE = 0x00
CLIENT_RESYNC = 0x01     # "repaint everything, I may have missed bytes"
CLIENT_BYE = 0x02
CLIENT_CREDIT = 0x03     # "I have consumed CREDIT_UNIT more bytes"
CLIENT_CAPABILITIES = 0x04  # request optional protocol extensions
CLIENT_PASTE_CHUNK = 0x05   # count byte, then 1..64 literal bytes (including $00)
CLIENT_PASTE_BEGIN = 0x06   # total length LE16, 1..16384
CLIENT_PASTE_END = 0x07     # publish only a complete, validated bracketed paste
CLIENT_PASTE_ABORT = 0x08   # discard a staged paste; no terminal input
FEATURE_PASTE = 1
MAX_PASTE = 16384

# Receiver-driven flow control. The C128 is always the slow party and only it
# knows when it has actually applied a byte, so the server never sends more
# than CREDIT_WINDOW bytes beyond what the client has acknowledged. This is
# transport-independent: neither VICE's RS232 emulation nor the Ultimate's
# TCP-backed modem honours the ACIA's nominal baud, so metering by time cannot
# be made safe, and a burst larger than the client's 256-byte receive ring is
# lost silently as missing rows.
CREDIT_UNIT = 64
CREDIT_WINDOW = 192      # < the client's 255-byte usable ring

MAX_RUN = 255
CURSOR_HIDDEN = (0xFF, 0xFF)


class Encoder:
    """Builds a frame of protocol bytes."""

    def __init__(self):
        self.buf = bytearray()

    def clear(self, attr=0x0E):
        self.buf += bytes((CMD_CLEAR, attr))

    def run(self, row, col, attr, codes):
        while codes:
            chunk, codes = codes[:MAX_RUN], codes[MAX_RUN:]
            self.buf += bytes((CMD_RUN, row, col, attr, len(chunk)))
            self.buf += bytes(chunk)
            col += len(chunk)

    def fill(self, row, col, attr, char, count):
        while count > 0:
            n = min(count, MAX_RUN)
            self.buf += bytes((CMD_FILL, row, col, attr, n, char))
            col += n
            count -= n

    def cursor(self, row, col):
        self.buf += bytes((CMD_CURSOR, row & 0xFF, col & 0xFF))

    def hide_cursor(self):
        self.buf += bytes((CMD_CURSOR, 0xFF, 0xFF))

    def panel(self, row, color, codes):
        codes = codes[:40]
        self.buf += bytes((CMD_PANEL, row, color, len(codes))) + bytes(codes)

    def bell(self):
        self.buf += bytes((CMD_BELL,))

    def glyph(self, code, bitmap):
        self.buf += bytes((CMD_GLYPH, code)) + bytes(bitmap)

    def scroll(self, top, bot, n, down=False):
        """Shift rows top..bot (inclusive) by n rows, upward unless `down`.

        The client moves whole rows of both planes in place - on the C128 the
        VDC's own block copy does it, so a one-line scroll of the transcript
        costs these four bytes instead of repainting every shifted row. The
        copy does not erase its source, so the n rows exposed at the trailing
        edge keep their old content; the differ knows this and repaints them.
        """
        self.buf += bytes((CMD_SCROLL, top, bot,
                           (n & 0x7F) | (SCROLL_DOWN if down else 0)))

    def hello(self, cols, rows):
        self.buf += bytes((CMD_HELLO, cols, rows))

    def bye(self):
        self.buf += bytes((CMD_BYE, BYE_MAGIC))

    def frame(self):
        self.buf += bytes((CMD_FRAME,))

    def take(self):
        out = bytes(self.buf)
        self.buf = bytearray()
        return out

    def __len__(self):
        return len(self.buf)


# A run shorter than this is not worth splitting off from its neighbour: the
# 5-byte header costs more than just resending the unchanged cells between.
RUN_HEADER = 5
GAP_TOLERANCE = RUN_HEADER


class ScreenDiffer:
    """Tracks what the client is displaying and emits minimal updates."""

    def __init__(self, cols=80, rows=25, blank_attr=0x0E, scroll=True):
        self.cols, self.rows = cols, rows
        self.blank_attr = blank_attr
        self.blank_cell = (0x20, blank_attr)
        self.prev = None
        self.prev_cursor = None
        self.scroll_enabled = scroll
        self.scrolls_used = 0       # SCROLL commands actually sent

    def reset(self):
        """Forget client state so the next diff is a full repaint."""
        self.prev = None
        self.prev_cursor = None

    def diff(self, grid, cursor):
        """grid: rows x cols list of (screen_code, attr). Returns frame bytes."""
        enc = Encoder()
        if self.prev is None:
            enc.clear(self.blank_attr)
            blank = [[self.blank_cell] * self.cols for _ in range(self.rows)]
            enc.buf += self._encode_against(grid, blank)
        else:
            body = self._encode_against(grid, self.prev)
            # When the frame is mostly the previous one shifted, a SCROLL
            # command plus a diff against the shifted screen can be far
            # smaller. Both encodings are exact, so the choice is purely
            # whichever costs fewer bytes on the wire.
            if self.scroll_enabled:
                alt = self._scrolled_encoding(grid)
                if alt is not None and len(alt) < len(body):
                    body = alt
                    self.scrolls_used += 1
            enc.buf += body

        self.prev = [list(row) for row in grid]

        if cursor != self.prev_cursor:
            if cursor is None:
                enc.hide_cursor()
            else:
                enc.cursor(cursor[0], cursor[1])
            self.prev_cursor = cursor

        enc.frame()
        return enc.take()

    def _encode_against(self, grid, prev):
        """Frame body updating a client showing `prev` to show `grid`."""
        enc = Encoder()
        for r in range(self.rows):
            new_row = grid[r]
            for start, end in self._changed_spans(new_row, prev[r]):
                self._emit_span(enc, r, new_row, start, end)
        return enc.take()

    def _scrolled_encoding(self, grid):
        """Frame body as SCROLL + diff, or None when no shift explains it."""
        found = self._detect_scroll(grid)
        if found is None:
            return None
        top, bot, n, down = found
        shifted = apply_scroll(self.prev, top, bot, n, down)
        enc = Encoder()
        enc.scroll(top, bot, n, down)
        return enc.take() + self._encode_against(grid, shifted)

    def _detect_scroll(self, grid):
        """The row shift that explains the most changed rows, or None.

        Detection only has to be good, not perfect: the caller re-encodes the
        frame against the shifted screen and keeps the plain diff whenever
        that is smaller, so a bad guess costs bytes, never pixels.
        """
        new_rows = [tuple(r) for r in grid]
        old_rows = [tuple(r) for r in self.prev]
        # Rows are compared many times; hashes make each comparison O(1) with
        # an exact tuple check behind the rare hash collision.
        new_h = [hash(r) for r in new_rows]
        old_h = [hash(r) for r in old_rows]

        def same(i, j):
            return new_h[i] == old_h[j] and new_rows[i] == old_rows[j]

        def changed(r):             # the shift must explain a real change:
            return not same(r, r)   # rows already right in place are free riders

        best = None                 # (score, top, bot, n, down)
        for down in (False, True):
            for n in range(1, self.rows - 1):
                if down:
                    rng = range(n, self.rows)       # new[r] == old[r - n]
                else:
                    rng = range(0, self.rows - n)   # new[r] == old[r + n]
                run = []
                for r in list(rng) + [None]:        # None flushes the last run
                    if r is not None and same(r, r - n if down else r + n):
                        run.append(r)
                        continue
                    if run:
                        score = sum(1 for q in run if changed(q))
                        if score and (best is None or score > best[0]):
                            if down:
                                region = (run[0] - n, run[-1])
                            else:
                                region = (run[0], run[-1] + n)
                            best = (score, region[0], region[1], n, down)
                        run = []
        if best is None:
            return None
        _, top, bot, n, down = best
        return top, bot, n, down

    def _changed_spans(self, new_row, old_row):
        """Changed column spans, merging ones separated by a tiny clean gap.

        Spans are closed on the last genuinely changed cell, so a run never
        loses its final character to the trailing clean gap.
        """
        spans = []
        col = 0
        while col < self.cols:
            if new_row[col] == old_row[col]:
                col += 1
                continue
            start = last_diff = col
            gap = 0
            while col < self.cols:
                if new_row[col] == old_row[col]:
                    gap += 1
                    if gap > GAP_TOLERANCE:
                        break
                else:
                    gap = 0
                    last_diff = col
                col += 1
            spans.append((start, last_diff + 1))
            col = last_diff + 1 + gap
        return spans

    def _emit_span(self, enc, row, new_row, start, end):
        """Split a span on attribute changes, using FILL for repeated chars."""
        col = start
        while col < end:
            attr = new_row[col][1]
            run_end = col
            while run_end < end and new_row[run_end][1] == attr:
                run_end += 1
            codes = [new_row[c][0] for c in range(col, run_end)]

            # A long stretch of one character is cheaper as a FILL.
            if len(codes) >= 8 and len(set(codes)) == 1:
                enc.fill(row, col, attr, codes[0], len(codes))
            else:
                enc.run(row, col, attr, codes)
            col = run_end


def apply_scroll(cells, top, bot, n, down):
    """Reference model of the client's scroll, shared by differ and sinks.

    Returns a new grid: rows top..bot shifted by n, the n rows at the trailing
    edge keeping their old content because a block copy does not erase its
    source. Bounds are validated exactly as the 6502 validates them, so a
    command the client would ignore is also a no-op here.
    """
    rows = len(cells)
    if not (top <= bot < rows) or not (1 <= n <= bot - top):
        return [list(row) for row in cells]
    out = [list(row) for row in cells]
    if down:
        for r in range(bot, top + n - 1, -1):
            out[r] = list(cells[r - n])
    else:
        for r in range(top, bot - n + 1):
            out[r] = list(cells[r + n])
    return out


def decode(data, sink):
    """Decode a protocol stream, driving `sink`. Used by the preview renderer
    and by the protocol tests to prove encoder and client agree."""
    i, n = 0, len(data)
    while i < n:
        cmd = data[i]
        i += 1
        if cmd == CMD_CLEAR:
            sink.clear(data[i]); i += 1
        elif cmd == CMD_RUN:
            row, col, attr, ln = data[i:i + 4]
            i += 4
            sink.run(row, col, attr, data[i:i + ln]); i += ln
        elif cmd == CMD_FILL:
            row, col, attr, ln, ch = data[i:i + 5]
            i += 5
            sink.run(row, col, attr, bytes([ch]) * ln)
        elif cmd == CMD_CURSOR:
            row, col = data[i], data[i + 1]
            i += 2
            sink.cursor(None if (row, col) == CURSOR_HIDDEN else (row, col))
        elif cmd == CMD_FRAME:
            sink.frame()
        elif cmd == CMD_BELL:
            sink.bell()
        elif cmd == CMD_PANEL:
            row, color, ln = data[i], data[i + 1], data[i + 2]
            i += 3
            sink.panel(row, data[i:i + ln]); i += ln
        elif cmd == CMD_SCROLL:
            top, bot, cnt = data[i], data[i + 1], data[i + 2]
            i += 3
            sink.scroll(top, bot, cnt & 0x7F, bool(cnt & SCROLL_DOWN))
        elif cmd == CMD_GLYPH:
            i += 9
        elif cmd == CMD_HELLO:
            i += 2
        elif cmd == CMD_BYE:
            i += 1
            break
        else:
            raise ValueError(f"bad opcode {cmd:#04x} at offset {i - 1}")
    return i
