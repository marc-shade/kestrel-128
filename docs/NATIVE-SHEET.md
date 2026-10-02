# Native Sheet

Sheet is the seventh native desktop app. Press **S** in the blue launcher,
or select **Sheet** with the keyboard or a port-1 1351 mouse. The app presents
an editable spreadsheet on the VIC and through the shared VDC display service.
Its first workbook supports eight columns, 32 rows, text and checked decimal
formulas. APP-SHEET remains open in the [completion roadmap](IMPLEMENTATION-ROADMAP.md).

Build the complete D64/D81 suite with `python3 -B build-native-desktop.py`.
`python3 -B build-native-sheet.py` builds the standalone app. Keep
`SHFONT.PRG`, `SHCALC.PRG`, `SHCLIP.PRG` and `VDSVC.PRG` beside `SHEET`
when copying the app to another disk or Ultimate folder. Keep the three
`SH*.PRG` modules paired with the exact app build. The app uses the checked native loader for either source.

## Desktop controls

| Control | Action |
|---|---|
| Arrows / Tab | Move between cells; the four-column, twelve-row viewport follows the selection |
| Home | Return to A1 |
| Ctrl-Z / Ctrl-R | Undo / redo the last cell edit or Clear |
| Ctrl-C / Ctrl-X / Ctrl-V | Copy / cut / paste one complete cell source through the session clipboard |
| Ctrl-F | The selected column's next display format: every decimal, then 0 to 6 decimals, then every decimal again |
| Enter / F7 / Edit | Edit the selected cell's existing source |
| Printable key | Start a replacement cell entry |
| Enter while editing | Commit and recalculate the workbook |
| Escape while editing | Cancel the draft and retain the old cell |
| Del / Clear | Empty the selected cell and recalculate |
| F1 / New | Create an empty workbook, with dirty-workbook confirmation |
| F3 / Open | Open a USHT workbook, with dirty-workbook confirmation |
| (at start) | A workbook handed over by GEMDESK (document kind 3, [contract](NATIVE-DOCUMENT-LAUNCH.md)) opens as with Open |
| F5 / Save | Save As a new file and verify its complete readback |
| Escape / Back | Return to the desktop; unsaved work requires confirmation |
| Ctrl-L | Retry the VDC service after a clean refusal or retained display failure |

Mouse clicks select visible cells and activate toolbar controls. Field editing
uses the shared native field service: Left/Right, Home, Ctrl-E, Del, Ctrl-D,
Insert and Ctrl-U. The cell field accepts 31 ASCII characters. PETSCII letter
keys are translated at the cell-input boundary; workbook records remain ASCII.
The complete selected source and number are shown above and below the grid.
Numbers too wide for a cell show `########` in the grid, retaining the complete
value below. The VDC currently mirrors the four-column viewport; a denser
native-width grid remains work.

Open and Save As accept a typed filename or absolute Ultimate path. In that
dialog, **F1** cycles D64/D71/D81/Ultimate and **F3** cycles IEC devices 8–30
or Ultimate DOS contexts 1/2. Enter confirms; Escape or Back cancels. IEC names
are limited to 16 bytes and use SEQ files; Ultimate paths can reach 255 bytes.
This initial dialog does not yet use the shared directory picker.

Undo/Redo exchanges the complete source of one cell and recalculates the
workbook, returning the selection to that cell. Unchanged edits preserve the
history. A new edit replaces it; successful New/Open clears it. Save As keeps
history available. Undo and Redo conservatively mark the workbook unsaved,
even if its bytes match an earlier saved version. History is unavailable while
a cell field or file dialog is open. Multi-step and range history remain work.

## Shared clipboard

Copy exports the selected cell's complete ASCII source, including a formula's
leading `=`. Cut publishes that source before clearing the cell. Paste replaces
the selected source and recalculates; Undo can restore the previous cell.
References are copied literally, without relative-reference rewriting.
These keys operate on cells outside field editing and modal dialogs.

Sheet exchanges text with Editor and Claude through the existing session
clipboard. It accepts only 1–31 printable ASCII bytes. Longer items, control
bytes (including line endings), non-ASCII bytes and empty items are rejected
without changing the workbook or clipboard. Copy/Cut on an empty cell also
leave the previous clipboard intact. Clipboard data survives app exit and
New/Open; kernel restart clears it. There is no range or tabular paste yet.

## Workbook files and ownership

A workbook owns 32 bank-1 pages (8 KiB), accessed through checked handles.
New and Open allocate a second workbook, validate and calculate it, and only
then replace the current one. Failed allocation, malformed input, reads or
staged calculation preserve the original source and dirty flag. Failed writes
to a live cell mark its storage uncertain and refuse further edits or Save As;
New/Open can replace it. A failed close keeps its handle for an explicit retry.
The app never frees its display owners while VDC restoration is incomplete.

USHT version 1 is exactly 8,208 bytes, without a PRG load address:

