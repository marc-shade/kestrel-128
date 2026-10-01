# Native blue Editor

The suite Editor now carries the desktop's blue bitmap, yellow focus and
1351 controls into document editing, file dialogs, Find/Replace and byte
positioning. Clicking the document places the caret; Tab moves between
controls and Enter activates them. Browse/F7 opens the shared text picker and
returns to the blue dialog with the complete document and field retained.
Closing the app returns to the blue desktop with Editor selected.

This local software checkpoint is based on
`8d2086c3ff088480247c98567dab88ee571425e9`. No physical hardware I/O or push was
performed. The installed machine and historical physical qualification are
unchanged. Terminal framing, the graphical shared picker and VDC presentation,
selection/clipboard/undo, session recovery, styled documents and the broader
OS roadmap remain open.

## Implementation and memory

The Editor core owns the document, query, fields, keyboard state and surface
descriptor. Search and graphics share `EDFIND.PRG`; the picker uses
`EDPICK.PRG` in the same checked window. Modules load from the original app's
device/context and folder even after changing document storage. Search calls
its renderer directly within the outer module invocation. Readiness is cleared
before every checked module call, including idle pointer sampling.

The core contains 13,126 bytes and declares 96 bank-0 app pages. Its window
starts at `$9346`: the picker contains 7,737 bytes and search plus graphics
contains 11,357 bytes. Both modules bind to the core's checksum. Peak core plus
graphics is 24,483 bytes, within the 24,576-byte allocation. The optional bitmap
reserves 36 pages at `$c000..$e3ff`. The suite requires ABI 1.10 and ships with
the unchanged ABI 1.11 kernel and 426-page heap.

Ordinary edits repaint changed glyphs and the old/new caret. Mouse caret
placement uses retained 24-bit line offsets, accounts for horizontal scrolling,
clamps to line ends and respects CRLF boundaries. The graphical field displays
38 cells while preserving the full 255-byte Ultimate path and caret. Only
Cancel remains enabled during I/O; write and reopened verification have
separate captions. Cancelling a save preserves the document's dirty state and
name and leaves only the newly created file's written bytes.

Failed picker aborts retain their code and descriptors and prevent new file
operations. Explicit Browse retry releases those resources before graphics
reloads. An uncertain module-source close similarly blocks file work until
checked cleanup succeeds. Missing/damaged graphics or another owner's surface
reservation leave both text consoles usable; Ctrl-L retries graphics after the
cause is resolved. Controlled exit restores display, sprites, key definitions,
input state and app-owned resources.

The diagnostic editor retains its earlier ABI 1.7 text build: 79 pages,
12,443 core bytes and a 2,090-byte search module. Its PRGs are byte-identical.
Install matching core/picker/search files together; the diagnostic and suite
modules are bound to different cores.

## Qualification

- Thirteen final graphical CPU groups pass keyboard/mouse editing, literal
  search and replacement, picker replacement, a document above 64 KiB,
  missing/corrupt modules, text fallback/retry, long paths, original Ultimate
  module-source routing, retained picker and source-close failures, foreign
  surface ownership, and mouse cancellation during writing and verification.
  Both cancellation cases check the complete busy bitmap at four transfer
  boundaries. Every observed graphical module call has readiness cleared.
- Five existing editor/document suites pass on the unchanged diagnostic
  binaries. The qualification bundle contains 18 named runs and
  58 groups. Two completed diagnostic runs are retained from the v7
  batch; the other three and all graphical groups complete in the final v8
  batch. Each qualifying test process reaches terminal exit zero.
- Full mouse workflows pass from both 40- and 80-column boot defaults across
  Calculator, Editor, Files, Ultimate, Claude and Paint. The complete
  keyboard-only suite also passes. The offline auditor checks 158
  complete 320x200 palette frames (10,112,000 pixels), including
  32 Editor frames, plus 36 Editor bitmap/VDC
  pairs across all workflows. Each mouse run creates and independently checks
  an editor note of 10 bytes, calculator history, a raw PRG copy and a Paint
  document while preserving every shipped disk file.
