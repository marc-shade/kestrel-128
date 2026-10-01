# Editor: Ctrl-L reopens the 80-column display while history is live — 2026-09-27

## Problem

`ci_native_editor_selection.py --case display --vdc-kib 64` failed at exit with
"refused provider never borrowed VDC RAM". The case pauses the VDC display
(stalled chip), restores it, then presses Ctrl-L to reopen it. After Ctrl-L the
display stayed closed: `vd_phase` 0, the VDC component still loaded
(`bk_state` 2), no VDC writes.

It passed in the 2026-09-14 selection record. Building each commit's own
sources and tests: `11d64e2` passes, `34bc252` (span history) and every later
commit fail, including `ef57914` ([report](unfixed-ef57914-disp64.json)).

## Cause

`34bc252` stores the undo history in the VDC component, so `vd_close`
(`src/native/graphics/vdc-client.inc`) keeps the component loaded while
`eh_available` is set, as it already did for an REU document lease
(`dm_lease`). `vd_open` reused a loaded component only for `dm_lease`; for a
component kept for history it returned `N_BADARG`. Ctrl-L's retry therefore
never reopened the display, and the Editor stayed on the VIC.

## Change

`vd_open` reuses a loaded component for exactly the reasons `vd_close` keeps it:
`dm_lease` or (`BP_HISTORY`) `eh_available`. 3 bytes in the Editor
(`EDITOR.PRG` ends at `$bff9`); every other app is byte-identical.

## Evidence (CPU, Py65; `physical_hardware_io` false)

Build with the change: `editor.prg` `8bf522eb…`.

| Suite | Result |
|---|---|
| `ci_native_editor_selection.py --case display --vdc-kib 64` | PASS ([report](disp64.json)) |
| `ci_native_editor_selection.py --case display --vdc-kib 16` | PASS ([report](disp16.json)) |
| `ci_native_vdc_editor_recovery.py --group exit` | PASS ([report](recexit.json)) |

The same cause failed 11 more jobs in the full CPU sweep of the `0021c4b` build
(the recovery, fallback and search-recovery suites reopen the display the same
way). With the change all pass: `ci_native_vdc_editor.py --size 16 --case source`;
`ci_native_vdc_editor_fallback.py` groups `modules`, `surface`;
`ci_native_vdc_editor_recovery.py` groups `idle`, `open`, `picker`, `save`,
`search`, `verify`; `ci_native_vdc_editor_search_recovery.py` cases `initial`,
`replace` (reports alongside).

`ci_native_vdc_editor_fallback.py --group open` also asserted that a refused
display leaves no component loaded. Since `34bc252` the component is loaded
without a VDC chip on purpose: it hosts the span history (`dm_ensure`,
`docs/NATIVE-HISTORY.md`), as it hosts REU documents in
`ci_native_editor_reu_documents.py --case no_vdc`. The test now requires, per
case: chip absent, display closed and the component loaded with history
available; component missing or corrupt, display closed and nothing loaded.
3/3 cases pass ([report](vdc_editor_fallback___group_open.json)).

Negative control: without the change (`34bc252` through `ef57914`) the display
case fails with the assertion above.

## Limits

- CPU-level only; not yet run in VICE or on the C128.
- The complete CPU sweep of this build is pending (see the goal state file).
