# Native C128 kernel and banked memory

The separate `target/native/kestrel.d64` or `.d81` boots through the C128 KERNAL into
BASIC 7 and enters the native kernel. It never enters C64 mode. The native
image provides a memory workspace, application-facing allocator and a
[disk-loaded native calculator](NATIVE-APPS.md) with verified history export
through [owned IEC and Ultimate files](NATIVE-FILES.md), plus a
[file/app browser and byte viewer](NATIVE-BROWSER.md) and
[banked text editor](NATIVE-EDITOR.md) with [native Ultimate files](NATIVE-ULTIMATE.md).
The [native graphical desktop](NATIVE-GRAPHICS.md) is built separately as
`target/native-desktop/kestrel.d64` and `.d81`. It adds owned VIC and VDC
graphical launchers, clipped drawing and keyboard/1351 app selection. Remaining desktop
services and the rest of the application suite remain open.
ABI 1.10 adds the read-only [Ultimate panel](NATIVE-ULTIMATE-CONTROLS.md)
and the native [Claude terminal](../apps/claude/README.md) to the desktop disks.

The current source includes the [owned-abort completion follow-up](validation/2026-09-11-native-owned-abort/README.md).
Its 24 CPU suites, clean build and ten emulator workflows pass. The first
physical USB attempt failed during a saved-file reopen through DOS context 2.
The full unmodified retry passes, including all closed-file readbacks and
restoration/cleanup. Physical IEC qualification and the combined audits also
pass, including independent readback of all four document-disk files. The
initiating USB fault remains unexplained. The signed
[module checkpoint](validation/2026-09-11-native-modules/README.md) is the
preceding qualified kernel. That follow-up preserves its ABI and heap size.
The current source provides ABI 1.8 presentation services while keeping all 426
heap pages and existing public entry addresses. Its exact software inputs and
checks are retained in the [integration record](validation/2026-09-12-native-desktop-integration/README.md);
physical desktop qualification has a separate [hardware record](validation/2026-09-11-native-desktop-hardware/README.md).
ABI 1.9 adds `N_DESKTOPSEL` at `$3d2f`, retaining the desktop selection across
app/workspace returns and clearing it on native restart. The resident intervals,
public entry addresses and 426-page heap are unchanged.
The [complete physical ABI 1.9 workflow](validation/2026-09-12-native-desktop-abi19-hardware/README.md)
now passes all three app handoffs and returns, full CPU-captured display RAM,
resident-code audits and verified restoration/cleanup. Physical video pixels
and additional machine/ROM combinations remain separate qualification gates.

ABI 1.10 adds `N_UQUERY` at `$1c6e`, using 147 bytes of existing service
padding at `$4b00`, and the eight-byte `N_NMIGATE` at `$1bf0`. Resident
reservations and all 426 managed pages remain unchanged. The NMI bridge maps
bank-0 application RAM before dispatching through `N_NMIPTR` at `$3d3e`.
A foreground serial borrower owns installation and teardown: disable and
acknowledge the source, save/restore the old vector and pointer, and remove
its callback before exit. Callbacks cannot invoke foreground APIs and unwind
through ROM `$ff33`. The Claude client follows this contract and saves its
cc65 zero page, software stack and VDC font within its app allocation.

ABI 1.12 adds `N_BOOTFORMAT` at `$3de4`. Startup sets it from the disk build
profile (0 D64, 1 D71, 2 D81) and initializes browser/application formats to
match. System shortcuts and launcher handoffs use this saved format with
`N_BOOTDEVICE`; data-disk preferences stay independent. Apps must treat these
two session fields as read-only. See [boot media](NATIVE-BOOT-MEDIA.md).

ABI 1.13 initializes the [shared clipboard](NATIVE-CLIPBOARD.md) session at
`$3de5..$3dff`. Its library manages owner-31 allocations across foreground app
exits. No resident entry was added, and all 426 heap pages remain managed.

