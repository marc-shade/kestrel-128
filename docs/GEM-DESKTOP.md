# GEM desktop (GEMDESK): v1 specification

Step 7 of the [GEM layer design](GEM-LAYER-DESIGN.md): a TOS-style desktop
built on the [AES](NATIVE-AES.md). It is a new native app beside the current
card launcher (`src/native/desktop.asm`). That launcher stays the default boot
target until GEMDESK's workflows replace its test oracles. This page fixes
v1's scope and acceptance. The status section below records what is built.

## Status (2026-09-29)

The build adds `target/native-desktop/gem.d81`, a D81 with GEMDESK as
`browse`, the card launcher as `cards`, and `aesvc.prg`.
`tests/ci_native_gemdesk.py` (Py65) passes 45 cases,
`tests/ci_native_gemdesk_select.py` 8 and `tests/ci_native_gemdesk_copy.py` 11,
against `tests/native_gemdesk_scene.py` ([first build](validation/2026-09-26-gemdesk/README.md),
[files and views](validation/2026-09-26-gemdesk-files/README.md),
[persistence and format](validation/2026-09-26-gemdesk-persistence/README.md)).

Built and tested:
- startup with the AES loaded from the boot folder;
- icon selection, and the 8 and 9 keys, which open that drive's window;
- drive windows for the boot drive and drive 9, four at once (a fifth is
  refused), staggered, topped by a click;
- drive 9's geometry from its DOS: the first time it is opened, GEMDESK sends
  `UI`. The drive's 73 reply names its ROM: 1581 reads as a D81, 1571 as a
  D71, and any other name as a D64. The answer is kept for the run; a drive
  that does not answer is asked again next time;
- scrolling by arrow, track (a page) and thumb; row selection by click and by
  cursor keys;
- View sorting: name (the default), type, size (largest first) and unsorted,
  with the current item checked;
- Show Info for an entry, as a [dialog](NATIVE-FORMS.md) with the name
  editable (OK renames the file with `R0:NEW=OLD`; the drive's refusal, such
  as 63 FILE EXISTS, is shown), type, blocks and read-only. Read-only can be
  ticked or cleared: CBM DOS has no lock command, so `GDDSK.PRG` (run by
  the core after the dialog, by the name the file then has) reads the
  directory chain (18/1 on a D64 or D71, 40/3 on a D81) through a `#`
  buffer channel with `U1` until a closed file has that name, writes the
  sector back (`B-P 0`, its 256 bytes, `U2`) with the entry's lock bit (bit
  6 of its type) set or clear, reads it again to prove it, and lists the
  drive again; a refusal (a write-protected disk answers 26) is shown with
  the drive's status line. For a drive icon, it shows files and blocks used
  in an alert.
