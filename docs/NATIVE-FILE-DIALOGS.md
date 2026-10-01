# Native file dialogs

The native desktop suite's Editor, Files, Paint and Ultimate share the
[blue graphical file picker](NATIVE-PICKER-GUI.md). Editor's **Browse** button
and **F7** open it from Open/Save As. The diagnostic text editor retains its
**Tab** shortcut. The picker handles D64, D71, D81 and Ultimate directories.
In graphics mode, **Enter** activates the focused control or file row;
**Choose** returns a file or enters an Ultimate folder. **P** goes to its
parent, **N/B** page, **F** changes backend and **D** selects an IEC device.
Graphical **Tab** moves focus and **F1** switches Ultimate DOS contexts;
the text fallback uses **Tab** for the DOS context.

In Save As, **Use Here** / **S** chooses the current folder/device and keeps
the proposed basename, including in an empty folder. Selection returns to
the caller. Open still checks dirty documents, and Save As still creates
exclusively and compares every byte after reopening. The picker itself does
not launch applications or write file contents. **Esc** returns to the
original field. The document, cursor and viewport remain owned by the caller.

Navigation remains a source library. The diagnostic editor introduced its
picker as an [ABI 1.7 module](NATIVE-MODULES.md), loaded
into its existing allocation on first use. All 22 CPU suites, ten emulator
workflows and complete physical USB/IEC workflows pass in the
[module checkpoint](validation/2026-09-11-native-modules/README.md). Kernel ABI 1.5
provides owned directory/file and heap operations, and ABI 1.6
[shared field controls](NATIVE-FIELDS.md) retain the field caret and display
viewports on cancellation. The diagnostic editor requires minor version 7; the graphical suite uses
the ABI 1.10 Editor and Files modules.
Desktop and dialog navigation share `file-browser.inc`, `browser-ui.inc`,
`browser-usb.inc` and `browser-ultimate.inc`; `FD_EMBEDDED` excludes application
discovery, launch and binary-preview code from the editor.

## Caller contract

`file-dialog.inc` exports `fd_run`. Set `fd_mode` to 1 for Open or 2 for Save
As, `fd_device`/`fd_format` to the data backend, and `fd_name`/`fd_length` to
the proposed name (0–255 bytes). `FD_NAME_BUFFER` supplies a writable 256-byte
bank-0 field. Calls are foreground only, with interrupts enabled and a valid
active app owner. Decimal and interrupt flags are preserved.
`FD_SAFE_CHARACTER` supplies a caller routine which returns a safe printable
character, replacing control bytes with a dot; the editor keeps it in its core
so document filenames can be drawn before the module loads.

Carry clear/A=0 returns a candidate filename and its backend. `fd_type`
identifies SEQ/PRG/USR for IEC Open, preserving raw PRG load-address bytes.
Save As chooses SEQ; Ultimate files remain raw. Carry set/A=0 cancels;
carry set/A=an ABI error reports failure. Input fields change only after
successful selection and checked cleanup. Complete raw names are retained;
the editor displays dots for bytes that are unsafe as console controls.

The dialog borrows and restores the desktop browser's path, ordinal, complete
selected name and preferences. Its last directory is separate from that
desktop state. File and heap argument mailboxes may change. Cleanup closes
only cursors opened by the picker and frees only its cache handles; it never
releases the caller's entire owner. Uncertain cursor cleanup prevents a
successful selection and retains the handle for a later checked cleanup.

## Memory

The caller supplies two, three or four distinct idle 512-byte buffers through
`FD_SCRATCH0` onward, selected by `FD_DIRECT_PAGES=4`, `6` or `8`. The editor
lends its input, output and second read-page buffers. These transient bytes
remain separate from document chunks, and callers invalidate their read
caches before repainting.

Ultimate records use 256 bytes plus a separate name-length array. Two
transactional pages of eight entries require 4 KiB. Cache allocations are
lazy, in blocks of at most four pages, and can use either RAM bank.
The graphical IEC picker packs twelve 20-byte records per page, preserving
all 296 D81 entries in 25 pages. The text picker retains 32-byte records.

The graphical Editor occupies 96 app pages and keeps its 36-page surface
while the picker is active. Its full D81 cache needs nineteen additional
pages. A seventeen-chunk document occupies 272 pages, for a total of 423
of the 426 heap pages. The diagnostic editor retains its 79-page allocation.
Allocation failure must return to an intact caller, and any failed release
must retain the exact descriptor for later cleanup.

## Qualification and remaining work

The library uses ABI 1.6 shared fields; embedded callers require at least minor
6, and the diagnostic modular editor requires 7. The preceding
[field checkpoint](validation/2026-09-10-native-fields/README.md)
qualifies its caret and viewport retention with twenty CPU suites, ten emulator
workflows and full physical USB/IEC checks. All five complete document captures
and the eight-byte field records match across picker cancellation. The older
counts below describe the preceding ABI 1.5 picker release.

All 18 CPU suites passed before the final six-byte F8 preference fix; the
editor, Ultimate editor, redraw and file-dialog suites passed again afterward.
The 11 picker flows cover all three IEC geometries, cancellation, raw PRG Open,
Save As, quoted Ultimate folders, empty folders, complete raw filenames,
296-entry D81 directories, 255-byte paths, memory exhaustion and retained-close
recovery. They also retain a 66,056-byte document through 300-entry navigation
with both workspace blocks. All ten native emulator workflows pass, including
complete document captures while the picker has focus on D64, D71 and D81.
The [picker checkpoint](validation/2026-09-10-native-file-dialogs/README.md)
also passes complete physical C128 USB and IEC workflows. Independent readback
matches nine USB files and all four files on the IEC data disk. The USB picker
pages beyond ordinal 255 while retaining the complete document; both physical
workflows capture all seventeen document chunks with the picker active.
The archive retains two interrupted IEC attempts and the host connection fix,
with eight fault-injection cases proving that sent writes are never replayed.
D71/D81 results are emulator evidence; the physical IEC run uses Ultimate
emulated 1541 drives. These counts describe the older text picker. The graphical picker is tracked
separately in [NATIVE-PICKER-GUI.md](NATIVE-PICKER-GUI.md). Scheduling and the
full OS roadmap remain open; dynamic module qualification is tracked separately
in [NATIVE-MODULES.md](NATIVE-MODULES.md).
