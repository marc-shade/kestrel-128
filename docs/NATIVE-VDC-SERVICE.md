# Shared native VDC service

Desktop, Calculator, Ultimate, Paint, Files, Editor, Claude and Sheet load the same `VDSVC.PRG` from their original app
source. It supplies both the native 640×200 desktop layout and the incremental
VIC-to-VDC presenter used by Calculator, Ultimate, Paint, Files, Editor, Claude and Sheet, including their file
pickers. The blue interface, app icons, focus colors and pointer behavior
remain consistent. All seven apps can save their original
VDC screen in an available REU, with main RAM as the fallback.

The component is included on both D64/D81 suite and workspace disks. When
copying any of these apps to another IEC disk or Ultimate directory, copy
`VDSVC.PRG` beside it. A data-device selection or file-dialog path does not
redirect component loading. Ultimate paths retain the original directory,
including spaces and case, in either source context. A missing, damaged or
unavailable component leaves the VIC controls and VDC text fallback usable.

## Memory and lifetime

[`vdc-service.asm`](../src/native/vdc-service.asm) is a 9,906-byte NBK1
component, reserved in 39 bank-1 pages at `$6000..$86ff`. The retained
[`vdc-client.inc`](../src/native/graphics/vdc-client.inc) uses the
[checked banked loader and executor](NATIVE-BANKED.md). It closes the component
stream before executing any provider code. The resident kernel and 426-page
managed heap are unchanged.

| Allocation while graphics are open | Desktop | Calculator | Ultimate | Paint | Files | Editor | Claude |
|---|---:|---:|---:|---:|---:|---:|---:|
| Bank-0 app | 35 pages | 49 pages | 91 pages | 96 pages | 96 pages | 96 pages | 96 pages |
| Bank-1 component | 39 pages | 39 pages | 39 pages | 39 pages | 39 pages | 39 pages | 39 pages |
| VIC surface | 36 pages | 36 pages | 36 pages | 36 pages | 36 pages | 36 pages | 36 pages |
| History | 0 | 2 pages | 0 | 0 | 0 | Variable, up to 16 records | 0 |
| Picture and undo | 0 | 0 | 0 | 72 pages | 0 | 0 | 0 |
| Retained scratch | 0 | 0 | 11 pages | 10 pages | 16 pages | 16 pages | 48 pages |
| IEC browser cache | 0 | 0 | 0 | 0 | 37 pages | 0 | 0 |
| Free main-RAM pages with REU backing | 316 | 300 | 249 | 173 | 202 | 239 | 207 |
| Free main-RAM pages with 16 KiB VDC RAM backing | 252 | 236 | 185 | 109 | 138 | 175 | 143 |
| Free main-RAM pages with 64 KiB VDC RAM backing | 244 | 228 | 177 | 101 | 130 | 167 | 135 |

Moving the display code saved eight pages in Desktop and Calculator's executable allocations.
The separate component occupies 39 pages while loaded. Its shared memory
operations and [span history](NATIVE-HISTORY.md) add nine pages to the earlier
display-only component. The table assumes no clipboard payload, Editor history or RAM document. Claude
retains its original font, live font and terminal cells in the 48 scratch pages. Editor
documents use REU extents when available; its free main-RAM count then stays
constant as a document grows. RAM documents still consume separate 4 KiB chunks.

Ultimate keeps one component and saved VDC screen while its picker borrows the
same VIC surface. Its picker allocates four scratch pages only while open and
releases them after closing its cursors and cache. No provider reload or VDC
restoration occurs between the panel, picker and confirmation dialog.

Paint likewise retains the provider and snapshot through drawing, file dialogs
and the picker. Its ten scratch pages live outside the executable window;
editable field buffers remain inside the app's loader allocation. A display
fault pauses edits and file actions until Escape restores the screen, while
the picture and undo remain owned. R retries graphics after fallback.
The client accepts an optional `BP_POINTER_STATE` byte (default `pm_seen`);
Paint supplies actual cursor visibility so its keyboard brush is shown too.

Files retains the same provider and screen backup while its checked graphics
and picker modules alternate in bank 0. Sixteen owned scratch pages outside
the executable window make room for its retained VDC client. Optional
`BP_POINTER_X`/`BP_POINTER_Y` symbols default to `pm_x`/`pm_y`; Files supplies
coordinates copied from whichever module currently owns the pointer. A failed
display pauses copy/verification at its current chunk without releasing streams
or changing launch identity. Escape restores before cancellation or app handoff.

