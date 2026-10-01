# Creating folders in native Files

In **Files**, choose **ULT** and navigate to the parent directory. Click
**New dir**, or press **Ctrl-K**, enter the folder name and choose **Create**.
Tab moves among the field and buttons; Enter activates the selected control.
The name supports the shared caret, insertion and deletion keys. **Back**, X
or Escape cancels before submission. After a submission, Back refreshes the
parent listing. Select the new folder and Open/Enter to enter it; Parent returns.

The dialog uses the shared blue VIC and VDC controls and 1351 pointer. A VDC
that cannot acquire graphics retains a text dialog with keyboard controls.
Creation requires the graphical Files module; the standalone diagnostic browser
and the Files text-only startup fallback do not expose this operation.

Names contain 1–127 printable ASCII bytes. Quotes, slashes, backslashes,
colons, angle brackets, wildcards and vertical bars are rejected, as are trailing
spaces or periods. The complete absolute path may contain at most 255 bytes;
each component must fit the supported firmware's 127-byte creation limit.
Invalid names and excessive paths are rejected before storage I/O.

Existing files and folders are preserved. Each dialog submits at most one
creation request. After a result, the field and Create button are disabled;
Back returns to the directory. A failed or uncertain request is never replayed
automatically. Refresh may reveal a newly created folder even if its result
could not be checked.

## Renaming and deleting

In **ULT**, select a file or folder and press **Ctrl-R** to rename it or
**Ctrl-D** to delete it. The dialog opens with the selected name. For rename,
edit it and press Enter. For delete, Enter deletes the named entry in the
current directory. Back, X or Escape cancels before submission.

Rename sends Ultimate DOS `RENAME_FILE` (`$0a`) with both complete absolute
paths, `old NUL new`. The firmware refuses an existing target, including a
change of letter case only, and refuses moves between filesystems, so rename
never replaces data. A renamed folder keeps its contents. The new name is then
checked with `FILE_STAT`. The old path, including its trailing slash, may hold
at most 254 bytes so that the packet fits the 510-byte command body.

Delete sends `DELETE_FILE` (`$09`). The firmware's FAT `f_unlink` removes a
file or an empty folder; a folder with contents is refused and kept. Success
is shown only when a following `FILE_STAT` of the same path returns DOS status
82, FILE NOT FOUND. Any other metadata reply shows **result unknown** and Back
refreshes the listing. Deletion is permanent: there is no trash yet.

The same name rules, one-request-per-dialog rule, cursor cleanup and display
recovery apply as for folder creation. Rename and delete need a selected entry
whose name fits the 127-byte field. Opening a dialog from the keyboard is the
only entry point; there are no buttons for these actions yet.

## Storage and lifecycle

`FSVIEW.PRG` contains the dialog and its bounded field/path buffers. Its modal
`N_MCALL` remains active while the dialog runs, so its executable cannot be
replaced. No additional kernel entry, app allocation or scratch page is needed.
The existing Files core owns any directory cursor. Creation closes that cursor
and checks cleanup before sending a command. A failed close submits no creation
request; Back retries directory recovery through the normal browser.

The app sends Ultimate DOS `CREATE_DIR` (`$16`) through `N_UCOMMAND`, using the
selected DOS context and the complete absolute path. It then submits `FILE_STAT`
(`$08`) for the same path, checking the metadata before showing **Folder created
and checked**. These requests do not change either context's working directory
or open/close a cartridge file. The shared transport rejects a pending foreign
transaction. Display recovery freezes the dialog's actions until the owned VDC
screen can be restored.

The protocol follows the [Ultimate DOS target documentation](https://1541u-documentation.readthedocs.io/en/master/uci/ultimate_dos_target.html#dos-cmd-create-dir-0x16).
The checked source basis is Ultimate firmware commit
`a01c04e8267a0d916b7203cb34dcf1127f75981d`: `software/filemanager/dos.cc`,
`filemanager.cc`, `path.cc` and `software/filesystem/file_system.h`.
Its file manager refuses creation at an existing path. Absolute names reset the
temporary path to the filesystem root. The `FILE_STAT` request includes an
explicit NUL because that handler passes its argument directly to `fstat`.

This is Ultimate filesystem folder creation, rename and delete. IEC
partitions/directories, IEC rename/delete, recursive copy, mounted-media identity and recoverable trash
remain on the [completion roadmap](IMPLEMENTATION-ROADMAP.md).

## Verification

Build with `python3 -B build-native-desktop.py`, then run:

```sh
python3 -B tests/ci_native_folders.py --report /tmp/native-folders.json
```

The tests require Py65. They execute the loaded Files module and actual native
file/command services against an independent Ultimate FIFO/filesystem model.
They cover both DOS contexts, active cursor cleanup, keyboard/mouse input,
complete VIC/VDC frames, path limits, existing entries, filesystem errors and
unverifiable results. Physical Ultimate folder creation still needs qualification.
Use a fresh report filename: its companion `-captures` directory preserves the
complete frames and will not overwrite an earlier run.

The [software qualification record](validation/2026-09-14-native-ultimate-folders/README.md)
retains the executed inputs, CPU and VICE results, clean rebuild and complete
display captures.
