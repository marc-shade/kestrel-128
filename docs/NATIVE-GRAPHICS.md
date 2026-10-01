# Native graphics and desktop

The ABI 1.11 desktop starts in C128 native mode and launches Calculator, Text
Editor, Files, Ultimate, [Claude](../apps/claude/README.md), and [Paint](NATIVE-PAINT.md). It presents a 320×200 VIC bitmap and a
[640×200 VDC graphical launcher](NATIVE-VDC-DESKTOP.md). Apps use the existing owner-checked heap, file and module
services. The dispatcher releases the desktop before loading an app and reloads
it when the app returns. [Calculator](NATIVE-CALCULATOR.md) shares the blue
bitmap, yellow buttons and mouse controls, including its history and save
dialog. The desktop keeps its selected app across app and
workspace returns for the current session.

Paint uses the same blue interface with drawing tools, a color palette, and
Save As and unsaved-picture dialogs. Its full picture remains in a separate
banked allocation while the viewport or file picker is shown. The blue
desktop is the intended common interface for the native apps.

[Files](NATIVE-FILES-GUI.md) now shares the blue bitmap, yellow focus and 1351
controls for its list, byte viewer, device/path fields and verified copy dialog.
Its permanent core owns the keyboard and file state while checked graphics and
picker modules alternate in one window. Returning from the picker reloads the
graphical copy dialog. Ordinary field edits repaint changed cells and the caret.
[Editor](NATIVE-EDITOR-GUI.md) now shares the same controls for document caret
placement, file dialogs and Find/Replace. Its banked document remains allocated
while the shared picker replaces the graphics module. The
[shared picker](NATIVE-PICKER-GUI.md) and [Claude frame](NATIVE-CLAUDE-GUI.md)
now use the same blue VIC controls. Calculator also uses the shared VDC lifetime
and incremental surface presenter. VDC graphics in the other apps require
further work within their tighter code and document-memory budgets.

The preceding desktop software qualification and the [full ABI 1.9 physical workflow](validation/2026-09-12-native-desktop-abi19-hardware/README.md)
pass. The C128 run verifies all three app handoffs, retained selection, complete
display RAM, mode restoration and cleanup. Physical video pixels remain a
separate gate. Earlier interruptions remain in the [hardware history](validation/2026-09-11-native-desktop-hardware/README.md).
The subsequent [focused capture diagnosis](validation/2026-09-12-native-capture-transport/README.md)
retains another restored failure and a reproducible observer guard defect:
a nested C128 ROM interrupt can legitimately save MMU `$00`. Earlier captured
byte differences remain unexplained.
The [next context experiment](validation/2026-09-12-native-capture-context/README.md)
qualifies nested RAM/VDC observation in VICE and retains a physical run with
exact boot display payloads. That run failed a strict comparison of three ABI
bytes, including the consumed-key counter and last key, and fully restored
the original deployment. The [pinned Commodore source](COMMODORE-SOURCE-REFERENCE.md)
confirms the ROM interrupt mapping and editor `CLI` path. The later complete
physical pass retains 12 successful captures interrupted with MMU `$00`.
The [observer integration](validation/2026-09-12-native-observer-integration/README.md)
now applies these mapping and evidence fixes in production. The complete
desktop/app sequence passes in VICE with 66 restored captures; physical mode
snapshots use the same pause context and failed workflows complete verified
cleanup before returning their error.

## Build and controls

```sh
python3 -B build-native-desktop.py
x128 -default -40col -8 target/native-desktop/kestrel.d64 -drive8true -drive8type 1541
```

The builder retains three distinct boot disks:

| Disk | Initial view | B from the diagnostic workspace |
|---|---|---|
| `target/native-desktop/kestrel.d64` | Graphical desktop | Desktop |
| `target/native-desktop/workspace.d64` | Diagnostic workspace | Desktop |
| `target/native/kestrel.d64` | Diagnostic workspace | Original Files and Apps browser |

Use arrows or Tab to select an app, Home to select Calculator, and Enter to
open the selection. C, E, F, U, A, P and S open Calculator, Editor, Files, Ultimate,
Claude, Paint and Sheet directly. A 1351 mouse in control port 1 selects app cards on both displays on
movement; press and release the left button on the same button to open it.
Moving off the button before release cancels the launch. A stationary mouse
preserves keyboard selection. The 64 KiB VDC highlights the selected card in
yellow; the 16 KiB VDC uses white graphics on blue and a selection arrow.
Escape returns to the diagnostic workspace. When graphics cannot be reserved
or the current display configuration is unsupported, the same desktop controls
remain available as text on both consoles. A missing app reports its load error
and returns to the desktop. A missing desktop leaves a usable workspace.

