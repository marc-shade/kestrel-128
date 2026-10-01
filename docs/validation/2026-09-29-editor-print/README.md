# Editor printing — 2026-09-29

## Change

Ctrl-P in the graphical Editor prints the document on IEC device 4 through
the KERNAL (logical file 121, secondary address 7), from the clipboard module
(`src/native/editor/print.inc`). ASCII letters become PETSCII; CR, LF and
CR LF each end a line with CR. The status line says "printed" or "no
printer"; Esc stops between chunks ("cancelled; document kept"). To fit the
core (2 bytes spare after the change), the clipboard keys are a table and one
clipboard message is shorter ("select text first").

## Evidence

- **CPU** (`tests/ci_native_editor_gui.py --case print`, [report](cpu-report.json)):
  with no printer, "no printer" and nothing sent; with a modelled printer on
  device 4, the exact PETSCII bytes
  `\xc8ELLO, \xd7ORLD!\rSECOND LINE: 42\r\xc5\xce\xc4`; the KERNAL file
  parameters ($b7..$bf, $c6, $c7, $9d) unchanged.
- **VICE** (`tests/ci_native_editor_print_vice.py`, [report](vice-report.json)):
  x128 with a 1581 and VICE's printer emulation on device 4 (ASCII driver
  to a text file). The Editor was started from the launcher, two lines were
  typed, Ctrl-P reported "printed", and the printer file held
  `Hello, World!\nsecond line: 42\nEND`.
- **Full CPU sweep** of the tree with this change and Sheet decimals
  (`tests/sweep_native.py --group cpu`, [summary](../2026-09-29-sheet-decimals/cpu-sweep-summary.json)):
  313/313 jobs passed.

## Not verified

- The Ultimate II+'s printer emulation and a real printer.
- Esc during a print (the path is the same as Save As's cancel check but has
  no test of its own).
