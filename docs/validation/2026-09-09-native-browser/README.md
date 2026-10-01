# Native Files and Apps — 2026-09-09

This checkpoint adds ABI 1.2 root-directory pages, a native file/app browser,
forward byte inspection and application handoff after owned cleanup. The
calculator now inherits its source disk format for verified history export.
The [browser guide](../../NATIVE-BROWSER.md), [file ABI](../../NATIVE-FILES.md)
and [application ABI](../../NATIVE-APPS.md) describe the contracts and controls.

The native graphical desktop, shared dialogs, banked document editor,
scheduler, Ultimate service migration and expansion certification remain on
the [completion roadmap](../../IMPLEMENTATION-ROADMAP.md). This milestone
does not complete R3 or the OS.

[SHA256SUMS](SHA256SUMS) covers every archived artifact except itself.
Run `sha256sum -c SHA256SUMS` from this directory to check the record.

## Exact images and packaging

The source reference before this checkpoint is signed commit `c825e88`.

| Image | Bytes | SHA-256 |
|---|---:|---|
| `uos128.prg` | 8,677 | `eee5097603657c87a50fdd100f90d528d8008eecda0ca7ed7e83b6c7bf082acf` |
| `boot.prg` | 258 | `f4babe887e041ea6c1a0c1219061f3cdd3ef8a61ec40c6c133dbb423f7f88ffd` |
| `calc.prg` | 2,573 | `7c7e6f1a33aa2e0cb762c12ab970e4cc0bf16f05fa8dbddab6fa3d2b939f56ca` |
| `browse.prg` | 3,418 | `4ad53ec06a051029e72ffeed374922dcfa205fde24fd2f9c432ef0fe1bae334f` |
| `uos128.d64` | 174,848 | `267b4294fddbf07173ea867f5fe45b9495432e495e8a83f0b7f642a041eb8794` |

Kernel code/data ends at `$3775` exclusive, leaving 139 bytes before the
ownership tables. Calculator and browser each reserve 16 bank-0 pages.
Calculator history uses two bank-1 pages; the browser cache uses 37 pages.
The file mailboxes still end at `$3de3` inclusive. The heap's total managed
capacity remains 442 pages, before application/workspace allocations.

The [isolated package report](package/report.json) records five byte-identical
images, correct BAM free counts and the allocated native boot sector. c1541
extracted U, CALC and BROWSE and matched every byte. All 18 legacy images
match the reference commit. [verify.py](package/verify.py) accepts a repository
and a fresh output directory; it rebuilds copied source without writing the
repository's target directory.

## CPU and fault models

All reports below passed on the recorded kernel/app hashes. Tests execute the
assembled code against independent CPU, sector, file and console models.

| Report | Coverage |
|---|---|
| [Directory](cpu-directory.json) | 18 cases: three geometries, deleted/empty/locked/full-name entries, page bounds, malformed links, bounded cycles, shared command ownership, foreign channels, reentry and uncertain-close retention |
| [Browser](cpu-browser.json) | Eight workflows: complete screens, binary/tiny/empty previews, paging and device prompt, app discovery/handoff, D71/D81 source context, partial-read errors, embedded-name rejection, all 296 root-D81 entries and 16-bit selection |
| [Files](cpu-files.json) | 93 ownership, extent, transfer and fault cases, including successful/failed replace/workspace cleanup with unrelated resources preserved |
| [Apps](cpu-apps.json) | 52 manifest, ABI, loader and lifecycle cases; nested-stack replace/workspace exits, stale-action clearing and invalid source-format rejection |
| [Calculator](cpu-calc.json) | 11 arithmetic cases/96 events, 40 results with 32 retained, complete screens/history, export and reopen comparison, error/cancel/existing-name protection, 192-byte maximum export and all three source formats |
| [Heap](cpu-heap.json) | 692 calls, 50 boundary transfers, 1,608 interrupt attempts, 442 managed pages |
| [Observer](cpu-capture.json) | 19 bounded RAM/VDC capture and restoration/fault cases |

The full-capacity D81 model covers cache bounds and navigation. It is not a
physical large-directory performance result. Each directory page currently
rewalks from the root; scanning 37 pages can require 703 directory-sector reads,
plus PRG extent/header probes. Persistent cursors and media identity remain open.

## Emulator results

| Run | Outcome |
|---|---|
| [D64 / true 1541](emulator-d64/report.json) | PASS: complete browser/app/view/save/return workflow on drive 8 |
| [D71 / true 1571](emulator-d71/report.json) | PASS: boot D64 on drive 8, data/apps on drive 9/D71 |
| [D81 / true 1581](emulator-d81/report.json) | PASS: boot D64 on drive 8, data/apps on drive 9/D81 |
| [Native file regression](emulator-files/report.json) | PASS: 66,053-byte copy/reopen, file types and exact small extents, cleanup, D64 disk full with original filler preserved |
| [Native workspace/calculator](emulator-workspace/report.json) | PASS: existing memory, calculator, export/error and complete-screen workflow |

