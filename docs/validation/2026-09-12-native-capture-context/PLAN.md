# Focused native capture transport experiment

## Revision 2: native ROM interrupt mapping and retained raw chunks

The preceding experiment is sealed in commit
`f13e269ee97a02dd221cf81403dcc47948b0b0c6`. It stopped on saved MMU `$00`;
all 856 write receipts and all borrower restorations matched. Its original
deployment and both temporary files were restored/cleaned.

This revision permits the two supported interrupted mappings, `$0e` and `$00`.
The field historically named `foreground_mmu` is the mapping saved by the IRQ
entry and need not describe the foreground app. The native ROM switches to
`$00` before its handler, whose CLI permits nested interrupts. Other mappings,
bad mode/common registers, failed status and short payloads remain rejected.
Each chunk now retains the raw twelve-byte status and raw payload before status
guards are evaluated; this adds no successful-path RAM reads. Buffer and oracle
comparisons remain exact, with no matching-reread acceptance.

Forty-eight CPU cases pass, including actual ROM/probe execution in both
supported mappings. Sixty host controls pass, including ten new accepted/
rejected status/length cases and first-byte evidence retention. The corrected
focused VICE workflow `uos-native-desktop-iec-h931wcws` passes all 27 captures,
35,726 payload bytes, 912 raw status bytes, 234 pause/resume batches and 16
surface/VDC samples.

A separate VICE workflow `uos-native-desktop-iec-jis09_he` forces nested RAM and
VDC captures inside the real ROM IRQ. Both save MMU `$00` at interrupted PCs
`$c567`/`$c569`, return exact 512-byte payloads and unwind both interrupt frames
to the normal desktop with matching stack depth and MMU `$0e`. All borrower
pairs and 128,000 before/after desktop pixels match. Its temporary RAM IRQ entry
and persistent emulator breakpoints are test machinery used only in VICE.
Earlier versions of that test missed temporary breakpoint stops; their failed
reports are retained as emulator-harness history and are not physical evidence.

The same bounded physical sequence below is used once with the corrected host
observer. OS, app, disk and IRQ-probe binaries remain unchanged. A passing
focused run would not establish the cause of prior byte differences or complete
the full desktop/app qualification.

Baseline: signed local main commit `a58cd26a5ff86f7c6ad8865255e8cd1726dbc52c`.
OS, application, disk and IRQ-probe bytes are unchanged. The prior three full
desktop attempts remain failed evidence; their original deployments and both
private uploads have been restored/removed.

## Question and limits

The third attempt retained seven differing restored output-buffer bytes and
71 unexpected bytes in its last 464-byte captured chunk. Its host writes did
not retain the firmware's accepted address range. A successful HTTP response
alone does not establish how many bytes were parsed or what RAM later held.

This experiment retains exact PUT request address/count/hash and raw JSON
receipts, refuses any incomplete range acknowledgement, and pauses the CPU
across bounded snapshot/install/command/result/restoration batches. It resumes
between batches so the unchanged IRQ probe can run. Every batch attempts one
compensating resume on exit, including a lost pause reply. It does not retry a
failed write or accept a later matching readback over a previous discrepancy.

The local Ultimate firmware checkout reports the parsed inclusive address
range and leaves an already stopped CPU paused during raw transfers. These
sources inform the experiment; they do not prove the installed firmware is
identical or that a full acknowledgement establishes correct RAM contents.
The run retains the device's version response separately.

## Bounded sequence

1. Verify the existing idle legacy desktop, nine settings bytes, drive mounts
   and both DOS working paths. Create and fully read back the private 2,036-byte
   recovery loader before changing the mount. Check all RAM write receipts.
2. Mount one private copy of the exact 174,848-byte desktop disk and verify its
   stored size. Reset once and leave the existing quiet boot interval intact.
3. Audit immutable native resident code, capture native display-mode fields,
   the complete boot bitmap allocation and VDC text.
4. Inject one Tab key to select Editor. In each of three trials, compare the
   selected desktop's `$c7d0`/2,000, `$cdd0`/464 and `$c000`/512 CPU-read bytes
   against the independent surface oracle. Capture selected VDC text and final
   display controls; require IRQ progress and an idle foreground app.
5. Restore the original disk and legacy desktop, exact settings and drive state.
   Verify both original DOS paths. Fully read both private files before deleting
   either, confirm both return 404, and verify controls/settings/drives/liveness.
   Propagate any capture failure after successful restoration and cleanup.

Stop on the first failed comparison or acknowledgement. Record exact expected
and observed sample bytes, every borrower before/after pair reached, all pause/
resume requests, and all successful or rejected RAM write receipts. Do not
launch apps or interpret this focused diagnostic as full desktop qualification.
A passing run would support this capture method for further tests; it would
not establish the initiating cause of any prior failure.

## Predecessor software gates (retained for context)

- 33 offline transport controls cover exact/short/wrong/missing range receipts,
  HTTP/JSON/lost replies, invalid requests, 128-byte segmentation, pause/body/
  resume failures, nested batches and strict borrower read faults.
- Four lifecycle controls exercise success, capture failure, restoration failure
  and stored-file mismatch. Failed restoration/readback must preserve files.
- Existing five borrower controls and eight connection controls pass.
- Final VICE sequence: `uos-native-desktop-iec-qyb94_r9`, 25 RAM/VDC captures
  plus two mode snapshots, 35,726 CPU-captured bytes, 234 completed pause/resume
  batches, 16 exact surface/VDC samples, and one Tab event.
- All native, legacy and probe inputs match the baseline manifest.

The entry point checks frozen input hashes and creates an exclusive attempt
journal before hardware I/O. A second invocation is refused until the first
attempt has been inspected. No firmware, cartridge configuration or permanent
system disk change is part of this experiment.
