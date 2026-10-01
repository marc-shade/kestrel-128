# GEM profile on the physical C128 — 2026-09-26

First runs of the GEM layer (AESVC, GEMDESK, `gem.d81`) on the reference
C128 with its Ultimate II+ (REST API 0.1), using `hw_native_gem_check.py`.
Each run:
- mounts a private copy of the committed `gem.d81` (`images.json`), plus the
  NOTE and PICTURE documents, read-only on drive A in 1581 mode;
- resets the C128 and leaves 60 seconds without DMA while it boots;
- reads screens with the held CPU capture (`probes/native-read-held.asm`);
- afterwards remounts drive A as it was (1541, no image), deletes the upload
  over FTP, confirms it is absent, and resets the machine.

No video signal is captured: screens are the 9,216 bytes of bitmap and
colour RAM that the CPU sees, compared with the same oracles as the CPU and
VICE suites. Every run's restore succeeded (drive A 1541 and empty, upload
absent, reset).

## Keyboard run (`keyboard-run.json`)

Six of seven checks passed:

| Check | Result |
|---|---|
| Boot from `gem.d81` on the 1581-mode drive; GEMDESK running, desktop exact | PASS |
| The 8 key lists the D81, sorted by name, exact | PASS |
| Return launches Calculator through the dispatcher | PASS |
| Leaving Calculator reloads GEMDESK, which reopens its window with the selection, exact | PASS |
| Return on a SEQ file opens it in the Editor; the Editor surface is exact | PASS |
| Leaving the Editor returns to GEMDESK with the document selected, exact | PASS |
| Return on a UPNT picture opens it in Paint | Document PASS, surface FAIL |

In the Paint step, Paint loaded the picture and claimed the request, and its
bank-1 document equals the picture byte for byte. The surface differed from
the oracle in one 2×2-cell block (cells 22–23, rows 2–3) of a numeric
readout: the oracle drew "90", Paint drew "1" (`paint-expected.surface`,
`paint-actual.surface`). The oracle's inputs had been read from Paint's
variables with direct DMA reads. The mouse run below shows such reads
sometimes return other bytes (`pm_x` = 5616, `pm_y` = 201) while the AES has
bank 1 mapped, so the suspected cause is a bad oracle input, not Paint. This
is not yet confirmed. The script now reads Paint's state through the held
capture; the Paint step has not been rerun.

The desktop shows the USB icon on this machine: the Ultimate's DOS answers
GEMDESK's identify query. This is the first physical check of that probe;
VICE has no Ultimate.

## Mouse run (`mouse-run.json`)

A person used an original 1351 on control port 1 while the script watched.
All five checks passed:

| Check | Evidence |
|---|---|
| GEMDESK up, desktop exact | full surface |
| The 1351 moves the pointer across the whole screen | reached (8, 3) and (316, 194); `pm_x`/`pm_y` matched the VIC sprite position |
| A double-click on the Boot icon opens drive 8 | full surface exact |
| Dragging the title bar moves the window | the surface matched the oracle only with the window at cell (3, 4) |
| The close box closes the window | desktop exact, icon still selected |

Two earlier mouse attempts timed out at the first step. In the first, the
mouse was on port 2; the pointer module reads port 1, and the SID pots read
`$ff`. In the second, the recorded positions stopped changing after the
first minute, though the person reported that the arrow moved; the cause was
not established. The third run also logged the VIC sprite registers and showed
the pointer tracking live. The pointer module's own state, read
during the third run, showed it sampling every frame inside its raster window.

## Limits

- The Paint surface in the keyboard run is unresolved (see above).
- No 80-column (VDC) output from GEMDESK exists yet, so dual-monitor use shows
  GEMDESK only on the 40-column screen.
- USB windows, USB Show Info, drive-9 detection, keyboard mouse, dialogs and
  menus by pointer were not exercised on hardware here.
- Loading apps over the 1581 emulation took minutes with the harness's
  quiet periods and polling; load speed was not measured.
