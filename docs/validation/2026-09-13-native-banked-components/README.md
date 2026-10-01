# Native bank-1 executable components

This software checkpoint adds an app-linked loader and returning bank bridge,
plus a separate-file SDK example whose REU arena runs in bank 1. It follows
signed commit `c509fc80e11108af08192206f8b563ebddf4ca6b`; the previous REU
Calculator record seal is
`57e4bc67c6bd1f336b67c417bc899dac7293c5214ea43f367db1a7f87d5d78eb`.

The [contract](../../NATIVE-BANKED.md) describes the fixed bank-1 executable
region, stream and code ownership, common-RAM mapping, callback restrictions,
NBK1 manifest, failure recovery and banked REU variant. The
[example](../../../examples/native-banked/README.md) builds without modifying
the suite media. Editor documents and the remaining VDC app views have not
yet moved onto this support.

## Qualified result

- 1,111 frozen inputs; 20 changed source, test and documentation files.
- Five terminal supervised jobs pass with their actual subprocess exit codes recorded. Test inputs remain byte-identical throughout execution.
- All 33 shipped native PRG/D64/D81 images reproduce byte-for-byte from the signed base. The resident kernel and 426-page heap are unchanged.
- The retained bank-0 loader/executor occupies 1,604 bytes. The example parent loads 2,382 bytes into 10 pages; its separate bank-1 provider loads 2,284 bytes into nine pages. No complete provider copy occupies the parent slot.
- 65 CPU case groups: 33 banked loader/provider groups, nine complete SDK workflows, and 23 default bank-0 REU regression groups. Checks include all eight REU capacities, malformed/truncated/long images, exact 24-KiB bounds, stale generations, owner/page validation, partial probe recovery and uncertain Ultimate source close.
- 736 IRQ/NMI attempts cover every unique instruction/map boundary of the bank switch and native callback. Accepted interrupts are counted; mapping, borrowed registers and stack balance are checked on return.
- Native callbacks exercise low bank-1 heap data, IEC/Ultimate file open/read/close and a multipart Ultimate query under IRQ delivery. Exit, module operations, owner-wide release and destructive access to active code are refused.
- Nine SDK workflows compare 72 complete console frames, covering three IEC geometries, both Ultimate DOS contexts, absent REU, missing provider and corrupt provider. Exit returns all 426 pages and 32 descriptors.
- Three cold C128 VICE boots cover 128 KiB, 256 KiB and 16 MiB REUs. Six complete snapshots independently compare 34,340,864 REU bytes. Captured low bank-1 data independently compares another 141,312 bytes before/after DMA and native heap callbacks.
- Raw loaded-provider captures match the sealed image with only its callback import patched. The bank-0 probe shadow, borrowed system registers, DMA-bank/speed restoration and final heap recovery are also checked.

Physical C128/REU/Ultimate qualification, larger app/display migration,
REU-backed documents, scheduling and shared driver ownership remain open.
No physical hardware was accessed and nothing was pushed or deployed.

## Evidence and reproduction

`inputs.tar.gz` contains the frozen repository inputs, excluding prior
validation records and interpreter caches. `jobs.tar.gz` contains reports,
commands, exit status and input hashes. `outputs.tar.gz` retains assembled SDK
and fixture files, the private VICE disks, complete REU snapshots, logs and
raw bank-1 guards. `rebuilt-images.tar.gz` contains the 33 unchanged images.
Each archive has an exact per-file manifest.

The build ran before two host tests gained additional query coverage and raw
guard captures. `build-source-overlay.tar.gz` contains those exact earlier
test files; `build-input-overlay.json` inside the jobs archive records the
complete build input hashes. Only these two host files differ. Every assembly,
build source, example, library and shipped image matches the final test inputs.

`provenance.json` pins source commits, ROM identity and base image hashes. The
installed proprietary KERNAL ROM is not redistributed. The VICE test harness
still requires the developer-local CBM helper documented in the example.

Run the independent audit without emulators or external files:

```sh
python3 verify.py
```

It verifies the seal, exact archive manifests, input versions, build equality,
image bounds/CRC, report identities, complete REU memory, loaded provider bytes
and low bank-1 guards. `audit.json` records the deterministic result.
To rerun CPU, SDK, VICE or build commands, extract `inputs.tar.gz` into a fresh
directory and follow the example's commands. Keep this sealed record immutable.
