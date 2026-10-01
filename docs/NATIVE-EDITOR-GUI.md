# Native blue Editor

Build with `python3 -B build-native-desktop.py`, boot
`target/native-desktop/kestrel.d64`, and open the **Editor** icon. The suite
Editor uses the desktop's blue bitmap, yellow focused buttons and port-1
1351 mouse. Closing it returns to the same desktop with Editor selected.
The VDC mirrors the complete interface at 640×200, including the document,
caret, file/search controls and picker. A 64 KiB VDC shows color and yellow
focus; a 16 KiB VDC uses white on blue with reversed focus.

The [banked editor](NATIVE-EDITOR.md) supplies the document, search and file
operations. This is plain-text editing with 24-bit byte positions, preserved
imported bytes, transactional Open and exclusive, reopened-verified Save As.
Selection supports keyboard marking, mouse dragging and replacing the selected
bytes. The [shared clipboard](NATIVE-CLIPBOARD.md) exchanges text with Claude.
[Sixteen-step undo/redo](NATIVE-HISTORY.md) covers edits and clipboard/search
replacement. Styled pages, printing and session recovery remain roadmap work.

## Controls

| Control | Action |
|---|---|
| Open / F1 | Enter a filename or absolute Ultimate path |
| Save As / F3 | Create a new file and compare every byte after reopening it |
| Find / Ctrl-F | Enter a literal query, with exact or ignored ASCII case |
| Replace / Ctrl-R | Enter a query and replacement, then choose One or All |
| `...` | Cycle file, New/Go To/Device/Format, Mark/All/Clear, Copy/Cut/Paste, and Undo/Redo/Forget controls |
| Mark / Ctrl-B | Start or end keyboard marking at the caret |
| All / Ctrl-A | Select the complete document |
| Clear / Ctrl-G | Clear the selection without changing document bytes |
| Copy / Ctrl-C | Copy the selection to the session clipboard |
| Cut / Ctrl-X | Copy and remove the selected bytes |
| Paste / Ctrl-V | Insert clipboard bytes or replace a selection |
| Ctrl-K | Clear clipboard memory |
| Ctrl-P | Print the document on IEC device 4 (see Printing) |
| Undo / Ctrl-Z | Restore the previous edit, up to 16 steps |
| Redo / Ctrl-Y | Reapply an undone edit |
| Forget / Ctrl-U | Release undo history while retaining the document |
| New / F5 | Start an empty document after confirming unsaved changes |
| Go To / F7 in the document | Enter a hexadecimal byte offset |
| Device / F8 | Select an IEC device or Ultimate DOS context |
| Format / F6 | Cycle D64, D71, D81 and Ultimate storage |
| Tab / Enter | Move focus among enabled controls / activate the focused control |
| Browse / F7 in Open or Save As | Open the shared file picker |
| Case in a search query | Toggle exact case and ignoring ASCII letter case |
| X / Esc | Close the app; Escape first clears an active selection, or cancels the current dialog/operation |
| Ctrl-L | Redraw; retry unavailable graphics/history |

Moving the mouse selects a control. Press and release on the same control to
activate it; releasing outside cancels. Clicking the document places its caret
at that character or the end of the clicked line. It accounts for horizontal
scrolling and treats CRLF as one navigation unit. Clicking a field positions
its caret within the full value. Typing returns focus to the document or field.
The [existing editing keys](NATIVE-EDITOR.md) still apply.

The 16-row document view scrolls to keep the caret visible. Filename and path
clipping changes only their display: Open and Save As retain up to 255 raw
Ultimate path bytes. Dirty-document confirmation defaults to **Keep**. Save As
refuses an existing file. Cancel is polled between file chunks while opening,
writing and comparing the saved file. A cancelled save preserves the document's
name and dirty state and may leave the new partial file; it never deletes or
replaces another file.

The [shared graphical picker](NATIVE-PICKER-GUI.md) keeps the entire document
allocated and returns to the blue dialog with the chosen filename, folder and
device. Cancel preserves the original field and caret. F7 opens it because
Tab now navigates graphical controls. Find/Replace also has a visible Case
button, while Ctrl-N finds the next occurrence of the saved query.
During search, the current byte position is shown in hexadecimal. A display
update failure pauses editing, file transfers and search until Esc can restore
the saved screen. Esc then follows the normal cancellation path. Completed
replacements and any new output file bytes remain available.

## Selecting and replacing text