Arrow/Tab selection and C/E/F/U/A/P/S shortcuts update `N_DESKTOPSEL` at `$3d2f`:
0 Calculator, 1 Editor, 2 Files, 3 Ultimate, 4 Claude, 5 Paint, 6 Sheet. A reloaded desktop restores that selection
in both graphics and text fallback; values outside 0–6 recover to Calculator.
Native restart clears the selection. This uses an existing mailbox byte and
uses 34 app pages, 36 VIC surface pages and the shared VDC component. Selection is
session state; preferences saved across restarts remain roadmap work.
The [selection checkpoint](validation/2026-09-12-native-desktop-selection/README.md)
records the ABI 1.9 build, compatibility checks and complete app/workspace
return workflows.

On a physical C128, mount the desktop disk on device 8 and boot in native mode.
The Ultimate PRG runner enters C64 mode; use native disk boot for this kernel.
The physical workflow in `hw_ultimate_check.py --native-desktop` is still
admitted only for its frozen ABI 1.9 images. A new frozen candidate is required
before qualifying the current ABI 1.14 suite and VDC desktop on the physical machine.

The desktop PRG occupies 34 app pages and reserves 36 VIC surface pages plus
the 39-page [bank-1 VDC component](NATIVE-VDC-SERVICE.md). REU snapshot backing
leaves 317 of the 426 managed pages free; RAM backing leaves 253 or 245 with
a 16 or 64 KiB VDC.
All desktop allocations are released before an app handoff; VDC memory and
registers are restored before the snapshot is freed. There is one foreground app; desktop preferences saved across restarts, broader widgets and menus,
overlapping windows and styled-document layout
remain roadmap work.

## Presentation lifetime

Include [`src/native/api.inc`](../src/native/api.inc). Declare minimum ABI 1.8
in an app that calls the presentation services.

| Service | Address | Contract |
|---|---:|---|
| `N_VSHOW` | `$1c68` | Present the current app's initialized 36-page allocation at bank 0 `$c000..$e3ff`; supply `N_OWNER` and the four-byte `N_HANDLE` |
| `N_VCLOSE` | `$1c6b` | Restore the saved text display while retaining the allocation |

Reserve the surface early using `N_RESERVE` with bank 0, page `$c0`, 36 pages
and the current app owner. The surface must exist as one exact allocation.
Free space elsewhere cannot satisfy a reservation blocked by an allocation at
`$d000`. A failed reservation must leave the app able to continue in text mode.

Initialize the surface through the heap transfer services before `N_VSHOW`.
Bitmap bytes occupy offsets 0–7999; offsets 8192–9191 hold the 40×25 color
attributes. The allocation also includes the intervening and trailing padding.
For pixel `(x,y)`, the bitmap byte offset is `(y//8)*320+(x//8)*8+y%8`, and its
bit is `128>>(x%8)`. An attribute byte supplies foreground in its upper nibble
and background in its lower nibble.

Presentation requires a valid running app, its current owner, a consistent
allocation record, enabled interrupts, the supported native memory mapping,
text display state, a raster IRQ mask of one, no active sprites, and output
direction on the VIC bank-select pins. Refusal returns a native status in A
with carry set. Existing presentation or a busy heap/file/UI operation returns
`N_REENTRANT`; unsupported display state returns `N_PLATFORM`. Handle, owner,
range and metadata failures use their corresponding native statuses.

The resident teardown restores text before a visible allocation is freed or
its owner is released. App return, explicit exit and replacement follow the
same cleanup path. Teardown precedes file cleanup even when an uncertain file
close retains app ownership. It needs no disk access or dynamically loaded code.
Closing twice is harmless for the valid current app. It does not free pages.

## Drawing library

Include [`graphics-core.inc`](../src/native/graphics/graphics-core.inc) after
the native API definitions, and optionally include
[`text-core.inc`](../src/native/graphics/text-core.inc). Keep the code and its
state in the app's writable allocation or a declared module window. The
complete library with the original 8×8 ASCII font occupies 2,685 bytes. The
[desktop source](../src/native/desktop.asm) is a complete caller.

| Entry | Inputs and behavior |
|---|---|
| `gfx_bind` | `N_OWNER`, `N_HANDLE`; validate access through byte 9215 and retain the handle; reset the clip to the full surface on success |
| `gfx_set_clip` | Signed little-endian 16-bit `gfx_x0`, `gfx_y0`, `gfx_x1`, `gfx_y1`; set a half-open pixel clip intersected with the surface |
| `gfx_rect` | The same half-open pixel bounds; `gfx_pen` 0 clears, 1 sets, 2 XORs |
| `gfx_colors` | Half-open bounds in 40×25 attribute cells; fill with `gfx_color` |
| `gfx_glyph` | Signed pixel origin `gfx_x0`, `gfx_y0` and eight rows in `gfx_bits`; pens 0/1/2 affect ink pixels, pen 3 replaces the clipped glyph rectangle |
| `gfx_text` | Signed origin, pen 0–3, at most 64 bytes in `gfx_text_buffer` and `gfx_text_length`; advance x by eight per byte, saturating at 32767 |

Drawing clips signed coordinates without wrapping extreme values into the
surface. Empty or inverted bounds perform no transfer. Attribute clipping
rounds inward to complete 8×8 cells, preserving colors outside the pixel clip.
Text replaces bytes outside printable ASCII with `?`. Drawing can target an
owned logical surface in either RAM bank; presentation currently requires the
fixed bank-0 surface described above.

