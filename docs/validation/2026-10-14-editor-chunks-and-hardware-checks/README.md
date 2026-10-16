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

e5b2449 reads the background under the pointer straight after its seek
instead of after a priming read; the capture probe reads the same way and
matched on hardware. In Py65 a desktop pointer frame went from 13,618 to
12,242 cycles. The same check at 95ce2e6 (disk image 7168a9df...), 512
updates, none missing, calibration exact:

| Cycles | Min | Mean | Median | p95 | Max | Under one frame |
|---|---:|---:|---:|---:|---:|---:|
| Service redraw | 11,085 | 12,405 | 12,270 | 13,660 | 14,289 | 100% |
| Whole bank call | 14,034 | 15,400 | 15,279 | 16,673 | 17,246 | 99.8% |

Updates came 1 jiffy apart in 253 of 511 intervals and 2 jiffies apart in
258, almost strictly alternating. The 1351 schedule explains it: `pm_poll`
notices a new jiffy only in raster lines 80 to 159 and samples 32 lines
later, so a sample falls in lines 112 to 159. When one loop pass, from the
sample to the next poll, takes more than 231 raster lines (about 15,000
cycles), each update starts later in the frame than the one before until
one misses the window and waits a jiffy. These passes took about 255 to 278
lines.

The redraw then stopped restoring and redrawing a row in two passes. A move
of fewer than 16 rows to the same or a neighbouring byte column now visits
each row either position covers once, in the direction of the move, so a
row's saved background is reused before the row 16 away overwrites its
slot. A row both cover is one write run (the old position's uncovered byte,
if any, and the new arrow) after reading at most one byte; the timing
check's dx of 5 is always a neighbouring column. Other moves, and the one
byte wide arrow at column 79, keep the restore-then-draw path. In Py65 a
desktop pointer frame went from 12,242 to 10,454 cycles; VDSVC grows from
32 to 35 pages. The same hardware check (disk image with the new
`vdsvc.prg`):

| Cycles | Min | Mean | Median | p95 | Max | Under one frame |
|---|---:|---:|---:|---:|---:|---:|
| Service redraw | 8,567 | 9,836 | 9,922 | 10,626 | 11,135 | 100% |
| Whole bank call | 11,398 | 12,784 | 12,890 | 13,623 | 14,093 | 100% |

Updates came 1 jiffy apart in 508 of 511 intervals and 2 apart in 3: the
pointer moves at 60 Hz over empty desktop space. The shipped desktop D64 now
has 1 block free, too little for the larger instrumented images, so the
measurement disk also leaves out `shcalc.prg`, a Sheet module the timed
desktop never loads. `ci_native_vdc_desktop` checks the read count of every
move against the new rule and adds moves a column left and right, up and
down, over the menu bar, whose rows differ: a build that walks upward moves
top to bottom fails it, while over the uniform space at x 304 and beyond it
passed.

## VDC write drift on the C128

`--native-apps` and `--native-apps-only` failed six more times before passing.
Run 3 was stopped by the operator's timeout after 15 checkpoints; run 4 timed
out waiting for Esc to leave Calculator; run 5 stopped when a pointer redraw
changed the borrowed buffer at $3a1c during the desktop-boot mode capture,
which that capture does not retry. The rest were VDC bitmap compares:

| Run | Images | Checkpoint | VDC bitmap |
|---|---|---|---|
| 1 | e99342b | `calculator-result` | bytes one position off |
| 2 | 6f0be67 | `paint-new` | bytes one position off |
| 6 | 3afc094 | `controls-drives` | Drives tab rows 32 to 47 not highlighted; row 45 one byte right |
| 7 | 3afc094, apps-only | `controls-drives` | bitmap row 11 of the close box one byte left |

Run 7 started 25 minutes after a power-off, so these are not heat. The
reference VDC runs in 64 KiB colour mode (`vd_color` 1). The capture probe
reads one VDC byte per address and checks R18/R19 after each; it logged
address resyncs in runs 1, 2, 3, 6 and 7, from the first desktop capture on,
and none in the passing `--native-desktop` run. The VICE twin passes with both
16 and 64 KiB VDCs. So this 8563 occasionally lands a write without advancing
its update address, or advances twice, and every later byte of that run lands
one position off.

