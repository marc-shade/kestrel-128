# One bank-1 call per pointer move, and pointer jump filter (2026-10-09)

## Why

After the [pointer speed record](../2026-10-08-pointer-speed/README.md) the
80-column pointer still lagged on the reference C128. A Py65 profile of a
moving frame showed every pointer move making two bank-1 calls: operation 3
(update the pointer) and operation 5 (copy the 41-byte status record), each
paying the executor's entry checks and a page-tag walk over all 39 VDSVC
pages.

Hardware runs of the new build also showed the desktop selecting the SHEET
card with nobody at the mouse (selection 0 to 6, the same heap arguments
`$3d08..$3d0c` = `d2 22 24 00 07` each time). A one-sample pot reading 40
counts off moves the pointer from (160,160) to y 140, inside the card, and
back: Py65 reproduces exactly that on the previous build.

## Change

- **Status with the operation** (`vdc-service.asm`,
  `graphics/vdc-client.inc`). Display operations 1-4 return with the status
  record of operation 5 in `N_BUFFER`; the client no longer makes the second
  call.
- **Cached page-tag walk** (`banked.inc`, `kestrel.asm`, `heap.inc`,
  `module-cache.inc`, `api.inc`). ABI 1.16 adds `N_HEAPEPOCH` at `$1bf8` in
  the low section's padding: the kernel counts heap page-owner changes there
  (it was a main-section variable for the module gate). The executor still
  checks the image shape, handle record and generation on every call; it
  repeats the walk over every page tag only when the epoch or the handle tag
  changed since the last walk that passed. A page tag altered without a heap
  operation is caught at the next heap change, not at the next call.
- **Shared shape check** (`banked-load.inc`). `bk_load` stores the header
  fields and calls the same extent and entry check as each call, which saves
  about 45 bytes in every app (the Editor needed 20).
- **Pointer jump filter** (`input/pointer.inc`, generated
  `picker/pointer.inc`). A change of 12 counts (6 pixels) or more in one
  sample after a steady sample is held, and the baseline moves on to it. The
  next sample adds to the held counts: a single bad reading and its return
  cancel, and real motion lands one jiffy late in full. Jumps that follow a
  moved jump move at once. The driver keeps each axis's baseline itself and
  was compacted to fit every app (sprite register loop, pot presence test,
  edge clamp), with two tail calls in the file picker and GEMDESK.
- **Hardware harness** (`native_capture.py`, `native_vdc_check.py`). A
  capture that sees the app redraw the pointer (only the pointer bytes of the
  VDC argument packet or status record changed) raises `ObservationChanged`
  and the frame is retaken, as a moved pointer already was.

## Measurements (Py65 model, cycles per moving frame)

Thirty frames alternating dx +5/-5 with dy 3, so both axes move on every
frame and no step reaches the jump filter; before is the previous `main`
build (7807a20).

| Case | Before | After |
|---|---:|---:|
| Desktop 80 columns | 17,360 | 14,962 |
| Editor 80 columns | 30,942 | 28,386 |

## Tests

- `ci_native_banked`: a passed walk is reused until a heap page owner
  changes (446 against 2,785 instructions per call in the fixture), then
  repeated and refused on a cleared page tag; interrupt injection covers both
  the walking and the cached path. Fails when the cache never hits or ignores
  the epoch.
- `ci_native_pointer`: 81,920 counter pairs through the assembled routine,
  both axes, after a steady sample, after a moved jump and with eight held
  jumps (every pair for the first two, a spread for the held ones); a
  one-sample spike leaves the pointer and the desktop selection unchanged;
  fast motion (40 and 62 counts a sample, both directions) lands in full a
  sample late and never reverses. On the build before the filter the spike
  selects card 6; on the first filter build fast motion reversed (160, then
  136 moving right at 20 pixels a jiffy).
- `ci_native_editor_selection --case edges` and `ci_native_paint_gui --case
  mouse`: the drag and the stroke follow the pointer's actual position, which
  is either unchanged (a held first jump) or the intended endpoint, and must
  reach every endpoint. A held first jump draws one straight segment where
  two samples would have drawn a corner.
- `ci_native_vdc_desktop --case core`: the same-column redraw walk keeps its
  steps under 6 pixels, so the filter never holds them.
- `ci_native_vdc_paint`: the 10-pixel stroke step is held a sample (asserted)
  and lands before the button is released.
- `ci_native_capture`: a redraw during a capture is reported with exactly
  the changed address; a frame retakes only pointer-byte changes and still
  fails on any other change.
- `ci_native_modules`, `ci_native_apps`, `ci_native_loader_ultimate`: ABI
  minor 17 is now the first refused; 1.16 is accepted.
- Full sweep (`tests/sweep_native.py` through the resumable driver, from a
  snapshot of this tree; the images in the commit are byte-identical to it):
  CPU 323/323. VICE 58/60: `ci_native_pointer_iec --files-only
  --files-open-with --d81` and its `--files-find` variant fail some runs
  (see Not verified).

## Hardware

Hardware `--native-desktop` on these exact images passed all eleven screens
(209 busy IRQs over 683 captures; no pointer retake was needed). The first
filter build had passed the same check (194 busy IRQs over 683 captures)
before the sweep found its fast-motion reversal.

Earlier the same day, after many hours powered on, three builds (including
the previous day's passing one) each lost or gained a single byte in one VDC
bitmap or attribute line. After a 30-minute power-off, a build with the
slower VDC access timing and one with the inline ready test both ran clean.
The errors followed the machine's temperature, not the code, so the inline
ready test from the pointer speed record stays.

## Known limits

- The filter's delay on a first jump: a 6-pixel or larger step from rest
  that is released within the same jiffy lands with the button up, so a
  stroke or drag loses that last step; a fast stroke from rest draws its
  first two samples as one segment.

## Not verified

- VICE `ci_native_pointer_iec --files-only --files-open-with --d81`: in the
  Files copy dialog, the capture probe sometimes never finds the foreground
  idle at an IRQ and times out after 60 s (7 of 33 runs of this build, 0 of
  16 runs of builds without the filter or with it disabled by threshold,
  PM_JUMP=65). At the timeout the pointer is still (pots jitter by one
  count, under the 2-count dead zone, the same instruction path either way),
  the MMU state passes the probe's checks, and N_READY reads 1 to the host
  but 0 at each IRQ. The cause of the association with the filter is not
  found. A separate "extra ROM key" failure in the same job (a host key
  release arriving after the next app has scanned it) also occurs with the
  filter disabled.
- Pointer speed on real hardware: no cycle count was taken on the C128.
- The cause of the wild pot sample. The filter removes its effect; the
  sample itself was not captured on hardware.
- The 8563 temperature: no measurement, only the power-off result.
