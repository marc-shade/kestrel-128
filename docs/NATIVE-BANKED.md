# Native bank-1 executable components

The native SDK can load a separate executable component directly into owned
bank-1 RAM and call it from a retained bank-0 app. The resident kernel and its
426-page heap are unchanged. This provides another 24 KiB executable region;
the component still consumes ordinary heap pages. It is a foundation for
moving larger app services out of the almost-full bank-0 application slot.
Editor documents and the remaining VDC app interfaces have not moved yet.

The [standalone example](../examples/native-banked/README.md) runs the native
REU arena in bank 1. Its two files demonstrate actual separate loading: the
bank-0 app contains no copy of the provider. This is an experimental native
SDK facility, separate from the replaceable bank-0 `NMOD` window. It adds no
resident ABI entry or permanent common-RAM scratch allocation.

## Parent lifetime

Include `banked.inc` and then `banked-load.inc` exactly once in the retained
bank-0 core. Both must remain outside any replaceable module window. Call
with native bank-0 mapping, standard zero-page/stack mapping and IRQs enabled.
All entries preserve the caller's decimal and interrupt flags. Other registers
and the normal native argument mailboxes may change.

| Entry | Contract |
|---|---|
| `bk_load` | Pass an already-open native read stream in `N_FHANDLE`, owned by 32. Load and close its source, then make the component callable. |
| `bk_call` | A selects the provider operation. Arguments/results use `N_BUFFER` or the provider's documented interface. Return the provider's A/carry. |
| `bk_close` | Retry retained source close, then free the owned bank-1 code allocation. It does not invoke provider-specific cleanup. |

`bk_error` reports a loader/gate error; it is zero after a completed provider
call even when that provider returns carry set. `bk_state` is 0 empty, 1
loading or cleanup retained, or 2 ready. `bk_file` and `bk_handle` retain the
source and code tokens. The code occupies a fixed allocation starting at
bank-1 `$6000`, ending no later than `$c000`. An occupied range causes a clean
allocation failure; the loader does not relocate another allocation.

`bk_load` first validates the foreground context, file ownership and common
ROM routines. If this preflight fails, the caller still owns its stream.
Once `bk_state` becomes 1, the loader owns it. Later failures retain state 1
and any acquired handles until explicit `bk_close` succeeds. A second load
is refused while state is nonzero. The source must close successfully before
execution is enabled. There is no automatic load or I/O retry.

Before every call, the executor checks the parent allocation generation,
the bank-1 code token, owner, bank, extent, entry range and every allocated
page tag. The provider is trusted native code: this is lifetime and bounds
checking, not an execution sandbox. It must balance its stack, restore any
hardware state it borrows, and return with RTS. No nested banked call, task
switch, foreground call from an interrupt, or one-way app exit is supported.

Close provider resources **before** `bk_close` or `N_EXIT`. In particular,
release REU allocations and successfully call `ru_close` before discarding
its bank-1 context. A failed probe restoration must keep that code and state
owned for retry. Display providers must restore their saved display first.
The generic executor cannot infer which resources arbitrary provider code owns.

## Memory map and native callbacks

The executor temporarily expands bottom common RAM from 1 KiB to 16 KiB and
uses configuration `$4e`. This exposes the native tables and `N_BUFFER` in
bank 0 while the component executes from bank 1. Physical bank-1 bytes
`$0400..$3fff` remain untouched; they are temporarily hidden from CPU reads.
The bank-0 services and path/status mailboxes at `$4000..$4fff` are not common.

The component includes `banked-client.inc`. Call `bk_native` with A equal to
the zero-based native jump-table index, using the usual service arguments.
The bridge restores native bank-0 mapping and the original common-RAM size
**before** entering a native service. Consequently, heap reads and writes can
still access low bank-1 document pages correctly. On return, the bridge restores
the bank-1 execution map. Both directions preserve the callee's A/carry.
An IRQ-disabled callback is refused before entering the service.

| Allowed indices | Native services |
|---|---|
| 0–5, 7 | Allocate, free, read, write, fill, stats, reserve |
| 11–16 | File open/read/write/close/release and directory pages |
| 19–20 | Field edit/draw; field state and buffer belong to the bank-0 parent |
| 24–27 | Display show/close and Ultimate query/command |

