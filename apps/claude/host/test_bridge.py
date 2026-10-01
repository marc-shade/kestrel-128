#!/usr/bin/env python3
"""Tests for the glyph map, the differ, and the ANSI -> C128 pipeline.

Run: python3 -m pytest server/test_bridge.py -q     (or execute directly)

Every assertion checks a contract that, if broken, puts wrong pixels on the
C128: dropped characters, wrong glyphs, wrong colours, or a diff that claims
the client is showing something it is not.
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import petscii                     # noqa: E402
import protocol                    # noqa: E402
from vtscreen import VTScreen      # noqa: E402


# --------------------------------------------------------------------------
# A model of the client: applies protocol bytes exactly as the C128 will.
# --------------------------------------------------------------------------
class ClientModel:
    def __init__(self, cols=80, rows=25, blank=(0x20, 0x0E)):
        self.cols, self.rows, self.blank = cols, rows, blank
        self.cells = [[blank] * cols for _ in range(rows)]
        self.cur = None
        self.frames = 0

    def clear(self, attr):
        self.cells = [[(0x20, attr)] * self.cols for _ in range(self.rows)]

    def run(self, row, col, attr, codes):
        for i, code in enumerate(codes):
            if row < self.rows and col + i < self.cols:
                self.cells[row][col + i] = (code, attr)

    def cursor(self, pos):
        self.cur = pos

    def scroll(self, top, bot, n, down):
        self.scrolls = getattr(self, "scrolls", 0) + 1
        self.cells = protocol.apply_scroll(self.cells, top, bot, n, down)

    def frame(self):
        self.frames += 1

    def bell(self):
        pass

    def panel(self, row, codes):
        pass


def text_grid(lines, cols=80, rows=25, attr=0x0E):
    """Build a grid from plain text, for readable test fixtures."""
    grid = [[(0x20, attr)] * cols for _ in range(rows)]
    for r, line in enumerate(lines[:rows]):
        for c, ch in enumerate(line[:cols]):
            grid[r][c] = (petscii.to_screen_code(ch), attr)
    return grid


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


class Skipped(Exception):
    """Raised when a check cannot run here - never counted as a pass."""


def skip(reason):
    raise Skipped(reason)


# --------------------------------------------------------------------------
def test_rom_verification():
    """The glyph table must match the real C128 character ROM.

    Skipped, loudly, where the ROM is absent - Debian and Ubuntu ship VICE
    without the Commodore ROMs for licensing reasons, so CI on those runners
    cannot do this check. A skip is not a pass and says so.
    """
    if not petscii.ROM_PATH:
        skip("no C128 character ROM; install VICE with ROMs or set CBM_CHARGEN")
    ok, errors = petscii.verify_against_rom()
    check(ok, "glyph table disagrees with the character ROM: " + "; ".join(errors))


def test_ascii_roundtrip():
    """Every printable ASCII character must survive text -> screen code."""
    inverse = {}
    for i in range(26):
        inverse[0x01 + i] = chr(ord("a") + i)
        inverse[0x41 + i] = chr(ord("A") + i)
    for c in range(0x20, 0x40):
        inverse[c] = chr(c)

    for o in range(0x20, 0x7F):
        ch = chr(o)
        code = petscii.to_screen_code(ch)
        check(0 <= code <= 255, f"{ch!r} produced out-of-range code {code}")
        if ch in inverse.values() or ch.isalnum() or 0x20 <= o <= 0x3F:
            back = inverse.get(code)
            if back is not None and (ch.isalnum() or 0x20 <= o <= 0x3F):
                check(back == ch, f"{ch!r} -> ${code:02X} -> {back!r} (case or map error)")


def test_no_glyph_collisions_with_letters():
    """Box/block glyphs must not land on $41-$5A, which charset 2 uses for A-Z."""
    for ch, code in petscii.GLYPHS.items():
        check(
            not (0x41 <= code <= 0x5A),
            f"glyph U+{ord(ch):04X} uses ${code:02X}, which is a letter in charset 2",
        )


def test_differ_preserves_every_character():
    """The exact bug this suite exists for: a run losing its last character."""
    lines = [
        "SessionStart:startup hook error",
        "Failed to run: EROFS: read-only file system, mkdir",
        "a b c d e f g",                       # short words, gap-sized holes
        "x" + " " * 5 + "y" + " " * 6 + "z",   # holes at and past the tolerance
        "end",
    ]
    grid = text_grid(lines)
    differ = protocol.ScreenDiffer()
    client = ClientModel()
    protocol.decode(differ.diff(grid, (0, 0)), client)
    check(client.cells == grid, "client screen differs from the intended grid")


def test_differ_incremental_matches_full_repaint():
    """After N random edits the client must match the source exactly."""
    rng = random.Random(1234)
    differ = protocol.ScreenDiffer()
    client = ClientModel()
    grid = [[(0x20, 0x0E)] * 80 for _ in range(25)]
    protocol.decode(differ.diff(grid, None), client)

    for step in range(60):
        for _ in range(rng.randint(1, 40)):
            r, c = rng.randrange(25), rng.randrange(80)
            grid[r][c] = (rng.randrange(0x20, 0x60), rng.choice([0x0E, 0x0D, 0x01, 0x4E]))
        protocol.decode(differ.diff(grid, (0, 0)), client)
        check(client.cells == grid, f"drift from source at step {step}")


def test_differ_sends_nothing_when_idle():
    grid = text_grid(["stable"])
    differ = protocol.ScreenDiffer()
    differ.diff(grid, (0, 0))
    second = differ.diff(grid, (0, 0))
    check(second == bytes((protocol.CMD_FRAME,)),
          f"idle frame should be a bare FRAME, got {second!r}")


def test_differ_is_smaller_than_full_repaint():
    base = text_grid([f"line {i} of output" for i in range(25)])
    differ = protocol.ScreenDiffer()
    full = differ.diff(base, (0, 0))
    changed = [list(row) for row in base]
    changed[24] = list(text_grid(["a new line of streamed text"])[0])
    delta = differ.diff(changed, (0, 0))
    check(len(delta) < len(full) / 4,
          f"delta {len(delta)}B not much smaller than full {len(full)}B")


def test_scroll_model_matches_hand_written_expectations():
    """apply_scroll is the reference the 6502 must match; pin it literally.

    A block copy does not erase its source, so the trailing-edge rows keep
    their old content - that invariant is load-bearing for the differ and is
    asserted here on grids small enough to write out by hand.
    """
    def rows(*names):
        return [[(ord(n), 0x0E)] * 4 for n in names]

    grid = rows("a", "b", "c", "d", "e")
    up = protocol.apply_scroll(grid, 1, 3, 1, down=False)
    check(up == rows("a", "c", "d", "d", "e"),
          "up-scroll must shift rows 1..3 and leave the source of row 3")
    down = protocol.apply_scroll(grid, 1, 3, 1, down=True)
    check(down == rows("a", "b", "b", "c", "e"),
          "down-scroll must shift rows 1..3 and leave the source of row 1")
    two = protocol.apply_scroll(grid, 0, 4, 2, down=False)
    check(two == rows("c", "d", "e", "d", "e"), "two-row up-scroll of the lot")

    for bad in ((3, 1, 1, False),       # top below bottom
                (0, 9, 1, False),       # bottom off a 5-row screen
                (0, 4, 0, False),       # zero shift
                (1, 3, 3, False)):      # shift larger than the region
        check(protocol.apply_scroll(grid, *bad) == grid,
              f"nonsense bounds {bad} must be a no-op, as on the client")


def test_scroll_shrinks_a_scrolling_frame():
    """A one-line transcript scroll must cost a few bytes, not a repaint.

    The same frame pair runs through a scroll-enabled and a scroll-disabled
    differ; both must leave the client exactly right, and the scroll encoding
    must be dramatically smaller - this is the entire point of the opcode.
    """
    base = [f"transcript line {i} with some text" for i in range(25)]
    scrolled = base[1:] + ["a fresh line of streamed output"]

    sizes = {}
    for enabled in (True, False):
        differ = protocol.ScreenDiffer(scroll=enabled)
        client = ClientModel()
        protocol.decode(differ.diff(text_grid(base), (0, 0)), client)
        frame = differ.diff(text_grid(scrolled), (0, 0))
        protocol.decode(frame, client)
        check(client.cells == text_grid(scrolled),
              f"client drifted from the grid (scroll={enabled})")
        sizes[enabled] = len(frame)
        if enabled:
            check(differ.scrolls_used == 1, "the scroll path was not taken")
            check(getattr(client, "scrolls", 0) == 1,
                  "the client never saw a SCROLL command")

    check(sizes[True] < sizes[False] / 4,
          f"scroll frame {sizes[True]}B not much smaller "
          f"than plain {sizes[False]}B")


def test_scroll_region_with_fixed_footer():
    """Claude Code's shape: transcript scrolls, input box and statusline sit
    still. The scroll must cover only the moving region and the fixed rows
    must never be touched."""
    transcript = [f"line {i}: output scrolling past" for i in range(21)]
    footer = ["+--------- input box ---------+",
              "| > _                         |",
              "+-----------------------------+",
              "statusline: model - cwd - git"]
    differ = protocol.ScreenDiffer()
    client = ClientModel()
    protocol.decode(differ.diff(text_grid(transcript + footer), (0, 0)), client)

    moved = transcript[1:] + ["line 21: the newest output"] + footer
    frame = differ.diff(text_grid(moved), (0, 0))
    protocol.decode(frame, client)
    check(client.cells == text_grid(moved), "client drifted after region scroll")
    check(differ.scrolls_used == 1, "region scroll was not chosen")
    check(len(frame) < 100,
          f"a one-line region scroll cost {len(frame)}B; expected tens")


def test_scroll_down_roundtrip():
    """Scrolling back through history shifts rows the other way."""
    base = [f"history line {i}" for i in range(25)]
    differ = protocol.ScreenDiffer()
    client = ClientModel()
    protocol.decode(differ.diff(text_grid(base), (0, 0)), client)

    back = ["an older line re-entering view"] + base[:-1]
    frame = differ.diff(text_grid(back), (0, 0))
    protocol.decode(frame, client)
    check(client.cells == text_grid(back), "client drifted after down-scroll")
    check(differ.scrolls_used == 1, "down-scroll path was not taken")


def test_differ_incremental_with_scrolls_matches_source():
    """Random edits interleaved with random region shifts: the client must
    track the source exactly at every step, whichever encoding the differ
    picks. This is the equivalence contract the whole feature hangs on."""
    rng = random.Random(4321)
    differ = protocol.ScreenDiffer()
    client = ClientModel()
    grid = text_grid([f"row {i} " + "x" * rng.randint(0, 60) for i in range(25)])
    protocol.decode(differ.diff(grid, None), client)

    for step in range(80):
        if rng.random() < 0.5:
            # Shift a random region, filling the exposed rows with new text.
            top = rng.randrange(0, 20)
            bot = rng.randrange(top + 1, 25)
            n = rng.randint(1, min(3, bot - top))
            body = [list(r) for r in grid]
            newline = lambda: list(text_grid(
                [f"step {step} " + "y" * rng.randint(0, 40)])[0])
            if rng.random() < 0.7:
                body[top:bot - n + 1] = [list(r) for r in body[top + n:bot + 1]]
                body[bot - n + 1:bot + 1] = [newline() for _ in range(n)]
            else:
                body[top + n:bot + 1] = [list(r) for r in body[top:bot - n + 1]]
                body[top:top + n] = [newline() for _ in range(n)]
            grid = body
        else:
            for _ in range(rng.randint(1, 30)):
                r, c = rng.randrange(25), rng.randrange(80)
                grid[r][c] = (rng.randrange(0x20, 0x60),
                              rng.choice([0x0E, 0x0D, 0x01, 0x4E]))
        protocol.decode(differ.diff(grid, (0, 0)), client)
        check(client.cells == grid, f"drift from source at step {step}")
    check(differ.scrolls_used > 0,
          "80 shifty steps never took the scroll path; detection is dead")


def test_real_claude_capture_renders():
    """The end-to-end path on genuine Claude Code output."""
    root = os.path.join(os.path.dirname(__file__), "..")
    cap = os.path.join(root, "tests", "fixtures", "render_sample.raw")
    if not os.path.exists(cap):
        cap = os.path.join(root, "docs", "claude_clean.raw")
    if not os.path.exists(cap):
        skip("no render fixture")
    raw = open(cap, "rb").read()
    vt = VTScreen(80, 25)
    vt.feed(raw)
    grid = vt.grid()
    differ = protocol.ScreenDiffer()
    client = ClientModel()
    protocol.decode(differ.diff(grid, vt.cursor()), client)
    check(client.cells == grid, "client render differs from the emulated screen")

    # The capture contains Claude Code's horizontal rules; they must survive
    # as the PETSCII horizontal line, not as '?' fallbacks.
    rule = petscii.GLYPHS["─"]
    check(any(sum(1 for code, _ in row if code == rule) > 40 for row in grid),
          "no horizontal rule row survived the conversion")
    unknown = sum(1 for row in grid for code, _ in row if code == 0x3F)
    check(unknown < 40, f"{unknown} cells fell back to '?' - glyph map too thin")


def test_private_prefix_csi_is_stripped():
    """Kitty-keyboard and modifyOtherKeys sequences must never reach pyte.

    pyte does not understand a `<`, `>` or `=` private prefix on a CSI. Left in,
    ESC[<u and ESC[>1u print a literal "u" at the cursor, and ESC[>4;2m is
    applied as SGR 4 and switches underline on for the rest of the screen. Both
    were seen on real hardware: a stray "u" in the top-left corner and a rule
    under every line.
    """
    from vtscreen import sanitize

    probe = (b"\x1b[<u\x1b[>1u\x1b[>4;2m\x1b[>0q"
             b"hello\x1b[<u world")
    assert_clean = sanitize(probe)
    check(b"u" not in assert_clean.replace(b"hello", b"").replace(b" world", b""),
          f"private CSI survived sanitize: {assert_clean!r}")

    vt = VTScreen(80, 25)
    vt.feed(b"\x1b[H\x1b[<u\x1b[>1u\x1b[>4;2m")
    grid = vt.grid()
    check(grid[0][0][0] == 0x20,
          f"cell (0,0) is ${grid[0][0][0]:02X}, expected a space - "
          f"a private-prefix CSI leaked a literal character")
    underlined = sum(1 for row in grid for _, a in row if a & 0x20)
    check(underlined == 0,
          f"{underlined} cells underlined after modifyOtherKeys - "
          f"ESC[>4;2m was parsed as SGR 4")


def test_osc_hyperlink_payload_never_renders():
    """OSC 8 URLs are far longer than their visible text and must not print."""
    vt = VTScreen(80, 25)
    vt.feed(b"\x1b[H\x1b]8;id=1;https://example.com/a/very/long/url\x07link\x1b]8;;\x07")
    row = "".join(chr(c) if 0x20 <= c < 0x40 else "?" for c, _ in vt.grid()[0][:40])
    check("https" not in row and "example" not in row,
          f"hyperlink payload rendered as text: {row!r}")


def test_font_slots_are_free():
    """A custom glyph must never overwrite a character PETSCII already uses."""
    import font

    clashes = sorted(set(font.CODES.values()) & set(petscii.GLYPHS.values()))
    check(not clashes,
          "custom glyphs would overwrite PETSCII characters at "
          + ", ".join(f"${c:02X}" for c in clashes))
    # The reserved list must actually cover everything GLYPHS claims up there.
    high = {c for c in petscii.GLYPHS.values() if c >= 0xA0}
    missing = sorted(high - font.RESERVED)
    check(not missing,
          "font.RESERVED misses PETSCII codes "
          + ", ".join(f"${c:02X}" for c in missing))


def test_custom_glyphs_win_over_substitutes():
    """Characters with a real glyph must not fall back to an ASCII stand-in."""
    import font

    for ch in ("❯", "⏺", "✳", "⎿", "…", "·", "←", "╭", "╮", "╰", "╯"):
        code = petscii.to_screen_code(ch)
        check(code == font.CODES[ch],
              f"{ch!r} rendered as ${code:02X}, expected the custom "
              f"glyph ${font.CODES[ch]:02X}")
    # Every bitmap is 8 rows of 8 bits.
    for code, bmp in font.definitions():
        check(len(bmp) == 8, f"glyph ${code:02X} has {len(bmp)} rows")
        check(all(0 <= b <= 255 for b in bmp), f"glyph ${code:02X} out of range")


def test_ascii_that_charset2_breaks_has_a_glyph():
    """Backslash, braces, tilde and caret must not render as letters.

    Charset 2 reassigns $41-$5A to A-Z, so the PETSCII codes for these land on
    letters or box drawing - a backslash came out as "M". In a tool for reading
    code that is not cosmetic.
    """
    import font

    for ch in ("\\", "{", "}", "~", "^"):
        code = petscii.to_screen_code(ch)
        check(code == font.CODES[ch],
              f"{ch!r} renders as ${code:02X}, not its glyph")
        check(not (0x41 <= code <= 0x5A),
              f"{ch!r} maps to ${code:02X}, which charset 2 draws as a letter")


def test_no_letter_lookalike_fallbacks():
    """Claude Code's bullets and spinners must not render as letters.

    The substitute table maps the whole circle family to "o" and the asterisk
    family to "*", which on screen reads as a word character in the middle of a
    sentence - "o AUTOBOOT OK" was showing on the real machine. Every one of
    these must resolve to a drawn glyph or a real PETSCII shape instead.
    """
    import font

    LETTER_LOOKALIKES = {
        petscii.to_screen_code("o"), petscii.to_screen_code("O"),
        petscii.to_screen_code("*"), petscii.to_screen_code("y"),
        petscii.to_screen_code("x"), petscii.to_screen_code("|"),
    }
    # Everything Claude Code has been observed to emit as a marker.
    MARKERS = "⏺●○◉⏹•‣✳✻✶✷✴✽❯›→▸▶↳⎿⏱⏸✓✗…·←"
    bad = []
    for ch in MARKERS:
        code = petscii.to_screen_code(ch)
        if code in LETTER_LOOKALIKES and ch not in petscii.GLYPHS:
            bad.append(f"U+{ord(ch):04X} {ch!r} -> ${code:02X}")
    check(not bad,
          "these render as letter/ASCII lookalikes: " + ", ".join(bad))

    # And none of them may fall through to '?'.
    unknown = [f"U+{ord(c):04X} {c!r}" for c in MARKERS
               if petscii.to_screen_code(c) == 0x3F]
    check(not unknown, "unmapped markers: " + ", ".join(unknown))


def test_glyph_aliases_point_at_real_glyphs():
    """Every alias must resolve to a slot that actually has a bitmap."""
    import font

    for alias, target in font.ALIASES.items():
        if alias not in font.CODES:
            continue                      # target is plain PETSCII, fine
        code = font.CODES[alias]
        check(code in font.BITMAPS,
              f"alias {alias!r} -> ${code:02X} has no bitmap")
        check(font.CODES[alias] == font.CODES[target],
              f"alias {alias!r} does not match its target {target!r}")


def test_accented_letters_fold_to_their_base(): 
    """"Sautéed" must not render as "Saut?ed".

    Claude Code reaches for words with accents, and a '?' mid-word reads as
    corruption rather than as a missing accent. Everything here has to land on
    the base letter, one cell wide so columns stay aligned.
    """
    inv = petscii.inverse_map()
    cases = {
        "é": "e", "è": "e", "ê": "e", "ë": "e",
        "á": "a", "à": "a", "â": "a", "ä": "a", "å": "a",
        "í": "i", "ó": "o", "ô": "o", "ö": "o", "ú": "u", "ü": "u",
        "ñ": "n", "ç": "c", "ý": "y",
        "É": "E", "Ü": "U", "Ñ": "N",
        "ø": "o", "æ": "a", "œ": "o", "ß": "s", "ł": "l", "þ": "t",
    }
    bad = []
    for ch, want in cases.items():
        got = inv.get(petscii.to_screen_code(ch))
        if got != want:
            bad.append(f"{ch!r}->{got!r} (want {want!r})")
    check(not bad, "accent folding wrong for: " + ", ".join(bad))


def test_every_must_cover_block_is_complete():
    """No character in a must-cover Unicode block may reach the screen as '?'.

    The terminal shows arbitrary text - file contents, source, command output -
    so coverage cannot be argued from the chrome Claude Code happens to draw.
    This is the same sweep tools/charaudit.py runs, pinned as a test.
    """
    import unicodedata

    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", "tools"))
    import charaudit

    problems = []
    for name, lo, hi, must in charaudit.BLOCKS:
        if not must:
            continue
        for cp in range(lo, hi + 1):
            ch = chr(cp)
            if unicodedata.category(ch).startswith("C"):
                continue
            kind, _, _ = petscii.render_path(ch)
            if kind == petscii.UNMAPPED:
                problems.append(f"{name} U+{cp:04X} "
                                f"{unicodedata.name(ch, '(unnamed)')}")
    check(not problems,
          f"{len(problems)} uncovered: " + "; ".join(problems[:8]))


def test_box_drawing_reduces_to_matching_arms():
    """Heavy, double and dashed box characters must keep their shape.

    Every character in U+2500-257F is some combination of up/down/left/right
    arms, so each must land on the light-line glyph with the same arms - not on
    a different junction. A substring match on "UP" inside "QUADRUPLE" turned
    every quadruple-dash horizontal into an up-tee, which this pins.
    """
    inv = petscii.inverse_map()
    cases = {
        "━": "─", "┃": "│", "═": "─", "║": "│",       # heavy and double lines
        "┄": "─", "┅": "─", "┈": "─", "┉": "─",       # dashed horizontals
        "┆": "│", "┇": "│", "┊": "│", "┋": "│",       # dashed verticals
        "┏": "┌", "┓": "┐", "┗": "└", "┛": "┘",       # heavy corners
        "╔": "┌", "╗": "┐", "╚": "└", "╝": "┘",       # double corners
        "┣": "├", "┫": "┤", "┳": "┬", "┻": "┴", "╋": "┼",
        "╠": "├", "╣": "┤", "╦": "┬", "╩": "┴", "╬": "┼",
    }
    bad = [f"{c}->{inv.get(petscii.to_screen_code(c))!r} (want {w!r})"
           for c, w in cases.items()
           if inv.get(petscii.to_screen_code(c)) != w]
    check(not bad, "box drawing mis-mapped: " + ", ".join(bad))


def test_negation_is_never_folded_away():
    """A combining slash must not be dropped: it inverts the meaning.

    NFD-decomposing accented letters is right, but the same decomposition turns
    U+2260 NOT EQUAL TO into "=", which is worse than any fallback because the
    screen would then assert the opposite of the truth.
    """
    inv = petscii.inverse_map()
    for ch, forbidden in (("≠", "="), ("∉", "e"), ("∌", "e"),
                          ("≁", "~"), ("≄", "=")):
        got = inv.get(petscii.to_screen_code(ch))
        check(got != forbidden,
              f"{ch!r} folded to {got!r}, which reverses its meaning")


def test_stand_ins_are_exactly_one_cell():
    """A multi-character stand-in would shift every column after it."""
    import font

    for ch, sub in petscii.SUBSTITUTES.items():
        check(len(sub) <= 1,
              f"substitute for {ch!r} is {sub!r}, more than one cell")
    for alias, target in font.ALIASES.items():
        check(len(target) == 1, f"alias target {target!r} is not one character")


def test_colors_map_to_claude_identity():
    # Both machines, because they do not share a palette and a colour chosen for
    # one is wrong on the other.
    try:
        for machine, yellow, white, dim in (("c128", 13, 15, 14),
                                            ("c64", 7, 1, 15)):
            pal = petscii.use_machine(machine)
            # The logo shade is chosen, not nearest-matched: its real salmon
            # lands on grey, which is indistinguishable from body text.
            check(petscii.rgb_to_index(0xD7, 0x87, 0x87) == pal.logo,
                  f"{machine}: logo colour not pinned")
            check(petscii.rgb_to_index(0xD7, 0x77, 0x57) == pal.logo,
                  f"{machine}: older logo shade not pinned")
            # Grey is the one thing it must not be: that is the body-text
            # colour, and the logo would vanish into the surrounding box.
            check(pal.logo not in (pal.light_grey, pal.dark_grey),
                  f"{machine}: logo colour must not be grey")
            check(petscii.rgb_to_index(0xFF, 0xC1, 0x07) == yellow,
                  f"{machine}: amber warning mismapped")
            check(petscii.rgb_to_index(0x00, 0x00, 0x00) == 0,
                  f"{machine}: black mismapped")
            check(petscii.rgb_to_index(0xFF, 0xFF, 0xFF) == white,
                  f"{machine}: white mismapped")
            check(petscii.parse_color("999999", 0) == dim,
                  f"{machine}: dim grey mismapped")
            check(petscii.parse_color("default", 7) == 7,
                  f"{machine}: default colour not honoured")
    finally:
        petscii.use_machine("c128")


def test_logo_is_the_orange_in_each_palette():
    """The logo must be the orange/brown its own palette actually has.

    Asserted against the RGB the palette entry holds, not against an index:
    an index alone would still pass if the two machines' tables were swapped,
    which is exactly the mistake this guards against.
    """
    try:
        for machine in ("c128", "c64"):
            pal = petscii.use_machine(machine)
            r, g, b = pal.table[pal.logo]
            check(r > b and g > b, f"{machine}: logo colour is not warm "
                                   f"(#{r:02X}{g:02X}{b:02X})")
            check(r > g, f"{machine}: logo colour is not red-dominant "
                         f"(#{r:02X}{g:02X}{b:02X})")
            # A salmon or pink has a high blue component; an orange does not.
            check(b <= 0x40, f"{machine}: logo colour reads as pink, not orange "
                             f"(#{r:02X}{g:02X}{b:02X})")
    finally:
        petscii.use_machine("c128")


def test_render_kind_is_not_shadowed_by_the_colour_table():
    """EXACT is the render-path kind, and must stay a string.

    The colour pin table was once also called EXACT at module level, which
    silently rebound this constant to a dict. Nothing compared against it, so it
    never bit - but the next person to write `kind == petscii.EXACT` would have
    got a very confusing afternoon.
    """
    check(petscii.EXACT == "exact", "EXACT is no longer the render-path kind")
    kind, _, _ = petscii.render_path("A")
    check(kind == petscii.EXACT, "render_path did not report an exact match")
    check(isinstance(kind, str), f"render kind should be a string, got {type(kind).__name__}")
    # Switching machines must not disturb it.
    try:
        petscii.use_machine("c64")
        check(petscii.EXACT == "exact", "use_machine clobbered the render kind")
    finally:
        petscii.use_machine("c128")


def test_palettes_are_not_interchangeable():
    """The C64 must not be driven with VDC indices.

    Both machines take a colour index over the same wire, so nothing downstream
    can catch a palette mix-up - the screen just comes out the wrong colour. The
    tables genuinely differ, and this pins that they are being kept apart.
    """
    check(petscii.VDC.table != petscii.VICII.table,
          "the two palettes are identical - one of them is wrong")
    # Index 12 is the case that bites: a brown on the VDC, a grey on the VIC-II.
    check(petscii.VDC.table[12] != petscii.VICII.table[12],
          "index 12 should differ between the machines")
    check(petscii.VDC.names["red"] != petscii.VICII.names["red"],
          "named colours should differ between the machines")
    try:
        check(petscii.use_machine("c64").name == "c64", "use_machine ignored")
        check(petscii.ACTIVE is petscii.VICII, "active palette not switched")
        check(petscii.use_machine("c128").name == "c128", "use_machine ignored")
        check(petscii.ACTIVE is petscii.VDC, "active palette not restored")
    finally:
        petscii.use_machine("c128")


def test_run_length_chunking():
    """A run longer than 255 must split without losing or duplicating cells."""
    enc = protocol.Encoder()
    codes = [(i % 0x40) + 0x20 for i in range(300)]
    enc.run(0, 0, 0x0E, codes)
    client = ClientModel(cols=320)
    protocol.decode(enc.take(), client)
    check([c[0] for c in client.cells[0][:300]] == codes, "long run corrupted")


def main():
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    failed, skipped = [], []
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
        except Skipped as exc:
            skipped.append((name, str(exc)))
            print(f"  SKIP  {name}: {exc}")
        except AssertionError as exc:
            failed.append(name)
            print(f"  FAIL  {name}: {exc}")
        except Exception as exc:                      # noqa: BLE001
            failed.append(name)
            print(f"  ERROR {name}: {type(exc).__name__}: {exc}")

    passed = len(tests) - len(failed) - len(skipped)
    line = f"\n{passed}/{len(tests)} passed"
    if skipped:
        line += f", {len(skipped)} SKIPPED (not verified)"
    if failed:
        line += f", {len(failed)} failed"
    print(line)
    for name, why in skipped:
        print(f"  not verified: {name} - {why}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