Editor likewise retains the provider, snapshot and surface through its checked
picker/graphics module swaps. Its document memory lease keeps the shared arena
and provider alive after a screen restore. The display can reopen against that
same arena. Documents and snapshots have distinct REU owners; each releases its
own storage before the final component unload. See the
[shared memory contract](NATIVE-SHARED-MEMORY.md).

Input, application logic and the VIC surface stay in bank 0. Calls clear
`N_READY` before preparing the mailbox or changing banks. The normal app input
loop publishes readiness again. The checked executor temporarily exposes
16 KiB of bottom common RAM; native callbacks restore the kernel's standard
mapping for the duration of the service. The REU probe buffer is in physical
bank 1; DMA transfers through `N_BUFFER` use physical bank 0.

Close restores all owned VDC memory and registers before releasing its snapshot.
The arena and executable remain loaded while a document memory lease is active.
Editor also retains the component for RAM undo records until controlled exit
or reclamation under document-memory pressure.
Display and REU recovery failures retain
the component and block app handoff until restoration succeeds. A clean VDC
setup refusal releases the component when no memory or history client needs it. An uncertain source
close retains the native file record and executable; repeated exits do not
retry I/O through a poisoned stream or discard its owner.

## Internal call contract

This is the suite's internal component interface under native ABI 1.12. Calls
use `bk_call` with A equal to an operation and return the native A/carry result.
The display parent retrieves status after each completed display operation. A checked-executor
failure leaves a conservative recovery phase until cleanup can be verified.

| Operation | Meaning |
|---|---|
| 0 | Check empty state; refuses an owned display, REU recovery or history allocation |
| 1 | Open and initially present; binds mode and surface once |
| 2 | Present changed mirror rows or the desktop selection/error |
| 3 | Update the clipped pointer |
| 4 | Restore and close, retaining recovery on failure |
| 5 | Copy the 41-byte status record into `N_BUFFER` |
| 6–14 | Shared memory version/lease/allocation/transfer/resize operations; use the transient heap mailbox, preserving the 512-byte payload |
| 15–26 | Versioned span-history preparation, transfer, replay and cleanup; see [history](NATIVE-HISTORY.md) |

Operations 1–3 consume this packet in bank-0 `N_BUFFER`:

| Offset | Bytes | Value |
|---|---:|---|---:|
| 0 | 1 | Mode: 0 incremental VIC mirror, 1 native Desktop scene |
| 1 | 4 | Owned VIC surface handle; bound by operation 1 |
| 5 | 1 | Desktop selection, 0–5 |
| 6 | 1 | Desktop launch error, zero for no error |
| 7 | 1 | Pointer visibility in bit 0 |
| 8 | 2 | Little-endian shared pointer X, 0–319 |
| 10 | 1 | Pointer Y, 0–199 |
| 11 | 25 | Mirror dirty-row flags; consumed only in mode 0 |

The surface and mode remain bound until close. Mirror presentation clears the
parent's dirty flags only after success, including the initial full upload.
Desktop error glyphs are read from the owned VIC status row, preserving the
native VDC layout without storing a second font in the component.

Status offsets 0–6 are phase/live/color/fault/saved-stack/base-high/pages;
7–10 hold the snapshot handle; 11–24 hold fourteen saved VDC registers;
25–28 hold pointer visibility/X/Y; 29 selects REU backing; 30–37 hold its token;
38–39 report REU active/probe-recovery state; 40 reports pending mirror rows.
These values are observations of the retained component, not authority to
release its storage independently.

## Checks

`ci_native_vdc_service.py` runs the actual provider through the checked loader
and banked executor, comparing complete bitmaps, attributes, status glyphs,
pointer clipping and exact VDC/REU restoration. `ci_native_vdc_client.py` checks
app-source loading, absent/corrupt components, allocation refusal and uncertain
source-close ownership. Existing Desktop, Calculator and REU workflows exercise
the loaded apps and recovery paths.

The VICE pointer workflow reads the component only after checking its live
heap token, page owners and patched NBK1 header. It compares original screen
backups with complete VRAM at the bank-1 restore checkpoint before handoff.
The breakpoint condition checks the MMU configuration so an identical bank-0
program address cannot satisfy the observation. Cold-boot and disk-chain
checks cover all six generated images. These are software checks; this
component has not been deployed to or qualified on physical hardware.

Paint's [graphical VDC qualification](validation/2026-09-13-native-paint-vdc/README.md)
adds complete picture and picker canvases, keyboard-brush visibility, panning,
connected strokes, owned scratch, both backing stores and failure recovery.
That checkpoint retained the shared provider's executable bytes. The document
memory extension changes the provider; the other app programs retain their
previous executable bytes.