ABI 1.15 adds `N_RCACHE` at `$3d9f`: the number of 4 KiB REU pages the
[module cache](NATIVE-MODULES.md#reu-module-cache) reserves at the top of an
REU of 512 KiB or more (16), or zero. App REU arenas stop below them. No
resident entry was added; the heap is unchanged.

Use the native CPU observer when a hardware test needs bytes from a specific
RAM bank. Direct cartridge DMA can return BASIC ROM at an application RAM
address; the [editor checkpoint](validation/2026-09-09-native-editor/README.md)
records a complete ROM snapshot and the corresponding correct CPU observation.

## Build and use

```sh
python3 build-native.py
x128 -default -8 target/native/kestrel.d64 -drive8true -drive8type 1541
```

The build requires Python 3, 64tass, VICE's c1541 and a host C compiler (`cc`,
or `CC`) for the bundled boot compressor. It creates the native
kernel, boot-sector, three app PRGs, two Editor modules, D64/D81 disks and
image hash manifest in `target/native/`. The D81 kernel and its symbols/layout
are in `target/native/d81/`; app PRGs are shared between both formats.
`layout.json` records resident, metadata and boot-staging bounds; `kestrel.sym`
exports the assembled runtime addresses. The kernel PRG remains loaded at `$1c01`.
Track 1/sector 0 is reserved in the BAM before adding file `U`; ordinary file
allocation therefore cannot consume the boot block. The boot sector feeds
`RUN"U"` to native BASIC, which enters the kernel through its SYS stub.

On a C128, mount this disk on drive 8 and reset into native mode, or use the
native BASIC `BOOT` command. The Ultimate `runners:run_prg` endpoint enters
C64 mode, so native deployment uses disk mount and machine reset. This workspace needs neither a mouse nor an REU.

Both screens show the same workspace. Press **1/2** to choose RAM bank 0/1,
**A** to allocate 8 KiB in that bank, **W** to initialize the complete block
with a bank-specific pattern, **V** to compare every byte and **F** to release
it. Both allocations may remain live together. Free-page and handle counts
are hexadecimal. A result of `00` means success, `04` means no valid selected
handle and `0A` means the workspace found different data. The remaining error
codes are listed below. On the suite workspace disk, **B** opens the blue
native desktop. The standalone diagnostic disk provides the text browser.
Press **C** to launch the native calculator and **Esc** there to return while
retaining the workspace's allocations. Its app lifecycle and additional ABI
entries are documented in the [native app guide](NATIVE-APPS.md).
Press **B** for Files and Apps. It discovers native applications on the selected
IEC disk and returns to the browser after each application exits. **Esc** in
the file list returns to the workspace with its allocations preserved.
**L** in the browser launches a native app from an absolute Ultimate path.
Select **EDITOR** for the [banked text editor](NATIVE-EDITOR.md), including
cursor editing beyond a 64 KiB offset and verified Save As to a new SEQ file.

## Memory and execution contract

This ABI runs bank-0 code with MMU configuration `$0e`: RAM below `$c000`,
system editor/KERNAL ROM above it and I/O visible. The standard bottom 1 KiB
common area, bank-0 zero page and bank-0 stack remain in place. Initialization
preserves the native SYS stack frame. The kernel takes over application RAM;
returning to the suspended BASIC program is not supported.

| Region | Purpose |
|---|---|
| Bank 0 `$0000..$0bff` | Native system workspace, vectors, screen and boot area |
| Bank 0 `$0c00..$0fff` | System section: resident kernel code (the memory workspace) in the KERNAL's RS-232 buffers and BASIC's sprite area |
| Bank 0 `$1000..$12ff` | Function-key definitions and BASIC variables |
| Bank 0 `$1300..$1bff` | Resident low kernel and growth space; never application scratch |
| Bank 0 `$1c01..$37ff` | Native kernel, workspace and reserved growth space |
| Bank 0 `$3800..$39ff` | Two page-ownership tables |
| Bank 0 `$3a00..$3bff` | Shared 512-byte transfer buffer |
| Bank 0 `$3c00..$3cff` | 32 eight-byte allocation records |
| Bank 0 `$3d00..$3fff` | API mailbox and reserved system space |
| Bank 0 `$4000..$4fff` | Resident Ultimate file service, buffers and path/status mailboxes |
| Bank 0 `$5000..$feff` | 175 managed pages, 44,800 bytes |
| Bank 1 `$0000..$03ff` | Common-area alias; excluded from allocation |
| Bank 1 `$0400..$feff` | 251 managed pages, 64,256 bytes |
| Both banks `$ff00..$ffff` | MMU register window and native interrupt stubs/vectors; excluded |