- A separate real-1581 workflow reads mixed newlines and binary bytes, opens
  66,053 bytes, inserts four bytes beyond offset 65,536 and verifies the
  resulting 66,057-byte file on another D81. It checks all seventeen document
  chunks across both RAM banks while the picker is open, refuses the existing
  output, and reopens the saved document. An independent disk export and an
  offline D81 sector-chain reader both match every saved byte. Six complete
  captured documents are reconstructed independently from raw handles, chunks
  and gap-buffer state. Source D81 and system D64 remain byte-identical.
- The shared desktop/Ultimate/Claude workflow passes two actual TCP/PTY
  lifetimes: acknowledged F8 and host exit. Shutdown is observed before
  `native_video_end` while Claude still owns its allocation. Font, NMI and
  gate bytes match afterward; both host processes exit normally. This workflow
  also checks the Editor and Files bitmap/VDC presentations.
- Final cleanup restores the resident code and ROM input state and frees all
  426 heap pages. The raw audit accepts 1,650 captures, 5,391 chunks,
  2,499,274 payload bytes and 6,600 matching borrower pairs. No rejected
  or interrupted observation supplies passing evidence.

The input archive contains 487 files. Independent frozen and main rebuilds
reproduce all 24 native PRG/D64 images exactly. Relative to the baseline, only
the suite editor core, its two bound modules and the two suite D64s change.
Both kernels and every other app PRG are byte-identical. The auditor checks
archive manifests, module binding, complete disk contents, all recorded app
frames, raw captures, banked documents, input restoration, resident code and
live serial shutdown.

## Retained development failures and limits

`preliminary.tar.gz` retains earlier source/image snapshots, build/test logs
and raw emulator evidence, including nonzero and interrupted runs. Early
builds failed the assembler's expression/size guards. Replacing a full old
screen copy with a cache of only displayed glyph cells made the renderer fit
below the surface range. An early VDC oracle incorrectly expected uppercase
footer text; it now checks the actual title-case labels independently. A
forward-search mouse fixture initially expected an earlier X even though a
later X existed after the caret; the final check verifies that later match
and records the actual cursor state.

A retained-picker failure exposed a real recovery defect: after successful
cleanup, the earlier failed graphics attempt prevented automatic reload. The
final Browse return clears that attempt flag and retries the checked module;
the same retained-cursor test then passes with the document intact. The
write-to-verification transition also repaints its changed caption.

The v7 full 40-column host and the combined CPU host ended with status 143;
their incomplete runs are retained and excluded. No initiating cause is
established. Final long-running hosts use a bounded supervisor that records
the actual test process's terminal result; all final supervisors observe zero.
Two early v8 mouse runs stopped at the key-count assertion. The old host wait
could accept a preexisting idle state before GTK delivered the new key. The
final runner waits for a changed ROM input counter, then still requires exactly
one consumed key and records both counter values; missing or duplicate input
continues to fail. The app images are unchanged by this host correction.
The v7 80-column, keyboard, large-document and serial passes remain development
evidence rather than substituting for the final suite-image runs.

Styled documents and printing remain future work, alongside REU/disk document
backing, a graphical VDC editor, clipboard,
undo or persistent session recovery. Physical native testing still needs the
qualified bank-aware high-RAM diagnostic and a transport-specific live Claude
shutdown observer. The shared picker remains text during this migration.
Historical sealed records are unchanged.

## Recheck

Run `python3 -B verify.py` here for the offline archive, frame, document and
lifecycle audit. `SHA256SUMS` seals every other file in this directory.
`rebuild.py` records the two build comparisons and refuses to write a sealed
record. The screenshots show the tested desktop, Editor and Save As dialog;
complete surfaces and palette readbacks provide the pixel checks.
