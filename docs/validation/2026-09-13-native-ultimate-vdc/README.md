# Ultimate graphical VDC qualification

Ultimate's identification, drive, network and clock panels now use the shared
graphical VDC presenter. Its file picker and explicit drive confirmation share
the same surface and original-screen backup. A 64 KiB VDC uses yellow focus;
16 KiB uses light reversed controls. Mouse and keyboard input retain their
existing meanings on both displays.

This record follows signed commit
`7b86297b643f42621dbc92a3954de637dee5301f`, whose packed-app record has seal
`3104f82d13066c5378640a7b102eb5386cf352b74e12954c71cecc0fb3e0719a`.

## Result and limits

The app uses 96 bank-0 pages, its 36-page VIC surface and the unchanged 30-page
bank-1 `VDSVC.PRG`. It allocates four bank-0 scratch pages only while the picker
is open, freeing them after the directory cursors and cache close. This moves
idle scratch out of the app's executable window and leaves room for the display
client without changing the resident kernel or its 426-page heap.

REU backing leaves 264 main-RAM pages free outside the picker. Main-RAM backing
leaves 200 with a 16 KiB VDC or 192 with 64 KiB. The complete D64 suite retains
140 free blocks and D81 retains 2,636. Packing trades startup CPU work for disk
space; this milestone makes no physical launch-speed claim.

The provider and six other packed programs retain their exact parent bytes.
All four app-bound modules and all eight resident/packed-kernel boot artifacts
are also unchanged. Only Ultimate and the four suite/workspace disks change
among the 34 native PRG/D64/D81 artifacts. All 34 reproduce in a separate build;
an independently assembled and sealed Ultimate PRG also matches the complete
expanded packed program.

Display failures retain the saved screen and block drive actions until Escape
can restore it. If a picker surface operation fails, the VDC is restored before
text controls are drawn. Refresh in the main panel can reacquire graphics.
Missing hardware/components and memory pressure leave usable fallback controls.
The mount/eject policy and literal commands retain their existing checks.

## Software evidence

Thirteen final jobs have observed terminal zero exit codes and unchanged frozen
input hashes. They cover panel and picker graphics, both VDC sizes and initial
addressing modes, pointer-only and field updates, mount confirmation, REU and
main-RAM backing, failed screen/probe restoration, absent/corrupt components,
picker scratch exhaustion, legacy control/drive workflows, shared picker callers,
packed startup, six media images, an exact rebuild and VICE.

The full picker tests compare the VIC surface against the independent dialog
oracle and both complete VDC bitmaps/attributes. They preserve the same provider
and snapshot token across the dialog, retain preferences and free all temporary
scratch. The mount assertion requires exactly one explicit confirmed command.

The VICE workflows use private D64/1541 and D81/1581 images. They start in
80-column/64 KiB VDC and 40-column/16 KiB VDC modes respectively; the latter
also uses a 16 MiB REU. Real host mouse and ROM keyboard input exercise every
Ultimate panel, return to the launcher and exact display restoration. VICE
does not emulate the cartridge's UCI target here, so these workflows verify its
unavailable-device UI; the independent CPU device model exercises actual drive
responses, picker paths and confirmation semantics. Six generated images also
cold-boot through their documented entry paths.

The standalone audit checks complete palette canvases, original VDC snapshots,
all bytes of the REU snapshots, native observer scratch restoration and exact
private disk contents. The runtime oracles additionally check the controls and
dialog contents. It does not infer physical cartridge support from these results.

## Reproduction

`inputs.tar.gz` holds the frozen source, test, build and target files. The jobs
archive retains exact commands, reports, terminal status and logs, including the
separately assembled expanded program. `outputs.tar.gz` holds private emulator
disks, raw surfaces, palette canvases, observation guards and snapshots.
Parent and rebuilt images have separate archives. Every archive has an exact
per-file manifest, and `SHA256SUMS` seals the complete record.

Run the standalone audit using standard Python without an emulator:

```sh
python3 -B verify.py
```

`audit.json` records the exact resulting case, image, canvas and restoration
counts. Runtime reproduction requires the documented 64tass/cc65, VICE and Py65
tools. Allocate one emulator's private X display before starting another.
The VICE harness still uses the developer-local CBM helper; the required KERNAL
ROM is identified by hash and is not redistributed.

No physical hardware I/O, deployment or push was performed. Editor, Files,
Paint and Claude VDC migration, document backing, scheduling, hardware
qualification and the rest of the completion roadmap remain open.
Keep this sealed record immutable.
