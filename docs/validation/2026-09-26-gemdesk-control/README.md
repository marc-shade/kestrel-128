# Control Panel, keyboard mouse, GEMDESK modules — 2026-09-26

## What changed

- **AES 1.6:** `AE_OP_DCLICK` (GEM's `evnt_dclick`). The double-click window
  is set by speed 0–4 (40, 30, 20, 15 or 10 jiffies) instead of a fixed 20.
  `AESVC.PRG` is 14,079 bytes.
- **AES client:** the keyboard mouse. ALT or C= with the cursor keys moves
  the pointer 8 pixels, and with Return clicks (the KERNAL `SHFLAG` bits
  were checked in ROM `318020-05`).
- **GEMDESK:**
  - Desk:Control Panel sets key repeat (KERNAL `RPTFLG` `$0a22`, checked in
    the same ROM) and double-click speed. Both are kept in the desktop
    record, now version 2.
  - The 8 and 9 keys open drive windows.
- **GEMDESK memory:** the core plus a module window. The dialogs are in
  `GDDLG.PRG` (Show Info, Format) and `GDSET.PRG` (Preferences, Control
  Panel), each with its own copy of the forms library. They are loaded on
  demand and replace each other, and a missing module gives an alert. The
  build splits and seals them like the Files modules; both are on
  `gem.d81`.

## Evidence

Images: `gemdesk.prg` `dde03a0f…` (11,281 bytes packed), `gddlg.prg`
`8a2e93b8…`, `gdset.prg` `1844c413…`, `aesvc.prg` `c9c36b3d…`.

- `tests/ci_native_gemdesk.py` → `gemdesk.json`: 35/35 (CPU). New cases:
  - The keyboard mouse: two ALT+right presses move the pointer exactly 16
    pixels, and ALT+Return selects Trash.
  - The Control Panel dialog, with key repeat set to None and speed 5.
    `RPTFLG` becomes `$40`. A double-click with its presses 12 jiffies
    apart opens a drive at the default speed, but at speed 5 it is two
    single clicks.
  - A missing `GDDLG.PRG` gives the load-error alert (`N_IOERROR`, `$11`),
    and the desktop goes on.
  - The 9 key opens drive 9.
- `tests/ci_native_aes.py` → `aes.json`: 31/31.
- `tests/ci_native_aes_vice.py` → `aes-vice.json`: 5/5 in VICE x128.
- `tests/ci_native_gemdesk_vice.py`: 4/4 in VICE x128
  ([the VICE record](../2026-09-26-gemdesk-vice/README.md)).

### Regression of the other CPU suites (second batch)

These cases take `--case` or `--size` arguments, so the first batch could
not run them. All ran against the main tree's build; the hashes were
unchanged before and after.
- **Passed (41):** every case of `clock` (6), `clipboard_apps` (6; `handoff`
  after installing the missing `pyte` package in the test venv) and
  `open_with` (10), and `claude_vdc` at 16 and 64 KiB. `picker_gui` and
  `editor_selection` passed every case except those below; `editor_history`
  passed every case except `large`.
- **Failed (5):** `picker_gui --case large`, `editor_selection --case large`
  and `--case capacity`, `editor_history --case large --reu-kib 512`, and
  `editor_selection --case display --vdc-kib 16`. Each fails identically in
  a worktree of `737adad`, before this session's changes, so these are
  pre-existing failures, not regressions. They are not fixed here.

## Limits

- The keyboard mouse works only in apps that use the AES client; the Files,
  Editor and Paint apps don't yet.
- The Control Panel is a desktop dialog, not an accessory; there is no key
  click, bell or clock setting in it.
- ALT and C= are the modifiers in the CPU model (`$d3` set by the test). The
  keyboard mouse has not been tried in VICE or on a C128.
