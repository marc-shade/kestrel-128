# Sheet MIN/MAX/COUNT — 2026-09-15

The integer calculation engine now supports MIN, MAX and COUNT over one
rectangular range, alongside SUM. Names are case-insensitive and endpoints
may be reversed. Text/empty cells are ignored; no numeric cells gives zero.
COUNT includes numeric zero and calculated numbers, resolves dependencies and
propagates cell errors. This contract is explicit; general spreadsheet-format
compatibility is not claimed.

## Evidence

- Host and compiled 6502 engine: 51,517 host scalar cases, 2,048 native scalar
  cases and 40 workbook/recovery cases. New cases cover positive-only and
  negative-only ranges, both signed integer limits, empty numeric sets,
  reversed ranges, forward dependencies, errors/cycles, malformed references
  and four deterministic random workbooks with independent Python results.
  Existing arithmetic, SUM overflow, 256-cell chains/cycles and storage
  recovery also pass. The standalone C stack used 131 of its reserved 1,024
  bytes; its guard and source records remained intact.
- Loaded packed app: entering MIN/MAX/COUNT, recalculation after an edit,
  Undo, full-byte verified Save As and reopen. Source/value expectations are
  independent, with complete VIC/VDC pixel and owner-release checks.
- VICE: 80-column cold boot with 64 KiB VDC, desktop launch, calculation,
  IEC save/reopen and desktop return. Both rendered displays are compared.
  This is the existing file/display regression on the new binary; the new
  functions themselves are covered by the engine and loaded-app tests.
- Media validation passes. A fresh build reproduces all 37 program/disk images.

`results.tar.gz` contains final reports, logs, full engine input/result captures
and its compiled harness. `inputs.tar.gz` contains the source snapshot and
fresh-build outputs (documentation was finalized later). `vice.tar.gz` retains
private disks, extracted workbook, display/canvas captures and the VICE report.
Run `python3 verify.py` to verify archive hashes, report results, captured engine
expectations, rebuild images and the independently decoded VICE workbook.
This verification does not rerun the CPU or display oracles.

An early development test used a rectangle excluding column A while expecting
its value. The fixture was corrected before the final engine run; no app or
engine code changed in response to that fixture error.

## Limits

Sheet now occupies 96 app pages. It leaves 159/151 free managed pages with
RAM-backed 16/64 KiB VDC snapshots and its workbook; staged New/Open requires
32 more. The suite leaves 33 free D64 or 2,529 free D81 blocks. Larger features
will need a module/memory layout change rather than exceeding the app window.

No physical C128/Ultimate/REU qualification is claimed. Decimal arithmetic,
argument lists, more functions, formatting, clipboard, shared picker,
printing and the wider desktop/expansion roadmap remain open.
