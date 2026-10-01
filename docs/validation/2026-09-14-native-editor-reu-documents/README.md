# Editor documents in shared REU memory

Graphical Editor can now open and edit documents beyond the RAM backend's
96 KiB limit. Documents and VDC screen backups share the checked REU arena
inside `VDSVC.PRG`, with separate ownership and lifetimes. A memory lease
retains the provider across display closure; clean hardware refusal selects
the existing RAM backend. Allocation failure preserves the original document,
uncertain transfers prevent Save As, and failed cleanup retains ownership
for recovery. Native ABI 1.12 and the 96-page Editor allocation are unchanged.

This checkpoint is based on signed commit
`d334b47bbd5295bbb52734e163aa88bfcd300579`. Its preceding Editor VDC record's
`SHA256SUMS` digest is
`ff7a440e40062c55ac7dc94bc4b53747754b116876cd5d393e115f93d0d55ba4`.
All execution used software models or private VICE images. No physical
hardware was changed, and this record does not claim hardware qualification
or completion of the broader [roadmap](../../IMPLEMENTATION-ROADMAP.md).

## Evidence

- 28 terminal runtime jobs passed, including 87 named CPU cases, the disk
  integrity check, the independent REU byte oracle, and two cold VICE boots.
- The shipped Editor core and search module passed document edits beyond
  1 MiB, two-context relocation, random replacements, IRQ/MMU checks,
  capacity rollback, transfer failures, and retained cleanup recovery.
- A private D81 boot with 64 KiB VDC and 16 MiB REU opened 131,113 bytes,
  inserted text beyond 96 KiB, used the destination picker, saved 131,118
  bytes, independently exported the file, reopened it, and returned to the
  desktop. A RAM-only D64 boot saved to a separate device-9 data disk.
- The offline audit independently decoded nine complete 16 MiB REU
  snapshots: seven document observations and two display restoration
  observations. It compared document data, gap contents, unrelated bytes,
  allocation ownership, and the original VDC bytes. It also compared 84
  graphical canvases, totaling 8,064,000 pixels, and four exact VDC restores.
- A separate build reproduced all 34 native app and disk artifacts. Eight
  changed: Editor, its two modules, the shared service, and four suite disk
  images. The other 26 artifacts, including every diagnostic native image,
  match the parent. All shipped disk files and three saved files were
  independently decoded and checked.

The expanded Editor is 14,125 bytes and its packed file is 9,820 bytes.
Its module origin is `$972b`; the picker ends at `$bf1a`. The shared service
uses 33 bank-1 pages. REU-backed Editor retains 245 free main-RAM pages;
document growth does not consume more. RAM-only display backups use their
existing 64 or 72 pages. The suite D64 has 138 free blocks and its D81 has
2,634.

## Reproducibility

Run `python3 -B verify.py` in this directory for the sealed offline audit.
It needs only Python's standard library. `audit.json` records the result;
`SHA256SUMS` covers every top-level record file.

`inputs.tar.gz` contains all 734 final input files. `executions.tar.gz` and
`executions.json` preserve the exact runtime input sets for six execution
generations, with their source roots and job mappings. The supervisor tracked
Python, assembly, include, PRG, disk and binary files before and after each
run. The archived additional C, header and assembler sources also match the
final production manifest. All 211 production sources and shipped artifacts
are identical across accepted generations; later changes concern test
oracles, test coverage and documentation. The two final memory tests ran
directly from the final frozen inputs.

For an original runtime environment, unpack the final inputs and overlay the
corresponding execution generation. Use the recorded command with its report
destination changed to a writable scratch path. Runtime commands require
the C128 test Python environment, 64tass and, for cold boots, VICE, Xvfb,
ImageMagick, c1541 and the local Commodore launcher used by the test harness.
The launcher path is environment-specific and remains a portability gap.
`jobs.tar.gz` preserves commands, status, reports, rebuild script and logs;
`outputs.tar.gz` preserves the captured evidence. Separate archives hold
rebuilt and parent images. `development.tar.gz` preserves earlier attempt
records, including excluded harness failures; they are not counted as
passing qualification jobs. Each archive has a manifest of member lengths
and SHA-256 digests. `changes.json` binds the applied files to the parent.

## Remaining limits

REU document capacity depends on available contiguous storage, with a
24-bit capacity limit of 4,095 pages. Relocation temporarily needs both old
and replacement extents. The memory choice is fixed for the app lifetime;
live Ultimate REU size changes, disk paging, cross-app clipboard and undo
remain future work. This checkpoint establishes the shared memory service
and Editor integration; it does not imply every app already uses that service.
