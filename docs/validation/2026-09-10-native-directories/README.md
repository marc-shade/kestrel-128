# Native Ultimate directory cursors and browser — 2026-09-10

This checkpoint adds ABI 1.5 owned Ultimate directory cursors and their native
Files and Apps consumer. The complete OS goal remains open: shared file dialogs,
GUI migration, scheduling, the app suite and expansion support remain on the
[roadmap](../../IMPLEMENTATION-ROADMAP.md).

All 17 CPU suites, two targeted canonical-path follow-ups, ten emulator
workflows, the complete physical C128 workflow and the package/artifact audits
passed. Physical evidence was archived at `2026-09-10T07:51:04.905444+00:00`.
The preceding interrupted hardware attempt is retained separately below.

## Behavior and ownership

**F** cycles D64/D71/D81/ULT. In ULT, **Enter** opens folders or selected files,
**P** selects the parent, **G** edits an absolute directory path, **Tab** chooses
DOS context 1/2 and **N/B** pages eight entries. **I** shows raw file bytes and
**L** retains the absolute app-launch field. Esc cancels an active scan while
retaining the old page; at idle it returns to the workspace.

The browser retains all filename bytes, uses the canonical returned path and
rejects joined paths longer than 255 bytes before I/O. It searches for the
selected full filename after an app returns, so creating a history or document
file cannot silently move selection to another entry. A deleted selection
falls back to page one. Forward pages continue one READ_DIR; backward or
reopened pages rescan to the 32-bit entry ordinal. An inactive buffer prevents
a partial or failed scan from replacing the visible page.

The cursor uses format 3/mode 2 through existing owned OPEN/READ/CLOSE entries.
READ requires a 512-byte buffer and returns one attribute/name packet of
2–256 bytes, or zero at EOF. One cursor may exist. Pending directory packets
reserve the shared UCI transaction across both contexts, while IEC transfers
can continue. EOF retains ownership until CLOSE. CLOSE cancels only its owned
transaction, confirms idle, restores the original CWD and compares every byte
through GET_PATH. Failed cleanup retains ownership. Owner release handles the
directory before another Ultimate stream. No failed transfer is replayed.