| Offset | Bytes | Meaning |
|---|---|---|
| 0 | 4 | ASCII `USHT` |
| 4 | 4 | Version 1, columns 8, rows 32, record bytes 32 |
| 8 | 2 | Payload length 8192, little endian |
| 10 | 2 | CRC16-CCITT of the payload, initial 65535, little endian |
| 12 | 4 | Column display formats, two columns a byte, low nibble first (0 every decimal, 1-7 for 0-6 decimals); zero in workbooks from before formats |
| 16 | 8192 | Row-major cell records, A1 through H32 |

Each record contains printable ASCII, one NUL, then zero padding to 32 bytes.
Open rejects unsupported headers, bad CRC, malformed records, truncation and
trailing bytes. Save As creates exclusively, closes, reopens and compares the
header and every cell before reporting success. Cancellation and errors keep
the workbook; a newly created partial file is retained. Transfers poll for
Escape and mouse Back at record boundaries and show progress.

The current app reserves 96 pages for code, state and the C stack, plus its
36-page VIC surface and the 39-page VDC component. With the 32-page workbook,
RAM-backed 16/64 KiB VDC snapshots leave 159/151 managed pages free. The calculated budget for a supported
REU-backed display snapshot leaves 223 (not yet tested with Sheet); staged Open/New need 32 additional
pages. Source cells currently stay in main banked RAM.

## Checked modules

The 96-page app allocation includes a shared module window at `$b100..$bfff`.
The core keeps source storage, calculation results, undo state, display owners
and the C stack below it. `SHCALC.PRG` computes values; `SHFONT.PRG` supplies
the display font; `SHCLIP.PRG` uses the shared clipboard library. Each module
is checked for extent, CRC and parent-app identity and loaded from the original
app's IEC device or Ultimate directory. A failed replacement cannot call an
old module token. No resident kernel ABI change is required.

A missing or corrupt calculation module preserves source cells and invalidates
all displayed results. Restoring the matching file and accepting the same cell
again retries calculation without replacing undo history. An unavailable font
after editing latches the failure and retains the workbook and display owners.
After restoring the file, Esc or Ctrl-L explicitly retries; unrelated input
does not repeat source I/O. Startup refusal releases the blank app through normal cleanup.
Module swaps add disk I/O when alternating edits, presentation and clipboard
actions. Caching and a larger shared picker module remain future work.

## Workbook and formulas

The initial calculation model has eight columns (A–H), 32 rows and 256 cells.
Each source record contains up to 31 printable ASCII bytes followed by NUL.
The core reads records through a storage callback; it does not assume that
the entire workbook is in directly addressable RAM. The native app translates keyboard letters into this explicit ASCII format.

Empty cells and cells containing only spaces are empty. A signed decimal
value, digits with an optional point and fraction (`12`, `-2.50`, `12.`), is
a number. Other non-formula input (`.5`, `1.2.3`, `12x`) is text; a leading
apostrophe forces text. Leading and trailing spaces around numbers are
accepted. Text and formulas remain in source storage; calculation does not
rewrite them.

Formulas begin with `=` and support:

- Decimal numbers, `+`, `-`, `*`, `/`, unary signs and parentheses.
- Normal multiplication/division precedence and left-to-right evaluation
  within each precedence level. Division is exact to six decimals: `=7/2` is
  3.5 and `=2/3` is 0.666667. (Before decimals, division truncated toward
  zero and `=7/2` was 3.)
- Case-insensitive references such as `A1` or `h32`.
- `SUM`, `MIN`, `MAX` and `COUNT` each accept one rectangular range, such as
  `=MIN(A1:B12)`. Reversed endpoints describe the same rectangle. Empty and
  text cells are ignored. An empty numeric set returns zero. `COUNT` counts
  numeric cells (including zero and calculated numbers); it resolves every
  dependency and propagates cell errors, as do the other range functions.
  Directly referencing text produces a value error.
- Full recalculation after source edits, forward references, error
  propagation and detection of cycles, including cycles inside a range.

A number is a signed 32-bit mantissa and 0 to 6 decimals: whole numbers
range from −2,147,483,648 through 2,147,483,647, and a number with decimals
has fewer whole digits (2147.483647 is the largest with six). Each step
(`+ - * /`, a unary minus, each addition in SUM) is computed exactly in 64
bits, then rounded once, half away from zero, to the most decimals (at most
six) whose mantissa fits; `=1000000000.5+1000000000.25` is 2000000001. A
literal keeps its first seven decimals and rounds at six. Trailing zeros are
dropped (`=5.00` is 5). Overflow is an error only when not even the whole
number fits; division by zero is an error. MIN and MAX compare exactly;
COUNT is unchanged. There is no floating-point, currency, date or time type.
Argument lists, other functions, multiple sheets, absolute references and
formula rewriting on cell moves are not implemented.

The grid shows 8 characters per cell. A number longer than that keeps the
decimals that fit, rounded once on the first dropped digit, then loses
trailing zeros (`-1/3` shows as `-0.33333`, `12345.6789` as `12345.68`);
only a whole part too long for the cell shows `########`. The Value line
shows every decimal.

