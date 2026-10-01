# Native drawing transfer optimizations

This private candidate processes complete eight-scanline bitmap bands as
contiguous transfers and draws aligned glyph cells with one eight-byte write.
Opaque aligned glyphs require no preceding bitmap read. Clear/set bands use
`N_FILL`; XOR bands use a bounded read, local XOR and write. Unaligned edges
retain the prior clipped drawing path and all transfers use the owned heap API.

The library, including its font, grows from 2,022 to 2,342 bytes (ten allocation
pages). The demonstration grows by 320 bytes to a 3,206-byte PRG declaring
thirteen app pages, plus its separate 36-page surface. Kernel and system app
images are unchanged from the isolated display candidate.

All 697 CPU cases pass: 239 rectangle cases, 318 glyph cases and 140 bounded
text cases, with 9,104 modeled interrupts. Added cases exercise complete and
partial bands, 256-byte transfer crossings and the final screen cell. Complete
surface comparisons, ownership/busy guards, both RAM banks and decimal/interrupt
state checks pass. All five emulator lifecycles also pass with exactly the same
surface and rendered pixels as the [preceding text candidate](../2026-09-11-native-graphics-text/README.md),
including IEC reads under graphics and restoration of both consoles.

| Identical successful CPU case | Previous instructions | Current instructions | Reduction |
|---|---:|---:|---:|
| Full-surface XOR, with modeled IRQs | 7,572,884 | 1,025,502 | 7.385× |
| Aligned opaque 8×8 glyph | 10,218 | 1,149 | 8.893× |
| Aligned opaque ten-character label | 102,901 | 12,211 | 8.427× |

These compare executed model instructions, not physical elapsed times.
The API contract is unchanged from the preceding text candidate. Per-window
clipping, events/focus/pointer input, VDC bitmap support, physical graphics
measurements and the concurrent large-document/desktop layout remain open.
Neither this candidate nor the underlying display kernel is integrated into
production; the underlying main USB fault is still under investigation.

The package pins the 218 unchanged inputs from the
[display lifetime archive](../2026-09-11-native-display-lifetime/README.md),
and records 32 additional source, binary and CPU report files in `source/`.
`display-emulator/` holds the exact client, harness, raw captures and reports.
The preceding text archive's manifest is pinned for the performance comparison.

Run the read-only auditors with:

```
python3 verify-package.py
python3 verify-display.py
python3 verify-performance.py
sha256sum --check --quiet SHA256SUMS
```

Package/display auditors accept `--record` to write their derived reports.
Reproduction otherwise uses the preceding text candidate's instructions, with
this `source/` overlay. The CPU runs used Python 3.14.7 and py65 1.2.0; emulator
checks used the same pinned native kernel and local VICE/cbm runtime.