- Options:Preferences, a dialog: Confirm deletes (a checkbox; off, Delete and
  Trash skip the question), Confirm copies (off, a dropped row is copied
  without "Copy NAME to DEST?"; Move needs the question), Confirm
  overwrites (off, a name on the target is replaced without "NAME already
  exists on DEST."), the sort order (radio buttons, the same as View),
  and the desktop colour (blue, grey, black; the AES repaints the desktop).
- Persistence. Before GEMDESK launches a program or hands over to the card
  launcher, it writes a 64-byte desktop record to the AES session:
  preferences, colour, and each window's drive, rectangle, scroll and
  selection. When GEMDESK starts again with the AES resident, it reopens
  those windows, the top one last. With a fresh AES it reads the same record
  from DESKTOP.INF on the boot drive, which Options:Save Desktop writes
  (scratch, then an exclusive create). A window whose drive cannot be read
  now is skipped without an alert.
- File:Format: a dialog for drive 8 or 9, name and ID, then a confirmation
  (Cancel is the default). It sends `N0:NAME,ID` under a "Formatting disk"
  window (the drive answers only when it is done), lists the drive's windows
  again, and reads the new disk's listing back: "Drive 9 is formatted: 664
  blocks free." (the drive's own count), or an alert that the new disk could
  not be read back (`GDFMT.PRG`).
- Delete (Ctrl-D) and dropping a row on Trash. Both ask first, with Cancel
  as the default. The file is scratched with
  [`dos-command.inc`](NATIVE-DOS-COMMANDS.md), the drive's count of scratched
  files is checked, and every window of that drive is listed again. A locked
  file the drive skips is reported. Names with DOS pattern characters are
  refused, and so is a drive whose command channel the kernel holds.
- File:Close, Desk:About, Options:Launcher, and launching a listed file;
- the drive and full-window error alerts;
- Desk:Control Panel: key repeat (all keys, cursor keys only, none),
  double-click speed 1–5 and Key click (a short noise burst on SID voice 1,
  `sd_click`, for every key GEMDESK reads; not in other apps), Bell (the SID
  bell, `sd_bell`, when an alert with the stop icon opens, such as a drive
  error or "Format drive 8?"), applied at once and kept with the desktop
  (record version 2; Key click is bit 2 of the preference byte, Bell bit 4),
  and the printer (TOS's Install Printer): IEC device
  4 or 5, and Lowercase (secondary address 7, the printer's upper and lower
  case; off, 0: upper case and graphics), kept in record bytes 60 and 61
  (records saved before hold 0 there and keep device 4). A new device is
  probed again for the Printer icon and the desktop is repainted; after a
  saved desktop is restored, its printer is probed too;
- the keyboard mouse from the AES client: ALT or C= with the cursor keys
  moves the pointer, and with Return clicks; ALT+Shift+Return holds the
  button until it is pressed again, so drags work from the keyboard.
- Multiple selection ([test](../tests/ci_native_gemdesk_select.py)): Shift-click
  adds a row or removes it; a plain click leaves one row selected; Ctrl-A
  selects every entry of the top window. A press below a window's entries
  clears the selection, and held, drags a band: the rows between the press
  and the pointer are selected live (the AES wakes the desktop when the
  pointer leaves its row) and stay selected after the release. Every
  selected row is drawn inverted; the most recently chosen one is the anchor
  that Show Info, Open and the cursor keys use.
- Delete, and dropping on Trash, act on every selected row: one question
  ("Delete N items?"), then each is scratched (IEC) or deleted (USB); a
  failure is reported and the next row is tried, and the drive is listed
  once at the end.
- USB Show Info with rename ([test](../tests/ci_native_gemdesk_folder.py)), in
  `GDUSB.PRG`: a dialog with the name (editable), "Folder" or "File, N bytes"
  and read-only from `FILE_STAT`. OK with a changed name (checked as for New
  Folder) sends Ultimate DOS `RENAME_FILE` with both full paths, `old NUL
  new` (the firmware refuses an existing name); `FILE_STAT` must then find
  the new name, and the window is listed again.
- File:New Folder ([test](../tests/ci_native_gemdesk_folder.py)), in
  `GDNEW.PRG`, in a USB
  window: a dialog takes the name (1..31 printable characters, none of
  `" / \ : < > * ? |`, not ending in a space or a period); Ultimate DOS
  `CREATE_DIR` gets the full path, `FILE_STAT` must then answer with a
  directory, and the window is listed again. A refused name, Cancel, or a
  drive window (IEC disks have no folders) sends nothing.
- Printing ([test](../tests/ci_native_gemdesk_print.py),
  [VICE test](../tests/ci_native_gemdesk_print_vice.py)), in `GDPRT.PRG`
  (the core sends rows dropped on the Printer icon there): at start GEMDESK
  opens logical file 121 on the printer's IEC device (4, or 5 from the
  Control Panel) through the KERNAL (no name, so
  nothing is sent) and addresses it with CHKOUT; when the device answers, a
  Printer icon appears below USB. Rows dropped on it are printed after
  "Print NAME?" (or "N items") with Print and Cancel, in listing order. A
  Paint picture (a file that starts with the UPNT version 1 header, 320×200)
  is printed as Print Screen prints the desktop: its bitmap in bit-image
  bands, read from the file one character row (320 bytes) at a time, two
  rows held; its colours are not printed, and its checksum is not checked
  first (a picture that ends early stops with "Printing stopped"). Any other
  IEC file is sent as stored (PETSCII); a USB file is taken as ASCII: letters
  are swapped for PETSCII, CR, LF and CR LF each become CR, a tab becomes a
  space, other control bytes are left out. Esc stops between 512-byte
  chunks; a printer that stops answering is reported. Folders are refused
  as for copies. There is no page layout, and no printing of a whole window.
- Disk copy ([test](../tests/ci_native_gemdesk_diskcopy.py),
  [VICE test](../tests/ci_native_gemdesk_diskcopy_vice.py)), in `GDDSK.PRG`:
  the Boot icon dragged onto the Drive 9 icon (or the reverse) copies the
  whole disk after "Copy the disk in drive 8 onto drive 9?" (Cancel is the
  default). Both drives must hold the same geometry (D64, D71 or D81). Every
  sector of every track goes through a buffer channel (`#`, secondary
  address 2) on each drive: `U1` reads the source sector and its 256 bytes
  are read; `B-P`, the bytes and `U2` write it on the target; `U1` on the
  target reads it back and it is compared. Each drive's status line is read
  after every command, and the first error (for example `26,WRITE PROTECT
  ON`) or difference stops the copy with the track and sector. Esc stops
  between tracks ("Drive 9 holds part of the copy"). The target's windows
  are listed again. While it works, a title-only window reads "Copy track
  T/N" (window titles hold 16 characters); it is closed, and the redraws its
  closing queues are answered, before the result alert. Every sector is
  copied, used or not; there is no copy between USB and IEC or of a disk
  onto a folder.
- Desk accessory ([test](../tests/ci_native_gemdesk_acc.py),
  [VICE test](../tests/ci_native_gemdesk_acc_vice.py)): at start `GDSES.PRG`
  adopts an accessory already resident at bank-1 `$4000`, else loads
  `DESK1.ACC` from the desktop's folder (a missing file means none; a file
  that cannot be loaded is reported with its error and nothing partial is
  kept), installs it in the AES and installs the menu again, so the Desk
  menu lists it. `gem.d81` carries the Calculator: a window with a display
  and a keypad, used with clicks or with keys while it is on top; the
  desktop does not see that input. See
  [GEM-LAYER-DESIGN](GEM-LAYER-DESIGN.md#desk-accessories).
- Print Screen ([test](../tests/ci_native_gemdesk_prtscr.py),
  [VICE test](../tests/ci_native_gemdesk_prtscr_vice.py)): Options:Print
  Screen, or the C128's HELP key (TOS's Alt-Help), sends the desktop's
  320×200 bitmap to the printer (device 4 or 5) in the Commodore bit-image mode
  (MPS-801/803): CHR$(8), then 29 bands of 7 dot rows, each 320 column bytes
  (bit 7 set, bit 0 the top dot) ended by CR, and CHR$(15) to return to
  text. A set bitmap bit prints a dot; colours are not printed; the pointer
  is a sprite and is not printed. The menu closes before the dump. Esc stops
  after the current band (the printer is returned to text mode); a missing
  printer is reported. It runs in `GDPRT.PRG`, reading the surface one
  character row at a time through `N_READ`.
