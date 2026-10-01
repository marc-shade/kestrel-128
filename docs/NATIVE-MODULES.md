# Native application modules (ABI 1.7)

The current source loads the editor's picker from `EDPICK.PRG` and its search
engine from `EDFIND.PRG` on the app's original disk or Ultimate folder. The
[graphical suite Editor](NATIVE-EDITOR-GUI.md) combines search and graphics in
`EDFIND.PRG`, with keyboard/document state retained in its 96-page core and
module allocation. The diagnostic editor retains the 79-page text build.
The editor core, document descriptors,
field and cursor remain live. Tab in the diagnostic editor
or F7/Browse in the suite editor loads the picker; subsequent calls reuse its verified image and
directory state until search or the suite graphical view replaces that module. Ctrl-F/Ctrl-N/Ctrl-R load
search into the same window. The accepted query and case choice remain in the
core across module switches. Missing or damaged modules keep the document.
Install **EDPICK.PRG**, **EDFIND.PRG** and the graphical Editor’s
**EDCLIP.PRG** beside the editor on USB; both suite
disks contain the core and matching modules from the same build.

The earlier picker-only checkpoint passed all 22 CPU suites, ten emulator workflows and complete physical USB/IEC
workflows pass on the [frozen checkpoint images](validation/2026-09-11-native-modules/README.md),
including module loading, warm reuse, document retention and independent file
readback. The first USB attempt stopped on a directory-rescan I/O failure
after a missing app launch, before reaching the editor; its initiating fault
remains unresolved. The original desktop was restored and all observations
retained in the checkpoint archive. The successful USB retry used identical
native images; it does not establish the first attempt's initiating cause.

The [search checkpoint](validation/2026-09-12-native-editor-search/README.md)
qualifies the two-module editor in CPU models and VICE. Module switches refuse
to discard a picker that retains a cursor or cache handle after failed cleanup;
an explicit picker retry can release those resources. This build has no new
physical-hardware qualification.

The [Sheet app](NATIVE-SHEET.md) also uses this service. Its `$ae00..$bfff`
window alternates between `SHCALC.PRG`, `SHFONT.PRG` and `SHCLIP.PRG`.
Source cells, calculated values, history, display ownership and the C stack
stay outside the window. Its cc65 linker places calculation code in a separate
output segment while keeping library routines and persistent data in the core.
The builder checks the runtime extent against the window and binds all three
modules to the final packed core. This software-only qualification is separate
from the historical physical Editor checkpoints below.

## App and module manifests

An app requiring minor 7 may use NAPP bytes 7 and 11 as the low and high byte
of a module-window offset from `$6000`. Zero/zero retains the older contract.
A nonzero offset must be at or beyond the loaded core extent and strictly
inside the declared allocation. The window ends at allocation end. It need
not begin on a page boundary. App entry remains within the core file, and
initial app allocation still clears all declared pages.

A module is a PRG at that exact window address followed by this manifest.
Offsets exclude the two-byte PRG address.

| Offset | Bytes | Meaning |
|---|---|---|
| 0 | 4 | `NMOD` bytes `4e 4d 4f 44` |
| 4 | 1 | Module format 1 |
| 5 | 1 | ABI major 1 |
| 6 | 1 | Required module ABI minor 7..14; presentation calls require 8; desktop selection requires 9; shared keyboard input requires 10 |
| 7 | 1 | Reserved, zero |
| 8 | 2 | Complete module extent including this manifest |
| 10 | 2 | Sealed parent core's CRC16 |
| 12 | 2 | Entry offset from the module origin, at least 16 and below extent |
| 14 | 2 | Module CRC16, with these two bytes treated as zero |

Words are little-endian. CRC uses the app format's CCITT polynomial `$1021`,
initial `$ffff`, no final XOR. The module must have at least one body byte,
fit the window and end at checked EOF. Parent CRC detects mismatched builds;
it is not a cryptographic signature or a security boundary against arbitrary
6502 code. Apps and modules must respect kernel-private RAM and the native ABI.

`build-native.py` assembles the editor's linked layout, splits it at the
declared window, seals the core, binds and seals each module, and packages all
three files. The search payload is assembled at the same logical window as the
picker and emitted after it for the builder to split. `native_module.py`
validates the same contract on the host. Module code
uses fixed addresses for this parent build. Relocation, multiple exported
entries and a general shared-library linker remain additional work.

The standalone [SDK example](../examples/native-module/README.md) builds a
four-page parent and a small counter module without rebuilding system images.
It demonstrates all three lifecycle calls, both consoles, token retention,
module A/carry results and explicit retry. Its 15 CPU workflows are separate
from the frozen system's 22-suite qualification run; they make no additional
emulator or hardware claim.

## Lifecycle and calls

| Entry | Address | Arguments and result |
|---|---|---|
| `N_MLOAD` | `$1c5f` | `N_FNAME`/`N_FNAMELEN`: 1–16 printable basename bytes, using the IEC filename filter. Success publishes a nonzero 24-bit `N_MTOKEN`. |
| `N_MCALL` | `$1c62` | `N_MTOKEN`: the token returned by the desired load. Returns the module's A/carry; `N_MERROR=0` distinguishes this from a gate error. |
| `N_MCLOSE` | `$1c65` | Invalidates the module and closes/checks only its retained loader source, if any. |

