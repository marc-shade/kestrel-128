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
  borrowed its buffer, which the observer cannot retake safely.
- Hardware (3cc97c7 images, run 12, the C128 on for about 20 hours): the
  full `--native-apps` passed its prelude again (10 checkpoints), then
  FAILED on the first read of Paint state, before `paint-new`: only
  `N_BUFFER` bytes 4, 26 and 28 changed, the status record a VDC service
  call writes back. Bytes 26 and 28 are `vd_pointer_x` and `vd_pointer_y`:
  the pointer went from (8,32), where Paint places it for its cursor at
  the canvas origin, to (7,33). In run 11 the same bytes went from (9,32),
  the cursor one step right, to (8,33). Both times the 1351 pointer
  stepped one pixel left and one down with nobody at the mouse, and Paint,
  which follows the pointer, worked while the probe held its buffer. A
  slow drift of the resting 1351's readings would give same-direction
  steps on a machine on for many hours; that cause is inferred, not
  measured. Drives were restored and matched, uploads deleted, images
  unchanged, no host connection failures.
- Hardware (f7d5f7e tree, the e2da4ce images as in runs 11 and 12, run 13, started
  minutes after a power cycle): the full `--native-apps` PASSED all 25
  checkpoints in one run (the 10 prelude checkpoints, the five Paint
  checkpoints, the Claude landing page, `controls-drives`, the three Sheet
  saves, each return to the desktop and `workspace-returned`) with 1,348
  capture admissions, restoring and matching the drives, deleting its
  uploads, with the images unchanged, no uncertain host writes and no host
  connection failures. The desktop disk was the pinned image (de603582...).
  `vd_rewrites`: `paint-new` 2, `paint-pen-origin` 2, `paint-ink2-right` 3,
  `paint-undo` 3, `paint-discard-prompt` 5, `controls-drives` 0,
  `sheet-save-new` 0, `sheet-save-calculated` 5, `sheet-saved` 9. One REST
  read timed out early in the prelude and its retry succeeded.
- `hw_native_apps_check.py` now also checks the Controls Info, Network and
  Clock pages and a keyboard Save As of a Paint picture to device 9 through
  the picker (`paint-saved`). The page references come from outside the
  app's UCI client: the control target identification from the firmware
  source; the interface address from the Ultimate's FTP greeting, with
  mask and gateway from the host's DHCP route on the same LAN (REST reports
  DHCP enabled); and two Clock readings against the RTC time the Ultimate
  stamped on the system disk upload (FTP MLSD; FAT stamps and GET_TIME both
  read the cartridge RTC), advanced by host elapsed time. The interface count
  (1) is an expectation the page compare tests. The retrieved data disk must
  hold exactly PICTURE and BUDGET. The VICE twin (no cartridge) passes both
  sweep variants, and checks the reference builder on a fake Ultimate,
  including rejected greetings and mismatched static settings.
- Hardware (run 14, `--native-apps-only` with those checks, the C128 on
  for about four hours): every Paint checkpoint passed, including
  `paint-saved` (status "Saved and verified", name and device held, picture,
  bitmap and VDC). The retrieved drive-B image held exactly PICTURE, SEQ,
  9,016 bytes, equal to the independently encoded UPNT file. Claude passed.
  `controls-info` FAILED its bitmap compare: the model line read
  `1541 ULTIMATE II`, not the FTP greeting's `Ultimate-II`, so this firmware's
  model reply is not the `getProductString()` of the pinned source; the
  identity line matched. The model is now a pinned observation (labelled as
  not independent); with it, the prediction equals the captured 9,216-byte
  Info bitmap. Drives restored and matched, uploads deleted, images
  unchanged.
- Hardware (run 15, the same checks with the pinned model, about 30 minutes
  later): FAILED at the first Paint state read, before `paint-new`. During
  the read `N_BUFFER` gained rows of glyph-like bytes and `vd_stack` moved
  by 2 (a VDC service call in progress), with the record's pointer position
  unchanged; Paint was drawing while the probe held its buffer. A status
  line redraw after pointer motion that returned to the same position would
  look like this; that cause is inferred. Drives restored and matched,
  uploads deleted, images unchanged.
- Hardware (run 16, `--native-apps-only`, 17f78a4 tree, the 1351 unplugged
  from control port 1): every checkpoint through `sheet-saved` passed (21),
  including `paint-saved` and all five Controls checkpoints. Network showed
  the address in the FTP greeting with the DHCP route's mask and gateway;
  the two Clock readings were 6,497 s and 6,930 s after the upload stamp,
  inside their host elapsed bounds. The host `timeout` (10,000 s) then
  killed the harness during the last `sheet-saved` capture, so the run has
  no verdict and did not restore the drives. Its drive-B image, fetched over
  FTP, passes `verify_data_disk` offline (PICTURE and BUDGET); both harness
  mounts were then removed by hand, matching the recorded `drives_before`
  (A and B empty). Its two uploads were left in `/Temp`. The new checks take
  1,211 admissions here against about 980 before, which is why 10,000 s
  was no longer enough.