The two pools provide **426 pages / 109,056 bytes (106.5 KiB)** from stock
128 KiB RAM. Allocation is contiguous within one bank. Automatic placement
tries bank 1 first, preserving bank-0 executable space. Fixed graphics or DMA
regions must be reserved before general allocations can use them. There is no
REU allocation, size probe, RAM disk or expansion-memory support in this ABI yet.
Until 2026-10-02 the resident regions had 15 free bytes in total. Since
2026-10-03 the text-mode memory workspace runs from the **system section** at
`$0c00..$0fff` and the code that runs only at cold boot runs from the boot
staging pages, so the heap keeps all 426 pages and the resident kernel has
room again: the workspace kernel's main section ended at `$3413` (1,005 bytes
free before the page tables; the direct-desktop variant 1,001). The REU
module cache (ABI 1.15) then took 753 of them, so main now ends at `$3704`
(252 free; direct-desktop 248). The low
section has 50 free bytes before the NMI bridge, the service region has 49
free bytes below `$4bfc` plus seven before `$5000`, and the system section
uses 860 of its 1,024 bytes.

The system section is C128 RAM that only two things use: the KERNAL's RS-232
input and output buffers at `$0c00..$0dff`, which exist while an RS-232
device (device 2) is open, and BASIC's sprite definition area at
`$0e00..$0fff`. The native system opens no RS-232 device (serial apps drive
the SwiftLink ACIA directly) and its pointer sprites live in each app's
surface. Startup copies the section from staging; the running-layout audit
compares it with the image like the other resident regions. Apps must not
open device 2 or place sprite data there. BASIC's run-time stack at
`$0800..$09ff` is unused by the native system too and is the next region for
resident growth. `$0b00..$0bff` (boot sector and cassette buffer) is left to
the boot and to test harnesses, and `$1100..$12ff` stays BASIC's: the
KERNAL's IRQ calls BASIC's sprite and sound handler, which reads tables
there. The graphical library remains app/module code.
Public entries and the app load address remain stable. ABI 1.6 adds
[shared focused field editing and drawing](NATIVE-FIELDS.md); the calculator
and browser require minor 6. The editor now requires the
[ABI 1.7 module service](NATIVE-MODULES.md), whose 22 CPU suites, ten emulator
workflows and complete physical USB/IEC workflows pass in the
[module checkpoint](validation/2026-09-11-native-modules/README.md).
The boot PRG retains its preceding bytes.
The signed [field checkpoint](validation/2026-09-10-native-fields/README.md)
passes twenty CPU suites, ten emulator workflows and complete physical USB/IEC
qualification, including independent saved-file verification.
Further module services and scheduling remain necessary for the complete native OS.

The 16,747-byte kernel PRG ends with three boot staging parts from `$5000`:
a nine-page low-section copy at `$5000..$58ff`, the boot-only code at `$5900`
(startup, relocation, keyboard ownership, page-table setup and the system
section copy) and the system section image, ending at `$5d6a` (staging may
reach `N_STAGELIMIT`, `$8000`). SYS enters `native_start` below `$4000`,
which selects the native map before jumping to the boot code; under BASIC's
map the staging addresses are BASIC ROM. Startup copies the 2,304 low-section
bytes to `$1300..$1bff`, including padding, initializes the page tables and
copies the system section to `$0c00`. The staging pages then become ordinary
managed memory, and no live code executes there. `$3e00..$3eff` retains the browser's complete
selected filename; `$3f00..$3fff` retains the original app source folder.
The observer borrows `$3e00..$3fff` while input is idle,
saves and restores all 512 bytes, and rejects this range as a capture source.
The retained path occupies `$4a00..$4aff` in the existing service reservation.
The workspace reserves `$df00..$feff` in bank 0 for its 8 KiB block so that the
application slot remains available and the remaining high RAM stays contiguous
for document chunks. CPU bank gateways access this RAM beneath ROM and I/O.
Cold entry requires a freshly loaded kernel image. Reentering SYS after that
staging memory has been reused is unsupported; reset and boot reload the image.

