# 80-column performance: pointer, kernel transfers and the VDC mirror (2026-10-13)

## Why

After the [hover record](../2026-10-10-desktop-hover/README.md) a pointer
update on the reference C128 still took 18,561 cycles, more than one
17,045-cycle frame, so 80-column motion ran at about 30 Hz, and a focus change
in an 80-column app took 4 to 7 frames (Paint's swatch row about 24).

## Measuring

`tests/bench_native_perf.py` runs the shipped images in Py65 and reports the
cycles of one frame or input step for 21 hover, focus, pointer and menu cases
(64 KiB VDC, 16 KiB initial addressing). The test buses hold the VDC busy for
a fixed number of status reads after every access, to prove the code polls;
their wait loops are an artifact of that model, not 8563 timing. The
benchmark therefore reports the VDC ready on the first poll after each
access, which counts the code's own cycles: a lower bound for real hardware.
Its desktop pointer-only frame at 4ba08dd, 19,063 cycles, is within 3% of the
18,561 timed on the C128. `--handshake` keeps the test buses' model.

Each change below was found by charging every instruction's cycles to the
nearest listing symbol, not by inspection: a one-pass pointer redraw, tried
first, lost (its per-row bookkeeping cost more than the writes it saved) and
was dropped.

## Changes

- **Desktop scene out of the VDC service** (a3cfaad). VDSVC carried the
  desktop's 2,346-byte packed 640x200 scene for every app. The scene now sits
  page-aligned in `desktop.prg`; operation 1 in mode 1 passes the desktop's own
  allocation handle and the scene's page, and the service reads it a page at a
  time through `N_READ` while unpacking. VDSVC dropped from 39 to 30 bank-1
  pages, so every app has nine more free pages while it is loaded: the Editor's
  main-RAM document limit on a 64 KiB VDC rose from 34,816 to 37,120 bytes.
  Its guard now checks the AES base it must stay under.
- **Pointer redraw** (122f9c0). A move restores 16 rows and draws 16, and
  each row paid for a shift loop, a call per register and per byte, and a copy
  through `N_BUFFER`. The build emits the arrow pre-shifted for the four even
  pixel offsets (128 bytes); the row bytes go from the saved slot to the VDC
  with inline ready polls; `vd_seek`, shared by every caller, inlines its two
  register writes. The chip sees the same accesses. VDSVC grows to 31 pages.
- **Kernel transfers in runs** (3df5803). `N_READ`, `N_WRITE` and `N_FILL`
  moved every byte through the KERNAL `INDFET`/`INDSTA` gateways, about 100
  cycles a byte, 35 to 66%
  of an 80-column redraw, since the service pulls each dirty surface row
  through `N_READ`. Bank-0 records, and bank-1 records from `$4000` up, now
  move in runs of up to 32 bytes: with IRQs masked, a run widens the bottom
  common RAM to 16 KiB, as the banked executor does for bank-1 code, maps full
  RAM `$3f`/`$7f`, copies and restores `$0e` and the 1 KiB common area. Bank-1
  pages `$04..$3f`, which that window would hide, keep the per-byte gateway.
  A first version also reused a passed page-ownership walk until
  `N_HEAPEPOCH` changed; the CPU sweep rejected it, because the display and
  graphics suites damage the page tables directly and expect the next call to
  report it. Every call walks again, in a tighter loop (896069f). IRQs now
  run between runs instead of between bytes; Kestrel uses no raster
  interrupts, so only the 60 Hz KERNAL timer waits, under 800 cycles. NMIs are
  never masked.
- **VDC mirror expand loop** (2ce873e). Each dirty row expands 320 VIC bytes
  into 640 VDC bytes. The loop writes with inline ready polls, keeps the byte
  in a variable instead of the stack and counts cells down; a 16 KiB mono VDC
  folds reversed cells into the row once before the eight lines. About 117 to
  76 cycles per VIC byte.

## Cycles

`bench_native_perf.py`, VDC ready on the first poll. The middle column
includes the scene move, which on its own changed these cases by a few
cycles; the last is the final build commit (a7ff654).

| Case | 4ba08dd | after the pointer change | final | Change |
|---|---:|---:|---:|---:|
| Desktop: pointer-only over empty space (mean of 30) | 19,063 | 13,617 | 13,631 | -28% |
| Desktop: within the selected card, same byte column | 15,181 | 10,858 | 10,873 | -28% |
| Desktop: within the selected card, next byte column | 18,827 | 13,637 | 13,651 | -27% |
| Desktop: onto the next card | 90,764 | 84,236 | 53,752 | -41% |
| Calculator: onto the next button across | 70,488 | 65,252 | 43,086 | -39% |
| Calculator: onto the next button down | 103,159 | 97,875 | 58,937 | -43% |
| Controls: Info tab onto Drives tab (across) | 92,952 | 82,529 | 56,297 | -39% |
| Controls: Info tab onto Prev (down) | 122,105 | 112,501 | 69,906 | -43% |
| Files: Device onto Format | 77,378 | 72,142 | 46,395 | -40% |
| Files: first file row onto the second | 84,062 | 78,826 | 45,267 | -46% |
| Editor: Open onto Save As | 75,049 | 69,813 | 44,791 | -40% |
| Paint: Pen onto Eraser | 103,911 | 98,627 | 58,873 | -43% |
| Paint: canvas onto Pen | 64,039 | 58,803 | 38,933 | -39% |
| Paint: swatch onto the next swatch | 401,650 | 398,630 | 159,602 | -60% |
| Paint: moving over the canvas (mean of 10) | 21,336 | 15,892 | 15,906 | -25% |
| Paint: first still frame after moving (status) | 491,597 | 485,977 | 262,405 | -47% |
| Claude: Connect onto Desktop (over disabled Repaint) | 100,658 | 95,398 | 52,962 | -47% |
| Claude: Next onto Panel | 103,955 | 97,639 | 53,367 | -49% |
| GEMDESK View menu: cursor key onto Type | 14,627 | 14,627 | 9,067 | -38% |
| GEMDESK View menu: pointer onto Type | 14,258 | 14,258 | 8,698 | -39% |
| AES menu test: cursor key onto Quit (40 columns) | 15,605 | 15,605 | 9,229 | -41% |

At 1 MHz a frame is 17,045 cycles: the pointer-only update now fits in one
frame, and focus changes in the 80-column apps take 2 to 4 frames instead of
4 to 7.

## Gates

Each sweep ran from a clean clone of its commit.

- Scene move and pointer redraw (9499ac0): CPU sweep 323/323.
- 7fd57ba (all four changes, page walk cached): VICE sweep 37/60. The
  running-kernel audit rejected the new heap variables and the copy loop's
  rewritten operands, which were not declared mutable (b55afcc declares
  them). The CPU sweep of that tree, stopped at 244 jobs, had also failed
  ci_native_display and ci_native_graphics on the cached walk (removed in
  896069f) and two tests that named moved kernel code.
- Final build a7ff654: CPU sweep 323/323; VICE sweep 60/60. One job,
  `ci_native_suite_iec`, missed a wall-clock checkpoint ("Claude close
  checkpoint not reached", 284 s) while the CPU sweep ran alongside, and
  passed when rerun alone (235 s); the cause was not isolated.
- Hardware (6241a57, which pins the a7ff654 disk and kernel images):
  `hw_ultimate_check.py --native-desktop` on the reference C128 with an
  Ultimate II+ PASSED. RAM, VDC and display mode matched at 14 checkpoints:
  desktop boot, Editor selected, Calculator new and result, Editor new and
  typed, Files, Sheet new and calculated, the desktop after each app, and the
  returned workspace. Drives were restored and matched, the upload was
  deleted, no leftovers, images unchanged, no host connect failures or
  uncertain host writes.
- Hardware (4a6c29c, the same images): `--native-editor` PASSED at 24
  checkpoints, among them a document over 64 KiB opened, edited past 64 KiB,
  saved through the file picker and verified, an existing file rejected, and
  the saved file reopened at its edit position; the files were independently
  read back. `--native` PASSED: cold boot, the memory workspace, and 8,192
  bytes allocated, filled and read back in bank 0 and in bank 1 through the
  kernel transfers. Both restored and matched the drives, deleted their
  uploads, left nothing behind and found the images unchanged.
- Hardware (c7a31de, the same images): `--native-files` (IEC streams,
  exported files and a copy read back), `--native-browser` (12 checkpoints),
  `--native-usb-apps` (33), `--native-ultimate` (15) and `--native-redraw`
  (24, the Editor redraw cases on a small and a large document) all PASSED,
  with the same drive restore, cleanup and image results.
- `ci_native_heap` injects an NMI and an IRQ at every masked instruction of
  both transfer paths (1,782 interrupts), checks IRQ delivery between runs,
  the masked span, the data of each operation, and a bank-1 record across
  `$4000` that leaves bank 0's kernel data at the same addresses untouched; a
  build that sent pages below `$4000` to the bulk path fails it.

## Not verified

- The cycle counts are Py65 with a VDC that is always ready. A real 8563
  sometimes needs a second status read; how far hardware lands above these
  lower bounds was measured only for the 4ba08dd pointer frame (3%).
- 60 Hz pointer motion on the C128 was not timed after the change; only the
  hardware desktop check's screens were.
- Every hardware check `hw_ultimate_check.py` offers ran for these images
  except `--native-usb-browser`, which the harness marks not available. No
  hardware check exists for Paint, Controls, Claude, GEMDESK, the AES menu
  test or a Sheet save to disk; those are covered only by the sweeps.
- The redraw check's timings are host wall-clock times that include REST
  polling, not cycle counts; they were not compared with earlier runs.
- The Editor's >64 KiB document beside a full 296-entry picker
  (`ci_native_picker_gui --case large`) is a zero-slack capacity case. With the
  service padded to other sizes it passes at 31 (this build), 36 and 39 pages
  and fails at 30 and 32 to 35. The document needs 259 pages: 16 chunks of
  4 KiB and a 3-page final chunk. Positions map to chunks by P >> 12, so only
  the final chunk may be short, and it grows in place from the first free page
  once no 4 KiB run is left. Every other free run loses its size mod 16 pages.
  At 32 pages Open failed with 26 pages still free, in runs of 15 and 11, so
  the result depends on the layout, not on the free total. It passes here; any
  later change to a resident size can flip it. Removing the limit means
  changing how positions map to chunks in the document code, which this work
  did not attempt.
