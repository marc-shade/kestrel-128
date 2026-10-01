# Shared graphical file picker

The desktop suite's Editor, Files, Paint and Ultimate use one blue bitmap file
picker. The selected control turns yellow, and a 1351 mouse on port 1 can
select rows, press buttons and position the path-field caret. Ultimate, Paint and Files also
show the picker graphically on the VDC, using yellow focus with 64 KiB and
reversed light controls with 16 KiB. Editor retains its VDC text view.

A row click selects a file. **Choose** opens a folder or returns a file to the
calling app. **Enter** activates the focused control or file row. **Tab** moves
among the available controls; cursor
keys select files and **N/B** change pages. **Refresh**, **Device**, **Format**,
**DOS 1/2**, **Parent** and **Path** expose the same operations as their keyboard
shortcuts. **F1** changes the Ultimate DOS context while the graphical picker
is active. **Use Here** is available for Save As and retains the proposed
basename, including in an empty directory. **Cancel** and **Esc** return to the
caller; inside a field, they dismiss that field first.

The path field retains all 255 bytes. Its display scrolls to keep the caret
visible, and mouse placement changes the caret within that viewport. The
formatter replaces control characters only for display. Selection still
returns the complete raw path. Typing repaints the field and its messages
without clearing the entire bitmap.

The picker does not open document files, write their contents or mount disk
images. Editor returns to its editable Open/Save As field; Files returns to
its copy destination; Paint performs its existing staged image load; Ultimate
returns to its explicit drive confirmation. Existing exclusive creation,
readback verification, dirty-document checks and drive protection remain in
the callers.

## Ownership and module layout

`FD_GUI=1` enables `src/native/picker/gui.inc`. It draws through the native
heap/display API into the caller-owned 36-page surface at `$c000`. The surface
descriptor remains in the calling app, including across a failed release.
Editor and Files load the picker into their existing checked module window.
Paint and Ultimate share their already resident font and pointer code.

The picker closes its VIC pointer and display before returning. Ultimate,
Paint and Files retain their shared VDC component and original screen backup across the
picker and app dialogs, releasing them when the app exits or explicitly
restores a failed graphical display. An unavailable
surface or display falls back to the existing text consoles. Refresh retries
display acquisition. Directory/stream cleanup retains its existing checked
ownership: a failed close or free cannot produce a successful selection or
permit a module containing the retained handle to be overwritten.

Every glyph transfer restores the bytes it borrows from `N_BUFFER`. This is
necessary because the Ultimate formatter reads the current raw directory
entry from that same buffer. Pointer sampling, ROM function-key ownership and
input counts follow the shared native input implementation. A keyboard event
disarms a held mouse press before changing the control or view.

## Directory capacity

A graphical IEC picker stores the 20 bytes needed for selection and display:
file type, flags, all sixteen filename bytes and the two-byte block count.
Twelve records occupy each cache page without crossing its boundary. The full
296-entry D81 root therefore needs 25 pages. The diagnostic text picker keeps
its original 32-byte record format.

Editor and Paint lend three idle 512-byte buffers; Paint keeps them in its separately owned scratch allocation. Ultimate lends one and
allocates two more in a four-page bank-0 heap extent while the picker is open.
Files lends two from its separately owned scratch allocation;
its copy and verification operations still use their complete 512-byte
transfer buffer. Remaining cache pages are allocated lazily in blocks of up
to four, from either RAM bank. The final block size uses the complete IEC
capacity for both formats, so changing from an Ultimate directory to IEC
cannot reuse an undersized allocation.

Ultimate still retains two transactional pages of eight full directory
entries. Names, continuation state and recovery semantics are unchanged.
Editor retains its entire banked document while the picker is visible. No
additional allocation is needed for a bitmap text cache.

The Editor core and picker occupy 24,574 bytes of their 24,576-byte window;
the build rejects a module that exceeds it. The complete suite D64 has twelve
entries plus the shared VDC component. The current suite leaves 140 free D64 blocks. The full mouse
workflow selects a separate data disk for its module copy and Paint image;
the boot disk retains its Editor and calculator sample files.

## Software qualification

The [frozen software qualification](validation/2026-09-13-native-picker-gui/README.md) passes. Checks cover complete bitmap
bytes and 80-column output; keyboard and mouse controls; fields and long raw
paths; all four callers; a full D81 directory beside a document over 64 KiB;
format changes; fallback and retained resources; and real IEC emulation.
This work does not change the installed physical C128 build.

The CPU runner is `tests/ci_native_picker_gui.py`, with a required `--case`
of `keyboard`, `mouse`, `paths`, `large`, `formats`, `callers` or `fallback`
and a `--report` JSON path. It requires the project's py65 test environment.
`tests/ci_native_pointer_iec.py` exercises real VICE mouse/keyboard input in
40-column mode or with `--80col`; `tests/ci_native_editor_gui_iec.py` covers
the full directory and large-document workflow through emulated IEC drives.
