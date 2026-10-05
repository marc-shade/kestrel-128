# REU module cache (2026-10-04)

## Change

- **Module cache** ([NATIVE-MODULES](../../NATIVE-MODULES.md#reu-module-cache)),
  ABI 1.15. With an idle REU of 512 KiB or more, cold boot reserves the REU's
  top 64 KiB bank and publishes `N_RCACHE` = 16 at `$3d9f`. `N_MLOAD` looks
  the requested module up there (name and the running app's core CRC) before
  opening the file. A hit is copied into the module window and checked like a
  disk image (window bounds before the copy, then manifest, parent CRC,
  extent, module CRC); it opens no file. A miss, a failed check or a busy REU
  loads from the disk as before, and a verified disk load is stored. The
  directory (eleven entries) and the bank reset when full; cold boot empties
  them. Transfers are at most 256 bytes.
- **Boot probe** (`rc_probe`, boot staging): REC idle checks, a two-byte
  pattern in bank 0, then each power-of-two bank for a missing bank or a wrap
  to bank 0, restoring every byte it touched.
- **App arenas**: `reu.inc` subtracts `N_RCACHE` from its probed capacity, so
  the VDC service (and every app that uses the shared arena) stops below the
  reserved bank. 128/256 KiB REUs have no cache and lose nothing.
- **Space**: the resident cache code is 753 bytes of the main section (now
  252 free; direct-desktop 248). `native_keyin` (25 bytes) moved to the
  service region's spare interval below `$4bfc` to make room for the three
  loader hooks in front of `$4a00`.
- **VDSVC size**: the first sweep failed `ci_native_gemdesk_diskcopy`. The
  arena subtraction pushed VDSVC (which includes `reu.inc`) from 39 to 40
  pages, into the AES at bank-1 `$8700`, so the desktop's 80-column screen
  could not open. `reu.inc` now builds the 16 MiB total through the same
  shift as the other sizes and subtracts with a shorter borrow, leaving
  VDSVC 9,973 bytes (11 left in 39 pages), and `build-native-desktop.py`
  fails the build if VDSVC would reach the AES.
- **Running-layout audit**: the first VICE pass failed 15 workflows because
  the cache's state (`rc_key`..`rc_chunklen`, 34 bytes) and the `rc_window`
  load operand changed resident bytes the audit had not been told about.
  `native_running_layout.py` now declares both; every other resident byte
  is still compared with the boot image.
- **Whole-REU oracles**: `ci_native_pointer_iec --reu-kib 512` compares every
  REU byte outside the VDC backups with its document oracle, which did not
  know the cache bank. `native_reu_check.module_cache` now rebuilds the
  expected top bank from the initial REU image, the directory and the module
  files (names, units allocated from 1, extents, each entry's parent CRC
  taken from the module's own manifest, byte-exact images) and compares all
  64 KiB; the pointer workflow checks the bytes below it against the oracle
  as before. `ci_native_sheet_iec --reu-kib 512` now uses the same check
  with a seeded REU image, and also requires every byte below the cache bank
  to be unchanged.
- `N_ABI_MINOR` is 15. Apps and modules requiring minor 14 or lower are
  unaffected.

## Tests

- `ci_native_module_cache` (new, 17 cases, CPU with the pinned REC model):
  the boot probe at 128/256/512 KiB and 16 MiB, with no REU and with an
  armed transfer, restoring every probed byte; IEC and Ultimate sources:
  a cold load reads the file and stores the exact window, warm loads open no
  file (with and without IRQs) and stay callable with new tokens; a damaged
  cached byte fails the CRC and falls back to the disk, which re-stores it; an
  out-of-window cached extent is refused before any copy into the window; a
  busy REU loads from the disk; twelve names reset the eleven-entry
  directory, which keeps caching; 128/256 KiB loads make no REU transfer.
- `ci_native_reu`: with `N_RCACHE` = 16 the arena reports 112, 240 and 4,080
  pages at 512 KiB, 1 MiB and 16 MiB, refuses anything beyond, and a write at
  its last byte leaves the reserved bank unchanged.
- `ci_native_reu_vice` and `ci_native_banked_vice` (VICE, real ROMs, whole-REU
  snapshots at 128 KiB to 16 MiB): the arena size and transfers follow the
  reduced capacity, and the only REU change outside the apps' own transfers
  is the cache's two-byte directory header written at boot.
- `ci_native_sheet_iec --reu-kib 512` (new VICE variant): the full Sheet
  workflow (desktop launch, edit and recalculation, IEC save and readback,
  reopen, desktop return) with a 512 KiB REU. Afterwards the cache directory
  holds SHCALC, SHFONT and SHCLIP once each with byte-exact images, and 11 of
  the session's 14 module loads were served from the REU (each miss appends an
  entry, so loads minus entries counts the hits).
- `ci_native_modules`, `ci_native_apps`, `ci_native_loader_ultimate`: the
  "minor too new" mutations use 16.

Full sweep on the final images (`tests/sweep_native.py` through the resumable
driver, from a snapshot of this tree):

- CPU group: 323/323 passed (four chunks), after the VDSVC fix above. The
  first sweep's 155 results were discarded because the fix changed the
  images. `ci_native_running_layout` (both variants, 7 controls each) was
  rerun after the audit declaration.
- VICE group: 60/60 passed. The first pass failed 15 jobs on the running-layout
  declaration; their retry passed except `ci_native_pointer_iec` with
  `--reu-kib 512`, which passed after the whole-REU oracle change. The Sheet
  REU variant was rerun with the same check: the cache held SHCALC, SHFONT
  and SHCLIP and served 11 of 14 loads. Every `.prg`, `.d64` and `.d81` in
  the commit is byte-identical to the swept snapshot.

## Hardware (2026-10-05)

The reference C128 through its Ultimate II+, with the Ultimate's REU enabled
at 16 MB, so the kernel reserved the top bank and the cache code ran on every
boot and module load. Images of commit `9c14a07`.

- Passed: `hw_ultimate_check.py --native-files`, `--native-browser`,
  `--native-editor`, `--native-ultimate`, `--native-redraw`,
  `--native-usb-apps`, `--native` and `hw_native_gem_check.py`.
- `--native` and the GEM check each passed on their second run. The first
  `--native` run accepted a wrong direct DMA read of the Calculator display
  (two consecutive REST reads returned the same wrong bytes; the C128's own
  read in the same capture held `DIV/0`). The first GEM run did not see the
  Editor start after Return on NOTE; the same GEMDESK workflow passed in VICE
  with a 16 MB REU, and the hardware rerun passed it.
- `--native-desktop` did not pass in six runs. One (`r5`) verified all eleven
  workflow screens and the resident layout at return, then failed the final
  Ultimate DOS context 2 probe (the context was idle afterwards). The others
  stopped at different steps: a capture that met a bank-1 service call, a
  wrong direct read of VDC state, an 80-column mirror sampled before its
  update, a desktop surface mismatch at boot, and a resident-layout chunk
  that returned the capture tool's own output buffer. The same check also
  failed on the two previous builds (`66e0b0c`, before the cache, and
  `01784c4`, before the kernel-space change), each at another step, so these
  failures are not from this change; at publication the check passed on its
  third run.
- The first sequential run was stopped by the session's two-hour limit inside
  `--native-ultimate`; `--native-reclaim` removed its seven private files and
  the drives matched their recorded state.

## Not verified

- No hardware check reads `N_RCACHE` or the REU, so cache hits on the
  physical machine were not observed directly; the hardware runs show only
  that the system works with the cache enabled.
- Load times with and without the cache were not measured; VICE ran in warp
  mode. A hit still computes the module CRC (about 150 cycles a byte).
- A module rebuilt without rebuilding its app core would be served from the
  cache until the next cold boot (documented; shipped builds seal both).
