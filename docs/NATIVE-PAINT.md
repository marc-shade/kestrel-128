# Native Paint

Paint is the sixth app on the native blue desktop. Press **P**, or click its
brush icon. Both `target/native-desktop/kestrel.d64` and `workspace.d64` include
the app; build them with `python3 -B build-native-desktop.py`.

Paint keeps a complete 320×200 hires picture in bank 1. Both displays show
the same 256×144 viewport, tool buttons, ink palette and file dialogs. The VDC
scales each horizontal pixel to two pixels. A 64 KiB VDC shows colors and yellow
focus; a 16 KiB VDC uses contrasting monochrome graphics. The keyboard brush
is visible without a mouse. Keep `VDSVC.PRG` beside Paint when copying the app.

## Drawing

| Control | Action |
|---|---|
| Left mouse button in the picture | Draw a connected pencil or eraser stroke |
| Pen / P; Eras / E | Select pencil or eraser |
| Color chip; + / − | Choose ink color |
| Cursor keys | Move the visible keyboard brush by one pixel; scroll at viewport edges |
| Home | Move to the picture's top-left |
| R | Refresh the picture and retry VDC setup after fallback |
| Space | Draw or erase one pixel at the keyboard brush |
| Tab, then Enter | Select and activate a control |
| Undo / U | Toggle the most recent edit between undo and redo |
| Clr / C | Clear the picture; Undo restores it |
| Save / S | Save As to a new file |
| Open / O | Choose a picture through the shared file picker |
| X / Esc | Close; an unsaved picture offers Discard or Keep |

Hires colors apply to 8×8 cells. Changing a pixel's ink color also changes the
foreground color of other pixels in that cell. Erasing preserves cell colors.
New pictures have white ink and black paper; Clear restores that blank picture.

One mouse gesture is one undo step, including connected segments between
samples. Leaving the canvas breaks the connecting segment. Releasing the
button ends the gesture. A button already held when a mouse attaches or
reconnects cannot begin drawing. Keyboard points each get their own undo step.
Clearing an already blank picture preserves the useful undo record.

## Files

In Save As, enter a name and press Enter or click Save. **Tab** opens the
[shared file picker](NATIVE-FILE-DIALOGS.md), where you can choose an IEC device
8–30 with D64/D71/D81 geometry, or Ultimate DOS context 1/2 and a folder.
Use **S** in the picker to choose the current device/folder. Back in Save As,
edit the proposed name before saving. Ctrl-U clears the field; cursor keys,
Home, insertion, and deletion use the shared field editor. Esc or Cancel
returns to the picture. The picker uses the same blue graphical controls on both displays.

Files are created exclusively. An existing destination is preserved. A save
succeeds only after closing the file, reopening it, comparing every byte and
the final length, and closing again. Esc cancels at transfer boundaries;
a new file from an interrupted save may remain incomplete. Paint preserves
the unsaved indication after a failed or cancelled save. Undoing a successful
save marks the changed picture as unsaved again.

Open checks a separate staging picture before replacing the current one.
Truncation, trailing data, an unsupported header, checksum failure, cancellation,
or a failed close leaves the current picture and undo intact. A successful
Open makes the preceding picture available through Undo. An unsaved picture
requires an explicit choice before Open proceeds.

The app reserves a separate display allocation and restores the pointer,
display mode, keyboard callback, and complete ROM function-key table before
returning to the desktop. If the display is occupied or unsupported, both text consoles retain
file controls and coordinate-based keyboard drawing. Picture and undo storage
remain independent of the picker and display.

## UPNT version 1

The native picture file contains exactly 9,016 bytes. The optional `.UPNT`
extension is a naming convention; Open validates the contents.

