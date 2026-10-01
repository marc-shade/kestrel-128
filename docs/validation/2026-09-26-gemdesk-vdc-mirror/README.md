# GEMDESK 80-column mirror — 2026-09-26/27

Begun 2026-09-26 in another session (uncommitted there); completed and verified
2026-09-27 on `goal/complete-uos`.

## What changed

GEMDESK now mirrors its desktop to the 80-column screen through the shared VDC
service (`VDSVC.PRG`, `BP_MODE` 0: the 320×200 VIC surface doubled to
640×200), as Calculator, Files, Editor and the other native apps do. The
design is in [GEM-LAYER-DESIGN](../../GEM-LAYER-DESIGN.md) ("Dual monitors").

- GEMDESK opens the mirror once the AES has drawn the desktop. Without the
  component, or if it cannot open, GEMDESK runs on the VIC alone.
- **Rows are presented only when they change:**
  - GEMDESK's own drawing marks rows through the graphics library;
  - window calls OR the rows the AES reports (reply bytes 4..7) into
    `ae_dirty`, and alerts do the same with theirs (bytes 2..5);
  - `ae_present` converts `ae_dirty` into the mirror's row flags and presents.
- **Hooks:** the AES client calls `ae_present` (new option `AE_MIRROR`) when
  a sample reports redrawn rows but no event, as with menus opening and
  closing. The forms library calls it once per dialog-loop pass (new
  `FO_PRESENT`).
- **Closing a form** restores its background with a raw copy the graphics
  core never sees, so `fo_close` now marks the form's rows itself
  (`fo_mark_rows`). Without this the VDC kept the closed dialog.
- **Idle input wait** (`ae_event_wait` in `aes-client.inc`):
  - Between samples the AES client stays at its input wait with `N_READY`
    published. It samples again only on a key, a jiffy tick, a keyboard click
    still counting, or a completed 1351 read (it drives the pointer module's
    two-phase read itself).
  - An app supplying its own pointer (`AE_POINTER` 0) also samples when
    `ae_pointer_*` change.
  - GEMDESK's alert loop uses the same wait (`ae_read_pointer` is shared).
  - Before this, each pass made a banked AES call, and GEMDESK was at its input
    wait 2% of the time on the C128. That starved anything that needs the
    foreground idle, including the held VDC capture.
- Every path that leaves GEMDESK closes the mirror before the pointer
  (`gm_leave`), which restores the 80-column screen.
- **Space:**
  - Show Info on USB entries moved from the core into the GDSET module
    (module operation 5).
  - `aes-client.inc` now sits in the slack before GEMDESK's page-aligned path
    table.
  - GDDLG ends at `$bf90`, GDSET at `$bfb2`.

## Evidence

Build: `gemdesk.prg` `725783228e19…` (identical in the branch build and the
hardware image).

CPU (Py65, `physical_hardware_io` false):

| Suite | Result |
|---|---|
| `ci_native_gemdesk.py` | 45/45, including the mirror case: startup, window, dialog, dialog closed, menu, menu closed, alert and alert closed match the VIC surface byte for byte on the VDC, and launching restores the VDC ([report](gemdesk.json)) |
| `ci_native_aes.py` | 31/31, including every timer, pointer and double-click case through the new wait ([report](aes.json)) |
| `ci_native_held_capture.py` | 4/4 ([report](held-capture.json)) |

Negative controls:

- Without `fo_mark_rows` the mirror case fails at "dialog closed" (complete
  VDC bitmap). A reproducer found 1,422 bytes in scanlines 56–135 still
  showing the dialog ([report](gemdesk-before-forms-fix.json)).
- Without the idle wait, the hardware capture could not find an idle moment
  (below).

Physical C128 (Ultimate II+, private `gem.d81` in 1581 mode; drive A, the
upload and a reset restored after every run):

- **`N_READY` duty after GEMDESK is running** (`--sample-ready 300`: 300 DMA
  samples of `$3d12`, taken after GEMDESK first publishes ready, about 111 s
  after reset):
  - previous loop: 7/300 ([report](hw-ready-peer-loop.json));
  - idle wait: 98/300 ([report](hw-ready-idle-wait.json), a build before the
    alert loop was converted).
- **`--mirror`, run 1** ([report](hw-mirror-run1.json)): desktop, drive
  window, open menu, closed menu and the Desk:About alert all match the VIC
  surface byte for byte on the VDC, colours included. "Alert closed" failed
  in all four attempts.
- **`--mirror`, run 2**, with a second VDC read per attempt
  ([report](hw-mirror-run2.json)): the desktop matched.
  - At the drive window, two reads of the same unchanged VDC disagreed in
    attempts 0 and 3. Every bitmap difference in those attempts is the
    capture one byte ahead, in whole 512-byte chunks.
  - Attempts 1 and 2 read identically and the bitmap matched exactly, but in
    all four attempts two attribute cells (row 15, VDC columns 14 and 58)
    read `$2f` where the VIC colours give `$f2`. Only one cell of each VDC
    pair differs, which a VIC colour change cannot produce.

## Limits

- **Not verified on hardware:** the "alert closed" and "window" steps, as
  described above. Two distinct problems were observed:
  - the held VDC capture intermittently returns 512-byte chunks one address
    late, i.e. the instrument's reads are unreliable;
  - attribute cells read wrong in every attempt: 2 cells in row 15 (run 2,
    window) and 4 in row 2 (run 1, alert closed). Run 1's "alert closed"
    bitmap differences are all the capture shift too.
    - Each wrong cell sits where the colour value changes along its row, and
      the row reads like the expected row moved by one cell. That fits one
      attribute byte lost or doubled while the row was written.
    - Captures taken between steps show the wrong values persisting from an
      earlier present.
    - Whether the mirror's own VDC writes or the probe's register accesses
      caused it is not known.
- Whether the pointer appears on the 80-column monitor has not been
  byte-checked (it was hidden during the captures).
- Extend mode (a second desktop area on the 80-column screen) is designed,
  not built.
- The earlier observation in this record (a person saw the desktop, a window
  and a menu on the 80-column monitor with a pre-dialog-hook build) came from
  the other session and was not re-observed here.
