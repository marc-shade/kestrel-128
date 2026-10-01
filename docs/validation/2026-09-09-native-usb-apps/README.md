# Native shared loader and USB applications — 2026-09-09

This checkpoint adds ABI 1.4 owned IEC/Ultimate application loading, an absolute
USB app path field in Files and Apps, and verified history export beside a
USB-loaded calculator. The editor and boot PRGs are byte-identical to the
[preceding redraw checkpoint](../2026-09-09-native-redraw/README.md).
The complete OS goal remains open; native USB directory navigation, shared
file dialogs, the graphical desktop, scheduling and expansion/app parity are
still on the [roadmap](../../IMPLEMENTATION-ROADMAP.md).

All 15 CPU suites, ten emulator suites and the complete physical C128 workflow
passed. Independent audits compare the archived screens, app headers, banked
RAM, saved files, cleanup and exact images. A fixture-capacity failure, a
physical screen-oracle failure and a host-request timeout are retained below,
with their corrections and recovery evidence.
Work began September 9 EDT; final physical evidence was archived at
`2026-09-10T05:11:33+00:00`.

## Behavior and memory

Press **B**, then **L** to enter a raw absolute app path such as
`/Usb0/Tools/Calculator.prg`. **Ctrl-U** clears the field, **Del** edits,
**Tab** changes DOS context 1/2, **Enter** launches and **Esc** cancels.
The field retains 255 bytes and clips only its display. It preserves the IEC
cache and selection, and changes only two rows on each screen. It does not
list USB directories or navigate folders.

Both loader backends validate the same manifest, exact extent and CRC before
entry, reserve and zero the declared allocation, and close the loader stream
before executing the app. Loading needs one of the two shared stream slots.
It may share an owned same-device IEC command lease or coexist with a stream
on the other Ultimate context; foreign resources remain preserved. Failed
cleanup retains ownership and the first loader result.

`N_APPFORMAT=3` selects Ultimate; `N_DEVICE` then means DOS context 1/2 and
`N_NAMELEN`/`N_UPATH` select the raw absolute path. `N_BOOTDEVICE` at `$3d2d`
retains the independent IEC boot device. Existing public entry addresses and
the `$6000..$bfff` app slot are unchanged. Source-dependent apps must inspect
`N_APPFORMAT`; accepting an older manifest does not prove an app handles USB.

The calculator creates history beside its USB image, refuses existing names,
and checks CLOSE, reopen, all bytes and final CLOSE before showing success.
The leaf is at most 16 bytes and the complete path at most 255. Uncertain
CLOSE retains the handle; another save first requires checked cleanup. Neither
failed data transfers nor writes are replayed.

The main kernel ends at `$3210` exclusive: 264 fewer bytes than preceding
`$3318`, leaving 1,520 bytes before the page tables. The low/service regions,
boot staging and 426 managed pages remain unchanged in extent. Calculator
code/data still reserves 16 pages; browser now reserves 17, one more than before.
Editor remains 48 pages. Service addresses linked to the changed main region
may change bytes; only the boot and editor PRGs are claimed byte-identical.

## Exact images

| Image | Bytes | SHA-256 |
|---|---:|---|
| uos128.prg | 14593 | `c886919042d061dd69aed604305f5cf5493055749ed029714ab52668605448b5` |
| boot.prg | 258 | `f4babe887e041ea6c1a0c1219061f3cdd3ef8a61ec40c6c133dbb423f7f88ffd` |
| calc.prg | 3084 | `8e6a281482706cbae8f7623ed11132e2018a9c7be4eaea36a6d5fe5f3e715265` |
| browse.prg | 4149 | `d4248b9222beb628c24e09158a8b69ec187b788d68f73285b42b136ba39abd4a` |
| editor.prg | 12202 | `71374b01091b30046d309d207b753e193127c5b0258040891d1bc14d9ef99aa8` |
| uos128.d64 | 174848 | `531e6f3c7480d4292113089aeada0a6ce1427c053c07fdfdcaf870101bca4029` |

