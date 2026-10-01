# Native banked text editor

Build with `python3 build-native.py`, boot `target/native/kestrel.d64`, press
**B**, select **EDITOR** and press Enter. This diagnostic editor is an ABI 1.7
application. It edits a document held in owned allocations across both C128
RAM banks, with a 24-bit byte position and length. Both displays show the
same document and cursor; the 80-column display shows more of each line.

The desktop suite instead opens the [blue graphical Editor](NATIVE-EDITOR-GUI.md),
with mouse caret placement and visible file/search controls on VIC and VDC. It
requires ABI 1.14; Tab moves focus, F7 opens Browse inside Open/Save As,
and the Case button toggles search case. The key table below describes the diagnostic text interface.

The [module loader](NATIVE-MODULES.md) loads the picker from `EDPICK.PRG`
and search from `EDFIND.PRG` beside the original app. The graphical suite
also loads `EDCLIP.PRG` for the [shared clipboard](NATIVE-CLIPBOARD.md). The matching files are
included on both suite disks; the suite combines search and graphics in
`EDFIND.PRG`. For USB, copy all modules for that Editor profile beside the editor
using those uppercase filenames. The modules must come from the same build
as the editor. All 22 CPU suites,
ten emulator workflows and complete physical USB/IEC workflows pass in the
[ABI 1.7 checkpoint](validation/2026-09-11-native-modules/README.md).

The [search checkpoint](validation/2026-09-12-native-editor-search/README.md)
records the new module's CPU and VICE checks, including a saved 66,058-byte
document and the five-app suite. Physical verification of this build remains
pending; preceding hardware records apply to their pinned images.

| Key | Action |
|---|---|
| F1 | Open an IEC SEQ file or an absolute Ultimate path |
| F3 | Save As a new file, close it, reopen it and compare every byte |
| Tab in Open/Save As | Browse files or choose a Save As folder/device |
| F5 | New empty document |
| F7 | Go to a hexadecimal byte offset, including offsets beyond `$ffff` |
| F2 / F4 | Beginning / end of document |
| F6 | Cycle D64, D71, D81 and Ultimate storage |
| F8 | Select IEC device 8–30, or Ultimate DOS context 1–2 |
| Arrow keys | Move by character or logical line; vertical movement retains the desired column |
| Home / Ctrl-E | Beginning / end of the current line |
| Ctrl-F | Find literal text, starting at the cursor and wrapping to the beginning |
| Ctrl-N | Find the next match, including overlapping matches; opens Find if no query is saved |
| Ctrl-R | Enter a query and replacement, then choose O for one match or A for all |
| Tab in Find/Replace query | Toggle exact case and ignoring ASCII letter case |
| Del | Delete the character before the cursor |
| Enter | Insert the document's first observed newline convention; a new document uses CR |
| Esc | Cancel a prompt or return to Files and Apps; during I/O, cancel after a transfer |

Open and Save As accept an IEC filename of at most 16 characters, or an
absolute [Ultimate path](NATIVE-ULTIMATE.md) of at most 255 bytes. Long fields
show the caret with `<` and `>` clipping markers; document names show their
tail with `<`. Both retain the complete path. [Shared field keys](NATIVE-FIELDS.md)
allow Left/Right, Home/Ctrl-E, insertion, Del/Ctrl-D and Ctrl-U.
Enter confirms
a field and Esc cancels it. New, Open and exit ask before discarding a dirty
document. **N** keeps it; **Y** proceeds. An asterisk after the filename means
there are unsaved changes. Save As refuses an existing filename. There is no
overwrite operation in this version.

Search fields accept up to 64 printable bytes. Find reuses the last query;
Ctrl-U clears the field. Enter accepts it and Esc cancels. An empty query is
not accepted; an empty replacement deletes matched text. Ignoring case folds
only ASCII `a`–`z` for comparison and preserves every other document byte.
Search is literal, without wildcards or regular expressions. The caret marks
the start of the result, and the status reports whether the search wrapped.

