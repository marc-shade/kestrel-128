# Native owned IEC files and calculator history export — 2026-09-09

This checkpoint adds native ABI 1.1 file handles and a product client: the
calculator exports its oldest-first result history to a new SEQ file, closes
it, reopens it and compares every byte. Existing names are preserved. Application
exit closes owned streams before releasing executable and banked memory.

The [file ABI](../../NATIVE-FILES.md) describes the exact contract. This is a
foreground backend with two streams and explicit D64/D71/root-D81 geometry.
Native directory enumeration, file dialogs, loader/backend unification,
cartridge integration, REL/VLIR files, removable-media identity and recovery
remain open. The [completion roadmap](../../IMPLEMENTATION-ROADMAP.md) remains
the broader acceptance checklist; this checkpoint does not complete R3 or the OS.

## Final images

The source reference before these changes is signed commit
`d27e9e1e4e41cfb54d29df1940c15b7985e4c59e`.

| Image | Bytes | SHA-256 |
|---|---:|---|
| `uos128.prg` | 8,677 | `2b5fefc6f4334ca59039c2b9ac981080489ec4d4972f8855650660d85b31ef09` |
| `calc.prg` | 2,570 | `126aafb50536a6c635cd42731676402336a8c94066a16a774ceeb81297474612` |
| `boot.prg` | 258 | `f4babe887e041ea6c1a0c1219061f3cdd3ef8a61ec40c6c133dbb423f7f88ffd` |
| `uos128.d64` | 174,848 | `3b3dfa3015f347032a4716375582ab8bb2f1ef0682ef88fe46a31f26fc3cc0b7` |

Kernel code/data ends at `$35d4` exclusive, leaving 556 bytes before allocator
metadata at `$3800`. File mailboxes/descriptors end at `$3de3` inclusive. The
calculator has a 2,568-byte payload and reserves 16 pages. The existing 442-page
banked heap remains available outside those reservations. Additional kernel
services will need an explicit code-space plan.

The [isolated package check](package/report.json) rebuilt four byte-identical
images from copied source, independently checked BAM free counts and the
allocated boot block, and extracted both PRGs with c1541. All 18 legacy images
match the reference commit. [verify.py](package/verify.py) accepts a repository
and a fresh output directory; it never rebuilds the repository's own target.

## CPU and fault-model results

All reports below passed. Kernel/app reports record the final image hashes;
the separate observer report records its probe hash. The file tests execute
assembled 6502 code against an independent file/sector model, rather than
substituting a host implementation for the native API.

| Report | Coverage |
|---|---|
| [Native files](cpu-model.json) | 89 cases: binary/empty/tiny files; exact sector boundaries; 32-bit positions; ownership and stale generations; channel conflicts; corrupt geometry/chains; partial/deferred output; DOS errors on close; cleanup and retained ownership after uncertain close |
| [Calculator](cpu-calc.json) | 11 arithmetic cases/96 arithmetic events; 40 history results with 32 retained; paging and both complete screens; export, reopen comparison, existing-name protection, cancel and partial-write error; maximum 192-byte export |
| [App lifecycle](cpu-apps.json) | 48 manifest, IEC and lifecycle cases, including ABI minor compatibility and preservation of unrelated resources |
| [Heap](cpu-heap.json) | 692 calls, 50 bank-boundary transfers and 1,608 interrupt attempts; 442 pages/113,152 bytes managed |
| [Native observer](cpu-capture.json) | 19 RAM/VDC capture and fault cases, complete frame restoration and bounded failure |

## Emulator and physical qualification

| Run | Outcome on final images |
|---|---|
| [D64/1541](emulator-d64/report.json) | PASS: complete file workflow and disk-full/preserved-existing-file check |
| [D71/1571](emulator-d71/report.json) | PASS: complete file workflow |
| [D81/1581](emulator-d81/report.json) | PASS: complete file workflow |
| [Native workspace/calculator](emulator-calculator/report.json) | PASS: both memory banks, real app loading, verified history export, existing-name rejection and cleanup |
| [Physical C128/Ultimate II+](hardware/report.json) | PASS: calculator on both displays; complete native file workflow; independent retrieval/comparison of both D64s; legacy desktop, settings and DOS paths restored |

