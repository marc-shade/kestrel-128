# Modular Sheet and session clipboard — 2026-09-15

Sheet's 96-page allocation now contains a checked `$b100..$bfff` module window.
Calculation, font presentation and the shared clipboard library alternate in
that window. Source cells, results, Undo/Redo state, display owners and the C
stack stay in the core. The three files `SHCALC.PRG`, `SHFONT.PRG` and
`SHCLIP.PRG` must match `SHEET`; their manifests bind them to its CRC and extent.
They load from the original app's IEC disk or Ultimate folder.

Ctrl-C/X/V exchange one complete cell source with the session clipboard. Cut
publishes before clearing; Paste validates the complete item before changing
the workbook. Only 1–31 printable ASCII bytes are accepted. Empty Copy/Cut
keeps the previous clipboard. Formula references remain literal; this is not
range paste or relative-reference rewriting.

## Evidence

Seven frozen-input CPU jobs cover:

- Clipboard Copy/Paste/Cut, Undo, empty-cell retention, control-byte refusal
  and a missing clipboard module without changing the workbook or old item.
- Editor → Sheet formula → Editor exchange on one kernel, plus rejection of
  an oversized Editor clipboard item. No kernel restart occurs between apps.
- Missing/corrupt calculation modules: retain edited source, invalidate stale
  values, and recalculate the same source after restoring the module. A missing
  font retains source/owners and latches its error; unrelated keys cause no
  additional source I/O, and explicit retry restores presentation.
- Ultimate-loaded app and its modules, file operations in both DOS contexts.
- MIN/MAX/COUNT, edit/recalculation, Undo and verified workbook save/reopen.
- Staging allocation/read failure, partial output and retained VDC failure.
- Core editing, formulas, scrolling through H32 and ownership on a 16 KiB VDC.

Each uses the actual packed app and native loader with independent source/value
expectations and complete VIC/VDC pixel checks. Reports/logs and exact commands
are in `results.tar.gz`; `statuses.json` records exit codes. Clipboard malformed
control-byte coverage injects opaque provider payload bytes; actual cross-app
exchange is covered separately by the Editor workflow.

Two private VICE workflows use 40-column startup/16 KiB VDC and 80-column
startup/64 KiB VDC. Both cold-boot the suite, enter formulas, Copy/Paste/Cut,
Undo, save/reopen through IEC drive 9 and return to desktop selection 6.
Complete display memory and rendered canvases are checked. Host `c1541`
extraction independently matches every byte of each 8,208-byte workbook.
`vice.tar.gz` retains the reports, private disks and complete captures.

A fresh build reproduces all 40 PRG/D64/D81 images exactly. Media validation
checks all six boot images, exact packaged payloads, allocation chains and
three corruptions. `inputs.tar.gz` retains frozen source and rebuilt outputs;
`inputs.json` hashes the snapshot before building. Documentation was finalized
later. `baseline.txt` identifies the parent commit. Earlier development runs
were superseded when font-error latching was added; accepted results here use
the final frozen executable sources.

The seven CPU reports, media report and rebuild report were regenerated on
2026-09-25 (the original session's result archive was never written) with
`tests/ci_native_sheet.py --case {clipboard,clipboard-handoff,modules,ultimate,
aggregates,faults}` and `--case core --size 16`, `tests/ci_native_boot_media.py`,
and a rebuild of the extracted `inputs.tar.gz` tree. That rebuild, the frozen
images and the working tree agreed on all 40 images, and the rebuilt `SHEET`
matches the one the VICE reports record.

Run `python3 verify.py` here to verify archive integrity, reports, image hashes,
module CRC/parent bindings, and independently decode both saved workbooks.
It does not rerun the CPU or VICE display oracles.

## Limits

The suite has 19 entries, with 16 free D64 or 2,512 free D81 blocks. Sheet keeps
its 96-page allocation; clipboard payloads use the shared owner-31 bank-1 arena
and may fail when memory is exhausted. Module swaps add source-device I/O.
No physical C128, Ultimate, mouse or REU qualification is claimed. VICE input
uses ROM/native key handling rather than electrical keyboard-matrix input.

Range clipboard, mouse clipboard controls, relative formula adjustment,
module caching, larger picker integration, decimal arithmetic, formatting,
printing and the wider OS/office/expansion roadmap remain open.
