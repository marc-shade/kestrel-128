# GEMDESK printing, disk copy, folders and the desk accessory; AES 1.7 — 2026-09-29

## Change

GEMDESK ([GEM-DESKTOP](../../GEM-DESKTOP.md)):

- **Printing**: a Printer icon when IEC device 4 answers at start; rows
  dropped on it are printed through the KERNAL (logical file 121, secondary
  address 7). Options:Print Screen, or HELP, dumps the desktop bitmap in the
  Commodore bit-image mode.
- **Disk copy**: a drive icon dropped on the other drive's icon copies every
  sector through buffer channels (`U1`, `B-P`, `U2`) and reads each one back
  to compare, under a "Copy track T/N" window (new module `GDDSK.PRG`).
- **USB**: File:New Folder (`CREATE_DIR`, proven by `FILE_STAT`) and rename
  from Show Info (`RENAME_FILE`) (`GDSET.PRG`, `GDUSB.PRG`).
- **Dragging**: an XOR outline follows a dragged row (AES window sub-op 9);
  ALT+Shift+Return holds the button so the keyboard can drag.
- **Desk accessory**: at start `GDSES.PRG` loads `DESK1.ACC` (the Calculator)
  into bank-1 `$4000` (owner 29), or adopts one already resident.

AES ([NATIVE-AES](../../NATIVE-AES.md)), minor 7: loaded at `$8700`; the
accessory interface (`AE_OP_ACC`: its Desk item, its window's messages, keys
and clicks, a dispatch while the app waits for events); window sub-ops 9
(outline) and 10 (text in a window's visible work area).

## Bugs found and fixed on the way

- `gm_restore_done` had lost its fall-through: the desktop colour was not
  restored on a cold start. It now jumps to `gm_restore_color`.
- The VDC mirror's present reuses `N_BUFFER`, where `gm_alert` returned the
  chosen button: in VICE, Copy in the disk-copy question was read as Cancel.
  The button is now stored after the last present.
- The progress window's drain left the AES timer bit set, so the next
  alert's wait woke on every jiffy and GEMDESK never went idle after a disk
  copy in VICE. The drain now clears it; the CPU test asserts it.

## Evidence

- **VICE** (`tests/sweep_native.py --group vice --only …`, [summary](vice-summary.json)),
  x128 on the committed tree: 5/5 passed.
  - [AES](ci_native_aes_vice.json): AESVC at `$8700` reports 1.7; alert, menu,
    three windows and unload match the painter; every owner-30 page returns.
  - [accessory](ci_native_gemdesk_acc_vice.json): GEMDESK loads `DESK1.ACC`;
    the Desk menu lists Calculator; typed keys give 12 + 3 = 15 and 1351
    clicks give × 4 = 60; the close box restores the desktop exactly.
  - [disk copy](ci_native_gemdesk_diskcopy_vice.json): Boot dragged onto
    Drive 9 with the 1351 (XTEST pointer); after the emulator exits, drive 9's
    D81 is byte-identical to drive 8's (3,200 sectors).
  - [Print Screen](ci_native_gemdesk_prtscr_vice.json): VICE's printer on
    device 4 received 29 bands whose dots are exactly the emulated surface's
    set pixels (9,339 bytes).
  - [GEMDESK](ci_native_gemdesk_vice.json): boot, drive 9 identity, launch and
    return of Calculator, Editor and Paint documents, surfaces as the oracle.
- **Full CPU sweep** of the committed tree (`tests/sweep_native.py --group cpu`,
  [summary](cpu-sweep-summary.json)): 318/318 jobs passed, among them the
  GEMDESK suites (desktop, copy, select, folder, print, Print Screen, disk
  copy, accessory) and the AES suite.

## Not verified

- Nothing here has run on the physical C128 or the Ultimate II+ (its USB
  DOS, printer emulation, or a real printer).
- Disk copy between a real 1541/1571/1581 pair; D64 and D71 copies ran only
  in the CPU model.
- Accessory use from AES apps other than GEMDESK: only GEMDESK installs an
  AES menu today.
