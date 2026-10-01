# Native shared text clipboard

The blue Editor, Claude and Sheet apps exchange text through one session clipboard.
It survives app exits and returns to the launcher or diagnostic workspace.
Restarting the native kernel clears it. Clipboard bytes stay in managed RAM;
no disk file, serial port or Ultimate configuration is changed by Copy.

## Controls

In Editor, **Ctrl-C** copies the selected bytes, **Ctrl-X** copies and removes
them, and **Ctrl-V** inserts the clipboard at the caret or replaces a selection.
The fourth **...** toolbar page provides Copy, Cut and Paste. **Ctrl-K** clears
the clipboard and releases its memory. Copy/Cut require a nonempty selection.
Save As still saves the whole document; New leaves the clipboard available.

In a connected Claude session, open local controls with **Ctrl-Help** or the
right mouse button. The first two buttons become **Copy** and **Paste**.
Ctrl-C/Ctrl-V invoke them while local controls are open. Ordinary terminal
keys retain their existing meaning outside local controls.

Claude Copy exports all 25 retained terminal rows, including columns outside
the current VIC view. Each row has 80 cells followed by LF. The suite bridge's
glyph map supplies ASCII characters; other cells become question marks.
Colors, attributes and arbitrary glyph artwork are not preserved. This
operation requires the retained terminal allocation.

Claude Paste negotiates support with the bridge, sends bounded packets and
waits for an acknowledgement. The bridge validates the complete item before
queuing a standard bracketed paste, without a trailing Return. Printable
ASCII, tab and CR/LF are supported; CRLF and CR become LF. Other control bytes,
ESC and non-ASCII bytes are rejected before terminal delivery. The
acknowledgement means the bridge accepted input, not that Claude has processed
or saved it. Escape cancels a transfer before its final packet. Once that
packet has been sent, an absent acknowledgement is reported as unconfirmed;
the client never retries the paste automatically. An older bridge leaves the
clipboard untouched and reports that an update is needed.

## Sheet cells

Sheet uses Ctrl-C/ Ctrl-X/ Ctrl-V outside field editing and dialogs to copy,
cut or replace one cell's complete ASCII source. It accepts 1–31 printable
bytes, rejects other clipboard items without truncation, and recalculates
formulas after Paste. Cut publishes before clearing. Empty Copy/Cut preserves
the old item, and Undo restores a changed cell. Formula references stay literal;
range operations and relative-reference rewriting remain open. Its checked
`SHCLIP.PRG` module shares the calculation/font window and uses the same
owner-31 session provider as Editor and Claude.

## RAM and lifetime

The initial provider stores up to **15 KiB** in one bank-1 allocation. A new
copy needs a second allocation until publication succeeds. Allocation scans
only bank-1 pages `$04..$5f` and `$c0..$fe`, leaving the fixed banked component
window free. The 15 KiB limit lets an item fit in the upper region even when
documents or display snapshots occupy lower memory. Fragmentation, live
allocations and exhausted handle slots can still refuse Copy or Paste.

Clipboard allocations use reserved owner **31**, independently of foreground
app owner 32 and workspace owner 16. Only the shared clipboard library may
allocate or release owner-31 memory. Native ABI **1.13** initializes 27
previously reserved session bytes at `$3de5..$3dff`. Existing entry addresses,
resident code intervals and all 426 managed heap pages are unchanged. The
service is a shared source library included in each client; it adds no
resident jump-table entry.

A copy writes an unpublished extent sequentially through checked 1–512-byte
heap transfers. Commit requires the entire declared length and the creating
app's allocation generation. It frees the previous item only after staging
completes. A failed allocation, incomplete write or failed publication keeps
the old clipboard. A transfer error poisons the draft. Begin, Abort and Clear
can reclaim an abandoned draft from an earlier app; uncertain frees retain
their tokens for retry. A publication sequence never wraps.

Editor uses a third checked module, `EDCLIP.PRG`, in the same window as its
picker and renderer. Its document and selection state remain in the core.
Paste reserves document growth before removing logical bytes. Allocation
failure keeps document bytes, caret and selection; already acquired capacity
may remain attached to the document. As with other Editor memory operations,
an uncertain transfer poisons the context and prevents Save As from reporting
success. Cut publishes a recoverable copy before removing the selected span.

Claude stores the original VDC font in a separate owned 4 KiB allocation,
retained until font restoration succeeds. This frees app code space for the
clipboard library while preserving font and display cleanup. Its current
terminal font and original font have separate lifetimes.

## Protocol and SDK

Include [clipboard.inc](../src/native/clipboard.inc) once in a foreground app
or checked module and use the contracts in
[clipboard-api.inc](../src/native/clipboard-api.inc). Info/Begin use a 24-bit
length; Read uses a 24-bit offset; transfers use the full `N_BUFFER` and a
16-bit count. Begin, Write, Commit, Abort, Clear, Info and Read preserve D/I and
return native A/carry results. They require enabled interrupts, the standard
bank-0 mapping and a running app. Heap mailboxes are scratch; file mailboxes
remain separate. Session metadata is private to the library.

The optional Claude extension is documented in
[protocol.py](../apps/claude/host/protocol.py): capability request 4, chunk 5,
begin 6, end 7 and abort 8 follow the existing zero-byte control escape.
Begin carries a two-byte length; each chunk carries a byte count and at most
64 literal bytes. Credits may occur between packets. Host capabilities and
paste results use opcodes 13 and 14. Legacy clients do not request the
extension, so they receive no new opcodes. The host's protocol bound is
16 KiB; the current RAM clipboard's bound is 15 KiB.

REU-backed scraps, image formats, terminal scrollback selection, grouped Editor undo,
persistence across restarts and physical C128 qualification remain on the
[roadmap](IMPLEMENTATION-ROADMAP.md).

The [shared clipboard qualification](validation/2026-09-14-native-shared-clipboard/README.md)
records the exact software inputs, app handoffs, failure recovery and cold-boot
emulator workflows for this version. Physical deployment remains pending.
