# Kestrel completion roadmap and gap analysis

Updated 2026-09-15. This is the current completion checklist. Requirement IDs
such as FR-A1 come from the project's original product requirements, which are
not included here.

The goal remains a complete C128 desktop OS with GEOS/Wheels-class applications,
modern desktop workflows, and integrated control of the Ultimate II+ and
Commodore expansion hardware. The existing text editor, calculator and other
suite apps do **not** satisfy that goal by themselves. A compatible IEC interface is not
proof that every attached device works. Emulator coverage is not hardware proof.

## Evidence and comparison baseline

This audit began from an earlier C64-mode desktop, before the native C128
kernel existed. That starting point had no native C128 kernel, office suite,
printer subsystem, application scheduler or desktop Ultimate control
application. The rows below record the native system.

Primary references used for the comparison and implementation direction:

* [Pinned Commodore source collection](COMMODORE-SOURCE-REFERENCE.md): C128
  KERNAL/editor IRQ and VDC behavior, 1571/1581 drive code, and REU RAMDOS.
  Two IRQ/editor excerpts match the local ROM exactly; broader driver work
  remains subject to the acceptance checks below.
* [Ultimate UCI DOS target](https://1541u-documentation.readthedocs.io/en/master/uci/ultimate_dos_target.html)
  and [control target](https://1541u-documentation.readthedocs.io/en/latest/uci/control_target.html):
  cartridge-side storage/control commands. Use the installed firmware's commands
  and responses; new firmware documentation alone cannot prove availability.
* [Ultimate HTTP target](https://1541u-documentation.readthedocs.io/en/latest/uci/http_target.html):
  firmware 3.15 adds target 6. It needs its own capability probe and driver;
  current Kestrel target-3 socket support does not implement it.
* [C64 OS user guide](https://c64os.com/c64os/usersguide/): comparison requirements
  include reusable UI controls, clipboard, app switching, customizable desktops,
  and consistent file/device management.
* [Click Here Software's GEOS distribution](https://cbmfiles.com/geos/index.php)
  and [application catalog notice](https://www.cbmfiles.com/): GEOS and Wheels
  belong in the application/format comparison, including the office applications
  geoPublish, geoCalc, and geoFile. The website's old “coming soon” notice is not
  a release or download-availability guarantee.
* The local `../mp3-manual-en.pdf`, GEOS application disks, and MegaPatch image
  are comparison fixtures. Their presence does not establish Kestrel compatibility.

The [Wheels owner-manual audit](WHEELS-PARITY.md) now covers all 67 PDF pages
of the 1998 copyright edition and maps 23 behavior groups to Kestrel acceptance
work. Repeatable comparison sessions and later-release coverage remain open.
Record manual edition/page and observed behavior for every parity claim.
The [Wheels programming-reference review](WHEELS-PROGRAMMING-REFERENCE.md)
now covers all 38 pages of the edited author correspondence. It supplies
specific module, source-location, expansion-memory, driver and display topics;
it complements the owner-manual review and does not establish runtime parity.
The same review now covers the seven-page 1998 installation leaflet visually,
with keyboard-only setup, memory/device choices and source-disk protection
mapped to installer acceptance work.
The [MegaPatch 3 manual audit](MEGAPATCH-3-PARITY.md) now maps all fifteen pages
of the supplied 2019/Jan/27 manual to sixteen behavior groups and concrete Kestrel
acceptance checks. Runtime comparison sessions remain open. Its task manager
pauses inactive applications, so suspended-app switching and background-service
scheduling have separate acceptance requirements.
The [local reference inventory](REFERENCE-FIXTURES.md) records nineteen images,
their hashes and directory listings, including geoWrite, geoPaint, geoSpell
and the write utilities. These are named candidates for the application and
format comparisons; they have not been qualified as running under Kestrel.
The first [GEOS128 reference boots](reference/2026-09-11-geos-boots/README.md)
now reach a visible desktop in VICE from unchanged private disk copies with
both initial display settings. Authentic input and application comparisons
remain open; this is reference boot evidence, not Kestrel compatibility.

The [native D81 suite](NATIVE-BOOT-MEDIA.md) provides 2,512 free disk blocks
while preserving the 426-page RAM budget. ABI 1.12 retains the system volume's
format independently of browser preferences. Automatic media detection,
D71 boot distribution, partitions, installer/recovery and dynamic system-volume
replacement remain work items; a larger disk does not provide more app RAM.

## Kernel, desktop, and application gaps

“Partial” means implementation exists but the complete row still needs work.
Every row below is required for completion unless its hardware capability is
physically unavailable; unavailable capabilities must remain visible as such.

| Requirement | Current evidence | Remaining implementation | Acceptance evidence |
|---|---|---|---|
| FR-A1 discovery and FR-A2 drivers | VDC/UCI probes | Versioned per-class registry, bounded probes, resources/conflicts, optional drivers, boot report, persisted configuration | Cold boot with present/absent/conflicting devices; no hangs or writes to unrelated hardware |
| Native C128 platform, FR-M3 | Native boot/kernel, two-screen workspace, banked files/apps and keyboard graphical desktop at 1 MHz; owned display lifetime and KERNAL gateways | Remaining desktop/app/Ultimate migration; safe 2 MHz regions, ROM/IRQ/DMA ownership and per-model qualification | Real C128 and C128D/DCR tests; bank isolation, I/O at both speeds, both displays live |
| Memory and FR-M1 | Native 426-page allocator with owner/generation checks and bounded transfers; [128 KiB–16 MiB foreground REU arena](NATIVE-REU.md) for Desktop, Calculator, Ultimate, Paint, Files, Editor and Claude VDC snapshots; [shared REU Editor documents](NATIVE-SHARED-MEMORY.md) with resizable extents, separate display lifetime and RAM fallback | REU-backed clipboard/caches and larger app heaps; disk-backed documents; scheduled shared arena; other expansion allocators; RAM disks and persistence | Large-document/app lifetimes across backing stores; concurrent ownership and live configuration recovery |
| Process/app lifecycle | Native single foreground app: directory discovery, checked manifest/ABI/size/CRC, owned memory and IEC/Ultimate streams, cleanup before app handoff, browser return | Cooperative scheduling, suspend/resume, app switcher, cleanup across remaining native handle/control backends | Switch among editor, terminal, file copy, clock; preserve buffers and release resources after errors |
| Desktop and FR-S1 | Native graphical keyboard/1351 launcher on VIC and 640×200 VDC, app handoff, text fallback and selection retained across app/workspace returns | Keyboard navigation everywhere; launcher scrolling/categories; shortcuts; draggable/resizable windows; focus/z-order; multiple desktops; context menus | Complete mouse and keyboard workflows; no stale controls; overlapping windows repaint correctly |
| Shared desktop services | Qualified native IEC/Ultimate picker; qualified ABI 1.6 focused fields; shared native pointer and rectangle focus/hit testing used by graphical Calculator, Paint, Ultimate, Files, Editor and Claude; [session text clipboard](NATIVE-CLIPBOARD.md) shared by Editor, Claude and Sheet; [span history](NATIVE-HISTORY.md) used by Editor; [Files-to-Editor/Paint document launch](NATIVE-DOCUMENT-LAUNCH.md) with retained file identity and selection | Broader widget/event toolkit; selectors for remaining backends; image/REU scraps; grouped and wider-app undo; configurable associations and more document types; progress/cancel; notifications; help | Copy text/image between apps; cancel file operations safely; select files from every backend |
| FR-D1/D2 display | Native owned VIC bitmap, clipped drawing/text and a [640×200 VDC launcher](NATIVE-VDC-DESKTOP.md) with owned snapshot/restore, plus graphical Calculator, Ultimate, Paint, Files, Editor and Claude through a shared incremental VDC presenter; retained Claude terminal and VIC left/right views | Wider modes and display backing stores; mirror/extended roles; live switching; independent focus; clipping and scroll surfaces | Operate all apps using only either monitor, then both; no invisible required controls |
| FR-D3/D4 enhanced video | Native reversible 16/64 KiB detection and 640×200 launcher, with color cards on 64 KiB | Further bitmap/hires modes; supported FPGA features through model-specific drivers | 16/64 KiB VDC modes; supported monitor timings; fallback on absent features |
| FR-I1 keyboard | GETIN, ESC and dedicated cursors; ROM scan bounds with counted rejections | Event queue, full keypad, TAB/ALT and modifiers, repeat policy, shortcuts, configurable mappings | Type while dragging and doing IEC/UCI I/O; no lost events or phantom keys |
| FR-I2/I3 pointer | Native port-1 1351 sprite pointer, clamping/jitter filter, reconnect baseline, hover and click/release app buttons; VICE/CPU tests | Physical native mouse/adapters; port 2, two-button menus, drag/drop, acceleration; joystick and keyboard pointer drivers | Measured latency/jitter; real 1351 and adapters; simultaneous keyboard/serial traffic |
| FR-F1/FR-S2 storage/file manager | Native owned IEC/Ultimate streams and checked app loading, verified Ultimate writes and 255-byte launch paths, IEC directory pages, ABI 1.5 owned Ultimate cursors/folder navigation and byte viewer; shared blue file picker; blue suite Files list, byte viewer, focused paths and cross-backend copy with reopened comparison, progress/cancel and destination picker; [Ultimate folder creation](NATIVE-FOLDERS.md); [current-directory filename search](NATIVE-FIND.md) | Native registry and media identity; faster IEC enumeration; zero-byte IEC create, rename/delete and append/replace; sorting, recursive search and persistent filters; multi-select/batch actions; interrupted-copy recovery; REL/VLIR support; folders/partitions; disk info/format/validate; recoverable trash | Large/malformed/empty directories; all file types; byte-exact copies; disk full/unplug/error/cancel; reliable navigation and status |
| FR-F2 devices | Native browser 8–30 with explicit D64/D71/D81 geometry; system-app source restored after data-device app launch | Inventory, type/capability handshake, hot presence, broader physical qualification | Real and emulated drives; absent device returns to UI; last-used device never changes system-app source accidentally |
| FR-F3/F4 advanced storage | Standard KERNAL IEC | CMD/1581 partitions, SD2IEC/IDE64 adapters, REU native RAM disks; C128 burst/JiffyDOS/fastload negotiation | Per-backend workflows and timing benchmarks; safe fallback without the expansion/ROM |
| FR-S3 preferences | GEMDESK preferences, colour and windows saved in DESKTOP.INF ([TOS parity](TOS-PARITY.md)) | Driver/device/boot preferences, atomic versioned records, recovery defaults, DST/calendar policy, appearance/accessibility | Power-cycle each setting; corrupt/old records and failed writes recover predictably |
| FR-S4 shell | No native command shell; `N_REPLACE` chains to another app ([TOS parity](TOS-PARITY.md)) | Shared FS integration, history/completion, scripts/pipes/redirection, jobs, useful errors, document/app launch | Scripted end-to-end workflow with removable media and network failures |
| FR-S5 editor/calculator | Native blue banked text editor with keyboard/mouse range selection, shared Copy/Cut/Paste, sixteen-step undo/redo and replacement, file/search controls, 24-bit positions, transactional Open, verified exclusive Save As, shared picker and literal find/replace module; native VIC/VDC graphical integer calculator with mouse/keyboard keypad, 32-result banked history and verified SEQ export dialog | Grouped undo and document/session recovery; calculator precision/scientific modes and history import/session persistence; standalone terminal | Save/reload documents beyond main RAM; arithmetic edge cases; interactive network/serial sessions |
| FR-S6 SDK | Native ABI, manifest/image validator/sealer, calculator and [standalone module example](../examples/native-module/README.md); 15 separate module-example CPU workflows reproduce from archived sources | Broader versioned APIs, docs generated from exports, clean-checkout third-party workflow and portable test tooling | Build and run a third-party app from a clean checkout; no hardcoded developer-home dependencies |
| FR-S7 appearance | Shared blue bitmap controls and yellow focus across the launcher, native apps and file picker; basic background colors | Backdrops, font/theme/pointer selection, screen saver, desktop arrangements and persistence | Change/restart/restore; memory budgets and low-RAM fallback |

## Application parity backlog

These are separate applications and shared formats, not additional shell
commands. Original GEOS application execution is a separate
compatibility requirement from providing equivalent Kestrel applications.

| ID | Deliverable | Existing implementation | Completion gate |
|---|---|---|---|
| APP-WRITE | Word processor with fonts/styles, pagination, embedded pictures, search/replace, spelling, printing | Banked plain-text editor; no page layout | Create, save, reopen, edit, preview and print a multipage illustrated document; exchange supported geoWrite formats |
| APP-PAINT | Bitmap editor, drawing tools, color/patterns, selection, zoom, clipboard, undo | [Native Paint](NATIVE-PAINT.md): 320×200 banked picture, graphical VIC/VDC viewport, connected pencil/eraser, 16 ink colors, keyboard brush and panning, undo/redo, staged Open and verified exclusive UPNT Save As through graphical IEC/Ultimate picker; retained display recovery | Native-width VDC tools; more tools/patterns, selection, zoom, clipboard, multiple undo, printing; physical round trips; declared GEOS/Commodore image import/export |
| APP-SHEET | Spreadsheet with cell types, formulas, references, recalc, formatting, import/export, printing | [Native Sheet](NATIVE-SHEET.md): editable 8×32 banked workbook, VIC/VDC grid, integer formulas, references, SUM/MIN/MAX/COUNT, cycle detection, one-step cell Undo/Redo, shared cell Copy/Cut/Paste, checked modules, transactional Open and verified exclusive USHT Save As; formatting, decimal types, shared picker, range clipboard and printing remain open | Recalculate/save/reopen a useful workbook; formula cycles/errors and memory limits tested; geoCalc exchange matrix |
| APP-DATA | Database/address book with schema, records, sorting/filtering, forms/reports, import/export | Absent | Maintain and report a record set larger than main RAM; geoFile exchange matrix |
| APP-PUBLISH | Page layout with text/image frames, columns, styles, preview, print/export | Absent | Complete a newsletter and reopen it without layout loss; geoPublish comparison fixtures |
| APP-ORGANIZE | Calendar, appointments, alarms, contacts, notes and clock accessories | Clock plus editor | Persistent appointments; alarms while another app is active; timezone/date rollover tests |
| APP-MEDIA | Image/document/text viewers, font browser, photo/text scrap managers, SID/audio player | Paged native byte viewers and native text/UPNT association launch | Wider associations, scrolling/zoom, playlist, inter-app scraps, supported format round trips |
| APP-COMMS | Terminal (PETSCII/ANSI), serial/modem and TCP/Telnet, file transfer; network resource browser | Native Claude host-PTY client over SwiftLink; general terminal protocols remain open | Real BBS/LAN session, encoding negotiation, transfer integrity, reconnect and cancel |
| APP-CLAUDE | Include marc-shade/claude-c128 as a native desktop suite app | Built into suite D64/D81 images with blue controls on both displays, a full retained VDC terminal, VIC left/right views, mouse/keyboard navigation, handshake-controlled bridge, shared text clipboard and acknowledged paste/shutdown | Native physical serial/mouse and authenticated Claude sessions; scrollback and session recovery |
| APP-PRINT | Printer setup, spooler, preview, job queue and cancel; text/raster/PostScript/PDF where backend supports it | Absent | Print document/picture/table through declared physical and Ultimate printer backends; disk-full/disconnect recovery |
| APP-ARCHIVE | Archive manager, disk-image tools, backup/restore, format conversion | Absent | Recover a backup after reset; malformed/truncated archive tests; byte-exact image/file verification |
| APP-DEVELOP | Assembler/editor integration, monitor/debugger, build/run tools, API help | Absent | Build and debug a small native app from Kestrel; preserve desktop/app state on exit |
| APP-COMPAT | GEOS sequential/VLIR/Convert formats, document migration, original GEOS app execution or an explicit managed compatibility environment | No compatibility layer | Named applications and documents tested on real C128; preserving GEOS metadata and files is mandatory |
| APP-SYSTEM | Hardware/resource monitor, disk utility, diagnostics, installer/updater/recovery, online/offline help | Deployment scripts and native Ultimate identification/drive/network/RTC panel | A user installs, diagnoses, updates and recovers Kestrel from the desktop without a developer workstation |

## Ultimate II+ integration backlog

Use the native UCI packet service; a “REST over a serial listener” design is
not required. The
cartridge's REST service is useful for host-side tests and any operations not
exposed over the installed UCI. Features that reset the CPU need explicit state
save/restore; loading a new REU image must not destroy active OS allocations.

| ID | Desktop feature | Current state | Completion gate |
|---|---|---|---|
| UCI-BASE | Hardware/firmware identification, target/version discovery, command queue, timeout/abort, status/error display | Packet streaming, 16-bit command length, explicit clipping, bounded polling/abort; physical DOS/control identification; shared native read-only queries, ABI 1.11 serialized packets and blue Ultimate controls; bounded handling of the reference cartridge's partial drive reply | Native panel hardware qualification; shared capability registry, missing peripheral records, observed completion of native-owned aborts, interrupted operations and per-firmware protocol coverage |
| UCI-FILES | USB/flash/temp browser, full paths, directories, file read/write/copy/move/rename/delete/create | Native ABI 1.6 owned app loading, directory cursors/navigation with retained full names, calculator export, editor access, shared picker and focused fields; native suite Files copy with progress/cancel and reopened comparison; native Ultimate folder creation and current-directory filename search | Reusable file-management controls; safe replace/rename/delete workflows, copy resume/partial cleanup/batch/folder picking, mounted-file protection, text/image/media viewers, faster sorted/indexed directories, longer paths, selector integration in other apps, Unicode display |
| UCI-DRIVES | A/B drive inventory, image mount/eject/create, drive type/power/address/ROM controls, write protection, save changes | Native blue drive controls, full-path picker, explicit confirmed IEC destinations, fresh inventory checks, power-state display, system-disk protection and mount/eject; native CPU/VICE qualification passes | Native physical mount/eject qualification; per-model D64/D71/D81/G64/G71 compatibility; mounted-media identity, remaining drive settings, write protection, dirty-media handling, system-volume replacement/recovery and unsaved work |
| UCI-MEMORY | REU size/configuration, RAM-disk management, REU image save/load, snapshots and restore | Foreground REU allocator and bounded DMA back Desktop, Calculator, Ultimate and Paint VDC screens through a shared bank-1 component; main-RAM fallback | Save/restore a session without corrupting owned banks; live size changes handle active allocations |
| UCI-NET | Network setup/status, DNS, sockets, transfers, firmware HTTP offload | Native panel displays configured interface addresses | Native panel hardware qualification; download/upload files; recover DNS/network/server errors; negotiate newer HTTP target where present |
| UCI-TIME | RTC read/write and offline date/time | Native cartridge-clock panel validates calendar replies, edits dates/times with keyboard/mouse, sends a confirmed binary SET_TIME request, and independently checks readback without replay | Native panel hardware qualification; power-cycle/backup retention and offline fallback; distinct system/cartridge clock status in the desktop panel |
| UCI-AUDIO | SID selection/configuration, audio routing/mixer, playback/record capabilities | Absent | Real output and supported chip/model configuration; unavailable hardware excluded by capability checks |
| UCI-PRINT | Printer selection, job status, output-file retrieval | Absent | Desktop print job produces a verified readable output file or physical page |
| UCI-TAPE | Tape image playback/capture and file management | Absent | Start/stop/capture, verify files, preserve desktop before incompatible launches |
| UCI-CART | Cartridge/ROM selection, freezer, DMA/program launch, reset/reboot | Host deployment only | Explicit launch/return lifecycle, unsaved-work handling, no accidental overwrite of resident modules |
| UCI-CONFIG | Discover/edit/save supported firmware settings, profiles, diagnostics, model-specific video/audio features | Host scripts only | Setting read/write/readback and persistence; distinguish II+, II+L and Ultimate 64-only capabilities |

## Hardware coverage ledger

For each concrete device, keep model, firmware/ROM, address, probe method,
conflicts, supported operations, test artifact, and hardware result. “Uses IEC”
or “has a driver slot” is insufficient to mark a device supported.

| Family | Required coverage | Current evidence / next gate |
|---|---|---|
| Base C128 | 8502, MMU, VIC-IIe, 8563/8568, SID, CIAs, keyboard, IEC, user port, cassette, Z80/CP/M handoff | Native memory workspace and graphical desktop; per-model desktop qualification, speed transitions and handoffs open |
| Memory/acceleration | 1700/1764/1750 REUs; Ultimate/RAD REU emulation; GeoRAM/NeoRAM; RAMLink/RAMDrive; SuperCPU/SuperRAM and compatible accelerators; VDC RAM upgrades | Native foreground REU arena and VDC 16/64 KiB handling implemented; physical model qualification, other expansion allocators and accelerator integration remain open |
| Storage | 1541/1570/1571/1581; CMD HD/FD/RL partitions; SD2IEC; Pi1541; IDE64; Ultimate drives/SoftIEC; Kung Fu Flash; network IEC devices | Partial KERNAL workflows; no blanket device certification |
| Input | 1351 and supported adapters, joystick, keyboard pointer; supported paddles/light pen/tablet; serial/Amiga mouse adapters with appropriate drivers | 1351 path exists; electrical/protocol-specific drivers and tests needed |
| Communications | Ultimate, RR-Net/64NIC+/CS8900A, WiC64, user-port RS-232, SwiftLink/Turbo232 and compatible modems | Native DE00/NMI SwiftLink Claude client qualified in VICE, physical serial qualification pending |
| Printing/audio | IEC/user-port/parallel printer adapters and compatible printers; Ultimate printer; SID variants, stereo/multi-SID and supported audio/MIDI expansions | No OS printer/audio service yet |
| Other hosts | C64, C128D/DCR; Ultimate 64 family, supported FPGA/emulated machines | The native system runs only in C128 mode; each model requires a separate capability/result entry |

Unknown expansions remain backlog entries when identified. I/O overlap,
incompatible operating modes, and absent physical resources need clear capability
reporting; software cannot make conflicting expansions operate simultaneously.

## Build sequence and exit gates

| Stage | Scope | Exit gate |
|---|---|---|
| R1: storage and correctness | Scrolling, complete directory parser, true copy/error semantics, module boundaries, reliable regression fixtures | Real disk streams and pixel checks; byte-exact large copies both directions; missing/full devices; physical C128 repeat |
| R2: Ultimate desktop | UCI discovery/service; Ultimate browser; mount/eject and drive settings; network/RTC panel | Full browse → mount → IEC file workflow without leaving desktop; errors and system-disk recovery verified |
| R3: platform services | Native C128 kernel, memory ownership/REU allocator, shared FS/driver registry, input/events, scheduler, file associations | Native dual-display workflows and safe concurrent app/service operation across memory configurations |
| R4: desktop toolkit | Both interactive displays, windows/widgets/file dialogs, clipboard, undo, pointer/keyboard, persisted preferences | Every interaction works with mouse or keyboard on either display; shared services used by apps |
| R5: productivity suite | Write/Paint/Sheet/Data/Publish/Organize; document/file compatibility and printing | Real document workflows, round trips and print fixtures compared with GEOS/Wheels/MegaPatch |
| R6: communications/media/tools | Terminal/transfers, media, archive/backup, developer/system tools; remaining UCI controls | Failure recovery, content integrity, peripheral output and session restore tests |
| R7: expansion certification | Hardware-family drivers, native filesystems/fastload, accelerated paths, legacy compatibility | Per-model hardware ledger with artifacts; graceful fallback/conflict handling |
| R8: distribution and finish | Clean-checkout build/SDK, installer/updater/recovery, manuals/help, versioned images, performance/accessibility/soak testing | Requirement-by-requirement audit passes; independently installable release with all above gates satisfied |

No stage is complete merely because its stubs compile or one happy-path test
passes.

## Current work and continuation

Stages R1 and R2 were first implemented in the earlier C64-mode desktop, which
this project no longer includes. The entries below record the native
implementation.

The first [native C128 kernel and memory ABI](NATIVE-KERNEL.md) now boots its
own D64 through BASIC 7 and manages 442 pages (113,152 bytes) across both RAM
banks. It provides generation/owner-checked handles, explicit reservations,
bounded read/write/fill and preflighted owner cleanup. Its two-screen memory
workspace is a first native client. See the
[native checkpoint](validation/2026-09-09-native-kernel/README.md) for CPU,
emulator and physical results and the remaining qualification gates.

The [native application lifecycle](NATIVE-APPS.md) now validates and loads
manifested PRGs into an owned 24 KiB slot, checks exact EOF/CRC, initializes
declared BSS and releases the app's RAM on balanced return or one-way exit.
Loader IEC channels are checked for conflicts and closed before app entry.
The native calculator uses this path, keeps 32 results in bank 1, reports
overflow/divide-by-zero and returns without discarding workspace allocations.
See the [app checkpoint](validation/2026-09-09-native-apps/README.md) for exact
fault/model, emulator and physical evidence for that earlier checkpoint.

The [native IEC file service](NATIVE-FILES.md) now provides two owned streams,
exclusive creation, bounded binary reads/writes, 32-bit positions and file
cleanup before application memory release. Read-only directory/sector-chain
checks establish exact file sizes, including empty and one-byte files. The
calculator exports its oldest-first history to a new named SEQ file and
reopens it for byte comparison. The [file-service checkpoint](validation/2026-09-09-native-files/README.md)
records exact images, passing coverage, retained failures and qualification
limits.

The [native Files and Apps browser](NATIVE-BROWSER.md) now consumes ABI 1.2
directory pages, caches up to 296 entries in bank 1, discovers app headers,
launches selected filenames and returns through owned cleanup. It provides
128-byte binary previews on both displays. The calculator inherits the selected
source device/format for verified export. The
[browser checkpoint](validation/2026-09-09-native-browser/README.md) records
the model, emulator and physical qualification separately. Full D81 enumeration
still rewalks directory pages and needs performance work.

The allocator now runs in the reserved low region, preserving public API
addresses and all 442 managed pages. Startup copies it before heap initialization
and makes the managed staging pages available for reuse. Observers use the shared buffer
in bounded chunks instead of writing over the low kernel. The
[resident-growth checkpoint](validation/2026-09-09-native-relocation/README.md)
records exact images and qualification. Main/low growth space is now 1,321/1,082
bytes; larger services still need explicit memory/lifetime records.

The [native banked text editor](NATIVE-EDITOR.md) now uses two owned document
contexts for transactional Open, preserves imported bytes and newline forms,
edits through 24-bit positions, and verifies exclusive Save As by reopening and
comparing every byte. Its 4 KiB allocations span both banks. The document format
addresses up to 96 KiB, subject to available heap and temporary Open capacity;
it does not yet use REU or disk backing. Literal find/replace supports case
control, wrapping, overlapping Find Next, counted replacement and cancellation;
its module shares the picker's reserved window. Selection, clipboard, undo and
the word processor's layout/printing features remain required.
The [search checkpoint](validation/2026-09-12-native-editor-search/README.md)
covers CPU failure/retry tests, both ROM text displays, large-file save/reopen,
and the five-app suite in VICE. Physical qualification remains open.
The [editor checkpoint](validation/2026-09-09-native-editor/README.md) records
the CPU, emulator and physical results, independent whole-disk readback and
the measured standard-IEC performance limit.

The [native Ultimate backend](NATIVE-ULTIMATE.md) adds owned absolute-path
streams to ABI 1.3, with foreign-context guards, checked 32-bit read extents,
verified writes and editor Save As. It reserves 4 KiB of bank 0; the managed
heap is now 426 pages. Both 8 KiB workspace blocks and the app slot remain
available. At that checkpoint the native browser and loader still used IEC.
The [Ultimate storage checkpoint](validation/2026-09-09-native-ultimate/README.md)
records twelve CPU reports, seven emulator suites and the physical C128 workflow,
including a 66,056-byte verified save through cartridge registers. Its measured
Open/verified Save As times are about 38/79 seconds, including hardware-harness
quiet and polling intervals.

The [native editor redraw checkpoint](validation/2026-09-09-native-redraw/README.md)
adds field-row updates, partial document repaint, two cached read pages and
24-bit visible-line offsets. It preserves complete redraw for structural and
viewport changes. The editor uses a 12 KiB allocation, and the kernel,
boot, calculator and browser PRGs retain their previous bytes. Broader shared
input/dialog services and further UI performance work remain required.

The [USB app checkpoint](validation/2026-09-09-native-usb-apps/README.md)
unifies IEC and Ultimate app loading under owned streams in ABI 1.4. The browser
accepts a full USB app path; calculator history is created beside its USB image
and verified after reopening. Source and boot-device contexts remain separate,
and checked cleanup precedes handoff. The change frees 264 main-kernel bytes
without reducing the 426-page heap. The editor and boot images retain their
preceding bytes. This provides direct USB launching, with directory navigation
and shared file dialogs still open.

ABI 1.5 now implements an owned Ultimate directory cursor through the existing
stream entries. The browser consumes one READ_DIR transaction across forward
pages, retains complete names and canonical paths, supports folders/parents
and restores selection by name after app saves reorder the listing. A second
page buffer preserves the previous page after failed/cancelled navigation.
The 426-page heap and boot/calculator/editor PRG bytes remain unchanged.
The [directory checkpoint](validation/2026-09-10-native-directories/README.md)
passes 17 CPU suites plus two targeted follow-ups, ten emulator workflows and
the full physical C128 workflow: 1,096-entry navigation past ordinal 255,
selection after saves reorder pages, nine independently verified files and
complete workspace/resource/desktop restoration. The audit retains an
interrupted harness attempt and two unexplained direct DMA bytes; CPU captures
remain the RAM authority.

The [shared file-dialog checkpoint](validation/2026-09-10-native-file-dialogs/README.md)
keeps the complete editor document allocated while browsing. All 18 CPU suites
and four targeted follow-ups pass, including 11 picker flows and a 66,056-byte
document with both workspace blocks. All ten native emulator workflows and
the complete physical USB/IEC workflows pass. Independent readback matches
nine USB files and four IEC files; five complete document captures match while
the picker has focus. Two interrupted IEC attempts remain archived alongside
the host connection fix and eight tests enforcing the no-replay boundary.
ABI 1.6 [shared focused fields](NATIVE-FIELDS.md) now provide bounded caret
navigation, insertion, forward deletion and independent clipping on both displays.
The [field checkpoint](validation/2026-09-10-native-fields/README.md) passes
all twenty CPU suites, all ten native emulator workflows and complete physical
USB/IEC qualification. App allocations and the 426-page heap remain unchanged.
The physical runs verify 57 USB and 24 IEC frame pairs, all nine USB files and
all four IEC files. A failed IEC boot exposed partial/empty REST uploads from
cartridge temporary-storage exhaustion. The retained recovery verifies the
deployed loader before starting it, restores the original desktop, and reclaims
only exact archived test images. Upload-size checks and reuse of a verified
recovery loader now protect qualification; 24 host fault checks pass.
The shared controls retain a 66,056-byte document and both workspace blocks
through a full 255-byte field edit and picker cancellation. Continue events,
list/viewport services and a larger module architecture, followed by the
native desktop/Ultimate apps and broader drive qualification. Integrate other selector
backends and complete drive media identity/recovery. Scheduling, 2 MHz/DMA regions, REU and
other expansion allocators, system-disk recovery and application parity remain
required. R3 is partial; the editor milestone does not complete it or the OS.
The [next native platform steps](NATIVE-PLATFORM-NEXT.md) identify the memory
constraints, observer changes and document/service acceptance gates for that work.

The [ABI 1.7 module loader](NATIVE-MODULES.md) now loads the editor picker
from the original app source into its existing 79-page allocation. Frozen-image
CPU checks cover loader faults, token generations, caller/entry/allocation
bounds, both Ultimate contexts, warm reuse and complete document retention.
All 22 CPU suites and ten emulator workflows pass, as do 51 distinct host fault
checks. The first physical USB run failed during a browser rescan before reaching
the editor. Its initiating transport failure remains unresolved; the original
desktop was restored and private resources were reclaimed with full byte proofs.
The complete USB retry and physical IEC workflow pass on the same images.
The [module checkpoint](validation/2026-09-11-native-modules/README.md) records
194 screen pairs, 1,203 CPU captures, five complete retained documents and
independent comparison of ten USB files and all four IEC document-disk files.
The [desktop migration plan](NATIVE-DESKTOP-MIGRATION.md) records why the earlier
C64-mode drawing code was not reused and the first display-ownership acceptance gate.
The isolated [display lifetime candidate](validation/2026-09-11-native-display-lifetime/README.md)
passes 25 CPU suites, ten existing emulator workflows and five graphics
lifecycles. The later [window clipping and layout candidate](validation/2026-09-11-native-graphics-clipping/README.md)
passes 1,243 CPU cases and five complete pixel/return workflows. It also retains
a 66,056-byte edited document, surface and picker cache with 31 pages free in a
CPU model using the actual editor and kernel code. Its renderer fits the existing
editor module window; save verification, replacement and cleanup pass. This
models foreground calls and does not yet provide an interactive graphical editor.
Masked band processing reduces the preceding identical scene's modeled
instructions by 3.741 times. The final drawing and display-lifetime sources
are now integrated with the separate native desktop build. The concurrent
graphical-editor workflow remains a model fixture. Physical video pixels and
timing, VDC bitmap presentation and pointer/window focus remain open.

The private [native launcher checkpoint](validation/2026-09-11-native-desktop-launcher/README.md)
adds direct desktop boot, keyboard selection, Calculator/Editor/Files handoff,
VDC text controls and app return. Nine launcher CPU workflows pass on both
private kernels, alongside five additional boot-kernel suites and five emulator
workflows. Capture audits match 26 complete surfaces and 1,664,000 rendered
pixels. Missing app files and unavailable graphics leave usable controls.
The launcher and surface are released before opening an app; no persistent
desktop heap reservation is added. Physical graphics, pointer/window input,
VDC bitmap presentation, persistent state and native Ultimate panels remain
open. The subsequent [production integration](validation/2026-09-12-native-desktop-integration/README.md)
reproduces the same kernels/apps/disks from standard source locations, passes
eighteen desktop CPU workflows and 1,243 drawing cases, and checks six VICE
workflows with 2,112,000 complete rendered pixels. The separate desktop target
preserves the diagnostic workspace build. Physical qualification is recorded
independently, including three incomplete attempts, full restoration and
verified private-file cleanup. The final attempt retains seven differing
restored-buffer bytes and 71 unexpected captured bytes. The cause remains
unproven; capture-transport investigation precedes another full physical run.

The [capture-context checkpoint](validation/2026-09-12-native-capture-context/README.md)
qualifies the ROM's nested interrupt mapping in CPU/VICE tests and retains a
further restored physical attempt. All boot VIC/VDC payloads matched, but the
strict observer rejected three ABI bytes consistent with consumed keyboard
input. The allocator tables matched; the source of physical input is not
established. This checkpoint does not complete physical desktop qualification.

The next [owned-abort completion change](validation/2026-09-11-native-owned-abort/README.md)
is implemented as fifteen resident bytes with no additional heap reservation.
It preserves the initiating transport error while waiting for the abort's
completion, with a bounded return and retained owner if completion stays
uncertain. All 24 CPU suites and ten emulator workflows pass on its exact
images. The first physical USB attempt failed during a saved-file reopen through
DOS context 2 after the editor had verified the save. The full unmodified retry
passes, including independent readback of ten closed files, all native cleanup
and restoration of the desktop, drives and DOS paths. All 87 current host fault
checks also pass. Physical IEC qualification and the final combined audits now
pass, including all four document-disk files, the edited 66,056-byte save,
restoration and confirmed removal of the three private temporary uploads.
Neither physical failure's initiating cause has been established.

The [complete ABI 1.9 physical desktop run](validation/2026-09-12-native-desktop-abi19-hardware/README.md)
now passes the native boot, Calculator/Editor/Files workflow, retained selection,
full display-RAM and resident-code comparisons, final workspace and all 426
pages free. It retains 66 captures, 101,274 CPU payload bytes, 264 matching
borrower pairs and 1,906 exact RAM-write receipts. The original deployment,
drives, settings, DOS paths and controls are restored; both private uploads
have complete readback and confirmed deletion. Physical video pixels, the
earlier failure causes and native Ultimate panels remain separate open work.

The user-requested [Claude app](../apps/claude/README.md) is now built into both
native desktop suite disks, with an A shortcut, Linux PTY bridge, native
keyboard accounting, serial NMI mapping, custom glyph restoration and desktop
return. The five-entry launcher also includes the [Ultimate information panel](NATIVE-ULTIMATE-CONTROLS.md).
These are ABI 1.10 software candidates; the prior ABI 1.9 physical pass does
not establish native serial or Ultimate-panel hardware qualification.
The [shared five-app workflow](validation/2026-09-12-native-suite-workflow/README.md)
exercises every launcher entry, two serial sessions and final memory recovery.
Its physical attempt stopped during the initial resident capture: three inputs
were consumed, the last was cursor down, and selection changed from 0 to 3.
No scripted input or added app launch had occurred. The changed resident bytes
are declared drawing state; input origin remains unestablished. The original
deployment was restored and both owned uploads were verified and removed.
The [bounded input trace](validation/2026-09-12-native-input-trace/README.md)
then recorded four Down and two Insert ROM scan/consumption pairs during a
CPU capture, with no events during idle or pause-only phases. Insert used
scan index 89, beyond the normal keyboard table. The initiating signal is
still unknown. A separate high-memory host read matched mapped BASIC ROM,
leaving the diagnostic's borrowed high-RAM restoration unverified; its
original-deployment restoration and owned-upload cleanup passed. Corrected
bank-aware diagnostic access and full keyboard/control-port testing remain
required before native physical suite qualification.
The [native keyboard guard](NATIVE-KEYBOARD.md) now rejects indices outside
the 88-key matrix while preserving valid callbacks and counting rejected
activity. Real ROM CPU tests and a VICE joystick negative control reproduce
index 89 producing Insert without the guard. The shared five-app workflow
passes with the guard and unchanged 426-page capacity. Physical valid-index
Down events and their initiating signal remain unresolved.
Additional Ultimate controls, persistent preferences, window/pointer services
and the remaining application/parity roadmap remain open.

Before calling the complete OS finished, audit every requirement row above,
all named app/hardware/firmware combinations, documentation,
packaging and performance gates. Missing hardware evidence remains unverified;
it does not become support by changing the wording of the roadmap.

The native suite Files copy dialog now streams IEC and Ultimate files through
the owned file API, with an editable destination/picker, exclusive creation,
32-bit progress, cancellation, complete reopened comparison and retained close
retry. Both suite disks now include its checked graphics and destination-picker
modules. The source remains read-only.
Zero-byte output to IEC is rejected before create: standard Commodore DOS
closes an unwritten file with a CR byte, and the native backend has no truncate
operation. Zero-byte output to Ultimate is supported. Rename/delete, directory
copy, batching, media identity, recovery and physical qualification remain open.


The [native pointer checkpoint](validation/2026-09-12-native-pointer/README.md)
adds mouse input to the blue desktop's five app buttons. Its pointer and input
state are released before every app/workspace handoff. Both suite disks include
the change. The blue desktop remains the intended unified shell; graphical
windows/widgets on both displays remain R4 work.


The [graphical Calculator checkpoint](validation/2026-09-12-native-calc-gui/README.md)
extends the intended blue desktop appearance into a native app. Both suite
disks include the keypad, history and save/cancel controls, with the existing
VDC text view and fallback on both consoles. Desktop and Calculator share the
1351 driver; rectangle focus and scene interpreters are reusable app libraries.
The resident kernels and diagnostic Calculator retain their program bytes.
This qualifies another part of the desktop migration; other applications,
window management, graphical VDC operation, physical qualification and every
remaining roadmap row still apply.

The [native Paint checkpoint](validation/2026-09-13-native-paint/README.md)
adds the sixth desktop icon and carries the blue controls into a 320×200 hires
picture editor. It includes connected pencil/eraser strokes, a 16-color
palette, keyboard drawing with viewport scrolling, one-step undo/redo,
verified exclusive Save As and staged Open through the shared file picker.
Desktop, Calculator and Paint now share a ROM-visible filter for port-1 mouse
button transitions, with complete callback/function-key restoration. The
resident kernels retain their bytes. This is an initial APP-PAINT milestone;
advanced tools, image interchange, printing, graphical VDC editing, physical
qualification and the remaining roadmap are still open.


The ABI 1.11 [native Ultimate controls](NATIVE-ULTIMATE-CONTROLS.md) extend the
blue appearance to hardware, drive, network and clock pages. Mount/eject uses
the shared packet service, a complete path and explicit destination, fresh
inventory, sticky system-slot protection and checks for open files in both DOS
contexts. Confirmation starts on Cancel and is consumed before I/O. The UI
reports firmware acceptance separately from mounted-media verification; neither
a timeout nor Refresh silently replays an operation. The command and keyboard
entries fit existing reserved memory and retain the 426-page heap. This
[software checkpoint](validation/2026-09-13-native-ultimate-drives/README.md) passes; physical drive operations,
media identity, settings, image creation and the remaining roadmap stay open.


The [graphical Files migration](NATIVE-FILES-GUI.md) carries the shared blue
bitmap and yellow focus into lists, byte viewing, device/path fields and copy.
Its core retains data and keyboard ownership while checked graphics and picker
modules alternate in one window. Failed picker aborts or module-source closes
retain ownership and prevent further file work until explicit cleanup succeeds.
Fields repaint changed cells, and mouse Cancel is polled during both copying
and verification. The app uses 93 pages plus its optional 36-page surface,
without changing the kernel or 426-page heap. The [software record](validation/2026-09-13-native-files-gui/README.md)
passes; physical testing, graphical picker/VDC work and every other
remaining roadmap item still apply.

The [graphical Editor migration](NATIVE-EDITOR-GUI.md) carries the blue bitmap
and yellow focus into document editing, mouse caret placement, Open/Save As,
Find/Replace, Go To and device controls. Search and graphics share one checked
module; the picker replaces it while the complete document remains allocated.
The core owns keyboard state and descriptors, preserves full paths, blocks
file work after uncertain cleanup and supports text fallback with explicit
graphics retry. The 96-page app and 36-page surface fit a document beyond
64 KiB without changing the kernel. The [software record](validation/2026-09-13-native-editor-gui/README.md)
passes; physical testing, selection/clipboard/undo, session recovery, styled documents,
the graphical picker/VDC and the remaining roadmap stay open.


The [shared graphical picker](NATIVE-PICKER-GUI.md) extends the blue interface
through Editor, Files, Paint and Ultimate. It retains existing navigation,
raw paths, caller state and checked resource cleanup. Compact IEC cache records
preserve all 296 D81 entries beside a document over 64 KiB. The [software qualification](validation/2026-09-13-native-picker-gui/README.md)
passes; physical installation,
VDC bitmap UI and the wider roadmap remain open.

The [Claude graphical companion](NATIVE-CLAUDE-GUI.md) completes blue VIC
frames for the six current suite apps. Connect, Repaint, Desktop and status
paging have icon buttons, yellow focus, keyboard controls and 1351 input.
The VDC retains the entire terminal; Ctrl+Help selects local controls while
ordinary terminal keys retain their meanings. All 25 panel rows, raw colors
and live glyphs remain available. The 75-page client and its 36-page surface
use the existing kernel. The [software qualification](validation/2026-09-13-native-claude-gui/README.md) passes; native
physical serial, an authenticated session, a VIC-only terminal, VDC bitmap
presentation and the remaining application roadmap still require work.

The [graphical VDC Calculator](NATIVE-CALCULATOR.md) is the first app using the
shared VDC lifetime, pointer and incremental surface presenter. Its keypad,
history and verified-save dialog now follow the blue interface on both displays.
Mono VDC focus uses reverse ink; color VDC focus uses yellow. The original VDC
memory remains owned until restoration succeeds, including fatal history errors.
A bounded, CRC-checked packed kernel boot file makes room on D64 without changing
resident RAM or app ABI. Applying VDC graphics to Editor, Files, Paint, Ultimate,
Claude and the picker still requires code-space and backing-store work.

The [bank-1 executable component SDK](NATIVE-BANKED.md) addresses part of that
code-space limit. A checked stream loader loads a separate component into
owned bank-1 `$6000..$bfff`, and a returning bridge restores the standard map
around native calls. The example runs the REU arena there while preserving
low bank-1 document data, borrowed system registers and failed-probe recovery.
The resident kernel, shipped suite images and 426-page heap are unchanged.
Moving Editor/Files/Paint/VDC services into these components, backing documents
with REU, shared scheduled driver ownership and physical qualification remain
the next steps; this SDK milestone does not complete those app migrations.

The [bounded LZSA2 boot wrapper](NATIVE-BOOT-MEDIA.md) increases free space on
the full D64 suite from 2 to 15 blocks. It preserves the unpacked resident
kernel, every app payload, and the 426-page heap. The shared bank-1 VDC service
is still under development; this packaging change provides room for that work
without changing the desktop layout or marking the remaining app views complete.

The [shared VDC service](NATIVE-VDC-SERVICE.md) is the first suite component
using that executor. Desktop and Calculator load `VDSVC.PRG` from their original
source, retain recovery before discarding it, and share REU-backed VDC snapshots
with RAM fallback. Each bank-0 app saves eight executable pages; the component
uses thirty bank-1 pages while active. Editor document backing, remaining VDC
app views, scheduled drivers and physical qualification remain open.

The [packed app startup](NATIVE-APP-PACK.md) recovers 146 D64 blocks, leaving
147 free blocks in the complete suite. Its temporary decoder and input storage
are released before app entry. Original app bodies and module layouts remain
exact, and the resident kernel and 426-page heap do not change. This removes
the immediate distribution-space constraint; it does not increase the app
code window or complete the remaining display and document migrations.

Ultimate now shares the graphical VDC presenter across its panels, image picker
and explicit drive confirmation. Temporary picker scratch moves into owned
bank-0 heap memory, leaving room for the retained display client in the 96-page
app. REU backing leaves 264 main-RAM pages free, with RAM fallback on either
VDC size. Display faults pause drive actions until Escape restores the saved
screen. The suite has 134 free D64 blocks and 2,630 D81 blocks. Editor, Files,
Paint and Claude display migration, document backing, physical qualification
and the rest of this roadmap remain open.

Paint now presents its image viewport, tools, keyboard brush, file dialogs and
picker on either display. Ten separately owned bank-0 scratch pages and one
shared scene renderer make room for the VDC client without reducing its
320×200 picture, undo, verified file operations or the resident 426-page heap.
REU screen backing leaves 182 main-RAM pages free; picture/undo remain in main
RAM. Display failures retain unsaved artwork while restoration is retried.
The full suite has 134 free D64 blocks and 2,630 D81 blocks. Editor, Files and
Claude VDC migration, document backing, scheduling, physical qualification
and the remaining application parity requirements are still open.


### 2026-09-14: Files on both graphical displays

The [Files VDC qualification](validation/2026-09-14-native-files-vdc/README.md)
extends the blue interface through the file list, byte viewer, editable fields,
copy/verification progress and destination picker on both displays. One retained
VDC component and screen backup survive graphics/picker module swaps. Sixteen
owned scratch pages make room for the client within the unchanged 96-page app
allocation; fields remain inside the checked loader allocation. Files leaves
211 main-RAM pages with REU backing before additional directory caches.

Display failures pause an active copy at its current chunk, preserving streams,
source bytes and the exact destination prefix until Escape can restore the
screen. Picker input is guarded before and after redraws. Module failures keep
their error codes through VDC restoration; app replacement preserves Files'
launch identity until cleanup succeeds. Refresh reacquires graphics after a
usable text fallback. The suite has 140 free D64 blocks and 2,636 D81 blocks.
Editor and Claude VDC migration, document backing, scheduling, physical
qualification and every other unimplemented roadmap item remain open.

The shared picker's text fallback currently retains the graphical Tab-focus
help line even when bitmap controls are unavailable. Its text Enter/R/D/F/S
shortcuts remain functional; selecting help text for the active presentation
is a remaining shared-picker cleanup item.


The [Editor VDC qualification](validation/2026-09-14-native-editor-vdc/README.md)
extends the blue document, caret, search/file controls and shared picker to both
monitors. The component and screen backup survive picker swaps. An owned,
zeroed sixteen-page workspace keeps transfer buffers and saved keys separate
from module code. Failed display updates pause file transfers and search at
visible progress boundaries; failed restoration retains document bytes,
completed replacements, output position, stream ownership and stack state.
After restoration, a complete text repaint precedes new input. Ctrl-L retries
VDC graphics. The original diagnostic Editor and the other app programs remain
unchanged.

At that VDC checkpoint, Editor documents still consumed main RAM in 4 KiB chunks. The active VDC service
reduces their capacity; the prior 66 KiB graphical-document result no longer
applied with that service loaded. Memory-limit Open preserved the old document,
and REU-backed documents were the next memory requirement. Claude VDC controls,
clipboard, undo, window management, scheduling, office apps, printing, expansion
drivers, physical qualification and the rest of this roadmap also remain open.

The shared REU document implementation now gives Editor one resizable extent
per context, using the same arena as the VDC snapshot. A memory lease retains
documents and the provider after display close; graphics can reopen without
losing them. The 24-bit document path passes software tests beyond 1 MiB, and
staged Open on a 128 KiB REU preserves a dirty original when capacity runs out.
A clean REU refusal keeps the existing RAM path. Failed transfers poison the
context and refuse Save As; uncertain probe and temporary-allocation cleanup
retain their owners for recovery. The service adds three bank-1 pages, while
REU document growth consumes no additional main RAM. Physical qualification,
live expansion reconfiguration, disk-backed documents, clipboard, undo,
scheduling and the remaining app/desktop work are still open.


### 2026-09-14: Claude controls on both displays

The [Claude display qualification](validation/2026-09-14-native-claude-displays/README.md)
completes the blue control interface across the six current suite apps. Claude
retains all 80×25 terminal cells and attributes plus its live font in owned RAM.
The VIC can show either terminal half and either row page. Ctrl+Help or the
right mouse button opens blue controls on the VDC; Terminal/Escape returns to
the complete current text screen. Pending protocol commands survive that handoff.

Serial NMI continues during bank-1 graphics calls under the existing 192-byte
host window. Bounded display waits and retained recovery prevent premature
release of terminal bytes, snapshots, components or input callbacks. Clean
model/service refusals retain usable terminal paths. VICE cold boots exercise
both display choices, real mouse/ROM keys, incoming PTY output while controls
are visible, acknowledged exit and complete desktop restoration. The 94-page
app leaves 231 main-RAM pages with a REU screen backup. The suite retains 124
free D64 blocks and 2,620 free D81 blocks. The resident kernel, VDC provider
and other app programs remain byte-identical to the prior checkpoint.

This completes the current apps' initial graphical display migration, not the
OS completion goal. Office apps, printing, clipboard/undo, window management,
scheduling, generalized display switching, expansion drivers, physical
qualification, authenticated Claude use and all other open checklist items
still require implementation or evidence.

### 2026-09-14: Manual Ultimate clock controls

The [clock software checkpoint](validation/2026-09-14-native-ultimate-clock/README.md)
adds **Set time** to the Ultimate app's blue Clock page on both displays.
The shared field supports keyboard editing and mouse caret placement. Calendar
validation accepts 1980–2079, including Gregorian leap days. Confirm sends one
binary SET_TIME packet; a separate validated GET_TIME reading must match the
requested value within two advancing seconds before the app reports confirmed
readback. Different or uncertain results are explicit, and Refresh only reads.
Cancellation also reads the current clock again.

The app uses 91 code pages, an initialized eleven-page bank-0 workspace and
its existing 36-page surface. REU display backing leaves 255 managed main-RAM
pages free; RAM backing leaves 191 with a 16 KiB VDC or 183 with 64 KiB. Workspace
refusals preserve foreign allocations and leave keyboard/display state intact.
Field edits update two VDC rows; pointer movement retains the rest of the panel.
The resident kernels, shared VDC component and other app programs retain their
bytes. Independent builds reproduce all 34 native program/disk images, and the
suite retains 121 free D64 blocks or 2,617 free D81 blocks.

This adds manual cartridge-clock control. Native physical RTC writes,
power-cycle retention, system/cartridge clock status, offline system-clock
fallback, window management, app switching and the other open roadmap items
remain work. The blue native desktop remains the suite interface; the native
diagnostic workspace retains its separate role.

### 2026-09-14: Editor text selection

The [selection checkpoint](validation/2026-09-14-native-editor-selection/README.md)
adds Ctrl-B marking, Ctrl-A Select All and Ctrl-G/Escape clearing to the blue
Editor on both displays. A third toolbar page exposes Mark, All and Clear.
Mouse drags select text and scroll at document edges; keyboard commands cancel
the pending drag release. Typing or Return replaces the range, and Del removes
it. Selection uses 24-bit byte positions, preserves CRLF boundaries, and stays
available across Save As and picker swaps. Save As continues to save the full
document.

Large deletions reuse document storage. Replacement reserves any required
growth first, so a refused allocation retains both bytes and selection.
Renderer fallback and display-restoration failures retain the document until
input can resume. The app keeps its 96-page code allocation and 16-page
workspace; the suite has 118 free D64 blocks or 2,614 free D81 blocks.
Independent builds reproduce all 34 images, with only Editor, its matching
modules and the four suite/workspace disks changing from the clock checkpoint.

The software record includes 22 CPU jobs covering 25 cases, both VICE startup
displays, full saved-file and REU comparisons, and a standalone archive audit.
Shared clipboard exchange, Editor undo, session recovery, window management,
app switching and the remaining parity requirements remain open. This build
has not been installed on the physical C128.


## Shared text clipboard checkpoint (2026-09-14)

Editor and Claude now exchange byte text through a session clipboard. Editor
provides selection Copy/Cut, Paste that can replace a range, and Clear. Claude
copies all 25 retained terminal rows to ASCII and negotiates a framed bracketed
paste with the matching host bridge. Complete payload validation precedes host
input delivery; no Return is appended and unconfirmed transfers are not retried.

ABI 1.13 initializes 27 private session bytes and reserves heap owner 31 for the
shared source library, preserving the resident entry addresses and 426-page
heap. The initial clipboard is limited to 15 KiB in checked bank-1 RAM outside
the component code window. Copy stages new bytes before replacing the previous
item; app exits preserve the published clipboard. Editor loads `EDCLIP.PRG` in
its existing module window. Claude keeps its original VDC font in a separate
owned allocation so the clipboard fits in its app image.

The [clipboard qualification](validation/2026-09-14-native-shared-clipboard/README.md)
records the exact source and test inputs, loaded-CPU app handoffs and failure
checks, private VICE cold boots and an independent build of all 35 program/disk
images. The [user and SDK guide](NATIVE-CLIPBOARD.md) documents controls,
allocation limits, cancellation and cleanup. Physical deployment, persistent
or REU/image scraps, Editor undo and wider application parity remain open.

## 2026-09-14: native Editor span history

Editor now shares a banked span journal through `VDSVC.PRG`. Ctrl-Z / Undo,
Ctrl-Y / Redo and Ctrl-U / Forget accompany the existing clipboard controls on
a fifth toolbar page. Up to sixteen changes retain removed and inserted bytes
with 24-bit positions. Typing, backspace, ranges, Cut/Paste and literal
replacement use the same history; verified Save As records the clean position,
and New or successful Open resets the journal.

The [history contract](NATIVE-HISTORY.md) specifies RAM/REU ownership, staged
publication, redo/oldest eviction, failure retention and bounded replay. RAM
memory pressure may reclaim optional history so an edit can proceed; Editor
announces successful unrecorded edits and refuses uncertain document transfers.
The enlarged provider occupies 39 bank-1 pages. Editor keeps its 96-page app
and existing module window allocation; the renderer ends at `$bff5`.

The [history qualification](validation/2026-09-14-native-editor-history/README.md)
tracks the exact input versions, CPU app/failure workflows, private D64/D81
VICE cold boots and independent image/capture audit. Physical deployment,
grouped edits, session recovery, undo in more apps, image/REU scraps and the
remaining desktop/office/expansion roadmap stay open.


## 2026-09-14: Ultimate folder creation in native Files

The [New folder dialog](NATIVE-FOLDERS.md) adds New dir and Ctrl-K to the
Ultimate file list. It uses the blue controls on both displays, shared field
editing and the 1351 pointer. Creation closes the browser's owned cursor,
submits one exclusive absolute-path request and checks directory metadata.
Back refreshes the parent listing; failed or uncertain requests are not replayed.

The [folder qualification](validation/2026-09-14-native-ultimate-folders/README.md)
retains fourteen passing CPU suites, two private VICE workflows and an independent
build that reproduces all 36 program and disk images.

The dialog stays in the existing checked `FSVIEW.PRG` module window. Files
retains its 96-page allocation and the kernel keeps all 426 managed pages.
The suite still contains fifteen disk entries, with 86 free D64 blocks or
2,582 free D81 blocks. Rename/delete, IEC folders and partitions, media identity,
recursive copying, physical qualification and the wider completion roadmap
remain required.


## 2026-09-14: Filename search in the blue Files app

[Find / Ctrl-F](NATIVE-FIND.md) selects the next filename containing the entered
text and wraps at the end. IEC searches the complete retained directory snapshot;
Ultimate streams full names using 32-bit positions and a second page buffer.
Cancellation, absent matches and errors preserve the published selection.
The shared modal keeps its graphics module resident, supports both displays
and accepts keyboard or 1351 Back/X cancellation while scanning.

The matcher has independent byte-string oracle coverage, including all single
byte values, ASCII/PETSCII case folding, 127-byte queries and end-of-name matches.
Directory workflows cover 296 IEC entries, 521 Ultimate entries, full 255-byte
names and both DOS contexts. The [search software checkpoint](validation/2026-09-14-native-file-search/README.md)
retains the executed inputs, complete displays, private VICE workflows and
independent clean build.

Files retains its 96-page app allocation and the kernel keeps all 426 managed
pages. The sixteen-page workspace shares inactive copy scratch with IEC directory
page staging. All three Files modules remain paired with the matching core.
The suite still has fifteen entries, with 81 free D64 blocks or 2,577 free D81
blocks. Recursive search, sorting, persistent filters, picker integration,
physical qualification and the wider desktop/office/expansion roadmap remain open.

## 2026-09-14: Native Sheet desktop app

[Sheet](NATIVE-SHEET.md) now opens from the seventh desktop card or S shortcut.
Its 8 × 32 workbook supports editing, checked integer formulas, scrolling,
keyboard/1351 controls and both displays. Open stages and validates a complete
workbook before publishing it. Save As exclusively creates a USHT file and
reopens it for a full byte comparison before clearing the dirty flag.

The [software checkpoint](validation/2026-09-14-native-sheet-desktop/README.md)
records CPU workflows, two private VICE IEC round trips and a clean rebuild of
all 37 program/disk images. The app needs 93 pages, with 32 more for its workbook
and temporary staging during New/Open. The seven-app suite has 34 free D64
blocks or 2,530 free D81 blocks.

Decimal arithmetic, formatting, range/clipboard operations, undo, printing,
picker integration, geoCalc/CSV exchange and physical qualification remain
required. The broader OS, office and expansion objectives remain open.

## 2026-09-15: Sheet cell Undo/Redo

Sheet now supports Ctrl-Z Undo and Ctrl-R Redo for the most recent cell edit
or Clear. Complete source text is restored and formulas are recalculated.
Unchanged edits keep history, new edits replace it, successful New/Open reset
it and Save As preserves it. Both Undo and Redo mark the workbook unsaved.
A failed source read retains retry history; an uncertain write blocks further
mutation until the workbook is replaced.

The [software checkpoint](validation/2026-09-15-native-sheet-undo/README.md)
records focused history/failure tests, a VICE IEC round trip, disk validation
and a clean rebuild of all 37 images. Sheet now reserves 94 app pages, with
33 free D64 blocks or 2,529 free D81 blocks in the suite. Multi-step/range
history, clipboard, decimal types, formatting, printing, picker integration
and physical qualification remain open.

## 2026-09-15: Sheet range functions

Sheet now calculates MIN, MAX and COUNT over rectangular ranges, alongside
SUM. Empty/text cells are ignored; an empty numeric set returns zero. COUNT
counts numeric values and resolves dependencies, propagating cell errors.
All functions accept reversed endpoints and case-insensitive names.

The [range-function checkpoint](validation/2026-09-15-native-sheet-ranges/README.md)
records host/6502 oracle tests, a loaded-app save/reopen and undo workflow,
a VICE file/display regression, media validation and a clean rebuild. The
app uses 96 pages; suite disk space remains 33 D64 / 2,529 D81 blocks. Decimal
types, further functions, formatting, clipboard/picker integration, printing
and physical qualification remain open.

## 2026-09-15: Modular Sheet and shared clipboard

Sheet now uses a checked `$b100` module window for calculation, its display
font and the shared clipboard library. Workbook state, results, undo history,
display ownership and the C stack remain in the core. The three modules are
bound to the matching app CRC and loaded from its original IEC/Ultimate source.
Missing/corrupt calculation code invalidates results while retaining source;
restoring the module and accepting the cell again retries calculation.

Ctrl-C/X/V exchange one complete ASCII cell source with the session clipboard.
Cut publishes before clearing; Paste validates the entire item and recalculates.
Empty, oversized, multiline and non-ASCII items are refused without truncation
or changing the workbook. Literal formula references are retained.

The [module/clipboard checkpoint](validation/2026-09-15-native-sheet-clipboard/README.md)
records frozen CPU workflows, cross-app exchange, both VDC sizes, private VICE
clipboard/IEC workflows, complete media validation and a 40-image clean rebuild.
The app remains 96 pages; the 19-entry suite leaves 16 free D64 blocks or 2,512
D81 blocks. Range clipboard/history, caching, shared picker integration, decimal
types, formatting, printing and physical qualification remain open.
