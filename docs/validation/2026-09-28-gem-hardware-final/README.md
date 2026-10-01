# Complete system on the physical C128 — 2026-09-28

The committed build of `goal/complete-uos` (`7564321`; `gem.d81` `4743563d…`,
as in `images.json`) on the reference C128 with its Ultimate II+, using
`hw_native_gem_check.py` (keyboard workflow). Setup and restore are as in
[2026-09-26-gem-hardware](../2026-09-26-gem-hardware/README.md): a private
read-only copy on drive A in 1581 mode, then drive A, the upload and a reset
restored. Every run below restored the machine (drive A matches, upload
absent).

## Keyboard run: 7/7 ([report](keyboard-run-pass.json))

| Check | Result |
|---|---|
| Boot from `gem.d81` on the 1581-mode drive; GEMDESK running, desktop exact | PASS |
| The 8 key lists the D81, sorted by name, exact | PASS |
| Return launches Calculator through the dispatcher | PASS |
| Leaving Calculator reloads GEMDESK, which reopens its window with the selection, exact | PASS |
| Return on a SEQ file opens it in the Editor; the Editor surface is exact | PASS |
| Leaving the Editor returns to GEMDESK with the document selected, exact | PASS |
| Return on a UPNT picture opens it in Paint; the banked document and the surface match | PASS |

The Paint step was the open item of the 2026-09-26 record. It now reads
Paint's state through the held capture, and passes.

The run also records the Editor's state on the machine:
- graphical, with the bitmap surface (`eg_started` 1, `eg_bitmap` 1, status 0);
- REU documents (`dm_mode` 2, lease 1) and the span history available;
- the 80-column mirror live (`vd_phase` 2, `vd_live` 1). Before `8d4b476` the
  Editor could not open the VDC while history was loaded, and stayed on 40
  columns.

## The harness must not use DMA during a load

GEMDESK now loads `VDSVC.PRG` for its 80-column mirror, and the boot takes
about 111 s to reach GEMDESK's input wait (was within the script's 60-second
quiet period before). The script's DMA reads during IEC loads broke them:

| Run | Quiet periods | Result |
|---|---|---|
| [20 s after app keys](keyboard-run-20s-quiet-gemdesk-back.json) | boot 60 s, keys 20 s | leaving Calculator never reached GEMDESK within 120 s |
| [20 s, with state dumps](keyboard-run-20s-quiet-editor-text.json) | boot 60 s, keys 20 s | the Editor opened NOTE, its CLOSE failed (status 9) and it stayed in its text mode on the 80-column screen |
| [60 s boot](keyboard-run-60s-boot-quiet.json) | boot 60 s, keys 90/60 s | the boot never reached ready within 300 s |
| [pass](keyboard-run-pass.json) | boot 150 s, keys 90/60 s | 7/7 |

Other runs with the same 20-second quiet periods failed at different
switches (Calculator launch; returning from Calculator) or passed them. The
script now stays quiet 150 s after reset, 90 s after Return (which may load an
app and its document) and 60 s after Escape. It logs every app switch
(`switch_log`: app header, `N_CURRENT`, `N_READY`, file service, pending keys)
and the Editor's display, storage and history state.

The ~111 s boot is a user-visible cost of the mirror on this drive path. Load
speed was not measured separately.

## CPU sweep of the same build

`tests/sweep_native.py --group cpu --jobs 5`: 310/310 jobs passed, covering
every `--case`/`--group` choice and qualified configuration of all CPU suites
([summary](cpu-sweep-summary.json)).

## Limits

- One passing hardware run with these quiet periods. The failures above came
  with shorter ones. Load reliability without DMA was not measured over many
  runs.
- The 80-column mirror's "alert closed" and "window" steps are not verified
  on hardware (see [2026-09-26-gemdesk-vdc-mirror](../2026-09-26-gemdesk-vdc-mirror/README.md)).
- VICE suites are not part of this record.
