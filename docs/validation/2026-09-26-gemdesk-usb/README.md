# GEMDESK USB storage, documents and the $5000 workspace — 2026-09-26

## What changed

- **USB storage** ([GEM-DESKTOP](../../GEM-DESKTOP.md)):
  - A USB icon appears when the Ultimate's DOS (target 1) answers an
    identify query through `N_UQUERY`.
  - Its windows list DOS context 1 from `/` through the kernel's directory
    cursor.
  - A folder opens in the same window; the close box goes up one level, as
    in TOS, and closes the window at the root.
  - A file launches through the dispatcher with its full path. The path is
    re-read from the cursor by position, because a record keeps only 16
    name bytes.
  - Delete asks for confirmation, sends `DELETE_FILE`, then checks with
    `FILE_STAT` that the name is gone (status 82) before listing again.
    A folder that is not empty is refused with an alert naming the DOS
    error. Show Info and rename say they are not available on USB (Files
    has them).
- **Documents:** double-clicking an IEC SEQ file, or a USB file ending in
  `.TXT` or `.SEQ` (any case), opens it in the Editor through the
  [document contract](../../NATIVE-DOCUMENT-LAUNCH.md). GEMDESK fills in
  the device, format, name and (USB) folder path, stages `N_DOCREQUEST`
  with kind 1 (Editor) and return flag 0, saves its session and replaces
  itself with `editor` from the boot disk. The Editor claims the request;
  leaving it returns to GEMDESK, which reopens its windows.
- **Memory:** the sort buffer moved out of the core into a 16-page bank-0
  workspace at `$5000`, reserved at start as Files does. A listing now
  holds 195 entries, the 16-page snapshot the design specifies. The core
  ends at `$a769` (it was `$b17f` before the move, without USB or
  documents).
- **Test models:**
  - The display bus reads `$df1c`–`$df1f` as `$ff` (no Ultimate)
    instead of failing.
  - The GEMDESK harness builds its Ultimate model from the directory and
    identify models (`ci_native_query.QueryDOS`).
  - A harness bug found here: with a USB model, the machine's bus is an
    `UltimateBus` wrapper that forwards attribute reads but not writes, so
    `Pointer.frame` set the button and raster on the wrapper and the
    pointer never moved. The harness now uses the wrapped bus.
  - The relaunch case clears `N_DOCREQUEST` before starting GEMDESK
    again, as the kernel's dispatch fallback does (`uos128.asm`, before
    loading the desktop).

## Evidence

`gemdesk.prg` `b2646b69…`, `gddlg.prg` `c46ed718…`, `gdset.prg` `b6101486…`,
`gem.d81` `6d3900ad…` (dev build of this change).

- `tests/ci_native_gemdesk.py`: 40/40 (CPU, Py65). New cases:
  - The USB icon, root, `/Usb0` sorted by name, a subfolder, and the close
    box back up. Every one is an exact surface.
  - A file with a 28-byte name launches with `N_UPATH` = its full path,
    `N_NAMELEN` its length, context 1 and format 3.
  - USB Delete: `DELETE_FILE` then `FILE_STAT` (82) and a fresh listing; a
    full folder is refused.
  - A SEQ file on drive 8 stages an Editor document (`$80`, kind 1, type 0,
    return 0) with its exact name, device and format. A PRG launched after
    that carries no document request.
  - `notes.txt` on USB opens in the Editor with its folder `/Usb0`.
  - A 204-file D81 root lists its first 195 entries.
- `tests/ci_native_gemdesk_vice.py`: 6/6 in VICE x128 (1581 true drive
  emulation). There is no Ultimate there: the probe sees none, and the
  desktop matches the oracle without the USB icon. The two new cases write
  a SEQ file `NOTE` to the test's copy of `gem.d81`:
  - Return on `NOTE` loads the real Editor, which claims the request
    (`N_DOCREQUEST` = 0). The whole 9,216-byte surface matches the Editor
    oracle (`native_editor_scene.surface`) with the file's text.
  - Esc returns to GEMDESK with `NOTE` still selected.

Planted bugs (each built and run through `ci_native_gemdesk.py`; each
failed):

| Planted bug | Failed at |
|---|---|
| No USB icon when the Ultimate answers | "usb icon" surface |
| The close box always closes a USB window | "back up" surface |
| USB names cut to 16 characters | the full-path launch assertion |
| An IEC SEQ file launched as a program | SEQ → `EDITOR`, name length 6 |
| `.txt` matched case-sensitively | `notes.txt` → `EDITOR`, request `$80`, kind 1 |
| The return flag set to Files | "a staged Editor document" |

## Limits

- USB windows are CPU-model only; nothing ran against a real Ultimate. The
  model is the directory-cursor model that the folder and browser suites
  already use. The USB document path is checked only in that model; the
  VICE document case is IEC.
- The planted bugs were run through the CPU suite, not VICE.
- USB windows are not kept in the desktop record, and USB rename and Show
  Info are not in GEMDESK.
- Only text opens as a document: GEMDESK does not route UPNT pictures to
  Paint (Files does), and there are no user-defined associations.
- Drive 9 is still assumed to be a D64.
- Nothing here ran on the physical C128.
