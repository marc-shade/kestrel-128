# Sheet decimal arithmetic — 2026-09-29

## Change

Sheet numbers become decimal: a signed 32-bit mantissa and 0 to 6 decimals,
kept in the high nibble of `sh_types` ([NATIVE-SHEET](../../NATIVE-SHEET.md)).
Each step is computed exactly in 64 bits and rounded once, half away from
zero, to the most decimals (at most six) whose mantissa fits. Division is
exact to six decimals, so `=7/2` is now 3.5 (it was 3). Literals such as
`1.25` are numbers (they were text).

- `src/native/sheet/decimal.s` (new): the 64-bit operations in 6502
  assembly for the app. `engine.c` keeps the same operations in C for the
  host build, so the test checks both against one oracle.
- `main.c` / `bridge.s`: the grid shows 8 characters; a longer number keeps
  the decimals that fit, rounded once (`fit_cell`, assembly); the Value line
  shows every decimal.
- Memory: the calculation module grew from 3,550 to 4,358 bytes. The module
  window moved from `$b100` to `$ae00` (all three modules and `sg_font`), and
  the C stack went from 1,024 to 384 bytes.

## Evidence

- **Engine test** (`tests/ci_native_sheet_engine.py`, [report](engine-report.json)):
  passed. Host C: 51,546 scalar cases (half of the 50,000 random cases have
  decimals) plus 41 workbook tests; 6502 (cc65 + `decimal.s` in Py65): the
  first 2,048 scalar cases and the same workbooks; 128 numbers formatted with
  0, 1 and 6 decimals (0..6 for the bounds). The oracle uses Python fractions.
  C stack written: 129 bytes. Worst recalculation: 19,254,403 instructions
  (the integer engine's recorded worst was 17,870,364).
- **App** (`tests/ci_native_sheet.py`, every case, both VDC sizes where the
  sweep runs them, [summary](sheet-sweep-summary.json)): 16/16 jobs passed,
  including the new core-case checks: `1.5`, `=E1/4` (0.375), `=-1/3`
  (grid `-0.33333`, Value `-0.333333`), `12345.6789` (grid `12345.68`).
- **Stack measured in the app**: the free C stack was filled with a pattern
  after start; the core, aggregates and undo cases wrote at most 72 bytes.
- **Full CPU sweep** of the tree committed with this change and the Editor's
  print (`tests/sweep_native.py --group cpu`, [summary](cpu-sweep-summary.json)):
  313/313 jobs passed.

## Not verified

- VICE (`ci_native_sheet_iec`) and the physical C128 have not run the
  decimal build yet.
- Recalculation time on a 1 MHz C128 with many divisions is not measured;
  a division costs up to a few tens of thousands of cycles.
