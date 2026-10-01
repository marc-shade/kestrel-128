# Native editor redraw checkpoint — 2026-09-09

The editor previously rescanned its document and cleared both screens for each
field character. The preceding physical run measured about 26 seconds for ten
queued filename characters with a small document and 46 seconds with the cursor
beyond 64 KiB. This checkpoint updates affected rows and retains useful document
read pages. The complete OS remains in progress; native Ultimate browsing and
loading, shared dialogs/input, the graphical desktop, scheduler, expansion
services and the application backlog remain required by the
[roadmap](../../IMPLEMENTATION-ROADMAP.md).

## Rendering and memory contract

Fields, shortened input, cancellation and range errors repaint only status row
6 on each display, without reading the document. Ordinary edits and cursor moves
within the same viewport repaint the old/new caret rows and mutable headings.
Structural changes, viewport movement, new documents and file-operation returns
use the complete renderer. Native ROM PLOT/CHROUT handles screen positioning and
character output; the existing quote-mode guard remains in place.

Two 512-byte pages cover document reads around a page boundary. One reuses the
document output buffer; the second belongs to the app. Edits, file-operation
returns and failed cache fills invalidate both. Seventeen 24-bit line offsets
describe the viewport. Single-byte edits adjust later offsets, including carry
and borrow across `$ffff`; structural redraw rebuilds them. Cursor-only updates
retain valid pages and offsets.

The editor is 12,202 PRG bytes, with a 12,200-byte payload at `$6000..$8fa7`.
Its 48-page allocation uses five more pages / 1,280 bytes than the preceding
editor. Document capacity remains subject to 4 KiB allocation fragmentation
and other live allocations. The 426-page kernel allocator, ABI 1.3 and file
backends are unchanged. The kernel, boot, calculator and browser PRGs, and all
18 legacy images, match signed source
`1282d616e6a2d6cd0bcac27a7f4631d82547df20`.

## CPU and emulator evidence

The CPU reports qualify the [complete IEC editor suite](cpu-editor-iec.json)
(nine groups), [integrated Ultimate editor](cpu-editor-ultimate.json) (three
groups), and [focused redraw checks](cpu-redraw.json). They cover mixed
binary/newline data, quoted carets, long paths,
discard/cancel/error recovery, allocation failure, verified Save As and reopen
beyond 64 KiB. The focused suite checks 1,086 complete frames and 516 field
actions without document reads. It also bounds the written rows, checks the
255-byte field limit and shortening, and exercises line-offset carry/borrow
before moving between those lines.

| Action | Previous model steps | Current model steps | Previous/current CHROUT calls |
|---|---:|---:|---:|
| Ten field characters, small document | 413,730 | 15,270 | 23,250 / 1,180 |
| Ten field characters, beyond 64 KiB | 5,207,520 | 15,270 | 23,250 / 1,180 |
| Insert one byte beyond 64 KiB | 583,191 | 142,797 | 2,344 / 480 |
| Backspace beyond 64 KiB | 523,947 | 83,541 | 2,344 / 480 |
| Move right beyond 64 KiB | 522,873 | 15,730 | 2,344 / 480 |

[Before](profile-before.json) and [after](profile-after.json) profiles identify
their exact images. These count CPU-model loop steps with ROM/cartridge calls
stubbed; they do not measure complete 8502 cycles or physical elapsed time.
The focused checks observe no page reads for the retained large-document cursor
move, and at most two after insertion/deletion at the tested boundary.

[D64, D71 and D81 emulator workflows](regressions/report.json) all pass. Each
checks the actual ROM key and cursor-positioning paths, complete VIC/VDC frames,
both document banks, workspace preservation, owned-resource cleanup and saved
bytes independently extracted with `c1541`. All save 66,056 bytes with SHA-256
`4bfb7babf2cd4195f0735e5a935943d0faa0d77bc2c1f17b502d9bf78fb35051`.

## Physical qualification

The [reference C128/Ultimate II+ run](hardware/report.json) passed the complete
private-USB editor workflow, including 24 VIC/VDC frame pairs and 22 editor-state
comparisons. Timed field entry, shortening/cancellation and cursor moves beyond
64 KiB each have complete screen/state checks.

| Physical operation | Elapsed seconds | Quiet interval, seconds |
|---|---:|---:|
| Ten field characters, small document | 1.230 | 0.1 |
| Ten field characters, beyond 64 KiB | 1.229 | 0.1 |
| Cursor right beyond 64 KiB | 2.322 | 0.1 |
| Cursor left beyond 64 KiB | 2.324 | 0.1 |
| Insert four characters beyond 64 KiB | 4.195 | 4 |
| Backspace beyond 64 KiB | 2.322 | 0.1 |

The [performance audit](performance.json) also compares 31 ordinary ten-character
filename queues in each run with the same 4-second quiet interval. They take
4.194–4.198 seconds now (median 4.196), versus 25.705–45.988 seconds previously
(median 26.632). These elapsed times include the stated quiet interval and host
monitoring. Single-key polling uses a 2-second interval; these measurements do
not isolate application latency or physical keyboard throughput.

Opening 66,053 bytes took 38.309 seconds, verified Save As of 66,056 bytes took
78.891 seconds, and reopening through the second DOS context took 38.311 seconds.
The harness independently compared all five closed source/output files,
including the complete edited file and EOF. It verified all 16,384 workspace
bytes, restored all 256 function-key bytes, and released all 426 heap pages,
32 handles and owned streams. It restored the deployed legacy desktop,
settings and both DOS paths, removed its five files and private USB directory,
and checked that the tested images remained unchanged.

The [combined artifact audit](artifact-verification.json) covers 78 emulator and
physical VIC/VDC frame pairs, 250 CPU captures in 628 bounded IRQ chunks, and
144 comparisons between CPU and direct-DMA observations.

Two of 45 physical RAM observations have direct-DMA bytes different from the
C128 CPU captures. The entire 128-byte sample at `$6a72` matches BASIC low ROM
`318018-04`; the entire 587-byte sample at `$8406` matches BASIC high ROM
`318019-04`. Both CPU captures pass their document/app-state and screen checks.
The [ROM comparison](rom-observations.json) retains the observation ranges and
exact ROM hashes; both raw observations remain in the hardware evidence.
`verify-rom-observations.py` repeats the comparison with separately installed
reference ROMs. The archive does not include full ROM images.

## Reproduction and limits

The private source/image snapshot, independent screen oracles and test sources
are retained here. `verify-package.py` builds in a temporary directory and
compares all six native images, assembler rows, four independent disk
extractions and the unchanged preceding binaries. `verify-artifacts.py` audits
the captured bytes, frames, ownership records and timing-event references.
The verification commands compare the archived reports without changing archive
files.
The explicit `--record` option is used only when first assembling a checkpoint.

```sh
python3 docs/validation/2026-09-09-native-redraw/verify-package.py
python3 docs/validation/2026-09-09-native-redraw/verify-artifacts.py
python3 docs/validation/2026-09-09-native-redraw/verify-rom-observations.py /usr/share/vice/C128
cd docs/validation/2026-09-09-native-redraw
sha256sum --check --quiet SHA256SUMS
```

CPU models do not qualify electrical timing. Emulator drive variants do not
qualify physical 1571/1581 hardware. Physical timing includes the stated quiet
intervals and host observation. Additional machine/ROM/cartridge revisions,
physical key switches, power-loss durability and hot removal remain outside
this checkpoint's qualification. Larger UI and document operations still need
performance work; this does not complete the desktop or application roadmap.
