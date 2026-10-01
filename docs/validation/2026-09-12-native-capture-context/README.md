# Native capture context qualification — 2026-09-12

The corrected private observer passes CPU and host controls, a focused VICE
sequence, and forced nested RAM/VDC captures with complete foreground returns.
The physical experiment remains a failure: its boot display payloads matched,
but the strict metadata comparison rejected three changed ABI bytes. Original
deployment restoration and removal of both owned temporary files completed.

A later controlled VICE experiment reproduces the exact three-byte pattern
with two cursor-down events. The source of the physical input remains
unconfirmed, and the earlier desktop payload/output-buffer differences remain
unexplained. This archive does not qualify the complete physical desktop/app
workflow.

## Inputs and software evidence

`frozen-inputs.json` pins 345 files, including the private capture/transport
helpers, all native images and the unchanged probe. The manifest SHA-256 is
`0f67b314fa7dcf806ac81140f100cac47e11f647351c69ee4f9eda352152706f`.
All predecessor `src/`, `target/` and `probes/` identities are preserved.
The files in `inputs/` remain the exact physical experiment inputs.

The observer accepts interrupted mappings `$0e` and `$00`, retains the first
raw status and payload bytes, and preserves strict borrower comparisons.
The historical `foreground_mmu` field is the interrupted context's mapping.
Bad mode/common-memory settings and unsupported mappings still fail.

| Evidence | Result and scope |
|---|---|
| `host-controls/` | 48 CPU/probe cases and 60 host controls pass; host controls model exchanges and failures separately from CPU execution |
| `emulator-focused/` | 27 captures, 35,726 payload bytes, 76 raw status records, 234 completed pause batches; boot and selected-surface samples match |
| `emulator-nested/` | Forced nested RAM and VDC captures each save `$00`; both return through the real ROM to the foreground with the original stack pointer and `$0e` mapping |
| `cbmsrc-reference/` | 70 assembled bytes from two pinned Commodore source excerpts match the local 318020-05 ROM |
| `emulator-input/` | Two injected cursor-down events reproduce all three physical ABI differences and cause the unchanged strict observer to reject the capture |

The nested VICE test retains complete stack frames and captured bytes. Both
64000-pixel desktop images match before/after, including their full VIC surface
and VDC controls. Its temporary RAM trampoline is used only in VICE. Four
earlier checkpoint-harness attempts remain in `emulator-harness-history/`;
they are failures, not qualification results. Persistent checkpoints with
explicit deletion resolved the missed-stop behavior in this harness.

The [Commodore reference note](../../COMMODORE-SOURCE-REFERENCE.md) pins the
user-provided `mist64/cbmsrc` checkout. Its IRQ dispatcher saves the current
mapping, selects `$00`, and restores the saved mapping on return. Its editor
executes `CLI` before scanning keys. The excerpt comparison uses explicit
external symbol addresses; it is not a complete ROM rebuild or an identification
of the ROM installed in the physical machine.

## Physical attempt

`hardware/` retains the terminal evidence from
`uos-hardware-native-transport-pa7jeyun`. `physical-attempt.json` records one
invocation and terminal failure. No physical process remains active.

The attempt captured 24,783 payload bytes in 53 chunks, with all 636 raw status
bytes retained. These comprise the 13,552-byte resident audit, the 15-byte mode
snapshot, all 9,216 VIC surface bytes and all 2,000 VDC cells. The resident
audit accepted 11,971 immutable bytes and 1,581 declared mutable bytes. Every
boot display payload matched its independent oracle. One resident chunk saved
MMU `$00`; the other 52 chunks saved `$0e`. No mapping guard failed.

The final VDC payload was saved before the restoration comparison failed.
Fifteen of sixteen capture records completed all borrower checks. Of 63
retained before/after pairs, 62 match and one metadata pair differs; the
comparison stopped before reading the final resident-after snapshot. The raw
borrower observations total 153,344 bytes. A false `restored` flag therefore
remains on the final capture even though output/probe restoration readbacks
match and the later original-deployment recovery completed.

| Address | Declared field | Before | After |
|---|---|---|---|
| `$3d0c` | `N_VALUE`, fill argument | `$1b` | `$07` |
| `$3d13` | Low byte of `N_KEYS` | `$00` | `$02` |
| `$3d15` | `N_LASTKEY` | `$00` | `$11` |

The high byte of `N_KEYS` stays zero. The allocator tables at `$3800..$39ff`
and the rest of the observed metadata match. The before/after metadata files
were recorded at approximately 12:16:54–12:17:05 Eastern. These are host
observations; the physical origin of the changes is not independently proven.
The error text “native heap changed during observation” covers the entire
metadata/ABI snapshot and does not by itself establish allocator corruption.

All 154 pause batches have acknowledged resumes. All 940 RAM writes have exact
inclusive-range acknowledgements, with no uncertain sent writes or replay.
One TCP connection timed out before any request was sent; reconnecting then
succeeded. That pre-send connection retry is retained in the report and stdout.
The API version response is `0.1`; it does not identify the installed firmware
build.

The original legacy desktop, drive A `/Temp/temp0098`, empty drive B, nine
settings bytes `507302f0a502030000`, DOS paths and borrowed controls were
restored and liveness checked. The owned native disk `/Temp/temp00AE` and
2036-byte private recovery loader were completely read back, compared against
their input images, deleted, and confirmed absent. Total readback was 176,884
bytes. `cleanup_complete` is true and both deletion records are confirmed.

## Controlled input explanation

The `input-control-manifest.json` resolves 346 files from `inputs/` plus two
files in `input-control-overlays/`. The original observer, probe, kernel and
apps are unchanged. The test injects two cursor-down events after the last
VDC payload is read and before borrower restoration. It reproduces all three
physical ABI differences exactly, retains the original VDC payload, and
requires the capture to fail.

The before/after desktops match 128,000 rendered pixels and their complete
VIC/VDC images, ending with Files selected. An independent low-resident read
finds only the declared `hbyte` scratch value at `$17d0` changing from `$1b`
to `$07`, as expected from redraw fill calls. The immutable bytes match.
The first control attempt incorrectly required this mutable scratch byte to
remain unchanged; its failing run and original helper remain in
`input-control-history/`. The revised control checks the exact declared change.

This establishes that normal input can produce the observed pattern; it does
not establish who or what generated input on the physical C128. The strict
observation boundary remains necessary because the foreground can change
between captures.

## Verification and next work

Run the read-only archive auditors from the repository root:

```sh
python3 -B docs/validation/2026-09-12-native-capture-context/verify-software.py
python3 -B docs/validation/2026-09-12-native-capture-context/verify-hardware.py
python3 -B docs/validation/2026-09-12-native-capture-context/verify-input-control.py
```

An auditor PASS verifies the retained evidence; the physical workflow's result
remains FAIL. `SHA256SUMS` seals every archive file except the manifest itself.
The source-correlation replay command is in the linked reference note.

Next integrate the qualified interrupted-mapping/raw-evidence changes and
describe input/ABI failures accurately, preserving strict comparisons. Before
another complete physical workflow, carry the pause context into its mode
capture too and qualify the combined app sequence in VICE. Investigate physical
input provenance and retain all prior transport failures. Full desktop/app
hardware qualification and the larger OS roadmap remain open.
