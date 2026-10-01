# Atari TOS feature parity

The Kestrel completion bar is feature parity with Atari TOS: the GEM Desktop, the
GEM AES and VDI services applications use, desk accessories, and the GEMDOS,
BIOS and XBIOS system services. This document is the acceptance matrix. A row
is **Have** only when a checked build, a repeatable test and a validation
record exist; "the code is there" is not enough.

The matrix covers the native C128 system (`src/native/**`,
`build-native-desktop.py`). Status was surveyed from source and docs on
2026-09-25 and changes only with a linked validation record.

Status: **Have**, **Partial** (named piece missing), **Missing**, or
**Mapped** (ST hardware without a C128 equivalent; the row names the analog).

## Architectural constraints that shape the plan

- One foreground app runs in a 96-page (24 KiB) slot at `$6000..$bfff`. The
  desktop is itself an app that is unloaded while another app runs
  ([NATIVE-APPS](NATIVE-APPS.md)). Desk accessories, a Desk menu over other
  apps, and app switching need a resident or banked accessory design.
- The resident kernel has single-digit free bytes per region
  ([NATIVE-KERNEL](NATIVE-KERNEL.md)). New system services go in banked
  components or module windows, not in the resident image.
- The D64 suite has 16 free blocks; the D81 suite is the full-system medium
  (2,512 free blocks). New desktop features target the D81 build.

## A. GEM Desktop

