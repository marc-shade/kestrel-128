# MegaPatch 3 manual comparison

Reviewed 2026-09-10 against all fifteen pages of the supplied
[GEOS-MegaPatch 64/128 User Manual](../../mp3-manual-en.pdf), edition dated
2019/Jan/27 on page 1. Printed and PDF page numbers agree. The PDF is a scan;
this review used rendered page images, including the hardware-driver tables.
Source SHA-256:
`085ab827d1b560d5780550724c7a606881b1454716052627fc534f4cb844d2c7`.

The reference column below describes this manual's claims. It is documentary
evidence; the remaining runtime comparison must exercise the corresponding
MegaPatch release and Kestrel on recorded configurations. Wheels, GEOS application
manuals and format compatibility need separate evidence. The
[completion roadmap](IMPLEMENTATION-ROADMAP.md) remains the full acceptance
checklist. The native field build currently passes twenty CPU suites and all
ten native emulator workflows; physical qualification is running. The
[local reference inventory](REFERENCE-FIXTURES.md) identifies installation and
application disks by hash and flags images that need further inspection.

## Requirements and acceptance checks

| ID / reference pages | Manual behavior | Current Kestrel coverage and required acceptance |
|---|---|---|
| MP-INSTALL: 2, 5–6 | Validates setup data, shows destination disks and free space, offers complete/custom installation, checks required files, detects drives/input and creates a bootable disk. | Native images have checked manifests and a reproducible host build. Add an on-machine installer with required/optional components, destination capacity checks and input-driver fallback. Test absent/read-only/full media, damaged packages, partial installation and recovery. Preserve existing files until the replacement can be completed. |
| MP-BOOT: 3, 6–8 | Uses separately loaded system components, boot-drive configuration, a selectable expansion device, a desktop fallback prompt and an optional reboot path through retained expansion RAM. | Kestrel has native cold boot and returns to its IEC system browser. Add versioned system modules, boot inventory, selectable system/data sources, missing-module/desktop recovery and a validated warm restart. Test a corrupt retained image, replaced boot media and changed device addresses; the native kernel currently requires a fresh load before entry. |
| MP-DRIVES: 3, 9, 14–15 | Configures four logical drives, switches device types, images and partitions, can cache drivers in expansion RAM and supports several native/RAM/partitioned backends. | Native Kestrel currently selects IEC devices and explicit D64/D71/root-D81 geometry, plus Ultimate contexts and folders. Add logical-device mapping, type/media discovery, selected partition/image persistence, driver lifetime management and capability-based dispatch. Test conflicting bus addresses, missing devices and changing media while an app is suspended. |
| MP-EXPANSION: 4, 7, 10, 14 | Supports several expansion families, reserves system memory, exposes an allocation overview and permits explicit reservations for software outside its allocator. The manual distinguishes its internal memory limit from memory available to extra RAM-disk drivers. | Kestrel has a 426-page native base-RAM heap. Add independently probed expansion pools, explicit ownership/reservations, alias detection, shared allocation with RAM disks and bounded transfer drivers. Test advertised sizes against actual alias behavior, including 16 MiB configurations where available; preserve unrelated expansion data. |
| MP-MEMORY: 10 | Separately configures task slots and printer-spool space; creating RAM disks can reduce these resources. C128 task storage has different requirements from C64. | Add explicit memory budgets and complete admission checks for suspended apps, display state, services, printer jobs and RAM disks. Refuse an operation without disturbing existing allocations when a pool cannot satisfy it. Base-RAM documents and workspaces already have retention tests. |
| MP-FIELDS: 9–10 | Text fields support Left/Right, Home, clearing and insertion of a space; the cursor's flashing speed is configurable. The documented full-field insert behavior discards the last character. | ABI 1.6 implements bounded navigation, middle insertion, forward/backward deletion, Ctrl-U clear, filters and separate viewports on both displays. Kestrel refuses an insertion at maximum capacity and preserves every existing byte. Clear-key mapping, configurable blink/repeat and pointer placement remain input work. Test both physical keyboards and programmable-key expansion, plus maximum-length and cancelled-picker fields. |
| MP-MENUS: 9, 13 | Mouse movement highlights pull-down choices, controls pointer movement within a menu and supports tabbed pages with text fields, checkboxes, buttons and app callbacks. | Native graphical menus and general widgets remain open. Define focus, hit testing, keyboard traversal, clipping, event delivery and callback ownership. Test leaving a menu in each direction, activation once per input action, disabled controls, overlapping windows and both displays. |
| MP-CONFIG: 9–11 | A central configuration program persists drive, system, memory, screen, menu, input and printer settings. Optional features can be disabled; input driver and keyboard layout can be changed. | A native configuration registry and application are still required. Version settings by service, validate unsupported choices and recover from damaged persistence. Test restart, driver removal, layout change and independent display/input preferences. |
| MP-RTC: 10 | Attempts RTC detection and offers manual device selection, disabling the RTC and updating the system clock. | A native clock-source service is still required. Add explicit clock-source status, manual override, unavailable-device fallback and persisted source selection. Test offline boot, source loss, invalid time and power-cycle retention on each available RTC family. |
| MP-TASK: 10–11 | Loads several applications and switches among them; only the active application runs. It exposes task slots and a task list. Forced closure and media changes have documented data-loss risks. | The native loader currently replaces one foreground app. Add owned suspend/resume records for RAM, screens, input, files and backend state; a task list and normal close protocol; recovery when a task fails. Verify editing two independent documents, repeated switching and cleanup under memory pressure. Keep background-service scheduling as a separate requirement in the broader roadmap. |
| MP-ASSOC: 11 | Starting a document can select its application; a desk accessory can return to the previous app. Task switching enables text and image transfers between applications. | Add document/application associations, accessory return contexts and an owned clipboard with text/image formats. Test opening a document from the browser, cancelling app startup, unknown types, transferring between two live documents and returning from an accessory without losing focus or data. |
| MP-SNAPSHOT: 12 | Saves a screenshot as a geoPaint image with an editable filename and chosen destination drive. | Host test captures currently observe both screens. Add an in-OS screenshot command, destination selection, explicit source display and a documented file encoder. Verify output in an independent viewer, including 40/80-column or bitmap differences and disk-full/cancel cases. |
| MP-SELECT: 12 | The shared selector supports list navigation and scroll controls, filename searching, repeated matches, exact-name opening, file metadata and protection controls, alphabetic sorting, and common/custom action icons. | The native picker retains full names and the caller's document, including paging beyond ordinal 255. Add keyboard search, pointer scrolling, sorting, metadata, protection actions and common action widgets across backends. Test duplicate/prefix/raw names, metadata failures, search with no match and retained selection after changes. Kestrel sorting should keep disk order unchanged unless a distinct write operation is requested. |
| MP-PRINT: 10–11, 13 | Selects printer drivers, reserves spool memory, queues documents, permits manual or idle-time printing, switches jobs and supports page selection and a printer choice for the queue. | A native printer subsystem is still required. Separate document rendering from transports; own each spool job and its buffers; expose queue progress, pause/cancel, errors, page selection and printer choice. Verify jobs from multiple apps, out-of-memory admission, absent/offline printers, partial output and restart policy. Qualify each physical transport separately. |
| MP-APPEARANCE: 9–10, 13 | Configurable dialog color, backgrounds and idle screensavers; an input action returns from a screensaver to the app. Some supplied effects apply only to C64. | Add native themes, application background hooks and an idle/display service. Preserve both screens and focus, suppress idle takeover during unsuitable operations and consume wake input deliberately. Test idle entry/exit with each display mode and a dirty document. |
| MP-COMPAT: 2, 10–12 | Uses existing GEOS and desktop software; identifies per-app memory/drive/printer compatibility issues and retains a GEOS installation identity for applicable software. | Existing GEOS-format, VLIR, application and printer compatibility remains unqualified. Inventory legal fixtures and supported formats; run an app-by-app and file-by-file ledger. Record required patches and memory assumptions explicitly. Native Kestrel features and a matching filename do not establish binary compatibility. |

