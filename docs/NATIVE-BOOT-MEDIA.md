# Native D64 and D81 boot media

`python3 -B build-native-desktop.py` builds the same seven native apps for a
1541/D64 and a 1581/D81. Both cold-boot into the blue graphical launcher.
The D64 suite has 16 free data blocks; the D81 has **2,512** (638,048 bytes
of sequential-file payload, before any additional directory allocation).

| Image under `target/` | Startup | Files |
|---|---|---|
| `native-desktop/kestrel.d64` / `.d81` | Blue launcher | Seven apps and their modules |
| `native-desktop/workspace.d64` / `.d81` | Memory workspace; B opens the launcher | Same suite |
| `native/kestrel.d64` / `.d81` | Memory workspace; B opens text Files and Apps | Diagnostic Calculator, browser, Editor and modules |

For an emulated 1581:

```sh
x128 -default -80col -8 target/native-desktop/kestrel.d81 -drive8true -drive8type 1581
```

The disk and kernel must match. D81-specific kernel PRGs, listings, symbols and
layout reports live in each output directory's `d81/` subdirectory. Applications
and the boot-sector PRG are shared with D64. Copying the D64 `U` file into a D81
does not select D81 geometry. Startup uses the build profile, without probing
or guessing the mounted disk's format. D71 data access already exists, but a
D71 boot distribution and partitioned 1581 volumes are not covered here.

ABI 1.12 stores the system geometry in `N_BOOTFORMAT` (`$3de4`): 0 D64,
1 D71, 2 D81. It is paired with `N_BOOTDEVICE` and is read-only for apps during
the native session. Workspace C/B and the launcher use that pair. A browser
may retain device 9/D64, or an Ultimate path, without changing where system
apps or the launcher are loaded. Modules retain their caller's original app
source through the existing module loader. Native restart resets preferences
and reloads the build's boot format.

The 426 managed RAM pages, API entry addresses, application slot and Editor
module window are unchanged. Both suites include the shared `VDSVC.PRG` beside
the apps. Deployment metadata reports its 39-page allocation and available
desktop pages for REU backing and both VDC RAM fallback sizes.

The boot block occupies track 1, sector 0 and is outside every file chain.
`native_disk.py` reserves it before adding files. On a 1581 the BAM occupies
track 40, sectors 1/2; its track entries start at byte 16 and contain a free
count plus five bitmap bytes. These constants follow Commodore's
[1581 declarations](https://github.com/mist64/cbmsrc/blob/01bd60f162ef92212ef0cb67546ae8f42be34168/DOS_1581_1987-03-19/equate.src)
and [BAM I/O](https://github.com/mist64/cbmsrc/blob/01bd60f162ef92212ef0cb67546ae8f42be34168/DOS_1581_1987-03-19/bamutl.src).

`tests/ci_native_boot_media.py` independently checks all six images, every
directory/file chain, all allocation bits/counts and exact shipped PRGs. It
then fills the D81's advertised free space, checks the full payload and original
files, and rejects boot/BAM corruption. The startup CPU test covers both formats
and boot styles, system shortcuts with stale data preferences, and both banks'
allocation/fill/verify/free controls. `tests/ci_native_pointer_iec.py --d81`
exercises the suite through a real emulated 1581 and host keyboard/1351 input.
Software evidence is retained in the [D81 record](validation/2026-09-13-native-d81-suite/README.md).
Physical 1581 and Ultimate-mounted D81 qualification remain separate work.

## Packed kernel boot file

The disk's `U` entry is now `kestrel-boot.prg`. The uncompressed `kestrel.prg`
remains available for loading tools, resident layout checks and debugging.
Each startup/geometry profile has its own pair. The wrapper retains the same
BASIC `SYS 7184` entry and expands a deterministic raw LZSA2 stream, checking
input and output bounds, prior-output match addresses, exact lengths and CRC16
before entering the kernel. Overlapping matches are permitted only within the
output already being reconstructed; a first repeat has no valid offset.
Malformed or damaged streams return to BASIC with `BOOT ERROR - RELOAD`.

The compressor (`native_lzsa.py`, an optimal-cost parser run in-process by the
builder) and the 6502 decoder (`src/native/lzsa2-decode.inc`) are independent
implementations written from the LZSA2 block format description; the format
itself is from Emmanuel Marty's LZSA project, and no LZSA project code is
included. No C compiler or network access is needed. Each packed result is
verified with a separate Python decoder.
The compression checkpoint recovered thirteen D64 blocks, increasing free
space from 2 to 15 while preserving the unpacked kernel and every app payload
at that checkpoint. The current shared VDC component uses that space; the full
suite had one free D64 block at that checkpoint. [Packed app startup](NATIVE-APP-PACK.md)
leaves 124 free blocks in the current suite while preserving all seven expanded programs and
their existing allocations. App-bound modules are resealed to their packed
parents; resident kernels and packed boot files retain their bytes.

During cold startup only, the decoder occupies the future low kernel area at
`$1300` and copies its compressed input into future app RAM at `$6000`. These
ranges do not overlap the decoded kernel at `$1c01..$58ff`. The normal kernel
startup then replaces the decoder and initializes the same 426-page heap.
No new resident allocation, API entry or application memory limit is added.
The wrapper uses no zero-page scratch, restores the incoming MMU and D/I flags,
and rejects C64 mode before changing the map. Interrupts are masked during the
bounded copy/decode step. This is a cold-boot file, not a running-app loader.

`tests/ci_native_boot_pack.py` executes all four wrappers against the exact raw
kernel images, checks reads and writes stay within the declared startup
regions, and exercises all offset formats, short/extended lengths, repeated
and overlapping matches, damage, truncation, early termination, output overflow
and mode refusal. Explicit valid fixtures, written by hand with their decoded
bytes, also run through the separate Python decoder. `tests/ci_native_boot_vice.py` cold-boots all six disks, checks keyboard
input and both desktop displays, and exercises workspace/desktop returns.
Disk-chain verification checks the packed `U` bytes; runtime layout verification
continues to compare the reconstructed resident kernel. See the
[software validation record](validation/2026-09-13-native-boot-lzsa/README.md).