Each column has a display format, set with Ctrl-F, which says "Column B
decimals: 2" (or "all"). A column with N decimals shows every number in it
with exactly N: more are rounded once on the first dropped digit (half away
from zero), fewer get zeros, within the cell's 8 characters (`123456.789`
shows `123456.8` at 2 decimals). A negative number that rounds to zero
shows no sign (`-0.004` at 2 decimals is `0.00`). The format changes only
what the grid shows, never a value or a formula's result. The formats are
saved with the workbook in header bytes 12 to 15, two columns a byte (low
nibble first: 0 every decimal, 1 to 7 for 0 to 6 decimals); a workbook from
before formats has zeros there and opens unchanged, and a nibble above 7 is
an invalid workbook. New clears them. Ctrl-F is not in the undo history.
Formats are per column only: there is no per-cell format, and no currency,
percent or thousands separator.

Parentheses may nest eight levels. Each unary-sign sequence may contain
eight signs; its combined sign applies to the following literal or primary
expression. Leading-zero row numbers and references outside A1:H32 are
rejected. Unterminated, non-ASCII and control-byte records produce syntax
errors without reading beyond the cell buffer.

## Calculation API and memory

`src/native/sheet/engine.h` exposes `sh_recalculate`, the result arrays and
a decimal formatter. A number is `sh_values[i]` over 10 to the power of
`sh_types[i] >> 4`; the low four bits of `sh_types` are the type. The app provides `sh_read_cell(index, out)`, which
copies exactly one 32-byte record and returns zero on success. The storage
adapter must keep the workbook stable throughout the call. The calculation
core is synchronous, is not reentrant and does not poll input.

Results distinguish empty, number and text cells from syntax, reference,
division, overflow, value, cycle, expression-depth and storage errors.
Non-number result values are zero. A read failure invalidates all results
with the storage-error type and returns `SH_IO`. A successful retry
recalculates from the current source; no old dependency state is reused.

Cell dependencies use an explicit stack that can hold every cell. Formula
parsing uses a separate bounded C stack, so a 256-cell reference chain does
not create 256 nested parser calls. A range containing unresolved cells is
revisited as those cells become available; a dependency-heavy SUM can take
more work than a simple formula. The core has no cancellation or timed
hardware responsiveness claim yet.

The 64-bit arithmetic is 6502 assembly (`src/native/sheet/decimal.s`) in
the app; the host build uses the same operations written in C, and the test
checks both against an exact fraction oracle. The app reserves 384 bytes for
the C stack: the engine test's deepest formula nesting writes 129 bytes, and
the app's core, aggregates and undo CPU cases wrote at most 72 (measured by
filling the free stack with a pattern after start); its module window
starts at `$ae00`, and the calculation module ends at `$bf15`. The standalone
linker reserves 1 KiB for the C stack and rejects a runtime
extent beyond `$c000`. Its source-cell region is read-only to the engine.
These are harness constraints, not qualification of a native app's memory
ownership, display cleanup or file handling.

## Qualification and remaining work

Run the standalone engine or the loaded app checks (Py65 is required):

```sh
python3 -B tests/ci_native_sheet_engine.py --report /tmp/sheet-engine.json
python3 -B tests/ci_native_sheet.py --case core --report /tmp/sheet-core.json
python3 -B tests/ci_native_sheet.py --case files --report /tmp/sheet-files.json
python3 -B tests/ci_native_sheet_iec.py --80col --vdc64
```

The test needs a C compiler, cc65 and Py65. It compares host and compiled
6502 output with independent decimal and workbook expectations. The host
build traps undefined behavior. Captures retain complete cell records and
actual/expected results, while the CPU fixture rejects writes outside its
assigned memory and checks its source cells and stack guard.

The [software checkpoint](validation/2026-09-14-native-sheet-engine/README.md)
records the executed inputs, compiled harness, captures and development
corrections. No VICE, native app or physical hardware claim is made here.

The [desktop checkpoint](validation/2026-09-14-native-sheet-desktop/README.md)
records the native app's software qualification separately from that engine
checkpoint. The [Undo/Redo checkpoint](validation/2026-09-15-native-sheet-undo/README.md)
covers the subsequent one-cell history feature. The [range-function checkpoint](validation/2026-09-15-native-sheet-ranges/README.md)
records MIN/MAX/COUNT qualification. The [module/clipboard checkpoint](validation/2026-09-15-native-sheet-clipboard/README.md)
records the modular app and session clipboard exchange. Physical C128/Ultimate testing
is still required.

Remaining work includes the shared file picker, range clipboard, multi-step/range undo, formatting,
CSV and geoCalc exchange, per-cell (not per-column) number formats, more functions, larger/multiple
sheets, printing and session recovery. Recalculation is synchronous; background
recalculation and cancellation of long dependency chains remain open. The
initial working app does not complete spreadsheet or GEOS/Wheels parity.
