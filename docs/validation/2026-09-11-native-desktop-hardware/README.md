# Native desktop hardware qualification preparation

Three physical attempts remain incomplete. The first timed out in the legacy
preflight before native boot. The second verified three native desktop views,
Calculator and Editor, then failed a strict observer metadata comparison.
Every attempt restored the original deployment. Both later attempts' temporary
uploads were independently read back and removed. This archive retains the
failures, recovery, frozen candidates and five completed VICE preflights.
The [software integration](../2026-09-12-native-desktop-integration/README.md)
is separate; complete physical desktop qualification is not established.

The prepared disk and all six app/kernel files extracted from it match the
[sealed launcher checkpoint](../2026-09-11-native-desktop-launcher/README.md).
The preparation builder reproduces that disk exactly and generates the complete
layout for the direct desktop boot kernel. Its main section ends at `$37f8`,
low section at `$1bf0`, service section at `$4ff9` and load image at `$5900`.
There are 383 frozen inputs and 27 unchanged native/legacy program/disk images.
`BROWSE` on this disk is the graphical launcher; `FILES` is the standalone file
browser. The separately retained `browse.prg` is still the original text browser.

## Completed preflight

* The original CPU observer captures all 9,216 VIC surface bytes and 2,000 VDC
  cells while graphics is active. Borrowed RAM, the IRQ vector and foreground
  state are restored. Both full rendered frames match before and after observation.
* A running-code audit accompanies the full desktop/app/fallback workflow.
  It compares 11,971 immutable bytes across all three resident sections at boot
  and after the workflow. All 1,581 declared data/address-operand bytes are
  retained in full; their values are not required to equal untouched boot bytes.
  Opcode bytes, constant tables and padding remain checked. Nine offline
  controls include corrupted opcodes beside mutable operands, altered command
  separators and service-buffer padding. The full workflow passes unchanged.
* The exact proposed hardware native sequence also passes in VICE, through
  the shared `run_native_workflow` function. Five complete desktop views match
  their bitmap/VDC oracles and mode-register checks. Calculator produces 42,
  Editor receives and discards `C128`, Files returns to the desktop, and Escape
  returns to a workspace with all 426 pages and 32 handles free. This sequence
  makes 60 CPU captures in 209 IRQ chunks, retaining 101,184 bytes and six
  complete app/workspace screen pairs.

Together the three preflight runs retain 84 CPU captures, 290 IRQ chunks and
139,504 captured bytes. The first two workflows also verify 768,000 rendered
VICE pixels. These are emulator results; no physical video pixels are captured
by the prepared hardware sequence.

The first running-code audit rejected seven legitimate changes from an omitted
file-extent include: two decimal command digits and five state bytes. The
original audit and failed capture are retained under `history/layout-initial`.
The writer instructions were traced before adding their explicit mutable
locations. No kernel or desktop image was changed to satisfy that audit.
`history/before-shared-workflow` retains the earlier harness and manifest from
before extracting the common native sequence. Neither earlier preparation was
used for physical qualification.

## First physical preflight and recovery

`history/physical-preflight-v1` retains the attempt, two DMA observations,
failed tick restoration, eight CPU IRQ PC samples and successful original-loader
reload. The pending first command was `01 07`; its entry/end/done markers were
untouched. The CPU remained in the legacy `$0dcb` error loop with the displayed
address `4FFF`. The initiating cause is unproven. Native desktop code never ran.
The reload used the exact original 2,036-byte loader once, without replaying the
cartridge command. Original settings, drives and desktop dispatch were verified.
Recovery did not freshly query DOS paths.

The initial DMA observation read `$df1b..$df20`, including the empty UCI FIFO
registers. Later observers read only the status register. The archived current
recovery source records this change; it is not claimed to be the original
source of the first observation. CPU IRQ captures also show why DMA reads of
the processor's on-chip `$00/$01` registers cannot qualify display banking.

`v2` freezes 385 inputs, adding a separate CPU mode-register observer and
preflight command/error journaling. Its shared native workflow passes unchanged
in VICE: 66 captures, 215 IRQ chunks and 101,274 bytes, including six fixed
15-byte mode snapshots. It rebuilds all 27 images exactly. The new observer
corrects the physical banking measurement; it is not a claimed fix for the
earlier legacy panic. The V1 inputs and evidence remain intact.

The V2 attempt is retained in `v2/hardware-failed`. Its 42 CPU captures contain
67,245 bytes, including the full three desktop surfaces and four app screen
pairs. After Editor returned, 8,000 bitmap bytes matched before the observer's
host-read metadata comparison failed. The differing metadata bytes were not
saved by that observer, so the cause cannot be classified. The check was not
ignored. The harness restored the original desktop; separate guarded cleanup
verified and reclaimed the 174,848-byte disk and 2,036-byte loader, then checked
the original settings, drives, DOS paths and desktop dispatch.

`v3` freezes 386 inputs and retains all before/after borrower observations.
It preserves the same comparisons and OS images. Five offline controls cover
normal restoration and injected bad reads of each borrowed region; every bad
read still fails with its exact differing byte retained. The complete VICE
sequence passes with 264 before/after pairs (642,048 host-observed bytes) in
addition to its 101,274 CPU-captured bytes. This supplies missing diagnostic
evidence; it does not establish or fix the V2 failure's cause.

The V3 physical run also stopped and is retained in `v3/hardware-failed`.
The original 512-byte output-buffer snapshot agreed with its independent
copy inside the pre-capture metadata snapshot. After restoration, offsets
201, 209, 217, 225, 233, 241 and 249 read as zero instead of `$ff`. The final
464-byte capture chunk also contained 71 bytes that differed from the surface
oracle. The first three chunks matched. These observations are retained
without accepting a later reread as a passed capture. They do not prove whether
the underlying fault was in the observer, host transfer or native RAM.
The original desktop/settings/drives were restored; separate guarded cleanup
verified and removed `/Temp/temp00AC` and its owned recovery loader and checked
both DOS paths. No private uploads from these attempts remain.

## Reproduction and pending physical work

These commands rebuild or read the archived inputs without hardware access:

```sh
python3 -B verify-inputs.py
python3 -B verify-observers.py
python3 -B verify-sequence.py
python3 -B verify-preflight-recovery.py
python3 -B verify-v2-failure.py
python3 -B verify-v3-failure.py
python3 -B v2/verify-inputs.py
python3 -B v2/verify-sequence.py
python3 -B v3/verify-inputs.py
python3 -B v3/verify-sequence.py
```

The last physical command is recorded in `v3/candidate-context.json`. All
restoration and cleanup work is complete. A focused capture-transport
investigation must precede another full desktop run. The harness mounts a private read-only disk,
performs the qualified native sequence, restores the original disk/settings/DOS
paths, independently reads back its two temporary uploads, and removes only
those verified, unmounted files. A failed or uncertain run must retain its
report and resource identities for recovery.

Future hardware results need a new frozen version and archive. Do not overwrite
these failed attempts or present them as a passing full sequence. Actual physical video output, pointer
input, overlapping windows, VDC bitmap mode and full Ultimate panels remain
separate work.