`verify-package.py` rebuilds the archived source in a private temporary tree,
compares all six images, listings apart from comment headers, layout and
symbols, and extracts all four disk files through independent sector parsing
and c1541. It checks the reserved boot block and each app's manifest. Eighteen
legacy images and the boot/editor PRGs match preceding signed source commit
`0fb375e1c50aac87941422f24e4c73a82d72efc1`.

## CPU qualification

All 15 CPU suites passed on the frozen images. `cpu-run/` preserves their logs,
individual reports, durations and the launch manifest; root `cpu-*.json` files
are exact copies. The models execute assembled code and inject KERNAL/UCI
responses at their external interfaces.

| Area | Coverage |
|---|---|
| Heap, relocation, capture | Ownership/generation, bank boundaries, IRQs, staging reuse and bounded observers |
| IEC app loader | 52 valid/rejected image, error, flag, stack and cleanup cases |
| Owned IEC files | 93 stream, extent, geometry, channel and failure cases |
| Directory/browser | 18 directory cases and eight complete browser workflows |
| Ultimate streams | Six groups including fragmented packets, 16 MiB extent carry, foreign resources and write verification |
| Calculator | Arithmetic, retained history, complete screens and verified export on all IEC geometries |
| Banked document/editor | Four document groups, nine full IEC editor workflows and three Ultimate workflows beyond 64 KiB |
| Editor redraw | 1,086 complete frames; 516 field events without document reads |
| Shared Ultimate loader | 54 cases: both contexts, 255-byte path, 24 KiB image, EOF/CRC, IRQ/decimal, foreign resources, retained close, shared IEC lease and occupied slots |
| USB apps | 1,002 field frames; real dispatcher, missing/corrupt images, verified history, failed write/reopen/close and recovery, full-length source/output paths |

The CPU screen checks model ROM output behavior; the emulator and physical
checks below use the actual ROM and complete VIC/VDC buffers.

## Retained failed observations

`initial-fixture-disk-full/` and `initial-regressions/` retain the first emulator
attempt. Native boot/app loading passed, then the private D64 stream fixture
ran out of space while making its 66,053-byte copy. Its closed files used 405
blocks; after the reserved boot block, only 258 remained for a 261-block copy.
The disk BAM reports zero free data blocks and the output is unclosed. The source
file remained exact. This is a fixture-capacity failure, not a passing copy.

The fixture now removes unused BROWSE and EDITOR images from its private disk
and checks capacity before boot. It still uses the frozen kernel and a checked,
disk-loaded stream client. The separate nearly-full disk continues exercising
actual disk-full detection and preservation of existing data. Product images
were not changed for this correction. The successful native boot suite from
the first runner is retained; only the nine remaining suites were rerun.
The byte audit also corrected the new capacity guard to exclude directory
track 18 from usable file blocks. `fixture-capacity-preflight.json` regenerates
the successful fixture byte-for-byte and records 324 available data blocks
for the 261-block copy. `source-tests/native_files_check-emulator-run.py`
preserves the helper used by the completed emulator run; the final helper
is in `oracle/`. This guard correction changes no fixture or product bytes.

The first physical run stopped while checking the path for the corrupt-image
fixture, after the calculator save and missing-image return had passed. The
browser correctly retained the previous `DISK I/O ERROR` on row 19 while editing
only rows 20/21. The harness had expected row 19 to become blank. Both captured
screens exactly match the prior error plus the new field; only row 19 differs
from that original expectation. The harness now carries the displayed browser
error into field comparisons. This correction changes no product image.
The failed report, original harness, raw frames and independent cleanup/readback
evidence are retained separately from the complete replacement hardware run.
One one-byte DMA observation in that failed run differs from the authoritative
CPU capture and equals the corresponding reference BASIC ROM byte. That sample
is too short to identify its origin independently. Both bytes and the ROM
comparison are retained; the CPU capture correctly records USB field mode 2.

The replacement run passed all USB app checks and opened the complete large
document, then a host HTTP request timed out while injecting Backspace after
typing `C128`. The diagnostic snapshot still showed the last consumed key as
`8`; it does not establish whether a pending host write might later have arrived.
The harness restored the desktop and settings and did not replay that input.
`initial-hardware-host-timeout/` retains the report, diagnostics, frames and
separate ROM comparisons.

