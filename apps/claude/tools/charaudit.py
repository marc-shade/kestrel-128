#!/usr/bin/env python3
"""Character coverage audit for the C128 renderer.

The terminal shows whatever Claude Code shows — file contents, code, command
output — so coverage cannot be argued from the chrome it happens to draw. This
sweeps the Unicode blocks a terminal realistically encounters and reports how
each character renders, so gaps are found before they appear on the screen as a
question mark.

  python3 tools/charaudit.py                 # per-block summary
  python3 tools/charaudit.py --gaps          # every uncovered character
  python3 tools/charaudit.py --file x.txt    # audit real text
  python3 tools/charaudit.py --capture x.raw # audit a captured PTY session
  python3 tools/charaudit.py --strict        # exit 1 if a must-cover block has gaps
"""
import argparse
import os
import sys
import unicodedata

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server"))

import petscii   # noqa: E402

# (name, first, last, must_cover)
#
# must_cover marks blocks where a fallback would be a visible defect: box
# drawing and blocks are what Claude Code's own UI is built from, and Latin text
# is the content. The rest are recorded but not required — a missing CJK
# ideograph is a legible '?', not a broken screen.
BLOCKS = [
    ("ASCII printable",        0x0020, 0x007E, True),
    ("Latin-1 Supplement",     0x00A0, 0x00FF, True),
    ("Latin Extended-A",       0x0100, 0x017F, True),
    ("Latin Extended-B",       0x0180, 0x024F, False),
    ("Greek",                  0x0370, 0x03FF, False),
    ("Cyrillic",               0x0400, 0x04FF, False),
    ("General Punctuation",    0x2000, 0x206F, True),
    ("Superscripts/Subscript", 0x2070, 0x209F, False),
    ("Currency Symbols",       0x20A0, 0x20BF, False),
    ("Letterlike Symbols",     0x2100, 0x214F, False),
    ("Number Forms",           0x2150, 0x218F, False),
    ("Arrows",                 0x2190, 0x21FF, False),
    ("Mathematical Operators", 0x2200, 0x22FF, False),
    ("Misc Technical",         0x2300, 0x23FF, False),
    ("Control Pictures",       0x2400, 0x243F, False),
    ("Box Drawing",            0x2500, 0x257F, True),
    ("Block Elements",         0x2580, 0x259F, True),
    ("Geometric Shapes",       0x25A0, 0x25FF, True),
    ("Misc Symbols",           0x2600, 0x26FF, False),
    ("Dingbats",               0x2700, 0x27BF, False),
    ("Braille Patterns",       0x2800, 0x28FF, True),
    ("Private Use (powerline)", 0xE000, 0xE0FF, False),
]

UNKNOWN = 0x3F          # what an unrenderable character becomes


def classify(ch):
    """How does this character reach the screen?

    Delegates to petscii.render_path, which distinguishes a deliberate
    stand-in from a failure - both produce screen code $3F for a character
    like the inverted question mark, so the code alone cannot tell them apart.
    """
    kind, code, via = petscii.render_path(ch)
    return ("UNKNOWN" if kind == petscii.UNMAPPED else via), code


def printable(cp):
    """Skip characters that are not real glyphs, so gaps mean something."""
    ch = chr(cp)
    cat = unicodedata.category(ch)
    return not (cat.startswith("C") or cat in ("Zl", "Zp"))


def audit_text(text):
    seen = {}
    for ch in text:
        if ch in seen or ch in "\r\n\t":
            continue
        seen[ch] = classify(ch)
    return seen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gaps", action="store_true", help="list uncovered characters")
    ap.add_argument("--file", help="audit the characters in a text file")
    ap.add_argument("--capture", help="audit a captured PTY byte stream")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 if a must-cover block has any gap")
    args = ap.parse_args()

    if args.file or args.capture:
        if args.capture:
            from vtscreen import VTScreen
            vt = VTScreen(80, 25)
            vt.feed(open(args.capture, "rb").read())
            text = "".join((vt.screen.buffer[y][x].data or " ")[:1]
                           for y in range(25) for x in range(80))
            label = f"capture {args.capture}"
        else:
            text = open(args.file, encoding="utf-8", errors="replace").read()
            label = f"file {args.file}"

        seen = audit_text(text)
        bad = {c: k for c, (k, _) in seen.items() if k == "UNKNOWN"}
        print(f"{label}: {len(seen)} distinct characters, {len(bad)} uncovered")
        for ch in sorted(bad, key=ord):
            print(f"  U+{ord(ch):04X} {ch!r}  {unicodedata.name(ch, '(unnamed)')}")
        return 1 if (bad and args.strict) else 0

    print(f"{'block':<24}{'chars':>6}{'covered':>9}{'gaps':>6}   must")
    print("-" * 60)
    failures = []
    for name, lo, hi, must in BLOCKS:
        chars = [chr(c) for c in range(lo, hi + 1) if printable(c)]
        gaps = [c for c in chars if classify(c)[0] == "UNKNOWN"]
        ok = len(chars) - len(gaps)
        flag = "yes" if must else "-"
        mark = "  <-- GAPS" if (gaps and must) else ""
        print(f"{name:<24}{len(chars):>6}{ok:>9}{len(gaps):>6}   {flag}{mark}")
        if gaps and must:
            failures.append((name, gaps))
        if args.gaps and gaps:
            for c in gaps:
                print(f"      U+{ord(c):04X} {c!r} {unicodedata.name(c, '(unnamed)')}")

    if failures:
        print("\nmust-cover blocks with gaps:")
        for name, gaps in failures:
            sample = " ".join(f"U+{ord(c):04X}" for c in gaps[:12])
            more = f" (+{len(gaps) - 12} more)" if len(gaps) > 12 else ""
            print(f"  {name}: {len(gaps)} -> {sample}{more}")
        return 1 if args.strict else 0

    print("\nno gaps in any must-cover block")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