Replace One searches from the cursor and wraps. Replace All starts at the
beginning, processes non-overlapping occurrences and never searches inserted
replacement text. The status shows the completed replacement count in hex.
Esc stops scanning or a bulk replacement at a polling point. Completed changes
remain dirty and are counted; a later allocation failure leaves the next
original match intact. Transfer faults poison the document as described below.
Search progress updates every 256 scanned bytes; cancellation is also checked
after each replacement. Gap moves and individual memory transfers are blocking.
Other keys are consumed while the working status is visible.

The diagnostic Editor’s two modules share one reserved window; the graphical
Editor adds `EDCLIP.PRG` in that window. Switching from the picker to search
or back loads the requested module from the original app source. The saved query
and case setting survive this switch. A missing, damaged or mismatched module
reports an error and keeps the document; an explicit retry can load a corrected
module. Search results and field editing work on both displays.

The [shared file picker](NATIVE-FILE-DIALOGS.md) keeps the document allocated
and returns the complete selected name to the field. It can select IEC
SEQ/PRG/USR files, including raw PRG load-address bytes, and Ultimate files
and folders. Its directory and backend choices are separate from the desktop's
saved selection. The [picker checkpoint](validation/2026-09-10-native-file-dialogs/README.md)
is followed by the fully qualified [field checkpoint](validation/2026-09-10-native-fields/README.md),
which preserves the caret and both viewports when the picker is cancelled.

Imported CRLF, lone CR, lone LF, NUL and other bytes are preserved. CRLF is
one navigation/deletion unit; a Go To position between its bytes advances
past the pair. Nonprintable file bytes appear as dots. Typing inserts printable
single-byte characters; it does not provide a Unicode decoder. Lines remain
logical lines rather than wrapping into the document. The 16-row viewport
scrolls vertically and horizontally to keep the cursor visible; `<` and `>`
indicate clipped text.

The editor inherits the browser's data device and geometry. Changes made with
F6/F8 persist when returning to Files and Apps, including Ultimate contexts.
The ABI 1.5 browser retains its USB folder and selected filename while loading
its system image from the boot device. **F** returns to IEC/D64. Choose geometry to match the mounted disk; automatic
drive/media detection remains part of the platform work.
The browser's **L** field can also load the editor PRG from USB. Its valid
data preferences still take priority over the app's load source; select Ultimate
with F6 when needed. The shared picker uses ABI 1.5 directory cursors and ABI 1.6 field controls;
older kernels reject this image before executing it.

## Memory and storage behavior

[`document.inc`](../src/native/document.inc) implements a gap buffer with two
independent document contexts. RAM contexts own up to 24 allocations of 4 KiB.
In the graphical Editor (`DOC_PARTIAL`), when no complete 4 KiB run is left the
last allocation may be shorter: it starts at one page and grows in place a page
at a time (freed and reserved again one page longer at the same start; the
kernel keeps RAM contents), so it holds exactly what the document uses and never
moves. When the next page is taken, growth is refused and the document is
unchanged. Only the last allocation can be short, because positions map to
allocations by their 4 KiB index.
Logical length, cursor and gap boundaries are 24-bit values; local transfers
use at most 512 bytes. The RAM format can address 96 KiB per context, but actual
capacity is lower when the application, workspace allocations, a second
document or fragmentation consume the heap. The graphical suite also uses
[shared REU extents](NATIVE-SHARED-MEMORY.md) when available. Each REU context
has one resizable extent and can exceed 96 KiB without consuming additional
main RAM. Documents retain their storage when VDC graphics closes. Disk-backed
documents remain to be implemented; the diagnostic editor keeps its RAM path.

Open fills the pending context while retaining the current document. Only
complete input and a successful CLOSE permit the switch. Missing files,
allocation failure, cancelled input and read errors release the pending
context and retain the original document, cursor, name and dirty state.
Consequently, replacing a large document can run out of memory even when
that file could be opened after explicitly choosing New.