The successful final run rechecked all six existing source fixtures and both
completed outputs before removing only those outputs. It then restarted the
entire native workflow from a fresh boot, using the same verified source files.
This preserved the source fixtures while keeping every native check. Its host request
timeout is 60 seconds, up from 25; failed RAM writes record their address,
length and payload hash and remain unreplayed. The final evidence includes
the prior output readbacks, complete restarted workflow and final directory removal.

## Emulator and physical qualification

Ten emulator suites passed: the native workspace/app test and stream, browser
and full editor workflows on each D64/D71/D81 geometry. The three stream copies
total 198,159 independently compared bytes. Editor saves
contain 66,056 bytes, including the edit beyond 64 KiB.

The successful physical run uses DOS context 2 for the USB calculator and
context 1 for the USB-loaded editor. It checks the complete quoted 255-byte
field, deletion, clear and cancel; calculator arithmetic and verified export;
existing-file refusal; missing/corrupt image rejection; and the boot-browser
return. The unchanged editor then opens and edits mixed bytes, preserves the
document after a failed Open, saves and reopens 66,056 bytes, refuses replacement,
and reopens the result through DOS context 2.

It independently compares all nine closed USB files, including both app images,
the deliberately corrupt fixture, the source documents and all three outputs.
Both full 8 KiB workspace blocks remain exact. All native memory/files are
released; 256 function-key bytes, the legacy desktop/settings and both DOS
paths are restored. The private files and directory are removed.

The successful physical evidence contains 32 complete
VIC/VDC frame pairs, 116 CPU captures and
257 bounded IRQ chunks. Across that run and the seven
emulator workflows using the CPU observer, the audit compares
125 frame pairs, 341 captures,
901 IRQ chunks and 166 paired RAM observations.
The three stream suites use separate emulator RAM/file evidence. Counts for the
retained failed physical runs are reported separately in `artifact-verification.json`.

| Physical operation | Observed seconds |
|---|---:|
| Load USB calculator and reach input | 3.224 |
| Load USB editor and reach input | 11.339 |
| Open 66,053 bytes | 38.309 |
| Save, close, reopen and compare 66,056 bytes | 80.935 |
| Reopen through DOS context 2 | 38.314 |

`performance.json` records the measured events and quiet/poll intervals.
These are complete workflow times with host observation cost. Returning from
an app still reloads and scans the IEC boot browser; direct USB launch does
not remove that cost.

One one-byte DMA observation in the successful run differs from the authoritative
CPU capture and matches the corresponding reference BASIC ROM byte. That sample
alone cannot establish its origin. The raw bytes and comparison with separately
installed reference ROMs are in `rom-observations.json`.

## Evidence and verification

The physical harness creates one uniquely named USB directory, retains two
independent 8 KiB workspace allocations, and tests USB app sources separately
from data preferences. Its final evidence includes complete closed-file
readback, all owned-resource release, restored function keys, DOS CWDs,
legacy desktop/settings and removal of its private files.

Use `python3 verify-package.py` and `python3 verify-artifacts.py` from this
folder to compare archived evidence. `verify-rom-observations.py ROM_FOLDER`
compares any DMA/CPU disagreements against separately installed C128 BASIC ROMs.
Add `--folder initial-hardware-field-oracle` to repeat the failed run's separate
ROM-byte comparison.
Use `--folder initial-hardware-host-timeout` for the later timeout run.
Default verifier runs are read-only; `--record` is used only while assembling
this new checkpoint. `SHA256SUMS` covers every sealed file except itself.
Tool versions are recorded in `tool-versions.json`.
The hardware/emulator harness still depends on the separately installed `cbm`
helper named and hashed there. Source snapshots make the executed checks
reviewable; they do not remove that existing test-environment dependency.

The physical reference is one C128/Ultimate II+ combination. Emulator D71/D81
results do not qualify corresponding physical drives. CPU fault injection does
not establish behavior for every firmware or expansion. Workflow timings
include their documented quiet/poll intervals and host observation cost.
