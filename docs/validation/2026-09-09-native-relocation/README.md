# Native resident kernel growth — 2026-09-09

The allocator now runs in the reserved bank-0 low region. Startup copies it
from declared staging storage before heap initialization, allowing those
staging pages to become ordinary managed memory. All 19 public jump entries,
mailboxes and the `$6000` application entry retain their addresses. The heap
still manages 442 pages / 113,152 bytes.

This removes the browser checkpoint's immediate resident-code limit. It does
not implement the native editor, desktop toolkit, scheduler, Ultimate service
migration or expansion drivers. Those remain on the
[completion roadmap](../../IMPLEMENTATION-ROADMAP.md) and
[next platform steps](../../NATIVE-PLATFORM-NEXT.md).

[SHA256SUMS](SHA256SUMS) covers every archived artifact except itself.
Run `sha256sum -c SHA256SUMS` from this directory to check the record.
The [artifact audit](artifact-verification.json) cross-checks report/image hashes,
chunk extents, exact boot bytes, saved screens and independently extracted disk
contents. Run `python3 verify-artifacts.py` from this directory in the repository
to repeat that readback audit without accessing hardware.

## Layout and exact images

The preceding signed source reference is `818154871d9dbf2d2697082f1db1d8c5ed900637`.

| Image | Bytes | SHA-256 |
|---|---:|---|
| `uos128.prg` | 9,985 | `279476aa3e5fa48f0ab0fc1dfd57a91537c90b0e9d888f4fb674bf6221f596bb` |
| `boot.prg` | 258 | `f4babe887e041ea6c1a0c1219061f3cdd3ef8a61ec40c6c133dbb423f7f88ffd` |
| `calc.prg` | 2,573 | `7c7e6f1a33aa2e0cb762c12ab970e4cc0bf16f05fa8dbddab6fa3d2b939f56ca` |
| `browse.prg` | 3,418 | `4ad53ec06a051029e72ffeed374922dcfa205fde24fd2f9c432ef0fe1bae334f` |
| `uos128.d64` | 174,848 | `065cae34795c11435ccd14b7a648c9579b3ff508e1d82e1a2f328222bc61f2b9` |

Boot, calculator and browser PRGs match the preceding checkpoint byte for byte.
The [generated layout](layout.json) and [runtime symbols](uos128.sym) describe:

| Region | Purpose |
|---|---|
| `$1300..$17c5` | 1,222 bytes of resident allocator code/data |
| `$17c6..$1bff` | 1,082 bytes available for low-region growth |
| `$1c01..$32d6` | BASIC entry, public jump table, startup and main resident code/data |
| `$32d7..$37ff` | 1,321 bytes available for main-region growth |
| `$3800..$3de3` | Existing ownership tables, transfer buffer, mailboxes and file descriptors |
| `$3e00..$42ff` | Five-page boot staging copy; no live code executes here after initialization |

Startup copies 1,280 bytes, including 58 padding bytes, to `$1300..$17ff`.
The 8502 stays in MMU configuration `$0e`; the copy preserves decimal/interrupt
flags and restores its modified operands. `$3e00..$3fff` remains reserved
scratch, while `$4000..$42ff` is reused by the workspace's first bank-0 allocation.
No additional heap pages are permanently reserved. Larger resident modules
still need explicit placement, ownership and lifetime rules.
Cold entry requires freshly loaded staging bytes. The CPU repeat-entry check
keeps those bytes intact; it does not qualify a warm SYS restart after heap
reuse. Reset and boot reload the kernel image.

The [isolated package check](package/report.json) rebuilt five identical
images, compared layout/symbol outputs, checked all public JMP destinations,
verified the BAM and reserved boot sector, and independently extracted U,
CALC and BROWSE. All 18 legacy images match the preceding signed commit.
[verify.py](package/verify.py) builds copied source in a fresh directory.

## Observer and CPU verification

The old observer output at `$1400` would overwrite the relocated allocator.
The revised probe instead writes at most 512 bytes into `$3a00..$3bff` per IRQ.
The host assembles larger observations from chunks, restores its borrowed
buffer/probe area, and compares the complete low resident region before/after.
RAM0 requests overlapping either borrowed range, and wrapped source ranges,
are rejected before writes. An active file service also blocks borrowing its
buffer. This is an idle foreground observation contract;
it is not a concurrent application/file-service operation.

The listing reader now uses the runtime PC in a 64tass `.logical` section,
rather than interpreting its file/staging offset as the execution address.
The build emits independent symbol and layout files to make both extents
reviewable.

All eight CPU reports passed on the recorded image/probe hashes:

