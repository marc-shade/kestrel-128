# Native Files and Apps

Press **F** on the native suite desktop to open Files. Its **C** command copies
the selected file, and **Esc** returns to the desktop on both IEC and Ultimate.
The [suite interface](NATIVE-FILES-GUI.md) uses blue graphics on both displays,
with yellow focus on the VIC and color VDC, and reversed focus on a 16 KiB VDC.
VDC text remains available as a fallback. Tab cycles its enabled controls
and Enter activates the focused control; clicking a row selects it.
The standalone diagnostic disk retains its read-only browser:
press **B** in the native memory workspace to browse files and launch native
applications. The same file list and byte viewer appear on the complete
40- and 80-column screens. Build with `python3 build-native.py` and boot
`target/native/kestrel.d64`; it contains `U`, `CALC`, `BROWSE` and `EDITOR`.

## Controls

| Key | Action |
|---|---|
| Up / Down | Select the previous / next file |
| N / B | Move forward / back eight entries |
| A | On IEC, select the next discovered native application, wrapping at the end |
| Enter | Launch a selected APP, otherwise inspect the file |
| I | Inspect file bytes, including a native application's PRG header |
| R | Refresh the current directory |
| D | Enter an IEC device number, 8–30; Enter accepts, Del edits, Esc cancels |
| F | Cycle D64 / D71 / D81 / ULT |
| G / P | On ULT, enter an absolute directory path / navigate to the parent |
| F1 / Tab | On ULT, switch DOS context 1 / 2 with F1 in suite Files, or Tab in the diagnostic browser |
| L | Enter an absolute Ultimate app path |
| C | In the suite Files app, copy the selected file |
| Ctrl-K | In graphical suite Files on ULT, create a folder in the current directory |
| Ctrl-F | In graphical suite Files, find the next filename containing the entered text |
| Esc | Return to the suite desktop, or to the standalone diagnostic workspace |

The list shows the stored name, file type and allocated block count. `*` marks
an unclosed file and `<` marks a locked file. Choose the actual disk format;
the selector does not identify hardware or guarantee support for every IEC
device. Root directories on standard D64, D71 and unpartitioned D81 images
are supported. IEC folders and partitions require further backend work.
The stream API accepts printable filenames without wildcard or DOS command
syntax. Other stored names remain visible, but opening them reports an error.
Only trailing shifted-space padding is removed; an embedded shifted-space
must never select a different file with a shorter name.

**L** opens a USB app path field, initially `/Usb0/`. **F1** in suite Files
(**Tab** in the diagnostic browser) selects DOS context 1 or 2.
**Ctrl-U** clears the field, **Del** deletes one byte,
**Enter** launches and **Esc** cancels. Up to 255 printable bytes are retained;
long paths keep the caret visible with `<` and `>` clipping markers.
[Shared field keys](NATIVE-FIELDS.md) also provide Left/Right, Home/Ctrl-E,
insertion and Ctrl-D forward deletion. Empty or relative paths are
rejected without I/O. Editing only repaints the field rows and preserves the
current listing, selection and preferences. This field launches a known
absolute path. **G** instead opens a directory path, using the same editing keys.

In **ULT** mode, **Enter** opens a folder or file and **P** opens the parent.
**N/B** page through eight entries at a time; Up/Down also cross page boundaries.
Names retain all 255 raw bytes even when the screen shows only their tail.
The complete canonical path is retained, and the selected raw name is used to
build the file target. A joined path longer than 255 bytes is rejected before I/O.

Forward pages continue one owned directory cursor. Backward pages, refreshes
and returns after a closed preview reopen and scan to the requested ordinal.
Both position and displayed page number use 32-bit counters. A second cache
buffer keeps the old page visible until the next page is complete. **Esc**
during scanning cancels and retains that page; another queued key is kept for
the event loop. A failed open or scan also preserves the previous listing.
An empty directory clears all eight rows. Canonical paths returned by the
backend keep parent navigation correct after `..` or redundant slashes.

The byte viewer reads closed SEQ, PRG and USR files, showing up to 128 bytes
per page as hex with a safe PETSCII column. Control and high bytes appear as
dots; the hex values preserve their exact values. PRG load-address bytes are
included. The header shows a 32-bit byte offset; row labels show its low
16 bits. **Enter/N** reads the next page and **Esc** returns to the selected
file. Empty files and a final short page report end of file and close their
streams. A read failure shows the accepted prefix and an error. The current
viewer is forward-only; seek, previous-page navigation and editing remain open.

