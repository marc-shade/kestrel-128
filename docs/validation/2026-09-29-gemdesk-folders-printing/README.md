# GEMDESK copy progress, USB folders, Confirm copies, picture printing — 2026-09-29

## Change

GEMDESK ([GEM-DESKTOP](../../GEM-DESKTOP.md)):

- **Copy progress**: while rows are copied or moved, a title-only window
  reads "Copying N/M" ("Moving N/M"). It opens for the first row that is
  copied; alerts about a row appear over it; it closes, and the redraws its
  closing queued are answered, before the windows are listed again. The
  window code is shared with the disk copy (`src/native/gemdesk-progress.inc`).
- **USB folders**: a USB folder dropped on another USB window is copied as a
  tree (`FILE_STAT` must find nothing; `CREATE_DIR` proven by `FILE_STAT`;
  each entry read again by its position, since a DOS context holds one open
  file; subfolders descended into, 16 levels). Move deletes the source's
  contents deepest first, then the emptied folder. A copy into itself and a
  folder dropped on a drive are refused.
- **Confirm copies** in Preferences: off, a dropped row is copied without
  the question. Stored as bit 1 of the saved preference byte, so desktops
  saved before keep asking.
- **Printing Paint pictures**: a file that starts with the UPNT header,
  dropped on the Printer icon, prints its bitmap in the Commodore bit-image
  bands Print Screen uses, read from the file a character row at a time.
- **Modules assembled one by one**: each module is now its own source
  (`src/native/gemdesk-{dlg,set,cpy,ses,usb,dsk,new}.asm`), assembled
  against the core's exported labels (`gemdesk.sym`). Before, the core and
  every module were one image at `$6000`, so together they could not pass
  40 KiB; that limit stopped a seventh module. With the same sources, the
  split build's core and six modules are byte-identical to the one-image
  build's.
- **Module moves**: Print Screen and file printing moved from GDCPY to
  GDDSK, with their stream helpers shared (`src/native/gemdesk-stream.inc`);
  New Folder moved into its own module, `GDNEW.PRG`. GDCPY keeps its names,
  and GDDSK its sector buffer, in the sort workspace. GDDSK, now the largest
  module, leaves the core 160 bytes to grow (it had 2 before GDNEW).

## Bugs found and fixed on the way

- In the folder delete, the DOS context overwrote the opcode, so the delete
  went out as command 1; the model's handle check caught it.
- A module cannot load another while it runs (the loader answered error
  `$07`), so the core, not GDCPY, sends Printer drops to GDDSK.
- The multiple-selection test's listing filled its window once `GDNEW.PRG`
  was on the disk; the test now removes that file (it does not use New
  Folder) so a blank row stays below the entries.

## Evidence

All on the committed tree, rebuilt with `build-native-desktop.py`:

- **Build** ([hashes](build-hashes.json)): only `gemdesk.prg`, its seven
  modules and `gem.d81` changed; the other 62 binaries and disk images are
  byte-identical to the previous commit's.
- **GEMDESK CPU suites** (`tests/sweep_native.py --group cpu --only …`,
  [summary](cpu-summary.json)): 9/9 passed: desktop, copy, select, folder
  (New Folder), print, Print Screen, disk copy, accessory and the new tree
  suite. The copy and select suites check the progress window's title at
  every file OPEN; the [tree suite](tree-report.json) copies a folder with a
  subfolder, refuses an existing name, a copy into itself and a folder on a
  drive, stops on Esc, and moves a tree (deletes deepest first); the
  [print suite](print-report.json) prints a Paint picture whose bands decode
  to exactly its bitmap pixels, and a truncated one that stops cleanly.
- **VICE** (x128, `tests/sweep_native.py --group vice --only …`,
  [summary](vice-summary.json)): 7/7 passed, including two new runs:
  - [file copy](ci_native_gemdesk_copy_vice.json): a 3,000-byte SEQ file
    dragged with the 1351 from an emulated 1581 in drive 9 onto the Boot
    icon; after the emulator exits, `c1541` reads the copy byte-identical to
    the unchanged source.
  - [picture printing](ci_native_gemdesk_print_vice.json): a UPNT picture
    dragged onto the Printer icon; VICE's printer on device 4 received 29
    bit-image bands whose dots are exactly the picture's bitmap pixels.
- Not rerun: the full CPU sweep (318 jobs) after this change. Nothing
  outside GEMDESK's binaries changed (above), and the other apps' suites ran
  318/318 on the previous commit.


## Not verified

- USB folder copy runs only against the CPU model of Ultimate DOS: its entry
  order (folders first) and its answers are the model's. The real Ultimate
  II+ firmware, and whether it lists `.` and `..` (skipped either way), are
  unverified.
- Nothing here has run on the physical C128 or a real printer.
- A folder dropped on the USB icon (the Ultimate's root) is not tested.