| Report | Coverage |
|---|---|
| [Relocation](cpu-relocation.json) | Nine cases: four D/I combinations with/without IRQ interleaving, repeat entry, exact copied bytes, both edge guards, original high resident bytes/bank 1 preserved, staging poisoned and then reused by the heap |
| [Observer](cpu-capture.json) | 32 cases: native ROM IRQ frame, both RAM banks/low code/ROM and I/O overlaps, VDC readiness/drift, invalid commands, complete 2,000-byte host assembly, third-chunk failure restoration and host source/busy guards |
| [Heap](cpu-heap.json) | 778 calls including initialization, 50 boundary transfers, 1,608 interrupt attempts, complete 442-page capacity and ownership/fault checks |
| [Apps](cpu-apps.json) | 52 manifest, ABI, loader, exit/handoff and cleanup cases |
| [Files](cpu-files.json) | 93 stream, ownership, exact-extent and failure cases |
| [Directory](cpu-directory.json) | 18 geometry, page, ownership and cleanup cases |
| [Calculator](cpu-calc.json) | Arithmetic/history, complete screens, verified export, source formats and error/cleanup checks |
| [Browser](cpu-browser.json) | Eight directory/cache/preview/handoff workflows, embedded-name rejection and full 296-entry D81 capacity |

## Emulator and physical qualification

| Emulator workflow | Result |
|---|---|
| [Workspace/calculator](emulator-workspace/report.json) | PASS: exact boot relocation, both 8 KiB allocations, calculator/history export and full release |
| [D64 / true 1541 browser](emulator-d64/report.json) | PASS: exact boot relocation, all 12 complete VIC/VDC frame pairs, byte previews, app rejection/launch/save/return and cleanup |
| [D71 / true 1571 browser](emulator-d71/report.json) | PASS: boot D64 on drive 8, data/apps on drive 9 with format context preserved |
| [D81 / true 1581 browser](emulator-d81/report.json) | PASS: boot D64 on drive 8, data/apps on drive 9 with format context preserved |
| [D64 file service](emulator-files-d64/report.json) | PASS: 66,053-byte copy/reopen, exact small extents, file types, cleanup and disk-full protection |
| [D71 file service](emulator-files-d71/report.json) | PASS: 66,053-byte copy/reopen, exact small extents, file types and cleanup |
| [D81 file service](emulator-files-d81/report.json) | PASS: 66,053-byte copy/reopen, exact small extents, file types and cleanup |

The [seven-suite run](regressions-all/report.json) passed sequentially with
fixed image hashes. It includes the retained
[initial workspace](emulator-workspace-initial/report.json) and
[initial D64 browser](emulator-d64-initial/report.json) results. The
[two-suite follow-up](regressions-boot-bytes/report.json) passed after adding the
explicit boot-byte comparison and host file-busy guard. No product image changed
between these runs. The D71/D81 browser runs use the revised bounded observer
but predate the explicit `resident_boot` assertion.

The [physical report](hardware/report.json) passed on the reference
C128/Ultimate II+ at `192.0.2.237`, using a private D64 on drive A/IEC 8 in
1541 mode. CPU readback matched all 1,280 staged bytes exactly before allocation:
SHA-256 `d6d2e3665019c5291ffac64466cbd0102ee478259855fa2cb638530dd9bf54a0`.
The workspace then allocated bank-0 page `$40` and bank-1 page `$04`, filled and
verified 8 KiB in each, and thereby reused all three managed staging pages.

All 12 complete VIC/VDC frame pairs matched through directory browsing,
257-byte/one-byte/empty previews, bad-CRC rejection, renamed-calculator launch,
the exact `42` + CR history export, browser return and workspace restoration.
The final workspace released all owned app/file resources. Native comparison
verified the two protected 8 KiB allocations; independent CPU captures compared
a 2,000-byte prefix of each before release.

The 15 physical captures comprise 59 IRQ chunks, each at most 512 bytes.
Every capture restored its borrowed buffer/probe area and preserved the whole
resident low region. The run included one successful retry of a read-only RAM
observation after an HTTP timeout. The additional host file-busy rejection was
added after this physical process started; it has CPU and follow-up emulator
coverage. The physical IRQ probe bytes are identical to the final tested probe.

After restoring the legacy desktop, the harness retrieved the complete
174,848-byte closed D64 through Ultimate DOS. Its SHA-256 is
`9c67c7dcc6a9d61d186eed73d12208beb25bc97119441053fb2243bae5fc5925`.
An independent sector-chain reader matched all 20 files, including the empty
file's zero stored bytes. c1541 separately matched all 19 nonempty files. The
native boot sector was unchanged. The legacy desktop was live after readback,
with its nine-byte settings record and both DOS paths restored; the other drive
and printer settings were preserved.

The recorded quiet intervals are 60 seconds at boot, 30 for directory/app
actions, four per ordinary key and two before each capture chunk. These host
event times are not application-latency measurements. Physical D71/D81 hardware,
other C128/ROM variants, 2 MHz operation, REU/DMA coexistence and long-running
input/NMI soak remain separate qualification gates.
