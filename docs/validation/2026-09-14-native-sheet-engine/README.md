# Native spreadsheet calculation core — software checkpoint

The new calculation core supports an 8×32 workbook with checked signed
32-bit integers, text and empty cells, arithmetic formulas, case-insensitive
cell references, rectangular SUM ranges and cycle detection. It reads cells
through a storage callback and handles complete recalculation and failed-read
recovery. The core does not change source cells.

This is a calculation-core milestone. The spreadsheet has no desktop grid,
Open/Save workflow or launcher entry yet. The existing six-app blue suite and
all shipping native PRG/D64/D81 images are unchanged. APP-SHEET remains open.
No VICE or physical C128/Ultimate qualification is claimed.

## Validation

- 51,517 host scalar cases, compiled with undefined-behavior traps.
- 2,048 scalar cases executed as compiled 6502 code under Py65.
- Nine workbook cases on both implementations, including edits and clearing,
  mixed-case formulas, complete 256-cell chains and cycles, SUM overflow and
  a SUM with 248 forward dependencies.
- Three storage failure positions, each followed by a successful full retry,
  plus 128 integer-formatting cases on both implementations.
- 50,598,143 native instructions across 152 calls. The largest individual call
  used 17,870,364 instructions; this is not a hardware responsiveness claim.
- The fixture recorded 131 bytes of C-stack writes within its 1,024-byte
  reservation, preserved its lower guard and rejected writes outside the
  assigned memory. The engine did not modify any source records.
- A fresh six-input build reproduced the 4,915-byte standalone PRG exactly.
  The full harness has 1,848 bytes of BSS and ends its C stack at `$7e69`.
- A separate standard-library AST/integer audit checks all 61,440 retained
  cell results across 217 host and 23 native captures.

The signed local parent is `16c2ebf936a250fb12225cdd2020949f1597f543`.
Nothing was pushed or installed on hardware. See
[the calculation contract](../../NATIVE-SHEET.md) for syntax, errors and
remaining app integration work.

## Reproduction

Run `python3 -B verify.py` in this directory for the offline archive, rebuild
identity, memory-extent and independent result audit. To execute the tests,
unpack `inputs.tar.gz` into an empty directory, then run:

```
python3 -B tests/ci_native_sheet_engine.py --report /tmp/sheet-engine.json
```

Use a fresh report name. The test requires a C compiler, cc65 and Py65. It
creates a separate build directory and records its path in the report.
`artifacts.tar.gz` preserves the executed binaries, link map and symbols;
`captures.jsonl.gz` preserves raw cell records and actual/expected results.
`baseline.json` and `changes.json` bind the checkpoint to its parent inputs.
`executions.json` and `development.tar.gz` retain the three earlier failures,
exact source versions and the corrected character-encoding defect.
