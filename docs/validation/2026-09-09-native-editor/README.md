# Native banked text editor — 2026-09-09

EDITOR is a disk-discovered ABI 1.2 application with owned documents spanning
both C128 RAM banks. It provides cursor editing, a scrolling viewport on both
displays, transactional Open and exclusive Save As followed by complete reopen
comparison. A 66,053-byte input is edited at byte 65,537; the resulting 66,056
bytes are compared independently after saving.

This is a plain-text application milestone. Selection, clipboard, undo/find,
shared visual file dialogs, word-processor layout/printing, native desktop and
Ultimate service migration, scheduling and expansion drivers remain on the
[completion roadmap](../../IMPLEMENTATION-ROADMAP.md). The OS is not complete.
See the [editor guide](../../NATIVE-EDITOR.md) for keys, capacity and failure behavior.

[SHA256SUMS](SHA256SUMS) covers archived artifacts except itself. Run
`sha256sum -c SHA256SUMS` here to check the record. The
[artifact audit](artifact-verification.json) cross-checks image/report hashes,
CPU-captured state, all editor screens, ownership cleanup and disk contents.
`python3 verify-artifacts.py` repeats that audit without accessing hardware.

## Exact package

The preceding signed source reference is `bf78b1e12b46ac56b2c4c83b6c9690722ebb21d3`.

| Image | Bytes | SHA-256 |
|---|---:|---|
| `uos128.prg` | 9,985 | `279476aa3e5fa48f0ab0fc1dfd57a91537c90b0e9d888f4fb674bf6221f596bb` |
| `boot.prg` | 258 | `f4babe887e041ea6c1a0c1219061f3cdd3ef8a61ec40c6c133dbb423f7f88ffd` |
| `calc.prg` | 2,573 | `7c7e6f1a33aa2e0cb762c12ab970e4cc0bf16f05fa8dbddab6fa3d2b939f56ca` |
| `browse.prg` | 3,418 | `4ad53ec06a051029e72ffeed374922dcfa205fde24fd2f9c432ef0fe1bae334f` |
| `editor.prg` | 10,199 | `87b8786f05edef1c06d3983f116d5d97805e4201bc0b0bc461bf216378712ba1` |
| `uos128.d64` | 174,848 | `196761f58a56fe328ac4eca9fe7b3530eff2b38e7f3706393c58586c7d96e020` |

The kernel, boot, calculator and browser PRGs match that reference exactly.
EDITOR occupies `$6000..$87d4`, with a 10,197-byte payload and a 40-page
application allocation. The kernel's 442 managed pages, public entry table,
mailboxes and relocated resident code are unchanged. The stock D64 adds EDITOR.

The [isolated package check](package/report.json) rebuilt six identical images,
checked layout/public jumps/BAM/boot-sector reservation, and independently
extracted all four disk PRGs. All 18 legacy images match the preceding commit.
[verify.py](package/verify.py) builds copied source in a fresh directory without
rebuilding the working tree. [document.prg](document.prg) is the standalone
CPU document probe assembled with `64tass -a -B` from the same document module.

## CPU qualification

| Report | Coverage |
|---|---|
| [Document model](cpu-document.json) | Four groups: byte-preserving edits, bounds/EOF, IRQ interleaving, overlapping gap moves, independent random edits, both banks and two contexts, offsets beyond 64 KiB, allocation-failure preservation, transfer poisoning and cleanup retry |
| [Editor](cpu-editor.json) | Nine groups: typing/navigation/prompts, quoted text, mixed newlines, empty files, long-line/viewport/column behavior, cancellation/read failure, failed verification, existing-file refusal, two uncertain-CLOSE quarantine paths, device 9 across all three formats, 66 KB edit/save/reopen and out-of-memory Open preservation |
| [Calculator](cpu-calc.json) | Shared input-harness regression: arithmetic/errors, history, screens, file export and cleanup |
| [Browser](cpu-browser.json) | Eight shared-harness workflows, complete screens, previews, directory capacity and app handoff |

The document model reconstructs bytes independently from handle records and
bank RAM. The editor model compares complete screens with a separate layout
oracle and verifies stored bytes. Its ROM console model checks quote state;
real-ROM checks below cover actual CHROUT and GETIN behavior. Every editor
instance starts with a custom function-key table and checks exact restoration
on normal or quarantined exit.

The [earlier CPU harness failure](cpu-initial-harness-failure/report.json)
identified the calculator model's assumption that an empty GETIN always meant
the app was ready. The editor also polls GETIN while busy to support cancellation.
The harness now permits that behavior only when a client explicitly opts in;
calculator and browser checks retain their strict default. This historical
report uses an earlier editor image and is not a passing current-image result.

The saved large-file SHA-256 is
`4bfb7babf2cd4195f0735e5a935943d0faa0d77bc2c1f17b502d9bf78fb35051`.
A failed Open leaves the old document/cursor/dirty state intact. A failed or
uncertain Save As does not clear dirty state. An uncertain CLOSE can quarantine
the owner and all its RAM; general media-error recovery remains open.

## Emulator qualification

