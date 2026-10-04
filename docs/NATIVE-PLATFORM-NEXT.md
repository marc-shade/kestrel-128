# Next native platform steps

The browser checkpoint left 139 bytes before the page tables at `$3800`.
The [resident-growth checkpoint](validation/2026-09-09-native-relocation/README.md)
moved the allocator to `$1300`. The native Ultimate backend now reserves an
additional 4 KiB at `$4000..$4fff`; the remaining heap has 426 pages. Public
entry addresses and the `$6000` app slot remain stable. The ABI 1.12 workspace
main region had six free bytes (four in the direct-desktop variant), the low
region eight, and resident services ended seven bytes before `$5000`. Since
2026-10-03 the memory workspace runs from the system section at `$0c00` and
boot-only code from staging: the main region has 1,005 free bytes (1,001),
the low region 50 and the service region 56, with the heap unchanged
([kernel contract](NATIVE-KERNEL.md)).
Presentation setup and the relocated keyboard-input wrapper leave three bytes
before the retained browser path at `$4a00`.
The [native desktop and drawing library](NATIVE-GRAPHICS.md) keep graphics code
in the app/module allocation. The ABI 1.5 directory
cursor shares the owned stream API and supports native folder navigation.
The diagnostic [shared file picker](NATIVE-FILE-DIALOGS.md) is implemented in the
editor and passes [CPU, emulator and physical qualification](validation/2026-09-10-native-file-dialogs/README.md).
The [ABI 1.7 module loader](NATIVE-MODULES.md) now loads that picker into
the editor's existing allocation. All 22 CPU suites, ten emulator workflows
and complete physical USB/IEC workflows pass on the
[frozen checkpoint images](validation/2026-09-11-native-modules/README.md).
The first physical USB run failed on a browser rescan
before reaching the editor; its evidence and successful resource cleanup are
retained. The complete USB retry passed on the same images; the initiating
fault remains unresolved. Scheduling and further module services remain required.

## 1. Resident growth and its remaining limits

The `$1c20` entry table, `$3800` ownership tables, `$3a00` transfer buffer,
`$3d00` mailboxes and `$6000` app entry remain stable. Future assignments still
need an interval audit covering KERNAL workspaces, both displays, boot staging
and observers; use the generated `target/native/layout.json` as the current map.