Native test observers borrow the existing `$3a00..$3bff` transfer buffer for
at most 512 bytes per IRQ, assembling larger captures on the host and restoring
the buffer afterward. They never write into the resident low region. Foreground
calls and user input must remain idle while that shared buffer is borrowed.

Transfers call the native KERNAL `INDFET`/`INDSTA` gateways at `$ff74/$ff77`.
Their common-RAM routines switch to full RAM `$3f/$7f` for one byte, then
restore the previous configuration. The wrapper preserves `$fb/$fc` and the
gateway's patched pointer operand. IRQs are masked only around each borrowed
pointer/bank operation and can run between bytes. Native IRQ/NMI entry has an
additional saved MMU byte; its ROM/RAM restore stub must remain intact.

The implementation stays at **1 MHz** with both displays enabled. Safe 2 MHz
regions, burst IEC, DMA arbitration and executable bank switching are still
required. Calls from interrupt handlers are forbidden. The allocator lock
detects reentry; it is not a scheduler. Standard native KERNAL interrupts remain
active, and the workspace uses native GETIN, CHROUT and screen switching.

## ABI 1

Include [`src/native/api.inc`](../src/native/api.inc). Call from foreground
bank-0 code with the mapping above. Carry clear and A=0 indicate success;
carry set and A=error indicate failure. Decimal and interrupt flags are
preserved. A/X/Y and arithmetic flags are otherwise scratch. The shared
mailbox/buffer must remain exclusive to the foreground caller until return.

| Entry | Address | Inputs and result |
|---|---|---|
| `N_ALLOC` | `$1c20` | OWNER, PAGES, BANK (0/1/`$ff` automatic); returns HANDLE, actual BANK/PAGE |
| `N_FREE` | `$1c23` | OWNER and HANDLE; releases one allocation |
| `N_READ` | `$1c26` | OWNER, HANDLE, OFFSET, COUNT; copies into N_BUFFER |
| `N_WRITE` | `$1c29` | Same; copies from N_BUFFER |
| `N_FILL` | `$1c2c` | Same, plus VALUE; initializes the requested range |
| `N_STATS` | `$1c2f` | Returns FREE0, FREE1 and reusable SLOTS |
| `N_RELEASE` | `$1c32` | OWNER; validates all its records before releasing any |
| `N_RESERVE` | `$1c35` | OWNER, PAGES, explicit BANK/PAGE; reserves an exact range |
| `N_VSHOW` | `$1c68` | ABI 1.8: current app OWNER and HANDLE for an initialized 36-page bank-0 surface at `$c000`; present the bitmap |
| `N_VCLOSE` | `$1c6b` | ABI 1.8: restore text for the current app without freeing its surface |

