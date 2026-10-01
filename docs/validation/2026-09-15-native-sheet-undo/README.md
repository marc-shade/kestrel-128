# Sheet one-cell Undo/Redo — 2026-09-15

Ctrl-Z restores the source of the most recently edited or cleared cell;
Ctrl-R reapplies it. Both recalculate formulas and return the selection to that
cell. Unchanged edits keep history, new edits replace it, successful New/Open
reset it and Save As preserves it. Undo/Redo conservatively mark the workbook
unsaved. This is one step, without range history or clipboard integration.

## Software evidence

`results.tar.gz` contains CPU reports/logs, media validation and clean-build
results. The two focused CPU commands use `tests/ci_native_sheet.py` with
`--case undo` and `--case undo-faults`, `--size 64`, and a JSON report path.
They execute the packed app with independent source/value expectations and
complete VIC/VDC pixel checks. The first covers Clear, formula restoration,
no-op edits, replacement of redo, save retention and successful/cancelled
workbook replacement. The second injects read/write failures: a failed read
retains retry history; an uncertain write poisons storage and blocks mutation.

`vice.tar.gz` retains a cold boot through a private 1581 suite and data disk,
calculation, verified IEC save/reopen and desktop return on the final app.
Both VIC/VDC display memories and rendered canvases are checked. This run uses
40-column startup and a 16 KiB VDC. It validates the existing file/display
workflow on the new binary; Undo/Redo keys are covered by the CPU tests above.
Host extraction independently confirms all 8,208 saved workbook bytes.

A fresh build in `inputs.tar.gz` reproduced all 37 program/disk images exactly.
Its source snapshot predates final documentation edits. The initial history
job started before the additional `undo-faults` branch was added to the test
file; its `undo` branch and executable sources are identical to the snapshot.
The archive includes final source and generated outputs for repeatability.

`SHA256.json` records archive integrity. Run `python3 verify.py` to check it,
the passing reports, final image hashes and the independently decoded saved
workbook. It does not rerun the CPU or VICE display oracles.

Sheet uses 94 app pages; the suite leaves 33 free D64 or 2,529 free D81 blocks.
No physical C128, Ultimate, mouse or REU I/O is claimed. Broader spreadsheet,
desktop, expansion and physical qualification work remains on the roadmap.