The low region is bank 0 `$1300..$1bff`, 2,304 bytes excluded from the heap.
Commodore identifies that range for machine-language routines used with BASIC.
[Commodore 128 Programmer's Reference Guide](https://www.pagetable.com/docs/Commodore%20128%20Programmer%27s%20Reference%20Guide.pdf)

The observer now borrows the shared transfer buffer for 512-byte chunks,
restores its contents and checks that the low kernel remains intact. Its old
`$1400` output path must not be used with this kernel. Host captures reject
RAM0 sources overlapping their borrowed output or probe workspace.

The BASIC entry remains intact. Startup copies nine pages from declared
staging at `$5000..$58ff` into the low region before initializing the heap.
The heap can then reuse all nine staging pages. `$4000..$4fff` remains reserved
for Ultimate services. The bank-0 workspace block occupies `$df00..$feff`
beneath ROM and is accessed through the CPU's native bank gateways.
Further growth must continue accounting for both final and peak boot footprints.
The [compressed boot wrapper](NATIVE-BOOT-MEDIA.md) temporarily uses `$1300`
for its decoder and `$6000` for packed input, before this relocation and heap
initialization. It saves disk blocks without growing either resident region.
Longer-term modules need their own owner/lifetime records; this small range
alone is not a memory architecture for the complete OS.

The diagnostic shared-field build makes the next memory constraint concrete. The editor
uses 79 pages, both workspace blocks use 64, and a 66,056-byte document uses
seventeen 16-page chunks. That is 415 of 426 pages before opening the picker;
its eight extra cache pages raise the total to 423. The tested allocation
order fills bank 0 and leaves three free pages in bank 1. Reserving another
bank-0 resident region would break this workload unless other live storage is
reduced or moved to an implemented backing store.

The tested allocation order has the following page budget. Document ranges
are also recorded in the emulator's complete live-document capture. Picker
cache pages are allocated lazily, up to the eight-page case shown here.

| Use | Bank 0 | Bank 1 | Pages |
|---|---|---|---|
| Editor code and persistent state | `$6000..$aeff` | - | 79 |
| Workspace blocks | `$df00..$feff` | `$0400..$23ff` | 64 |
| Seventeen document chunks | `$5000..$5fff`, `$af00..$deff` | `$2400..$f3ff` | 272 |
| Extra picker cache at peak | - | `$f400..$fbff` | 8 |
| Remaining heap | - | `$fc00..$feff` | 3 |

ABI 1.7 implements a checked bank-0 module window inside an app's declared
allocation. App code outside that window, its field
state and its document handles must remain live while a picker or device panel
occupies the window. A module load needs separate image/version/extent checks,
an invalid state until complete verification, checked stream cleanup and a
generation that prevents calling a replaced module. It must never overwrite
caller code, and a missing or damaged module must return to the intact app.
CPU checks retain the large-document/two-workspace case and exercise failed
module loads, stale entry tokens, allocation ownership and both displays.
The completed emulator checks retain ROM/IRQ behavior and the full document
and source lifecycle. Complete physical USB/IEC workflows also pass on the
same frozen images, including independent saved-file readback.
The [native REU arena](NATIVE-REU.md) now backs Calculator's VDC snapshot,
with 4 KiB allocations, app-generation tokens and bounded DMA. It retains its
code and descriptors in the app core and does not reserve more resident RAM.
The Calculator leaves 331 main-RAM pages free with an REU. Integrating that
backing into documents, caches and the larger graphical apps still needs code
placement and lifetime work. REU-backed caching and banked execution remain additional work; a module
window alone does not implement app suspension or background scheduling.

Bo Zimmerman's [geoModules project](https://www.zimmers.net/geos/geomods.html)
is a useful original-author comparison: it defines a common calling convention
and shared scratch for linked UI modules, plus VLIR module loading and calls.
It also documents file dialogs and overlapping movable windows. Those are
separate contracts to account for in Kestrel; adding a loader does not supply the
remaining shared widgets, clipping, focus or window behavior. No geoModules
code has been imported into the native field implementation.

The checkpoint records the section bounds, startup/IRQ/staging tests, existing
native workflows and revised observer qualification. No test may save and
restore memory over active kernel code. These resident regions are a
next-step capacity increase, not the complete scheduler/driver memory architecture.

## 2. Extend the banked document model and native editor

The [native editor](NATIVE-EDITOR.md) uses the existing heap/file ABI for owned
4 KiB chunks, with 24-bit logical length separate from capacity. It preserves
CRLF/lone CR/lone LF and other imported bytes, provides cursor/viewport editing,
retains the original document after a failed Open and verifies Save As by a
complete reopen comparison. Both contexts and the app share an explicit owner.

Add selection, clipboard, undo/find and session recovery next to the shared
dialog/input work. REU/disk backing is still required for documents exceeding
available base RAM. The word processor's layout/format/printing requirements
remain separate.

The base workflow crosses a 64 KiB logical offset, saves and reopens the edited
bytes, and preserves unrelated allocations. Keep those checks when extending it.
Compare saved bytes independently, include allocation and transfer failures,
and retain document ownership across reusable dialogs. An uncertain CLOSE
currently quarantines the owner; provide an explicit recovery path before
claiming media-failure recovery is complete.

## 3. Share input, dialogs and backend state

ABI 1.6 now implements [shared focused fields](NATIVE-FIELDS.md) in the kernel,
used by the editor, browser and calculator. Caret navigation, middle insertion,
forward deletion, filters and independent clipped viewports pass
[CPU, emulator and physical qualification](validation/2026-09-10-native-fields/README.md).
Picker cancellation retains the field state and document.
Next, extend shared list/viewport behavior and define events and focus for both displays,
and preserve the Open/Save As contract that keeps the caller's document allocated.
The current file-picker implementation shares browser navigation source with
the editor. CPU workflows retain a 66,056-byte document and both 8 KiB workspace
blocks through paging past ordinal 255, cancellation and verified Save As.
The fault cases cover missing directories, cache exhaustion and retained
directory-close recovery. All ten emulator workflows and the complete physical
USB/IEC checks pass, including independent saved-file readback and full document
captures while the picker has focus.
The [native editor redraw checkpoint](validation/2026-09-09-native-redraw/README.md)
replaces full repaint for fields and ordinary edits/cursor motion with affected
rows. A second read page and cached line offsets remove repeated banked reads.
It retains full repaint for structural changes and viewport movement. Keep the
complete VIC/VDC comparisons for clipping, deletion, cancellation, line-offset
carry/borrow and document cursor movement when extracting these services.
The physical ten-character filename queues now take about 4.20 seconds versus
26–46 seconds previously, with the same 4-second quiet interval. Extra checks
with a 0.1-second quiet interval take about 1.23 seconds in both small documents
and positions beyond 64 KiB. Continue measuring both cases; isolate device
throughput from UI and observation cost before making broader performance claims.
Loader, stream and Ultimate directory ownership are now shared; add media
identity, operation progress/cancel across the remaining backends and recovery
from retained errors.

Acceptance: browse a data drive, return to an intact document, save through
the selected backend, and reopen the system browser from its boot device.
Repeat with missing media, full disks and directory/transfer failures. Measure
large-directory I/O and redraw cost before claiming performance improvements.
The older editor checkpoint recorded roughly 296-second Open and 523-second
verified Save As through standard 1541 IEC. The [native Ultimate backend](NATIVE-ULTIMATE.md)
now supplies raw absolute-path streams and verified writes to the editor.
The browser's absolute-path field now launches USB apps through the shared
backend, and the calculator saves beside its USB image. ABI 1.5 adds owned
directory cursors, complete names, canonical paths, checked cancellation/CWD
restoration and browser folder navigation. Preserve the qualified shared picker
while extending common focus/input behavior and remaining selector backends.
Reduce IEC extent I/O and add cancellation
within long operations. Keep complete byte comparisons and state the harness's
quiet/poll intervals when measuring timing.

The implemented directory contract makes these lifetimes explicit:

* A caller owns its cursor, complete selected name, path and cached records.
  Abbreviated display text must never become an OPEN target.
* A scan owns a DOS context and the active READ_DIR transaction until the final
  packet or checked cancellation. The UCI transport is shared across both DOS
  contexts, so even other-context file calls must wait while packets remain
  pending. File operations and another scan must not reuse the reserved context.
* Capture the selected context's original CWD, restore it on checked CLOSE,
  and retain the owner if restoration is uncertain. EOF alone leaves ownership
  intact; the browser closes its cursor at EOF or when abandoning the scan.
* Bound packet size, entry count and RAM use. Report a partial list explicitly;
  do not treat exhaustion, timeout or malformed response as end of directory.
* Preserve the visible browser page and selection during an incomplete scan.
  Empty/large directories, long and quoted names, parent navigation, cancellation,
  foreign transactions, absent media and failed CWD restoration have dedicated
  CPU cases. A shared dialog must additionally preserve its caller's document.

The service uses existing OPEN/READ/CLOSE entries with format 3/mode 2.
The source
inspection above uses `1541ultimate` revision
`a01c04e8267a0d916b7203cb34dcf1127f75981d`,
[`software/filemanager/dos.cc`](https://github.com/GideonZ/1541ultimate/blob/a01c04e8267a0d916b7203cb34dcf1127f75981d/software/filemanager/dos.cc).
The [documented DOS commands](https://1541u-documentation.readthedocs.io/en/master/uci/ultimate_dos_target.html)
describe the transport operations; physical qualification remains specific to
the recorded cartridge and firmware observations.
FILE_INFO can establish that no file is open; it cannot establish that a
foreign client has no retained directory snapshot. The native service claims
the selected context's idle snapshot for Kestrel; a future broker must coordinate
that ownership with other clients. It preserves foreign files and active UCI
transactions. See the [full contract](NATIVE-ULTIMATE.md#directory-cursors-abi-15).

The [first ABI 1.7 USB failure](validation/2026-09-11-native-modules/hardware-usb-initial-failure/README.md)
also exposed a recovery gap in the CPU model: a timed-out native command
submits an abort and returns before its completion is observed. Immediate
directory cleanup can then report a busy interface and retain its owner.
The [owned-abort follow-up](validation/2026-09-11-native-owned-abort/README.md)
now implements a bounded wait while preserving the initiating error, avoiding
command replay and retaining ownership if completion remains uncertain. Its
24 CPU suites and ten emulator workflows pass. Its first physical USB attempt
failed during a saved-file reopen through DOS context 2. The full unmodified
retry and the physical IEC workflow pass with complete file readbacks and
restoration/cleanup. Combined audits also pass. This modeled gap and the passing runs do not
establish either physical failure's cause.

## 4. Migrate the desktop and Ultimate services

The [native desktop migration plan](NATIVE-DESKTOP-MIGRATION.md) records why
the earlier C64-mode drawing code was not reused, a provisional surface budget
and the first display-ownership/return acceptance gate. That code's bitmap and
matrix overlapped the editor and its document storage.

The integrated [native launcher](NATIVE-GRAPHICS.md)
boots a graphical app selector on VIC and [VDC](NATIVE-VDC-DESKTOP.md),
with actual handoff to all six suite apps, app return and allocation fallback.
The VDC driver saves its overwritten memory in owned RAM and restores it
before each handoff. Its current software evidence is linked from the VDC
checkpoint; physical qualification below covers the earlier three-app build. The [full ABI 1.9 physical workflow](validation/2026-09-12-native-desktop-abi19-hardware/README.md)
also passes, with complete CPU display-RAM/mode observations and verified
restoration/cleanup. Physical video pixels remain unqualified.
It releases the launcher, surface and VDC snapshot before opening another app, preserving
the full native application memory budget.

Build the cartridge file/control service, drive panel, network/RTC behavior
and applications on the versioned native services. Then add scheduling,
REU/expansion allocation and the productivity suite using the full
[completion roadmap](IMPLEMENTATION-ROADMAP.md) as the acceptance checklist.

Each step requires its own exact-image checkpoint. A successful prototype or
one tested expansion does not complete the application, desktop or hardware
rows in the broader roadmap.


## ABI 1.10 app-suite integration

The desktop suite now includes a native Claude terminal and an Ultimate
information panel. [Claude setup and controls](../apps/claude/README.md) cover
its Linux bridge, explicit serial connection and F8 return. The foreground app
saves/restores the custom VDC font and NMI state. The kernel's mapping bridge
occupies eight bytes below BASIC; all 426 managed heap pages remain available.
[Ultimate queries](NATIVE-ULTIMATE-CONTROLS.md) reuse the existing serialized
file transport. ABI 1.11 adds a generic bounded command entry and the native
app's guarded mount/eject workflow. The blue drive controls share keyboard,
mouse and focus code; the image picker retains full paths and returns to a
confirmation with Cancel selected. Fresh inventory and open-file checks precede
each mutating request. Accepted requests are not presented as verified media
changes. The [frozen software qualification](validation/2026-09-13-native-ultimate-drives/README.md) passes; native
physical qualification and broader device settings remain open.

The [graphical Files app](NATIVE-FILES-GUI.md) extends the blue controls to
navigation, byte viewing and verified file copy. Graphics and the destination
picker share a checked module window while the core retains keyboard ownership,
raw names, preferences and file handles. Its current 96-page app and optional
36-page surface fit the existing ABI. The original 93-page version has a
[software qualification](validation/2026-09-13-native-files-gui/README.md).
The [suite Editor](NATIVE-EDITOR-GUI.md) now uses 96 app pages and a 36-page
surface, with its graphics/search and picker sharing one window. Its desktop
launch releases workspace allocations before loading the app; it supports a
17-chunk document above 64 KiB with graphics active. The
[software qualification](validation/2026-09-13-native-editor-gui/README.md) passes; physical qualification and document backing storage remain open.

The [shared graphical picker](NATIVE-PICKER-GUI.md) carries the same blue controls
through Editor, Files, Paint and Ultimate. Compact IEC records retain all 296
D81 entries while a 66,057-byte edited document remains live: 96 app pages,
36 display pages, 272 document pages and 19 banked cache pages use 423 of the
426 available pages. Its [software qualification](validation/2026-09-13-native-picker-gui/README.md) passes. Native physical
qualification, VDC graphics and backing storage
remain open.

The [Claude frame](NATIVE-CLAUDE-GUI.md) now uses blue icon buttons, yellow
focus and the shared 1351 pointer. Its VDC terminal retains all 80×25 cells;
both graphical status pages preserve all 25 host panel rows and live glyphs.
Ctrl+Help selects local controls without changing ordinary terminal shortcuts.
The app uses 75 pages plus a 36-page surface; the resident kernel is unchanged.
The [software qualification](validation/2026-09-13-native-claude-gui/README.md) passes.

The [Claude lifecycle checkpoint](validation/2026-09-12-native-claude-lifecycle/README.md)
addresses the Ultimate's asynchronous relay: the client keeps its NMI handler
and receive credits active until the host acknowledges F8. Timeout and a second
F8 both take normal native teardown. The Linux PTY starts only after RESYNC.
Two frozen VICE workflows verify both exit directions, font/NMI restoration
and complete desktop return; a separate rebuild matches all 19 images.

The [shared suite workflow](validation/2026-09-12-native-suite-workflow/README.md)
adds all five apps and two Claude sessions to the same desktop, display,
resident-code and allocation checks. Successful Ultimate replies are checked
against independent query fixtures; VICE exercises the absent-device display.
Serial checks use a fixed PTY fixture, with no model requests. A foreground VDC
mirror and settled output avoid observing the terminal during drawing.

Physical preflight found DE00/NMI, port 3000, DTR disconnect and incoming RING
already enabled, and retained independent device/drive/network/RTC replies.
The native attempt then stopped during the initial resident capture after
three consumed inputs, last key cursor down, changed the desktop selection.
The observer's buffers matched after restoration; changed resident bytes were
declared drawing state. The input source is unknown. No added app was reached.
Original deployment, drives, settings, DOS paths and controls were restored;
both private uploads were fully verified and removed. Separate final GETs
confirmed unchanged modem settings.

Diagnose the uncommanded input before another full physical attempt. Preserve
the failed capture and strict comparisons; any new attempt needs fresh frozen
inputs. The connect-only bridge must start after opening the native client.
The IRQ observer does not preserve an interrupted client's selected VDC
register, so serial display checks still require settled output.
