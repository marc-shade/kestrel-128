# Resting 1351 noise, and idle apps that the observers could not see (2026-10-11)

## Why

A hardware `--native-desktop` run of the [hover record](../2026-10-10-desktop-hover/README.md)
images failed on the Calculator screen with nobody at the mouse: the bitmap
capture was retaken three times because the pointer moved during each one.
The recorded pointer sat at x 344 while y flipped between 172 and 173.

Sampled 200 times at rest, the reference 1351 read X 143 or 144 and Y 141 or
142: the noise does not stay in bit 0, as the 1351 intends, but straddles a
count boundary. The driver ignored a 1-unit difference but moved on 2 and kept
its baseline on the reading that last moved the pointer. Once that reading was
the lowest or highest of three resting values, the noise moved the pointer a
pixel back and forth for as long as the mouse lay still, and each step cost a
full 80-column pointer redraw. Commodore's own 1351 driver uses the same rule.

## Change

- **Pointer** (`input/pointer.inc`, and the picker's copy in
  `picker/pointer.inc`). After a one-pixel step up the counter (2 or 3 units)
  the baseline trails the reading by one unit. Resting noise then stays within
  one unit of it, and the pointer settles after at most two one-pixel steps.
  A reversal from there measures 2k-1 units, which still floors to k pixels,
  and every other move is unchanged, so no motion is lost. The 7 bytes this
  adds are paid for in the same driver (`pm_place` merges `$d010` without a
  temporary, the vertical clamp subtracts without `pm_step`): every app is
  6 bytes smaller. A first version that trailed after every move cost one
  pixel at every reversal and failed the Paint stroke and desktop step tests;
  it was replaced.
- **Sheet** (`sheet/gui.asm`, `sheet/main.c`). The 6-byte shift broke all four
  `ci_native_sheet_iec` jobs although Sheet worked: its main loop presented and
  polled on every pass and published `N_READY` only around its KEYIN call. The
  IRQ capture observer and VICE's monitor both look at a fixed point in the
  frame, so whether they ever found Sheet idle depended on the loop's phase.
  Sampled 150 times after launch in VICE, the previous build was ready in 10.7% of
  samples and this one in none; 6 bytes of padding after the driver made the
  suite pass again. Sheet now waits in `sg_wait`, as the AES does: `N_READY`
  stays published while it polls KEYIN and drives `pm_poll` through each 1351
  read, until a key arrives or a read completes. `sg_polled` then handles the
  pointer without polling again.
- **Files** (`files/presentation.inc`). `fg_input` synced the VDC on every
  pass, and the sync clears `N_READY` first. With no key, no sample due, no
  rows pending and the VDC already attempted, it now returns without the
  sync. This was the Copy dialog capture timeout of `ci_native_pointer_iec`
  on D81, unexplained since the
  [2026-10-09 record](../2026-10-09-bank-call-and-pointer-jumps/README.md);
  it failed 4 of 4 runs on the pointer commit and passes now.
- **Tests.** `ci_native_pointer`'s exhaustive counter-pair model uses the
  trailing baseline, and a new case cycles three resting readings after one-
  and three-pixel steps both ways on both axes, from either edge of the noise:
  at most two one-pixel steps, then stillness. The previous driver fails it
  (x flips between 101 and 102). `ci_native_vdc_desktop` no longer steps one
  pixel back right after a one-pixel step, which the driver now holds as
  noise until a second count.
- **Test runner.** `tests/sweep_native.py` imports every suite to list its
  jobs. Run by an interpreter without py65, every suite fell back to one
  argument-less job (133 CPU jobs instead of 323, nearly all failing at once);
  it now stops with the reason.

## Gates

All on the build-output commit that closes this change, run from a clean
clone of it.

- CPU sweep (`tests/sweep_native.py`, PyPy, 4 jobs): 323/323.
- VICE sweep (3 jobs): 59/60 in parallel. `ci_native_keyboard_iec` failed
  with "real keyboard consumed" after 20 s and passed when rerun alone, as it
  did on the pointer commit; 60/60.
- `hw_ultimate_check.py --native-desktop` on the C128: PASS. 218 captures,
  154 IRQs passed through busy, no Calculator retake (the screen that failed
  before this change). Four Ultimate TCP connects timed out before sending and were retried.
- `hw_ultimate_check.py --native-editor` on the C128: PASS. The saved files
  were verified independently, the drives restored and the uploads deleted.

## Not verified

- The C128 was not sampled for long periods at rest; the three-value spread
  is what 200 samples and the failed run showed. A wider spread would still
  move the pointer.
- The Sheet and Files idle waits were measured in VICE. On hardware, the
  desktop check covers Files and the editor check covers the Editor; no
  hardware check opens Sheet.
- Other apps whose loops publish `N_READY` only briefly (for example the
  forms dialog loop) were not changed; none failed.
