"""Terminal emulation: ANSI byte stream -> a grid of (screen_code, attr).

Claude Code is a full-screen Ink/React app. It uses the alternate screen
buffer, truecolor SGR, and heavy absolute cursor positioning, so the bridge
runs a real VT emulator (pyte) rather than trying to interpret the stream
directly. What comes out the far side is a plain 80x25 grid the differ can
compare frame to frame.
"""
import re

import pyte

import petscii

# Sequences pyte does not consume and that would otherwise land on screen as
# stray text. OSC 8 hyperlinks are the important one: Claude Code wraps URLs in
# them, and the payload is far longer than the visible text.
_OSC_HYPERLINK = re.compile(rb"\x1b\]8;[^\x07\x1b]*(?:\x07|\x1b\\)")
_OSC_OTHER = re.compile(rb"\x1b\][0-9]+;[^\x07\x1b]*(?:\x07|\x1b\\)")
# Synchronized-output and modern feature-query sequences.
_PRIVATE_MODES = re.compile(rb"\x1b\[\?(?:2026|2031|1004|2004)[hl]")
_DA_QUERY = re.compile(rb"\x1b\[c")

# CSI sequences with a `<`, `>` or `=` private prefix. pyte does not recognise
# these and mishandles them in two ways that both put wrong pixels on screen:
#
#   ESC[<u  ESC[>1u   Kitty keyboard protocol - the final `u` is emitted as a
#                     literal character, leaving a stray "u" at the cursor.
#   ESC[>4;2m         modifyOtherKeys - the `>` is ignored and it is applied as
#                     SGR 4, switching underline on for the rest of the screen.
#
# None of them carry display state, so they are dropped before pyte sees them.
_PRIVATE_CSI = re.compile(rb"\x1b\[[<>=][0-9;:]*[A-Za-z]")


def sanitize(chunk: bytes) -> bytes:
    chunk = _OSC_HYPERLINK.sub(b"", chunk)
    chunk = _OSC_OTHER.sub(b"", chunk)
    chunk = _PRIVATE_MODES.sub(b"", chunk)
    chunk = _PRIVATE_CSI.sub(b"", chunk)
    chunk = _DA_QUERY.sub(b"", chunk)
    return chunk


class VTScreen:
    def __init__(self, cols=80, rows=25, default_attr=0x0E):
        self.cols, self.rows = cols, rows
        self.default_color = default_attr & 0x0F
        self.screen = pyte.Screen(cols, rows)
        self.stream = pyte.ByteStream(self.screen)
        self.bell_pending = False

    def feed(self, data: bytes):
        if b"\x07" in data:
            self.bell_pending = True
        self.stream.feed(sanitize(data))

    def title(self):
        return getattr(self.screen, "title", "") or ""

    def grid(self):
        """Current screen as rows x cols of (screen_code, attr)."""
        out = []
        buf = self.screen.buffer
        blank = (0x20, self.default_color)
        for y in range(self.rows):
            line = buf[y]
            row = [blank] * self.cols
            for x in range(self.cols):
                cell = line[x]
                ch = cell.data or " "
                # Combining marks / wide-char continuation cells arrive as
                # multi-codepoint strings; the first codepoint is the glyph.
                if len(ch) > 1:
                    ch = ch[0]
                code = petscii.to_screen_code(ch)

                fg = petscii.parse_color(cell.fg, self.default_color)
                fg = petscii.apply_intensity(fg, cell.bold, getattr(cell, "dim", False))
                attr = fg & 0x0F
                if cell.reverse:
                    attr |= 0x40
                if cell.underscore:
                    attr |= 0x20
                row[x] = (code, attr)
            out.append(row)
        return out

    def cursor(self):
        cur = self.screen.cursor
        if cur.hidden:
            return None
        y = max(0, min(self.rows - 1, cur.y))
        x = max(0, min(self.cols - 1, cur.x))
        return (y, x)

    def take_bell(self):
        rung, self.bell_pending = self.bell_pending, False
        return rung
