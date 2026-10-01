# Packed native app qualification

The launcher and six apps now fit on the D64 suite with 147 free blocks,
compared with one at the preceding shared-display checkpoint. D81 has 2,643
free blocks. The temporary startup decoder and compressed input are released
before the original app begins. Application allocations, the 426-page heap,
resident kernels and diagnostic native disks are unchanged.

This record follows signed commit
`c4647f7685ec395e88b8153ac5e3ba9a8badbac9`, whose shared-display record has seal
`68c277a13a8f8c83f148a1809acf93a10a69c771462901ecc84c43f9a9111b1c`.
The [startup contract](../../NATIVE-APP-PACK.md) describes allocation, image
identity, failure recovery, module pairing and temporary memory requirements.

## Result

Packing saves 36,996 file bytes and 146 disk blocks across the seven programs.
Each reconstructed original PRG is byte-identical to the parent commit.
Editor and Files modules have the same code and layout; their parent and
module checksums are resealed to the packed app identities. Restoring the old
parent checksum reconstructs all four original module files exactly.

Packing trades startup CPU work for fewer disk bytes. The CPU model measured
the following cycles from the native loader call to original app entry. ROM
IEC calls are stubbed, so this excludes actual device-transfer timing:

| Program | Original file | Packed file | Packed startup alone |
|---|---:|---:|---:|
| Desktop | 5,402,304 | 11,268,340 | 6,744,036 |
| Paint | 14,840,026 | 26,271,511 | 16,993,924 |

Both suite disk formats currently use packed apps. These measurements do not
establish physical launch times or a speed improvement. A fast-storage profile
with original app files remains follow-up work; app/module identities must
remain paired when selecting a profile. The archived `timing.py` and its report
make the CPU comparison reproducible against these exact program images.

All 34 native PRG/D64/D81 artifacts reproduce in a separate build. Fifteen
change from the parent: seven apps, four app-bound modules and four suite or
workspace disks. The other nineteen artifacts are unchanged, including all
eight resident-kernel and packed-kernel-boot files.

The kernel verifies the complete outer NAPP and closes its source before
startup. The wrapper checks the running app, structural manifest, descriptor
and page ownership before reserving its four decoder pages. A separately owned
input allocation prefers bank 1 and can fall back to bank 0. Bounded decoding
and its complete output CRC precede original app entry. Cleanup runs in unused
app memory, so no instruction is fetched from the released decoder.

## Software evidence

The final commands have terminal zero exit codes and unchanged input hashes:

- Twenty-one startup cases exercise complete original bodies, memory release
  before entry, bank-0 input fallback, allocation and transfer failures, outer
  truncation/extension/checksum rejection, malformed decoded lengths, decoded
  checksum failure and a resealed header declaring a smaller allocation.
- Ninety-eight IRQ/NMI deliveries exercise decoding with a decimal-mode caller;
  mapping, borrowed gateway scratch, unrelated memory and an open foreign file
  remain intact. Two further cases exhaust the temporary code or input handle
  slots after the parent has loaded.
- Editor's graphical picker and large-document workflow pass. Files rejects a
  corrupt picker and recovers from a missing graphics module. All eleven native
  Claude workflows pass with the packed client.
- Full six-app VICE workflows pass with D64/1541, 80-column startup and 64 KiB
  VDC RAM, and with D81/1581, 40-column startup, 16 KiB VDC RAM and a 16 MiB REU.
  Real host mouse and ROM keyboard input exercise saving, viewing, copying,
  terminal controls, painting and return to the blue desktop.
- All six native/suite/workspace disks cold-boot in VICE. Media checks separately
  verify complete file chains, allocation maps and exact payloads, including a
  full private D81 and corrupt-media rejection.

The standalone audit reconstructs the packed apps against archived parent
artifacts and verifies the exact rebuild and module identities. It also checks
complete launcher/Calculator palette canvases, fourteen VDC restores, all bytes
of the independent REU snapshots, observer scratch restoration and final private
disk contents. No shipped file is lost during the workflows.

## Evidence and reproduction

`inputs.tar.gz` contains the final source, tests, build dependencies and target
artifacts. `parent-images.tar.gz` contains the 34 artifacts from the preceding
signed revision. `rebuilt-images.tar.gz` contains the separate build.
`jobs.tar.gz` retains commands, status records, reports and logs, and
`outputs.tar.gz` retains private emulator disks, raw surfaces, palette canvases,
snapshots and observation guards. Each archive has an exact per-file manifest.

The earlier input set used by the first CPU and D64 jobs differs only in five
documentation/comment files and the absence of the new startup document and
supplemental handle-slot test. `earlier-input-files.tar.gz` and the earlier hash
manifest reconstruct that version. The host workflow's executable statements
are identical; only its explanation of the data-disk selection changed. All
production and build inputs are identical between the two sets.

Run the audit with standard Python and no emulator:

```sh
python3 -B verify.py
```

`audit.json` records the resulting byte, case, canvas and restoration counts.
To reproduce runtime checks, extract the frozen inputs into a fresh directory,
install the documented build/VICE/Py65 tools and run the archived commands.
Allocate each emulator's private X display before starting another emulator.
The VICE harness still uses the developer-local CBM helper. The installed C128
KERNAL ROM is identified by hash in `provenance.json` and is not redistributed.

No physical hardware I/O, push or deployment was performed. Remaining app VDC
views, document backing, shared scheduling, hardware qualification and the
broader OS roadmap remain open. Keep this sealed record immutable.