Drag from a character to select a range. Moving above or below the document
view scrolls through logical lines; the left and right edges let the caret
follow horizontally clipped text. Releasing outside the document completes
the range without activating a toolbar control. Disconnecting the pointer
ends the drag at its last observed range.

With the keyboard, **Ctrl-B** sets an anchor. Move with the normal arrows,
Home, Ctrl-E, Top or End, then press Ctrl-B again to stop extending the range.
**Ctrl-A** selects everything. Once marking ends, Left/Right collapse the range
to its beginning/end; other navigation clears it and performs the requested
move. Ctrl-G or Escape clears it. Go To and a started search clear the old
range. New or a successful Open starts a new selection state.

Selected glyphs and line endings appear reversed on both displays. Selection
uses 24-bit byte boundaries and keeps CRLF together. Nonprintable imported
bytes remain exact even though they display as dots. Typing or Return replaces
the selected bytes; Del removes them. An empty mark retains ordinary typing
and backspace behavior. Replacement reserves any extra capacity before changing
the document. A refused allocation retains the original bytes and selection.
The document reuses its extent; optional undo history stores the removed bytes
separately. Memory pressure can discard history as described in the
[history contract](NATIVE-HISTORY.md).

The anchor and bounds survive Save As and the file-picker module swap. Save As
still writes the entire document. If the renderer cannot reload while a range
is active, document input waits for Ctrl-L to retry or Ctrl-G/Escape to clear
that range; typing cannot bypass it. Display-restoration failures retain the
existing pause/retry behavior. The shared clipboard exchanges selected text with Claude; clipboard
persistence across restarts remains roadmap work.

## Storage and presentation lifetime

The suite requires ABI 1.14. Its expanded core PRG contains 14,228 bytes
(10,053 packed) and reserves 96 bank-0 pages (`$6000..$bfff`).
The three checked modules share a window at `$9792`.
`EDPICK.PRG` has a 10,223-byte payload;
`EDFIND.PRG` combines search and graphics in 10,097 bytes;
`EDCLIP.PRG` provides clipboard, history replay and document launch in 2,309 bytes.
The largest module ends at `$bf81`, leaving 127 bytes before the VIC surface.
All modules bind to the core checksum and load from its original source
volume and directory. Install all four matching Editor files and `VDSVC.PRG`
together on Ultimate storage.

Files can open a selected document directly in Editor through the
[document launch contract](NATIVE-DOCUMENT-LAUNCH.md). The exact name, device,
format and IEC type are copied before transactional Open, and closing Editor
returns to the selected file. Ordinary desktop launches still start empty.

Before installing keys or initializing documents, Editor reserves and clears
16 bank-0 pages at `$5000..$5fff`. Transfer buffers, read caches and saved keys
occupy `$5000..$56ff`; the two document contexts occupy `$5700..$57ff`.
Graphics body/cache and inactive picker scratch share `$5800..$5f17`.
Document scratch uses `$5f18..$5f3e`, VDC status `$5f40..$5f68`, line offsets
`$5f69..$5f9b`, history scratch `$5f9c..$5fb4`, the retained toolbar at `$5fb5`,
and text scratch `$5fc0..$5fff`. Another owner's reservation
causes startup to refuse cleanly. This layout retains the existing 16-page
workspace while making room for the REU client in the executable.

The VIC surface reserves 36 pages at `$c000..$e3ff`; the shared VDC component
uses 39 bank-1 pages. An empty Editor has 239 free heap pages with REU screen
backing, 175 with a RAM-backed 16 KiB VDC snapshot, or 167 with a RAM-backed
64 KiB VDC snapshot. When an REU is available, documents use one resizable
extent each in the same arena as the snapshot; growth leaves those 239 main-RAM
pages free. REU documents can exceed 96 KiB. A clean optional-service refusal
keeps the 4 KiB RAM-chunk path, whose capacity depends on remaining heap and
fragmentation. Staged Open retains the old document until complete input and
CLOSE succeed, so it can need more capacity than opening after New.
A retained clipboard consumes its own bank-1 pages and handle; these free-page
figures assume an empty clipboard and history. The kernel still manages 426 heap pages. Disk-backed documents remain
roadmap work. The [shared memory contract](NATIVE-SHARED-MEMORY.md) describes
growth, ownership and the 24-bit capacity limit.

