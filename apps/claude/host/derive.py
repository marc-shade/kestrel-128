"""Rule-based character mapping driven by Unicode names.

The C128 shows whatever Claude Code shows, which is arbitrary text: file
contents, source code, command output. Enumerating every character that might
appear is hopeless, and every one that is missed reaches the screen as a
question mark, indistinguishable from a real one.

So instead of a table, the structure in the Unicode *name* is used. "BOX
DRAWINGS HEAVY DOWN AND LEFT" names its own arms, so the light-line glyph with
the same arms is the right answer without anyone listing all 128 box characters.
The same trick covers partial blocks, geometric shapes, arrows, Greek letters,
superscripts and most punctuation.

Everything here returns a single character that some other layer already knows
how to render, so this module never needs to know about screen codes.
"""
import unicodedata

# Box drawing resolved by which arms it has. Every character in U+2500-257F is
# some combination of these, whatever its weight or dash pattern.
_BOX_ARMS = {
    frozenset("LR"): "─", frozenset("L"): "─", frozenset("R"): "─",
    frozenset("UD"): "│", frozenset("U"): "│", frozenset("D"): "│",
    frozenset("DR"): "┌", frozenset("DL"): "┐",
    frozenset("UR"): "└", frozenset("UL"): "┘",
    frozenset("UDR"): "├", frozenset("UDL"): "┤",
    frozenset("DLR"): "┬", frozenset("ULR"): "┴",
    frozenset("UDLR"): "┼",
}
_BOX_ARCS = {
    frozenset("DR"): "╭", frozenset("DL"): "╮",
    frozenset("UR"): "╰", frozenset("UL"): "╯",
}

# Greek letters transliterate to the first letter of their Unicode name, which
# is right for nearly all of them; these are the ones where it is not.
_GREEK_FIX = {"ETA": "e", "PHI": "f", "CHI": "c", "PSI": "p", "OMEGA": "o",
              "THETA": "t", "XI": "x", "OMICRON": "o", "UPSILON": "u"}

_WORD_TO_DIGIT = {
    "ZERO": "0", "ONE": "1", "TWO": "2", "THREE": "3", "FOUR": "4",
    "FIVE": "5", "SIX": "6", "SEVEN": "7", "EIGHT": "8", "NINE": "9",
}

# Letters whose Unicode name is a word rather than a letter, so the base cannot
# be read off the name directly.
_NAMED_LETTERS = {
    "ENG": "n", "KRA": "k", "ETH": "d", "THORN": "t", "SCHWA": "e",
    "HWAIR": "h", "WYNN": "w", "YOGH": "y", "SHARP S": "s", "AE": "a",
    "OE": "o", "IJ": "i", "DZ": "d", "LJ": "l", "NJ": "n", "TZ": "t",
    "TURNED E": "e", "OPEN O": "o", "DOTLESS I": "i", "DOTLESS J": "j",
}

# Direction words -> a one-cell stand-in, used for arrows and triangles alike.
_DIRECTION = {
    "RIGHTWARDS": ">", "LEFTWARDS": "<", "UPWARDS": "^", "DOWNWARDS": "v",
    "RIGHT": ">", "LEFT": "<", "UP": "^", "DOWN": "v",
    "EAST": ">", "WEST": "<", "NORTH": "^", "SOUTH": "v",
}

