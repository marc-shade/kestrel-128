# AES alerts (GEM layer step 2) — 2026-09-25

The persistent AES gains GEM-style alert boxes (AES minor 1, capability bit
0): `ae_alert_open` and `ae_alert_step`, drawn by the shared graphics library
from bank 1 through the executor's heap callbacks. See
[NATIVE-AES](../../NATIVE-AES.md#alerts).

## Evidence

`~/.venvs/uos-tests/bin/python -B tests/ci_native_aes.py` → `aes.json`,
11/11 cases:
- the six step-1 persistence cases;
- five alert cases on the `DisplayBus` VIC model.

Every alert frame is compared as a complete 9,216-byte surface against an
independent renderer, `tests/native_aes_scene.py`. That renderer recomputes
the layout from the string and draws the expected pixels and colours from
the same font file. The alert cases cover:

- open, Tab/cursor focus with exact dirty-row masks, Return, and exact
  restoration with the owner-30 save buffer freed;
- digits, Escape (last button) and Return (default);
- pointer press/release on the same button, and release elsewhere;
- arbitrary pixels and colours under the alert restored byte for byte;
- seven malformed strings and an alert over 250 cells refused before any
  surface change or allocation.

Mutation check: a wrong paper colour, a missing gap between buttons, and a
skipped restore each made the test fail. The source was restored and the
test rerun.

`AESVC.PRG`: 5,566 bytes, 22 pages, CRC16 `$0f6e`, SHA-256 in `aes.json`.

## Byte identity

`graphics-core.inc` now calls the heap through weak names
(`gfx_heap_read/write/fill`) so bank-1 code can route them through the
bridge. `build-native-desktop.py` and `build-native.py` reproduced every
system image except Files, whose rename/delete change is recorded
separately. The graphics change alone was proven byte-identical on all 59
images in a scratch tree.

## Limits

No physical C128 run. No suite app uses the alert service yet. The
application input loop supplies pointer samples; the example sends them as
key `$ff` because it has no pointer driver. Rendering speed through the
per-byte heap gateway is not yet measured.
