# Native application loader and calculator — 2026-09-09

This checkpoint adds checked IEC loading, an owned foreground application
lifecycle and a separate native calculator with bank-1 history. It advances
the native migration; the graphical desktop, remaining apps and shared native
filesystem still require implementation. The full OS goal and R3 remain open.
See the [application guide](../../NATIVE-APPS.md) and
[completion roadmap](../../IMPLEMENTATION-ROADMAP.md).

## Exact images and packaging

| Image | Bytes | SHA-256 |
|---|---|---|
| `target/native/uos128.prg` | 8,577 | `16feb476227e3adb5ea409ab4abc349cc2acfc88c9630f5214f590123f153251` |
| `target/native/boot.prg` | 258 | `f4babe887e041ea6c1a0c1219061f3cdd3ef8a61ec40c6c133dbb423f7f88ffd` |
| `target/native/calc.prg` | 1,650 | `bf869533b05d7e83f77214b95b81d04694509a1af4672f35b77207aaf2eda3bd` |
| `target/native/uos128.d64` | 174,848 | `28bba6257bf946f4283b278243408145f5579a2576b361dae048992f30f4e1c9` |

A private clean build reproduces all four images byte for byte. c1541 extracts
both disk files exactly; the boot sector remains allocated separately and
every track's BAM free count matches its free bits. `U` uses 34 blocks, `CALC`
uses 7 and 622 remain free. The 17 legacy PRGs and legacy D64 are unchanged
from signed commit `7794f8d`. See [package/report.json](package/report.json).

Native code/data end at `$2a0f` exclusive; private tables, transfer buffer and
mailboxes occupy `$3800..$3d7f`. The calculator declares 16 pages at `$6000`,
has 1,648 image bytes including its manifest, enters at `$6020` and carries
CRC16 `$d950`. Its 512-byte history is a separate allocation in bank 1.

## CPU and fault coverage

[cpu-apps.json](cpu-apps.json) records 48 passing cases against the assembled
kernel. The harness executes the actual native bank gateways and models the
external KERNAL IEC calls; x128 and hardware below exercise real IEC loading.

Coverage includes:

* Balanced return and stack-restoring `N_EXIT`, separate application and loader
  results, zero-initialized BSS, a one-page image and the full 24 KiB slot.
* Load address, magic, format, ABI, flags, allocation, title, entry and size
  rejection; short streams at the address/header/payload boundaries, trailing
  data and CRC damage. Rejected bytes never become executable app entry.
* Missing file/device, serial read and close failures; masked interrupts,
  code-slot overlap, existing app owner, redirected console, channel conflicts
  and bad device/name arguments.
* App-owned secondary allocations, foreign owner/file preservation and an
  atomic cleanup failure that retains the corrupt owner's complete allocation.

[cpu-calculator.json](cpu-calculator.json) covers 11 arithmetic cases and 96
input events, including overflow, underflow, division by zero, delete and
immediate operation order. A second session evaluates 40 results, retains the
newest 32, pages through all history views and checks every visible cell on
both screens. Exit releases the code/history allocations, including while an
arithmetic error is latched. The instruction-level input check rejects any
publication of a consumed key with `N_READY=1` before the app returns to its
idle loop.

[cpu-heap.json](cpu-heap.json) reruns 692 heap calls, 50 bank-boundary transfer
cases and 1,608 interrupt attempts against this final kernel. All 442 managed
pages recover. [cpu-capture.json](cpu-capture.json) passes all 19 observer
cases, including faults, bounds, MMU/register restoration and VDC address drift.
These are focused CPU/bus models, not full machine or peripheral emulators.
The native ROM is `kernal-318020-05.bin`, SHA-256
`64ed21ad31da2840aa90eab70c6ed4731f63268a1b3c5cf85273e28d6cfa6d4d`.

## x128 integration

[emulator/report.json](emulator/report.json) and
[regressions/report.json](regressions/report.json) pass on the final disk.
x128 cold boots the disk through the native KERNAL, exercises both 8 KiB
workspace allocations and verifies all bytes through its independent RAM-bank
monitor views. Both text screens and the native capture observer agree.

The workspace loads the separate `CALC` PRG through IEC. `12+30=` displays
`42` on both complete screens. The code and history have the expected owner,
bank and page counts; Esc releases all app allocations and leaves no loader
logical files open. The native machine remains responsive afterward.