`N_MTOKEN` occupies `$3d17..$3d19`; `N_MERROR` is `$3d1a`. Read-only
`N_MSTATE` at `$3d1b` is 0 empty, 1 loading, 2 ready, 3 executing, or 4 source
CLOSE retained. The independent module manifest is private `$3d50..$3d5f`.
The validated app manifest and original allocation handle remain separate.

All three calls require a running owner-32 app, enabled IRQs, native MMU
configuration and a return address from `$6020` up to, but not including, the
module window. That retained parent area includes any initialized gap between
the loaded core's end and the window; module loading does not overwrite it.
The original allocation's owner, bank, base, page count, complete generation
and every page tag are checked. CALL also bounds the saved entry and extent.
Load/call/close cannot nest or replace a currently executing module. Module
callbacks may use ordinary field, heap and file services. D/I are preserved;
module entry receives A=0 with decimal clear. X/Y and other flags are scratch.
Normal module return restores native MMU configuration. EXIT, REPLACE and
WORKSPACE retain the app loader's original stack cleanup path.

Load uses the app's original source device/context and format. For Ultimate,
the kernel retains the parent directory at `$3f00..$3fff` before source OPEN,
then appends the requested basename, rejecting lengths beyond 255. Document
operations and browser changes do not redirect module lookup. File/heap
argument mailboxes and the shared transfer buffer are scratch. Loader I/O
diagnostics use `N_DOSCODE`/`N_IOSTATUS`; `N_APPERROR` remains separate.

After argument checks, each load invalidates the old token and advances a
boot-wide 24-bit generation. No entry is published until header, extent,
EOF, CRC and source CLOSE all succeed. A failed load may leave partial bytes
in the window; its token stays invalid. Bytes outside the declared module
extent are not initialized by module loading. Generation never wraps: after
`$ffffff`, another load returns `$16` until a fresh kernel boot. An already
loaded final-generation module remains callable until invalidated.

Modules share the app owner; they must release their own scratch resources
before replacement. The loader closes only its own source handle and never
releases the caller's document, other stream or heap allocations. It borrows
the idle app loader's buffered-read/CRC scratch, while preserving the original
app allocation handle, manifest, entry and exit stack.

## Failed CLOSE and remaining recovery work

A source CLOSE failure leaves state 4, keeps the source descriptor and
prevents another load. CLOSE is attempted once within that load. Explicit
`N_MCLOSE` uses the existing backend recovery contract. Ultimate can retry
its owned CLOSE and accept checked success/no-file-open. The IEC file service
retains an uncertain CLOSE without replaying serial operations, including
on explicit retry. Full IEC recovery remains required; clearing a local file
table alone would not prove the drive released its channel.

The editor's next Tab explicitly checks retained loader cleanup before trying
to load again. Ordinary missing-file, short-file and checksum failures permit
a new load after their source has closed. An uncertain IEC close keeps the
existing owner quarantine; it must not be described as recovered.

## Memory and acceptance

The diagnostic text editor remains 79 pages (`$6000..$aeff`). Its core and the larger picker
module share that allocation; the smaller search module uses the same window.
The 66,056-byte document,
both 8 KiB workspaces and ten picker-cache pages use 425 of 426 heap
pages. Module services occupy existing resident holes; no heap page is newly
reserved. Low-section staging grows to nine pages, reclaimed after boot.
`target/native/layout.json` reports the module, source-path and staging bounds.

The existing observer borrows `$3e00..$3fff` only at idle, preserves all 512
bytes and restores the saved source directory along with the browser name.
That range cannot itself be a CPU-capture source. Module observations instead
check the core header, module header, lifecycle, saved token and source fields.

CPU acceptance includes IEC/DOS sources, both Ultimate contexts, cold and warm
picker use, missing/damaged/mismatched files, exact window boundaries, stale
and exhausted tokens, changed allocations, caller/entry bounds, nested calls,
retained CLOSE behavior and original-stack EXIT. The editor checks preserve
both displays, fields, documents and workspaces through retry, cancellation
and byte-verified Save As. The completed emulator and physical runs repeat
the source/lifecycle and document checks on frozen images. Physical cold picker
times are 9.308 seconds over USB and 42.363 seconds over IEC, including module loading and the
initial directory scan; they are not isolated loader throughput measurements.

This window is groundwork for additional native services. Background tasks,
app suspension, GUI windows/events/focus, REU caching and allocation, general
overlay replacement cleanup, and the rest of the
[completion roadmap](IMPLEMENTATION-ROADMAP.md) remain open.

The graphical Editor now uses a third checked module, `EDCLIP.PRG`, for
[shared clipboard transfers](NATIVE-CLIPBOARD.md). It shares the existing
module window and keeps document/selection state in the core. The diagnostic
Editor retains its picker/search pair.
