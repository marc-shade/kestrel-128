# GEMDESK name conflicts, Confirm overwrites, Key click, Format progress — 2026-09-29

## Change

GEMDESK ([GEM-DESKTOP](../../GEM-DESKTOP.md)):

- **Name conflicts in a copy**: a file whose name is on the target (a drive
  answers 63 to the create; on USB, `FILE_STAT` finds it first) asks
  "NAME already exists on DEST." with Replace, Skip (the default) and Stop.
  Replace scratches the target (`S0:NAME`, exactly one file scratched) or
  deletes it (`DELETE_FILE`, an empty reply) and copies again, compared as
  any copy; Stop ends the remaining rows. Before, the copy was refused.
- **Confirm overwrites** in Preferences (TOS's third confirmation): off, a
  name on the target is replaced without the question. Stored as bit 3 of the
  saved preference byte (set means "do not ask"), so desktops saved before
  keep asking.
- **Key click** in the Control Panel: GEMDESK plays a short noise burst on
  SID voice 1 (`sd_click` in `src/native/sound.inc`) for every key it reads.
  Bit 2 of the preference byte.
- **Format**: `N0:NAME,ID` runs under a "Formatting disk" window, the drive's
  windows are listed again, and the new disk's `$` listing is read back:
  "Drive 9 is formatted: 3160 blocks free." (the drive's own count), or an
  alert that the new disk could not be read back. Format moved from GDDLG to
  a new module, `GDFMT.PRG`, which carries the progress window; the core
  gained its 9-byte name (core end `$b1b4`; GDDSK, the largest module, leaves
  75 bytes).

## Bugs found and fixed on the way

- **Preferences cleared Key click**: OK in Preferences rebuilt the preference
  byte from its own checkboxes, dropping bit 2. It now keeps the bits it does
  not show. The Control Panel test presses OK in Preferences with Key click
  on and asserts the byte and a click afterwards; a build with the old
  behaviour fails it (`gm_confirm` read 1).
- **The copy hid the preferences from its own rows**: GDCPY cleared the whole
  preference byte while rows were copied (so Move deletes without a second
  question), so the conflict code could not see Confirm overwrites. It now
  clears only bit 0. A build with the old line fails the new copy case
  ("the target holds the new source").
- **Format did not list a 1581 again** (present before this change): Format
  took the geometry of any drive but the boot drive as a D64, and the
  relisting only refreshes windows of the same geometry, so a 1581 in drive 9
  kept showing its old files. The new VICE test found it (the window still
  listed OLD); Format now takes the geometry the drive's icon opens it in
  (`gm_drive_format`). The CPU test's drive 9 is now a 1581 in the model,
  and the build before the fix fails it on the same screen bytes as VICE.
- **Test harness**: the desktop harness had no SID, so the Key click case
  added with the feature could not run (the heap bus refused the write to
  `$d404`). The harness now records SID register writes; the case asserts on
  them.

## Evidence

All on the committed tree (the rebuilt outputs are byte-identical to the
scratch tree the suites first ran in; [build hashes](build-hashes.json):
only the GEMDESK core, its modules, `gem.d81` and `vt52.prg` changed, 61
images unchanged).

- **GEMDESK CPU set** (`tests/sweep_native.py --group cpu --only …`,
  [summary](cpu-summary.json)): 12/12 passed: the desktop suite
  ([report](ci_native_gemdesk.json): Preferences with Confirm overwrites,
  Key click kept through Preferences, Format under its window with the free
  blocks of a 1581), copy ([report](ci_native_gemdesk_copy.json): Replace,
  Skip and Stop on IEC and USB, Confirm overwrites off), select, print,
  folder, Print Screen, disk copy, accessory, tree, AES, services (the
  `sd_click` registers) and VT52 (which shares `sound.inc`).
- **VICE** (`tests/sweep_native.py --group vice --only …`,
  [summary](vice-summary.json)): 8/8 passed, among them the new
  [Format test](ci_native_gemdesk_format_vice.json): x128 with true-drive
  1581s, File:Format from the keyboard onto drive 9, the "Formatting disk"
  window seen while the drive works, "Drive 9 is formatted: 3160 blocks
  free." afterwards with the window listed again (empty), and after the
  emulator exits c1541 reads drive 9 as `"blank" b1 3d` with no files and
  3160 blocks free.
- **Mutation checks** (each a one-line change to a scratch build, run
  against the new case):
  - Preferences clearing the other bits (`and #0` for `and #GM_KEYCLICK`):
    the Key click case fails, `gm_confirm` = 1.
  - GDCPY clearing the whole preference byte during a copy: the Confirm
    overwrites case fails ("the target holds the new source").
  - Format's old geometry (the build before the fix): the CPU Format case
    fails on the same stale OLD row as the VICE run.

## Not verified

- Nothing here has run on the physical C128, a real 1541/1571/1581 or the
  Ultimate II+ (its USB `FILE_STAT`/`DELETE_FILE` answers are the CPU
  model's).
- Replace on USB and the Key click sound run only in the CPU model; VICE
  covers Format (true-drive 1581) and the existing GEMDESK flows. The click's
  sound was not listened to: the tests assert the SID register writes.
- Format of a 1541 or 1571 in VICE (the CPU model covers the relisting logic
  for D64 and D81 geometry only through its drive model).
