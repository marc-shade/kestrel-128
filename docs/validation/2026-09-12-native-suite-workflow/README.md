# Native five-app suite workflow — 2026-09-12

The shared workflow passes in VICE from the main checkout. Calculator, Editor,
Files, Ultimate and Claude return through the native dispatcher, including two
Claude serial sessions. The physical attempt failed during initial resident
verification, before scripted input or either added app. Restoration and owned
file cleanup completed. This record does **not** qualify physical Claude or
Ultimate app operation.

## Inputs and software results

The kernel and app images are unchanged from signed commit
`c5f8e44242fa2e3d1a2ac0f9666463a23b81c55a`. `inputs/` retains 387 frozen files:
383 base inputs, one modified hardware harness, and four added files. The
integrated files are `hw_native_desktop_check.py`, `native_suite_workflow.py`,
`tests/ci_native_suite_iec.py` and `tests/ci_native_suite_oracles.py`.
`run-hardware.py` is the private runner for the already completed attempt.

| Image | SHA-256 |
|---|---|
| Suite D64 | `9809bace09b871d31a6ccd82d48d99086d5f2fbaf9953cb1eb9f177cc072cdcf` |
| Kernel PRG | `1ac2547dff0ebeb1306bb12ba0a2baa59026d1f912a195e72b0bca1acaed49ed` |
| Claude PRG | `b4367aed8d97c772fabe62ed595d24dcc6052198579ac197c536d3969d907912` |

The shared test adds Ultimate identification, drive, network and clock pages,
then two Claude sessions to the existing Calculator/Editor/Files workflow.
Independent raw query replies supply the panel expectations. The physical
preflight uses the existing legacy transport; VICE uses an absent-cartridge
reference. Three CPU test groups cover successful, partial, malformed and
unsupported replies, plus independent RTC time bounds and refresh behavior.
The emulator's absent-device checks do not establish successful physical UCI
operation in the native app.

`vice/` retains the final main-checkout pass: 126 memory captures and nine mode
captures, 403 IRQ chunks, 183,385 payload bytes, 540 matching borrower pairs,
eight full desktop comparisons, both resident-code comparisons and final
426-page recovery. All bridge processes and the emulator terminated.
`main-oracles.json` retains the three passing CPU reference groups.
`suite-oracles.json` is the earlier identical-source private CPU pass.

Claude sessions use the fixed `tests/fixtures/claude-session.py` PTY program.
They verify custom glyphs, typed input, Escape, Help repaint, acknowledged F8,
host-process exit, restored 4,096-byte font, NMI vector and resident NMI pointer.
The serial receive counters report no drops or overruns. A foreground VDC
mirror and settled output protect display observation from concurrent drawing.
No Claude authentication or model request is exercised.

Run the current shared software checks from the repository root:

```sh
python3 -u tests/ci_native_suite_iec.py
python3 -B tests/ci_native_suite_oracles.py --report /tmp/native-suite-oracles.json
```

The first command requires VICE, Xvfb and the bridge dependencies. The second
requires py65. These are software tests and do not connect to the physical
cartridge. Hardware boot/restoration remains owned by a separately frozen
runner with explicit expected image hashes.

## Physical attempt and diagnosis

`hardware-failed/` retains the complete terminal work directory from
`uos-hardware-native-desktop-40g5lqpe`. `physical-attempt.json` records exit
failure and terminal host processes. The source manifest digest was
`94525454c427f8a3f486d3b01c86038e44f2344d49bd269c2d2118b596acbd8b`.

Before native boot, legacy queries returned model `1541 ULTIMATE II`, control
and network identities, two drive records in a four-record declaration, one
network interface with IP/mask/gateway, and a valid RTC string. Raw replies,
status, clipping flags and monotonic time bounds are retained in the report.
These are reference replies, not native app results or proof of the installed
board/firmware identity.

The fifth capture, `resident-boot-main-0fa0`, was rejected during borrower
comparison. Its four chunks completed and retained their first payloads.
The output and scratch buffers matched their originals after restoration.
Metadata and resident drawing state changed while the observer ran:

| Address | Observation |
|---|---|
| `$3d13..$3d14` | Consumed-input count 0 → 3 |
| `$3d15` | Last input 0 → `$11` (cursor down) |
| `$3d2f` | Desktop selection 0 → 3 |
| `$3d11/$3d12` | Idle/ready → busy/not ready |
| `$1719`, `$172b` | Declared heap transfer address operands changed |
| `$17cb`, `$17cd`, `$17cf` | Declared heap address, remaining count and bound state changed |

The last key and selection are consistent with cursor navigation. Only the
last key is retained; the record does not establish all three input values.
Every changed resident byte belongs to an existing mutable declaration.
The before/after resident snapshots match the pinned image outside those
declarations. The available CPU captures likewise match all 8,112 captured
immutable bytes. These partial captures do not replace the full resident
qualification that failed to finish.

There were no scripted input events and none of the 802 acknowledged RAM
writes overlap the normal/function-key queue counts, function-key index or
keyboard buffer. The input origin remains unestablished. The evidence does
not identify physical keys, an attached input device, another writer, ROM
scanning or the pause/capture transport as the cause. The strict rejection is
preserved; no mismatch was masked, replaced or accepted on retry.

Before another complete hardware run, use a bounded input diagnostic that
retains KERNAL scan/last-key state, modifier and function-key queue state at
input consumption, with timestamps for pause/resume and probe activity.
Compare an idle interval with a capture interval, restoring any diagnostic
hook and preserving the first event. The present record lacks those inputs
and cannot resolve the source retrospectively. A fresh candidate is required
for any further physical attempt.

## Restoration and limits

The original A image `/Temp/temp0098`, unmounted B, both DOS paths, nine saved
desktop settings bytes and controls were restored. Runtime restoration checks
passed. Both owned uploads were fully read back, compared and deleted with
absence confirmed: the 174,848-byte suite disk `/Temp/temp00B0` and the
2,036-byte restore program. There were no uncertain host writes and no cleanup
error. The report retains readback hashes and deletion confirmations; the
original settings and uploaded restore-program bytes are also retained.

The frozen runner's final modem comparison followed its success return and
was skipped when the native error was rethrown. Separate terminal GETs in
`modem-final-0.json` through `modem-final-3.json` close that observation gap:
DE00/NMI, port 3000, DTR disconnect and incoming RING match preflight.
No modem configuration write was issued.

The physical machine was restored after the failed check. The new native
apps, a live authenticated Claude session, physical video pixels and the
broader desktop/expansion roadmap remain unqualified by this record.

## Offline audit

```sh
python3 -B docs/validation/2026-09-12-native-suite-workflow/verify.py
```

The audit verifies the seal, frozen inputs, raw captures/status and borrower
pairs, full VICE desktop surfaces, terminal/font/NMI results, resident images,
final heap, exact rejected physical changes, write receipt ranges, restoration
records and final modem GETs. It performs no network or hardware operation.
`audit.json` records the result; `SHA256SUMS` seals all retained payloads.
