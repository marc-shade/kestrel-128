# AES windows (GEM layer step 5a) — 2026-09-25

The persistent AES gains GEM windows (AES minor 4, capability bit 3):
create, open, close, delete, set, get, find, fill and surface
sub-operations. The RAM tables move into a 16-page owner-30 data segment at
bank-1 `$5000`, and the image moves to `$8800` (56 pages). See
[NATIVE-AES](../../NATIVE-AES.md#windows).

## Evidence

`~/.venvs/uos-tests/bin/python -B tests/ci_native_aes.py` → `aes.json`,
27/27 cases: the 22 earlier cases (now with the data segment reserved on
attach and freed on unload) plus 5 window cases.

The oracle is the painter's algorithm (`tests/native_aes_scene.py`). After
every operation and the demo's redraw responses, the complete surface must
equal drawing the desktop and then each window bottom to top from scratch:
frames with every GEM element, the work fill, and marker cells at each work
area's corners. Visible-rectangle lists from `WF_FIRSTXYWH`/`WF_NEXTXYWH`
must equal an independent row-run decomposition. Steps covered:
- open three windows;
- top each one in turn;
- move right/down, grow, move left/up, and move again;
- close the top window twice;
- Escape closes and deletes everything, and the slots are reused.

## Mutation check and a test gap it exposed

Four planted bugs:
1. no forced redraw for a moved or resized window;
2. no top-window highlight;
3. no skipping of runs already covered from the row above;
4. wrong slider rounding.

Bugs 2–4 failed the test at once. Bug 1 first survived. With uniform
fills, and with only right/down moves whose changed-cell bounding box
covers the whole work area, a missing redraw left identical pixels. The
demo now paints position markers that move with each window, and the test
moves a window left/up so the changed cells cover only one column. Bug 1
now fails the move case, and the real code passes all 27 cases.

`AESVC.PRG`: 12,450 bytes, 49 pages, CRC16 in `aes.json`.

## Limits

CPU-level only; no physical C128. Clicking and dragging frame gadgets
(topping, moving, sizing, arrows, sliders through the event wait) is step
5b and not implemented. The AES does not copy moved content: the app
repaints its whole work area after a move or resize, which is slower than
GEM's blit. Redraw speed is unmeasured. While resident, the AES holds
65 bank-1 pages (49 image + 16 data).
