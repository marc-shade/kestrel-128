# Integrated native observer — 2026-09-12

The production observer now accepts the two qualified native interrupted
mappings, retains raw status/payload files, and records every completed first
borrower readback before rejecting differences. Input-field changes name
`N_VALUE`, `N_KEYS` and `N_LASTKEY`; the report retains their before/after
values without inferring the physical source of input. Short and differing
readbacks still fail. No matching reread can replace a failed observation.

The `--native-desktop` hardware entry now selects exact RAM-write receipts and
bounded pause/resume batches. Its mode snapshots inherit the same pause
context as RAM/VDC captures, and scripted key injection runs in one batch.
A capture failure returns after original-deployment restoration and verified
temporary-file cleanup. A failed restoration or file readback retains the
resources needed for recovery.

All 15 integrated helper/test sources are copied in `overlays/` and hashed in
`source-manifest.json`. The preceding
[context archive](../2026-09-12-native-capture-context/README.md) supplies the
unchanged source, probe and image inputs named by
`unchanged-images-and-sources.json`. No native kernel, app, disk or probe
binary changes in this checkpoint.

| Validation | Result |
|---|---|
| Native CPU/probe cases | 48 pass, including both banks, VDC faults and interrupted mappings |
| Host controls | 54 pass: 33 transport, 10 status/length, 7 borrower and 4 lifecycle cases |
| Complete shared desktop/app sequence | 66 captures, 101,274 payload bytes, 2,580 status bytes, 647 pause batches, 19 keys; Calculator, Editor, Files and all returns pass |
| Forced nested IRQs | RAM/VDC captures save `$00` and return through both IRQ frames to the original `$0e` foreground and stack pointer |
| Input during capture | Two cursor-down events reproduce the prior three ABI differences; the strict observer rejects them and also retains the first resident-after snapshot |

Every mode capture in the full sequence has matching pause-batch records.
Both running-resident audits pass and all 66 borrower records restore exactly.
The input experiment now retains the declared fill scratch byte at `$17d0`
changing from `$1b` to `$07`, alongside the three ABI changes. Both rendered
desktop states and all immutable low-resident bytes match. The nested and
input tests each check 128,000 rendered pixels.

These are CPU, host-model and VICE results. No new physical attempt was made
for this integration. The previous physical failures remain retained, with
their original-deployment restoration and cleanup verified. Full physical
desktop qualification remains open.

Run the archive auditor with:

```sh
python3 -B docs/validation/2026-09-12-native-observer-integration/verify.py
```

The integrated emulator entries are `nativedesktopsequence`,
`nativecapturetransport`, `nativecapturenested` and `nativecaptureinput` in
`tests/run_ci.py`. Replay creates fresh reports; preserve this sealed archive.
`SHA256SUMS` covers every payload file, including the source overlays.
