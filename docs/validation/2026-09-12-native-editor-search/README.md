# Native editor search and replace — 2026-09-12

This checkpoint adds Ctrl-F Find, Ctrl-N Find Next and Ctrl-R Replace to the
native editor included on both uOS suite disks. Queries and replacements accept
up to 64 printable bytes. Tab selects exact case or ASCII case folding. Find
wraps and permits overlapping matches; Replace All processes non-overlapping
original occurrences and never scans inserted replacement text. Empty
replacements delete matches. Esc stops at a polling point, with completed
replacements retained and counted. A failed allocation preserves the next
original match; a failed memory transfer poisons the document.

`EDFIND.PRG` and `EDPICK.PRG` share the editor's reserved module window. Each
module is bound to the core CRC. The accepted query and case setting remain in
the core across module switches. Failed loads and stale calls report an error
and can be retried. The picker stays loaded if failed cleanup retains a cursor
or cache handle, keeping those descriptors available for a retry.

The editor still reserves 79 pages. Its core PRG is 12,445 bytes, its picker
PRG is 7,739 bytes and its search PRG is 2,092 bytes, including load addresses.
Saving reuses the insertion buffer for reopen comparison. The picker borrows
three independent 512-byte buffers and uses partial final allocations for its
remaining cache. A document beyond 64 KiB and both 8 KiB workspace buffers fit
alongside the picker, including both transactional Ultimate directory pages.
The bank-0 workspace remains at `$df00..$feff`.

The eight CPU groups cover 81 named cases plus 1,086 complete redraw frames.
They include random byte-array comparisons, IRQs, 512-byte/4-KiB/64-KiB
boundaries, repeated-prefix search, allocation and transfer failures, partial
cancellation, exact saved bytes, both Ultimate contexts, module retries,
retained-resource cleanup, 296-entry IEC directories and paging beyond 255
Ultimate entries. The physical-cache decoder is tested against the executed
picker's RAM in a CPU model; that test does not access hardware.

VICE executes the actual C128 ROM input and output paths with true drive
emulation. The search workflow checks 23 editor frame pairs, saves and
independently exports 66,058 bytes from a D81, reopens and searches the saved
file, and reconstructs every document extent while the picker has focus.
The five-app workflow exercises Calculator, Editor, Files, Ultimate and two
Claude lifetimes. Both return all 426 heap pages. These runs contain 300 CPU
captures, 780 chunks, 328,414 copied bytes and 1,200 matching before/after
borrower checks, with no rejected captures. Claude uses the existing fixture
PTY; no authenticated Claude session is claimed.

The first built-in search prototype used 90 app pages and failed to open the
large file in VICE while both workspaces were live. Total free RAM was
insufficiently contiguous for another 4 KiB document extent. Its failed run,
images and changed source are retained under `preliminary/`. The module design
restores the original allocation. Other development fixture/decoder corrections
are described in `provenance.json`; their partial runs are not counted above.

`inputs/` freezes 401 source, helper, reference and generated files. The main
checkout rebuilt all 21 native PRG/D64 images byte for byte. Both kernels and
all other application PRGs match the signed base commit
`e140f3aae5ce1ca304654549ba74191ccd61f82c`. The editor core and both modules must
be installed together; both suite disks include all three.

Run `python3 -B verify.py` for the sealed offline audit. It checks every archive
hash, frozen inputs, both module bindings, packaged disk entries, CPU reports,
capture chunks and borrower restoration, complete editor screens, document
extents, exported bytes, suite return state and the retained negative result.
`main-rebuild.json` records the exact integration comparison.

No physical C128 operation, modem setting change, deployment or push occurred
for this checkpoint. Physical search qualification remains open. The broader
uOS roadmap still includes selection, clipboard, undo, graphical editor
controls, word processing, expansion drivers and the remaining desktop work.