edd9d40 checks R18/R19 after each 80-byte bitmap and attribute run in the
shared VDC service and writes a drifted run again (three tries, then
`N_IOERROR`); `vm_rewrites` counts them. `tests/ci_native_vdc_drift.py`
injects one drift in each direction, in a bitmap and an attribute run, on 16
and 64 KiB VDCs, and requires an exact surface after exactly one rewritten
run; with the check disabled it fails on the bitmap. The hardware apps check
records `vm_rewrites` before each Paint, Controls and Sheet comparison, and
the VICE twin requires every count to be 0.

Run 8 (`--native-apps-only`, 83a03e5, the C128 on for over three hours)
PASSED: every Paint screen, the Claude landing page and return, the Controls
Drives page against REST, and the Sheet Save As to drive B, whose retrieved
image held exactly BUDGET (8,208 bytes). The service rewrote drifted runs
during it, counts cumulative within each app:

| Checkpoint | `vm_rewrites` |
|---|---:|
| `paint-new`, `paint-pen-origin`, `paint-ink2-right` | 1 |
| `paint-undo` | 2 |
| `paint-discard-prompt` | 3 |
| `controls-drives` | 2 |
| `sheet-save-new` | 0 |
| `sheet-save-calculated` | 2 |
| `sheet-saved` | 6 |

The probe logged 2 resyncs on its own reads. Drives were restored and matched,
uploads deleted, nothing left behind, images unchanged, no host connection
failures.

Run 9 (the full `--native-apps`, cad29c1) failed in the prelude before any
app compare: the Files launch took over 428 seconds amid Ultimate network
timeouts, and an idle capture admission gave up after 7 looks inside its 30
second bound. 1d6b144 gives up only after both 30 seconds and 40 looks;
`ci_hardware_uploads` has a case with slow looks that the old bound fails.

e5a8446 moves the check into a shared `vd_verify` and applies it to every
block run as well: the open-time snapshot, the close-time restore and the
desktop scene. The counter is now `vd_rewrites`. `ci_native_vdc_drift.py` has
14 cases (writes, reads and the restore, both directions, 16 and 64 KiB); with
the check disabled all 14 fail. The mode capture also retries when only a
pointer redraw changed its borrowed buffer (run 5); `ci_native_capture` has
cases for it that the old code fails.

Run 10 (`--native-apps-only`, 95ce2e6, the C128 on for over two hours)
PASSED with 976 capture admissions, none deferred more than once:

| Checkpoint | `vd_rewrites` |
|---|---:|
| `paint-new`, `paint-pen-origin` | 1 |
| `paint-ink2-right`, `paint-undo`, `paint-discard-prompt` | 2 |
| `controls-drives` | 0 |
| `sheet-save-new` | 0 |
| `sheet-save-calculated` | 3 |
| `sheet-saved` | 9 |

Drives were restored and matched, uploads deleted, nothing left behind,
images unchanged, no host connection failures.

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
- Hardware: `--native-apps` FAILED on VDC bitmap compares at
  `calculator-result` (e99342b; the desktop check had passed the same
  checkpoint 90 minutes earlier), then at `paint-new` (6f0be67), and later
  runs failed as described above, until the drift check. Drives, cleanup and
  images were clean every time.
- 3afc094 (`--native-apps-only`): CPU sweep 324/324, VICE sweep 65/65.
- edd9d40 to 83a03e5 (VDC drift check and rebuilt images): CPU sweep 325/325,
  VICE sweep 65/65 (both apps twins with every `vm_rewrites` 0).
- Hardware: `--native-apps-only` PASSED (83a03e5), as above.
- Hardware: `--native-apps` FAILED (cad29c1, run 9) at an idle capture
  admission in the Files prelude, as above.
- e5a8446 to c7f13c2 (block-run drift check, mode capture retry): CPU sweep
  325/325, VICE sweep 65/65.