# Plain name-contains rules, checked in order. First match wins, so the more
# specific phrases come first.
_CONTAINS = [
    ("ZERO WIDTH", ""), ("WORD JOINER", ""),
    ("NO-BREAK SPACE", " "), ("SPACE", " "), ("QUAD", " "),
    ("PLUS-MINUS", "+"),          # before MINUS, which would win on substring
    ("SOFT HYPHEN", "-"), ("HYPHEN", "-"), ("DASH", "-"),
    ("MINUS", "-"), ("PLUS", "+"), ("HORIZONTAL BAR", "-"), ("OVERLINE", "-"),
    ("DOUBLE QUOTATION MARK", '"'), ("QUOTATION MARK", "'"),
    ("DOUBLE PRIME", '"'), ("PRIME", "'"),
    ("APOSTROPHE", "'"), ("GRAVE", "'"), ("ACUTE", "'"),
    ("ELLIPSIS", "…"), ("BULLET", "·"), ("MIDDLE DOT", "·"),
    ("PERIOD CENTERED", "·"), ("ONE DOT LEADER", "."),
    ("DAGGER", "+"), ("PER MILLE", "%"), ("PER TEN THOUSAND", "%"),
    ("PILCROW", "P"), ("SECTION SIGN", "S"), ("NUMERO", "N"),
    ("MULTIPLICATION", "x"), ("DIVISION", "/"), ("SOLIDUS", "/"),
    ("FRACTION", "/"),
    ("SEPARATOR", " "),
    # Any negated relation becomes "#". Falling through to the positive form
    # (NOT TILDE -> "~", NOT EQUAL -> "=") would make the screen assert the
    # opposite of the truth, which is worse than an obvious stand-in.
    ("NOT SIGN", "-"), ("DOES NOT", "#"), ("NOT ", "#"), ("NEITHER", "#"),
    ("ALMOST EQUAL", "~"),
    ("LESS-THAN", "<"), ("GREATER-THAN", ">"),
    ("IDENTICAL", "="), ("EQUAL", "="), ("TILDE", "~"),
    ("INFINITY", "8"), ("SQUARE ROOT", "v"), ("SUMMATION", "E"),
    ("INTEGRAL", "J"), ("PARTIAL DIFFERENTIAL", "d"), ("INCREMENT", "D"),
    ("DEGREE", "*"), ("COPYRIGHT", "c"), ("REGISTERED", "r"),
    ("TRADE MARK", "t"), ("MICRO", "u"), ("OHM", "O"),
    ("CURRENCY", "$"), ("SIGN", "$"),          # currency block catch-all
    ("DOUBLE ANGLE QUOTATION", "<"),
    ("SINGLE LEFT-POINTING", "<"), ("SINGLE RIGHT-POINTING", ">"),
    ("INVERTED EXCLAMATION", "!"), ("INVERTED QUESTION", "?"),
    ("BROKEN BAR", "|"), ("VERTICAL LINE", "|"),
    ("REVERSED SEMICOLON", ";"), ("SEMICOLON", ";"),
    ("CLOSE UP", "-"), ("FLOWER PUNCTUATION", "*"),
    ("DOTTED CROSS", "+"), ("TRICOLON", ":"),
    ("DOT PUNCTUATION", ":"), ("DOT MARK", ":"), ("FOUR DOTS", ":"),
    ("COLON", ":"),
    ("LOW LINE", "_"), ("UNDERTIE", "_"),
    ("DOT LEADER", "."), ("CARET", "^"),
    ("REFERENCE MARK", "*"), ("ASTERISM", "*"),
    ("EXCLAMATION", "!"), ("QUESTION", "?"), ("INTERROBANG", "?"),
    ("CHARACTER TIE", "-"), ("MACRON", "-"), ("DIAERESIS", '"'),
    ("CEDILLA", ","), ("OGONEK", ","), ("BREVE", "'"), ("CARON", "'"),
    ("FEMININE ORDINAL", "a"), ("MASCULINE ORDINAL", "o"),
    ("PARALLELOGRAM", "/"), ("BULLSEYE", "◉"),
    ("CIRCULAR ARC", ")"),
    ("LOZENGE", "*"), ("DIAMOND", "*"), ("STAR", "*"), ("ASTERISK", "✳"),
    ("SNOWFLAKE", "✳"), ("SPARKLE", "✳"), ("BURST", "✳"),
    ("CHECK MARK", "✓"), ("BALLOT X", "✗"), ("MULTIPLICATION X", "✗"),
    ("HEAVY BALLOT", "✗"),
]


