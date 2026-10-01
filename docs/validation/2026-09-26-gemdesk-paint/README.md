# GEMDESK opens pictures in Paint — 2026-09-26

## What changed

GEMDESK now decides a document the way Files does
([NATIVE-DOCUMENT-LAUNCH](../../NATIVE-DOCUMENT-LAUNCH.md)): the signature
first, then the name.

- Before opening an IEC SEQ file or any USB file, GEMDESK opens it, reads
  four bytes and closes it again (`gm_peek`).
- `UPNT` stages a Paint document (kind 2) and replaces GEMDESK with `paint`
  from the boot disk. Otherwise the earlier rules apply: an IEC SEQ file, or
  a USB `.TXT`/`.SEQ` file, goes to the Editor (kind 1), and other USB files
  launch as programs.
- A file that cannot be opened or read counts as "not a picture". The app
  or dispatcher that opens it next reports the error itself.
- The file service reads `N_UPATH` and `N_FNAMELEN` and writes neither, so a
  USB program launch after the peek still has its full path.

This fixes a misroute from the previous change: Paint saves pictures as SEQ
files by default, so double-clicking one opened it in the Editor as text.

The core now ends at `$a869` (it was `$a769`).

## Evidence

`gemdesk.prg` `1c1acef2…`, `gddlg.prg` `5fa2d042…`, `gdset.prg` `21787317…`,
`gem.d81` `22d1f73f…` (dev build of this change).

- `tests/ci_native_gemdesk.py`: 42/42 (CPU, Py65). New or changed cases:
  - `FILE01`, a SEQ file starting with `UPNT`, stages a Paint document:
    request `$80`, kind 2, type 0, return 0; `PAINT` from the boot disk; its
    name and device.
  - A USB file `draw.txt` that starts with `UPNT` opens in Paint with its
    folder: the signature wins over the suffix.
  - The long-named USB program and `notes.txt` now have contents, so their
    peeks read real bytes before the program launch (full `N_UPATH`) and
    the Editor document.
- `tests/ci_native_gemdesk_vice.py`: 7/7 in VICE x128 (1581 true drive
  emulation). The new case writes a Paint picture as the SEQ file `PICTURE`
  to the test's copy of `gem.d81` and presses Return on it. The real Paint
  loads and claims the request, and reports "Opened". Its current document
  allocation in bank 1 equals the picture byte for byte, and the whole
  9,216-byte surface matches the Paint oracle (`paint_scene.surface`).

Planted bugs (each built and run through `ci_native_gemdesk.py`):

| Planted bug | Result |
|---|---|
| The peek never reports `UPNT` | Failed: `FILE01` → `PAINT` |
| Paint's name taken from the wrong table offset | Failed: `FILE01` → `PAINT` |
| `N_FNAMELEN` not restored after the USB peek | Passed, 42/42 |

The third one survived because the restore guarded nothing: no kernel file
routine writes `N_FNAMELEN` (only the dispatcher's own launch setup in
`apps.inc` does). The save and restore were removed. Both suites were then
run again on the build hashed above: CPU 42/42, VICE 7/7.

## Limits

- USB pictures are checked only in the CPU model; nothing ran against a real
  Ultimate. The VICE case is IEC.
- IEC PRG and USR files are not peeked: a picture saved with type PRG or USR
  goes to the dispatcher as a program launch (Files would open it in
  Paint). What the dispatcher then shows for it was not tested here.
- Nothing here ran on the physical C128.
