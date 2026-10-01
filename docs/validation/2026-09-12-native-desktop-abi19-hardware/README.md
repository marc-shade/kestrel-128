# Native desktop ABI 1.9: complete physical qualification

The full desktop workflow passed on the C128 using the exact signed
`a90fadfb484e54aedfd446ccd07da3d4365e8182` images and the integrated observer.
This is the first complete physical pass of this desktop sequence. The original
legacy desktop, drives, settings, DOS paths and borrowed controls were restored;
both private uploads were completely read back and deleted, with absence
confirmed. No recovery resources remain from this attempt.

The workflow verifies native boot, keyboard selection, Calculator
`12+30=42`, Editor `C128` text and confirmed discard, Files, retained selection
on app return, the final workspace and all 426 heap pages released. Five complete
VIC surfaces and their VDC companion screens match the independent oracles.
Resident code checks pass before and after the app sequence.

| Retained evidence | Result |
|---|---|
| Frozen inputs | 348 files, all original hashes match |
| Native captures | 60 data captures plus six mode snapshots |
| CPU payload | 101,274 bytes in 215 chunks |
| Raw observer status | 2,580 bytes; 203 interrupted mappings `$0e`, 12 mappings `$00` |
| Borrower checks | 264 matching before/after pairs, 642,048 bytes retained |
| Pause batches | 647; every pause and compensating resume acknowledged |
| RAM writes across the full lifecycle | 1,906 exact range receipts, no replay or uncertain write |
| Scripted keys | 19 |
| Running kernel | 11,971 immutable bytes plus 1,581 explicitly mutable bytes, captured twice |
| Temporary files | 174,848-byte native D64 and 2,036-byte restoration loader; full readback and confirmed deletion |
| Connection failures | None |

The desktop selections were `0, 1, 0, 1, 2`. Every complete capture restored
its output buffer, scratch space, metadata/ABI and low resident bytes. The
final CPU mode snapshot shows text restored with processor port `$73`, and
the allocation records have no remaining app or surface owner.

This qualification uses CPU-captured physical RAM and display-mode registers.
It does not capture the physical video signal or establish a cartridge firmware
build identity: `ultimate-version.json` records REST API version `0.1`.
The preceding [software checkpoint](../2026-09-12-native-desktop-selection/README.md)
retains the six VICE workflows and their complete rendered-pixel comparisons.
The prior failed physical attempts remain preserved in their separate archives;
their unexplained payload/buffer differences and input source remain unresolved.

`hardware/report.json` contains the complete lifecycle. `inputs/` is the frozen
source and image tree; `frozen-inputs.json`, `physical-attempt.json` and
`physical-stdout.log` identify the single invocation and terminal result.
The frozen manifest hash is
`da468070c73d9842e0157e23279fde4a8d4978f6f8d4339401e10cd0183f1c48`.

The original drive A image was `/Temp/temp0098`; B had no image. The attempt
owned `/Temp/temp00AF` and
`/Temp/uos-hardware-native-desktop-j68k61ya-restore.prg`. Both uploads are absent
after cleanup. The nine borrowed settings-area bytes were restored and compared
during execution. The saved boot snapshot precedes that restoration: its five
setting bytes match, while the surrounding scratch bytes differ as expected.
The archive retains the original nine bytes and their exact restoration-write
receipt; it does not contain a separate raw final nine-byte readback.

Run the offline audit without contacting the C128:

```sh
python3 -B docs/validation/2026-09-12-native-desktop-abi19-hardware/verify.py
```

The audit reconstructs every CPU payload from its raw chunks, compares all
borrower pairs, complete screens, mode snapshots and resident images, and
checks the receipts, restoration record and complete temporary-file readbacks.
`SHA256SUMS` seals every payload after that audit.
