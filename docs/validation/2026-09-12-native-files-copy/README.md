# Native suite Files copy — 2026-09-12

The native Files app now copies a selected file to another IEC device or an
Ultimate absolute path. C opens the copy dialog; Tab opens its destination
picker, F1 selects device/DOS context, F3 selects format and F5 selects IEC
file type. Both suite disks contain the complete app and inline picker.
The 20,793-byte PRG reserves 82 pages, plus the existing 37-page browser cache.
Both 8 KiB workspace allocations can remain live.

Copies use exclusive creation and 512-byte transfers with 32-bit progress.
The new file is closed and both files are reopened. Every byte and the final
length are compared before success is shown. Esc cancels at transfer boundaries.
Failed/cancelled output remains available for inspection; uncertain writes are
not replayed or deleted. Failed closes and picker cleanup retain their handles
for retry. The source file and browser preferences are preserved. Changing the
destination clears the previous result. The copy dialog restores all 256 bytes
of the ROM function-key table before returning to Files. Esc from either IEC
or Ultimate Files now returns to the suite desktop.

The CPU run passes 26 copy cases and 90 complete display frames. It covers
SEQ/PRG/USR, files beyond 64 KiB, same-drive and cross-drive copies, both
Ultimate directions and contexts, full raw filenames, folder selection,
preexisting workspace buffers, existing destinations, source read failures,
short writes, cancellation in both phases, reopened corruption/truncation/extra
tails, foreign contexts, failed cursor abort and retained close recovery.
Eight unchanged diagnostic-browser cases also pass. These CPU models do not
replace native file routines, but model IEC devices and Ultimate DOS replies.

VICE uses the actual C128 ROM, true IEC drives on devices 8/9/10 and CPU-based
VIC/VDC capture. It copies and independently exports 66,058 bytes and a raw PRG
from one D81 to another. It checks exclusive-name refusal, destination picking,
ROM programmable-key expansion, restored key tables, both screens, repeated
desktop return and all 426 heap pages released. Its 109 captures contain 319
chunks, 147,101 copied bytes and 436 matching borrower before/after pairs, with
no rejected captures. Ten complete copy frame pairs are audited offline.

Zero-byte copies to Ultimate storage pass. Zero-byte IEC output is refused
before creating a destination. The first VICE run exposed the standard drive
DOS behavior: closing an unwritten file inserts a carriage return. The full
comparison correctly reported a mismatch. The supplied Commodore source's
`clswrt` routine confirms this for 1541, 1571 and 1581. The native API currently
has no truncate operation. Those source references and the original failed
run are retained. A subsequent message-encoding failure and its correction
are also retained under `preliminary/`.

The CPU report initially listed the desktop kernel hash, although its inherited
machine loads the workspace kernel. Only that report field was corrected;
the original report and executed test source are retained. The verifier checks
that all cases, counters and other results are unchanged. The maintained test
now hashes its actual `KERNEL_IMAGE`. VICE qualifies the desktop kernel.

`inputs/` freezes 407 source/helper/generated files. The main checkout rebuilt
all 21 native PRG/D64 images byte for byte. Only Files and the two suite disks
change their program/image bytes relative to signed base
`3b4847e8070e7ed1d63e324f5b971442647d2660`. Both kernels, the diagnostic browser,
editor/modules, calculator, Ultimate and Claude PRGs are unchanged.

Run `python3 -B verify.py` to audit the sealed archive, inputs, packaged apps,
CPU reports, capture chunks/restoration, complete copy screens, raw D81 file
chains, independently exported files, resident bytes and final heap state.
`main-rebuild.json` records the integration comparison.

No physical C128 access, deployment, modem change or push occurred. Native
zero-byte IEC creation, rename/delete, folder/batch copying, removable-media
identity, resumable recovery and physical qualification remain roadmap work.
