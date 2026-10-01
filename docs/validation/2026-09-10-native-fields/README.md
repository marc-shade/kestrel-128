# Native shared fields — ABI 1.6 qualified checkpoint

ABI 1.6 supplies owned field editing and caret drawing to the editor, browser
and calculator. Left/Right, Home/Ctrl-E, insertion, Del/Ctrl-D and Ctrl-U use
the same bounded service. Both displays retain separate clipped viewports.
The editor's picker preserves the complete field state and live document
on cancellation. See the [field contract](../../NATIVE-FIELDS.md).

All twenty CPU suites, ten native emulator workflows and complete physical
USB/IEC workflows pass against the frozen images. Independent readback matches
nine USB files and all four files on the IEC document disk. All five complete
66,056-byte document captures match while the picker has focus; cancellation
preserves the eight-byte field record exactly.

| Qualification | Frame pairs | CPU captures | IRQ capture chunks |
|---|---:|---:|---:|
| Ten native emulator workflows | 111 | 439 | 1,237 |
| Physical C128 USB workflow | 57 | 469 | 887 |
| Physical C128 IEC workflow | 24 | 126 | 335 |
| Total | 192 | 1,034 | 2,459 |

The first IEC attempt failed before native boot because the cartridge stored
partial/empty uploads despite successful HTTP replies. It and the failed
recovery attempts remain archived. A verified load from the intact prior disk
restored the desktop; exact old test images were reclaimed before the new run.
The new IEC workflow verifies stored upload sizes and a complete recovery
loader before boot, restores the original mounted system disk, and removes its
own temporary files after independent readback. All 24 host transport, upload
and restoration fault checks pass. See [upload recovery](BOOT-UPLOAD-RECOVERY.md).

The kernel occupies 15,361 PRG bytes, with eight pages relocated into low RAM.
The 426-page heap and the calculator/browser/editor allocations of 16/28/79
pages remain intact. Main code ends at `$379d`; low code ends at `$1ab9`.
The editor is 20,116 bytes. Larger modules, native graphical desktop migration,
events, scheduling, clipboard/undo and expansion support remain roadmap work.

`cpu-initial` retains the run before shortening the numeric field's help text
by one space. It caught a one-column overflow in the DOS-context prompt.
Two loader fixtures also still rejected minor 6; the corrected fixtures reject
minor 7. Those failures remain recorded; all seven affected suites pass in the follow-up.
The initial run passed the other 14 suites, including all eleven picker flows.
Separate final-kernel field and USB dispatcher reports are included.
`cpu-run/report.json` maps each of the twenty passing reports to its original
run; `verify-artifacts.py --cpu-only` checks those reports and image identities.

Earlier development checks also caught use of a closed file handle in place
of the app's memory handle. The loader now retains its actual allocation
identity; the field validator compares its full generation and page tags.
The USB browser-to-calculator dispatcher regression passes with that fix.

The physical USB run records 57 frame pairs, 469 CPU captures and 887 IRQ
capture chunks. It verifies the 255-byte browser field and middle edit,
calculator `HISTORY` at caret 5, all 66,056 document bytes while the picker
is at ordinal 256, and exact preservation of the eight-byte editor field
record on cancellation. All nine independent file readbacks match. Both
workspace blocks, resources, DOS paths, settings and the deployed desktop
are restored, and the private fixtures are removed.

The offline directory audit passes 19 pages and 26 frame pairs against the
independent 1,096-entry directory oracle and the final private directory order.
Four direct-DMA samples disagree with CPU RAM captures: three match the
separate BASIC ROM images completely; two bytes in the fourth sample remain
unexplained. Those bytes and both original observations are retained. CPU
captures remain the RAM authority. Two read-only observation timeouts recovered;
no uncertain write is reported.

`hardware-iec-boot-timeout` preserves the failed boot attempt, original report,
RAM observations and complete traceback. It contains no completed editor test
and is excluded from qualification totals. Product images remain unchanged.
The [upload and recovery record](BOOT-UPLOAD-RECOVERY.md) explains the partial
and zero-byte cartridge files, verified restoration and exact reclamation of
524,544 bytes. Its separate verifier checks the original 99-file harness and
current 102-file harness without accessing the cartridge.

The physical IEC run performs 123 input events and independently reads back
the full 174,848-byte data disk. Its `SAVED` field is cancelled at caret 4 with
both viewports unchanged. Open, verified Save As and reopen take 289.894,
537.495 and 295.981 seconds, including quiet intervals and host monitoring.
The physical USB equivalents take 38.309, 80.936 and 38.313 seconds. These are
observed workflow times, not isolated throughput benchmarks. The completed IEC
run has no TCP retries, uncertain writes or DMA/CPU disagreements.

Physical IEC coverage uses Ultimate-emulated 1541 drives on devices 8 and 9;
D71/D81 qualification is from the emulator. The native workspace and these
apps are qualified for the recorded workflows. The full graphical OS, office
suite, scheduling, broader expansion support and faster IEC paths remain open.

## Reproduce the archive audits

These commands perform no hardware I/O. The package verifier rebuilds in a
private temporary directory. Omit `--record` to compare the recorded results.

```sh
python3 docs/validation/2026-09-10-native-fields/verify-package.py
python3 docs/validation/2026-09-10-native-fields/verify-artifacts.py
python3 docs/validation/2026-09-10-native-fields/verify-directories.py
python3 docs/validation/2026-09-10-native-fields/verify-dialogs.py
python3 docs/validation/2026-09-10-native-fields/verify-rom-observations.py /usr/share/vice/C128 --folder hardware
python3 docs/validation/2026-09-10-native-fields/verify-rom-observations.py /usr/share/vice/C128 --folder hardware-iec
python3 docs/validation/2026-09-10-native-fields/verify-boot-recovery.py
cd docs/validation/2026-09-10-native-fields
sha256sum -c SHA256SUMS
```

`SHA256SUMS` covers every archived file except itself. Earlier validation
archives remain unchanged.
