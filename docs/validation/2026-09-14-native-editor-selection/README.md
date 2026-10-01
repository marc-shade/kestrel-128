# Native Editor text selection — 2026-09-14

This checkpoint adds keyboard and mouse text selection to the blue suite
Editor on both displays. Ctrl-B starts/ends marking, Ctrl-A selects all and
Ctrl-G/Escape clears the selection. The third toolbar page provides Mark, All
and Clear. Typing/Return replaces selected bytes; Del removes them. Ranges use
24-bit byte boundaries and keep CRLF pairs together. See the
[Editor guide](../../NATIVE-EDITOR-GUI.md) for controls and memory layout.

The parent is signed commit `b48888816a32f02ece57f224563ed3edb853a1c2`.
The preceding clock record's seal is
`5444a34964fcb167a9457695453ddb194e7f5af4caebc8eb21afc9cd7653ed70`.
This record contains software evidence. Physical C128 installation and
qualification are pending; clipboard exchange and Editor undo remain open.

## Checks

* 22 successful CPU jobs cover 25 cases: keyboard marking/collapse, Select All,
  toolbar controls, CRLF replacement, empty marking, mouse drag and edge
  scrolling, held-drag cancellation by keys, selection beyond 64 KiB, and
  complete removal of a document larger than 128 KiB. A separate document-engine
  workflow uses spans beyond 1 MiB, validates out-of-range refusal and checks
  two contexts with randomized replacements.
* At zero free heap pages, failed growth preserves document state and selected
  bytes; replacement that fits existing storage and full removal still work.
  Save As retains selection and saves all bytes. Picker swaps, missing-renderer
  retry, display faults, workspace refusals, search and original USB source
  recovery retain their documented state and ownership.
* Actual VICE ROM keyboard and 1351 input run from a VIC startup with a 16 KiB
  VDC, RAM documents and separate D64 data disk, and from a VDC startup with
  64 KiB VDC RAM, 512 KiB REU and D81. Both verify selection and replacement,
  Save As, picker round trips, search, display restoration and desktop return.
  The D81 workflow opens 131,113 bytes, inserts beyond 96 KiB, saves and reopens
  131,118 bytes, and compares complete REU snapshots including unrelated bytes.
* A clean independent rebuild reproduces 34 program/disk images. The offline
  verifier checks packed app CRCs, module binding/extent, six disk directories,
  allocation chains and BAMs, saved files, VIC/VDC capture pixels and restored
  observer scratch. The suite leaves 118 free D64 blocks or 2,614 D81 blocks.

All qualified runs use identical runtime sources and program/disk bytes.
Execution manifests retain the actual test-script versions. Test-only fixes
account for the optional provider's separate REU probe, aim the mouse at a
character's center rather than a boundary within its motion tolerance, and
restrict the input-loop checkpoint to Editor's bank-0 MMU map. The same numeric
address is used by a bank-1 REU transfer routine; stopping there slowed file
verification. Earlier development failures and superseded runs are retained
in `development.tar.gz` and are not counted as successful qualification.

## Recheck the record

Run `python3 -B verify.py` in this directory. It needs only Python's standard
library and these archives. `audit.json` stores the completed audit counts;
`SHA256SUMS` seals every record file. The audit verifies 70 display canvases
(6,720,000 pixels), 810 restored capture operations and nine complete REU
document snapshots. The input archive contains the source and
built images; the execution manifests and content-addressed blobs reconstruct
each qualified tree. Job statuses include commands, working directories,
process IDs, exit codes and timestamps. The output archive includes private
VICE disks, complete captures, REU snapshots and reports. System ROM bytes are
not redistributed; their fingerprint and tool versions are in `provenance.json`.

The runtime remains a foreground app with a fixed module window. The renderer
ends at `$bff5`, leaving eleven bytes before the VIC surface at `$c000`.
Selection adds no new heap allocation. Shared clipboard, undo, scheduling,
expanded display modes and physical expansion-device evidence remain on the
[completion roadmap](../../IMPLEMENTATION-ROADMAP.md).
