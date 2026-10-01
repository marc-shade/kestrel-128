# Native VDC graphical desktop

The native suite launcher now draws its blue desktop, seven app cards and mouse
pointer on the VDC at 640×200 as well as the VIC at 320×200. Calculator, Text
Editor, Files, Ultimate, Claude, Paint and Sheet use the same selection and launch
actions on both monitors. On a 64 KiB VDC the selected card is yellow. A
16 KiB VDC shows white graphics on blue with an arrow beside the selection;
the complete bitmap plus separate color attributes would exceed its RAM.

Build with `python3 -B build-native-desktop.py` and boot
`target/native-desktop/kestrel.d64` in C128 native mode. Arrows and Tab select;
Enter opens. C/E/F/U/A/P/S open the corresponding app. A 1351 mouse in control
port 1 moves both pointers; press and release on the same card to open it.
Escape opens the diagnostic workspace, and B returns to the blue launcher.
The VDC layout uses the extra width for app names and descriptions beside
each icon. It shares selection and input with the VIC; independent focus and
extended desktop roles remain future work.

The seven apps and the shared file picker already use blue VIC controls.
[Calculator](NATIVE-CALCULATOR.md), [Ultimate](NATIVE-ULTIMATE-CONTROLS.md),
[Paint](NATIVE-PAINT.md) and [Files](NATIVE-FILES-GUI.md) present their controls graphically on the VDC too,
including Paint's picture and the shared pickers in Ultimate, Paint and Files. Editor and
Claude's full terminal still use VDC text views.
App launch restores
the original VDC memory and registers before loading the app, and app return
reloads the graphical launcher. The green native workspace remains a
diagnostic view.

## Memory and display lifetime

The launcher uses the existing ABI 1.12 heap and dispatcher. The resident
kernel retains its bytes. The [shared VDC component](NATIVE-VDC-SERVICE.md),
containing the desktop renderer, lifetime and pointer code, runs in bank 1
in the foreground with interrupts
enabled and without borrowed zero-page scratch. Monitor sync timing remains
unchanged. Its supported entry state is 80×25 text with eight-pixel character
cells, eight raster lines per cell and no interlace. Register 23 must display
all eight lines: its last-raster value is inclusive, so seven is sufficient.

| Allocation | 16 KiB VDC | 64 KiB VDC |
|---|---:|---:|
| Launcher app | 35 pages | 35 pages |
| Bank-1 VDC component | 39 pages | 39 pages |
| VIC surface | 36 pages | 36 pages |
| Saved VDC memory without REU | 64 pages | 72 pages |
| Free managed pages without REU | 252 | 244 |
| Free managed pages with REU | 316 | 316 |
| Bitmap address | `$0000` | `$4000` |
| Attribute address | Disabled | `$8000` |
| Entire saved address range | `$0000..$3fff` | `$4000..$87ff` |

The expanded desktop program contains 8,833 bytes; its packed PRG is 7,362
bytes including the load address. The
[suite disks](NATIVE-BOOT-MEDIA.md) contain thirteen shipping files, including
`VDSVC.PRG`, with 93 free blocks on D64 and 2,589 on D81 before user documents. Use a
separate data disk or Ultimate storage for larger documents and pictures.
Qualification saves the small Calculator sample on the system disk. On D64,
Editor selects device 9 through the file picker; on D81 its sample also fits
on the system disk. The full search-module copy uses device 9, as does the
Paint picture with a D64 system disk.

Register 28 selects the VDC address arrangement; its bit 4 does not establish
physical RAM capacity. A reversible alias probe distinguishes 16 and 64 KiB
chips even when the incoming address arrangement differs. Both probe bytes
and all fourteen changed configuration registers have recovery state before
their first mutation. The complete memory snapshot is copied into an owned
REU allocation before the first bitmap write, or a native heap allocation when
an REU is unavailable. The RAM fallback currently places it in bank 1.

The driver saves registers 10, 12, 13, 18, 19, 20, 21, 24, 25, 26, 27, 28,
32 and 33. Registers 30 and 31 are command/data latches; replaying their old
values would issue new memory operations. Close first restores the entire
saved RAM range, then the configuration registers, with display control and
the update address restored last. Only then does it free the snapshot and
permit an app or workspace handoff.

Each register and data access has a bounded ready wait. A setup or drawing
timeout retains the recovery phase. If close also times out, the desktop
keeps its snapshot and blocks handoff; a later action retries the complete
restore. A partial register restore can change the address arrangement, so
each retry reinstates the snapshot's arrangement before copying RAM back.
Allocation refusal or unsupported text geometry restores any setup changes
and retains usable VIC graphics with VDC text. A refused VIC surface keeps
the existing text launcher on both displays.

## Rendering

The build-time [scene generator](../native_vdc_scene.py) emits a lossless
2,393-byte stream for the 16,000-byte bitmap. Literal runs, fills and earlier
nonoverlapping blocks map to VDC data writes and hardware fill/copy commands.
The independent scene renderer checks the expanded image. Selection updates
change the arrow and, on 64 KiB hardware, the card attributes. The software
pointer XORs a clipped arrow into the bitmap and restores its old pixels
before moving or redrawing selection. Its horizontal position is twice the
shared 320-pixel pointer coordinate.

The RAM layout and register behavior follow the Commodore
[C128 Programmer's Reference Guide](https://www.pagetable.com/docs/Commodore%20128%20Programmer%27s%20Reference%20Guide.pdf)
and [Mapping the Commodore 128](https://www.cubic.org/~doj/c64/mapping128.pdf).
The independent model also checks address aliasing, block counts and attribute
nibbles against pinned
[VICE VDC source](https://github.com/VICE-Team/svn-mirror/blob/86fb219f3214bf0dcbb74dc965bde4116109d388/vice/src/vdc/vdc-mem.c).
The [Commodore source reference](COMMODORE-SOURCE-REFERENCE.md) supplies the
native ROM/editor interrupt context. Emulator palette captures use the
[official binary monitor protocol](https://vice-emu.sourceforge.io/vice_13.html).

## Verification and next steps

The [software checkpoint](validation/2026-09-13-native-vdc-desktop/README.md)
retains exact images, CPU cases, VICE workflows, full palette frames and
byte-for-byte snapshot restoration before app handoff. The CPU model covers
both physical RAM sizes in both initial address arrangements, all six app
launches, selection, pointer clipping, allocation refusal and recovery from
setup, drawing and close stalls. Emulator captures check both full bitmaps
and their displayed pixels, alongside existing app workflows and final heap
cleanup. This change has not been run on physical hardware.

Calculator is the first app using the shared display lifetime and incremental
VIC-to-VDC presenter. Applying that code and snapshot to every app would exceed
current budgets: Editor with its large document and D81 picker uses 423 of
426 pages, its core/picker window has two spare bytes, and resident regions
are nearly full. Preserve that workload while designing display backing
storage, overlays and owned cleanup. Remaining VDC app views, app switching,
independent monitor focus, physical qualification and the remaining
[OS roadmap](IMPLEMENTATION-ROADMAP.md) remain open.
