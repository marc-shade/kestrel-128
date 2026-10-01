# Editor: documents beyond 64 KiB without an REU — 2026-09-27

## Problem

`ci_native_picker_gui.py --case large` had failed since `d334b47`: opening a
66,053-byte document with no REU was refused (status 3, empty document).

`d334b47` reserved the graphical Editor's workspace at bank-0 `$5000..$5fff`
(16 pages). Beside the 96-page app slot and the 36-page VIC surface, bank 0 then
has 27 free pages (`$e4..$fe`), room for one 4 KiB document chunk instead of
two. Bank 1 holds 15 after the history provider is reclaimed. Documents used
only complete 4 KiB chunks, so RAM documents stopped at 16 chunks = 65,536
bytes; the file needs 17. No layout change can fix this with 4 KiB chunks:
bank 0 needs 32 free pages for two chunks and has 27.

## Change (`DOC_PARTIAL`, enabled in the graphical Editor)

- When no complete 4 KiB run is left, the document's **last** chunk may be
  shorter. It starts at one page and **grows in place** a page at a time:
  `N_FREE` it, then `N_RESERVE` the same start one page longer. The kernel keeps
  RAM contents across free and reserve, and nothing allocates in between
  (foreground only; interrupt handlers may not allocate), so the bytes never
  move. If the next page is taken, the original range (just freed) is reserved
  again and growth is refused with `N_NOMEM`; the document is unchanged.
- Only the last chunk can be short: positions map to chunks by `P >> 12`, so
  `doc_grow` never appends after an unaligned capacity.
- The chunk's bank/page are kept in context bytes 112/113 (`D_TAILBANK`,
  `D_TAILPAGE`), previously unused.
- `doc_insert` and `doc_replace` re-check room after each growth (the clipboard
  path already did), since one growth may add a single page.
- `DOC_COMPACT` handle copies are loops, paying for the new code. The Editor's
  largest module (`EDPICK.PRG`) ends 15 bytes below `$c000`.

Placement matters: the picker caches a full D81 directory (296 entries) in
19 pages of ≤4-page blocks beside the document. An exact-fit final chunk that
stays where it was first placed leaves those blocks intact. Two rejected
alternatives, both measured: a copy-based regrow moved the chunk into the middle
of bank 1's 8-page run and the picker failed; taking the longest short run
left the picker 11 pages.

## Evidence (CPU, Py65; `physical_hardware_io` false)

Built from this commit's sources in a scratch copy (`editor.prg`
`806a6777…`, `edpick.prg` `109d0a3a…`).

| Suite | Result |
|---|---|
| `ci_native_document.py` | 8/8, including the new case `partial-final-chunk-exact-fit-refusal-and-regrowth-to-full-chunks` built with `-D DOC_PARTIAL=1 -D DOC_COMPACT=1` ([report](document.json)) |
| `ci_native_picker_gui.py --case large` | PASS: 296-entry D81 beside the edited >64 KiB document, exact cache release, verified save ([report](picker-large.json)) |
| `ci_native_editor_selection.py --case capacity` | PASS ([report](editor-selection-capacity.json)) |

The new document case pins RAM so that only an 11-page run is left, then checks
after every step that the bytes are exact (walked through the kernel's
allocation records) and that capacity is the exact page fit
(4096 + 256·⌈(length−4096)/256⌉); that a blocked growth is refused with the
bytes and state unchanged (only the re-reserved chunk's generation differs, same
slot); that edits across the boundary keep exact bytes; that with memory back
the last chunk grows to 4 KiB and the next growth appends a full chunk; and that
disposal returns every page. The default-flag model is unchanged (7/7 existing
cases pass; the default probe image is byte-identical).

Planted bugs, each caught by the intended check:

| Plant | Caught by |
|---|---|
| growth reserves two extra pages | exact-fit assertion (capacity 4,864, want 4,608) |
| refusal skips re-reserving the freed range | chunk walk finds a freed record behind a stale handle |
| `doc_grow` ignores the partial check | insert fails with a range error after appending past an unaligned capacity |

## Regression found by the full sweep: REU documents

The first version made `doc_grown` add `d_pages` instead of 16. REU documents
also reach `doc_grown`, from `dm_grow` (`src/native/editor/memory.inc`), which
did not set `d_pages`. The stale 0 meant capacity never grew, and the new
re-check loop in `doc_insert` spun: `ci_native_editor_reu_documents.py --case
large` and `--case capacity` stopped at the first typed key ("calculator did
not reach input"). `dm_grow` now sets `d_pages` to 16 (5 bytes; `EDPICK.PRG`
ends at `$bff6`, 10 bytes spare). The document suite's model build does not
enable `DOC_EXTERNAL_MEMORY`, so it could not see this path; the REU document
suite is the oracle that caught it.

With the hang fixed, the same two cases still failed, as they did on the
unchanged `ef57914` build. Their oracles predate the span history (`34bc252`),
whose REU records share owner 33 with the document:

- `capacity` counted exactly one owner-33 record after the failed Open; the
  four history spans of the typed `KEEP` are also there, as
  `docs/NATIVE-HISTORY.md` specifies (a failed Open retains history).
- `large` required every REU byte outside the document extents to be
  unchanged; the history journal writes its spans there, and released records
  keep their contents.

The test now reads the history service's own table (`bh_records`, kind 2),
checks each token against the arena record (owner 33, generation, cookie), and
requires exactly the document plus those spans (`capacity`), and that every REU
byte outside the display snapshot, the document extents and the observed
history spans is unchanged, with the `KEEP` spans actually written (`large`).

On the fixed build (`editor.prg` `dd05c31b…`, `edpick.prg` `2fe5a65b…`) all six
REU document cases pass: [capacity](reu-documents-capacity.json),
[large](reu-documents-large.json), transfer, file_close, no_vdc, probe.
Negative controls, each rejected by the updated oracle:

| Plant | Caught by |
|---|---|
| owner-33 record left behind after the failed Open | record set ≠ document + history spans |
| one REU byte flipped above every extent (`$7ffff`) | `REU changed` from `$2f000` |
| one REU byte flipped between the display snapshot and the first extent | `REU changed` `$4800..$5000` |

## Limits

- CPU-level only. Not run in VICE or on the C128 yet.
- The remaining Editor suites (history, selection, GUI, VDC, REU documents,
  clipboard) are being rerun against this build in the full sweep.
- A copy fault is impossible here (no copy); a failed restore after the free
  poisons the context.
