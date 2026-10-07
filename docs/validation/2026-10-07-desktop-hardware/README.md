# Desktop hardware check: pointer retake and boot quiet time (2026-10-07)

## Hardware runs

`hw_ultimate_check.py --native-desktop` on the reference C128 (Ultimate II+,
16 MB REU enabled), images of `0672221` (the capture gate and hold of
[2026-10-06](../2026-10-06-capture-gate/README.md)):

| Run | Harness | Result |
|---|---|---|
| 1 | `0672221` | Pass, all eleven screens, 68 min |
| 2 | `0672221` | Fail at `editor-new`: the VDC pointer was one row below the pointer state read before the bitmap capture |
| 3 | + pointer retake | Fail at boot: the desktop's VDC service load failed its CRC (`vd_fault` `$14`) |
| 4 | + pointer retake, 240 s quiet boot | Pass, all eleven screens, 75 min |

Each run restored the drives, deleted its upload and left both Ultimate DOS
contexts idle. A second run chained after run 1 was stopped about a minute in
(the chain would have passed the session's two-hour job limit); its mounted
upload, `/Temp/temp0007`, was checked against its SHA-256, unmounted and
deleted by hand, and the drives then matched their recorded state.

## Findings and changes

- **The capture gate works on hardware.** Runs 1 and 4 counted 8,995 and
  10,091 IRQs that found the foreground busy, almost all during the Editor
  captures; the probe waited them out. Under the earlier observer such IRQs
  produced the failed captures of 2026-10-05. Why the idle 80-column Editor
  is busy that often is not established: in run 4 the pointer did not move.
- **Pointer retake** (`native_vdc_check.py`). Run 2's bitmap held the pointer
  arrow one row below the position read first, so the pointer moved while
  the 16,000-byte bitmap was captured. The frame check now reads the drawn
  pointer state through the IRQ observer before and after the bitmap and
  retakes an attempt whose pointer moved (three attempts); an attempt with a
  steady pointer must match exactly. Moved attempts are kept in the frame
  record as `pointer_moves`. Run 4 needed none.
- **Boot quiet time** (`hw_native_check.quiet_boot`, `hw_native_desktop_check`).
  The check slept 60 s after reset, then polled RAM by DMA every 0.1 s, and a
  DMA read stalls the CPU during a bit-timed IEC load. A real-speed VICE boot
  of the desktop D64 on a true 1541 had the kernel running after 35.9 s and
  the desktop's VDC open and ready after 171.2 s, so the polling overlapped
  about 110 s of loading; run 3's VDC service load failed its CRC. The
  desktop check now waits 240 s; the text-system checks keep 60 s (the GEM
  check already waits 150 s).
- `ci_native_transport_lifecycle` stubs `quiet_boot` with the new argument.

## Tests

- VICE group (snapshot with the pointer retake): 60/60; `ci_native_gemdesk_print_vice`
  failed once in the three-way pass (its mouse never reached a target; it does
  not use the frame check) and passed run on its own.
- CPU tests that import the changed modules: `ci_hardware_uploads` (34 cases),
  `ci_native_suite_oracles`, `ci_native_transport_lifecycle` (6), and
  `ci_hardware_usb_restore` and `ci_hardware_editor_restore`, which stub
  `quiet_boot`. The full CPU group last ran on `0672221` (323/323); these
  changes touch only hardware-harness modules.

## Not verified

- Two passes in four runs on this build are not a pass rate; run 1 passed
  without the two harness changes, run 4 with them.
- Direct REST reads still go through the live memory map and can return ROM
  during an IRQ (2026-10-06 record); none failed in runs 1 and 4.
- The 240 s figure comes from VICE's true-drive timing, not from a hardware
  measurement.