## Finding filenames

**Find / Ctrl-F** opens the [filename search dialog](NATIVE-FIND.md). It finds
literal text anywhere in a stored name, ignores letter case and wraps once at
the end. IEC uses the complete retained directory snapshot; Ultimate streams
complete names across page boundaries. Back, X or Escape cancels scanning and
keeps the published page and selection. A successful search selects the matching
row for Open, View, Copy, Edit or Paint.

## Copying from the suite Files app

Select a closed SEQ, PRG or USR file, or an Ultimate file, and press **C**.
The dialog retains the exact source name/path and proposes it as the destination.
Use **Ctrl-U** to clear the name and the shared field keys to edit it. **F7**
opens the destination picker; **Tab** cycles graphical controls. Select a device/folder with **S**, or choose a
listed name and edit it after returning. Browser source preferences and the
source selection survive the picker. **F1** edits the destination device or DOS
context, **F3** selects D64/D71/D81/ULT, and **F5** selects the destination IEC
type. PRG load-address bytes are copied as stored. Ultimate files are raw bytes;
the type setting matters when the destination is IEC.

**Enter** creates a new destination exclusively. An existing name is rejected.
The app streams 512-byte chunks, closes both files, reopens them, compares every
byte and checks for extra destination bytes. It reports success only after
that comparison and both final closes succeed. Copied and verified byte counts
use 32 bits. **Esc** cancels at a transfer boundary. Failed/cancelled new files
are retained and may be incomplete; the app does not replay uncertain writes
or delete their output. Changing a destination clears its previous result.
Failed closes retain their descriptors for Copy, Browse or Back cleanup retry.
The text fallback also accepts Tab to open the picker.

Ultimate-to-Ultimate copies require different DOS contexts: each supports one
open file. The dialog initially selects the other context. It closes directory
cursors before starting streams. The permanent Files core owns the ROM keyboard
callback and function-key table across graphics/picker replacement, and restores
the callback and all 256 original table bytes on app exit.

**Zero-byte files can be copied to Ultimate storage.** Zero-byte IEC output is
rejected before destination creation. The standard 1541/1571/1581 DOS close
routine inserts a carriage return when no bytes were written; the current
native file API has no operation to truncate that file back to zero bytes.
VICE exposed this difference from the original CPU model, and the full reopen
comparison detected it. Native zero-byte IEC creation remains a backend gap.

Build with `python3 -B build-native-desktop.py`. Both suite disks contain the
Files core, `fsview.prg` graphics module and `fspick.prg` destination picker.
Files reserves 96 bank-0 app pages, sixteen scratch pages, its 36-page graphical
surface and the usual 37-page IEC browser cache in bank 1. Its shared VDC
component uses 39 bank-1 pages and retains one screen backup in REU or
main RAM. The modules share one checked window
and load from the original app source folder, independently of the selected
data device or DOS context. Scratch storage must be available at `$5000..$5fff`;
an occupied bitmap range leaves usable text controls. Copy size is not limited
by the transfer buffers. No new kernel service is required.
The [copy checkpoint](validation/2026-09-12-native-files-copy/README.md) retains
the exact build, CPU/VICE checks, exported files and the discovered DOS limit.

## Discovering and returning from applications

A closed PRG is labelled APP when its first 34 bytes are readable and begin
with the `$6000` load address and `NAPP` magic. This is discovery only. The
[application loader](NATIVE-APPS.md) validates the full manifest, ABI, declared
length and checksum before execution. A damaged or incompatible image can
therefore appear as APP and be rejected when launched.

Launching releases the browser's code allocation and directory cache before
loading the selected app. A normal app return reopens the browser from the
boot disk. The selected data device and format survive; the row selection
starts at the first file for IEC. Ultimate additionally retains the canonical
folder and selected full filename. On app return it scans for that name, even
if a saved file changed its ordinal or page; a removed name falls back to the
first page. Load errors with completed cleanup also return to
the browser and display the error. Uncertain resource cleanup retains the
owner and returns an error to the workspace; recovery still needs a dedicated UI.

For example, a calculator PRG named `NUMBER` on device 9/D71 can be discovered
and launched without adding a fixed launcher entry. Its **S** command writes
and verifies history on that source device/format. **Esc** returns to BROWSE
on the boot disk while keeping the device-9/D71 file list preference.
An app launched through **L** uses the same checked loader. A USB-loaded
calculator saves history beside its app file and returns to the boot browser.
The editor retains its selected data backend independently of where its app
image was loaded; use F6/F8 to choose the data source.