- e5b2449 to 95ce2e6 (pointer read, admission bound): CPU sweep 325/325, VICE
  sweep 65/65.
- Hardware (95ce2e6 images): `--native-pointer-timing` PASSED and
  `--native-apps-only` PASSED (run 10), as above. `--native-desktop` first
  refused to start: it admits only a pinned disk image, still the 6806b13
  one. With the pin moved to 7168a9df... it PASSED all 14 checkpoints
  (Calculator, Editor, Files and Sheet from the desktop, then the workspace),
  restoring and matching the drives, deleting its upload, with the images
  unchanged and no host connection failures.
- One-pass pointer step (VDSVC 35 pages): CPU sweep 325/325, VICE sweep
  65/65. The two pointer-timing jobs first failed on a tree without the
  `shcalc.prg` removal (c1541 could not fit the instrumented images) and
  passed on the tree with it. The VICE twin measured a whole bank call mean
  of 13,697 cycles, all 512 under a frame, with updates 1 jiffy apart in 441
  of 511 intervals.
- Hardware (pointer step images): `--native-pointer-timing` PASSED, as above.
  With its pin moved to the new disk image (de603582...; the kernel is
  unchanged), `--native-desktop` PASSED all 14 checkpoints with 590 capture
  admissions, restoring and matching the drives, deleting its upload, with
  the images unchanged and no host connection failures.
- Hardware (e2da4ce images, the C128 on for about seven hours):
  `--native-apps-only` PASSED every Paint, Claude, Controls and Sheet
  checkpoint with 996 capture admissions, restoring and matching the
  drives, deleting its uploads, with the images unchanged and no host
  connection failures. `vd_rewrites`: `paint-new` to `paint-undo` 0,
  `paint-discard-prompt` 3, `controls-drives` 2, `sheet-save-new` 0,
  `sheet-save-calculated` 2, `sheet-saved` 5.
- Hardware (2b4fc32 images, run 11, the C128 on for about nine hours): the
  full `--native-apps` passed its Calculator, Editor and Files prelude (10
  checkpoints, every VDC compare), then `paint-new` and `paint-pen-origin`
  (`vd_rewrites` 3), and FAILED on the next one-byte read of Paint state:
  between the idle admission and the restore, most of `N_BUFFER` changed,
  including the VDC packet bytes a pointer redraw writes (other VDC service
  calls write them too), and so did the kernel's heap walk (`haddress`,
  `hbound`). Paint, or a service it called, was working while the probe
  borrowed its buffer, which the observer cannot retake safely. What
  started that work is not established. Paint keeps the default pointer
  start (160,160), which is on its canvas, so any pointer motion there
  moves Paint's cursor and redraws its status line. Drives were restored and matched, uploads deleted,
  images unchanged, no host connection failures.
- `ci_native_document` gains a case with chunks below 4 KiB in three
  separate runs, edits across their boundaries and growth after RAM returns,
  and checks the size nibbles and the leading-chunk count against the
  kernel's allocation records. A build that never counts leading chunks
  fails it, and so did a register clobber found while writing it.

## Not verified

- The full `--native-apps` has not passed in one run since the drift check:
  run 11 passed its prelude and failed in Paint, and the apps-only run
  passed Paint, Claude, Controls and Sheet on the same images. A capture
  fails, by design, when the app starts work while the probe borrows
  `N_BUFFER`; what started Paint's work in run 11 is not established.
- The pointer redraw, single register pokes and the VDC's own block fills and
  copies do not check their writes for drift; a drifted write there is not
  repaired.
- The Controls Info, Network and Clock pages, Paint mouse drawing and file
  I/O, and the Claude serial session are not checked on hardware.
- The pointer check runs over empty desktop space only, with steps to the
  neighbouring byte column; pointer cost over app surfaces, and for longer
  or same-column steps, on hardware is not measured. A real 1351 moved by
  hand was not part of any run.
- The shipped desktop D64 has 1 block free; any growth of its programs needs
  room made on that image (the D81 is unaffected).
- The large picker case at 30 pages (not reachable by padding) and at 36 (the
  padded build no longer fits the test disk image).
