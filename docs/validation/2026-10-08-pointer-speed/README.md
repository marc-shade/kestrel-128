# Mouse detection and pointer speed (2026-10-08)

## Why

Moving the pointer on the 80-column screen lagged. A Py65 profile (64 KiB
VDC, the pointer moving 6 logical pixels across and 3 down each frame) put
one moving frame at 21,297 cycles on the desktop and 38,796 in the Editor,
where a 1 MHz frame is about 16,700. Most of it was the VDC pointer redraw:
per move about 104 register selects, 123 data writes, 34 data reads and 609
status polls. The 40-column Editor spent most of its moving frame in the
kernel module gate, which walked the module's page map on every call.

Separately, the reference 1351 was not detected after it was plugged back in
([pointer start record](../2026-10-08-pointer-start/README.md)): port 1 read
POTX `$94`, POTY `$c5`, and the driver accepted only `$40..$bf`.

## Change

- **Mouse detection** (`input/pointer.inc`, generated `picker/pointer.inc`).
  Only `$ff` on either pot means no mouse (an open port, or a 1351 in
  joystick mode). A proportional 1351 keeps a 128-value window whose position
  depends on the mouse and the SID; this machine's spans about `$53..$d0`.
  Motion uses only differences.
- **Module gate** (`heap.inc`, `module-gate.inc`, `module-cache.inc`). Every
  heap page-owner change bumps a 16-bit `heap_epoch`; the gate repeats the
  page-ownership walk only when the epoch, the app handle or the module end
  changed since the last walk that passed.
- **VDC pointer** (`graphics/vdc-pointer.inc`, `vdc-lifetime.inc`,
  `vdc-state.inc`):
  - The arrow fits two bytes per row at every shift (shifts are 0, 2, 4
    or 6), so each row now reads and writes two bytes instead of three.
    `native_vdc_scene.py` asserts the shape keeps that property.
  - Register and data accesses test the ready bit inline and call the
    bounded wait only when the VDC is busy; the wait after selecting R31 is
    gone because the data access that follows waits.
  - Saved pixels are kept by screen row (slot = row mod 16), so a move that
    stays in the same byte column reuses them for the rows both positions
    cover instead of reading them back.
- **Scene packing** (`native_vdc_scene.py`). The 80-column desktop scene
  packer chooses the shortest parse in the same format (2,451 to 2,346
  bytes; decoder unchanged), which gives the VDC component the room for the
  pointer change. VDSVC is 9,931 of 9,984 bytes (39 pages).

## Measurements (Py65 model, cycles per moving frame)

| Case | Before | After |
|---|---:|---:|
| Desktop 80 columns, dx ±6, dy 3 | 21,297 | 17,466 |
| Editor 80 columns, dx ±6, dy 3 | 38,796 | 31,149 |
| Editor 40 columns, dx ±6, dy 3 | 7,163 | 3,627 |
| Editor 80 columns, dx ±2, dy 2 (without/with reuse) | 36,336 | 28,391 |
| Editor 80 columns, dy 3 only (without/with reuse) | 28,532 | 23,016 |

The two reuse rows compare builds with and without only the reuse change.
When every move changes byte column, the reuse bookkeeping costs about 3%.
The model reports the VDC busy for three status polls after every register
select and two after every data access, so it gives the inline ready test
almost no credit. On real hardware the remaining fixed cost per redraw is
the bank-1 call (about 4,700 cycles, 1,750 of them the code check).

## Tests

- `ci_native_pointer`: readings above `$bf` are a mouse; `$ff` on either axis
  is not. Fails on the previous build ("a 1351 reading $c5 is a mouse").
- `ci_native_modules`: the page walk is skipped while the heap epoch is
  unchanged and repeated after a change, which then catches a foreign page.
- `ci_native_vdc_desktop` core: small moves up, down, sideways and at the
  bottom and right edges check the whole bitmap after each move and the
  exact number of VDC data reads. Fails on a build without reuse (48 reads
  where 9 are expected) and on a broken slot index (bitmap mismatch).
- Full sweep (`tests/sweep_native.py` through the resumable driver, from a
  snapshot of this tree; the images in the commit are byte-identical to it):
  CPU 323/323, VICE 60/60.
- Hardware `--native-desktop` on these images: passed all eleven screens with
  the 1351 detected and the pointer drawn on both displays (262 busy IRQs
  over 717 captures). A first attempt stopped at the first screen when the
  desktop selection changed during the capture; the pointer had moved at
  least 9 pixels, more than the one-count jitter the driver ignores, so the
  mouse was most likely touched.

## Not verified

- The speed-up on real hardware. No cycle count was taken on the C128; how
  often its VDC is ready on the first status read decides how much the
  inline ready test saves.
- The bank-1 call overhead is unchanged.
