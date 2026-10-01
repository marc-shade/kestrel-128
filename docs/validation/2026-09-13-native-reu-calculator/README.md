# Native REU allocator and Calculator display backing

This checkpoint adds an app-owned REU arena and uses it for Calculator's VDC
snapshot. It qualifies software images only; no physical C128, REU or Ultimate
was accessed, and nothing was pushed or deployed.

The base is signed commit `ab66f4a242196fa0711a444e8690fa129f503e1b` and the
previous VDC Calculator seal is
`985f7de3422215cb4386146922166c4855dce42d046d59885419f6b1b1cb5090`.
The [library contract](../../NATIVE-REU.md) describes its foreground lifetime,
eight-byte tokens, capacity probe, DMA bounds, register ownership and recovery.

## Result

- 577 frozen inputs and 33 native PRG/D64/D81 images; two clean rebuilds reproduce every image.
- Only Calculator and the four desktop suite disks change among those images. The four raw kernels, four boot wrappers, Desktop and the other apps/modules remain byte-identical to the base.
- Calculator contains 14,369 loaded bytes and occupies 57 app pages. With REU backing it leaves 331 main-RAM pages free, a net gain of 55/63 pages over the prior 16/64 KiB VDC build. Its no-REU fallback leaves 267/259 pages free.
- D64 retains all twelve shipped files with two free blocks. D81 retains 2,498 free blocks; allocating all 634,492 bytes of advertised SEQ payload preserves every shipped file and the boot sector.
- 56 primary CPU case groups cover the allocator, loaded Calculator, existing graphical controls, VDC setup failures and fallback. An additional earlier seven-group Calculator run is retained separately.
- Eight cold native VICE runs cover 128/256/512 KiB and 1/2/4/8/16 MiB REUs. Sixteen independent complete REU snapshots compare 66,846,720 bytes, including the floating 1764 hole, 512 KiB counter edge and final 16 MiB byte. The host's bank-1 RAM, DMA bank, CPU speed and D/I flags are checked.
- Two complete desktop workflows pass: D64/1541/40-column boot/16 KiB VDC without REU, and D81/1581/80-column boot/64 KiB VDC with a 16 MiB REU. Both run Calculator, Editor, Files, Ultimate, Claude and Paint; verify saved files and preserve every shipped file.
- 137 VIC and 45 VDC frames match independent pixel oracles: 14,528,000 palette pixels. Fourteen VDC snapshots are restored before app handoff; the REU-backed Calculator snapshot is read independently from VICE's saved machine state.
- 1,612 CPU captures, 5,709 chunks and 6,448 borrower preservation pairs have no rejected evidence. Both workflows finish with all 426 native heap pages and 32 descriptors free and all host processes terminal.

REU allocations are confined to the current foreground app's retained arena.
Documents, caches, other app views, persistent RAM disks, scheduling, hardware
configuration changes and physical expansion qualification remain additional
work. The kernel and diagnostic text Calculator do not acquire an REU.

## Evidence and reproduction

`inputs.tar.gz` contains the complete frozen build/test inputs, with per-file
sizes and hashes in `inputs-files.json`. `reference.tar.gz` pins Commodore
RAMDOS and VICE REC/C128/snapshot implementations. Every archive has an exact
manifest; `SHA256SUMS` seals the record. The archive paths contain only files.

`jobs.json` and `jobs.tar.gz` record ten terminal successful supervised jobs,
including the exact input hashes before execution and their preservation on
completion. The first frozen host fixture used a method symbol cache; the final
fixture uses an instance-local cache so old CPU machines can be reclaimed.
Both source versions are retained in `source-versions.tar.gz`; no shipped image
changed. The final Calculator REU workflow passes with the final fixture.

`preliminary.tar.gz` retains exploratory reports and logs. An early Calculator
run failed while its mutable candidate inputs were being rebuilt. That run is
excluded from qualification. The corresponding retained-probe recovery case
passes on frozen inputs.

Run the independent offline audit:

```sh
python3 verify.py
```

It verifies the seals, exact archive contents, source versions, rebuilt images,
media allocation, CPU reports, complete REU snapshots, both display oracles,
file readback, borrowed scratch and resource cleanup. `audit.json` records the
result. `rebuild.py` documents the two clean build commands and comparisons;
run a new reproduction in a fresh copy because sealed records are immutable.
