# Focused native capture transport diagnosis

The physical experiment failed on the observer's saved-MMU guard. The original
desktop was restored and both private files were fully verified and removed.
No full desktop hardware qualification is claimed. The production kernel,
apps, disk images and IRQ probe remain exactly those of signed main commit
`a58cd26a5ff86f7c6ad8865255e8cd1726dbc52c`.

The earlier [three desktop attempts](../2026-09-11-native-desktop-hardware/README.md)
remain failed evidence. In particular, this experiment does not explain their
buffer or payload differences. The [plan](PLAN.md) defines the bounded sequence
and the [frozen manifest](frozen-inputs.json) records 343 inputs.

## Transport and software evidence

The private `ReceiptUltimate` records each PUT RAM write's address, length,
payload hash and raw reply. It requires an exact inclusive address-range
acknowledgement, HTTP success and an empty error list. Failed acknowledgements
are retained without replay. A full receipt establishes what the firmware
acknowledged, not the later contents of RAM.

The private monitor pauses across each bounded snapshot, installation,
command, result and restoration batch, then resumes so the unchanged IRQ probe
can execute. Every batch attempts one compensating resume, including a lost
pause reply. Strict borrower comparisons remain active. The hardware lifecycle
can defer a capture error until the original deployment and temporary files
have been restored/cleaned; failed restoration or readback preserves files.

Fifty host controls pass: 33 transport/borrower cases, four lifecycle cases,
five existing borrower cases and eight existing connection cases. The final
VICE sequence passes 27 captures, 35,726 CPU-captured bytes, 234 completed
pause/resume batches, 16 exact surface/VDC samples and one Tab selection.
The final hardware-only lifecycle changes add version-response retention and
accurate diagnostic labels; their four offline lifecycle controls pass.

## Physical outcome

The run `uos-hardware-native-transport-2e_li_y9` verified the 11,971 immutable
resident bytes, saved all 1,581 declared mutable bytes, captured a valid native
graphics mode and compared the first 2,000 bitmap bytes. It then failed on the
first 512-byte chunk of `boot-surface-07d0`, before reading that chunk's payload:

| Observed status field | Value |
|---|---|
| Completion | 1 |
| Native mode register | `$37` |
| Common-memory register | 4 |
| Saved interrupt MMU mapping (`foreground_mmu`) | `$00`, while the guard requires `$0e` |
| VDC address resynchronizations | 0 |

There are 12 capture records, including one mode snapshot and the interrupted
sample. Eleven complete payload files retain 15,567 CPU-captured bytes. All
48 borrower before/after pairs match, totaling 116,736 retained host-observed
bytes. All 106 pause/resume batches completed. All 856 RAM writes across the
whole lifecycle received exact range acknowledgements; no uncertain write or
connection failure was recorded.

The error remains a failed test. The failed chunk's payload and raw twelve-byte
status read were not saved; parsed status fields are retained. The observation
alone does not establish whether the zero was a valid saved CPU mapping or an
incorrect host read.

The original drive A image `/Temp/temp0098`, empty drive B, nine settings bytes
`507302f0a502030000`, DOS paths `/` and `/Usb0/c64/#-a/`, controls and active
legacy desktop were verified after restoration. Both private files were fully
read back (176,884 bytes total), deleted and confirmed absent:

- `/Temp/temp00AD`, the 174,848-byte desktop disk.
- `/Temp/uos-hardware-native-transport-2e_li_y9-restore.prg`, the 2,036-byte loader.

No temporary hardware resource or running process remains from this attempt.
The retained device version response is the API's `0.1`; it does not identify
the installed firmware build. The five local firmware source references explain
the proposed API behavior and are not asserted to match that installed build.

## A reproducible guard defect

The local C128 ROM's IRQ entry saves the interrupted mapping and switches to
MMU `$00` at `$ff22`. Its display interrupt helper executes `CLI` at `$c229`.
A second IRQ can therefore save `$00` while interrupting an existing ROM IRQ.

The retained CPU model executes that real ROM entry and helper from an outer
`$0e` context, injects a nested IRQ immediately after `CLI`, and executes the
unchanged native probe. It captures the exact 512 expected bank-0 bytes with
saved MMU `$00`, then restores the outer frame and registers. Its nested chain
handler is a modeled counter followed by the actual native ROM return gateway;
this is not a full-machine VICE reproduction. It demonstrates a valid capture
that the current host guard rejects, without proving the physical failure had
that cause. The separate VICE transport pass did not force nested IRQ timing.

The next observer change should account for the supported ROM interrupt
mapping, qualify complete nested return behavior, and retain raw status and
payload evidence before evaluating a status guard. Earlier byte mismatches
remain separate unresolved observations.

## Verification

```sh
python3 -B docs/validation/2026-09-12-native-capture-transport/verify.py
<home>/.venvs/uos-tests/bin/python3 -B docs/validation/2026-09-12-native-capture-transport/nested-irq-model/replay.py --work /tmp/uos-nested-irq-replay
```

The audit performs no hardware I/O. The model requires py65, 64tass and the
local C128 ROM; it writes only to the supplied work directory. The archive-local
replay reproduces its report, probe, captured bytes, expected bytes and saved
outer stack exactly. `SHA256SUMS` covers all retained files except itself.
