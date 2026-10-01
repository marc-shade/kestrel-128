# GEMDESK files, views and dialogs (GEM layer steps 6–7) — 2026-09-26

The second GEMDESK build, the first forms library (step 6), IEC delete and
rename through an app-side DOS command library, and one AES fix. Specs:
[GEM-DESKTOP](../../GEM-DESKTOP.md), [NATIVE-FORMS](../../NATIVE-FORMS.md),
[NATIVE-DOS-COMMANDS](../../NATIVE-DOS-COMMANDS.md).

## What changed

- **GEMDESK:**
  - View sorting: name, type, size and unsorted;
  - Show Info: a dialog for an entry, which can rename it on IEC; an alert
    for a drive;
  - Delete (Ctrl-D) and dropping a row on Trash, both confirmed;
  - Options:Preferences: confirm deletes, sort order.
- **`src/native/forms.inc`:** GEM-style dialogs with text, buttons,
  checkboxes, radio groups and `N_FEDIT` fields.
- **`src/native/dos-command.inc`:** one CBM DOS command on secondary address
  15, with the status line parsed. It refuses while the kernel holds the
  drive's command channel.
- **AES:** the double-click window is timed from the first press, so it also
  closes when the jiffy clock resets at midnight. The AES shrank by 12 bytes.
- **Test models:**
  - The pointer harness's `frame()` used to bump only `$a2`, with no carry.
    It now counts the clock as the KERNAL's UDTIM does: it carries into
    `$a1`/`$a0` and resets to 0 at `$4F1A01`. The constant was checked in
    KERNAL `318020-05` at `$35f8`. The missing carry had frozen a
    double-click window, which is how the bug was found.
  - `StreamIEC` gained scratch (skipping locked files, with locked directory
    entries flagged) and rename.

## Evidence

All runs are Py65 at CPU level. The build is in a scratch copy of the tree,
whose `src/`, `tests/` and `build-native-desktop.py` were checked to be
identical to this commit (`diff -r`). Images: `gemdesk.prg` SHA-256
`d4da05dd…`, `aesvc.prg` `060c71e4…`.

- `tests/ci_native_gemdesk.py` → `gemdesk.json`: 27/27 cases. Each state is
  a complete 9,216-byte surface compared with `native_gemdesk_scene.py`,
  which uses `native_forms_scene.py` for the dialogs.
- `tests/ci_native_aes.py` → `aes.json`: 31/31 on `aesvc.prg` `060c71e4…`.
  This includes the new case of a click whose window straddles the midnight
  clock reset.

Planted bugs: 11 were planted, one at a time, each in a copy of the tree
that was then rebuilt; every one failed the case named:

| Planted bug | First failing case |
|---|---|
| Size sorts ascending | sorted by size |
| `$a0` padding not ordered below a space | sorted by name (after adding the `MIKE`/`MIKE ` pair; before it, this bug survived) |
| Delete's default button is Delete | confirm delete |
| A scratch count of 0 accepted | locked not deleted |
| No drop on Trash | trash confirm |
| No check of the kernel's command channel | channel in use |
| AES click window never closes past a 16-bit wrap | the AES double-click case |
| Radio button leaves its group set | size chosen |
| Default button drawn with one border | show info |
| Field caret not shown | show info |
| `fo_close` restores nothing | show info closed |

Two of the planted-bug runs predate the dialogs: no Trash drop, and no
channel check. They ran against the earlier Delete build; the code they
changed is the same in this commit.

### Regression run of the other CPU suites

This covers the shared test models changed here: the pointer clock and
`StreamIEC`. 31 CPU suites were run against the unchanged build of this
change; the target hashes matched before and after.
- **Passed (23):** `ci_native_gemdesk`, `aes`, `calc_gui`, `claude_gui`,
  `controls_gui`, `editor_gui`, `folders`, `find`, `paint_gui`,
  `paint_document`, `pointer`, `vdc_controls_picker`, `vdc_desktop`, `sheet`,
  `files_gui`, `vdc_controls`, `vdc_files_picker`, `vdc_paint`,
  `vdc_paint_picker`, `vdc_calc`, `vdc_files`, `reu_calc`, `files`.
- **Failed (1):** `ci_native_paint_keys`, with
  `AssertionError: (0, 0, False, False, '0xb00')`. It fails identically in a
  worktree of `737adad`, before this session's changes, so it is a
  pre-existing failure, not a regression. It is not fixed here.
- **Not run (7):** `claude_vdc`, `clipboard_apps`, `clock`, `open_with`,
  `picker_gui`, `editor_selection` and `editor_history` require `--case` or
  `--size`, so this run's command line was refused. They are being rerun
  with every case.

## Limits

- CPU level only (Py65 with IEC, pointer and display models). Nothing here
  has run in VICE or on a C128, including the DOS command library against a
  real drive.
- GEMDESK has no Ultimate windows yet. Delete and rename are IEC only here;
  Files keeps its Ultimate paths.
- Forms draw only the VIC surface (no VDC mirror). Field view scrolling,
  focus wrapping and a disabled button are not covered by tests.
- Preferences are not saved; dragging shows no outline; read-only cannot be
  changed.
