# AES window gadgets (GEM layer step 5b) — 2026-09-26

The window manager's frame gadgets now work through the event wait. Presses
and drags become GEM messages, and the app answers them with `wind_set`:
- `WM_TOPPED` 21, `WM_CLOSED` 22, `WM_FULLED` 23;
- `WM_ARROWED` 24 (line and page steps);
- `WM_HSLID`/`WM_VSLID` 25/26 (thumb drags);
- `WM_SIZED` 27 and `WM_MOVED` 28 (size-box and title drags with an XOR
  outline).

See [NATIVE-AES](../../NATIVE-AES.md#frame-gadgets).

## Evidence

`~/.venvs/uos-tests/bin/python -B tests/ci_native_aes.py` → `aes.json`,
31/31 cases: the 27 earlier cases plus 4 gadget cases. Each checks complete
surfaces against the painter's-algorithm oracle, including the XOR outline
while a drag is held. The gadget cases cover:
- a press on a lower window's title;
- a title drag followed by release;
- the full box;
- a size-box drag;
- up/down arrows and paging on both sides of the thumb;
- vertical and horizontal thumb drags to the track ends;
- horizontal arrows;
- the close box;
- presses in the top window's work area and on the desktop reaching the
  app without a gadget message.

Mutation check: topping on every press, and swapped line-up/line-down
arrows, each failed the first gadget case that exercises them. The source
was restored.

`AESVC.PRG`: 13,933 bytes, 55 of 56 pages.

## Limits

CPU-level only; no physical C128 or real 1351 drag. Arrows do not repeat
while held. The slider position comes from the pointer's cell, not from a
drag offset. No suite app uses windows yet. With one page left in the
image, later AES steps need an overlay mechanism.
