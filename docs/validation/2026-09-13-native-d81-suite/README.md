# Native D81 suite software qualification

ABI 1.12 adds bootable 1581/D81 distributions for the blue native desktop,
the suite workspace and the standalone diagnostics. The full D81 suite has
2,504 free blocks, versus eight on D64. `N_BOOTFORMAT` at `$3de4` keeps the
system geometry independent of data-volume preferences. The six application
PRGs and their modules are shared between formats. Only the launcher needs
the new ABI field; app/module validators accept minor 12 and reject 13.

The main and clean isolated builds reproduce all **29** native PRG/D64/D81
images exactly. The record freezes **545** inputs and retains ten successful
supervised jobs, twelve CPU/media reports and their actual source versions.
The 300 recorded CPU cases cover startup, both bank patterns, desktop
handoffs/refusals, IEC/Ultimate app and module validation/recovery, resident
layout, and the large Editor picker. Its 66,057-byte document plus 296-entry
D81 picker leaves three free pages, preserving the existing memory budget.

Two complete VICE 3.10 workflows use native cold boot, true drive emulation,
real host keyboard/1351 input and both displays:

| System disk | Initial display / VDC | Workflow |
|---|---|---|
| D81 / 1581 | 80 columns / 64 KiB | All six apps; Calculator and Editor verified saves; Files copy to device 9/D64; Paint save/reopen on the D81; workspace C/B return to system apps |
| D64 / 1541 | 40 columns / 16 KiB | Same six apps; Calculator and Editor saves on the system disk; Files copy and Paint save/reopen on the separate D64 |

Both retain all shipped files, restore the keyboard/display borrowers and
finish with all 426 managed pages and 32 handles free. Offline verification
reconstructs 137 VIC and 35 VDC palette frames (13,248,000 pixels), checks twelve
pre-app VDC snapshot restores and audits 1,528 CPU captures / 5,376 chunks /
6,112 borrower comparisons. Complete file exports, input events, resident
bytes, captures and process exit receipts remain in the archives.

The independent media test audits every allocation bit/count and file chain
on all six shipping disks, compares every shipped PRG, fills all 2,504 free
D81 blocks with a 636,016-byte payload, and verifies the original files and
reserved boot sector. It also rejects three boot/BAM corruptions. The stress
image is temporary; its result/hash and reproducible test are retained.

Development attempts are preserved in `preliminary.tar.gz`. Two early D81
runs stopped because Editor and Files copy screen expectations still named
D64; both apps were displaying the correct D81 format. An early module test
still treated ABI 12 as unsupported and was updated along with the host module
validator. The first startup-pattern test was stopped because it reread a
large listing every instruction. Caching addresses exposed a separate test
budget issue: full 8 KiB fill/verify paths take 540,514–614,240 instructions,
exceeding the original 500,000 limit. The final test uses a bounded 2,000,000
limit, records actual counts and passes all original semantic checks. These
changes did not alter the built application or kernel images.

Run `python3 -B verify.py` here to audit this record without an emulator or
hardware. `rebuild.py` is an unsealed-record construction utility; sealed
records are immutable. `source-versions.tar.gz` pins earlier imported files
used by successful jobs while unrelated tests, documentation and builders
were being completed. The offline verifier checks those hashes explicitly.
`reference.tar.gz` contains the consulted 1581 BAM declarations/routines from
`mist64/cbmsrc` commit `01bd60f162ef92212ef0cb67546ae8f42be34168`.

This is software qualification. No physical device was accessed and no remote
changes were pushed. Physical 1581/Ultimate D81 qualification, D71 boot media,
partitions, automatic format detection, installers/recovery and dynamic
system-volume replacement remain open. VDC graphics inside the applications,
shared display services and the broader OS/application roadmap also remain
open. The existing VDC launcher geometry limitations still apply.