def derive(ch):
    """A single stand-in character, or None if nothing sensible applies."""
    try:
        name = unicodedata.name(ch)
    except ValueError:
        return None

    if name.startswith("BOX DRAWINGS"):
        return _box(name)
    if name.endswith("BLOCK") or "BLOCK" in name:
        got = _block(name)
        if got:
            return got
    if "TRIANGLE" in name or "POINTING" in name or "ARROW" in name:
        got = _by_direction(name)
        if got:
            return got
    if (("SQUARE" in name and "ROOT" not in name)
            or "RECTANGLE" in name or "CIRCLE" in name):
        got = _shape(name)
        if got:
            return got
    if name.startswith("GREEK "):
        got = _greek(name)
        if got:
            return got
    if name.startswith("LATIN "):
        got = _latin(name)
        if got:
            return got
    if name.startswith(("SUPERSCRIPT ", "SUBSCRIPT ")):
        word = name.split()[-1]
        if word in _WORD_TO_DIGIT:
            return _WORD_TO_DIGIT[word]
        if word == "SIGN":                       # SUPERSCRIPT PLUS SIGN etc.
            return "+"
        if len(word) == 1 and word.isalpha():    # SUPERSCRIPT LATIN LETTER N
            return word.lower() if "SMALL" in name else word

    for needle, repl in _CONTAINS:
        if needle in name:
            return repl
    return None


def _latin(name):
    """Any Latin letter reduces to its base letter.

    Covers modified letters ("H WITH STROKE"), ligatures ("LIGATURE IJ") and
    the ones named as words ("ENG", "LONG S") in one rule, so the Latin
    Extended blocks do not need enumerating.
    """
    upper = "CAPITAL" in name
    for key, base in _NAMED_LETTERS.items():
        if f"LETTER {key}" in name or f"LIGATURE {key}" in name:
            return base.upper() if upper else base

    for marker in (" LETTER ", " LIGATURE "):
        if marker in name:
            rest = name.split(marker, 1)[1].split()
            if not rest:
                return None
            # "LONG S" ends in the letter; "H WITH STROKE" starts with it.
            for token in (rest[-1], rest[0]):
                if len(token) == 1 and token.isalpha():
                    return token.lower() if not upper else token.upper()
            first = rest[0]
            if first.isalpha():
                return first[0].lower() if not upper else first[0].upper()
    return None


def _box(name):
    # Match whole words, not substrings: "QUADRUPLE" contains "UP", which
    # silently turned every quadruple-dash horizontal into an up-tee.
    words = set(name.replace("-", " ").split())
    arms = set()
    if "HORIZONTAL" in words:
        arms |= {"L", "R"}
    if "VERTICAL" in words:
        arms |= {"U", "D"}
    for word, arm in (("UP", "U"), ("DOWN", "D"), ("LEFT", "L"), ("RIGHT", "R")):
        if word in words:
            arms.add(arm)
    if "DIAGONAL" in name:
        if "UPPER RIGHT TO LOWER LEFT" in name:
            return "/"
        if "UPPER LEFT TO LOWER RIGHT" in name:
            return "\\"
        return "X"
    key = frozenset(arms)
    if "ARC" in name and key in _BOX_ARCS:
        return _BOX_ARCS[key]
    return _BOX_ARMS.get(key)


def _block(name):
    """Partial blocks snap to the nearest fraction the character ROM has."""
    eighths = None
    for word, digit in _WORD_TO_DIGIT.items():
        if f"{word} EIGHTHS" in name or f"{word} EIGHTH" in name:
            eighths = int(digit)
    if "ONE QUARTER" in name:
        eighths = 2
    elif "THREE QUARTERS" in name:
        eighths = 6
    elif "HALF" in name:
        eighths = 4
    if "FULL BLOCK" in name:
        return "█"
    if eighths is None:
        return None
    if "LOWER" in name:
        return "▁" if eighths <= 2 else ("▄" if eighths <= 5 else "█")
    if "UPPER" in name:
        return "▔" if eighths <= 2 else ("▀" if eighths <= 5 else "█")
    if "LEFT" in name:
        return "▎" if eighths <= 2 else ("▌" if eighths <= 5 else "█")
    if "RIGHT" in name:
        return "▐" if eighths <= 5 else "█"
    return None


def _by_direction(name):
    for word, ch in _DIRECTION.items():
        if word in name:
            return ch
    return None


def _shape(name):
    """Filled shapes read as solid, hollow ones as a light shade."""
    if "CIRCLE" in name:
        return "⏺" if "BLACK" in name else "◉"
    if "BLACK" in name:
        return "█"
    return "░"


def _greek(name):
    letter = name.split()[-1]
    if letter in _GREEK_FIX:
        base = _GREEK_FIX[letter]
    elif letter.isalpha():
        base = letter[0].lower()
    else:
        return None
    return base.upper() if "CAPITAL" in name else base