| Workflow | Recorded result |
|---|---|
| [D64 / true 1541 editor](emulator-editor-d64/report.json) | Browser discovery, ROM function-key expansion, 18 complete VIC/VDC frame pairs, mixed/empty input, edit above 64 KiB, verified save, existing-name refusal, New/reopen, browser return, complete cleanup |
| [D71 / true 1571 editor](emulator-editor-d71/report.json) | Boot disk on IEC 8, data on IEC 9; same document checks and preserved browser device/format |
| [D81 / true 1581 editor](emulator-editor-d81/report.json) | Same data-device workflow, independent saved-byte extraction and cleanup |
| [Workspace/calculator](emulator-workspace/report.json) | Cold boot, two 8 KiB allocations, calculator/history export and complete release |
| [D64 browser](emulator-browser-d64/report.json), [D71 browser](emulator-browser-d71/report.json), [D81 browser](emulator-browser-d81/report.json) | Existing discovery, byte preview, rejected app, renamed calculator launch/export/return and ownership checks with EDITOR also packaged |

The [initial D64 run](regressions-editor-d64/report.json) and
[six-suite follow-up](regressions-followup/report.json) passed before metadata
checks moved to CPU snapshots. Their three editor runs are retained in the
`emulator-editor-*-initial` directories. The
[three-suite observation follow-up](regressions-cpu-observation/report.json)
uses explicit CPU snapshots of the saved key table and both editor/document
state for every checked frame. Product images stayed fixed across all ten
emulator runs. The final editor runs each contain 54 restored captures and
116 bounded IRQ chunks. No emulator run is a physical keyboard-switch test;
function keys are supplied through the real ROM's pending expansion state.

## Hardware qualification

The [physical report](hardware/report.json) passed on the reference C128 and
Ultimate II+ at `192.0.2.237`, with a private D64 on drive A/IEC 8 in 1541 mode.
It verifies all 18 VIC/VDC frame pairs and 33 CPU memory snapshots, using 54
restored captures and 116 IRQ chunks of at most 512 bytes each. CPU capture
matched the complete 1,280-byte boot relocation. Both unrelated 8 KiB workspace
allocations passed the native verifier after application exit; independent
2,000-byte prefixes also matched. All 442 pages and 32 handles were free again.

The closed private disk was read back in full through Ultimate DOS, after the
legacy desktop had been restored. Independent sector-chain extraction verified
all eight files, and c1541 separately extracted all seven nonempty files. NOTE,
EMPTY, LARGE and the four packaged PRGs were unchanged. SAVED contains exactly
the expected 66,056 bytes; EMPTY has zero stored bytes and the native boot sector
is intact. The complete 174,848-byte disk SHA-256 is
`e43e485952343ad17822801e4c516f3400ad583f2166c8b98346aaa0d35f3d9a`.

All original function-key bytes, legacy settings bytes and both Ultimate DOS
working paths were restored. Other drive configurations were unchanged, and the
legacy desktop was live after readback. The test used 60-second boot quiet
intervals, 4-second key intervals, 30-second initial waits for file/app operations,
2-second polling and a 1,800-second operation limit. The measured initial large
Open was 295.976 seconds, verified Save As 523.278 seconds, and subsequent
reopen 289.889 seconds. These are harness observation windows, not a throughput
benchmark. Standard IEC performance and blocking extent/KERNAL calls remain
limitations; native Ultimate storage and faster/cancellable I/O are still needed.

This hardware result covers the reference machine and Ultimate's 1541 drive
mode. D71/1571 and D81/1581 editor workflows are emulator-qualified here;
physical drive-family coverage remains on the broader roadmap.

## Initial hardware observation and recovery

The [first physical attempt](hardware-initial-failed/report.json) stopped while
decoding a direct DMA observation of the editor's filename after Go To. It
retains the exact image and host helper snapshots. Its saved VIC screen
[compares exactly](hardware-initial-failed/diagnostic-screen.json) with the
intended byte-5 cursor position and NOTE document. That screen alone does not
prove the rest of the interrupted workflow. The retry captures application
state through the CPU and archives the corresponding direct DMA bytes for
comparison; no product image was changed for this retry.

The retry captured a complete 109-byte direct snapshot from `$806f` that
matched the corresponding bytes of Commodore BASIC ROM `318019-04`. Its CPU
snapshot and both screens matched the intended empty document. This confirms
that a direct cartridge observation can see ROM at an application RAM address.
The [ROM comparison](rom-observations.json) records the exact ROM hashes and
saved observation ranges. `python3 verify-rom-observations.py /usr/share/vice/C128`
repeats that comparison with installed reference ROMs; the ROM images themselves
are not included in this archive.

The restore attempt also exposed a harness assumption: the larger native app
uses the inactive legacy record at `$7350`. Legacy boot reinitialized the active
settings fields but left the record header/reserved bytes from native app RAM.
The [read-only diagnosis](hardware-recovery-observations/report.json) confirmed
a live legacy desktop with matching active fields. The
[bounded recovery](hardware-initial-failed/settings-recovery.json) restored all
nine saved bytes. The revised harness explicitly performs this restoration
only after the legacy desktop is live and its active settings fields match.
The initial failed report remains failed and is not used as passing evidence.
