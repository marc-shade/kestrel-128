# Files: Ultimate rename and delete — 2026-09-25

Native Files gains **Ctrl-R** (rename) and **Ctrl-D** (delete) for the
selected Ultimate entry, through the existing modal dialog. See
[NATIVE-FOLDERS](../../NATIVE-FOLDERS.md#renaming-and-deleting).

- Rename sends `RENAME_FILE` (`$0a`, "old NUL new", both absolute) and
  proves the result with `FILE_STAT` of the new path.
- Delete sends `DELETE_FILE` (`$09`). It reports success only when a
  following `FILE_STAT` returns DOS 82 with an empty reply.

Command semantics were read from Ultimate firmware `a01c04e`
(`software/filemanager/dos.cc`, `filemanager.cc`, FAT `f_unlink`):
- rename refuses an existing target and moves between filesystems;
- delete removes files and empty folders only.

## Evidence (final build; FSVIEW SHA-256 `32ad365f…` unchanged across the runs)

| Report | Command | Result |
|---|---|---|
| `folders-ui/bounds/edit/faults/safety.json` | `tests/ci_native_folders.py --group …` | 5 + 6 + 14 + 11 + 4 cases |
| `files_gui.json` | `tests/ci_native_files_gui.py` | 14 |
| `find.json` | `tests/ci_native_find.py` | 13 |
| `vdc_files.json` | `tests/ci_native_vdc_files.py` | 2 |

The earlier reports in this directory are from builds before the last two
fixes below. Those suites do not use the dialog code:
- `calc`, `files`, `files_workspace`, `find_match`, `launch_contract`;
- `vdc_files_fallback`, `open_with_files`, `picker_callers`.

The edit group checks every dialog frame against the shared scene
renderer. It covers:
- rename, and deletion of a file and of an empty folder, at three display
  sizes;
- a non-empty folder kept; a folder rename carrying its contents; an
  existing target refused;
- invalid names refused before I/O;
- the 510-byte maximum rename packet, and a 255-byte old path refused;
- no selection;
- unknown delete results (still present, other status, unexpected data);
- a refused delete;
- a stale caret after longer earlier fields;
- an uncertain cursor close blocking delete.

The test model (`FolderDOS`) follows the firmware. FILE_STAT's not-found
status corrected from 88 to the firmware's 82.

## Bugs found and fixed

- A not-found status with reply data was accepted as proof of deletion; it
  is now "result unknown".
- Dialogs kept the previous dialog's caret and viewports, so a shorter
  prefilled name, or New folder after Find, started with an invalid caret.
  All three field positions are reset on open.

## Limits

- Ultimate only; IEC scratch/rename needs a kernel command-channel service.
- Keyboard only: there is no button for these actions.
- There is no trash; deletion is permanent.
- No physical Ultimate run.
- FSVIEW has 137 bytes left in its module window.
