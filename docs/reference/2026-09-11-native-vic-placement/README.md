# Native VIC placement experiment

A disposable native client demonstrates a 36-page VIC surface above the editor:
bank-0 bitmap `$c000..$dfff` and matrix `$e000..$e3ff`. The corrected 468-byte
client uses four app pages. It reserves and initializes the surface through
the public native heap services, then changes VIC presentation. The kernel
and its production images were unchanged by this experiment.

Two presentations passed complete 9,216-byte surface comparisons and complete
320×200 rendered-pixel comparisons. Jiffies advanced across three observations
of each presentation. Explicit `N_EXIT` and normal return each restored the
processor port, VIC bank/mode, allocator ownership and both text consoles.
A reservation overlapping the workspace's existing allocation was refused;
the observed surface bytes and existing allocation were preserved.

This is a client that explicitly restores its own display. It does not supply
kernel-enforced display ownership, automatic recovery from an app that omits
teardown, replacement/failed-launch handling, clipped drawing, VDC graphics or
physical-hardware qualification. File operations while graphics are active and
the full editor document together with desktop storage remain untested here.

The preliminary read-only probe found raster IRQ mask 1, IRQ vector `$fa65`
and MMU `$d506 = $04`. In the installed, hash-recorded C128 KERNAL, `$fa65`
calls the display handler through `$c024 → $c194`. Setting the handler's `$d8`
mode byte to `$ff` skips its mode-register writes while IRQ service continues.
The client restricts entry to the observed native text setup; it retains the
text raster comparison at line 255 instead of treating a raster-counter read
as a saved comparison value.

The first 432-byte client passed RAM/restoration checks, but its screenshot
showed character ROM in the lower bitmap. The corrected client applies the
processor-port bit sequence used by that KERNAL's bitmap branch at `$c1bd`:
clear bit 1 and set bit 2, then restore those bits on return. Observed `$00/$01`
changed from `$2f/$73` to `$2f/$75` and back. The original client fails the new
pixel oracle: only 96 complete stripe rows match, against the required 200.
The original observations and this negative control are retained separately.

The rendered oracle reads VICE's indexed VIC canvas using its documented
[Display Get command](https://vice-emu.sourceforge.io/vice_13.html).
This installed build declares 104,448 pixel bytes but returns 104,444. Both
parser failures and their diagnostics are retained. The final check records
the four-byte discrepancy and checks all 64,000 active pixels present in the
received data; it adds no padding. The matching rectangle is `(32,35,320,200)`
within the reported 384×272 canvas. Host screenshots provide separate visual
evidence.

`probe` contains the initial native observations. `initial-client` preserves
the first execution, `first-canvas-parser-failure` and
`canvas-length-diagnostic` preserve the observer failures, `corrected` holds
the completed run, and `negative-control` retains the rejected original
client under the final oracle. Each includes its executed source. The native
disk copies contain this project's own programs; no reference GEOS disk or
system ROM image is included.

Run `python3 verify.py` here for a nonmutating rebuild and offline byte,
ownership, screen and rendered-pixel audit. `observations.json` records the
source disk/kernel hashes, installed tool and KERNAL hashes, and the remaining
integration gates. This experiment is separate from the 24 CPU suites and ten
emulator workflows qualifying the owned-abort kernel change.
