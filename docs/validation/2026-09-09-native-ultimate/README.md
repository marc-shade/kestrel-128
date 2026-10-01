# Native Ultimate storage checkpoint — 2026-09-09

This checkpoint adds Ultimate DOS to the native file API and text editor.
The full OS goal remains active: the native Ultimate directory browser and
loader, shared dialogs, graphical desktop migration, scheduler, REU/other
expansion services and the GEOS/Wheels application backlog remain required.
See the [current roadmap](../../IMPLEMENTATION-ROADMAP.md).

## Change and resource contract

ABI 1.3 keeps the 19 public entries and `$6000` app slot. Format 3 selects
Ultimate files by a 1–255-byte absolute path, with contexts 1/2 sharing the
existing two owned stream slots with IEC. Foreign files and UCI transactions
are refused. Reads use checked 32-bit extents; empty status is accepted only
with an exact byte count. Writes split 512 bytes into 511 + 1 and compare a
seek/readback. The editor additionally closes, reopens and compares the whole
document before clearing dirty state. Errors retain the document and never
replay a write. Failed saves may leave partial files; there is no overwrite.

The kernel reserves bank-0 `$4000..$4fff` for the service and mailboxes.
The allocator now owns 426 pages / 109,056 bytes. Low-kernel staging moves to
`$5000..$54ff`, all reusable after relocation. The workspace's bank-0 block
occupies RAM beneath ROM at `$c000..$dfff`; both 8 KiB blocks coexist with an
app. The editor occupies 43 pages and keeps full path fields while rendering
their tail on each screen. [layout.json](layout.json) records exact bounds.

## CPU and emulator evidence

Twelve CPU reports qualify heap/IRQ boundaries, relocation/staging reuse,
banked observers, app lifecycle, IEC streams/directories, calculator/browser,
banked documents, IEC editor workflows, Ultimate streams and the integrated
Ultimate editor. The Ultimate cases include:

- Fragmented binary reads from 0 to 66,053 bytes and carry across a 16 MiB extent.
- Short writes, the sector-write corruption model, full verification, malformed
  and overlong replies, numeric errors across packets, and bounded timeout/abort.
- Wrong owners and stale handles, foreign DOS files/transactions, mixed IEC/UCI
  handles, retained uncertain ownership and explicit close retry.
- 255-byte paths, the 127-byte creation-component limit, 238 injected IRQs
  during file operations, preserved zero page, and disabled-IRQ rejection.
- Complete editor screens, long paths, both contexts, cancellation, failed
  reopen comparison, recovery, and editing/saving beyond 64 KiB with OOM retention.

[Seven emulator suites](regressions/report.json) pass: the native workspace,
the editor on D64/D71/D81, and the browser on D64/D71/D81. Their boot observers
compare both relocated low code and the entire resident Ultimate region with
the packaged image. The editor workflows independently extract saved files
with `c1541`; each saves 66,056 bytes with SHA-256
`4bfb7babf2cd4195f0735e5a935943d0faa0d77bc2c1f17b502d9bf78fb35051`.

The first emulator workspace run used its old free-page expectation while the
calculator was allocated. Its failed report is preserved in
[initial-emulator-harness-failure](initial-emulator-harness-failure/report.json).
The corrected expectation accounts for the 16 reserved service pages and
the calculator's allocation; all seven subsequent suites pass unchanged images.

## Physical evidence

The [physical run](hardware/report.json) passes on the reference C128/Ultimate
II+. It verifies mixed binary/newline data, a long saved path, missing-file
retention, an empty document, an edit beyond 64 KiB, verified Save As,
existing-file refusal and reopening through DOS context 2. Both screens match
at all 15 checkpoints. There are 55 CPU captures containing 145 bounded IRQ
chunks; all 27 paired direct RAM observations agree with the CPU bytes in this
run. The earlier editor checkpoint's DMA/ROM disagreement remains a reason to
keep the CPU observer authoritative.

Both unrelated 8 KiB workspace blocks survive. The C128 CPU independently
captures all 16,384 bytes for comparison with host-generated patterns. Exit
restores all 256 function-key bytes and releases all 426 heap pages, 32
allocation slots and owned file resources.

Only a new private `/Usb0/uos-native-…` folder is used. All three fixtures are
read back before native boot. After restoring the deployed legacy desktop and
its saved settings, an independent raw UCI probe reopens and compares every
byte of the five closed files, including EOF. Source files remain unchanged;
the 66,056-byte saved copy has the same SHA-256 as the CPU and emulator results
above. Both DOS working directories are preserved and all test files and their
private directory are removed. The 18 legacy build images remain unchanged.

| Physical workflow | Preceding IEC checkpoint | Native Ultimate |
|---|---:|---:|
| Open 66,053 bytes | 295.976 s | 38.311 s |
| Save 66,056 bytes, close, reopen and compare | 523.278 s | 78.891 s |
| Reopen the saved file | 289.889 s | 38.312 s, DOS context 2 |

[performance.json](performance.json) links each duration to its input event.
These times start at Enter, exclude path typing and include the harness's
30-second initial quiet interval and 2-second polling. Boot uses 60 seconds of
quiet, ordinary keys/literal queues 4 seconds, and captures 2 seconds. These
are workflow measurements, not isolated transfer benchmarks.

Typing still redraws the full document on both screens: ten queued filename
characters took about 26 seconds with a small document and 46 seconds with the
cursor beyond 64 KiB. Incremental field/document redraw is the next performance
work item. The console also showed at least two read-only RAM observation
timeouts followed by successful retries; [observation notes](observation-notes.json)
state the recording limit. Mutating commands were not replayed.

An initial connection timeout occurred while preparing the first 37-byte
fixture, before the new kernel was booted. Its report and exact error are
preserved in [initial-hardware-connection-timeout](initial-hardware-connection-timeout/outcome.json).
The retry passed both foreign-handle probes and independently verified all
three source fixtures. This timeout is not evidence of a native-kernel failure.
The bounded [cleanup record](initial-hardware-connection-timeout/timeout-fixture-cleanup.json)
records inspection and removal of only that earlier private fixture and folder,
with the desktop, settings and DOS path preserved.

## Reproduction and limits

`verify-package.py` copies the private source snapshot to a temporary directory
and rebuilds there, preserving the archive and working hardware-test images.
It verifies all six native outputs, four independent
disk extractions, the boot-sector reservation, ABI 1.3 and the memory map.
All 18 legacy images and the native boot/calculator/browser PRGs are identical
to signed source `1a106390125f6ff7ebf50393da599557952c87a2`.

```sh
python3 docs/validation/2026-09-09-native-ultimate/verify-package.py
python3 docs/validation/2026-09-09-native-ultimate/verify-artifacts.py
cd docs/validation/2026-09-09-native-ultimate
sha256sum --check --quiet SHA256SUMS
```

The archived oracle helpers keep screen and disk comparisons independent of
later UI changes. The [artifact audit](artifact-verification.json) checks 108
complete VIC/VDC frame pairs, 280 captures containing 789 IRQ chunks, and 126
paired RAM observations. CPU models do not qualify electrical timing. Emulator IEC
drive variants do not qualify physical 1571/1581 devices. Performance figures
must include the hardware harness's quiet/poll intervals; they are workflow
elapsed times, not standalone transport benchmarks. Installed firmware revision,
power-loss durability, hot removal/media identity and additional cartridge/
expansion families remain outside this checkpoint's qualification.
