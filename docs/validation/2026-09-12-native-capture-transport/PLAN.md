# Focused native capture transport experiment

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

## Software gates

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
