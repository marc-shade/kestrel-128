# Native focused text fields (ABI 1.6)

The editor, Files and Apps browser, and calculator share bounded field editing
and drawing in the native kernel. Open, Save As, path, byte-offset and device
prompts use the same caret keys. The [field checkpoint](validation/2026-09-10-native-fields/README.md)
passes twenty CPU suites, all ten native emulator workflows and complete physical
USB/IEC qualification. Independent readback verifies the saved files and the
66,056-byte document retained while the picker has focus.

| Key in a field | Action |
|---|---|
| Left / Right | Move one byte, bounded by the field ends |
| Home or Ctrl-A / Ctrl-E | Beginning / end |
| Printable character | Insert before the caret |
| Del / Ctrl-D | Delete before / at the caret |
| Ctrl-U | Clear the field |
| Ins | Insert a space when the field's filter permits it |
| Enter / Esc | The application accepts / cancels the prompt |

The reversed cell marks the caret. Each display keeps its own viewport and
shows `<` or `>` at an edge when text is clipped. A long field can be edited
in the middle without deleting its tail. The full value remains separate from
its screen representation. Tab still opens the editor's picker or changes the
browser's DOS context. Cancelling the picker preserves all eight field-state
bytes, including the caret and both viewports, together with the document.
A successful selection initializes the caret at the selected name's end.

## Calls and ownership

[`api.inc`](../src/native/api.inc) exports `N_FEDIT` at `$1c59` and `N_FDRAW`
at `$1c5c`. Existing entries keep their addresses. Apps using these calls must
require minor version 6 in their manifest. All three supplied apps do so.

Both calls require the normal native bank-0 mapping, a running foreground app
and enabled IRQs. They return C clear/A zero on success, or C set/A equal to
`N_UIERROR` on error. D/I are preserved; A/X/Y are otherwise scratch. Drawing
uses the native console's PLOT and CHROUT and leaves reverse and quote mode
off. It does not borrow a caller zero-page pointer. Console ROM scratch and
cursor state follow the normal KERNAL contract.

`N_UIPTR` (`$3d35`, little-endian word) points to this eight-byte record:

| Offset | Size | Value |
|---|---|---|
| 0 | 1 | Current length, 0..maximum |
| 1 | 1 | Caret offset, 0..length |
| 2 | 1 | Maximum length, 1..255 |
| 3 | 2 | Buffer pointer; reserve maximum+1 bytes |
| 5 | 1 | 40-column viewport offset |
| 6 | 1 | 80-column viewport offset |
| 7 | 1 | Filter: 0 printable, 1 decimal, 2 hexadecimal, 3 IEC filename |

The record and complete reserved buffer must be disjoint and lie in the
running app's original bank-0 allocation at `$6000`. Extra heap allocations
are not accepted as field storage. Validation checks the allocation's owner,
bank, base, page count, all three generation bytes and every touched page tag
before writing caller storage. The loader retains the app's memory handle
separately from its closed source-file handle; their generations can diverge
across repeated IEC/Ultimate launches.

Error values are 1 invalid state/draw arguments, 4 invalid or stale allocation,
5 no running app owner, 6 range outside the app, 7 reentrant/busy service and
8 disabled IRQs. Rejected operations leave the field record and text intact.
`N_UIFLAGS` is meaningful only after success. These services allocate no heap
memory, poll no input and perform no file or document I/O.

## Editing and drawing

Set `N_UIKEY` (`$3d37`) and call `N_FEDIT`. Key zero initializes a record after
the app replaces its value: caret becomes length, both views become zero and
the buffer receives a zero terminator at length. Other calls use the key table
above. `N_UIFLAGS` (`$3d39`) bit 0 means content changed and bit 1 means the
caret moved. Key-zero initialization returns flags zero. Ignored keys and
insertion at maximum length succeed without changes. The app handles modal
actions such as Enter, Esc and Tab before passing editing keys to the service.

Printable input is `$20..$7e`. Decimal accepts `0..9`; hexadecimal also accepts
`A..F`, converting lowercase hex input to uppercase. IEC filenames additionally
reject `* ? , : / \\ @ # $`. Filters apply to inserted bytes. Existing raw bytes
are preserved and displayed as dots if they are outside the printable range.
The length is authoritative; drawing never treats embedded NUL as a terminator.

Position the current console with PLOT, set `N_UIWIDTH` (`$3d38`) to 3..79 and
call `N_FDRAW`. Width includes two edge cells and the inner caret cell. The
rectangle is one row and must end before the display's final column; invalid
rows, widths or wrapping positions are rejected before output. Only the
current display is drawn, and its viewport is adjusted to keep the caret in
view. The other display's viewport remains intact. Drawing emits exactly
width printable cells and three reverse controls, leaving normal video active.
It never wraps, clears the screen or redraws document rows.

The editor still paints its complete status row when a field changes. Across
both displays this is at most 118 printable cells plus six caret controls.
No document reads or line searches are required, including beyond 64 KiB.
Selection, clipboard, undo, pointer focus, a shared event queue and general
graphical widgets remain work in the [completion roadmap](IMPLEMENTATION-ROADMAP.md).

## Memory and checks

The kernel PRG is 15,361 bytes. Startup relocates eight pages from
`$5000..$57ff` to `$1300..$1aff`, then returns all staging pages to the heap.
The heap remains 426 pages. Calculator, browser and editor allocations remain
16, 28 and 79 pages, respectively. Shared controls fit without increasing the
editor's allocation or changing the banked document model.

`tests/ci_native_fields.py` executes the assembled calls with all key values,
deterministic edit sequences, full 255-byte buffers, both viewports, raw bytes,
screen boundaries, ownership failures and atomic rejection. App regressions
cover real dispatcher replacement, middle edits and verified saves. The field
app suite retains a 66,056-byte document and both workspace blocks through a
full path edit and picker cancellation.

The complete archive audits 192 frame pairs, 1,034 CPU captures and 2,459 IRQ
capture chunks across emulator and physical runs. All five captures of the
66,056-byte document while its picker has focus match, and the field record
survives cancellation exactly. Physical USB and IEC each restore the deployed
desktop, saved settings and other drives. Four USB DMA observations disagree
with CPU RAM; three match separate BASIC ROMs, while two bytes remain unexplained.
The raw observations are retained and CPU captures remain the RAM authority.

The initial IEC boot failed because cartridge uploads were incomplete. The
[recovery audit](validation/2026-09-10-native-fields/BOOT-UPLOAD-RECOVERY.md)
retains that failure and verifies restoration. The new IEC harness checks stored
upload sizes, reserves a byte-verified loader before disk switching and reuses
the original system image for restoration. It removes its temporary files after
independent disk readback. All 24 host transport/upload/restoration fault checks
pass without hardware I/O.

Physical IEC covers Ultimate-emulated 1541 drives on devices 8 and 9; D71 and
D81 coverage here is emulator evidence. The 66,053-byte IEC Open took 289.894 s,
verified 66,056-byte Save As 537.495 s, and reopen 295.981 s. These include quiet
intervals and host monitoring. Burst transfers, native 2 MHz regions, broader
device certification and the graphical desktop remain separate work.
