# Native desktop production build integration

This isolated integration places the native display lifetime, clipped drawing
library and keyboard desktop in production source/build locations. The source
overlay starts from signed commit `ddb7ef1f3103102db2c614d5142603f1fc743757` and
preserves its USB recovery helpers. The final source is applied to the main
tree and its build reproduces the same images. Physical qualification is
tracked separately in the [hardware archive](../2026-09-11-native-desktop-hardware/README.md);
three attempts were incomplete, with full restoration and verified cleanup.

The direct desktop disk, workspace-with-desktop disk, both kernels and all apps
reproduce the sealed candidates exactly. `build-native-desktop.py` writes the
desktop package to `target/native-desktop`, preserving the diagnostic package
in `target/native`. Graphics and scene sources live under `src/native`.
`build-native-graphics.py` builds the public library for its CPU regression.
The 335-file input closure needs no prototype `graphics`, `client` or `launcher`
directory. The build auditor compares every retained program/disk image and
extracts all six members from each desktop disk.

Both kernel variants pass the same nine desktop CPU workflows: complete
surfaces, selection, direct app shortcuts, dispatcher errors, fragmented-surface
fallback, unsupported display state and cleanup. All 1,243 public graphics
cases pass with 22,943 modeled interrupts, using the same 2,685-byte library
retained by the clipping checkpoint. The existing Calculator regression also
passes after its test helper gains a separate app-image directory argument.

Six packaged-path VICE workflows pass: direct desktop boot, workspace entry,
80-column boot, missing app, missing desktop and the shared hardware sequence.
Five workflows independently reproduce 33 complete surfaces and 2,112,000
rendered pixels. The separate shared sequence retains 101,274 CPU-captured
bytes in 66 captures/215 IRQ chunks, including five complete desktop views,
six app/workspace screen pairs and six CPU mode snapshots. The running-code
audit compares 11,971 immutable bytes at boot and return and retains all 1,581
declared mutable bytes. Nine corruption/observation controls pass.

The first integration CPU/emulator runs used the reorganized source tree.
Ten runtime/test files are identical in this clean input closure. The clean
tree additionally restores the latest signed USB recovery code and merges
the desktop CLI option without removing existing options. Its exact images
and graphics library were rebuilt, and its graphics/default-Calculator checks
were rerun. `source-overlays.json` preserves the initial 51 source changes.
The final two-file observer overlay under `current` retains all before/after
borrower bytes. Its five strict host-fault controls and complete shared VICE
sequence pass. `source-overlays-current.json` identifies the final 52 files;
the effective input closure contains 336 files. The final sequence retains
264 borrower pairs, totaling 642,048 host-observed bytes, in addition to its
CPU captures. Documentation is outside this executable input closure.

Read-only audits (no physical machine access):

```sh
python3 -B verify-package.py
python3 -B verify-emulators.py
python3 -B verify-sequence.py
python3 -B verify-current.py
python3 -B current/verify-sequence.py
python3 -B verify-integration.py
```

A passing software workflow does not establish
physical video output, pointer/window interaction, VDC bitmap support,
persistent desktop state or full application/Ultimate parity. The current
hardware observer's additional before/after diagnostics are retained in the
separate V3 hardware package and the final production overlay. Initial software
inputs remain intact, and the final combined workflow is retained separately.