The [D64/calculator](regressions-d64-calculator/report.json) and
[D71/D81](regressions-d71-d81/report.json) regression reports also require all
build hashes to remain unchanged throughout their suites.

The emulator workflow uses x128/VICE 3.10 with true drive emulation. D64 uses
drive 8/1541. D71 and D81 boot their client from drive 8/D64 and use drive
9/1571 or 1581 for data. Each copy is 66,053 bytes, crossing a 16-bit position
boundary. It closes and reopens COPY, compares every byte, rejects replacement,
and exercises SEQ, USR and PRG data (including the PRG load address). Small-file
fixtures include lengths 0, 1, 2, 253, 254, 255, 256, 257, 258, 508 and 509.
The final app-return path closes two remaining owned read streams and releases
the app's memory. c1541 independently extracts the large copy.

The additional D64 disk-full scenario starts with a 662-block FILLER on a
private second disk. It attempts a new file, requires a native I/O failure on
write or close, then independently compares the original FILLER bytes.
The passing run returned native error `$11` with 509/512 bytes accepted on
WRITE, and native error `$11` with DOS 72 on CLOSE. FILLER remained byte-identical.

The physical workflow uses the available C128 and Ultimate II+ at
`192.0.2.237`, drive A/IEC 8 in its existing 1541 configuration, and private
uploaded D64 images. It checks calculator save/verify and existing-name screens
on both VIC and VDC, a 1,557-byte copy/reopen comparison, the small-file fixtures,
and app cleanup. After restoring the legacy desktop, it retrieves both complete
174,848-byte D64 images through raw Ultimate DOS. An independent host sector-chain
reader checks all stored file bytes, including empty files; c1541 cross-checks
every nonempty file. Other drive settings, desktop preferences and original
Ultimate DOS target paths are compared/restored. Private Temp images are retained.

The final hardware run completed without resuming or correcting its report.
It verified 14 files on the file-test disk and the calculator's `PHYSHIST`
containing exactly `42` followed by CR. The saved raw image hashes are:

| Retrieved image | SHA-256 |
|---|---|
| [Calculator D64](hardware/calculator-readback.d64) | `4b3fcf9f0b89514ce7885671471ec7fca85e8388e428d569ad8210d4f8b71f89` |
| [File-test D64](hardware/files-readback.d64) | `bcf7f86937579c31d09ff26fe19fa8f48989f6a9189e0ce2314354ee2cfff779` |

Both images are 174,848 bytes. All 15 expected files passed the independent
linked-sector comparison; 14 nonempty files also matched c1541 extraction. The
empty file has zero stored bytes; c1541's separately recorded 254-byte padding
does not define its length.

Observation quiet intervals are recorded in the reports. They are test-harness
timing choices, not application performance measurements. Physical D71/1571,
D81/1581, other drive models/ROMs and partitions are not qualified by these runs.
The saved Ultimate `version` response identifies REST API 0.1, not a full
firmware revision. No claim of arbitrary firmware compatibility follows from it.

## Retained failures and corrections

These artifacts retain earlier image hashes and failing outcomes. They must
not be mistaken for passing evidence on the final kernel.

1. **Empty and one-byte sequential extents.**
   [The initial emulator run](before-exact-size/emulator/report.json) copied
   66,053 bytes correctly, then read `00 00 02 00` from the one-byte ZERO file.
   [CHRIN](before-exact-size/chrin-trace/report.json) and
   [ACPTR](before-exact-size/acptr-trace/report.json) diagnostics produced the
   same data; EMPTY yielded 254 padding bytes. Independent sector inspection
   established ZERO/CR length 1 and EMPTY length 0. Read OPEN now uses read-only
   U1 directory/chain inspection to establish the exact extent. Empty files
   need no CHRIN. Only an independently measured one-byte file may complete
   without first-byte EOI; larger files require EOI at their exact end. No data
   pattern is stripped. The old source/build and diagnostic runner are retained
   under `before-exact-size/`.