- Hardware (run 17, the full `--native-apps`, same tree, 1351 still
  unplugged): PASSED all 30 checkpoints in one run (the 25 of run 13 plus
  `paint-saved`, `controls-info`, `controls-network`, `controls-clock-0`
  and `controls-clock-1`) with 1,652 capture admissions in about 270
  minutes, restoring and matching the drives, deleting its uploads, with
  the images unchanged, no uncertain host writes and no host connection
  failures. Clock read `13:50:59` and `13:59:32`, 11,235 s and 11,748 s after
  the upload stamp, inside bounds of [11,218, 11,277] and [11,730, 11,790].
  The retrieved data disk held exactly PICTURE (9,016 bytes) and BUDGET
  (8,208 bytes), byte-identical to run 16's (313e8266...). `vd_rewrites`:
  Paint 3, 3, 3, 5, 5, 5; Controls and Sheet 0.
- `hw_native_apps_check.py` now also checks Paint Open (47133a3): after
  Undo, a second U redoes to the saved picture, O lists device 9 and Return
  opens PICTURE. `paint-opened` checks the state (status "Opened; Undo
  restores old image", name and device), the banked picture, bitmap and VDC,
  and that the load put the picture in a new allocation with the former one
  as the undo slot, since the pixels equal the document already shown. A new
  pixel at (2,0) then makes it dirty for the discard prompt. The VICE twin
  passes both sweep variants (30 and 21 checkpoints).
- Hardware (run 18, `--native-apps-only` at 47133a3, 1351 still unplugged):
  PASSED all 22 checkpoints, including `paint-opened` (handles: former 3,
  opened 7 with 3 as undo), with 1,368 capture admissions in about 207
  minutes, restoring and matching the drives, deleting its uploads, with the
  images unchanged and no uncertain host writes. One RAM write request timed
  out before it was sent and was retried (recorded under
  `host_connect_failures`). Clock read 7,636 s and 8,118 s after the upload
  stamp, inside bounds. The retrieved data disk is byte-identical to runs
  16 and 17. `vd_rewrites`: Paint 2, 2, 2, 3, 4, 5, 5; Controls and Sheet 0.
- Performance (f5f15ce, 979c0e9): a partial cell row in the graphics core
  now reads and writes its band once each way instead of once per scanline.
  `bench_native_perf.py` (Py65 cycles, ready-VDC model): the Paint status
  line from 263k to 164k cycles, a Paint swatch move from 161k to 122k.
  (ad53c60): the colour VDC attribute byte comes from a pre-shifted palette
  table; focus changes in Calculator, Controls and Paint take 8 to 11% fewer
  cycles. Both are emulator cycle counts; no hardware run times them. CPU
  sweep 325/325 and VICE sweep 65/65 on the combined tree.
- Hardware (run 19, the full `--native-apps` at 979c0e9, 1351 unplugged):
  FAILED at `controls-info` after 20 checkpoints, every Paint checkpoint
  before it passed. Controls' VDC state read phase 0, live 0, colour 0,
  fault $11 (`N_IOERROR`), base 0, pages 0. Two paths leave exactly that
  after Controls' client (`graphics/vdc-client.inc`) closes: VDSVC.PRG
  failing to load, or a `vd_wait` timeout in the service's first register
  reads, before it changes anything. In both the 8563's contents and
  registers were not changed. The Controls launch took 119 s against 155 s
  on the passing runs, which fits a load cut short better than a full load
  followed by a failed open, but does not decide it. Controls showed its
  VIC page normally. Nothing left in RAM tells the two apart: the load's
  file status is cleared by the client's own `N_FCLOSE` (every file call
  clears `N_FDOS`/`N_FSTATUS`), and `N_DOSCODE`/`N_IOSTATUS` are kept only
  for the launcher's loads. A suspect for a failed load (run 23 below):
  after the 30 s quiet interval the harness polls RAM by REST DMA every 2 s
  until the launch completes, during the remaining IEC loads. Drives
  restored and matched, images unchanged. The same check passed on the next
  two runs.
- Hardware (run 20, `--native-apps-only` at ad53c60, desktop D64
  d57a1ed0...): PASSED all 22 checkpoints with 1,368 capture admissions,
  restoring and matching the drives, with the images unchanged and no
  uncertain host writes (one resume request timed out before it was sent
  and was retried). The retrieved data disk is byte-identical to runs 16 to
  18 (313e8266...). `vd_rewrites`: Paint 2 at each checkpoint; Controls and
  Sheet 0.