Save As clears dirty state and changes the filename only after an exclusive
create, full write, CLOSE, complete reopen comparison and read CLOSE succeed.
A failed or cancelled save retains the document and reports that a partial
file may remain. It neither retries uncertain data nor deletes that file.
An uncertain IEC CLOSE retains the file service's ownership record and can
block subsequent file actions; reset/recovery of those retained resources is
still a platform limitation. It must not be described as a successful save.

The IEC backend uses standard KERNAL calls and walks the file's sector chain
before reading. On the reference C128/Ultimate II+, opening 66,053 bytes took
295.976 seconds through the emulated 1541 and 38.311 seconds through native
Ultimate DOS. Save As of the edited 66,056 bytes, including a complete reopen
comparison, took 523.278 and 78.891 seconds respectively. Reopening the Ultimate
file through DOS context 2 took 38.312 seconds. These are hardware-harness
workflow times, including a 30-second initial quiet interval and 2-second
polling; they exclude entering the path and are not isolated throughput tests.

Known fault: on the reference machine that reopen through DOS context 2 has
failed twice (2026-09-11 and 2026-09-30), both times with status 9 (DISK
CLOSE FAILED); the 2026-09-11 record shows the read stopped at byte 64,000 of
66,056. The same workflow passed in the other runs. The cause is not known. The failed CLOSE
left the file open in context 2 across a C128 reset and a cartridge reboot;
the hardware checks now refuse to start until it is closed
(`hw_ultimate_check.py --close-dos-context 2`).

Esc is polled between data transfers; the IEC extent walk and individual
KERNAL calls remain blocking. Ultimate mode verifies each write before the
editor's full reopen comparison. Faster IEC paths and finer cancellation remain
required.

The preceding Ultimate checkpoint measured about 26 seconds for ten queued
filename characters with a small document and 46 seconds with the cursor beyond
64 KiB. The editor now updates field/status row 6 directly through the native
ROM cursor-positioning call. Field edits, deletion, cancellation and range-error
messages leave the document and its read cache alone. Each field update emits
at most one row per display, including spaces that erase a shortened value.

Ordinary byte edits and cursor moves within the current viewport redraw the old
and new caret rows plus mutable headings/status. Scrolling, line splits/joins,
new documents and file-operation returns use the complete renderer. The two
displays keep the same viewport and byte-preserving document model.

Two 512-byte read pages prevent repeated banked reads around a page boundary;
one uses the existing document output buffer and the other is private app RAM.
Edits and file-operation returns invalidate both pages. A failed cache fill
invalidates them as well. Seventeen 24-bit line offsets describe the visible
rows and their end. Single-byte edits adjust later offsets with carry/borrow;
structural changes rebuild the table. Cursor-only updates retain valid pages.
The [redraw checkpoint](validation/2026-09-09-native-redraw/README.md) records
CPU work counts, complete frame comparisons and physical timing qualification.
On the reference C128, ten queued field characters take 1.230 seconds in the
small document and 1.229 seconds beyond 64 KiB, including a 0.1-second quiet
interval. With the preceding 4-second interval retained, all 31 ordinary
ten-character queues take 4.194–4.198 seconds (median 4.196), compared with
25.705–45.988 seconds (median 26.632) previously. These elapsed times include
host monitoring; they are not isolated keyboard or CPU benchmarks.

Allocation failure occurs before an edit mutates logical bytes. Unexpected
handle/transfer failure poisons that context; subsequent reads/edits/saves
reject it instead of treating uncertain memory as a valid document. Cleanup
retains failed handles for a later release attempt. Controlled graphical exit
frees both documents, ends the memory lease and closes the provider. An
uncertain file owner remains quarantined with its document storage. The
diagnostic editor uses kernel owner cleanup for its RAM contexts.

