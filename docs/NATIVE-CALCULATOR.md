# Native graphical Calculator

The Calculator on both native desktop suite disks uses the desktop's blue
bitmap, yellow focused buttons and port-1 1351 pointer. It has a numeric
keypad, arithmetic operators, Delete, Clear, history paging, Save and Close.
The VDC now shows the same controls at 640×200, with yellow focus on a 64 KiB
VDC or a bright reverse selection on a 16 KiB VDC. Returning from Calculator
reloads the blue desktop. The original text view remains the fallback when
VDC graphics cannot be opened.

Use digits, `+ - * /`, Enter or `=`, Delete and C as before. Tab or arrows
move button focus; Space presses that button. Mouse movement focuses a button;
press and release on the same button activates it. A stationary pointer leaves
keyboard focus alone. Dragging to another button cancels the press.

S or Save opens the filename dialog. Type a name, use the existing cursor and
editing keys, then Enter or the Save button. Tab selects Save or Cancel; Enter
confirms that choice. Escape or Cancel returns to Calculator. Saving retains
the existing exclusive-create and reopen/compare verification; an existing
file is preserved and a failed write keeps its failure status. N/B and the
Older/Newer buttons page through the 32 retained results.

This remains an unsigned 16-bit integer calculator with immediate operation
evaluation, overflow and division-by-zero reporting. Scientific/decimal modes,
history import and persistent sessions remain in the roadmap. The window is
fixed; desktop window management is still open.

## Memory and shared controls

The suite Calculator uses 49 app pages, the 39-page bank-1
[shared VDC component](NATIVE-VDC-SERVICE.md), a two-page history in bank 1 and the
existing 36-page VIC surface at bank 0 `$c000..$e3ff`. Saving the original VDC
contents uses an available [REU](NATIVE-REU.md), leaving 300 of the 426 managed
main-RAM pages free. Without an REU it takes another 64 pages on a 16 KiB VDC
or 72 on a 64 KiB VDC, leaving 236 or 228 pages free. Display and mouse ownership end
before app exit or a history failure. A stalled VDC restore retains all owners
and blocks exit; Escape retries it. A fatal history error also retains its
original exit code and accepts only Escape until recovery succeeds.
REU snapshot-read or capacity-probe restoration failures use the same retained
recovery path. An absent or already active REU uses the main-RAM fallback.
An occupied VIC surface or unsupported display configuration
releases any temporary surface and runs the original controls on both text
consoles. The standalone diagnostic disk retains the original 16-page text
Calculator; its program bytes are unchanged.

`src/native/input/pointer.inc` is shared by Desktop, Calculator and Paint. The
caller supplies its surface selector, hit-test callback and control count;
events distinguish focus from activation. Each caller handles its own app or
dialog actions. The qualified sampling delay, reconnect baseline and exact
sprite/CIA/BASIC-hook restoration remain in the driver. The shared keyboard
ownership code also filters port-1 button transitions at the ROM key-check
callback and restores the prior callback and complete function-key table.

`src/native/graphics/buttons.inc` supplies rectangular hit testing and focus
colors on the bound surface. Callers provide the selected index and a static
table of fewer than 32 on-screen rectangles. Focus painting requires edges on
8-pixel cell boundaries. Dialogs restrict the active index interval, so covered
calculator controls cannot receive clicks. The graphics scene interpreters
are shared as well; each application retains its own layout tables.

The builder generates Calculator's scenes and hit rectangles from
`native_calc_scene.py`, which also contains the independent bitmap oracle.
Neither resident kernel grows and no persistent desktop allocation is added.

Keep `VDSVC.PRG` beside Calculator when copying the app to another source.
The component loads from the original app disk/directory before borrowing VDC
state. A missing component leaves the existing VIC and text controls usable.

The shared `graphics/vdc-lifetime.inc` and `vdc-pointer.inc` run in bank 1 and handle the saved
display, bounded port waits and pointer. `vdc-mirror.inc` reads the owned VIC
surface through `N_READ`, doubles each horizontal pixel and converts the color
cells to VDC RGBI attributes. On a 16 KiB VDC, relative foreground/background
brightness controls monochrome reversal so button focus remains visible.
The graphics primitives flag changed eight-line rows; presentation clears each
flag only after that complete row has been written. Pointer movement uploads
only the old and new pointer footprints. Calculator avoids repainting history
when its count, head and visible page have not changed. ROM text output is
suppressed while any VDC recovery phase remains owned.

The [packed boot file](NATIVE-BOOT-MEDIA.md) recovers disk space for this added
app code while keeping all six applications on D64 and D81.

## Verification

The [graphical Calculator qualification](validation/2026-09-12-native-calc-gui/README.md)
records assembled arithmetic, mouse gestures, complete bitmaps, text mirrors,
save/cancel/failure behavior and cleanup. VICE exercises actual host mouse and
ROM keyboard input in both boot modes, saves a history file, compares all app
files on the disk and operates the five apps present at that checkpoint.
The [Paint and shared-input qualification](validation/2026-09-13-native-paint/README.md)
rechecks Calculator and its save dialog with the shared keyboard filter in
the expanded six-app suite. Physical C128 testing and deployment of this
revision remain pending.

```sh
python3 -B build-native-desktop.py
python3 -B tests/ci_native_calc_gui.py --report /tmp/calculator-gui.json
python3 -B tests/ci_native_pointer.py --report /tmp/pointer.json
python3 -B tests/ci_native_pointer_iec.py
python3 -B tests/ci_native_pointer_iec.py --80col
```

The CPU suites require the existing py65 environment. The VICE workflows use
private disk copies and X displays and perform no physical-machine I/O.
