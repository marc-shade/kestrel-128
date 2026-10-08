# Per-app pointer start (2026-10-08)

## Why

A hovered control takes focus when the 1351 pointer moves, and every app
started the pointer at (160,160). That point is the bottom edge of the
Calculator's + button and of a Files control (and inside Calculator, Files,
Editor, Controls and file-picker controls), so the reference machine's
one-row drift moved focus and made Files redraw during a capture
([Editor readiness record](../2026-10-07-editor-ready/README.md), hardware runs
8 and 9).

No single point is clear of every app's controls: across the apps the
controls cover x 60..260, so only screen edges qualify.

## Change

`input/pointer.inc` takes its start from a weak `pm_start` (x and y, default
160; the generated `picker/pointer.inc` gets `pgm_start`). Apps whose controls
cover (160,160) set their own, chosen from their hit tables (the
`native_*_scene` RECTS and BUTTONS, and the desktop and Sheet hit tests in
assembly) as the most central diagonal point at least 12 pixels from any
control edge:

| App | Start |
|---|---|
| Calculator | 172 |
| Files | 172 |
| Editor | 124 (inside the text area, 12 from its edges) |
| Controls | 60 |
| File picker | 52 |

Desktop, Paint, Claude, Sheet and GEMDESK keep 160 (already clear). x equal
to y keeps the start a single immediate, so no app grows. The desktop
hardware check's comments and disk pin follow.

## Tests

- Py65 pointer suites on the new images: `ci_native_calc_gui`,
  `ci_native_controls_gui`, `ci_native_pointer`, all seven
  `ci_native_picker_gui` cases, `ci_native_editor_gui` mouse and picker,
  `ci_native_files_gui` mouse and keyboard.
- Full sweep (`tests/sweep_native.py` through the resumable driver, from a
  snapshot of this tree; the images in the commit are byte-identical to it):
  CPU 323/323, VICE 60/60.
- Hardware `--native-desktop` run 10 on these images passed all eleven
  screens (169 busy IRQs) but with no pointer: the 1351 was not detected.

## Not verified

- The new starts on hardware with a detected mouse. After the mouse was
  plugged back in, port 1 read POTX `$94` and POTY `$c5`; the driver accepts
  only `$40..$bf` on both, so the pointer stays hidden (run 11 stopped at the
  first screen for that reason).
- The hit rectangles come from the Python scene tables and the assembly hit
  tests read by hand; a table that differs from its app would put a start
  inside a control.