- Copy and move by drag and drop ([test](../tests/ci_native_gemdesk_copy.py),
  [VICE test](../tests/ci_native_gemdesk_copy_vice.py): a SEQ file dragged
  with the 1351 between two emulated 1581s, read back with `c1541`),
  in `GDCPY.PRG`: rows dropped on another window or on a drive icon (Boot,
  Drive 9, USB) are copied there after "Copy NAME to DEST?" (or "N items")
  with Copy, Move and Cancel. Each target is created exclusively, closed,
  reopened and compared with the reopened source, including a final read that
  proves it has no extra tail, as Files copies. Move deletes each source only
  after that comparison. IEC to IEC keeps the file type; USB to IEC names a
  ".PRG" file PRG and anything else SEQ, and refuses names over 16
  characters or with DOS pattern characters; IEC to USB writes into the
  target window's folder (the root for the USB icon); USB to USB opens the
  target on the other DOS context. Refused: folders onto a drive, REL,
  unclosed files and an empty file onto a drive. A file whose name is on the
  target (a drive answers 63 to the create; on USB, `FILE_STAT` finds it
  first) asks "NAME already exists on DEST." (unless Confirm overwrites is
  off in Preferences, when it is replaced at once) with Replace, Keep both
  and Skip (the default), Esc for Stop: Replace scratches the target
  (`S0:NAME`, exactly one file scratched) or deletes it (`DELETE_FILE`, an
  empty reply) and copies again; Keep both copies under the source's name
  with "-2" before its extension (`notes-2.txt`), then "-3" and on while
  those are taken too, asking again after "-9"; on a drive the name keeps 16
  characters by shortening the part before the suffix (`REPO-2.TEXTFILE1`),
  or the name itself when its extension leaves too little; Skip goes on with
  the next file; Stop ends the remaining rows. The
  alert names the file itself, also inside a folder being copied. A USB
  folder whose name is a folder on the target is merged into it (nothing is
  made; each file on both asks as above); one whose name is a file there is
  refused. A Move in which a name was skipped keeps its source. Esc stops a copy between chunks; the partial target stays, the alert
  says so, and the target is listed. A target that differs when reread is
  reported and the source is kept. While the rows are copied, a title-only
  window reads "Copying N/M" (or "Moving N/M") for row N of M; it opens for
  the first row that is copied, alerts about a row appear over it, and it
  closes when the rows are done, before the windows are listed again.
