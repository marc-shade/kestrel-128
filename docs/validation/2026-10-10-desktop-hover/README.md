# Hover and focus changes in every 80-column screen (2026-10-10)

## Why

After the [bank call and jump filter record](../2026-10-09-bank-call-and-pointer-jumps/README.md)
the 80-column desktop still lagged on the reference C128, most over the
application cards. Every pointer move over a control reports a hover, so that
movement can take focus back from the keyboard. The desktop answered each
one by highlighting the card again, even when it was already selected.

A Py65 audit of every app in 80-column mode (64 KiB VDC) then found that
moving inside a control was already pointer-only everywhere else, but that a
focus change was not:

- the VDC mirror re-sent each dirty 40-cell row in full (320 bitmap and 40
  colour bytes read from the heap, 720 VDC bytes written) although a focus
  change only recolours cells;
- Claude rebuilt its whole control panel on every focus change;
- Paint redrew its status line and message row on every frame the pointer
  moved over the canvas;
- the AES redrew every row of an open drop-down when the hovered item
  changed.

## Change

- **Desktop** (`desktop.asm`, `desktop/vdc.inc`, `vdc-service.asm`). A hover
  over the card already selected does nothing. A selection change rewrites
  the attribute rows and markers of only the card shown selected and the new
  one (`vd_shown`; a new or restored scene draws every card, `vd_render_all`),
  and the VIC surface recolours only those two cards (`gd_shown`).
- **Colour-only mirror rows** (`graphics/vdc-client.inc`,
  `graphics/vdc-mirror.inc`). An app marks a row dirtied only by `gfx_colors`
  with 2 and any other drawing with 1 (or-ed). The service writes just the
  80 attribute bytes of a row marked 2 on a 64 KiB VDC. GEMDESK, whose colours
  come from the AES, keeps marking 1 (`BP_COLOR_ROWS=0`) to stay inside its
  module window. The service's 50-byte row table became a computed offset, so
  it gained room (41 bytes free).
- **Claude** (`claude/gui.asm`). A focus change repaints the control drawn
  focused and the new focus only, and marks their rows colour-only.
- **Paint** (`paint/input.inc`, `paint/renderer.inc`). Canvas motion and
  strokes no longer redraw the status line; it is updated on the first
  sample without motion. When only the position changed, just the six digits
  of X and Y are rewritten (aligned glyph copy); otherwise the whole status
  line and message are drawn as before.
- **AES menus** (`aes-menu.inc`). A hover change by pointer or cursor key
  recolours the previous and the new row; opening a drop-down still draws it
  all.

## Measurements (Py65 model, cycles for one frame)

| Screen and case | Before | After |
|---|---:|---:|
| Desktop: move within the selected card | 425,686 | 33,787 |
| Desktop: onto the next card | 393,820 | 117,730 |
| Calculator: onto the next button, across / down | 349,266 / 647,971 | 90,031 / 129,524 |
| Controls: onto the next button, across / down | 384,616 / 671,900 | 125,208 / 153,335 |
| Files: onto the next button / file row | 356,000-362,817 | 96,915-98,458 |
| Editor: Open onto Save As | 353,975 | 94,582 |
| Paint: Pen onto Eraser | 648,432 | 130,256 |
| Paint: canvas onto Pen | 342,672 | 83,580 |
| Paint: each frame moving over the canvas | 2,561,391 | 35,430 |
| Paint: first still frame after moving (status update) | none | 566,655 |
| Claude: onto another control | 1,739,661-1,739,849 | 123,615-185,888 |
| GEMDESK drop-down: hover onto another item | 444,620 | 10,578 |
| AES menu test: cursor key onto another item | 319,773 | under 60,000 |

Moving within a control or over empty space stays pointer-only (about
23,000-37,000) in every app. Sheet has no hover highlight and was already
pointer-only.

## Hardware measurement

A measurement-only build (not committed) timed each bank-1 pointer update on
the reference C128 with CIA2 timer B while the pointer moved on the
80-column desktop: 637 updates, 18,561 cycles on average (3,595 to 25,598);
consecutive updates were 1 jiffy apart 66 times, 2 jiffies 389 times,
3 jiffies 77 times and 4 or more 102 times. A pointer update alone takes
about one frame, so plain motion still updates at roughly 30 Hz. That is not
changed here.

## Tests

- `ci_native_vdc_desktop --case core`, all four VDC configurations: a move
  within the selected card writes no more than the pointer's 96 data bytes;
  moving onto the next card writes no more than both pointer redraws, two
  markers and, with 64 KiB, four attribute rows. On the previous build the
  hover case fails (184 data writes).
- `ci_native_vdc_calc --group core`: moving onto the next button writes no
  more than two attribute rows and two pointer redraws on a 64 KiB VDC
  (previous build: 1,504).
- `ci_native_claude_vdc --case core`: the same for Claude's controls, three
  attribute rows allowed (previous build: 5,824).
- `ci_native_aes`: a pointer or cursor-key hover change in a drop-down costs
  under 60,000 cycles (previous build: 319,773 for the cursor key).
- `ci_native_paint_gui --case mouse`: while a stroke moves the pointer the
  status rows are unchanged and the stale flag is set; one still sample
  brings the status line up to date. Every Paint surface check now requires
  that update first.
- Every check still compares complete VDC bitmaps, all attributes and the VIC
  surfaces after each step.
- Full sweep (`tests/sweep_native.py` through the resumable driver, from a
  snapshot of this tree): CPU 323/323. VICE 60/60: the first pass had 57;
  `ci_native_desktop_iec --input-during-capture` expected the heap residue
  of the old seven-card highlight (its expectation now names card 2, the
  new selection, and the selected colour 7), and two
  `ci_native_pointer_iec` jobs (80 columns; Files open-with/Find on D81) hit
  the capture timeout recorded as unexplained on 2026-10-09 and passed when
  rerun one at a time.

## Hardware

Hardware `--native-desktop` on these exact images passed all eleven screens
(216 busy IRQs over 683 captures; no pointer retake was needed) after a
power-off. The same images failed once before it, on a machine powered for
many hours: two bytes of the Calculator result bitmap moved by one position,
the dropped-byte pattern of the overheated 8563 recorded on 2026-10-09. A
Py65 replay of that workflow's keys and pointer position matched the
expected VDC bitmap at every step on both VDC sizes.

On an interim build with only the desktop change the reference C128's owner
reported the desktop "less laggy" over the buttons.

## Known limits

- Paint's colour swatches show focus with an outline, which changes bitmap
  pixels, so crossing swatches still re-sends two full rows (469,201 cycles).
- A desktop card change still takes about seven frames, and the Paint status
  update after motion about half a second, in the model; both re-send whole
  rows that changed bitmap.

## Not verified

- Pointer update rate and focus-change cost on hardware after this change:
  the hardware timing above was taken before it and covers pointer moves.
- The 16 KiB VDC: colour-only rows are drawn in full there by design; the
  suites run both sizes, but no timing was taken for 16 KiB.
- GEMDESK in 80 columns presents only when `ae_event` returns; whether a
  drop-down's hover is visible on the VDC while the AES tracks the menu was
  not examined.
