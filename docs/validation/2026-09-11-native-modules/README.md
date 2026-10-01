# Native application modules — ABI 1.7 qualified checkpoint

ABI 1.7 loads the editor picker from `EDPICK.PRG` beside its original app,
retains the verified module for later calls and preserves the parent,
document, fields and workspace allocations. It checks the module's extent,
parent binding, CRC, source CLOSE and generation before publishing an entry.
See the [module contract](../../NATIVE-MODULES.md).

All 22 native CPU suites, ten emulator workflows, complete physical USB/IEC
workflows, clean rebuild and 51 distinct host fault checks pass. The final
offline audits compare captured bytes, screens, directory records and stored
files against the frozen images and independent oracles. This supersedes the
[ABI 1.6 field checkpoint](../2026-09-10-native-fields/README.md) for the
recorded native workflows.

| Qualification | Frame pairs | CPU captures | IRQ capture chunks |
|---|---:|---:|---:|
| Ten native emulator workflows | 111 | 530 | 1,328 |
| Physical C128 USB workflow | 59 | 518 | 943 |
| Physical C128 IEC workflow | 24 | 155 | 364 |
| Total | 194 | 1,203 | 2,635 |

The module suites cover 109 loader/gate cases and twelve editor retry flows.
The five emulator/physical module workflows observe states `0,3,2,3,2` and
retain token 1 after the first load. All five complete 66,056-byte documents
match while the picker has focus, and all five field records survive
cancellation byte-for-byte. The module headers, original parent manifests,
source records and tokens are CPU-observed. These captures do not independently
recapture every loaded module-body byte.

The first USB run failed while the boot browser rescanned its retained USB
directory after a missing-app launch. It stopped before reaching the editor
module. The browser reported disk I/O failure with an uncertain-close directory
descriptor; the initiating transport failure is not established. The exact
logical sequence passes the CPU model, which does not establish physical
timing behavior. See [the retained evidence](hardware-usb-initial-failure/README.md).

The failed run restored the original mounted disk, boot settings and live legacy
desktop. A separate checked cleanup read back all ten complete private input and
output files, restored both DOS paths, and removed twelve exact private paths
with acknowledged deletes and confirmed absence. Its observations and host
fault checks are audited by [verify-usb-recovery.py](verify-usb-recovery.py).
Cleanup success does not resolve the native workflow failure.

The successful USB retry includes 59 screen pairs, 518 CPU captures and 943
IRQ capture chunks. It independently compares ten complete files, including
the picker module and the 66,056-byte saved document. The cold picker load
takes 9.308 seconds including its first directory scan; later calls retain
token 1 and the original USB source. Both workspace blocks, document bytes
and the eight-byte field record survive picker use and cancellation. All
owned memory/files are released, both DOS paths and the deployed desktop
are restored, and the private fixtures and two temporary boot inputs are
removed with checked readback and confirmed absence.

The directory audit passes all 21 pages against independent listing bytes.
Six DMA samples disagree with CPU RAM observations: five match the separate
BASIC ROM images completely, and two bytes in the sixth remain unexplained.
Both observations are retained; CPU captures remain the RAM authority. One
read-only RAM observation times out and is safely retried. No uncertain host
write or host connection failure is reported. This successful retry does not
identify the first run's initiating transport fault.

The physical IEC run has 123 input events and independently reads back the
entire 174,848-byte document disk, including all four exact files. Its cold
picker takes 42.363 seconds, including the initial scan. Open, verified Save As
and reopen take 289.888, 537.522 and 295.979 seconds; the USB equivalents take
38.307, 78.886 and 38.309 seconds. These include the recorded quiet intervals
and host monitoring and are not isolated throughput measurements. One
read-only RAM observation recovers on retry, with no connection retry or
uncertain write. All four IEC DMA/CPU disagreements match BASIC ROM completely.
The original mounted disk, drive B, settings, function-key table and DOS paths
are restored; both temporary disk images and the recovery loader are removed
with acknowledged deletes and confirmed absence.

The kernel PRG is 15,617 bytes. Main code ends at `$37a9`, low code at `$1bc1`,
and the module service ends at `$490a` before the retained path at `$4a00`.
The editor core is 12,496 PRG bytes and its picker 7,724 bytes, sharing the
same 79-page allocation. The tested document, both workspaces and picker use
423 of 426 heap pages. Nine staging pages are reclaimed after relocation.
The boot, browser and calculator PRGs retain their preceding bytes; eighteen
legacy images also remain unchanged.

The frozen native source/image set has 47 files. The original CPU/emulator/USB
harness snapshot has 123 files; `harness-after-usb-failure` holds four diagnostic
and cleanup overrides/additions used for the retry. The earlier three USB
preparation/restoration harness versions are retained in
`harness-before-usb-restore`. The 13 restoration checks rerun after the diagnostic
change are repeats, so they do not increase the 51 distinct host case count.

The additional [SDK example](sdk-example/README.md) has 15 passing CPU
workflows on the same frozen kernel. Its sources and two PRGs are retained
separately; these checks do not change the original 22-suite count or add a
hardware claim. [verify-sdk-example.py](verify-sdk-example.py) rebuilds the
saved example and reproduces its complete CPU report in a private directory.

Physical IEC coverage uses Ultimate-emulated 1541 drives on devices 8 and 9;
D71/D81 data-disk workflows are emulator coverage. The first USB fault remains
unexplained. Its separate CPU delayed-abort reproduction identifies a bounded
cleanup improvement for a follow-up, which is not included in these images.
IEC uncertain-close recovery, general module replacement cleanup, native
graphical desktop migration, scheduling, office applications and wider
expansion support remain open in the [roadmap](../../IMPLEMENTATION-ROADMAP.md).

## Reproduce the archive audits

These commands perform no hardware I/O. The package verifier builds privately;
the SDK verifier also needs the test environment's `py65` dependency.
Omit `--record` to compare the saved reports, as shown here.

```sh
python3 docs/validation/2026-09-11-native-modules/verify-package.py
python3 docs/validation/2026-09-11-native-modules/verify-artifacts.py
python3 docs/validation/2026-09-11-native-modules/verify-directories.py
python3 docs/validation/2026-09-11-native-modules/verify-dialogs.py
python3 docs/validation/2026-09-11-native-modules/verify-modules.py
python3 docs/validation/2026-09-11-native-modules/verify-rom-observations.py /usr/share/vice/C128 --folder hardware
python3 docs/validation/2026-09-11-native-modules/verify-rom-observations.py /usr/share/vice/C128 --folder hardware-iec
python3 docs/validation/2026-09-11-native-modules/verify-usb-recovery.py
python3 docs/validation/2026-09-11-native-modules/verify-sdk-example.py
cd docs/validation/2026-09-11-native-modules
sha256sum -c SHA256SUMS
```

`SHA256SUMS` covers every archived file except itself. Earlier validation
archives remain unchanged. The initial failure is retained outside the passing
workflow totals.