## Hardware cases from the manual

Pages 2–4 and 14–15 identify concrete families for the expansion ledger:
1541/1541-II, 1571, 1581; cached 1541 and DOS-format 1581 behavior; RAM 1541,
1571, 1581 and native disks; Commodore REU, GeoRAM-compatible memory,
RAMLink/DACC, SuperCPU/RAMCard; CMD FD2000/FD4000 and HD partitions;
SD2IEC image and native modes; and compatible emulated expansions. Page 8
also identifies 1351/SmartMouse and joystick input drivers. Page 2 describes
64NET as untested since 2002/2003; preserve that qualification when building
the comparison ledger.

These names define cases to investigate. Driver/API compatibility, emulator
success and physical certification are separate results. Record firmware,
ROMs, memory size, drive mode, bus address and cabling for each physical run.
The manual's broad device claims do not expand Kestrel's qualified hardware list.

## Implementation order

Finish the frozen shared-field qualification first. The next native work needs
module ownership and an execution/memory model that can grow beyond the
remaining 99 main-region and 327 low-region bytes. Build the event/focus and
list services on that foundation, then build the graphical desktop and
native settings/device inventory. Add suspend/resume and clipboard ownership
before concurrent document workflows, and establish spool/document interfaces
before the productivity suite and printing drivers.

Each row still needs a recorded comparison session. A manual review establishes
the behavior to test; implementation completion requires Kestrel workflow evidence
and any applicable physical qualification.
