# Isolated native display lifetime candidate

This candidate is separate from `<home>/geos128/uos`. The main tree still
contains the owned-abort change whose physical USB reopen failure is under
investigation; IEC qualification remains pending.
No display code from this directory has been applied to the main tree or to
the physical machine.

The experimental ABI 1.8 adds `N_VSHOW` at `$1c68` and `N_VCLOSE` at `$1c6b`.
Both use the ordinary heap result convention, including `N_ERROR` and preserved
decimal/interrupt flags. VSHOW additionally requires interrupts enabled.

VSHOW takes the current app's `N_OWNER` and `N_HANDLE`. The allocation must be
exactly 36 pages in bank 0 at `$c000..$e3ff`; the app initializes it first using
the checked transfer APIs. The bitmap occupies the first 8,192 bytes and the
matrix the last 1,024. VSHOW validates the app allocation/generation and every
app page, then the surface handle/generation and every surface page. It rejects
other owners, layouts, an existing presentation, busy file/field services,
unsupported native mapping, existing graphics/multicolor modes, active sprites,
and unsuitable port directions or interrupt masks before changing display
registers.

The presentation establishes a 320×200 high-resolution bitmap and preserves the
prior text geometry, matrix register, VIC bank and relevant processor-port bits.
It keeps the standard native raster comparison at 255 and lets the C128 KERNAL
continue its IRQ service using its `$d8 = $ff` display-skip state. The first
placement experiment demonstrated why both that IRQ mode and the processor-port
character-ROM selection are necessary.

VCLOSE restores text and keeps the surface allocated. It is idempotent for a
valid running app. The caller may free the allocation separately. The resident
`heap_clear_record` hook restores presentation before any visible page becomes
free; unsuccessful stale, foreign or corrupt frees retain the presentation.
`app_cleanup` independently restores text before file/heap cleanup, including
paths that retain ownership after a cleanup error. Teardown reads no app code,
performs no allocation and needs no file/device access.

Native app minimum ABI 1.8 is accepted. Native modules now accept minimum ABI
1.7 or 1.8; older modules retain their exact format. Tests include a module
declaring 1.8 and calling VCLOSE. The future-version rejection fixtures use 1.9;
module versions below 1.7 remain invalid. The ABI 1.7 SDK example is unchanged.

All additional resident code fits already reserved space. No additional heap
page is reserved: the kernel still provides 426 pages. `build-native.py` records
the actual module and display intervals separately. The module-side gap before
`$4a00`, low-kernel padding, main-kernel padding and the service tail hold the
new code. Further desktop code must have its own layout and ownership budget.

`before-geometry-abi-review` preserves the earlier exact candidate and its
reports. That candidate passed 25 new CPU groups, heap/app/field/module
regressions and five VICE presentation workflows. The revised candidate fixes
bitmap geometry, refuses active sprites and accepts module minimum ABI 1.8.
It passes 27 display CPU groups (1,409 modeled interrupts), 113 module cases,
55 Ultimate-loader cases, and the five presentation workflows again.

The revised emulator evidence is at
`/var/tmp/arc-scratch/uos-native-vic-placement-qiqkzhob`. Three workflows verify
normal return, explicit exit and freeing a visible allocation. Two more read and
check a 513-byte IEC file while graphics remain active, then perform a missing
app replacement or replace the display client with the text calculator. All
five compare the complete 64,000 rendered pixels; both text consoles and the
surface ownership are checked after exit/replacement. VICE's observed four-byte
canvas-length discrepancy remains recorded; all active pixels are present and
no padding is inserted.

The full 25-suite CPU qualification and ten ordinary native emulator workflows
passed from a 218-file frozen input set under
`/var/tmp/arc-scratch/uos-native-display-qualification`. The first two current
CPU reports are retained; the other 23 suites are executed there. Previous
candidate reports are not counted as passes for this revised image.

This is still a prototype. Production integration, physical observations,
native clipped drawing/text, VDC graphics, pointer/window events and the large
document with simultaneous desktop allocations remain open. The graphics
client is a test pattern, not a desktop or a user-facing app.
