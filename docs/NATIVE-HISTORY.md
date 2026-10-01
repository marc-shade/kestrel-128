# Native text undo and redo

Suite Editor keeps up to **16 changes** in a session. **Ctrl-Z / Undo** restores
the preceding change; **Ctrl-Y / Redo** reapplies it. The fifth `...` toolbar page
has Undo, Redo and **Forget** and remains selected across module loads. Forget / **Ctrl-U** releases history without
changing the document or shared clipboard.

Typing, Return, backspace, selection replacement/deletion, Cut, Paste and
literal replacement use the same history. Each keystroke or replaced match is
one step; Replace All can therefore require several Undo actions. Replaying
clears selection and puts the caret after the restored span. Imported binary
bytes and CR/LF/CRLF forms remain exact. Positions and span lengths are 24-bit.
The diagnostic text Editor retains its earlier interface.

Successful Open and New start a new history. Verified Save As marks the current
history position as clean, so Undo/Redo can return to that saved state. A new
edit after Undo removes the redo branch. Evicting the oldest of 16 steps or
discarding a branch also invalidates a saved position that can no longer be
reached. This tracks edit history, rather than comparing the complete document
after every keystroke. History is volatile; session recovery remains open.

## Storage and failures

The existing checked `VDSVC.PRG` component holds the journal. It is loaded once
and records normal edits without a disk overlay load per key. Undo and Redo
replay through `EDCLIP.PRG`, which then returns to the graphical renderer.
Those module transitions still use the original app volume and directory.

Each record contains a nine-byte header followed by removed and inserted
bytes. With a shared REU lease it occupies one extent rounded to 4 KiB;
otherwise it uses one native RAM allocation rounded to 256 bytes. A complete
record must fit the available storage and descriptors. RAM records are at
most 65,280 bytes including the header; REU records can preserve spans beyond
64 KiB. The journal has 16 published slots plus one unpublished slot. Its
REU records use the existing memory owner 33 and foreground app generation;
RAM records use app owner 32.

The editor first stores removed bytes, performs the edit, then captures the
inserted bytes and publishes the record. Allocation or journal-write failure
does not silently retain an undo chain for different document contents. After
a successful unrecorded edit, it clears that chain and shows **edited; undo
unavailable**. A refused edit retains the preceding history except for the
RAM reclamation described below. If reserving a
record consumed memory needed by the edit, the editor returns that unpublished
record and retries the refused edit once.

When a RAM document in the VIC interface needs another 4 KiB chunk, it may
reclaim optional history and its provider before refusing growth. This can
also discard history during a staged Open that later fails; the existing
document bytes remain protected by transactional Open. The VDC presenter and
an active REU document lease are retained while in use. Ctrl-L, New or a
successful Open can retry an unavailable provider. Recovery initializes the
history baseline from the current dirty flag, including a document edited
while the provider was missing.

A document transfer fault retains the existing poisoned-document behavior:
further editing and Save As refuse uncertain bytes. Failed history frees
retain their tokens for retry; controlled exit releases history before ending
the document lease and unloading the component. Closing/restoring only the
display does not discard the journal. Clipboard contents have their own
session lifetime.

## Component interface

This is version 1 of the internal foreground span-journal interface, defined in
[`history-api.inc`](../src/native/history-api.inc). Call directly through
`bk_call`; automatic display-status reads would overwrite the payload.
The checked executor preserves its owner, generation, mapping and interrupt
rules. Calls return the native A/carry result and do not change file arguments.

| Operation | Contract |
|---|---|
| 15 Info | `N_BUFFER[0..3]` = dirty, undo count, redo count, version 1 |
| 16 Begin | Header in `N_BUFFER`: position, removed length, inserted length, each LE24; allocate an unpublished record |
| 17 Append | Store the next removed/inserted bytes; `H_COUNT` (`$3d0a`) is 1–512 |
| 18 Seal | Require the complete record; trim redo/oldest history, then publish |
| 19 Abort | Cancel preparation/replay and retry release of an unpublished token |
| 20 Undo / 21 Redo | Prepare a replay; return its position, removal and insertion lengths in the same header format |
| 22 Read | Return the next 1–512 replacement bytes in `N_BUFFER` |
| 23 Applied | Require complete replay consumption, then advance the history position; return Info |
| 24 Clear | Release history; `N_BUFFER[0]` sets the new baseline's dirty flag |
| 25 Save | Mark the current history position clean; refuse an unfinished record/replay |
| 26 Close | Release all history, retaining any failed token; must succeed before component unload |

Only the caller edits the document. An unsuccessful replay must Abort without
advancing history; a transfer failure during document mutation must poison
the document. An incomplete record cannot be sealed. Partial cleanup failure
invalidates the published list while retaining every remaining token, and
Begin retries those inactive allocations before accepting another record.

## Software checks

`tests/ci_native_history.py` executes the shipped provider against an independent
byte-edit model, including 16-step eviction, saved positions, redo branching,
unpublished records, allocation/transfer failures, retained free retry and a
131,119-byte span crossing 64 KiB. `tests/ci_native_editor_history.py` drives
the actual editor, checked modules, files, keyboard and mouse. It covers both
displays, large REU documents, memory pressure, recovery and poisoned-transfer
refusal. These software checks do not constitute physical qualification.

The [history qualification record](validation/2026-09-14-native-editor-history/README.md)
binds the executed test versions and emulator captures to the exact program
images. Its standalone verifier checks document/history bytes, display frames,
saved files, allocation cleanup and the independent rebuild.