## Physical reference C128 + Ultimate II+

[hardware/report.json](hardware/report.json) is a terminal **PASS**, including
restoration of the live deployed desktop. The run uses machine reset to boot
the native disk, with a full 60 seconds free of RAM DMA during each native or
legacy boot and 30 seconds before observing each application load.

The 43 input events and 25 native CPU captures verify:

* Native MMU mode and common RAM; both complete text displays; separate bank-0
  and bank-1 8 KiB allocations. All 16,384 data bytes match independent host
  patterns, using cartridge DMA for bank 0 and native CPU reads for bank 1.
* The calculator runs while both workspace allocations remain live. `42`,
  `OVF` and `DIV/0` each match independent direct DMA and native CPU reads of
  the complete eight-byte display buffer, plus all VIC and VDC screen cells.
  Each VDC screen is captured twice and the pair must agree.
* An independent CPU read of bank-1 history matches all three 16-byte records.
  Esc during `DIV/0` releases only app resources; both workspace blocks remain.
* A private disk with one unsealed payload-byte change returns checksum error
  `$14`, closes loader channels and retains the caller's allocations. A valid,
  sealed app variant returning A=2 produces loader success and workspace
  result 2. The good calculator then loads again with a fresh history session.
* Both retained workspace blocks still verify, then release all 442 pages and
  32 handles. Native keyboard input continues after all observations.

All 25 CPU captures restore their borrowed RAM/IRQ state; all 16 VDC captures
complete without address resynchronization. One host RAM observation timed
out during damaged-app checking and succeeded through the existing bounded
read retry. The run does not use a retry to bypass any content assertion.

Drive A is restored with the unchanged legacy disk under a fresh firmware
`/Temp` filename. The legacy desktop is live, its nine-byte settings record is
unchanged, and drive B/software IEC/printer inventory is unchanged. All build
hashes remain stable throughout the run. No cartridge filesystem commands or
USB fixture files are used. The earlier inaccessible long-name USB fixture
remains outside this checkpoint's scope.

The observer PRG is unchanged at SHA-256
`bc9305d5f79808ee2eaf1fe12f7afb91e8d337d295b4d37e6b472ffabfc0c4aa`.
It operates only while this foreground workspace/app is idle; these results
do not qualify arbitrary concurrent rendering, ROM variants or C128D/DCR models.

## Development failures retained

The first emulator app check assumed the free-page statistics mailbox updates
automatically. It instead contains the last `N_STATS` snapshot. The app loaded
and calculated 42, but that stale-count assertion failed. The test now checks
the actual ownership/page tables while the app runs. The failed disk and log
remain in [before-page-count-oracle](before-page-count-oracle/).

A hardware run on kernel `8e73b915353be0dc65b6dbc3c670b53a0ff677f9436c4251eeaf8b60df764f38`
failed a direct display-buffer assertion after entering the overflow case.
Its later saved VIC screen shows correct `OVF` and history. The first mismatching
buffer bytes were not saved, so the exact physical sample and cause cannot be
established retrospectively. That run restored the live legacy desktop and
left images unchanged. Its report, captures and exact build/source remain in
[before-readiness](before-readiness/).

Investigation found a reproducible input-publication race: `N_KEYIN` advanced
the key counter while the preceding iteration's ready flag could still be set.
The new CPU invariant fails on the retained old kernel at `$28cd`, before the
app's input loop. The kernel now clears readiness before advancing the counter;
that invariant and all final suites pass. Hardware diagnostics now retain the
first DMA sample, compare a separate native CPU read, and save app RAM/state
on failure. This fixes the proven race without claiming the missing physical
sample independently proves its cause.

## Remaining scope and reproduction

This lifecycle owns RAM and its loader's IEC channels. Application-created
raw KERNAL files still need explicit close by the app. Shared native file
handles, app discovery, banked documents, scheduling, native display/input
services and the remaining desktop/Ultimate migrations are next. CRC checks
damaged files; it does not isolate arbitrary app machine code from system RAM.

Run the commands in the [native app guide](../../NATIVE-APPS.md). CPU suites
require Py65; the tests here used `<home>/.venvs/uos-tests/bin/python`.
`source-hashes.json` identifies the final implementation and test sources.
`evidence-hashes.json` identifies retained files. Copied text logs/transcripts
have trailing spaces and empty rows trimmed; firmware version JSON is formatted.
Binary captures and images retain their original bytes.
