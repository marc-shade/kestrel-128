# Wheels owner-manual comparison

Reviewed 2026-09-11: all 67 PDF pages of Maurice Randall's
[Wheels 64 / Wheels 128 Owner's Manual](https://commodore.bombjack.org/commodore/geos/Wheels%20_128_Owners%20Manual.pdf),
copyright 1998. The scan has 40,829,622 bytes and SHA-256
`a95df528e3cb43299108c7c6827c83442df017e5389e5512ddefa1e5a382f8e9`.
Its metadata dates from November 2011. Reading used a private OCR transcript,
with PDF pages 1–4, 25, 36, 46, 49, 59 and 67 also checked visually. OCR and scan
files are reading aids outside the repository. No release number is inferred
from the filename or scan date.

This completes the documentary review of this edition. Runtime comparisons,
later Wheels revisions, GEOS application manuals and file-format qualification
remain open. The separate [programming and installation review](WHEELS-PROGRAMMING-REFERENCE.md)
provides additional source material. The [completion roadmap](IMPLEMENTATION-ROADMAP.md)
still governs the whole OS.

## Page coverage

References below use printed section/page numbers. PDF pages 1–4 contain the
cover, credits and contents; page 67 is the back cover.

| Printed pages | PDF pages | Subject |
|---|---|---|
| 1-1–1-2 | 5–6 | Historical product information |
| 2-1–2-2 | 7–8 | Overview |
| 3-1–3-8 | 9–16 | Boot |
| 4-1–4-4 | 17–20 | System disks |
| 5-1–5-20 | 21–40 | Dashboard |
| 6-1–6-8 | 41–48 | Toolbox |
| 7-1–7-8 | 49–56 | Appearance and input |
| 8-1–8-4 | 57–60 | Application integration |
| A-1–A-6 | 61–66 | Recovery and shell |

## Kestrel acceptance work

These are Kestrel design and acceptance requirements, not implemented compatibility
claims. Each ID needs an implementation result and a recorded comparison
session. Existing native streams, fields, directory cursors and the picker
provide parts of this work; none of the rows is complete. The ABI 1.7 module
candidate adds original-source loading, while its physical qualification is
still in progress.

| ID / printed pages | Source topic | Required Kestrel result and evidence |
|---|---|---|
| WH-BOOT: 3-1–3-7 | Startup choices | Build a native boot inventory and settings UI. Boot with no working mouse, a missing preferred driver, changed drive addresses and unavailable expansion memory. Establish input before optional startup apps. |
| WH-INSTALL: 4-1–4-4 | System-disk creation | Create a bootable distribution from Kestrel. Verify required files, available space and selected source/target identity before writing. Exercise separate drives, one-drive swaps, read-only/full media and interrupted installation. Include the picker module and required recovery components in package validation. |
| WH-RECOVERY: 3-5–3-6, A-3–A-4 | Warm restart | Validate retained kernel/app data against its format, image identity and memory ownership before reuse. Recover from a stale cached executable, corrupt settings and a changed expansion device using an independently verified boot source. Preserve recoverable user data. |
| WH-DRIVES: 3-2, 6-1–6-3 | Device configuration | Provide stable logical devices and visible physical identities. Installing, removing or changing an address must preserve unrelated devices and active files. Test duplicate bus addresses, the internal 128D drive, missing devices and failed driver initialization. |
| WH-RAM: 6-4–6-7 | Expansion allocation | Implement named expansion ownership, RAM disks, retained reservations and a resource display. Show both total free storage and the largest usable extent. Exercise fragmentation, exhausted handles, detach/reinstall, changed geometry, reboot and aliasing without granting the same storage to two owners. |
| WH-WINDOW: 5-1–5-5 | Directory windows | Add movable/resizable windows, focus, stacking and scroll controls. Test overlaps, minimum dimensions, clipped labels, pointer capture and full repaint after moving or closing a window. Make the active window identifiable without color. |
| WH-SELECTION: 5-2–5-3, 5-18–5-20 | Selection and filtering | Add range/multiple selection, keyboard search and saved filters. Preserve selected file identity across sorting, viewport movement and refresh. Test invalid timestamps, duplicate display labels and directories exceeding 255 entries. Keep display sorting separate from a requested directory rewrite. |
| WH-SYSDIR: 5-6–5-8, 5-13–5-14 | Shared system directories | Add GEOS/Wheels directory metadata to the compatibility backend. Test extended chains, shared references, cycles, duplicate names and a missing parent. Bind operations to exact entries; renaming one entry must not select a different same-named file. Preserve original images during format investigation. |
| WH-FILES: 5-9–5-14 | File actions | Supply native copy/move/rename/delete, metadata and protection controls. Show exact source and destination, resolve collisions explicitly, and preserve the original until replacement is committed. Test multi-file cancellation, disk-full, failed close, raw names and reopened output bytes. |
| WH-SWAP: 5-14–5-15 | Single-drive copying | Retain separate source and destination media identities while using one drive. Reject a wrong disk, an unexpected image replacement or a changed partition. Resume only at a known boundary; verify complete output before reporting success. |
| WH-DISK: 5-9–5-10, 5-15–5-17 | Whole-disk operations | Implement geometry-aware image copy, format and validation with explicit target selection. Test allocation maps, native partitions, GEOS metadata and source extents that cannot fit. Distinguish copying used blocks from a complete physical image and verify each declared result independently. |
| WH-PARTITION: 5-5–5-8, 6-3, 8-3 | Native and 1581 modes | Add CMD and compatible native backends with explicit format/partition capabilities. Qualify the 1581 native mode separately from root-D81 support. Test unsupported partition layouts, mode changes and loss of the original app source during a data operation. |
| WH-RETURN: 5-17–5-18, 8-4, A-4 | Desktop return | Restore windows, selection, paths and focus after apps use other data locations. Load system resources from a retained, verified source identity. Exercise conflicting executable names, changed disks, damaged cached resources and repeated returns with documents retained. |
| WH-PICKER: 8-2–8-3 | Shared selectors | Extend the native picker to every implemented backend and both graphical displays. Keep text entry, navigation and action shortcuts unambiguous. Test first/last/page movement, long names, cancellation, field focus and caller-document retention with exhausted cache memory. |
| WH-INPUT: 3-4, 3-6–3-7, 7-4–7-6 | Pointer and repeat | Implement configurable drivers, both buttons, keyboard repeat and pointer timing. Provide a keyboard path to cancel an unusable preview. Measure jitter and input loss while IEC/UCI operations and redraws are active; qualify each physical input family. |
| WH-DISPLAY: 5-5, 7-1–7-4, 8-4 | C128 display modes | Deliver an interactive native desktop on either display with explicit 16/64 KiB VDC capabilities. Test monochrome focus cues, pointer restoration, color mapping and live mode changes. Qualify accelerated CPU regions with IRQ/ROM/IEC behavior and both monitors accounted for. |
| WH-DETAILS: 5-17–5-18, 7-1–7-8 | Preferences and artwork | Add theme, pattern, pointer and icon editors with preview, cancel and persistence. Save versioned settings separately from sealed executables. Test failed writes, damaged profiles and restart from another boot volume without silently loading conflicting preferences. |
| WH-IDLE: 7-4–7-5 | Screensaver | Implement idle entry and wake policy through the event service. Retain both screens, focus and dirty documents. Test mouse jitter, wake keys and active transfers; an input used to wake the display must not accidentally trigger a destructive action. |
| WH-TIME: 3-4–3-5, 5-12 | Clock sources | Provide clock selection and editing in native settings. Expose source availability and support manual/offline operation. Test invalid dates, rollover, source loss and persistence on each available RTC backend. |
| WH-PRINT: 5-8–5-9, 5-12 | Document printing | Add file associations, printer selection and owned spool jobs. Print a document from the desktop and from its app, with queue status and cancel. Verify complete stored or physical output and recover from absent printers, partial writes and insufficient spool memory. |
| WH-SHELL: A-4–A-6 | Shell integration | Build a shell on the same filesystem, driver and return services as the desktop. Script directory/partition changes, copy and app launch across supported backends. Avoid private driver replacement and retain explicit targets when multiple devices share a class. |
| WH-COMPAT: 2-1–2-2, 8-1–8-4 | Existing applications | Maintain an app/version/format ledger for original GEOS execution and document exchange. Test direct kernel patching and fixed expansion-memory assumptions in a controlled compatibility environment. A native Kestrel app with similar behavior does not establish original-binary compatibility. |
| WH-HELP: A-1–A-6 | Recovery guidance | Ship on-machine help, diagnostics, package inventory and recovery workflows. A user must be able to identify a failed component and restore the last verified system without requiring this development workstation. |

## Comparison boundaries

The manual's 255-file selector and 2,040-entry directory limits are different
contracts. Its RAM disk reservation and active drive slot are also distinct.
Do not collapse these into one Kestrel limit. It describes keyboard-button
exceptions during text entry and a shortened color display for the Detail Shop
on 16 KiB VDC systems; broad keyboard or color claims need those qualifications.

For each runtime comparison, record the Wheels build, boot/data images, memory
configuration, display mode, drive/partition identities and the exact action.
Retain failures and saved-file bytes as well as screenshots. Driver-specific
and later-release behavior stays unverified until that configuration is tested.
The office suite, background services, Ultimate controls and expansion families
in the main roadmap remain required beyond this manual review.

## Upgrade notice

Both pages of the [Wheels Upgrade Notice](https://commodore.bombjack.org/commodore/geos/Wheels_Upgrade_Notice.pdf)
were read and checked visually on 2026-09-11. The scan has 206,044 bytes and
SHA-256 `ce4b58a51684bcacb7fb908e28fb0b6b0e4c438a5667525f0fe33da5e6a350a0`.
Neither a release number nor a publication date is printed.

PDF page 1 describes conflicts from mixed system versions and loading Dashboard
modules from a different source. Page 2 couples installation of fonts and
keyboard layouts; early prompts still use the USA layout before German support
is installed, and the write-protected practice procedure needs that distinction.

Extend WH-INSTALL, WH-RECOVERY and WH-RETURN acceptance to coherent package
activation, an independently usable fallback and source-bound resources. The
ABI 1.7 parent CRC and retained source folder address part of this; transactional
installation and volume identity remain open.

WH-INPUT and WH-DETAILS also need paired font/keymap versions, a visible early
boot layout and locale configuration outside sealed executables. Test canceled,
read-only and interrupted changes, stale cached components, and mismatched
resources on both displays. This notice is not a version-specific changelog;
the later-release audit remains open.
