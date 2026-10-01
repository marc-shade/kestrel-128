"""C128 keyboard (PETSCII) -> the bytes a Unix terminal application expects.

Translation lives on this side rather than in the C128 client so the key map
can change without rebuilding and redeploying a disk image.

The case swap is the classic PETSCII trap: an unshifted letter key produces
$41-$5A, which is *lowercase* in the C128's lowercase charset, while a shifted
letter produces $C1-$DA. Sending $41-$5A straight through would give Claude
Code nothing but capitals.
"""

RETURN = 0x0D
STOP = 0x03
DEL = 0x14
ESC = 0x1B
TAB = 0x09
HOME = 0x13
CLR = 0x93
INS = 0x94

CRSR_DOWN, CRSR_UP = 0x11, 0x91
CRSR_RIGHT, CRSR_LEFT = 0x1D, 0x9D

# Function keys. F1-F4 are convenience shortcuts for Claude Code; F5-F8 send
# the conventional VT sequences.
FUNCTION_KEYS = {
    0x85: b"\x1b[A",      # F1  -> previous input (history up)
    0x89: b"\x1b[B",      # F2  -> next input
    0x86: b"\x1b\x1b",    # F3  -> double ESC (clear input / rewind menu)
    0x8A: b"\x03",        # F4  -> interrupt
    0x87: b"\x1bOR",      # F5
    0x8B: b"\x1bOS",      # F6
    0x88: b"\x1b[15~",    # F7
    0x8C: b"\x1b[17~",    # F8
}

SPECIAL = {
    RETURN: b"\r",
    STOP: b"\x03",
    DEL: b"\x7f",
    ESC: b"\x1b",
    TAB: b"\t",
    HOME: b"\x1b[H",
    CLR: b"\x1b[H",
    INS: b"\x1b[2~",
    CRSR_UP: b"\x1b[A",
    CRSR_DOWN: b"\x1b[B",
    CRSR_RIGHT: b"\x1b[C",
    CRSR_LEFT: b"\x1b[D",
    0x0A: b"\r",          # LINE FEED key
    0x08: b"\x7f",
}


def petscii_to_bytes(code: int) -> bytes:
    """Translate one key code from the C128 into terminal input bytes."""
    if code in FUNCTION_KEYS:
        return FUNCTION_KEYS[code]
    if code in SPECIAL:
        return SPECIAL[code]

    # Unshifted letters: PETSCII $41-$5A is lowercase on screen.
    if 0x41 <= code <= 0x5A:
        return bytes([code + 0x20])
    # Shifted letters.
    if 0xC1 <= code <= 0xDA:
        return bytes([code - 0x80])
    # Digits, punctuation and space pass through unchanged.
    if 0x20 <= code <= 0x40:
        return bytes([code])
    if code in (0x5B, 0x5D):
        return bytes([code])
    if code == 0x5C:
        return b"\\"
    if code == 0x5F:
        return b"_"
    if code == 0x5E:
        return b"^"
    # Ctrl-A..Ctrl-Z arrive as $01-$1A minus the codes claimed above.
    if 0x01 <= code <= 0x1A:
        return bytes([code])
    return b""


def translate(data: bytes) -> bytes:
    return b"".join(petscii_to_bytes(c) for c in data)