The firmware has no explicit directory CLOSE or idle snapshot-owner query.
The native service claims the selected context's idle directory snapshot for
uOS; it preserves foreign open files and active UCI transactions, but cannot
preserve an undetectable foreign idle snapshot. Background clients still need
a shared broker. [The API guide](../../NATIVE-ULTIMATE.md) records the complete
contract and protocol references. Source inspection used revision
`a01c04e8267a0d916b7203cb34dcf1127f75981d` of
[`dos.cc`](https://github.com/GideonZ/1541ultimate/blob/a01c04e8267a0d916b7203cb34dcf1127f75981d/software/filemanager/dos.cc);
the installed cartridge's exact source revision is not established.

## Memory and images

Main code ends at `$366e`, leaving 402 bytes before `$3800`. The allocator ends
at `$17c6`; service code ends at `$4678`, leaving 904 bytes before the retained
path at `$4a00`. The selected-name buffer is `$3e00..$3eff`, with lengths and a
32-bit ordinal in the existing mailbox. All use already reserved RAM; the
heap remains 426 pages. Browser code/data grows to 7,110 bytes and 28 allocated
pages, retaining the existing 37-page bank-1 cache allocation. Calculator
requires ABI 1.4 and editor 1.3; their PRGs and boot PRG are byte-identical to
preceding signed commit `1a93d06aa9d22970de185be428b8548ed546ac88`.
All 18 legacy product images also match that commit.

| Image | Bytes | SHA-256 |
|---|---:|---|
| uos128.prg | 14593 | `5e0896d8b26a61430b660feb29f68693e503dc8a1495722ed708c9fae85c5ce9` |
| boot.prg | 258 | `f4babe887e041ea6c1a0c1219061f3cdd3ef8a61ec40c6c133dbb423f7f88ffd` |
| calc.prg | 3084 | `8e6a281482706cbae8f7623ed11132e2018a9c7be4eaea36a6d5fe5f3e715265` |
| browse.prg | 7112 | `c3fb0ea873d078db1502a32c531e0242ec6f3f6557ec68a75edf2e45a11b5199` |
| editor.prg | 12202 | `71374b01091b30046d309d207b753e193127c5b0258040891d1bc14d9ef99aa8` |
| uos128.d64 | 174848 | `aa9ca07fc70ef34fdb18cd4c16696aa5266c5b0485f5e97298a4722c0d44ceab` |

The IRQ observer borrows and restores `$3a00..$3bff` and `$3e00..$3fff` while
input is idle. Its existing host tests compare restoration of every borrowed
byte, including the new retained-name buffer. It rejects those buffers as
capture sources. Physical directory cache and state checks use CPU captures;
the retained-name observation at `$3e00` is explicitly a direct below-ROM RAM
read. App returns and independently checked cache entries also verify selection.

## Physical results and timing

The independent DOS oracle contains 1,096 entries in `/Usb0/c64/#-a/`.
The native browser completed 32 Next actions, and the complete cached names
and both screens at ordinals 0, 256 and 248 match independent packet captures.
Root, Usb0, parent, private and empty-folder navigation, raw byte preview,
255-byte field editing/cancellation, missing/corrupt app recovery and both
DOS contexts passed. Nineteen native directory pages were reconstructed from
CPU cache/state captures and independent directory listings.

A calculator launched from the listing saved and verified `HISTORY`, refused
an existing file and returned to the same full filename. The editor completed
all 13 storage states, including a 66,053-byte Open, an edit at byte 65,537,
a 66,056-byte verified Save As and a complete reopen on DOS2. Creating files
moved `TEXT EDITOR.PRG` from ordinal 6/page 1 to ordinal 8/page 2; app return
selected that same name. Seven post-creation page/order checks match the final
independent DOS listing after filtering to each recorded stage's membership.

All 16,384 workspace bytes, all 256 programmable-key bytes and complete
resource release were checked. The legacy desktop, settings and both DOS paths
were restored. All nine closed files were independently read back and compared,
then the private files, empty subfolder and enclosing folder were removed.
The complete physical run has 45 frame pairs, 258 CPU captures and 533 IRQ
chunks. Combined emulator/physical audits cover 138 frame pairs, 483 captures,
1,177 IRQ chunks and 253 direct/CPU RAM observations; the initial interrupted
run's three boot captures remain separate.

| Operation | Observed seconds |
|---|---:|
| USB calculator launch | 3.222 |
| USB editor launch | 11.338 |
| Next page, median of 32 actions | 7.281 |
| Open 66,053 bytes | 38.310 |
| Save, close, reopen and verify 66,056 bytes | 78.884 |
| Reopen saved file on DOS2 | 38.307 |

These workflow times include host requests, quiet intervals and polling.
Next actions and successful USB launches use a one-second initial quiet;
file operations use 30 seconds before polling. File-operation times exclude
path typing. Missing/corrupt launches take 44.039/41.819 seconds including a
browser reload from the boot IEC disk. These are not isolated throughput or
keyboard-latency measurements. `performance.json` retains the values and event
references. Browser reload caching and further input/drawing performance work
remain open.

## DMA and CPU observations

Seven direct DMA observations differ from their corresponding CPU captures.
Six complete samples match the reference BASIC ROM at the same addresses.
The remaining 256-byte saved-key-table DMA sample matches 254 reference ROM
bytes. At `$8323` and `$839c`, DMA returned `$10`; the reference ROM has `$08`,
while the CPU-captured key bytes are `$0d` and `$c0`. The origin of those two
DMA bytes is not established. They are retained explicitly in the comparison
report; this archive does not claim that every DMA discrepancy is a ROM match.

The independently saved original key table, the CPU capture of the editor's
saved copy, and the restored key table agree in all 256 bytes. Native RAM
checks use CPU captures. `verify-rom-observations.py` reproduces the ROM
comparisons and records both unexplained bytes. Its successful audit means
the archived comparison is consistent, not that the unexplained bytes have
been attributed to a source or that direct DMA is a reliable RAM observer.

## Retained interrupted run

The first physical attempt independently created and read back all six source
files and captured the directory oracles. GET_PATH returned trailing slashes.
Review then found that the new harness's app-return assertion compared that
canonical path with the fixture string without its trailing slash. The run
was interrupted during a host input quiet interval, after eight complete
workspace events and before native USB navigation or app saves. It restored
the legacy desktop and settings and reported no uncertain host writes.
This is retained as an interrupted attempt, not passing directory coverage.

The harness now keeps the canonical private-directory path separately from
the fixture construction path. The complete replacement workflow rechecks
all source bytes and exact private-directory membership before reuse. The
initial report, captures and original harness sources are retained in
`initial-hardware-harness-interruption/` and `source-tests/*-initial.py`.
No product image changed for this correction. The CPU DOS model gained a
trailing-slash mode and an additional folder/parent/preview workflow.

## Qualification and reproduction

All 17 CPU suites passed on frozen images. New coverage includes 37 directory
cases and six complete browser workflows with 132 screen comparisons: empty
and 300-entry directories, 255-byte names/paths, quoted/high bytes, exact file
selection, DOS2, canonical parent paths, cancellation, queued input, stale
positions, missing selections, app saves that reorder pages, malformed replies,
foreign resources, retained abort/restore failures, IRQ/decimal and reentry.
The complete 17-suite CPU run is retained; two targeted runs additionally
check the cartridge's trailing-slash canonical-path convention.
The existing 15 suites include the full editor workflows, shared loader,
verified file writes and 1,086 editor redraw screen comparisons.

The private D64 editor fixture removes its unused calculator before adding
source documents. Its independent BAM preflight excludes directory track 18
and records 265 available data blocks for the 261-block saved copy. The product
disk retains all three apps. `fixture-capacity/` contains the exact generated
fixture, source documents and the capacity report.

The package audit rebuilds the private source snapshot, compares all six
images/listings/layout/symbols, independently extracts all four product disk
files and checks the boot block allocation and app manifests. Default audit
commands are read-only; `--record` is used only when creating this archive.

```sh
python3 verify-package.py
python3 verify-directories.py
python3 verify-rom-observations.py /path/to/C128/roms
python3 verify-artifacts.py
sha256sum --check --quiet SHA256SUMS
```

Live test entry points are in the [browser guide](../../NATIVE-BROWSER.md).
The physical workflow changes only its uniquely named private USB fixture and
the test mount, preserves unrelated workspace allocations, restores the legacy
desktop/settings/DOS paths, independently reads back all closed files and
removes the private directory after verification. Read-only navigation past
entry 255 uses the existing `/Usb0/c64/#-a/` directory. These results qualify the
recorded C128/Ultimate II+ setup, not every cartridge or firmware revision.
