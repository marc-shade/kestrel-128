# VT52 terminal, first build — 2026-09-26

`src/native/vt52.asm` ([NATIVE-VT52](../../NATIVE-VT52.md)): Atari VT52
sequences on the 80-column VDC over the SwiftLink ACIA. It is on the GEM
disk as `vt52`.

## Evidence

`tests/ci_native_vt52.py` → `vt52.json`: 9/9 cases (Py65; image
`vt52.prg` SHA-256 `d7c24c08…`, 3,338 bytes packed). The harness is the
Claude client's `TerminalMachine`. It models the ACIA and the VDC and
delivers each received byte as an NMI through the ROM stubs. After every
step, the test compares the VDC's 2,000 characters and 2,000 attributes,
the hardware cursor and the background register with the independent model
in `tests/native_vt52_scene.py`. On exit, the Claude harness's restore
checks run: font, VDC registers, 40/80 setting, NMI vector and gate,
function keys, border, and every heap page released.

Four planted bugs, each rebuilt in a copy of the tree, all fail:

| Planted bug | First failing case |
|---|---|
| ESC K leaves the last column | erase to end of line (after adding text up to column 79; before that it survived) |
| Cursor left sends ESC A | the keyboard case |
| The saved font is not restored | "font leaked" in the restore checks |
| A full ring overwrites (the mutant also broke normal receive) | text, CR LF, tab |

Bugs found while testing, all fixed:
- the cursor was not placed before the first key wait;
- a row count stopped after 4 rows when the addition carried, which cut
  delete-line copies short;
- the transmit routine clobbered the cursor-key index, so every arrow sent
  ESC A.

## Limits

CPU level only; not run in VICE, on a C128, or against the Ultimate's modem
emulation. There is no flow control (RTS stays on) and no bell. It is a
foreground app, not an accessory. Colours are VDC numbers, and ESC c sets
the whole screen's background.
