# Sheet opens workbooks from GEMDESK and Files; GEMDESK Bell — 2026-09-30

## Change

- **Sheet workbooks as documents** ([contract](../../NATIVE-DOCUMENT-LAUNCH.md)):
  document kind 3. GEMDESK and Files send a file that starts with `USHT`
  (Sheet saves workbooks as SEQ) to Sheet instead of the Editor or the byte
  viewer. Sheet claims the request in its `SHCLIP.PRG` module (operation 2,
  the shared `document-launch.inc`), which the build assembles with the
  addresses of the core's `wb_path`, `wb_device` and `wb_format` taken from
  the core's link (`sheet.lbl`); the core then runs its ordinary Open before
  the first frame ("Opening cell:"). A request of another kind, or an
  unusable one, is cleared and leaves the blank workbook. Sheet's core had
  39 bytes left below its module window; this used 37.
- **Bell** in GEMDESK's Control Panel (bit 4 of the preference byte): the SID
  bell (`sd_bell`) when an alert with the stop icon (`[3]`) opens. OK in
  Preferences keeps it (as it keeps Key click).

## Tests changed

- `ci_native_pointer_iec`: the wait for a drag's destination samples
  N_READY at a random point of the frame (see Evidence).
- `ci_native_sheet --case document` (new): a staged kind-3 request for an
  IEC workbook and for a USB one (folder and name joined), and a kind-1
  request that must be cleared.
- `ci_native_open_with --case sheet` (new): Files hands a workbook to Sheet
  through the dispatcher, and Sheet returns to Files with the row selected.
  The suite learned Sheet's labels (`sheet.lbl`) and its PETSCII output.
- `ci_native_gemdesk`: a USHT file launches "sheet" with kind 3; Bell rings
  for a drive error's stop alert, not before it is ticked, and survives
  Preferences. `ci_native_gemdesk_vice` opens a workbook in Sheet from the
  desktop in VICE and returns.

## Evidence

- **Full CPU sweep** of the tree without Bell ([summary](cpu-sweep-full-summary.json),
  `tests/sweep_native.py`'s jobs through a resumable driver, since one
  background task may run 2 hours): 321/321, including the new
  `ci_native_sheet --case document` and `ci_native_open_with --case sheet`.
  The tree with Bell differs from it only in GEMDESK's core, its modules,
  `gem.d81` and GEMDESK's tests and docs.
- **GEMDESK CPU set** with Bell ([summary](cpu-gemdesk-summary.json)): 12/12.
- **Full VICE group** with Bell ([summary](vice-summary.json)): 59/59 after
  one test fix. The first run ([results](vice-run1-results.jsonl)) failed the
  two Pointer-suite Editor-selection jobs at "mouse destination idle", and
  alone again. That regression is older than this change: the job fails at
  `a52df72` (the commit before), passes at the commit before `0b39e4e`
  (Editor Print) and fails at `0b39e4e`. Print shifted the Editor core's
  timing, and the test's wait for the drag's destination read N_READY at
  the monitor's fixed point of the frame, where an app that samples the 1351
  every frame is busy (the phase lock this suite already avoids elsewhere
  with a random step, `unphase`). The wait now steps a random part of a frame
  before each sample; both jobs pass. The Editor did go idle during the drag,
  or no sample could have seen it.
- The GEMDESK VICE test opens a USHT workbook from the desktop in Sheet
  (A1 7, B1 =a1*6 read 7 and 42) and returns.
- **Mutation check**: SHCLIP claiming kind 1 instead of 3 leaves Sheet blank
  and fails `--case document` ([0, 0] for [7, 42]).

## Not verified

- Nothing has run on the physical C128. The bell's sound was not listened
  to: the tests assert the SID register writes.
- The Bell rings only for GEMDESK's alerts; other apps and the VT52 terminal
  do not read it.