Calls return A=0 with carry clear on success, otherwise a native status with
carry set; `gfx_error` retains the result. Decimal and interrupt flags are
preserved. Other registers, heap argument mailboxes and `N_BUFFER` are scratch.
The library stores one binding and clip, uses writable operands, and accepts
foreground calls only. Busy-state refusal precedes drawing. An attempted bind
that reaches handle validation invalidates the old binding on failure; a busy
refusal preserves it. Heap services revalidate the retained handle on transfers.

## Verification

The source and captured evidence are linked from the
[desktop migration record](NATIVE-DESKTOP-MIGRATION.md). CPU model, emulator
pixels and physical CPU captures are distinct evidence. The hardware workflow
captures complete surface RAM, VDC cells and CPU mode registers; it does not
capture physical video pixels.

```sh
python3 -B build-native-desktop.py
python3 -B build-native-graphics.py
python3 -B tests/ci_native_desktop.py --desktop-boot --report /tmp/desktop-cpu.json
python3 -B tests/ci_native_graphics.py
python3 -B tests/ci_native_glyph.py
python3 -B tests/ci_native_graphics_text.py
python3 -B tests/ci_native_graphics_clip.py
python3 -u tests/run_ci.py nativedesktop nativedesktopworkspace nativedesktop80 nativedesktopmissingapp nativedesktopmissing nativedesktopsequence
```

CPU suites require py65 and the local C128 KERNAL ROM used by the existing
native tests. Builders use Python 3, 64tass and VICE's `c1541`; emulator suites
use VICE and the existing Xvfb/ImageMagick capture tools. Reports retain image
hashes. The running-code audit compares all immutable resident bytes and saves
every declared mutable byte separately.

The [ABI 1.10 suite qualification](validation/2026-09-12-native-claude-suite/README.md)
retains 30 native CPU suites, 24 desktop CPU workflows, 34 host checks and four
VICE workflows, including both serial exit paths and 1,920,000 checked VIC
pixels. The new apps have not yet been qualified on the physical C128.

## Native desktop pointer

The blue native desktop is the intended primary Kestrel shell. The native
diagnostic workspace still serves testing and recovery workflows. Returning from a native suite app reloads the
blue desktop; Escape explicitly opens the workspace. The broader migration is
tracked in [Native desktop migration](NATIVE-DESKTOP-MIGRATION.md).

The desktop now reads a proportional 1351 mouse on control port 1. It samples
once per ROM jiffy in raster lines 80–159, allowing at least another 32
raster lines after noticing the jiffy before reading the SID. A delayed ROM
interrupt restarts this interval; a late frame is skipped. This allows conversion
to settle even when the keyboard scan occurred later than its usual line 255.
The scan restores CIA1 port A to `$7f`. It preserves
CIA direction registers and briefly releases both keyboard column sets to read
the left button. No IRQ handler is added. A shared ROM key-check callback
filters ambiguous button transitions using the owned function-key table's
unused tail; the previous callback and all 256 table bytes are restored at
pointer close. Paint retains that keyboard ownership across its text picker.
Other CIA
configurations and absent/out-of-range POT readings suspend the pointer and
cancel an armed click. Attachment/reconnection establishes a fresh baseline;
a button held during attachment cannot launch an app. Two counter units move
one pixel; +/-1 jitter does not consume the subpixel remainder.

Two single-color sprites form a white arrow with a black outline. Their 128
bytes occupy unused bitmap padding `$df40..$dfbf`; two sprite pointers occupy
unused screen-matrix padding `$e3f8..$e3f9`, all within the existing owned
36-page surface. The desktop saves and restores all 12 sprite registers it
changes and the BASIC sprite-hook flags before app/workspace handoff or a
graphics failure. It does not add resident kernel services or heap allocations.
The desktop PRG reserves 26 pages, leaving 364 pages free with its surface.

The initial software evidence is in the [pointer qualification record](validation/2026-09-12-native-pointer/README.md).
The [Paint and shared-input record](validation/2026-09-13-native-paint/README.md)
rechecks the six-entry desktop and the shared keyboard callback.
For VICE mouse input, add `-controlport1device 3 -mouse`. Use
`-soundwarpmode 1` with warp mode so the SID mouse inputs remain emulated.
Run `tests/ci_native_pointer.py` with the py65 environment for protocol/gesture
checks, and `python3 -B tests/ci_native_pointer_iec.py` for actual VICE mouse and
ROM keyboard input; `--80col` starts with the other console selected.
The native [keyboard guard](NATIVE-KEYBOARD.md) continues to reject control-port
signals that the ROM reports as out-of-matrix keys. Holding a mouse button may
suppress simultaneous physical keys because they share CIA lines; keyboard
navigation between clicks is qualified. Physical mouse/adapter tests, port 2,
right-button menus, dragging objects, acceleration and VDC graphical pointer
presentation remain open. This is desktop button input, not yet a shared app
widget/window system.
