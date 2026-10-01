# Native input diagnostic — 2026-09-12

The bounded physical diagnostic failed. It recorded six ROM key-check calls,
each followed by native consumption, while the first CPU memory capture ran.
The input signal's source remains unknown. Separately, high-memory host
readback matched BASIC ROM, so this diagnostic cannot verify its borrowed
high RAM on the physical machine. The original desktop, drives, settings and
DOS paths were restored, and both owned uploads were verified and removed.

This record preserves the failure. It does not qualify native Claude, the
Ultimate panel, or this diagnostic's high-memory host access for normal use.
The frozen runner has already run; do not reuse it for another physical attempt.

## Candidate and software checks

`inputs/` contains 395 frozen files: 386 unchanged inputs from signed commit
`81a21418a0a5bde52f78935945bbce514d6ff7ae` and nine diagnostic files.
`frozen-inputs.json` has SHA-256
`118d47233058691004caff10db22a38768098ca6aab7815b38a683db96df10f1`.
The suite disk and kernel are unchanged from the five-app lifecycle candidate.

The diagnostic temporarily leases eight otherwise free bank-0 pages at
`$5000..$57ff`, a low mapping gate at `$3fc0`, and the native input and ROM
key-check vectors. It records scan and consumption state in separate scratch
areas. It retains the first 20 records and a saturating overflow count. Native
GETIN still consumes and counts keys, but the wrapper returns zero to keep the
desktop from acting on them. The allocation map must remain unchanged.
The logger samples CIA ports and directions; it does not read CIA interrupt
status or write the CIA. The original ROM callback performs its normal writes.

Three CPU groups pass: native/ROM normal and function-key consumption;
register, stack, flag and `$00/$0e` mapping preservation; and interleaved
producer/consumer recording with bounded overflow. Four host fault controls
cover successful restoration, occupied-page refusal, partial writes and raw
corrupt-journal retention. These software models did not cover mapped BASIC
ROM appearing in a paused host read.

`vice/` retains the final emulator pass. Actual X keyboard events produce
dedicated Down scans (index 84), followed by native consumption. Input during
an observation causes the expected strict metadata rejection. An explicit
host-buffer `P` produces a consumption record without a scan record. Hook,
borrowed-memory and resident restoration pass, and an ordinary Down key after
detach changes desktop selection. `vice/shared/` exercises the complete
shared diagnostic workflow. The emulator fixture temporarily disables ROM
key repeat for synthetic input under warp; the physical workflow does not.

## Physical observations

`hardware-failed/` is the complete terminal work directory for
`uos-hardware-native-transport-_lkgq2n4`. Its process exited with failure.

| Phase | Observed scan and consumption records |
|---|---|
| 30 seconds idle, no host requests | None |
| Twelve pause/read/resume batches | None |
| First 2,000-byte CPU RAM capture | Four Down (`$11`, index 7), then two Insert (`$94`, index 89) |

Each scan has zero modifier flags and no function-key queue. Each is followed
by a matching consumption record; `N_KEYS` advances from zero to six.
The first capture rejects exactly the changes in `N_KEYS` and `N_LASTKEY`.
Its output, scratch and low resident bytes match their saved originals.
The journal's hold kept the desktop selection unchanged. No failed payload
was replaced, accepted on retry, or exempted from the strict comparison.

The Insert scans sampled CIA port A and extended keyboard lines at `$ff`,
port B at `$fd`, and data directions A=`$ff`, B=`$00`. These are callback-time
samples, not a complete electrical trace. The observations do not identify
a physical key, attached device, firmware, or pause/capture transport as the
initiating cause.

The pinned [C128 key table](https://github.com/mist64/cbmsrc/blob/01bd60f162ef92212ef0cb67546ae8f42be34168/EDITOR_C128/ed7.src)
starts at `$fa80`, matching the recorded table pointer. It has 88 key indices
and an `$ff` sentinel at index 88. Index 89 reaches the following shifted
table's first byte, `$94`. The retained source excerpt matches the local
VICE ROM. This correlates the observed value with an out-of-table index;
it does not establish why that index was produced or identify the entire
physical ROM. `keyboard-correlation.json` records the pins and excerpts.

## High-memory read limitation and restoration

Pause batch 9 returned 15 BASIC bytes instead of the journal header at
`$5200`. Later, the entire 2,048-byte read at `$5000` after acknowledged
restoration writes matched local BASIC-low ROM at offset `$1000` exactly.
It differed from the saved high RAM at 2,017 offsets. The full first readback
is retained, along with the matching reference and `rom-correlation.json`.

This supports a mapped-ROM host-read interpretation. It cannot establish
whether the underlying borrowed RAM was restored or corrupted. Hook detach
readbacks passed before this failure; the low gate restoration also matched.
The high-page failure leaves `input_trace.restored` false. Its exception is
retained alongside the earlier capture rejection. A future diagnostic needs
CPU-controlled bank access or another qualified mapping method for high RAM,
including initial backup and final restoration verification.

The parent restoration completed independently: original drive A
`/Temp/temp0098`, unmounted B, both DOS paths, saved settings
`507302f0a502030000`, and controls. The 174,848-byte disk `/Temp/temp00B1` and
2,036-byte restore program were fully read back, verified, deleted and
confirmed absent. There were no uncertain host writes or cleanup errors.
No modem configuration or Claude authentication/model request was performed.

## Offline audit

```sh
python3 -B docs/validation/2026-09-12-native-input-trace/verify.py
```

The audit verifies the seal, all frozen inputs, raw journals, capture chunks,
borrower comparisons, the exact physical rejection, ROM correlations and
restoration/cleanup receipts. It does not connect to hardware or rerun the
diagnostic. Passing the archive audit means the retained evidence is
consistent; the physical diagnostic remains failed.