The diagnostic editor reserves 79 heap pages for code, local state and either
module. The graphical suite uses 96 app pages, a 16-page owned workspace,
a 36-page surface and a 39-page VDC/memory/history provider plus its RAM/REU screen backup;
its [memory and lifetime contract](NATIVE-EDITOR-GUI.md#storage-and-presentation-lifetime)
accounts for those allocations separately.
Saving reuses the insertion buffer for its reopen comparison. The picker
borrows three idle 512-byte buffers and allocates additional cache blocks of
at most four pages
only while browsing. RAM document capacity depends on the remaining heap
and 4 KiB allocation fragmentation. REU capacity depends on free extents and
temporary space for relocation or staged Open. The workspace's bank-0 block sits at
the top of managed RAM, keeping the free region below it contiguous.
The kernel reserves 4 KiB for Ultimate services and manages 426 heap pages.
The existing public file entries dispatch both backends; ABI 1.3 adds the
Ultimate path/status mailboxes. The preceding loader and directory checkpoints
kept the editor image unchanged; the search build changes the core and binds
both modules to it. The graphical Editor's bank-0 workspace occupies `$5000..$5fff`
([workspace.inc](../src/native/editor/workspace.inc)). Beside it and the 36-page
surface, bank 0 keeps one complete 4 KiB run, so a RAM document beyond 64 KiB
relies on the short final allocation described above. Without a RAM-backed VDC
snapshot (no 80-column display, or the snapshot in an REU) that also leaves the
picker's 19 cache pages for a full D81 directory beside a 66,057-byte document.
With the 80-column display snapshotted in RAM, 175 or 167 pages remain
([NATIVE-EDITOR-GUI](NATIVE-EDITOR-GUI.md)), so an Open of that size is refused
and the current document kept; with an REU, documents move to the REU instead.

## ROM integration

The native ROM normally expands programmable function keys. The editor saves
all 256 bytes of the definition table, installs one returned code per key,
and restores the original table on controlled exit. Table updates mask IRQs
and clear pending expansion state. The tests exercise the real ROM GETIN
expansion path; they do not claim to simulate a physical key switch.
The memory layout and expansion behavior come from Commodore's editor source:
[declarations](https://github.com/mist64/cbmsrc/blob/master/EDITOR_C128/declare.src),
[key definitions](https://github.com/mist64/cbmsrc/blob/master/EDITOR_C128/ed6.src),
and [input/output routines](https://github.com/mist64/cbmsrc/blob/master/EDITOR_C128/ed1.src).

Literal text output clears the ROM quote flag before each CHROUT. This keeps
reverse-video cursor controls working inside quoted text. Complete VIC and VDC
screen comparisons cover that behavior through the actual ROM.

## Qualification and remaining work

The [field checkpoint](validation/2026-09-10-native-fields/README.md) adds shared
caret editing and exact field-state retention through picker cancellation.
Twenty CPU suites, ten emulator workflows, 57 physical USB frame pairs and
24 physical IEC frame pairs pass. Both physical paths independently verify the
saved 66,056-byte document and restored the machine afterwards. The archived
initial boot/upload failure is excluded from the passing workflow counts.

The preceding [picker checkpoint](validation/2026-09-10-native-file-dialogs/README.md)
qualifies the shared Open/Save As library with 18 CPU suites, four final-image
follow-ups, all ten native emulator workflows and complete physical USB/IEC
checks. All seventeen document chunks match the expected 66,056 bytes while
the picker has focus. The archive records both interrupted IEC attempts and
the host-only connection fix, alongside the completed run and independent
closed-file readback.

The [redraw checkpoint](validation/2026-09-09-native-redraw/README.md) records
the editor image and display performance checks. The
[Ultimate checkpoint](validation/2026-09-09-native-ultimate/README.md) records
the earlier kernel/backend and its initial physical C128 USB timings. The
[USB app checkpoint](validation/2026-09-09-native-usb-apps/README.md) loads
the same editor from USB through the ABI 1.4 kernel. The preceding
[IEC editor checkpoint](validation/2026-09-09-native-editor/README.md) records
the initial observation failure with its correction and the IEC timing baseline.

Use an environment with Py65 for the CPU models, and VICE/64tass for emulator
checks:

```sh
python3 tests/ci_native_document.py --report /tmp/native-document.json
python3 tests/ci_native_editor_search.py --report /tmp/native-search.json
python3 -u tests/ci_native_editor_iec.py --format d81 --search
python3 tests/ci_native_editor.py --report /tmp/native-editor.json
python3 tests/ci_native_editor_ultimate.py --report /tmp/native-editor-ultimate.json
python3 tests/ci_native_editor_redraw.py --report /tmp/native-editor-redraw.json
python3 tests/ci_native_file_dialog.py --report /tmp/native-file-dialog.json
python3 -u tests/run_ci.py nativeeditor nativeeditor71 nativeeditor81
python3 -u hw_ultimate_check.py --native-editor
python3 -u hw_ultimate_check.py --native-ultimate
python3 -u hw_ultimate_check.py --native-redraw
python3 -u hw_ultimate_check.py --native-usb-apps
python3 -u hw_ultimate_check.py --native-usb-browser
```

The physical commands take the Ultimate's address from `--host` or
`KESTREL_ULTIMATE_HOST`. Each records the drive state first and, when it ends,
puts every drive's image and mode back, deletes its uploads and resets the
C128 (`hw_session.py`). `--native-editor` mounts the complete system D64 on
drive A/device 8 and a separate document D64 on drive B/device 9. Drive B must
initially be an enabled, empty 1541 on device 9; the helper returns it to that
state, then downloads the closed data disk over the Ultimate's FTP server for
the independent readback. The checks use a 60-second host request timeout and
never replay a RAM write whose acceptance is unknown. The helper retries TCP
connection establishment at most three times before sending HTTP request
bytes; it disables reconnection after sending begins. It checks stored
disk-upload sizes before boot. An interrupted run's report lists what it left
behind; `hw_ultimate_check.py --native-reclaim REPORT` restores and removes
exactly that.
`--native-ultimate` uses a new private USB directory and independently compares
all five closed source/output files before removing its fixtures.
`--native-redraw` adds field/cursor timing checks to that complete USB workflow.
`--native-usb-apps` adds browser path input, USB calculator/history, rejected app
images and USB editor loading before the complete large-document workflow.
`--native-usb-browser` checks folders and paging beyond ordinal 255 in both
Files and Apps and the editor picker, with the complete document retained. It
currently refuses to run: it compares the app's directory packets with an
independent listing in the same form (attribute bytes, firmware order,
canonical paths), and the Ultimate's REST API has no directory listing while
its FTP listing carries no attribute bytes.
Editor metadata is captured by the C128 CPU into bounded low-memory chunks;
the host also retains direct DMA observations for comparison. The earlier IEC
checkpoint recorded a 109-byte direct snapshot matching BASIC ROM. The redraw
checkpoint records two more complete ROM snapshots, of 128 and 587 bytes, while
the corresponding CPU snapshots and screens match the document. The host uses
CPU captures as its editor-state oracle and retains these ROM comparisons.

The [suite build](NATIVE-EDITOR-GUI.md) supplies graphical controls, mouse
caret placement and 24-bit keyboard/mouse selection with range replacement.
The suite also supplies [shared clipboard](NATIVE-CLIPBOARD.md) exchange and
[sixteen-step undo/redo](NATIVE-HISTORY.md). Document associations,
multiple open tabs and session recovery remain open. Fonts,
styles, pagination, images, spelling and printing belong to the word processor
work. The [completion roadmap](IMPLEMENTATION-ROADMAP.md) retains those
requirements along with the native desktop, Ultimate services and expansion
drivers. This text editor is one application milestone toward that scope.
