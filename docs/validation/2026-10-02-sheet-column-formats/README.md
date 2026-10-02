# Sheet: column display formats; listing paths in the picker check (2026-10-02)

## Change

- **Column display formats** in Sheet ([NATIVE-SHEET](../../NATIVE-SHEET.md)).
  Ctrl-F cycles the selected column through every decimal, then 0 to 6
  decimals, and says so ("Column B decimals: 2"). A number in a column with
  N decimals shows exactly N: more are rounded once on the first dropped
  digit (half away from zero), fewer get zeros, within the cell's 8
  characters; a negative number that rounds to zero shows no sign. Values
  and formula results are unchanged. The formats are saved in USHT header
  bytes 12 to 15 (two columns a byte, low nibble first); a workbook from
  before formats has zeros there and opens unchanged, and a nibble above 7
  is an invalid workbook. New clears them.
- The formatting is in `bridge.s` (`fit_column`, `format_next`, and
  `fit_cell`, which now cuts or pads to the format before the width rule and
  drops the sign of any negative zero, not only "-0").
- Sheet's core had 8 bytes left below its module window. `main.c` and
  `workbook.c` are now compiled with `-Os -Cl` (static locals; neither file
  has a recursive or reentered function, checked by reading every call
  site; the recursive engine module is unchanged). The core now ends at
  `$add4` with 44 bytes left. The C stack keeps its 384 bytes.
- `native_picker_check.py` read the picker's include from a listing path
  that had to be absolute. The previous change (2026-10-01, listings without
  host paths) made those paths relative and broke `ci_native_pointer_iec`
  and `ci_native_editor_gui_iec`, which use it; that change was pushed with
  only the GEMDESK suites run. The pattern now accepts both.
- `hw_native_desktop_check.py` pins the new `target/native-desktop/kestrel.d64`
  (Sheet is on it).

## Tests

- `ci_native_sheet --case formats` (new): column A holding 1.5, 2, -0.004,
  9.995 and 123456.789 shown at every format (e.g. 0 decimals: 2, 2, 0, 10,
  123457; 2 decimals: 1.50, 2.00, 0.00, 10.00, 123456.8), the message, the
  packed bytes for columns A and B, values unchanged, Save writes header
  bytes 12 to 15, New clears, Open restores; an old workbook opens; a nibble
  of 8 is refused.
- `ci_native_sheet --case faults`: the "unsupported header" file now sets
  byte 12 to `$08` (an invalid format) instead of `$01` (now a valid one).
- Full sweep on the final images: `sweep_resume.py --group cpu` 322/322
  (the new case included), `--group vice` 59/59. One VICE job,
  `ci_native_pointer_iec --80col`, failed once in the parallel run (Paint's
  pointer moved 6 pixels after settling) and passed when run alone; Paint is
  not changed here.

## Not verified

- Nothing has run on the physical C128.
- The Sheet core's speed with `-Os -Cl` was not measured; the VICE Sheet
  workflows pass within their existing time bounds.
- Ctrl-F is not part of undo, and formats are per column, not per cell.
