# GEMDESK reads drive 9 in its own geometry — 2026-09-26

## What changed

Until now GEMDESK always read device 9 as a D64. A 1571 or 1581 on device 9
was listed with the wrong geometry. TOS works out a drive's format itself;
now GEMDESK does too.

- The first time drive 9 is opened (icon, 9 key, or Show Info on its icon),
  GEMDESK sends `UI` through `dos-command.inc`. The drive's DOS resets and
  answers 73 with its ROM's name.
- GEMDESK searches that line for `15?1`: `1581` → D81 (2), `1571` → D71 (1),
  anything else (`1541`, or a drive that names no CBM model) → D64 (0).
- The answer is kept in `gm_dev_format` for the rest of the run. A drive
  that does not answer (absent, busy channel, not 73) is read as a D64
  without keeping the answer; the listing reports the drive's error, and
  the next open asks again.

The ROM names come from VICE's drive ROMs (`strings` on
`/usr/share/vice/DRIVES/dos15*.bin`): "CBM DOS V2.6 1541" (1541 and 1541-II),
"CBM DOS V3.0 1571" (V3.1 on the 1571CR), "COPYRIGHT CBM DOS V10 1581".

## Evidence

`gemdesk.prg` `c6671f23…`, `gddlg.prg` `f818fb41…`, `gdset.prg` `6d34d3fe…`,
`gem.d81` `36e5d30e…` (dev build of this change).

- The IEC model (`tests/ci_native_files.py`, `StreamIEC`) now answers `UI`
  with 73 and the ROM line for the device's format, or a per-device
  override (`identity`). Its own suite still passes: 93 cases.
- `tests/ci_native_gemdesk.py`: 43/43 (CPU, Py65). The new case runs three
  drives: a 1581 with a D81, a 1571 with a D71, and an SD2IEC-named drive
  with a D64. Each is listed exactly (surface oracle), `gm_dev_format` is
  2, 1 and 0, and after closing and reopening the window only one `UI` was
  ever sent. The Format case now expects `UI` before `N0:BLANK,B1`.
- `tests/ci_native_gemdesk_vice.py`: 8/8 in VICE x128. Device 9 is a
  true-drive-emulated 1581 with a D81 made by `c1541`. The 9 key lists it
  exactly and `gm_dev_format` reads 2: the real 1581 ROM's reply was
  recognised. The run then closes it with Ctrl-W and goes on to the earlier
  cases.

Planted bugs (each built and run through `ci_native_gemdesk.py`; both
failed):

| Planted bug | Failed at |
|---|---|
| `1581` not recognised | "drive 9 read as format 2" surface |
| The answer not kept | `gm_dev_format` after the first open |

## Limits

- Detection is by drive model, not by the mounted image. A drive that does
  not name 1571 or 1581 is read as a D64, so an SD2IEC holding a D81 image
  would be listed wrongly. A 1571 is always read as a D71, which reads a
  single-sided disk's directory the same way.
- `UI` resets the drive's DOS; GEMDESK sends it only when the kernel holds
  no channel to the drive (`dos-command.inc` refuses otherwise).
- The 1571 answer is checked only in the CPU model, and no test covers a
  drive that does not answer. Nothing ran on the physical C128 or an
  Ultimate-emulated drive 9.