- Folder copy and move ([test](../tests/ci_native_gemdesk_tree.py)), in
  `GDCPY.PRG`: a USB folder dropped on another USB window is
  copied as a tree (a folder dropped on the USB icon would go to the
  Ultimate's root and is not tested). `FILE_STAT` must find nothing under the target name;
  `CREATE_DIR` makes the folder, proven by `FILE_STAT` answering with a
  directory; then each entry of the source folder is copied as above, a
  subfolder by descending into it (16 levels at most, paths up to 255
  bytes). Because a DOS context holds one open file, the source folder is
  reopened for each entry and read to its position. Entries named `.` or
  `..` are skipped. Move deletes the source's contents after the whole tree
  is copied, deepest first (a file, or a folder once empty, each with
  `DELETE_FILE`), then the emptied folder through the same delete as a
  single row. A folder
  dropped on a window showing that folder or one inside it is refused ("A
  folder cannot be copied into itself"); a failure stops the tree and leaves
  what was made.

Built but not yet covered by tests: fulled, moved and sized answers.

- USB storage: a USB icon appears when the Ultimate's DOS (target 1) answers
  an identify query. Its window lists DOS context 1 from `/` through a
  directory cursor. Folders (`DIR`) open in the same window; the close box goes
  up a level, as in TOS, and closes the window at the root. A file launches
  through the dispatcher with its full path, re-read from the cursor, so names
  longer than the 16 characters shown still work.
- USB delete (and Trash): after the same confirmation, `DELETE_FILE` with the
  entry's full path, then `FILE_STAT`; only DOS 82 with an empty reply proves
  the removal, otherwise an alert says so. A full folder is refused by the
  drive, and the refusal is shown.
- Documents, decided as Files decides ([document contract](NATIVE-DOCUMENT-LAUNCH.md)):
  GEMDESK reads the first four bytes of an IEC SEQ file or any USB file. `UPNT`
  opens it in Paint, `USHT` (a workbook, which Sheet saves as SEQ) in Sheet.
  Otherwise an IEC SEQ file, or a USB file ending in `.TXT`
  or `.SEQ`, opens in the Editor. Closing the app returns to GEMDESK, and its
  windows come back. Other files (IEC PRG and USR included) go to the
  dispatcher, which runs native programs.
- A listing holds up to 195 entries: the snapshot is 16 pages, sorted in a
  bank-0 workspace at `$5000` reserved like Files'. Larger directories show
  their first 195.

Not built yet, or limited:
- USB Show Info shows the name, Folder or File and the exact size from
  `FILE_STAT`, but not the date: the firmware sources checked do not settle
  how that date is encoded. Its name field shows 26 of up to 63 characters
  (longer names scroll with the caret); names over 63 cannot be renamed here.
- USB windows are not kept in the desktop record or session.
- Drive 9 is identified by drive model, not by the mounted image: a drive
  that does not name 1571 or 1581 (an SD2IEC, for example) is read as a D64
  whatever image it holds. `UI` resets the drive's DOS.
- Read-only is set on IEC files only (USB entries show it from `FILE_STAT`
  and cannot change it). A dragged row is shown by a 10x1-cell
  XOR outline at the pointer (AES window sub-op 9, drawn and erased around
  each wait), not by the row's own image; several selected rows show one
  outline.
- Selection by band covers rows of the listing text only (there is no icon
  view); Shift with a band is not additive, it replaces the selection.
- Copy's progress is counted in rows, not bytes: one large file shows
  "Copying 1/1" until it is done. A name conflict cannot be renamed to a
  name you type: Keep both picks the next free numbered name, since
  `GDCPY.PRG` has no room for the forms library. Folders are copied only between USB windows: IEC disks
  have no directories.

Emulator: [the VICE run](validation/2026-09-26-gemdesk-vice/README.md) boots
`gem.d81` on an emulated 1581. It opens drive 8 with the 8 key, launches
Calculator, and returns with the window restored; every surface matches the
CPU oracle. Pointer workflows and the dialogs have run only in the CPU model.
Nothing has run on hardware.

Memory: GEMDESK is a core plus one module window (NAPP bytes 7 and 11).
Nine modules share the window: `GDDLG.PRG` (Show Info),
`GDSET.PRG` (Preferences, Control Panel), `GDUSB.PRG` (USB Show Info with
rename), `GDNEW.PRG` (New Folder) and `GDFMT.PRG` (Format, with the progress
window), each with its own copy of the forms library;
`GDCPY.PRG` (copy and move of files and folders); `GDPRT.PRG` (printing
files and pictures, Print Screen), which shares GDCPY's stream helpers
(`gemdesk-stream.inc`); `GDDSK.PRG` (disk copy, and the read-only lock that
Show Info leaves to it, since a module cannot load another), with the
sector routines in `gemdesk-sector.inc`; and `GDSES.PRG`, which runs only at start (the desk accessory,
then the session or DESKTOP.INF) and for Options:Save Desktop.
Building and saving the session record before a launch stays in the core,
so no module load comes between a launch's settings and the launch. The one an
operation needs is loaded from the desktop's folder, replacing the others
([NATIVE-MODULES](NATIVE-MODULES.md)). If it is missing, an alert says so and
the desktop goes on. The USB windows' paths are a 4-page heap block (one
page per window, read into a one-page buffer when used), and record
addresses in the sort workspace are computed rather than tabled; together
these made room for the selection. The core ends at `$b234`; GDDLG ends at
`$bdd4`, GDSET at `$bfe7`, GDUSB at `$bedf`, GDSES at `$bcaa`, GDDSK at
`$baec`, GDCPY at `$bf2e`, GDNEW at `$bdcc`, GDFMT at `$bf96` and GDPRT at
`$b956`, below the `$c000` limit; GDSET, the largest, leaves the core 25
bytes to grow. Each module is
assembled on its own against the core's labels (`gemdesk.sym`, written by
the core's assembly) from `src/native/gemdesk-{dlg,set,cpy,ses,usb,dsk,new,fmt,prt}.asm`,
so together they are not limited to one 40 KiB image; each still has to
fit the window. GDCPY keeps its two
256-byte names in the sort workspace after the 512-byte chunk (`$5200` and
`$5300`); painting, which happens only when its progress window closes,
fills just the rows buffer below them.

## v1 scope

**Desktop.** At start, GEMDESK:
- presents the VIC surface and installs the 1351 pointer;
- attaches to the AES, or loads `AESVC.PRG` from its own folder;
- installs the menu bar;
- draws icons on the desktop: drive 8, drive 9, the Ultimate USB root when
  a command interface answers, and Trash.

Desktop icons are redrawn on `WM_REDRAW` for handle 0.

**Menu.**
- `Desk: About Kestrel... | - | Control Panel...`
- `File: Open^O | Show Info^I | - | Delete^D | Format... | New Folder... | - | Close^W`
- `View: Name | Type | Size | Unsorted`
- `Options: Preferences... | Save Desktop | Print Screen | Launcher^L`

Choosing Launcher returns to the card launcher (`N_EXIT`).

**Folder windows.** Opening a drive icon opens a window with the drive's
listing. It has the name, close, full, move, size, up/down and
vertical-slider gadgets. Up to four folder windows may be open at once.
- Each window keeps a directory snapshot. IEC uses `N_DIRPAGE`; Ultimate
  scans the directory cursor once and closes it.
- The work area shows one entry per text row: name, type and blocks (IEC)
  or size (Ultimate), drawn clipped to the visible rectangles on
  `WM_REDRAW`.
- Arrows scroll a row, the track a page, and the thumb positions the list.
- The app answers moved, sized, fulled, topped and closed messages with
  `wind_set`.

**Selection and actions.**
- A click selects an entry (inverse row). A double-click, or Open, acts on it:
  - a native app (NAPP manifest) launches through the dispatcher;
  - a folder (Ultimate) opens in place;
  - anything else shows an info alert.
- Show Info shows an alert with the name, type and size (and read-only).
- Delete asks for confirmation in an alert. On IEC it scratches the file
  through [`dos-command.inc`](NATIVE-DOS-COMMANDS.md) and checks the drive's
  count; on Ultimate it will use the same verified path as Files.
- Dragging an entry onto Trash does the same as Delete.
- View sorts the snapshot by name, type or size, or keeps directory order.

**Keyboard.** The menu's shortcuts, plus cursor keys and Return in the top
folder window.

## Acceptance

- CPU tests (Py65, `DisplayBus`, IEC and Ultimate fixtures) compare complete
  surfaces against an oracle that composes the AES window oracle with the
  desktop's icons and listing text. They cover:
  - open, scroll, select, open an app, Show Info;
  - delete with confirmation, and Trash by drag;
  - the error paths: a missing drive, a failed delete, a missing
    `AESVC.PRG`.
- A VICE workflow: boot the D81 suite, start GEMDESK, open drive 8, launch
  Calculator, return to the desktop.
- Planted-bug checks for the listing oracle, as for the AES.

## Not in v1

- Icon view.
- Install Application, and saved desktop configuration.
- Keyboard pointer emulation.
- Printing.
