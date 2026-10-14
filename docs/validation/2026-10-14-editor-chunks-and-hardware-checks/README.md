# Editor document chunks of 1 to 16 pages, and new hardware checks (2026-10-14)

## Why

The [80-column performance record](../2026-10-13-80-column-performance/README.md)
left one fragile case: the graphical Editor opening a 66,053-byte document
beside a full 296-entry D81 picker (`ci_native_picker_gui --case large`)
passed or failed with the size of the resident VDC service. At 31 pages it
passed; padded to 32, Open failed with 26 pages still free, in runs of 15 and
11. Positions mapped to 4 KiB chunks by P >> 12, so only the last chunk could
be short and every other free run lost its size mod 16 pages. The document
needs 259 pages: 16 chunks of 4 KiB and a 3-page chunk.

The owner also asked for hardware checks of the apps that were verified only
in emulators, and for a hardware timing of the 80-column pointer.

## Change

`document.inc` with `DOC_PARTIAL` (the graphical Editor) (6806b13):

- Each chunk holds 1 to 16 pages; the context records them as one nibble per
  chunk (bytes 114 to 125) and counts the leading 16-page chunks (byte 126).
- `doc_locate` maps a position through those leading chunks by P >> 12, as
  before, and walks the sizes of the rest. The forward and backward transfer
  limits stop at the real chunk boundary. A shared REU extent has none.
- A short last chunk still grows in place a page at a time. When the page
  after it is taken, it is reserved again unchanged and a new chunk follows
  it in another free run, so no free page is lost to alignment. Growth is
  refused only when no free page or no chunk slot is left.
- In the compact build the 3-byte context load and store macros call shared
  subroutines for transient variables, which pays for the new code: the
  Editor core is 91 bytes smaller than before.

The text editor and Paint do not use `DOC_PARTIAL` and are unchanged.

## Results

`ci_native_picker_gui --case large`, with the VDC service padded:

| VDC service pages | Before | After |
|---:|---|---|
| 31 (shipped) | pass | pass |
| 32 | fail | pass |
| 33 | fail | pass |
| 34 | fail | pass |
| 35 | fail | pass |

Editor main-RAM capacity (`ci_native_vdc_editor_capacity`): 37,120 to 39,680
bytes with a 64 KiB VDC, 38,912 to 41,728 bytes with 16 KiB.

Cost: moving the gap across a 66,053-byte, 17-chunk document took 0.2 to 1.0%
more instructions in Py65 than with fixed 4 KiB chunks. The Editor hover
benchmark changed by 28 cycles.

## New hardware checks

Each has a VICE or Py65 twin in the sweeps that runs the same workflow:

- `--native-apps` (83a2b19): Paint keyboard edits and discard, the Claude
  landing page and clean return without a connection, the Ultimate controls
  Drives page against the REST drive list, and a Sheet Save As to an empty
  drive B whose retrieved image must hold exactly the expected workbook.
- `--native-gem` and `--native-aes` (1a636a0): GEMDESK's keyboard workflow on
  drives A and B in 1581 mode (the standalone hardware script now follows the
  VICE sequence it had drifted from), and the AES demo's 40-column alert,
  menu and window tests.
- `--native-pointer-timing` (405a05c): a measurement-only build, never
  shipped, moves the pointer itself over empty desktop space through the
  shipped 1351 path and times 512 pointer-only updates with CIA2 timer B. In
  Py65 every timed record equals the shipped code's cycles. In VICE the
  service's redraw averaged 16,386 cycles and the whole bank call 19,382,
  none under one 17,045-cycle frame; VICE's 8563 timing is approximate.

## Pointer timing on the C128

`--native-pointer-timing` (6f0be67, the shipped disk image 2b4d56be...) on the
reference NTSC C128 with an Ultimate II+, 512 driven updates, none missing,
calibration exact (1,001 and 2,002 cycles):

| Cycles | Min | Mean | Median | p95 | Max | Under one frame |
|---|---:|---:|---:|---:|---:|---:|
| Service redraw | 13,181 | 14,512 | 14,492 | 15,461 | 16,024 | 100% |
| Whole bank call | 16,138 | 17,510 | 17,482 | 18,438 | 18,983 | 23% |

The bank gateway costs about 1,550 cycles in and 1,450 out; every timed
update also took one 60 Hz KERNAL interrupt. Updates came 2 jiffies apart in
508 of 511 intervals and 1 jiffy apart in 3, so the 80-column pointer moves
at 30 Hz on this machine, not 60. The redraw itself fits a frame; the call
around it misses by 465 cycles on average. VICE overstated both (16,386 and
19,382). The first run (e99342b) refused to start because the connected 1351
had already caused one pointer call before the start key; 6f0be67 records
such calls (`calls_before_start`, 1 here) instead of refusing.

## Gates

- 451bfe5 (chunks): CPU sweep 323/323.
- 405a05c (chunks and the new checks): CPU sweep 324/324, VICE sweep 64/64.
- Hardware, reference C128 (e99342b images): `--native-desktop` PASSED at 14
  checkpoints; `--native-gem` PASSED its 10 keyboard steps (GEMDESK cold boot
  matching the CPU oracle, drive 9 detected as a 1581 with a D81, the
  directory, Calculator, Editor, Sheet and Paint opened from GEMDESK and
  returned); `--native-aes` PASSED (alert, menu bar, three windows, unload
  returning every page). Each restored and matched the drives, deleted its
  upload, left nothing behind and found the images unchanged; two runs had
  one host connection attempt time out before any request was sent.
- Hardware: `--native-pointer-timing` PASSED (6f0be67), as above.
- Hardware: `--native-apps` FAILED twice on VDC bitmap compares, both times
  as bytes displaced by one position (adjacent pairs swapped), the pattern
  this C128 shows after hours powered on: first at `calculator-result`
  (e99342b; the desktop check had passed the same checkpoint 90 minutes
  earlier), then at `paint-new` (6f0be67) after `calculator-result` passed.
  Its VICE twin passes. Drives, cleanup and images were clean both times.
- `ci_native_document` gains a case with chunks below 4 KiB in three
  separate runs, edits across their boundaries and growth after RAM returns,
  and checks the size nibbles and the leading-chunk count against the
  kernel's allocation records. A build that never counts leading chunks
  fails it, and so did a register clobber found while writing it.

## Not verified

- `--native-apps` has not passed on hardware: Paint, the Claude page, the
  Controls Drives page and the Sheet save to drive B are covered on hardware
  by no passing run. It needs a rerun after the C128 has been powered off.
- The pointer check runs over empty desktop space only; pointer cost over
  app surfaces on hardware is not measured.
- The large picker case at 30 pages (not reachable by padding) and at 36 (the
  padded build no longer fits the test disk image).