| TOS feature | Status | Kestrel evidence / missing piece |
|---|---|---|
| Drive icons on the desktop | Have | [GEMDESK](GEM-DESKTOP.md): Boot, Drive 9 (D64/D71/D81 from its DOS identity), Trash, and USB when the Ultimate's DOS answers ([record](validation/2026-09-26-gemdesk-usb/README.md), [record](validation/2026-09-26-gemdesk-drive9/README.md)) |
| Trash can (drag to delete) | Have | GEMDESK: drop listing rows (every selected one) on Trash, confirm, delete on IEC (scratch count checked) or USB (`DELETE_FILE`, proven by `FILE_STAT` 82) ([record](validation/2026-09-26-gemdesk-files/README.md), [record](validation/2026-09-26-gemdesk-usb/README.md)); an XOR outline follows the dragged row |
| Open drive/folder in a window | Have | GEMDESK: IEC drives, and USB folders that open in place, with the close box going up a level as in TOS ([record](validation/2026-09-26-gemdesk-usb/README.md)); listings hold 195 entries |
| Several directory windows at once | Have | GEMDESK: four windows on drives 8 and 9, topping, a fifth refused ([record](validation/2026-09-26-gemdesk-files/README.md)) |
| Icon view / text view | Partial | Text list only |
| Sort by name, date, size, type | Partial | GEMDESK View: name, type, size (largest first), unsorted ([record](validation/2026-09-26-gemdesk-files/README.md)); IEC has no dates |
| Drag-and-drop copy and move | Partial | GEMDESK: selected rows dropped on a window or drive icon are copied or moved (IEC and USB, both ways), each target reopened and compared before a Move deletes the source, with an XOR outline following the drag and a "Copying N/M" window while the rows are copied ([GEM-DESKTOP](GEM-DESKTOP.md)); progress counts rows, not bytes; USB folders are copied and moved as trees between USB windows; a name conflict asks Replace, Keep both (the next free NAME-2 style name) or Skip, Esc stops (no typed name); a folder is merged into one of the same name ([record](validation/2026-09-30-gemdesk-printer-merge/README.md)) |
| Rubber-band and multiple selection | Have | GEMDESK: Shift-click, Ctrl-A, and a band dragged from below the entries, selected live; Delete, Trash, copy and move act on the selection ([GEM-DESKTOP](GEM-DESKTOP.md)) |
| Show Info (size, date, rename, read-only) | Partial | GEMDESK Show Info dialog: editable name (renames on IEC), type, blocks, read-only; drive icons: files and blocks used ([record](validation/2026-09-26-gemdesk-files/README.md)); USB entries: name, Folder/File and exact size from `FILE_STAT` ([record](validation/2026-09-26-gemdesk-usb-info/README.md)); USB entries are renamed from the same dialog (`RENAME_FILE`, checked with `FILE_STAT`); drive icons also show blocks free; Read-only is set or cleared on IEC files through the directory entry's lock bit (`U1`/`U2` on the directory, read back; [record](validation/2026-09-30-gemdesk-readonly/README.md)); no dates (CBM directories hold none); USB read-only cannot be changed |
| New Folder | Have | Ultimate paths in Files ([NATIVE-FOLDERS](NATIVE-FOLDERS.md)) and GEMDESK File:New Folder ([GEM-DESKTOP](GEM-DESKTOP.md)); IEC disks have no directories |
| Delete file / folder | Have | GEMDESK Delete/Trash with confirmation: IEC scratch with the count checked; USB files and empty folders with `DELETE_FILE` proven by `FILE_STAT`, a full folder refused ([record](validation/2026-09-26-gemdesk-usb/README.md)); Files Ctrl-D too ([NATIVE-FOLDERS](NATIVE-FOLDERS.md)) |
| Rename file | Have | IEC: GEMDESK Show Info sends `R0:NEW=OLD` and reports the drive's refusal ([record](validation/2026-09-26-gemdesk-files/README.md)); Ultimate: Files Ctrl-R and GEMDESK Show Info, also folders, checked with `FILE_STAT` |
| Format disk | Partial | GEMDESK File:Format: drive 8/9, name and ID, confirmation, `N0:NAME,ID` under a "Formatting disk" window, then the new disk's listing read back and its free blocks reported ([record](validation/2026-09-26-gemdesk-persistence/README.md), [progress](validation/2026-09-29-gemdesk-conflicts-format/README.md)); no single/double-sided or interleave options (the drive's `N0` decides), no track-by-track progress (the drive answers once, when done); IEC only |
| Disk copy (drive onto drive) | Have | GEMDESK: a drive icon dropped on the other drive's icon copies every sector through buffer channels (`U1`, `B-P`, `U2`) and reads each one back to compare; same geometry only (D64/D71/D81); a "Copy track T/N" window shows progress ([GEM-DESKTOP](GEM-DESKTOP.md)) |
| Install Application (document type → app) | Partial | Fixed rules: Files `.TXT/.SEQ` → Editor, UPNT → Paint; GEMDESK the same: UPNT signature → Paint, then IEC SEQ and USB `.TXT/.SEQ` → Editor; in both, a USHT signature → Sheet ([record](validation/2026-09-30-sheet-documents-bell/README.md)) ([record](validation/2026-09-26-gemdesk-usb/README.md), [record](validation/2026-09-26-gemdesk-paint/README.md)); no user-defined associations |
| Install Icon | Missing | |
| Set Preferences (confirm delete/copy/overwrite) | Have | GEMDESK Preferences: confirm deletes, confirm copies, confirm overwrites (off, a name on the target is replaced without the Replace/Skip/Stop question), sort order, desktop colour; kept across launches and in DESKTOP.INF ([record](validation/2026-09-26-gemdesk-persistence/README.md), [overwrites](validation/2026-09-29-gemdesk-conflicts-format/README.md)) |
| Save Desktop (DESKTOP.INF) | Have | GEMDESK Options:Save Desktop writes a 64-byte DESKTOP.INF (preferences, colour, windows) on the boot drive; after a program returns, the AES session reopens the windows ([record](validation/2026-09-26-gemdesk-persistence/README.md)) |
| Show File (view/print) | Have | Files' byte viewer; text opens in the Editor from Files and GEMDESK ([record](validation/2026-09-26-gemdesk-usb/README.md)); files dropped on GEMDESK's Printer icon (Paint pictures in bit-image bands), and the Editor's document (Ctrl-P), print on IEC device 4 ([GEM-DESKTOP](GEM-DESKTOP.md), [NATIVE-EDITOR-GUI](NATIVE-EDITOR-GUI.md#printing)) |
| Print Screen | Partial | GEMDESK Options:Print Screen or HELP (TOS's Alt-Help) dumps the desktop bitmap to device 4 in the Commodore bit-image mode ([GEM-DESKTOP](GEM-DESKTOP.md)); only in GEMDESK, not in other apps |
| Launch programs, parameter dialog (TTP) | Partial | GEMDESK double-click/Return launches through the checked dispatcher, and its windows come back when the program returns ([record](validation/2026-09-26-gemdesk-persistence/README.md)); no parameter dialog |
| Menu keyboard shortcuts | Have | Desktop letters, Files/Editor/Sheet control keys |
| Desktop pattern and colors | Partial | GEMDESK Preferences: blue, grey or black desktop through the AES's `WF_DESKCOLOR`, saved with the desktop ([record](validation/2026-09-26-gemdesk-persistence/README.md)); no patterns |

## B. GEM AES services

| TOS feature | Status | Kestrel evidence / missing piece |
|---|---|---|
| File selector (`fsel_input`) | Have | Shared IEC/Ultimate picker ([NATIVE-PICKER-GUI](NATIVE-PICKER-GUI.md)) |
| Clipboard / scrap (`scrp_*`) | Partial | Session text clipboard ([NATIVE-CLIPBOARD](NATIVE-CLIPBOARD.md)); no image scraps |
| Alert boxes (`form_alert`) | Partial | Shared [AES alert](NATIVE-AES.md#alerts) with icons, 1–3 buttons, keyboard/pointer and exact restoration, CPU-qualified; suite apps still use their own confirm scenes |
| Dialogs (`form_do`) | Partial | [Forms](NATIVE-FORMS.md): text, default/cancel/exit buttons, checkboxes, radio groups, `N_FEDIT` fields, keyboard and pointer, exact save-under ([record](validation/2026-09-26-gemdesk-files/README.md)); used by GEMDESK only; no VDC mirror |
| Object trees / resource files | Partial | Forms are flat object lists in app memory ([NATIVE-FORMS](NATIVE-FORMS.md)); no nesting, no resource files or editor |
| Menu bar with drop-downs, checks, disabled items | Partial | [AES menu bar](NATIVE-AES.md#menus) with shortcuts, keyboard and pointer, CPU-qualified; no suite app uses it yet |
| Event library (`evnt_multi`: key, button, rectangle, message, timer) | Partial | [AES event wait](NATIVE-AES.md#events) with all five sources, click counting and GEM state rules, CPU-qualified; suite apps still poll directly |
| Application messages (`appl_write/read`) | Partial | AES 16-message queue; a desk accessory takes the messages for its own windows and its Desk item; no messages between app and accessory |
| Window library (title, close, full, move, size, scroll bars, overlapping, redraw lists) | Partial | [AES windows](NATIVE-AES.md#windows): 7 overlapping windows, every GEM frame element with working gadgets (top, close, full, arrows, paging, sliders, move/size drags with XOR outline), exact damage, `WM_REDRAW`, visible-rectangle lists, CPU-qualified; no suite app uses them yet |
| Graphics library (rubber/drag box, grow/shrink, slider, busy pointer) | Partial | 1351 pointer; AES drag box (XOR outline) and slider tracking for windows; no rubber-band box, grow/shrink effects or busy pointer |
| Shell library (`shel_write`, environment) | Partial | `N_REPLACE` chains to another app; no environment |

## C. Desk accessories

| TOS feature | Status | Kestrel evidence / missing piece |
|---|---|---|
| Accessories usable while another app runs | Partial | One accessory slot in bank 1 (`$4000`, owner 29): the AES (minor 7) adds its item to the Desk menu of any AES app and runs it cooperatively while that app waits for events; its window gets its messages, keys and clicks, never the app ([GEM-LAYER-DESIGN](GEM-LAYER-DESIGN.md#desk-accessories)). The Calculator is the accessory. Only AES apps (GEMDESK) show it; one accessory at a time |
| Control Panel (key repeat, double-click, colors, clock, click/bell) | Partial | GEMDESK Desk:Control Panel sets key repeat (KERNAL `RPTFLG`) and double-click speed (AES `evnt_dclick`), Key click and the printer; the desktop colour is in Preferences; all kept with the desktop ([record](validation/2026-09-26-gemdesk-control/README.md)). It is a desktop dialog, not an accessory. Key click (Control Panel) clicks on keys GEMDESK reads, not in other apps; Bell rings the SID bell for GEMDESK's stop alerts ([record](validation/2026-09-30-sheet-documents-bell/README.md)), not for other apps or the VT52 terminal (which always rings on BEL). The Ultimate app sets the clock. |
| VT52 terminal | Partial | [VT52 app](NATIVE-VT52.md): Atari VT52 sequences on the 80-column VDC over the SwiftLink ACIA ([record](validation/2026-09-26-vt52/README.md)); a foreground app, not yet an accessory; CPU-level only |
| Install Printer | Partial | GEMDESK Control Panel: printer on IEC device 4 or 5, Lowercase (secondary address 7) or upper case and graphics (0), kept with the desktop; the Printer icon shows when that device answers ([record](validation/2026-09-30-gemdesk-printer-merge/README.md)); the Editor still prints to device 4; no driver choice (the Commodore bit-image mode only), paper or quality settings |
| RS-232 configuration | Missing | SwiftLink used only inside Claude |
| XControl / CPX modules | Missing | |

## D. GEMDOS services

| TOS feature | Status | Kestrel evidence / missing piece |
|---|---|---|
| Open/create/read/write/close | Have | `N_FOPEN`..`N_FCLOSE` ([NATIVE-FILES](NATIVE-FILES.md)) |
| Seek, append, replace | Missing | |
| Delete, rename | Partial | IEC: app library [dos-command.inc](NATIVE-DOS-COMMANDS.md), scratch and rename used by GEMDESK and tested ([record](validation/2026-09-26-gemdesk-files/README.md)); Ultimate `DELETE_FILE`/`RENAME_FILE` in Files; no kernel entry point |
| Attributes, date/time stamps | Missing | |
| Directory search (`Fsfirst/Fsnext`, wildcards) | Partial | Directory pages and substring search; no wildcards |
| Folders: create, delete, current path | Partial | Ultimate create and paths; GEMDESK deletes empty USB folders (`DELETE_FILE`, proven by `FILE_STAT`); no kernel folder service |
| Free space (`Dfree`) | Partial | IEC: `dc_blocks_free` in [dos-command.inc](NATIVE-DOS-COMMANDS.md) reads the drive's `$` listing; GEMDESK's drive Show Info shows it ([record](validation/2026-09-26-services/README.md)); no Ultimate free space |
| Program execution and exit codes (`Pexec/Pterm`) | Partial | Checked launch and exit codes; no command tail or nesting |
| Memory (`Malloc/Mfree/Mshrink`) | Have | Owned heap and REU arena; no shrink |
| Date and time | Partial | Ultimate RTC get/set; no system clock service |
| Console I/O | Partial | `N_KEYIN` and KERNAL output; no redirectable console |
| Printer and serial character I/O | Partial | Printing through the KERNAL on IEC device 4 (logical file 121) from GEMDESK and the Editor; no kernel printer service or serial console |
| Handle redirection (`Fdup/Fforce`) | Missing | |

## E. BIOS / XBIOS services

| TOS feature | Status | Kestrel evidence / missing piece |
|---|---|---|
| Keyboard device | Partial | Owned ROM scan; no shift-state or key-table API |
| Mouse | Have | 1351 driver with clamp, filter and reconnect |
| Real-time clock | Have | Ultimate RTC |
| Screen base and resolution | Partial | Owned VIC surface and banked VDC service; no live mode switching |
| Palette / color registers | Missing | |
| Sound (`Dosound`), bell and key click | Partial | SID bell library ([NATIVE-SERVICES](NATIVE-SERVICES.md)), rung by the VT52 terminal on BEL ([record](validation/2026-09-26-services/README.md)); `sd_click` for GEMDESK's Key click; no `Dosound` sequencer or system-wide key click |
| Random numbers | Have | `random.inc`: the XBIOS `Random` formula, self-seeding ([NATIVE-SERVICES](NATIVE-SERVICES.md), [record](validation/2026-09-26-services/README.md)) |
| Timer tick callbacks | Partial | Jiffy clock readable; no callback |
| Exception vectors / crash handling | Partial | Load/cleanup errors reported; no BRK trap |
| Floppy/sector read, write, format, verify | Partial | GEMDESK's disk copy reads and writes IEC sectors through buffer channels (`U1`, `B-P`, `U2`) and reads each one back; Format sends `N0:`; no sector service for apps |
| Serial configuration (`Rsconf`) | Missing | |
| Printer output and screen dump (`Prtblk`) | Partial | KERNAL output on device 4 from GEMDESK and the Editor, and GEMDESK's bit-image screen dump; no kernel printer or dump service |
| Cookie jar (capability registry) | Partial | `N_UQUERY` for Ultimate facts |
| Supervisor mode (`Super/Supexec`) | Mapped | The 8502 has no privilege levels; kernel entry points are the equivalent |
| Blitter | Mapped | REU DMA (`src/native/reu.inc`) is the transfer engine |
| MIDI ports | Mapped | No built-in MIDI on the C128; a MIDI cartridge driver would be an expansion |

## F. System behavior

| TOS feature | Status | Kestrel evidence / missing piece |
|---|---|---|
| Text console for text programs (VT52) | Missing | The [VT52 app](NATIVE-VT52.md) interprets VT52 from a serial host; local programs have no VT52 console service yet |
| System fonts in several sizes | Partial | 8×8 and 5-pixel fonts; no font service |
| AUTO folder programs at boot | Missing | |
| Accessories loaded at boot | Partial | GEMDESK loads `DESK1.ACC` from its folder when it starts (the gem profile's boot) and adopts it when already resident; one accessory |
| Desktop configuration loaded at boot | Have | GEMDESK reads DESKTOP.INF when a fresh AES has no session ([record](validation/2026-09-26-gemdesk-persistence/README.md)) |
| Crash display with return to desktop ("bombs") | Partial | Loader errors only; mapped to a BRK/NMI trap |
| Warm reset key combination | Missing | |
| Keyboard mouse emulation (Alt+cursor) | Partial | ALT (or C=) + cursor keys move the pointer, ALT+Return clicks, ALT+Shift+Return holds the button for keyboard drags, in every app that uses the AES client ([record](validation/2026-09-26-gemdesk-control/README.md)); the suite apps outside the AES do not have it |
| Hard disk partitions | Partial | Ultimate USB/SD paths; no CMD/SD2IEC partitions |
| Resolution switching | Mapped | VIC 320×200 and VDC 640×200 are both driven |

## Delivery order

1. **File operations:** delete, rename, Show Info, free space, wildcards,
   format. These are prerequisites for trash, drag-and-drop and the desktop.
2. **AES toolkit:** shared alert service, radio/checkbox controls, menu bar,
   event service.
3. **Window manager and GEM desktop:** overlapping windows with scroll bars;
   desktop with drive icons, trash and folder windows.
4. **Accessories:** banked accessory slot, Desk menu, Control Panel, VT52.
5. **System:** preferences and saved desktop, AUTO folder, crash trap, sound,
   keyboard mouse, printer and serial services.

Each step lands with a validation record under [validation](validation/) and
updates the status column above. Steps 2–4 follow the
[GEM layer design](GEM-LAYER-DESIGN.md).
