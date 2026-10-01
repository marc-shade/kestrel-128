# Native Sheet desktop software checkpoint — 2026-09-14

Sheet is the seventh native desktop app: an editable 8 × 32 workbook with
checked integer formulas, keyboard and 1351 controls, VIC/VDC display,
transactional Open and exclusive Save As with complete readback verification.
See [Sheet controls and format](../../NATIVE-SHEET.md).

## Evidence

- Seven frozen-input CPU jobs cover 16/64 KiB VDC core editing, file round trips,
  malformed input, mouse operation, Ultimate DOS contexts and failure recovery.
  Their exact commands and exit codes are in `statuses.json`; reports and logs
  are in `jobs.tar.gz`.
- Two private VICE runs cover 40-column startup with 16 KiB VDC and 80-column
  startup with 64 KiB VDC: cold boot, desktop launch, edit/recalculate, real IEC
  drive save/reopen and desktop return. `vice.tar.gz` retains disk images,
  rendered canvas and display memory captures, reports and emulator logs.
  Host `c1541` extraction matches all 8,208 expected workbook bytes.
- Desktop pointer and VDC/service regression reports are retained separately.
- Packed-app checks pass for all eight images (desktop and seven apps), including
  complete decoded bodies, cleanup, corrupt inputs and allocation failures.
  The report is included in `jobs.tar.gz`.
- A fresh source copy reproduced all 37 PRG/D64/D81 images byte for byte;
  `rebuild.json` records their hashes. Final media validation checks exact suite
  payloads and allocation chains, including rejection of three corruptions.

`inputs.tar.gz` contains the source/build tree used for the seven CPU jobs and
fresh build. `inputs.json` identifies the original snapshot inputs; generated
outputs were subsequently rebuilt in that tree. Documentation was finalized
later in the repository. `baseline.txt` identifies the parent commit.
`SHA256.json` covers the evidence files. Run `python3 verify.py` here to check
archive integrity, job results and independently decode both saved workbooks.
This verifier does not rerun the emulators or replace their display oracles.

## Limits and remaining work

This is software qualification, with no physical C128, Ultimate, mouse or REU
I/O. Ultimate tests use the protocol model; IEC VICE tests use emulated drives.
VICE input is injected through ROM/native key handling, not the keyboard matrix.
Sheet-specific REU backing, transfer cancellation and failed-CLOSE retry have
not received dedicated end-to-end tests in this checkpoint.

The app reserves 93 pages plus a 32-page workbook and shared display storage;
Open/New temporarily need another 32 pages. The suite has 16 disk entries and
34 free D64 blocks or 2,530 free D81 blocks.

Decimal arithmetic, formatting, range operations, clipboard, undo, printing,
shared file-picker integration and geoCalc/CSV interchange remain open, along
with the wider desktop, office and expansion roadmap. No GEOS/Wheels parity or
physical deployment qualification is claimed.
