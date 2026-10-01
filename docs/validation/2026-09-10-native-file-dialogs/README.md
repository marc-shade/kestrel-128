# Native shared file dialogs — qualified checkpoint

The editor's shared Open/Save As picker passes CPU qualification, all ten
native emulator workflows, complete physical USB and IEC workflows, and a
clean package rebuild. All five captured documents retain the exact 66,056
edited bytes while the picker has focus. Independent readback matches nine
USB files and all four files on the physical IEC data disk. Both hardware
workflows restore the deployed desktop, settings and DOS paths; the IEC
workflow also restores its initially empty data drive.

## Behavior and memory

**Tab** in either filename field opens the picker. It shares Files and Apps
navigation source for IEC D64/D71/D81 directories and Ultimate folders, parents,
DOS contexts and complete names. Selection returns to an editable field;
**Esc** cancels and **S** in Save As chooses the current folder or IEC device.
The editor still confirms before discarding dirty work and creates files
exclusively, then reopens and compares every saved byte.

The foreground library keeps the caller's document, cursor and viewport
allocated. It borrows and restores the desktop browser's complete path,
selection and preferences. It closes its own directory cursor and frees its
own cache handles. A failed close retains ownership and prevents a successful
selection until checked cleanup succeeds.

The editor lends four idle 512-byte transfer buffers to the picker and
invalidates its two read caches before repainting afterward. Ultimate names
use 256-byte records with separate lengths. Two eight-entry pages require
4 KiB: 2 KiB in those buffers and eight additional heap pages. IEC uses
32-byte records, with lazy allocations for larger directories. Memory failure
returns to the unchanged document and field.

The editor PRG is 20,095 bytes, with 79 allocated pages and an assembly guard
at that limit. The bank-0 workspace block moves from `$c000` to `$df00..$feff`
to leave larger contiguous ranges for 4 KiB document chunks. The heap still
contains 426 pages. Both 8 KiB workspace blocks, the editor and seventeen
document chunks consume 415 pages, leaving enough for the Ultimate picker.
The banked document model itself is unchanged.

ABI 1.5 supplies the existing directory, heap and file operations. The editor
now requires minor version 5. This is a source library shared with browser
navigation; it does not add a resident GUI entry or a dynamic module loader.

## Build and CPU evidence

`images.json` pins all six native images. `verify-package.py` rebuilds a
private copy of the saved source, compares the PRGs, disk and normalized
listings, and extracts all four disk files both directly and with `c1541`.
Boot and calculator PRGs, and all 18 legacy images, retain the bytes from
`fb9fd916de43b35bd3bd45927f190528bce17467`.

All 18 CPU suites passed on the initial picker build. A final six-byte fix
makes an explicit F8 device preference also carry the editor's backend.
The editor, Ultimate editor, redraw and file-dialog suites then passed again
on the final image. `cpu-run` and `cpu-followup` preserve both runs and their
image identities; the top-level CPU reports select the follow-up where one
exists. The earlier editor image is retained inside the initial emulator's
system disk and separately as `initial-emulator-editor-d64/editor.prg`.
The package audit also removes exactly those two F8 instructions in a second
private source copy and reproduces all six baseline images. This pins the
difference between the baseline and follow-up runs to that six-byte fix.

The eleven final picker flows cover:

* D64, D71 and D81 selection/cancellation, dirty Open confirmation and raw PRG
  load-address preservation, followed by verified SEQ Save As.
* Quoted Ultimate folders, empty folders and full raw filenames, including
  bytes that must be sanitized only for display.
* Cancelled scans, missing directories, retained cursor-close failure and
  checked recovery without releasing the caller's owner.
* Cache exhaustion without changing the document, field or unrelated pages.
* A 66,056-byte document and both workspace blocks through 300-entry paging,
  ordinal 256, backward paging, a DOS-context change and a complete save.
* All 296 D81 entries, the last one-page cache allocation, 255-byte absolute
  targets, overflow rejection and explicit backend-preference synchronization.
* The physical observer's 256-byte cache decoder exercised against executed
  picker code, covering both borrowed buffers and banked cache records.

The redraw suite compares 1,086 complete frames, including 516 field events.
The decoder case is a CPU-model test of the observer; it is not physical
qualification by itself.

## Emulator and hardware gates

The required emulator aggregate includes boot/workspaces and the file,
browser and editor workflows for D64, D71 and D81. Editor tests use the
complete system disk on device 8 and a separate data disk on device 9. The
D64 data fixture leaves 401 blocks free; the complete saved document needs
261. No app or source-document bytes are removed to make the test fit.

The hardware Ultimate workflow checks native directories beyond ordinal 255,
app dispatch and return, and editor Open/Save As selection. The picker must
keep the complete 66,056-byte document through large-directory paging and
cancellation. Both workspace blocks must survive, and nine closed USB files
must match independent DOS readback before private fixtures are removed.

The physical IEC editor uses private system/data D64s on the Ultimate's
emulated 1541 drives A/B, devices 8/9. Drive B must initially be enabled as
a 1541 on device 9 and empty. The
helper restores it to that state, restores the legacy desktop/settings, and
then reads the closed data disk through Ultimate DOS. Direct file-chain
decoding and `c1541` extraction must agree with all three fixtures plus the
complete saved file.

`verify-dialogs.py` reconstructs each complete document from all seventeen
owned 4 KiB chunks captured while the picker has focus. It compares the
logical bytes across the gap with the independently specified edited file.
It also decodes physical picker cache records and compares their full names,
positions and both screens against separately recorded directory listings.
`verify-directories.py` retains the standalone browser's independent checks.