| Offset | Bytes | Value |
|---|---:|---|
| 0 | 4 | ASCII `UPNT` |
| 4 | 1 | Version 1 |
| 5 | 1 | Flags 0 |
| 6 | 2 | Width 320, little endian |
| 8 | 2 | Height 200, little endian |
| 10 | 2 | Payload length 9,000, little endian |
| 12 | 2 | CRC-16/CCITT, polynomial `$1021`, initial `$ffff`, little endian |
| 14 | 2 | Reserved, both zero |
| 16 | 8,000 | VIC hires bitmap order |
| 8,016 | 1,000 | Row-major 40×25 foreground/background attributes |

The CRC covers the complete 9,000-byte payload. The bitmap offset for pixel
`(x,y)` is `(y//8)*320 + (x//8)*8 + y%8`, with mask `128 >> (x%8)`.
An attribute has foreground in the high nibble and paper in the low nibble.
The host codec is [`native_paint_format.py`](../native_paint_format.py).
Display controls, sprites, and memory padding are excluded from the file.

Paint uses 96 app pages, two 36-page document allocations, a 36-page VIC
surface, ten bank-0 scratch pages and the shared 39-page VDC component. REU
screen backing leaves 173 of the 426 managed pages free while drawing. Main-RAM
backing leaves 109 pages with a 16 KiB VDC or 101 with 64 KiB. Open needs
another 36 bank-1 pages temporarily; the [graphical picker](NATIVE-PICKER-GUI.md)
shares the display, font and pointer and uses transient directory caches.

ABI 1.14 adds [opening selected pictures from Files](NATIVE-DOCUMENT-LAUNCH.md).
Paint validates the complete picture before replacing its blank document, and
closing it returns to Files at the selected name. The expanded PRG is 24,387
bytes; the packed PRG is 16,856 bytes. Compact font storage reconstructs the
original glyphs for both the app and its shared picker.

The app reserves `$5000..$59ff` before installing input controls. It stores
picker scratch, file comparison data, saved function keys and rendering buffers
there. A conflicting allocation refuses startup without changing that owner's
data. Editable filename/path fields stay inside the app allocation.

Paint retains one VDC component and original-screen backup through drawing,
dialogs and the picker. If a VDC transfer fails, edits and file actions pause.
Escape retries screen restoration; it still follows the normal dirty-picture
confirmation once restoration succeeds. The picture and undo remain owned.
R can then reopen the graphical VDC view. A failed picker surface restores
the VDC before drawing fallback text. Missing hardware or components retain
VIC drawing and text controls.

The [original software record](validation/2026-09-13-native-paint/README.md)
records the first Paint app. The [graphical VDC qualification](validation/2026-09-13-native-paint-vdc/README.md)
retains the current program, complete dual-display workflows, screen and REU
restoration evidence, scratch ownership checks and the independent rebuild.
Physical Paint timing, mouse behavior, and file/device qualification remain
open. So do native-width VDC tools, more drawing tools and patterns, selection/clipboard,
zoom, multiple undo levels, printing, and GEOS/Commodore image import/export.
These display changes do not complete APP-PAINT or the wider OS roadmap.

## Keyboard and mouse line sharing

The port-1 button pulls a keyboard row line low. A transition during the ROM's
scan can otherwise decode as an ordinary key. Desktop, Calculator and Paint
share a small filter in the unused tail of the function-key table they own.
It rejects an
ambiguous candidate while that line is held, and rechecks the candidate's
physical matrix column after release. Other candidates chain to the existing
native guard. CIA columns are restored; the filter changes no IRQ vector,
zero-page workspace, or MMU mapping. The prior keyboard callback and all 256
function-key bytes are restored together before exit. Paint retains that
ownership while its graphical picker is open; the other two clients release it
when closing their pointer/display controls.

The [pinned Commodore editor source](COMMODORE-SOURCE-REFERENCE.md), especially
`EDITOR_C128/ed3.src`, supplies the matrix scan and callback contract. Software
tests cover real row-line transitions in VICE and all scan ordinals in both
ROM and application mappings. Simultaneous typing while dragging and physical
mouse/adapter qualification remain broader input-driver work.
