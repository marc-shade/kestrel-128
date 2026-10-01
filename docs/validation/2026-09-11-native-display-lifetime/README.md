# Isolated native display lifetime candidate

This experimental ABI 1.8 kernel gives a native app a checked VIC bitmap
presentation and restores text before its surface is freed or the app exits.
It has not been integrated into the production tree or run on physical hardware.
Its base includes the owned-abort follow-up whose physical USB reopen failure
remains under investigation.

The candidate passes all 25 CPU suites on its exact images, including 27 display
groups, 113 module cases and 55 Ultimate-loader cases. Two initial current-image
passes were retained; the other 23 suites were run from 218 frozen inputs.
The five dedicated VICE display workflows also pass, with a complete comparison
of all 64,000 active pixels in each presentation. All ten ordinary emulator
workflows pass. The [source patch](change.patch), exact inputs, reports and
raw observations are retained with a checksum manifest.

`N_VSHOW` at `$1c68` validates a running app and its initialized 36-page
bank-0 allocation at `$c000..$e3ff`. `N_VCLOSE` at `$1c6b` restores text while
keeping the allocation. The heap release path restores text before reclaiming
visible pages. App cleanup restores text before attempting file cleanup, even
when a failed cleanup retains ownership. Both direct exits, visible-surface
release, IEC reading under graphics and successful/missing app replacements
are exercised. The [design record](DISPLAY-PROTOTYPE.md) describes the limits.

The kernel remains within existing resident reservations and keeps all 426 heap
pages. The boot, calculator, browser, editor and picker programs are unchanged.
Modules declaring minimum ABI 1.7 or 1.8 are accepted; versions below 1.7 or
above 1.8 remain rejected. No drawing, window manager, pointer input or desktop
application parity is claimed by this test-pattern client.

The kernel SHA-256 is
`e1e6b6c3858d8f38c3d6986ffedc25acb06d74f2a442655342eda208322b66c0`;
the disk SHA-256 is
`d31b88f387b97219c687b14f6aed8cb9b8c3d41f3ca8d32068001db1af625a5f`.
`before-geometry-abi-review` retains the earlier candidate and its reports.
Those passes are not counted for the revised image. The revised candidate
establishes known bitmap geometry, rejects active sprites, and accepts module
minimum ABI 1.8.

[verify-package.py](verify-package.py) rebuilds the candidate privately, compares
all seven images and five disk members, verifies the CPU report/image mapping,
and checks the frozen inputs and memory bounds without changing them.
The observer suite reports its probe digest; that probe is rebuilt separately.
The eighteen legacy inputs and shared `cbm` runtime used by the test harness
are retained in `runtime` and recorded separately from the 218-file freeze.

[verify-emulators.py](verify-emulators.py) checks 530 CPU captures, 1,328 IRQ
chunks, 111 screen pairs, 219 RAM observations and 198,159 independently copied
file bytes. The RAM observations have no DMA disagreement.
[verify-dialogs.py](verify-dialogs.py) reconstructs all 66,056 bytes of each of
three retained documents. [verify-modules.py](verify-modules.py) checks source,
manifest and warm-token lifetime; the loaded module bodies were not separately
recaptured. [verify-display.py](verify-display.py) rebuilds the display client
and checks three complete surfaces, five complete pixel frames, nine workspace
screen pairs and seven application screen pairs. Its two replacement workflows
each verify a 513-byte IEC read while graphics are active.

VICE returned four fewer canvas-tail bytes than its declared length. All
64,000 active pixels are present in every retained frame; the oracle inserts
no padding. This observation and the initial ROM-overlay negative control are
documented in the [placement experiment](../../reference/2026-09-11-native-vic-placement/README.md).
Physical display behavior and the large document with simultaneous desktop
allocations remain unqualified.