- Hardware (run 21, the queue at ad53c60, 1351 unplugged): `--native-desktop`,
  `--native-gem`, `--native-pointer-timing` (512 updates), `--native-editor`,
  `--native-files`, `--native-redraw` and the full `--native-apps` PASSED, the
  last with all 31 checkpoints and 1,740 capture admissions in about 289
  minutes; its three host connection failures were requests not sent and
  retried, its data disk is byte-identical to run 20's and `vd_rewrites` was
  0 at every checkpoint. `--native-aes` FAILED in the `menu-bar` capture
  with probe status 2: the held probe waited about 20 seconds for the host
  handshake and released, while the host's REST request to the Ultimate
  timed out at the same time. Drives restored and matched, images
  unchanged. Rerun alone on the same images (run 22), `--native-aes`
  PASSED: alert, menu bar, three windows and the unload, with no host
  connection failures, drives restored and matched, images unchanged. The
  run 21 failure is taken as the host link, not the build; that is
  inferred from the coincident timeout, not measured.
- Hardware (run 23, a stress test, not a release check): `--native-apps-only`
  on run 21's images with the harness polling for completion every 0.05 s
  instead of every 2 s after a launch or file key's 30 s quiet interval.
  Paint launched in 173 s and five checkpoints passed through `paint-undo`;
  then the Open of PICTURE ended with Paint's "Checksum wrong; picture
  kept" (`pa_status` 6) where runs 18, 20 and 21 showed "Opened". Each poll
  is a REST DMA read that stops the CPU, and the serial bus does not wait
  for a stopped listener, so a poll inside a byte can lose bits. Paint's
  checksum caught the bad read and kept the picture as designed. Drives
  restored and matched, images unchanged. This is the measured cause of a
  failed load under host polling; it is the likely, not the measured, cause
  of run 19.
- The apps check now waits 90 s without DMA after each launch or file key
  and then polls every 10 s (`IO_QUIET`, `IO_POLL` in
  `hw_native_apps_check.py`; `io_poll` in `run_native_workflow`, which keeps
  the old behaviour for every other caller). Most of these operations take
  100 to 180 s, so polls during their IEC traffic drop from dozens to a few.
  Hardware (run 24, the full `--native-apps` on run 21's images with this
  harness, 1351 unplugged): PASSED all 31 checkpoints, including
  `paint-opened` and `controls-info`, with 1,740 capture admissions in about
  292 minutes (run 21: 289), no host connection failures and no uncertain
  host writes. Its 21 launch and file waits took 91 to 445 s; five ended
  at about 91 s, the new floor. The retrieved data disk is byte-identical
  to run 20's (313e8266...), the independent readback found PICTURE and
  BUDGET, and drives were restored and matched with the images unchanged.
  `vd_rewrites`: Paint 1 to 3, Controls and Sheet 0. One pass shows the
  quieter waits cost nothing measurable; it does not show they prevent a
  failure that occurred once in four full runs.
- `ci_native_document` gains a case with chunks below 4 KiB in three
  separate runs, edits across their boundaries and growth after RAM returns,
  and checks the size nibbles and the leading-chunk count against the
  kernel's allocation records. A build that never counts leading chunks
  fails it, and so did a register clobber found while writing it.

## Not verified

- The full `--native-apps` passed four times: run 13 with the 1351 attached
  on a freshly powered C128, and runs 17, 21 and 24 (with the new checks)
  with the 1351 unplugged. Run 19's Controls VDC failure (a failed VDSVC.PRG
  load or a VDC ready timeout) has no measured cause. Runs 11, 12 and 15 failed in Paint, with the 1351 attached,
  when Paint worked during a read: in 11 and 12 the resting pointer had
  stepped one pixel; in 15 its position was unchanged. A capture fails, by
  design, when the app starts work while the probe borrows `N_BUFFER`. The
  cause of the resting pointer's motion is not measured, Paint still starts
  its pointer on the canvas, and the new checks have not passed with the
  1351 attached.
- The Controls Info model line is pinned to the value this machine showed,
  not an independent reference; the interface count is an expectation.
- The pointer redraw, single register pokes and the VDC's own block fills and
  copies do not check their writes for drift; a drifted write there is not
  repaired.
- Paint mouse drawing needs a hand on the 1351, and the Claude serial
  session needs a qualified hardware shutdown observer; neither is checked
  on hardware. Paint Open is checked only for a file Paint itself saved, with
  no dirty-picture Open prompt and no failed or cancelled load.
- The pointer check runs over empty desktop space only, with steps to the
  neighbouring byte column; pointer cost over app surfaces, and for longer
  or same-column steps, on hardware is not measured. A real 1351 moved by
  hand was not part of any run.
- The shipped desktop D64 has 1 block free; any growth of its programs needs
  room made on that image (the D81 is unaffected).
- The large picker case at 30 pages (not reachable by padding) and at 36 (the
  padded build no longer fits the test disk image).
