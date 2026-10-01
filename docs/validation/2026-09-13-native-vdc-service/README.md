# Shared native VDC service qualification

Desktop and Calculator now load the same `VDSVC.PRG` from their original app
source. It contains the native 640×200 desktop renderer, Calculator's
incremental VIC-to-VDC presenter, saved-display lifetime, pointer and REU
backing. The existing blue layouts, icons and selection behavior are preserved.
The [component contract](../../NATIVE-VDC-SERVICE.md) documents loading,
memory costs, internal calls and recovery.

This checkpoint follows signed commit
`4935a695d4da9023ca63b91f517bebbc48c9e1fc`. The previous boot-compression seal is
`4a67506a2434684f58a65a279964619398a3f9a6cafc00e9a55664a07dd4c802`.

## Result

The Desktop app occupies 8,833 loaded bytes in 35 pages; Calculator occupies
12,428 bytes in 49 pages. Each saves eight bank-0 executable pages. The separate
7,592-byte component occupies 30 bank-1 pages while loaded. REU-backed screen
snapshots leave 325 managed main-RAM pages free in Desktop and 309 in Calculator.
The main-RAM fallback consumes another 64 or 72 pages according to VDC capacity.
The component creates room in the app code window; total RAM use increases on
machines using the fallback.

The component stream closes before execution. Native callbacks validate
ownership and restore the kernel mapping. App input readiness is cleared before
mailbox writes or bank switching. Complete VDC memory and register restoration
precedes release of the snapshot, REU arena and executable. A failed restore
retains every required owner and blocks handoff; a clean setup refusal releases
the unused component. Uncertain source close retains its poisoned file record
and code without issuing further I/O on repeated exit requests.

All 34 native PRG/D64/D81 artifacts reproduce exactly in an independent build.
Seven artifacts change from the parent: Desktop, Calculator, the new provider,
and four suite/workspace disks. The other 27 artifacts, including resident
kernels, packed boot files and the remaining app programs, are unchanged.
The full suite contains thirteen files and leaves one free D64 block or 2,497
D81 blocks. Calculator history uses the D64's final block; the full workflow
selects device 9 through the Editor picker for its document. D81 retains room
for both samples. Every shipped file is preserved.

## Software evidence

The archived final jobs record actual subprocess exit codes and unchanged
input hashes. They cover:

- Complete Desktop and Calculator bitmaps, attributes, focus, pointer edges,
  arithmetic, history, save/cancel, app handoff and retained display faults.
  Both VDC capacities are exercised in both initial addressing arrangements.
- The actual separate provider through the checked banked loader, including
  both renderers, all launch-error glyphs used by the fixtures, pointer clipping
  and exact VDC/REU restoration.
- Component loads on three IEC geometries, both Ultimate contexts and a data
  drive differing from the app source. Missing/corrupt providers, an overlong
  component path, occupied code region and uncertain stream close are checked.
- REU-backed Calculator workflows, absent-REU fallback, capacity-probe recovery
  and failed snapshot-read recovery. Provider records are read only after
  validating the live code allocation, generation, page tags and patched header.
- The banked SDK's loader/callback and interrupt guards, plus the existing
  VIC-only pointer and Calculator workflows.
- Full six-app VICE workflows using real host mouse and ROM keyboard input:
  D64/1541 with 80-column startup and 64 KiB VDC RAM, and D81/1581 with
  40-column startup, 16 KiB VDC RAM and a 16 MiB REU. Each app returns to the blue
  desktop before the final diagnostic-workspace return.
- Independent parsing of all six disk images, exact payloads and allocation
  maps, full private D81 allocation and corrupt-media rejection.

The VICE observer checks bank-1 allocation identity before reading provider
state. Restore checkpoints require the bank-1 MMU configuration, preventing
bank-0 code at the same numeric address from satisfying the check. Complete
saved VRAM is compared before register restoration and app handoff. REU backing
is independently read from VICE snapshots; bytes outside the display backups
are checked against the initial REU image.

## Evidence and reproduction

`inputs.tar.gz` retains the frozen source, tests, build dependencies and target
artifacts. `jobs.tar.gz` records commands, reports, logs and exit status.
`outputs.tar.gz` retains private emulator disks, snapshots, raw surfaces,
palette canvases and observer guards. `rebuilt-images.tar.gz` contains the
independent build. Exact per-file manifests accompany all four archives.

One host file changed after the initial freeze: the D64 workflow's Files wait
now records file/list progress, with a two-minute stall limit and ten-minute
total limit, and its destination-picker expectation includes the Editor file
already saved on device 9. The first run had loaded Files and was still
validating its directory when the fixed two-minute deadline expired. Its stopped
state and failure record are retained under `superseded-vice-d64`. The next run
reached the data picker, which correctly showed that saved document; its old
expectation was an empty disk. That host revision, failure and disk are retained
under `superseded-picker-oracle`. No app, driver, build source or rendering model
changed for either rerun. `earlier-host-files.tar.gz` and the
earlier input manifest reconstruct the exact inputs used by the other jobs;
the current inputs contain the revised host wait.

Run the standalone audit with standard Python and no emulator:

```sh
python3 -B verify.py
```

It checks the seal, archive manifests, input versions, terminal job results,
NBK1 bounds/CRC, rebuilt artifacts, disk allocation, complete VIC/VDC frames,
VDC restoration, REU snapshot contents and observer scratch restoration.
`audit.json` records the resulting case, frame and byte counts.

To reproduce, extract the frozen inputs into a fresh directory, install the
documented native build/VICE/Py65 tools and run the archived commands. Start
emulator runs separately so each private X display is allocated before the
next run starts. The VICE harness still imports the developer-local CBM helper;
the offline audit does not need it. The installed proprietary C128 KERNAL ROM
is identified in `provenance.json` and is not redistributed.

No physical hardware I/O, push or deployment was performed. Remaining VDC app
views, Editor document backing, shared scheduled
drivers, physical qualification and the broader OS roadmap remain open.
Keep this sealed record immutable.