Callbacks cannot free, write or fill the active component or its parent app
allocation. Heap callbacks other than stats require owner 32. Owner-wide heap
release, input polling, launch/exit/replace/workspace, and module load/call/close
are refused. Interactive loops and app handoff remain in the parent. Prepare
bank-0 path arguments such as `N_UPATH` in the parent; a direct bank-1 reference
to `$4e00` accesses different RAM. The same applies when consuming `N_USTATUS`.

The bridge checks the exact existing common-RAM tails at `$02ab` and `$02f2`
before loading/calling. It borrows and restores only the ROM's A/X/Y argument
bytes `$06..$08`; it installs no trampoline in unassigned system RAM. The
switching sequences follow Commodore's pinned
[C128 KERNAL source](https://github.com/mist64/cbmsrc/blob/01bd60f162ef92212ef0cb67546ae8f42be34168/KERNAL_C128_05/routines.src).
A different ROM tail is a platform refusal, rather than an assumed-compatible call.

## NBK1 file format

Files are PRGs with load address `$6000`. The following 32-byte header starts
after the two-byte PRG address. `native_banked.py` validates and seals it;
the 8502 loader independently checks the same format and exact EOF.

| Offset | Bytes | Meaning |
|---|---:|---|
| 0 | 4 | ASCII `NBK1` |
| 4 | 1 | Format 1 |
| 5–6 | 2 | Required native ABI major/minor; this SDK parent requires 1.12 |
| 7 | 1 | Zero flags |
| 8 | 2 | Loaded length LE16, 33–24,576 bytes including this header |
| 10 | 1 | Exactly ceil(length / 256) pages |
| 11 | 1 | Bank 1 |
| 12 | 2 | Entry offset LE16, at least 32 and less than loaded length |
| 14 | 2 | CRC16-CCITT, initial `$ffff`, with these two bytes treated as zero |
| 16 | 5 | `LDX #$0e` / `JMP $02ab` exit stub |
| 21 | 1 | Zero |
| 22 | 2 | Zero callback import; patched by the loader after validation and source close |
| 24 | 8 | Zero reserved bytes |

Transfers go through the existing 512-byte native file and heap services.
There is no temporary bank-0 copy of the whole file. Page padding is neither
loaded nor executable entry space. CRC detects file damage; it is not a
signature or authentication mechanism. Runtime code may modify its private
state and dispatch instructions, so the loader does not recompute file CRC
on every call.

## Banked REU variant and qualification

With `RU_BANKED = 1`, `reu.inc` requires the executor's bank-1/common-16-KiB
map. Its private two-byte probe buffer uses physical bank-1 DMA; payload
transfers still use physical bank-0 `N_BUFFER`. Both paths restore the original
DMA-bank and speed bits. There must still be exactly one retained REU arena
per foreground app. The default bank-0 library produces the existing shipped
Calculator image unchanged at that checkpoint. The suite now uses the same
executor for its [shared VDC component](NATIVE-VDC-SERVICE.md).

`ci_native_banked.py` executes checked loads, malformed files, ownership and
generation failures, partial I/O/probe failures, native callbacks, maximum
24-KiB files, and interrupt injection across bank transitions. The SDK test
uses both complete consoles, three IEC geometries and both Ultimate DOS
contexts, including absent REU and corrupt-provider exits. The VICE test cold
boots private C128 disks and compares complete REU snapshots independently
of the provider. It also checks low bank-1 data, the bank-0 probe shadow,
borrowed registers, native callbacks and final heap recovery.

These are software/emulator checks. Physical ROM, C128/D/DCR, REU and Ultimate
qualification, app suspension and the larger app/display migrations remain open.

## Persistent instances

`BK_BASE`, `BK_LIMIT` and `BK_OWNER` (the code allocation's owner) are weak
defaults (`$6000`, `$c000`, owner 32). Including `banked.inc` and
`banked-load.inc` inside a `.block` that defines them creates a second,
independent executor; the default instance assembles byte-identically. When
`BK_OWNER` is not the app owner, the instance also accepts heap callbacks for
that owner and adds `bk_attach` (adopt a resident image instead of loading)
and `bk_detach` (forget it without freeing). The [AES](NATIVE-AES.md) is the
first such instance: owner 30 at `$8700` (`AE_BASE`).
