# IEC DOS commands (`dos-command.inc`)

A native app includes `src/native/dos-command.inc` to send one CBM DOS
command to an IEC drive and read the drive's status line. GEMDESK uses it to
delete files (`S0:NAME`). It is the IEC counterpart of the Ultimate
`DELETE_FILE`/`RENAME_FILE` commands that Files sends through `N_UCOMMAND`.

It is an app-side library, not a kernel entry: the resident kernel has no
free bytes for another service ([TOS-PARITY](TOS-PARITY.md)).

## Call

| In | Meaning |
|---|---|
| `dc_device` | IEC device 8..30 |
| `dc_text`, `dc_length` | The command, 1..40 bytes, sent exactly (PETSCII) |

`jsr dc_command`. Carry clear: A = `dc_code`, the DOS code from the status
line. `dc_status`/`dc_status_length` hold the line without its CR, and
`dc_track` holds its third field as a number. After a scratch, that field is
the number of files the drive removed.

Carry set, A =:

| Code | Meaning |
|---|---|
| `N_BADARG` | Length 0 or over 40, or a device outside 8..30 |
| `N_REENTRANT` | Called inside a kernel file call |
| `N_CHANNELS` | Input or output is redirected, or the kernel holds a command channel to that device |
| `N_IOERROR` | OPEN failed, the device is absent, the status line was not read, or it is not `NN,...`. `dc_iostatus` has the KERNAL status. The command may or may not have run. |

The code 01 is not an error. A scratch that finds nothing, or finds only
locked files, reports `01, FILES SCRATCHED,00,00`. Callers check `dc_track`
to learn whether anything was deleted.

## Free blocks

`jsr dc_blocks_free` (with `dc_device` set) opens the drive's `$` listing on
secondary address 0 and reads it to its end. The listing is a BASIC program
whose line numbers are block counts. The number of its last line, the
"BLOCKS FREE." line, goes to `dc_free` (word). The checks, the errors and
the channel rule are the same as for `dc_command`. GEMDESK's Show Info on a
drive icon shows it.

## How it works, and the rule it keeps

The command is the name of an `OPEN` on secondary address 15 with logical
file 127 (the kernel uses 122..126). The drive executes it when the channel
opens. The library reads the status line through `CHKIN`/`CHRIN`, bounded to
40 bytes, and closes the channel.

On a CBM drive, closing the command channel closes every channel of that
drive. So the library refuses while the kernel's command-channel table
(`NFCMDS`) names the device, which is the case whenever a native stream is
open on it. The kernel keeps no channel open between `N_DIRPAGE` calls. Like
the kernel, the library saves and restores the KERNAL file parameters
(`$b7`–`$bc`, `$c6`/`$c7`, `$9d`), selects bank 0 for the name, and refuses
redirected channels.

The library reads `NFCMDS`, which `api.inc` marks as private kernel state. If
the kernel's channel table changes, this library must change with it.

## Limits

- Commands run as sent. The library does not check names for DOS pattern
  characters: `S0:A*` scratches every match. GEMDESK refuses names that
  contain `* ? , = : " @` before sending.
- One command per call; no block commands with data (`B-W`, `M-W`).
- No timeout beyond the KERNAL's serial timeouts.

## Verification

`tests/ci_native_gemdesk.py` runs GEMDESK's Delete through the library. It
checks that:
- the drive receives `S0:DOOMED` exactly once, and only after confirmation;
- a rename is sent as `R0:NEWNAME=OLDNAME`, and a clash with an existing name
  (63 FILE EXISTS) is reported with the drive's status line;
- a locked file the drive skips (count 00) is reported;
- the call refuses with the kernel's channel table naming the drive, before
  any OPEN;
- a failed OPEN reports `N_IOERROR`.

The IEC model is `StreamIEC` in `tests/ci_native_files.py`. It
implements scratch (skipping locked files) and rename. It answers any other
command with `31,SYNTAX ERROR`. The library has not run against a real drive or in
VICE.
