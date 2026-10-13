# Parallel VICE jobs on one X display, Sheet on hardware, resting noise over ten minutes (2026-10-12)

Follow-up to the [resting pointer record](../2026-10-11-pointer-rest-noise/README.md),
which left three items open: `ci_native_keyboard_iec` failing only in
parallel sweeps, no hardware check opening Sheet, and a noise spread taken
from 200 samples.

## Parallel keyboard failures

`tests/cbm_tools.py` gave each emulator an Xvfb display by taking the first
number without a socket. Two tests starting together could take the same
number: the second server failed, the first one's socket made it look ready,
and both emulators ran on one display. `ci_native_keyboard_iec` sends real
key presses through XTest, so they reached whichever window had focus: one
test's Up press consumed three keys while the other's Down press consumed
none. Running four copies at once, five times, failed 16 of 20.

Xvfb now claims its own display (`-displayfd`). The same run then failed 4 of
20, all in the negative control, which reinstalls the ROM keyboard callback
to show what the guard prevents. Joystick Down holds keyboard row 1 low in
every column; a release that lands inside the ROM's column scan leaves only
some columns lit and decodes as another row-1 key (Y, I or a keypad digit)
after the Insert. That is the ROM's behaviour, not Kestrel's, so the step now
accepts one or two keys and still requires that nothing was rejected. 20 of
20 passed: 19 runs saw the single Insert, one saw Insert and then I.
`ci_native_pointer_iec` also presses keys through XTest and was exposed to
the same race; whether that explains its earlier intermittent capture
timeouts was not tested.

## Sheet on hardware

The shared desktop workflow (`hw_native_desktop_check.py`) takes
`sheet=True`. After Files it launches Sheet, enters 12, 30 and `=A1+B1`,
checks the three values, the VIC bitmap rendered from Sheet's own cell
characters and colours, the VDC mirror and the display registers, then
discards the workbook (the hardware disk is read-only, so nothing is saved)
and checks the desktop. `hw_ultimate_check.py --native-desktop` and the VICE
`ci_native_desktop_iec --hardware-sequence` job, which runs the same
workflow, both enable it.

## Resting noise

With nobody at the mouse, the SID pot registers were read through the
Ultimate's memory interface 7157 times over 600 s, with no read errors. X
read 103 (4993) or 104 (2162), Y 113 (3552) or 114 (3603): two neighbouring
values per axis, inside the three-value spread the driver settles on. Four
single readings were far off (X 130 and 140, Y 141 and 150), at least 27
counts away; a jump of 12 counts or more is held for one sample and cancels
with the return, so none of them moves the pointer.

## Gates

The OS images are those of the [previous record](../2026-10-11-pointer-rest-noise/README.md)
(no source or build output changed); only test code did. Each run is from a
clean clone of its commit.

- X display fix (2dab76b): CPU sweep 323/323; VICE sweep 60/60 with three
  jobs in parallel, no reruns.
- Sheet step (d797988): CPU sweep 323/323; VICE sweep 60/60 in parallel, no
  reruns, including `ci_native_desktop_iec --desktop-boot --hardware-sequence`
  with the Sheet visit.
- `hw_ultimate_check.py --native-editor` on the C128 (d797988): PASS.
- `hw_ultimate_check.py --native-desktop` on the C128 (d797988): **failed
  four times** before the pass below, the first three before the Sheet
  visit, on screens that passed with the same images the night before:
  1. After many hours powered on: the Calculator's VDC bitmap, a run of
     bytes shifted by one from offset 9941.
  2. After a short power cycle: back at the desktop after the Calculator,
     the desktop's VDC service load failed its image CRC (`N_CHECKSUM`,
     $14); the desktop reported the fault and kept the VDC closed.
  3. After 30 minutes off: the Editor's VDC bitmap, one bit missing at
     offset 10992 (row 137, x 256), the tail of the pointer drawn at its
     unmoved start position.
  4. About 90 minutes after that power-on, a fourth run reached Sheet:
     `sheet-new` passed on hardware (Sheet's values, VIC bitmap, VDC mirror
     and display registers). `sheet-calculated` then failed in the VDC
     bitmap only: on pixel line 88 a stretch of the row sits one byte to
     the right, visible where it carries the top line of two column
     separators (offsets 7098/7099 and 7116/7117); the other six lines of
     those glyphs and the whole VIC bitmap match.
  Failures 1 and 4 are the same one-byte VDC address slip in opposite
  directions. Every VDC register and data access in the service waits on
  the 8563's ready bit, so the service has no timing shortcut to fix; the
  errors point at this machine. Each run restored the drives and deleted
  its upload.
- `hw_ultimate_check.py --native-desktop` on the C128 (d797988), fifth run,
  after the machine was checked over: **PASS**, with the same images and
  test code. Every desktop, Calculator, Editor and Files screen passed, then
  `sheet-new` (0, 0, 0), `sheet-calculated` (12, 30, 42) and
  `desktop-after-sheet`. 281 captures; 190 capture snapshots waited for a
  later idle instant while the pointer was sampling; no Ultimate connect
  retries and no uncertain writes. Drives restored and matching, images
  unchanged, the upload deleted, no leftovers.
- A clean clone of 40a847e (this record; no source change since d797988),
  built with `build-native.py` and `build-native-desktop.py`, reproduces all
  45 build outputs that run recorded, byte for byte (SHA-256).
- `hw_ultimate_check.py --native-desktop` from that clone, sixth run: stopped
  at `desktop-editor-selected` by unrequested input. The pointer, still at
  its start position for the previous screen, moved 28 pixels left and 7 up
  between captures, then on during the retaken capture until it rested on
  Sheet's card, and the selection followed it from Editor to Sheet with no
  key pressed. The check refuses a frame whose session state changes while
  it is observed, which is what stopped it. A movement lasting tens of
  seconds is not the resting noise above, which only produced single
  readings that cancel. Drives restored, upload deleted.
- Seventh run, same clone, with the mouse left alone: **PASS**, every screen
  including both Sheet frames and `desktop-after-sheet`. 281 captures; 159
  capture snapshots waited for an idle instant; one Ultimate connect timed
  out before sending and was retried; no uncertain writes. Drives restored
  and matching, images unchanged, no leftovers.

## Not verified

- The Sheet visit has passed on hardware in two runs, about two hours apart,
  after four failures attributed to the machine. Whether the VDC slips
  return after many hours powered on was not measured again.
- The cause of the four hardware failures was not isolated beyond the
  machine; the 8563 was not examined.
- The pot readings are DMA reads of the SID registers between frames, not the
  driver's own samples, and the pointer position was not read alongside
  them: the desktop's pointer variables lie under BASIC ROM, where a direct
  host read returns ROM, so only the IRQ capture observer can read them. The
  hardware desktop check, which reads them that way, is the evidence that the
  pointer stays still.
- Sheet's save and open paths were not run on hardware, because the disk is
  read-only there; they run in VICE (`ci_native_sheet_iec`).
- Only this mouse, on this machine, was sampled.
