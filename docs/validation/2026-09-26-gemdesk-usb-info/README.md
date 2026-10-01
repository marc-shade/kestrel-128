# GEMDESK Show Info on USB entries — 2026-09-26

## What changed

File:Show Info (Ctrl-I) on a USB entry used to say "not available". It now
asks the Ultimate's DOS for the entry with `FILE_STAT` (`$08`), using the full
path re-read from the directory cursor, and shows an alert:

    [0][<name, up to two lines of 29>|Folder]
    [0][<name>|File, 70000 bytes]

- The reply layout is from the firmware's `dos.cc` (`DOS_CMD_FILE_INFO`):
  size (LE32), date, time, extension (3), attribute, name (at most 63). The
  Ultimate DOS documentation gives the same field order.
- A name over 29 characters continues on a second line. Over 58, the second
  line ends in "...". The characters `[ ] |` and DEL show as `?` so that a
  name cannot break the alert syntax.
- The size is the exact 32-bit byte count ("1 byte" when singular).
- The alert has no icon. With an icon, a 28-character name on three lines
  needs 33 × 8 = 264 cells, over the AES's 250-cell limit, and the AES would
  refuse it. At most, this alert is 31 × 8 = 248 cells.
- The date is not shown: the firmware sources fetched here do not show how
  FileInfo's date and time are filled, and guessing an encoding was avoided.
- A failed `FILE_STAT` shows the existing "Could not read USB storage"
  alert with its error code. Rename on USB is still not in GEMDESK.

The core now ends at `$a969`.

## Evidence

`gemdesk.prg` `4ebcfd28…`, `gddlg.prg` `18cdbf6b…`, `gdset.prg` `12af6424…`,
`gem.d81` `85ce5d90…` (dev build of this change).

- `tests/ci_native_gemdesk.py`: 44/44 (CPU, Py65). The harness's Ultimate
  model now reports each file's real size in the `FILE_STAT` reply. Cases:
  - The 28-character program name: `[0][A VERY LONG PROGRAM NAME.PRG|File,
    10 bytes][OK]`.
  - A folder.
  - 56- and 58-character names on two lines, with sizes 70,000 and 67,895
    (both over 16 bits).
  - A 70-character name, which `FILE_STAT` cuts to 63, shown as 29 +
    26 + "...", size "1 byte".
  - Every alert is compared as a full surface against the AES oracle, and so
    is the desktop after closing it.
- `tests/ci_native_gemdesk_vice.py`: 8/8 in VICE x128 (no Ultimate there,
  so it checks that nothing else changed).

Planted bugs (each built and run through `ci_native_gemdesk.py`; both
failed):

| Planted bug | Failed at |
|---|---|
| The size converted with 16 shifts instead of 32 | the first USB info alert ("10 bytes") |
| No "..." past 58 characters | the 70-character name's alert |

## Limits

- Checked only in the CPU model of the Ultimate's DOS, not on a real
  Ultimate.
- The failure path (a `FILE_STAT` error or a short reply) is not covered by
  a test.
- No date, and no USB rename.
