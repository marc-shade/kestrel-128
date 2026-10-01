# AES in VICE x128 — 2026-09-26

First run of the persistent AES on an emulated C128 rather than the Py65
bus model. `tests/ci_native_aes_vice.py` does the following:
1. Cold-boots the native diagnostic disk with `AESDEMO` as `calc` and
   `AESVC.PRG` beside it.
2. Launches it; the demo loads the AES into bank-1 `$8800`.
3. Drives the alert, menu-bar and window demos from the keyboard buffer.
4. Reads the complete VIC surface (`$c000..$e3ff`, bank 0) over the VICE
   binary monitor after each step, and compares it with the same oracles
   the CPU tests use (`tests/native_aes_scene.py`).

`python3 -u tests/ci_native_aes_vice.py --report vice.json` → 5/5 checks:

| Check | What is compared |
|---|---|
| Cold boot and load | The resident header and callback import at bank-1 `$8800`, the attach reply: version 1.4, capabilities `$0f`, 1 attach |
| Alert | Exact frames at open and after Tab; Return chooses; exact restoration |
| Menu bar | Exact bar, Desk drop-down, File drop-down with Quit hovered past the disabled item; Return queues `MN_SELECTED` File:Quit |
| Windows | Exact frames, fills and position markers after open, top, move left/up, move right/down, close |
| Unload | Every owner-30 page returned (175/251/32 free) |

Of the image's 13,933 bytes, 13,924 are unchanged after running; the
others are its own counters. VICE ran in warp mode with a true-drive 1541.

The PNGs render three of the checked surfaces with `render_surface.py` (VICE
default palette). They are memory renderings, not screenshots of the VICE
window. The `.surface` files are the raw 9,216-byte captures.

## Limits

No pointer input: the VICE harness injects keys only, and the pointer paths
are covered by the CPU tests. No physical C128. The 80-column VDC mirror of
these surfaces is not exercised, because the demo has no VDC component.
