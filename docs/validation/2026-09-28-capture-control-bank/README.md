# Capture control traffic in RAM bank 0 — 2026-09-28

## Problem

The confirming VICE sweep on `91dcde9` failed one job,
`ci_native_claude_iec --host-exit --80col` ([log](failing-run/job.log)). That
job passed in the previous sweep. The failure is at the desktop, before Claude
starts, while the test saves the 80-column snapshot that lives in bank 1:

- The third 512-byte chunk of `before-claude-font-snapshot-0fa0` returned
  status `00` ([status bytes](failing-run/)). `wait()` had already accepted
  `$3ff2` as nonzero, and the status read that followed found the chunk still
  running.
- The IRQ probe reads bank 1 through the ROM's INDFET (`jsr $ff74`). For a few
  instructions per byte, the CPU view maps bank 1.
- `NativeCapture` read and wrote its command block, status, borrowed buffers
  and idle checks through the CPU view (VICE bank 0). A monitor pause inside
  INDFET reads bank 1's `$3ff2`. In VICE that byte is `$f9`.

`ci_native_editor_gui_iec` already pinned this traffic to `ram00` through its
own wrapper. The other VICE suites did not.

## Measurements (VICE, same fixture)

Both scripts are in [diagnostics](diagnostics/). They are copies of the Claude
test with a sampling block after the boot desktop.

- **Idle desktop:** 400 of 400 pauses showed MMU CR `$0e`, and the CPU view of
  `$3ff0..$3fff` equalled bank-0 RAM ([samples](diagnostics/idle-bank-samples.json)).
  So the bank-1 view does not come from the desktop itself.
- **Bank-1 probe runs:** in 12 of 60 runs, a CPU-view poll read a nonzero
  `$3ff2` while bank-0 `$3ff2` was still 0. Every such poll came at CR `$7f`,
  inside INDFET ([runs](diagnostics/false-done.json)).

## Change (harness only)

- **`PausedViceMonitor.control_bank`:** the VICE id of `ram00`, resolved once
  from the monitor's bank list. It is `None` for a monitor without banks, such
  as the offline fakes and `ObserverRAM`.
- **`NativeCapture`:** passes that bank to every read and write it makes.
  Every address it touches is bank-0 RAM. Each capture record stores
  `control_bank`.
- Hardware transports have no `control_bank` and are unchanged.
- Not changed: probe code, product code, or what any suite checks.

## Evidence

- **Regression test (`ci_native_capture_transport`):** 35/35
  ([report](transport.json)). The new case models the INDFET window: the probe
  runs for two monitor steps, and a CPU-view poll of `$3ff2` returns `$f9`.
  - **Pinned:** four chunks complete, and the record says bank `ram00`.
  - **Negative control, CPU view:** the false completion reproduces as status
    `00` on chunk 0.
  - **Mutation:** with the pin removed from `NativeCapture`, the pinned case
    fails.
- **CPU suites that use the capture:** 6/6 pass (`--only`, fixed code):
  `ci_native_capture`, `ci_native_capture_transport`,
  `ci_native_borrower_evidence`, `ci_native_status_evidence`,
  `ci_native_transport_lifecycle`, `ci_native_suite_oracles`.
- **The failing job:** `ci_native_claude_iec --host-exit --80col` passed 4 of
  4 runs on the fix ([runs](claude-host-exit-80col-runs.json)).
  - Run 4 records `control_bank` 4 (`ram00`) on all 62 captures.
  - Runs 1–3 ran the same pin before the record field existed.
- **The stopped sweep:** 30 passes and this one failure in its first 31 jobs
  ([output](vice-sweep-stopped.out)). It was stopped because the change
  affects every VICE suite that captures.
- **The full VICE sweep on this commit (`a8e121b`): all 51 jobs pass**
  ([summary](sweep/summary.json)). It ran in three parts on the same commit:
  - [`final2`](sweep/final2.out): 19/19 before the Claude Code session
    exited and took the sweep with it.
  - [`final2b`](sweep/final2b.out): the 11 untouched suites. Its first 4 jobs
    (`editor_iec` d64/d71/d81-search, `editor_gui_iec`) failed before any test
    step: VICE's monitor refused the connection or timed out
    ([d64](sweep/ci_native_editor_iec__format_d64-load-failure.txt),
    [gui](sweep/ci_native_editor_gui_iec-load-failure.txt)). This was during
    a host load spike at session start (load average 10–13 on 6 cores).
    `editor_iec` d81 passed a minute later, and the next 7 jobs passed.
  - [`final2c`](sweep/final2c.out): 25/25, the four editor jobs included,
    with the remaining suites.

## Not verified

- **Hardware:** the Ultimate's DMA observations cannot select a bank. Whether
  the same INDFET window explains the held capture's unexplained
  one-address-late chunks on the C128 is a hypothesis, not tested.
- **Failure rate:** 4 passing runs do not measure how often the old harness
  failed. The mechanism is measured above; the old harness's failure rate in
  the sweep was not.