The [presentation contract](NATIVE-GRAPHICS.md#presentation-lifetime) covers
display-mode refusal, owner validation and teardown before visible pages or
app ownership are released. Drawing routines are included in app/module code.

OWNER is 1..254. PAGES is 1..255, subject to contiguous availability. A handle
is four bytes: slot+1 followed by a little-endian 24-bit generation. Each reuse
advances the generation. A slot is retired after generation `$ffffff` instead
of reissuing an old handle. An owner must match even when the generation is
valid. Allocation retains existing RAM contents; initialize them before use.

OFFSET and COUNT are unsigned little-endian 16-bit values. COUNT must be
1..512; offset plus count must fit completely within the allocation without
overflow. Validation precedes data changes. Each transfer/free also checks the
descriptor's bank, range and page tags. Failed validation leaves the allocation
and data unchanged. Owner-wide release preflights every matching record so a
corrupt later record cannot leave an earlier one already freed.

| Mailbox | Field |
|---|---|
| `$3d00..$3d03` | OWNER, PAGES, BANK, PAGE |
| `$3d04..$3d07` | HANDLE |
| `$3d08..$3d0b` | OFFSET word, COUNT word |
| `$3d0c..$3d0d` | VALUE, ERROR |
| `$3d0e..$3d10` | FREE0, FREE1, SLOTS |
| `$3d11` | BUSY; private lock, read-only to callers |
| `$3d12..$3d16` | Workspace READY, KEYS word, LASTKEY, last command RESULT |
| `$3a00..$3bff` | N_BUFFER |

ERROR reflects the latest completed API operation. A reentrant attempt returns
7 in A/carry without replacing the active ERROR or lock. The workspace keeps
its command RESULT separately because its subsequent statistics call also
updates ERROR. Apps must not modify the allocation tables or MMU registers.
FREE0, FREE1 and SLOTS are snapshots from `N_STATS`; allocation and release
do not automatically refresh them.
Owner checks provide API discipline, not hardware memory isolation against
arbitrary machine code.

| Error | Meaning |
|---|---|
| 0 | Success |
| 1 | Invalid owner, page count or bank argument |
| 2 | No contiguous free range, or requested reservation overlaps |
| 3 | No reusable handle slot |
| 4 | Invalid, freed or stale handle |
| 5 | Owner does not match |
| 6 | Invalid reservation/transfer range or count |
| 7 | Reentrant call |
| 8 | Unsupported execution/MMU/common/zero-page/stack mapping |
| 9 | Corrupt allocation record or page ownership |

## Validation and references

```sh
python3 tests/ci_native_heap.py --report /tmp/native-heap.json
python3 tests/ci_native_capture.py --report /tmp/native-capture.json
python3 tests/ci_native_relocation.py --report /tmp/native-relocation.json
python3 -u tests/run_ci.py native
python3 -u hw_ultimate_check.py --native
```

The three CPU tests need Py65 from the test requirements. The heap model executes
assembled instructions and the installed C128 ROM's actual bank gateways; it
models only the memory configurations used here. x128 separately cold-boots the
real disk and compares independent RAM-bank contents and complete screens.
The hardware workflow records the Ultimate's drive state, boots a private copy
of the native disk, uses a native IRQ observer for RAM1/VDC readback, then puts
drive A's image and mode back, deletes its upload and resets the C128
(`hw_session.py`). It does not change drive B.
Probe RAM and IRQ state are restored and checked after each observation.

The [checkpoint record](validation/2026-09-09-native-kernel/README.md) records
exact images, test limits and physical results. Per-model C128D/DCR/ROM coverage,
long-running load/input/NMI soak, REU/DMA coexistence and speed transitions remain
separate acceptance gates.
The [resident-growth checkpoint](validation/2026-09-09-native-relocation/README.md)
records the current layout, startup copy, staging reuse and revised observer.

Hardware contracts follow the Commodore *C128 Programmer's Reference Guide*,
printed pp. 453–455 (banked KERNAL access), 467–470 (common RAM/page relocation)
and the MMU memory map; see the [Commodore manual scan](https://www.pagetable.com/docs/Commodore%20128%20Programmer%27s%20Reference%20Guide.pdf).
Jim Butterfield's original [COMPUTE! part 4](https://www.atarimagazines.com/compute/issue78/035_1_Commodore_128_Machine_Language.php)
and [part 5](https://www.atarimagazines.com/compute/issue79/Commodore_128_Machine_Language.php)
explain the native per-byte gateways and their cost. The CPU evidence records
the installed ROM filename and SHA-256; emulator and hardware observations
check the actual native state independently.
