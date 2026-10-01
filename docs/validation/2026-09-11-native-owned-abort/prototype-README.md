# Owned Ultimate abort completion — software qualification

The separate candidate waits for an abort submitted by the native transport
to reach idle, or for a bounded second interval to expire, before returning
the original transport error. The wait does not resubmit a command or abort.
It leaves the existing owner-retention contract in place when completion
remains uncertain. This addresses the delayed-abort cleanup gap demonstrated
in the CPU model; the initiating cause of the first physical USB failure is
still unproven.

The change is 15 resident bytes in `src/native/ultimate.inc`. It adds no heap
reservation, changes no public ABI address, and leaves the boot, calculator,
browser, editor and picker PRGs byte-identical to the module candidate.
The rebuilt kernel SHA-256 is
`45281b86a55f93c6402a7b0159075148d0f19086471c504bf859332c0b25e63d`;
the D64 SHA-256 is
`279ea21079c19181a0c5827a9c05cbf55fd5e23a90ef74c5e157c0f48f024a36`.

The frozen module kernel fails the first new delayed-abort assertion. Its
executed test and failure report are retained as the negative control.
The changed kernel passes 14 new fault workflows, including command/ACK
stalls, malformed packets, a non-completing abort, unrelated ownership and
123 interrupts during the new wait. These are synthetic register delays,
not measured cartridge timings.

All 24 CPU suites pass: the 22 existing native suites, the new abort suite,
and the 15-workflow SDK example. Five initial passes on these exact images
were retained and the other 19 suites were run. The SDK exit label was later
corrected and its 15 workflows repeated in a separate source tree. Original
SDK observations remain under `cpu-original-sdk`; the three changed sources
are under `harness-sdk-correction`. The original 130-file harness snapshot
remains intact.

The seven images reproduce in a clean build, and five disk members extract
exactly. All ten emulator workflows and their independent audits pass:
530 captures, 1,328 IRQ chunks, 111 screen pairs, 219 RAM observations,
zero direct-DMA disagreements and 198,159 independently compared copied bytes.
The three editor module workflows retain their original source and warm token.

Physical qualification is pending. These sources have not replaced the live
module candidate, whose USB/IEC qualification must finish first. After that
checkpoint, apply the saved patch and new test, rebuild to these hashes,
retain this software evidence and run both physical backends on the changed
kernel before publishing a qualified result.
