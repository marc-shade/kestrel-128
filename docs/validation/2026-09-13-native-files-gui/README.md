# Native blue Files app

Files now carries the desktop's blue bitmap, yellow focus and shared 1351
pointer into directory lists, byte viewing, editable device/path fields and
verified copy. The Files icon returns to the same blue desktop when the app
closes. Tab moves focus and Enter activates a control. Browse/F7 opens the
shared destination picker and returns to the graphical copy dialog with the
source and destination preserved. The picker remains a text interface.

This local software checkpoint is based on
`b19671d592d8130fa93494c22dd714d68376b543`. No physical hardware I/O or push was
performed. The installed machine, physical native qualification and the full
OS roadmap remain unchanged by this checkpoint.

## Implementation and memory

Files keeps browser/copy state, raw paths, transfer buffers, descriptors and
keyboard ownership in its core. Checked graphics and picker modules alternate
in one window and load from the original app's device, format and folder.
Failed picker aborts and uncertain module-source closes retain ownership and
block further file operations until explicit cleanup succeeds. A missing or
invalid graphics module, or an occupied surface range, leaves text controls
available; Refresh retries the graphical view.

The core contains 14,272 bytes and declares 93 bank-0 app pages. Its module
window starts at `$97c0`: `fspick.prg` contains 7,737 bytes and `fsview.prg`
contains 9,464 bytes. Both modules bind to the core's checksum. The peak core
plus graphics footprint is 23,736 bytes, within the 93-page allocation. The
bitmap uses a separate 36 pages at `$c000..$e3ff`; the IEC list cache uses 37
bank-1 pages, with other caches allocated as needed. The app requires ABI 1.10
and ships with ABI 1.11. Kernel bytes and the 426-page heap are unchanged.

Field edits repaint changed glyphs and the old/new caret. Explicit mouse or
Tab focus clears any pending row-follow request. Pointer polling avoids
completed samples and clears readiness before entering the checked module
gate, including idle mouse calls. Copy and reopened comparison both sample
mouse Cancel between chunks. Keyboard, display and pointer state are restored
before replacement or exit.

## Qualification

- Ten unchanged binary regression suites pass: browser, Ultimate browser,
  file dialog, modules, heap, apps, display, keyboard, pointer and suite
  oracles. Their original 26-job batch is retained in `core-cpu.tar.gz`;
  earlier Files runs in that batch are development evidence. Final Files
  qualification uses the separate current-image batch below.
- Sixteen final application runs pass all 40 groups: 14 graphical groups
  plus 26 existing IEC/Ultimate copy and fault groups. They cover keyboard
  and modeled mouse input, long names/caret placement, module replacement,
  missing/corrupt modules, retained close failures and recovery, original
  Ultimate app-source routing after data-device changes, foreign bitmap
  ownership, and mouse cancellation during copying and verification. Every
  observed graphical module call starts with readiness cleared.
- Full mouse workflows pass with both 40- and 80-column boot defaults across
  Calculator, Editor, Files, Ultimate, Claude and Paint. The complete
  keyboard-only suite also passes. The offline auditor checks all 126
  complete 320x200 palette frames (8,064,000 pixels), including 19 Files and
  24 Paint frames, plus the matching bitmap surfaces and VDC text controls.
  Mouse tests reopen and compare calculator history, a raw PRG copy and a
  Paint document. Every shipped disk file remains byte-identical.
- A separate 1581 workflow copies a 66,058-byte SEQ and a raw 12-byte PRG
  between private D81s. Reopened comparison and independent exports match;
  an independent offline sector-chain reader verifies the destination
  bytes again. Empty IEC output is refused before creation. Source media
  and the system D64 remain byte-identical, and all 426 pages are free after
  workspace cleanup.
- The shared desktop/Ultimate/Claude workflow passes two actual TCP/PTY
  lifetimes, including acknowledged F8 and host exit. Shutdown is observed
  before `native_video_end`, while Claude still owns its allocation. Fonts,
  NMI state and the native gate match their original bytes afterward; both
  host processes exit normally. Files' complete graphical browser is also
  checked in this workflow.
- All qualifying host processes reach terminal exit zero. The raw audit
  accepts 1,216 captures, 4,086 chunks, 1,912,806 payload bytes and 4,864
  matching borrower pairs. No rejected observation supplies passing evidence.

The input archive contains 480 files. Independent frozen and main rebuilds
reproduce all 24 native PRG/D64 images exactly. Relative to the baseline,
only the Files core and the two suite D64s change; the graphics and picker
modules are added. Both kernels and every other app PRG are byte-identical.
The auditor checks archive manifests, module binding, complete disk contents,
raw captures, input restoration, resident code and live serial shutdown.

## Retained development failures and limits

`preliminary.tar.gz` retains earlier build/test logs and raw VICE runs,
including failed captures and nonzero exits. These exposed module readiness,
pointer polling/settling, clipping, focus restoration and recovery issues.
An initial ready observation changed module-gate scratch during idle polling;
readiness is now cleared before every call. Early polling entered the checked
gate too often and duplicated the raster delay; sampling now waits after the
gate and skips completed samples.

The mouse workflow also exposed an ignored Home key leaving a pending row
follow that overrode later mouse focus. The final focus setter clears that
request even if the focused control is unchanged. Host diagnostics separately
now read physical bank-0 app RAM, and only inspect GUI state while its module
is present, since the same window can contain the picker. The final full
mouse runs retain the exact host runner used by the frozen source.

Long-path fixtures were corrected to exercise 255-byte total Ultimate paths
with supported created components of at most 127 bytes. Successful picker
recovery clears an earlier close/picker error while preserving unrelated copy
results. Older runs, including a process terminated after printing a local
pass, are retained without being counted as final qualification.

The shared picker and VDC remain text interfaces. Graphical editor/terminal
framing, rename/delete, sorting, multi-selection, directory copy, media identity,
interrupted-copy recovery, REL/VLIR, zero-byte IEC creation and the broader
roadmap remain open. Physical native testing additionally needs the qualified
bank-aware high-RAM diagnostic and a transport-specific live Claude shutdown
observer. Historical sealed records are unchanged.

## Recheck

Run `python3 -B verify.py` here for the offline archive, frame and lifecycle
audit. `SHA256SUMS` seals every other file in this directory. `rebuild.py`
records the separate build comparisons and refuses to write a sealed record.
The screenshots show the tested desktop and Files copy dialog; the binary
surfaces and complete palette readbacks supply the pixel checks.
