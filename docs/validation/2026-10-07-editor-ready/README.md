# Editor readiness and desktop-check reads (2026-10-07)

## Why

On the reference C128 the idle 80-column Editor made the IRQ observer skip
about 9,000 to 10,000 IRQs per `--native-desktop` run
([desktop hardware record](../2026-10-07-desktop-hardware/README.md)). A Py65
measurement (64 KiB VDC) found it by design, not pointer drift: `eg_vdc_sync`
cleared `N_READY` on every input-loop pass (a 545-cycle idle pass was 73% not
ready) and the graphics module is called twice per jiffy for the pointer
(about 3,600 cycles each, 2,000 of them in the kernel module gate).

## Change

- **Editor readiness** (`src/native/editor.asm`, `src/native/editor/vdc.inc`).
  `eg_vdc_sync` no longer clears `N_READY` on every pass; `vd_open`,
  `vd_close`, `vm_present` and `vd_poll` clear it themselves before they use
  `N_BUFFER`, the bank-1 service or the VDC. The input loop publishes
  `N_READY` = NOT (`vm_pending` AND `vd_live`), so rows the VIC already shows
  but a live VDC does not are presented before the next publish (hardware run
  6 caught a capture in that window). `eg_repair_text` clears `N_READY`
  before it redraws; `dm_ensure` works only after a key path reset it. The
  Editor still fits its window: a `jsr`/`rts` became `jmp` and the pointer
  x/y copy became a loop over adjacent bytes. In Py65 an idle pass is now
  ready throughout; the two module calls per jiffy are unchanged.
- **Desktop-check reads on the C128** (`native_vdc_check.py`,
  `hw_native_desktop_check.py`). The VDC state and every app byte the check
  reads at `$4000` and above (`cg_bitmap`, `fg_bitmap`, `pm_seen`,
  `vs_reu`) now go through the IRQ observer: runs 5 and 7 failed on direct
  REST reads that returned BASIC ROM (the VDC state read in run 5 returned
  BASIC HI `$8a1f`).
- **Focus follows the pointer** (`hw_native_desktop_check.py`). Hovering a
  control while the pointer moves gives it focus, and the shared pointer start
  (160,160) is the bottom edge of the Calculator's + button and of a Files
  control, so the reference machine's one-row drift moved the focus (run 8).
  The Calculator and Files frames now read the app's own selection on the
  C128 before and after the bitmap, retake an attempt where it changed, and
  compare with it, as the VICE and Py65 checks do.

## Audit

A Py65 detector ran the desktop, Calculator, Editor and Files with a 64 KiB
VDC through startup, 20 idle frames and pointer moves across the screen, and
recorded every write to the VIC surface, the VDC ports or the 40-column
screen while `N_READY` = 1: none in any app (control: 19,725 to 87,423
surface writes counted while not ready). VDC writes all go through the bank-1
service, whose calls clear `N_READY` first.

## Tests

- Py65: `ci_native_vdc_editor` (64 KiB keyboard, 16 KiB mouse) and
  `ci_native_editor_gui` keyboard, including the no-VDC Editor that a first
  version of the readiness rule left unpublished.
- Full sweep on these images (`tests/sweep_native.py` through the resumable
  driver, from a snapshot of this tree): CPU 323/323, VICE 60/60 (`ci_native_pointer_iec --80col` timed out once waiting for a Paint button in the three-way pass, after Xvfb reported a display collision, and passed run on its own).
- Hardware `--native-desktop` on intermediate builds: runs 6 to 9 counted
  116, 18, 14 and 251 busy IRQs (about 10,000 before). None passed: run 6
  found the mirror window above, 7 a direct ROM read, 8 the Calculator focus,
  9 a Files capture whose kernel heap state and `N_BUFFER` changed between
  chunks (the Files app working during the capture; addressed by the separate
  per-app pointer start).

## Not verified

- No `--native-desktop` hardware pass on this build.
- The idle cost of the two module-gate calls per jiffy is unchanged.
