# Native boot compression qualification

The full native D64 suite had only two free blocks before the shared bank-1
VDC service could be packaged. The boot wrapper now uses bounded raw LZSA2
compression and leaves 15 free blocks. The four boot files shrink by
3,136–3,139 bytes. The uncompressed resident kernels and every app payload
are byte-identical to signed parent `ea01477649840d25a4a94200b606475a67976052`.
The six shipped disks contain the new boot files and the complete existing app
suite. The D81 suite has 2,511 free blocks.

The decoder lives temporarily at `$1300`, with compressed input at `$6000`.
It checks input and output bounds, prior-output backreferences, exact lengths,
and CRC16 before entering the kernel. Its scratch bytes stay outside zero
page; it restores the incoming MMU and decimal/interrupt flags. It rejects
C64 mode before changing the map. The existing resident memory layout, ABI,
426-page heap, desktop appearance and app behavior remain unchanged.

The host compressor is vendored from
[emmanuel-marty/lzsa](https://github.com/emmanuel-marty/lzsa/tree/15ee2dfe118eeb8f7683ca44f64821c3a61ca1e5).
The host build now needs `cc` or the command specified by `CC`; it compiles in
a temporary directory without network access. All copied sources and licenses
are checked against the pinned revision. The adapted 6502 decoder retains the
upstream zlib notice and describes the uOS changes.

## Software evidence

Four supervised jobs finished successfully against the archived frozen inputs:

- 59 CPU cases execute the real decoder. They cover all four kernel profiles,
  all D/I combinations, all match-offset forms, repeated and overlapping
  matches, literal/match length boundaries, the maximum kernel region, damaged
  input, truncation, invalid addresses, reserved lengths, early/missing end
  markers, overflow, wrong CRC and C64 refusal. Ten explicit valid fixtures
  also agree with the upstream C decoder.
- Six VICE cold boots cover the standalone workspace, direct desktop and
  workspace-with-desktop disks in both D64/1541 and D81/1581 configurations.
  Checks cover keyboard input, bank selection, desktop selection, workspace
  returns and reopening the desktop. The four suite boots compare 24 complete
  VIC/VDC canvases, including 16 KiB and 64 KiB VDC configurations.
- Independent disk parsing verifies all file chains, exact PRG contents, boot
  sectors and BAM allocation. Filling a private D81 preserves every suite file
  and its boot sector; malformed boot/BAM fixtures are rejected.
- An independent rebuild reproduces all 33 native PRG/D64/D81 artifacts. Ten
  change from the parent: four packed boot files and six disk images. The other
  23 artifacts, including the unpacked kernels and app payloads, are unchanged.

Each job records its actual exit status. Runtime jobs verify every input hash
before and after execution; the rebuild checks source hashes and image bytes.
Regenerated listings retain their private build paths. The standalone audit
rechecks every archive and job record, independently decodes the four boot
streams, walks all six disk allocation maps and compares 2,304,000 displayed
pixels. Run it with standard Python:

```sh
python3 -B verify.py
```

`inputs.tar.gz` contains the exact source, host tests, dependencies and target
artifacts used by the jobs. `jobs.tar.gz` contains commands, logs, reports and
input hashes. `outputs.tar.gz` retains the VICE disk copies, surfaces and raw
palette canvases. `rebuilt-images.tar.gz` retains the independent rebuild.
Their companion manifests include every member's size and SHA-256. The outer
`SHA256SUMS` seals the complete record.

To reproduce in a checkout with the documented native build tools and Py65:

```sh
python3 -B build-native-desktop.py
python3 -B tests/ci_native_boot_pack.py --report /tmp/uos-boot-cpu.json
python3 -B tests/ci_native_boot_media.py --report /tmp/uos-boot-media.json
python3 -B tests/ci_native_boot_vice.py --report /tmp/uos-boot-vice.json
```

This is a software qualification. No physical hardware I/O, deployment, push
or external service access was performed. The shared bank-1 VDC component is
still under development; this checkpoint creates disk space for its integration.
The remaining app views and the broader OS roadmap stay open.
