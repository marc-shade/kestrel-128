# Native window clipping and concurrent editor layout

This private drawing library adds a per-window pixel clip and efficient masked
edges for eight-scanline bands. Rectangles, glyphs and bounded text intersect
the clip. Attribute writes affect only complete 8×8 cells wholly inside it.
Empty or inverted clips suppress drawing. Successful binding resets the clip;
refused calls preserve the documented binding and busy-state behavior.
The library and original ASCII font occupy 2,685 bytes. The demonstration PRG
is 3,694 bytes, declaring fifteen app pages plus its 36-page surface.

All 1,243 CPU cases pass: 287 rectangles, 318 glyphs, 140 text operations and
498 window-clip operations, with 22,943 modeled interrupts. Full surface
oracles cover both banks, signed edges, partial cells, clipping across x=256,
ownership and extent errors, stale handles and decimal/interrupt state.
All five VICE lifecycles pass: explicit exit, normal return, freeing the visible
surface, missing replacement and text-app replacement. Evidence includes three
complete 9,216-byte surfaces, five complete 64,000-pixel frames, both restored
text consoles and two 513-byte IEC reads while graphics is active. Four absent
bytes at the end of VICE's full canvas are retained; every active pixel arrived.

The concurrent layout test uses the real editor, module loader, heap, file and
display code with modeled device ports. A foreground call is modeled from the
retained editor core; this is not yet an interactive graphical editor feature.
It reserves the surface before loading a 66,053-byte document, edits beyond
64 KiB, draws through an editor-bound module, opens the picker past directory
ordinal 256, saves and verifies all 66,056 bytes, reloads the renderer, frees the
visible surface and exits. All 426 pages and 32 handles are available afterward.
The renderer fits the existing editor module window and adds no resident reserve.

| Allocation at the picker peak | Pages |
|---|---:|
| Editor, including its module window | 79 |
| Owned display surface | 36 |
| Seventeen document chunks | 272 |
| Picker cache | 8 |
| Remaining free pages | 31 |

A separate one-page allocation at `$d000` makes the aligned surface reservation
fail despite 74 free pages. The full document and previous allocations remain
unchanged. This demonstrates fragmentation handling and the need to reserve
the display early; it does not mean every late reservation must fail.

`history/` retains both preceding layout implementations and the initial
15-million-instruction test-bound failure. The unchanged implementation passed
with a 60-million bound. Masked band processing then reduced the identical
scene from 17,729,767 to 4,738,938 modeled instructions (3.741×). The final
clipping scene adds operations and takes 5,197,786 instructions. These are CPU
model counts, not physical drawing times. Historical runs are not added to the
current 1,243-case/five-emulator totals.

The package reuses 218 frozen inputs from the
[display lifetime candidate](../2026-09-11-native-display-lifetime/README.md),
pins 53 current source/report files and retains 97 historical inputs. The
kernel and editor images are unchanged. No graphics candidate is integrated
into production or qualified on physical hardware. Persistent desktop events,
focus, pointer input, VDC bitmap presentation and physical performance remain
open. The main USB regression is qualified separately.

Read-only audits:

```
python3 verify-package.py
python3 verify-display.py
python3 verify-layout.py
sha256sum --check --quiet SHA256SUMS
```

The first three auditors accept `--record` to derive reports. To reproduce CPU
runs, overlay `source/` on the pinned display archive's `frozen/` tree and use
Python with py65 (recorded environment: Python 3.14.7, py65 1.2.0). Run
`tests/ci_native_graphics.py`, `tests/ci_native_glyph.py`,
`tests/ci_native_graphics_text.py`, `tests/ci_native_graphics_clip.py` and
`tests/ci_native_graphics_layout.py`. The retained emulator harness and exact
client are in `display-emulator/`.