Hardware input uses the ROM GETIN queue and programmable-key expansion;
these are not physical keyboard-matrix or mouse tests. Timing includes
declared quiet intervals and host observation. CPU captures are the RAM
authority. Direct DMA disagreements are retained and compared separately
with the installed reference ROMs; unmatched bytes must remain unexplained.

The completed USB run records 55 frame pairs and 458 CPU captures. The
standalone browser contributes 19 independently checked pages; the editor
picker contributes seven, using both its borrowed buffers and banked cache.
All nine files match closed-file readback, all 16,384 workspace bytes match,
and the private folder, DOS paths and desktop are restored.

The completed IEC run records 23 frame pairs and 120 CPU captures. It preserves
both workspace blocks through native full-block verification and independent
2,000-byte captures from each block. The function-key table's complete 256
bytes are restored, and all owned memory and file resources are released.
The independent 174,848-byte D64 readback contains exactly NOTE, EMPTY, LARGE
and SAVED, including all 66,056 saved bytes. `c1541` independently extracts the
three nonempty files. The data disk's first sector happened to remain unchanged;
that is an observation, not a requirement for this separate data fixture.

Observed large-file Open, verified Save As and fresh Open take 38.310, 78.961
and 38.311 seconds over USB; the IEC run records 346.834, 537.490 and 295.961
seconds. These include quiet intervals and host monitoring. The first IEC Open
also includes one successfully retried read-only RAM observation timeout.
The completed IEC log records no TCP connection retry or uncertain write.
These are workflow timings, not isolated device-throughput measurements.

The USB run contains seven direct-DMA/CPU disagreements. Six whole samples
match the separately installed reference ROMs. One direct sample contains
three bytes at `$6f45..$6f47` that match neither the CPU capture nor those ROM
bytes. They are retained without assigning a cause. The CPU capture of the
complete 255-byte path field and both corresponding screens match the expected
field. `hardware/rom-observations.json` records every differing byte and the
reference ROM hashes.

The completed IEC run adds three DMA/CPU disagreements, all whole samples
matching reference ROMs, with no additional unexplained bytes. Across the
completed emulator and hardware workflows, `artifact-verification.json`
audits 995 CPU captures, 2,388 IRQ chunks and 186 frame pairs. Earlier interrupted
attempts remain separate from these successful-run totals.

## Retained earlier attempts

`initial-emulator-capture-interruption` records a harness assertion after
correctly reaching the large-document Save As picker. The helper requested
4,096 bytes from an observer limited to 2,000 bytes per call. Capturing each
document chunk in supported parts fixed the helper. The complete D64 run
then passed in `initial-emulator-editor-d64`, before the final F8 change.
`initial-sandbox-fixtures` contains the fixtures prepared before a sandbox
socket restriction prevented emulator startup. None of these attempts made
hardware writes.

`initial-hardware-iec-transport-interruption` retains an unsuccessful physical
IEC attempt and its exact host helpers. Its 25-second request timeout expired
while restoring 128 bytes at `$3f80` after a CPU capture. Acceptance of that
RAM write is unknown; it was not replayed. The report contains 87 restored
captures and one capture whose scratch restoration was not verified. The run
stopped before Save As wrote a file and does not qualify the complete document.
The helper restored the desktop, settings and initially empty drive B. The
next IEC run used new private disks, a 60-second request timeout matching the
USB workflow, and explicit reporting of uncertain host writes.

`second-hardware-iec-transport-interruption` retains that run. It stopped after
26 restored captures when clearing the idle keyboard-expansion index at `$00d2`.
The original report conservatively classified the one-byte write as uncertain.
The retained traceback locates its timeout in `socket.connect`, before any HTTP
request bytes were sent. The desktop, settings and drive B were restored again.
Increasing the timeout alone did not prevent the connection failure.

The corrected IEC host client establishes TCP explicitly and permits at most
three connection attempts before sending a request. It disables implicit
reconnection once sending begins. Send failures, response timeouts, disconnects,
partial responses and HTTP errors stop the workflow without replaying writes.
`host-transport.json` records eight fault-injection cases with no hardware I/O.
The final IEC workflow passes after starting again with fresh disks; all native
product images remain identical across the physical attempts. The fault-injection
tests exercise connection retries; no such retry was needed in the passing live run.

## Recomputing the final archive

The default audit mode is read-only. Package rebuilding uses a temporary
directory; ROM comparisons use separately installed ROMs. The `harness`
directory preserves test/helper source for review. Full workflow reruns
require the repository, its emulator/hardware tooling and the recorded
dependencies; they are separate from these offline artifact audits.

From this directory, verify the manifest and recompute the saved audits:

```sh
sha256sum --quiet -c SHA256SUMS
python3 verify-package.py
python3 verify-directories.py
python3 verify-dialogs.py
python3 verify-rom-observations.py /path/to/C128/roms --folder hardware
python3 verify-rom-observations.py /path/to/C128/roms --folder hardware-iec
python3 verify-artifacts.py
```

Graphical widgets, pointer/focus events, dynamic modules, scheduling,
clipboard/selection/undo/find, media recovery, additional storage backends,
desktop migration and the wider application/expansion roadmap remain open.
The D71/D81 editor results are emulator evidence; separate physical drive and
expansion combinations still need their own qualification.
This milestone does not complete uOS or R3.