The [five-suite report](regressions/report.json) requires all build hashes
to remain unchanged throughout the run. These suites ran sequentially.

Each browser workflow compares 12 complete VIC/VDC frame pairs, inspects
257-byte/one-byte/empty files, rejects a bad CRC before its marker instruction
can execute and launches the real calculator under the filename NUMBER.
The calculator computes 42 and saves BROWSAVE as exact bytes `34 32 0d`.
c1541 independently verifies the export and every nonempty SEQ fixture.
Returning reloads BROWSE from boot device 8 with the selected data device and
format preserved. The final workspace has no app/file resources left; native
comparison verifies both protected 8 KiB allocations and CPU capture checks
an independent 2,000-byte prefix of each before release.

Ownership-table observations separately confirm free pages/slots at the browser,
calculator, restored workspace and final release. The calculator gets the
browser's 37 cache pages back before allocating its two history pages.

## Physical C128 / Ultimate II+

The [final hardware report](hardware/report.json) passed on the reference
C128/Ultimate II+ at `192.0.2.237`, using a private D64 on drive A/IEC 8 in
1541 mode. All 12 VIC/VDC frame pairs matched. The test verified app discovery,
CRC rejection, renamed-calculator launch, source-device save, browser return,
protected workspace data and complete owned-memory/file cleanup.

After restoring the live legacy desktop, the test retrieved the complete
174,848-byte closed disk through Ultimate DOS. Its SHA-256 is
`453854b662977c5be2ed1f7ae0106e37133e18388a2a6e4bc97d0585a1546e4f`. An independent sector-chain reader matched
all 20 files, including the empty file's zero stored bytes. c1541 separately
matched every nonempty file (19), including U, BROWSE, NUMBER, BADAPP and the
exact `42` + CR history export. The native boot sector was unchanged.

The legacy desktop was live after readback, with its nine-byte settings record
and both DOS paths restored. Drive B/IEC 9 remained enabled in 1541 mode with
no image; soft IEC 10 and the disabled printer configuration were preserved.
No physical D71/D81 result is claimed. The embedded-name regression is CPU
coverage; the physical run exercises the corrected image's ordinary filenames.

Test quiet intervals were 60 seconds for boot, 30 for directory/app actions,
four per ordinary key and two before captures. Recorded host event times include
these intervals and are not application-latency benchmarks. The
[earlier physical run](before-filename-validation/hardware/report.json) also
passed, but belongs to the pre-filename-fix browser image.

## Retained test failures

[Before the PETSCII oracle correction](before-petscii-oracle/) retains D64/D71
runs and the old host/model sources. Their first 128-byte preview showed
correct file data and hex values, but the expected printable column used the
wrong screen codes for PETSCII `$60..$7e`: 31 cells differed. The real native
console produces codes `$40..$5e` for those bytes. Correcting both the host
screen oracle and CPU console model required no product-image change. The
corrected pre-filename runs use the same recorded product hashes.

[Before the ownership oracle correction](before-ownership-oracle/) retains
the next D64 failure and a concurrent D71 connection loss. The D64 test
incorrectly treated N_FREE0/N_FREE1/N_SLOTS as live counters. These are N_STATS
snapshots; the failure dump already shows the real calculator. The final
test reads the allocation tables independently and retains those bytes.
The D71 run ended when its VICE monitor connection closed, with no usable
failure RAM capture. Its exact cause is unestablished. Sequential D71/D81
reruns passed; no product change was made for that connection loss.

[Before filename validation](before-filename-validation/) preserves a later
product bug and its regression: selecting SEQ name `41 a0 42` opened the
different file named `41` and displayed its `FIRST` contents. The browser had
stopped at the first shifted-space byte instead of trimming trailing directory
padding. The fix copies the complete stored name and trims only trailing `$a0`.
The stream API then rejects an embedded unsupported byte before I/O. Separate
SEQ and PRG regressions ensure neither byte inspection nor app discovery uses
the shorter alias. Only BROWSE and the packaged D64 change for this fix;
kernel, boot and calculator hashes remain the same.

Discovery deliberately checks only a readable prefix. The bad-CRC fixture is
shown as APP and then rejected by the full loader; an APP label is not a claim
of image integrity or ABI compatibility. Neither the three emulator formats
nor a physical D64 run qualifies all IEC devices, physical D71/D81 drives,
partitions, REL/VLIR, removed media or recovery after uncertain cleanup.
