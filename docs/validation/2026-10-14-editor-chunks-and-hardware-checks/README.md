# Editor document chunks of 1 to 16 pages, and new hardware checks (2026-10-14)

## Why

The [80-column performance record](../2026-10-13-80-column-performance/README.md)
left one fragile case: the graphical Editor opening a 66,053-byte document
beside a full 296-entry D81 picker (`ci_native_picker_gui --case large`)
passed or failed with the size of the resident VDC service. At 31 pages it
passed; padded to 32, Open failed with 26 pages still free, in runs of 15 and
11. Positions mapped to 4 KiB chunks by P >> 12, so only the last chunk could
be short and every other free run lost its size mod 16 pages. The document
needs 259 pages: 16 chunks of 4 KiB and a 3-page chunk.

The owner also asked for hardware checks of the apps that were verified only
in emulators, and for a hardware timing of the 80-column pointer.

## Change

`document.inc` with `DOC_PARTIAL` (the graphical Editor) (6806b13):

- Each chunk holds 1 to 16 pages; the context records them as one nibble per
  chunk (bytes 114 to 125) and counts the leading 16-page chunks (byte 126).
- `doc_locate` maps a position through those leading chunks by P >> 12, as
  before, and walks the sizes of the rest. The forward and backward transfer
  limits stop at the real chunk boundary. A shared REU extent has none.
- A short last chunk still grows in place a page at a time. When the page
  after it is taken, it is reserved again unchanged and a new chunk follows
  it in another free run, so no free page is lost to alignment. Growth is
  refused only when no free page or no chunk slot is left.
- In the compact build the 3-byte context load and store macros call shared
  subroutines for transient variables, which pays for the new code: the
  Editor core is 91 bytes smaller than before.

The text editor and Paint do not use `DOC_PARTIAL` and are unchanged.

## Results

`ci_native_picker_gui --case large`, with the VDC service padded:

| VDC service pages | Before | After |
|---:|---|---|
| 31 (shipped) | pass | pass |
| 32 | fail | pass |
| 33 | fail | pass |
| 34 | fail | pass |
| 35 | fail | pass |

Editor main-RAM capacity (`ci_native_vdc_editor_capacity`): 37,120 to 39,680
bytes with a 64 KiB VDC, 38,912 to 41,728 bytes with 16 KiB.

Cost: moving the gap across a 66,053-byte, 17-chunk document took 0.2 to 1.0%
more instructions in Py65 than with fixed 4 KiB chunks. The Editor hover
benchmark changed by 28 cycles.

## New hardware checks

Each has a VICE or Py65 twin in the sweeps that runs the same workflow:

- `--native-apps` (83a2b19): Paint keyboard edits and discard, the Claude
  landing page and clean return without a connection, the Ultimate controls
  Drives page against the REST drive list, and a Sheet Save As to an empty
  drive B whose retrieved image must hold exactly the expected workbook.
- `--native-gem` and `--native-aes` (1a636a0): GEMDESK's keyboard workflow on
  drives A and B in 1581 mode (the standalone hardware script now follows the
  VICE sequence it had drifted from), and the AES demo's 40-column alert,
  menu and window tests.
- `--native-pointer-timing` (405a05c): a measurement-only build, never
  shipped, moves the pointer itself over empty desktop space through the
  shipped 1351 path and times 512 pointer-only updates with CIA2 timer B. In
  Py65 every timed record equals the shipped code's cycles. In VICE the
  service's redraw averaged 16,386 cycles and the whole bank call 19,382,
  none under one 17,045-cycle frame; VICE's 8563 timing is approximate.

## Gates

- 451bfe5 (chunks): CPU sweep 323/323.
- 405a05c (chunks and the new checks): CPU sweep 324/324, VICE sweep 64/64.
- `ci_native_document` gains a case with chunks below 4 KiB in three
  separate runs, edits across their boundaries and growth after RAM returns,
  and checks the size nibbles and the leading-chunk count against the
  kernel's allocation records. A build that never counts leading chunks
  fails it, and so did a register clobber found while writing it.

## Not verified

- None of the new hardware checks has run on the C128 yet; their runtimes
  are estimates.
- The large picker case at 30 pages (not reachable by padding) and at 36 (the
  padded build no longer fits the test disk image).
- Whether the real C128 moves the 80-column pointer at 60 Hz.