## Resources and current limits

BROWSE is a 7,127-byte image plus its two-byte PRG address. It reserves 28
bank-0 pages for code/data and 37 bank-1 pages for 296 compact directory
records on IEC. ULT reuses that allocation for two eight-entry buffers, each
entry occupying 512 bytes. Its retained path uses `$4a00..$4aff`; the selected
name uses `$3e00..$3eff`, with lengths and the 32-bit ordinal in the native
mailbox. These regions were already excluded from the heap. The browser
requires ABI 1.6 for shared field controls; the allocator still manages 426 pages.
Workspace allocations remain owned across browser/app handoffs. Exit closes
owned files before releasing memory. Neither a mouse nor an REU is required.

The [directory API](NATIVE-FILES.md#directory-pages) rewalks from the root for
each page. Reading all 37 D81 pages can require 703 directory-sector reads,
plus file extent/header probes for PRGs. A persistent cursor and performance
work are needed for large directories. Enumeration has geometry bounds, but
there is no removable-media identity check or resumable background scan.
ULT uses the [owned cursor contract](NATIVE-ULTIMATE.md#directory-cursors-abi-15).
A pending page reserves the shared UCI transport until it is consumed or
closed. Native scheduling and a broker for background clients remain required.
ULT file headers are inspected when opened; it does not prelabel every row APP.

This application adds a native file list, app discovery and byte inspection.
The editor's [shared file picker](NATIVE-FILE-DIALOGS.md) now includes the same
navigation source, with caller-owned buffers and checked return to its filename
field. The [picker checkpoint](validation/2026-09-10-native-file-dialogs/README.md)
qualifies both applications against CPU, emulator and physical USB/IEC workflows.
The [field checkpoint](validation/2026-09-10-native-fields/README.md) also qualifies
middle edits, both clipped viewports and the full 255-byte browser path through
the shared ABI 1.6 controls, without increasing the 28-page app allocation.

The graphical suite's [New dir dialog](NATIVE-FOLDERS.md) creates Ultimate
folders, checks the result and refreshes the parent listing. Files also opens
text and UPNT documents through [Editor/Paint associations](NATIVE-DOCUMENT-LAUNCH.md).

Native rename/delete, zero-byte IEC creation, configurable file associations, richer document
editing, broader widgets, scheduling and the remaining native Ultimate desktop
services remain on the [completion roadmap](IMPLEMENTATION-ROADMAP.md).

## Validation

```sh
python3 tests/ci_native_directory.py --report /tmp/native-directory.json
python3 tests/ci_native_browser.py --report /tmp/native-browser.json
python3 tests/ci_native_usb_apps.py --report /tmp/native-usb-apps.json
python3 tests/ci_native_directory_ultimate.py --report /tmp/native-directory-ultimate.json
python3 tests/ci_native_browser_ultimate.py --report /tmp/native-browser-ultimate.json
python3 tests/ci_native_files_copy.py --report /tmp/native-files-copy.json
python3 -B tests/run_ci.py nativefilescopy
python3 -u tests/run_ci.py nativebrowse nativebrowse71 nativebrowse81
python3 -u hw_ultimate_check.py --native-browser
python3 -u hw_ultimate_check.py --native-usb-apps
python3 -u hw_ultimate_check.py --native-usb-browser
```

`--native-usb-browser` refuses to run until an independent directory reference
is available (see [NATIVE-EDITOR](NATIVE-EDITOR.md)).

CPU tests require Py65. The emulator workflows use true 1541/1571/1581 drive
emulation, compare both complete screens and independently extract saved bytes.
The physical test uses a private D64 on the reference C128/Ultimate II+,
puts the machine's drive state back, then downloads the complete closed disk
over the Ultimate's FTP server for independent file comparisons. It does not qualify physical
D71/D81 drives. See the [dated evidence](validation/2026-09-09-native-browser/README.md)
for exact builds, outcomes and retained failed observations.
The [USB app checkpoint](validation/2026-09-09-native-usb-apps/README.md)
adds full-path field, shared-loader and USB calculator/editor qualification.

The [ABI 1.5 directory checkpoint](validation/2026-09-10-native-directories/README.md)
records owned cursors, complete names, folder navigation and selection after
app saves reorder the listing, with CPU, emulator and physical qualification.
