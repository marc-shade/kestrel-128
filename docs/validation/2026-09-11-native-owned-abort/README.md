# Native owned-abort completion

Qualification completed 2026-09-12 on the frozen images below.

The current kernel waits for an abort submitted by its own Ultimate transport
to reach idle, or for a bounded second interval to expire, before returning the
original transport error. The added wait does not resubmit a command or abort.
When completion remains uncertain, the existing owner-retention contract stays
in force. This addresses the delayed-abort cleanup gap demonstrated by the CPU
model; the initiating cause of the first module-checkpoint USB failure remains
unproven.

The exact 15-byte source change and its 14-case regression have been applied
after signed module checkpoint `2bde88b`. The current seven images match the
isolated software qualification. All 24 CPU suites and ten emulator workflows
pass. The physical USB attempt failed during reopening of the saved large file
through DOS context 2, after the editor had verified the save. The desktop was
restored and the images remained unchanged. The [failure evidence](hardware-usb-reopen-failure/README.md)
is retained; its initiating fault remains under investigation. The full
uninstrumented USB retry, physical IEC workflow and combined hardware audits
now pass. The [module checkpoint](../2026-09-11-native-modules/README.md)
is the preceding qualified baseline.

The [focused first-error diagnostic](hardware-first-error-diagnostic/README.md)
completed six successful second-context reopens with temporary rollback
instrumentation. The patch, desktop, paths and owned resources were restored;
five closed files and both temporary inputs matched complete readback. The
fault did not reproduce. Its 114 CPU captures and 245 IRQ chunks include five
DMA disagreements; all five complete direct samples match the separately
installed C128 BASIC ROM bytes in [the comparison report](first-error-rom-observations.json).
CPU captures remain authoritative for RAM, and these matches do not establish
the cause of either the mapping discrepancy or the USB failure.

The full unmodified USB retry passes on 255 frozen source/build/runtime inputs.
It passes the previously failing second-context reopen, returns through the
browser, releases all native owners and restores the deployed desktop, drives,
settings and DOS paths. Independent readback matches all ten closed files
(155,547 bytes) and both temporary inputs (176,884 bytes), followed by removal
of the exact private resources. Its 59 screen pairs, 518 CPU captures and 943
IRQ capture chunks are retained in `hardware/`. The directory audit reconstructs
all 21 observed pages. Nine DMA/RAM disagreements include seven whole ROM
matches and 18 unexplained direct bytes in two samples; CPU captures remain
authoritative and the [ROM comparison](hardware/rom-observations.json) retains
those deviations. The passing retry does not establish the earlier fault's
cause.

Physical IEC qualification also passes on the same 255 frozen inputs. The
editor opens 66,053 bytes, edits at logical offset 65,537, saves 66,056 bytes
through the picker, refuses an existing destination, and reopens the saved
document. Independent readback verifies all four files on the separate device-9
document disk, including the empty file. The 24 screen pairs, 155 CPU captures,
364 IRQ capture chunks, 73 RAM observations and 20 editor states are retained
in `hardware-iec/`. Three DMA/RAM disagreements are whole reference-ROM
matches, with no unexplained direct bytes in this run. All native owners,
function keys, original drives, settings and DOS paths are restored. The two
private disk uploads and restore loader are deleted and confirmed absent.

The long IEC Open, verified Save As and reopen events take 289.868, 537.429
and 298.027 seconds respectively, including the harness's quiet/poll intervals.
These observations are not isolated device-throughput measurements.

The kernel SHA-256 is
`45281b86a55f93c6402a7b0159075148d0f19086471c504bf859332c0b25e63d`;
the D64 SHA-256 is
`279ea21079c19181a0c5827a9c05cbf55fd5e23a90ef74c5e157c0f48f024a36`.
The boot, calculator, browser, editor and picker PRGs remain byte-identical.
No ABI entry moves and no additional heap page is reserved. The module service
moves from `$4678..$4909` to `$4687..$4918`, leaving 231 bytes before `$4a00`.

The old kernel fails the first delayed-abort assertion. Its executed test and
failure report are retained as the negative control. The changed kernel's
fourteen fault workflows cover delayed command/ACK completion, malformed
packets, an abort that never finishes, unrelated ownership, and 123 interrupts
during the new wait. These are synthetic register delays, not measured cartridge
timings. The first error remains `$ff` for timeout or `$fc` for the malformed
packet. The never-completing case retains its owner until external completion
and explicit checked CLOSE.

The 24-suite total includes the 22 preceding native suites, the new abort suite
and the 15-workflow SDK example. Five initial exact-image passes were retained
and the other nineteen suites were run. The SDK label correction was then
qualified separately on the same kernel; its original observations remain in
`cpu-original-sdk` and its three source changes in `harness-sdk-correction`.
The SDK example also rebuilds and reproduces its current report from this
archive. CPU mappings are explicit in `cpu-run/report.json`.

The original 130-file harness is retained. Three SDK overrides and four
physical-harness overrides/additions produce the 132-file software-qualification
harness. The final recovery changes replace two files and add one new test,
giving 133 effective files. Of the 125 preceding module-harness files, 123 remain
unchanged. All 51 existing host fault checks have now been rerun against the
current recovery code, alongside 36 new checks for the retained-file reopen and
exact cleanup scope. All 87 pass without hardware I/O. Their reports are in
`host-current/`; the preceding reports are retained separately. Thirteen prior
repeated restoration cases add no distinct cases.
[verify-integration.py](verify-integration.py) checks both harness stages against
the preceding signed archive's pinned checksum manifest.

The 47 original frozen files and 47 integrated files are both retained.
Five listing files differ only in assembler metadata; their assembly rows,
all native sources and every program/disk byte match the qualified build.
[verify-package.py](verify-package.py) rebuilds privately and verifies all
seven images, all five disk members and the exact source patch without changing
the archived build. The original prototype records and runner scripts are
retained with a `prototype-` prefix.

Emulator audits retain 530 CPU captures, 1,328 IRQ capture chunks, 111 screen
pairs and 219 RAM observations, with no DMA disagreement. The native file
workflows independently compare 198,159 copied bytes. The three editor workflows
retain their module source/token, complete 66,056-byte document and field state.

`SHA256SUMS` seals the complete archive, including failed attempts and recovery
evidence. The package, integration, physical-input, emulator, module, dialog,
directory, ROM and combined-artifact audits pass. The full OS, native graphical
desktop migration, scheduling, office applications and remaining expansion and
recovery work are still open.
