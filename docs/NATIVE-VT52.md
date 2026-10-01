# VT52 terminal (`vt52`)

A native app that turns the C128 into an Atari-style VT52 terminal on the
80-column VDC. It talks to a SwiftLink-compatible ACIA at `$de00`, which is
what the Ultimate II+ modem emulation provides. On the GEM disk
(`target/native-desktop/gem.d81`) it is the file `vt52`. **F8** returns to
the desktop.

This covers the TOS parity rows "VT52 terminal" and, as an app, the VT52
text console. It is a foreground app, not a desk accessory: accessories need
the step 8 slot ([GEM-LAYER-DESIGN](GEM-LAYER-DESIGN.md)).

## Serial

19200 baud, 8N1, on the SwiftLink's doubled clock (control `$1E`, command
`$09`: DTR, receive interrupt, RTS on). The Claude client measured overruns
at 38400 during full repaints; 19200 was safe there.

Received bytes arrive by NMI into a 256-byte ring. The handler is installed
through the kernel's NMI gate (`N_NMIPTR`, vector `$0318` → `$1bf0`) and
leaves through ROM `$FF33`. When the ring is full, a byte is dropped and
counted (`vt_rx_dropped`); nothing already received is overwritten. RTS stays
asserted: there is no flow control yet. A non-serial NMI (RESTORE) ends the
session like F8. If the ACIA is absent, or its DTR is already on (another
owner), the terminal restores the screen and returns at once.

## Screen

The VDC shows 80 × 25 cells: characters at `$0000`, attributes at `$0800`.
The app saves the VDC's alternate character set (4 KiB) to an owned
allocation and loads the system's 8×8 ASCII font there. Every character
cell is then an ASCII code with attribute bit 7 set. Bit 6 is reverse video,
and bits 3–0 are the colour.

| Received | Action |
|---|---|
| 32–126 | Printed at the cursor; the cursor advances |
| CR, LF (also VT, FF), BS, Tab | Column 0; down (scrolling at the bottom); left; next multiple of 8 |
| BEL | The SID bell ([`sound.inc`](NATIVE-SERVICES.md)) |
| Other controls | Ignored |
| ESC A / B / C / D | Cursor up / down / right / left, stopping at the edges |
| ESC E / H | Clear the screen and home / home |
| ESC I | Up; at the top the screen moves down one line |
| ESC J / K | Erase to the end of the screen / line |
| ESC d / o / l | Erase from the start of the screen / line to the cursor / the whole line |
| ESC L / M | Insert / delete a line at the cursor (column 0) |
| ESC Y r c | Position: row r−32, column c−32, clamped to the screen |
| ESC b c / ESC c c | Foreground colour c & 15 / background colour c & 15 |
| ESC e / f | Cursor on / off |
| ESC j / k | Save / restore the cursor |
| ESC p / q | Reverse on / off |
| ESC v / w | Wrap at the end of a line on / off (on at start) |

Colours are VDC RGBI numbers, not Atari palette entries. The VDC has one
background colour for the whole text screen, so ESC c changes all of it.
With wrap on, printing in column 80 moves to the next line at once; with
wrap off, the last column is overwritten. Unknown escape letters are
ignored.

## Keyboard

Keys are sent as ASCII. Unshifted letters are lowercase and shifted letters
uppercase; digits, punctuation, Return, Esc, Tab and Ctrl-letters are sent
unchanged. Del sends backspace (8), and the cursor keys send ESC A–D. F8
leaves; the other function keys and graphics characters send nothing.

## Restoration

On F8 the terminal restores, in reverse order:
- the ACIA's control and command registers, and the NMI vector and gate;
- the font;
- the VDC registers (10–15, 18–21, 24–29, 32, 33);
- the 40/80-column screen setting;
- the programmable function keys.

It frees its allocation. This is the same contract as the Claude client.

## Verification

`tests/ci_native_vt52.py` (Py65) runs the loaded app with the Claude
harness's `TerminalMachine`, which models the ACIA and the VDC and
delivers NMIs through the ROM stubs. After each step it compares all 2,000
characters, 2,000 attributes and the cursor with the independent model in
`tests/native_vt52_scene.py`. Nine cases cover:
- startup: registers, vector, 80 columns, the font in VDC memory;
- every sequence in the table above;
- scrolling both ways;
- key translation;
- ring overflow;
- the restore checks, with and without an ACIA.

Not verified: VICE, real hardware, the Ultimate's modem emulation, flow
control under sustained input, and PAL/NTSC timing.