2. **Intermediate 1571 status replies.**
   [First](d71-status-failure/first/report.json) and
   [repeat](d71-status-failure/repeat/report.json) D71 runs failed after 2,048
   and 26,624 accepted copy bytes. A captured reply began `0, OK,00,00` and
   failed the strict two-digit parser. [Longer observation intervals](d71-status-failure/longer-observation-interval/report.json)
   and an [emulated delay before status](d71-status-failure/delayed-status/report.json)
   still failed. A [private diagnostic patch](d71-status-failure/close-only-experiment/report.json)
   skipping only intermediate status reads passed the complete workflow.
   Production transfers now check IEC status on each byte and flush, with DOS
   checked at OPEN, CLOSE and metadata commands. WRITE success means acceptance;
   callers must check CLOSE. The fault model explicitly covers a deferred DOS
   72 error. The underlying drive-firmware/emulator timing cause is unproven.
   Diagnostic source and the earlier `$35d9` kernel are retained here.

3. **Physical DMA observer read ROM instead of app RAM.**
   [The first physical run](before-result-mailbox/hardware/report.json) read
   test-result value 121 at `$60f0`, despite the native mailbox reporting a
   successful 512-byte write. The captured app region matched the BASIC ROM
   view; the [comparison](before-result-mailbox/hardware/failure-rom-view-analysis.json)
   records that evidence. The test-only result moved to `$3d9f`, and physical
   calculator status now uses the CPU bank observer. This was an observation
   failure; it did not establish a product write failure. The legacy desktop
   was restored.

4. **Independent cartridge readback oracle.**
   [A later physical run](before-empty-packet-readback/hardware/report.json)
   completed all native checks but its host EOF assertion rejected a successful
   Ultimate response containing one empty record (code 255, carry clear, empty
   status). The corrected check permits that response while requiring no errors
   or truncated records. The resumed download then exposed c1541 returning 254
   padding bytes for EMPTY. Its original and retrieved data sectors are
   [identical](before-close-status/hardware/empty-sector-comparison.json), with
   final-link count 1 and therefore zero stored bytes. The host chain reader
   now verifies all exact file extents, with c1541 comparison for nonempty files.
   [Completed cached readbacks passed](before-close-status/hardware/report.json)
   after these oracle corrections. That report retains both prior errors and
   qualifies only its earlier `$35d9` image.

5. **Disk-full prefix assertion.**
   [The first final-image D64 run](before-disk-full-oracle/emulator/report.json)
   completed the main file workflow, then correctly returned I/O error `$11`,
   serial status 3 and an accepted prefix of 509/512 bytes on the nearly full
   disk. A host assertion still required full acceptance when the test explicitly
   allowed an error. It now requires a full count only for an expected successful
   write. The failed run is retained; it did not reach the close/preservation
   assertions.

`before-close-status/` also retains the earlier CPU, D64/D81/calculator and
package passes. The regression logs and reports preserve each run's image hashes.
Some retained traceback source lines reflect a later on-disk harness edit;
their recorded mailbox bytes and errors remain the observed runtime results.
The [SHA-256 manifest](SHA256SUMS) covers the archived files, excluding itself
and ignored Python caches. Raw SEQ files retain their Commodore CR delimiters;
captured API responses and c1541 listings retain their original whitespace.

## Primary references

The native KERNAL calls and observer's application scratch region follow the
[Commodore 128 Programmer's Reference Guide](https://www.pagetable.com/docs/Commodore%20128%20Programmer%27s%20Reference%20Guide.pdf).
Disk geometry, U1 access and channel semantics are checked against the original
[1571 User's Guide](https://s3.amazonaws.com/com.c64os.resources/weblog/sd2iecdocumentation/manuals/1571_Users_Guide.pdf),
[1581 User's Guide](https://s3.amazonaws.com/com.c64os.resources/weblog/sd2iecdocumentation/manuals/1581_Users_Guide.pdf),
and [Inside Commodore DOS](https://www.pagetable.com/docs/Inside%20Commodore%20DOS.pdf).
The [1541 User's Manual](https://www.commodore.ca/wp-content/uploads/2018/11/commodore_vic_1541_floppy_drive_users_manual.pdf)
documents the device-wide effect of closing command channel 15; the native
service therefore shares that channel per device and closes it last.