Keyboard ownership, the surface descriptor, document state, fields and query
remain in the core while picker and graphics replace one another. A missing or
invalid graphics module, or another owner's surface reservation, leaves both
text consoles usable. Ctrl-L retries after the cause is resolved. A picker
that retains a cursor or cache after failed cleanup keeps its module loaded;
new file operations wait for an explicit Browse retry. An uncertain module
source close similarly retains ownership until checked cleanup succeeds.
The VDC provider, screen backup and surface descriptor survive successful
picker swaps. Failed restoration blocks further input, transfers, replacement
and owner release. After restoration, Editor repaints the complete text view
before publishing readiness; Ctrl-L can reacquire graphics. The memory lease
keeps REU documents and the provider alive across that restore/reopen cycle.
An REU probe failure without an active VDC has its own retained recovery state
and Esc retry message. New and controlled exit explicitly dispose documents;
a failed transfer poisons its context and prevents a false successful save.

Ordinary edits repaint changed glyph cells and the old/new caret. Search
calls the renderer within its existing module invocation. Readiness is cleared
before entering a checked module call, including idle pointer polling. Closing
or replacing the graphical view restores the display and sprites before
releasing its allocation. Controlled app exit restores the original ROM key
definitions and input state.

The diagnostic disk built by `build-native.py` keeps the earlier ABI 1.7
text editor: 79 pages, a 12,443-byte core and separate 2,090-byte search module.
Its PRG bytes are unchanged. Use the module files from the same build as each
editor; suite and diagnostic modules are not interchangeable.

## Qualification

The preceding [frozen software qualification](validation/2026-09-13-native-editor-gui/README.md) passes CPU, full
mouse/keyboard VICE, large-document disk and serial workflows with independent
rebuilds. This build has not been installed or qualified on the physical C128. Tests execute the real app, kernel and modules
in CPU models and VICE, check complete bitmap/VDC surfaces and VIC palette
pixels, compare large saved files independently, and verify cleanup before
returning to the desktop.

The [VDC qualification](validation/2026-09-14-native-editor-vdc/README.md) records
complete VIC/VDC images, keyboard and mouse input, picker swaps, RAM/REU screen
backing, retained display failures, module fallback and memory-limit rollback,
with an independent rebuild and disk audit. Physical qualification of these
images remains pending.

The [REU document qualification](validation/2026-09-14-native-editor-reu-documents/README.md)
covers shared arena ownership, documents beyond 1 MiB, a 131,118-byte cold-boot
edit/save/reopen workflow, complete physical REU comparisons, RAM fallback,
retained failures and the other apps using the same provider. This software
build has not been deployed to physical hardware.

The [selection qualification](validation/2026-09-14-native-editor-selection/README.md)
covers marking, Select All, mouse dragging and edge scrolling, CRLF boundaries,
replacement and deletion, zero-free-page refusal, ranges beyond 64 KiB and
document operations beyond 1 MiB. It also checks selection across Save As,
picker swaps and renderer/display recovery, plus original module-source
loading with RAM and REU backing. Actual VICE mouse/ROM-key workflows compare
both displays, complete saved files and REU snapshots. The independent build
reproduces all 34 native program/disk images. Physical qualification remains
pending. The subsequent clipboard checkpoint adds text exchange with Claude;
the [history extension](NATIVE-HISTORY.md) adds sixteen-step undo/redo.

The [shared clipboard qualification](validation/2026-09-14-native-shared-clipboard/README.md)
records the exact software inputs, app handoffs, failure recovery and cold-boot
emulator workflows for that version. Physical deployment remains pending.

The [history qualification](validation/2026-09-14-native-editor-history/README.md)
adds Undo/Redo through keys and mouse, saved history positions, memory-pressure
recovery and large REU span replay. It includes the shared-provider regressions
and a standalone audit of the complete emulator captures.

## Printing

Ctrl-P sends the whole document to the printer on IEC device 4: a Commodore
printer, VICE's printer emulation, or the Ultimate II+'s printer emulation.
The code is in `EDCLIP.PRG` (`src/native/editor/print.inc`), so the core
grew only by its status texts and a key table. It opens logical file 121
(the kernel's file service uses 122..126) with secondary address 7, the
Commodore printers' upper/lowercase set, through the KERNAL, and restores
the KERNAL file parameters afterwards, as the file service does. ASCII
letters are sent as PETSCII; CR, LF and CR LF each end a line with CR; a tab
prints as a space; other control bytes are left out. The status line says
"printed", or "no printer" when device 4 does not answer (nothing is sent).
Esc stops between 512-byte chunks ("cancelled; document kept"); the printer
may already hold part of the document. There is no page layout, margins,
fonts or print preview, and no choice of device.

The CPU test (`tests/ci_native_editor_gui.py --case print`) checks the exact
bytes a modelled printer receives and the "no printer" path.

