# Capture gate and hold; Claude floating-bus detection (2026-10-06)

## Why

The real-C128 `--native-desktop` check failed six times on 2026-10-05, at a
different step each time, and also failed on the two previous builds
([REU module cache record](../2026-10-04-reu-module-cache/README.md#hardware-2026-10-05)).
Its evidence showed two harness faults:

- **Direct reads through the live memory map.** The Ultimate's REST memory
  read uses whatever the MMU maps at that instant. During an IRQ or a KERNAL
  call (map `$00`) it returns ROM: the wrong `--native` read at `$6688` was
  BASIC LO ROM `$6688` byte for byte, and the wrong desktop `vd_phase` read
  at `$8a1f` was BASIC HI ROM `$8a1f`. Two such reads agree, so the "two
  consecutive reads" rule accepted one. Not changed here.
- **The IRQ observer borrowed a buffer the idle app still uses.**
  `probes/native-read.asm` copies into `N_BUFFER` (`$3a00`). An 80-column
  app's idle loop calls the bank-1 VDC service when its pointer state
  changes, writing 36 argument bytes and reading back a 41-byte state record
  there and running in map `$4e` meanwhile. Two failed captures held exactly
  that record (the same 40 bytes at the start of a 512-byte chunk, at
  `$dd70` and at `$2201`), and one capture met the foreground inside the
  bank-1 call.

## Change

- **Observer gate** (`probes/native-read.asm`): the copy runs only from an
  IRQ that finds `N_READY` = 1, the interrupted map `$00`/`$0e`, common RAM
  setting 4 and mode bit 6 clear. Any other IRQ goes straight to the old
  handler, leaves the hook armed and counts itself at `$3fee`.
- **Observer hold**: after the copy and its status the probe stays in the
  IRQ until the host writes `$3ffe`; the host reads the result, puts
  `$3a00` back and checks it while held, then releases. A hold the host
  never releases gives up after about three minutes and sets `$3fff`, and the
  host rejects such a chunk. A failed host step disarms or releases the
  probe and restores `$3a00` (`native_capture.py`). The probe is 491 bytes
  and ends at `$3feb`.
- `native_nested_irq_vice.py` ran its one-shot ROM IRQ entry from `$3fd0`,
  which the probe now occupies; it runs from `$3bf0` in the borrowed output
  buffer, which the capture puts back.
- **Claude serial detection** (`src/native/claude/c128hw.s`): with no ACIA,
  I/O1 reads return whatever the VIC last fetched. VICE runs of
  `ci_native_pointer_iec --80col` read control `$e0` and command `$ff` (bit 0
  set), so the app reported "serial port busy" instead of "unavailable" (3 of
  4 runs with the new capture timing; 3 of 3 passed with the old timing, by
  luck of which bytes were fetched). `acia_open` now reads both registers 16
  more times and treats any change as no ACIA; a real 6551 reads back the
  same values, so an active port is still left alone and reported busy.
- The desktop hardware check's disk pin follows the rebuilt disk.

## Tests

- `ci_native_capture` (Py65, real probe through the ROM IRQ frame): every
  earlier RAM/VDC/fault case now holds until released; new cases for each
  busy condition (not ready, map `$7f`, map `$3f`, common 7, mode bit 6: hook
  armed, nothing touched, skip counted) and for a hold that gives up (built
  with `HOLD_PAGES=1`). Each new case fails against the previous probe.
- `ci_native_capture_transport`, `ci_native_borrower_evidence`,
  `ci_native_status_evidence`, `ci_native_held_capture`: pass unchanged.
- `ci_native_claude`, `ci_native_claude_gui`: a floating-bus ACIA (reads
  starting with the `$e0`/`$ff` pair VICE returned) must show "unavailable"
  and write nothing to the port.
- VICE A/B before the Claude change: `ci_native_pointer_iec --claude-only
  --80col` passed 2/2 with both probes; the full `--80col` workflow failed
  the Claude port step in 3 of 4 runs with the new probe and passed 3 of 3
  with the old; `--files-only --files-open-with --files-find --d81` passed
  2/2 with both (one sweep failure was an extra autorepeat key under load).

Full sweep on the final images (`tests/sweep_native.py` through the resumable
driver, from a snapshot of this tree; every `.prg`, `.d64` and `.d81` in the
commit is byte-identical to it):

- CPU group: 323/323 passed (four chunks, no retries).
- VICE group: 60/60 passed. The three-way parallel pass failed one job,
  `ci_native_pointer_iec` with `--editor-only --editor-selection
  --editor-large --80col --vdc64 --d81 --reu-kib 512`: the workspace `c`
  shortcut counted three extra keyboard events (key repeat is disabled in
  that test). It passed run on its own. An earlier sweep of the capture change
  failed another `--d81` variant the same way; an A/B of `--files-only
  --files-open-with --d81` through that step passed 3/3 with the new observer
  and 3/3 with the old one, so this is recorded as a load-dependent flake, not
  explained.
- `ci_native_pointer_iec --80col` with the Claude fix: 4 of 4 runs showed
  "serial port unavailable" (the sweep run and three repeats), against 1 of 4
  with the new observer before the fix.

## Not verified

- Nothing here has run on the physical C128 (the Ultimate was unreachable
  from 2026-10-06 morning). Whether the gate and hold make `--native-desktop`
  pass on hardware is the open question.
- Direct REST reads still go through the live map; gating them on the MMU
  configuration register needs a hardware test of whether an Ultimate read of
  `$ff00` returns that register.
- Why the idle desktop calls the VDC service on hardware with a still pointer
  is not known (the CPU model makes no calls once the pointer has been
  drawn).
