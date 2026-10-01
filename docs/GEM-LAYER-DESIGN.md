# GEM layer design (AES, window manager, accessories, desktop)

Design of record for the [TOS parity](TOS-PARITY.md) GEM rows: a shared AES
service, a window manager, desk accessories and a GEM-style desktop. Written
2026-09-25 from the current source and docs; nothing here is implemented yet.
Each delivery step below lands with its own validation record.

## Constraints that shape the design

- The resident kernel and the `$3d00..$3dff` mailbox are full
  (`target/native-desktop/layout.json`, [NATIVE-KERNEL](NATIVE-KERNEL.md)).
  New services cannot live in the resident image.
- Module windows are bound to one parent app's CRC and pages
  ([NATIVE-MODULES](NATIVE-MODULES.md)), so they cannot host shared services
  or accessories.
- The banked executor (`src/native/banked.inc`) is single-instance, fixed at
  `BK_BASE=$6000` and owned by the foreground app. Bank-1 code sees only bank-0
  RAM below `$4000` and may not call `N_LAUNCH`, `N_KEYIN` or `N_EXIT`. AES
  inputs therefore arrive as `N_BUFFER` packets, surface access goes through
  heap callbacks, and the event loop stays in bank 0.
- The VDC shows a 640×200 mirror of the 320×200 VIC surface
  (`src/native/graphics/vdc-mirror.inc`), so the window manager targets one
  320×200 surface and reports dirty rows for the mirror.
- The D64 suite has 16 free blocks. The AES and GEM desktop are D81-only.

## Where the AES lives

`AESVC.PRG` is a persistent NBK1 component at bank-1 `$8700..$bfff`
(57 pages; `$8800` until minor 7 took the spare page above VDSVC) owned by owner 30. It was planned at `$9000` (48 pages); after
alerts, events and menus it filled 38 pages, so the base moved down into the
unused space above VDSVC, which ends at `$86ff`. Like the clipboard's owner 31, owner 30 survives
foreground cleanup. A 10-page owner-30 allocation above `$c000` holds
menu/alert save-under (9 pages) and the session record (1 page). Idle cost is
58 pages, 74 with an accessory open. That cost cannot coexist with the
qualified no-REU large-document workload (423 of 426 pages), so the desktop
offers an AES unload before launching memory-heavy non-AES apps.

Bank-1 map:

| Range | Use |
|---|---|
| `$0400..$3fff` | General heap |
| `$4000..$4fff` | Desk accessory slot (`AC_BASE`), owner 29 while an accessory is loaded; general heap otherwise |
| `$5000..$5fff` | AES RAM-table data segment, owner 30 (planned as the accessory slot; the window manager's cell maps needed it) |
| `$6000..$87ff` | Per-app banked component window (VDSVC uses 39 pages, one spare) |
| `$8700..$bfff` | AESVC, owner 30, persistent |
| `$c000..$feff` | General heap plus the owner-30 save-under/session pages |

Clients find the AES without new mailbox bytes by checking the private handle
tables for owner 30 / bank 1 / page `$87`, then the NBK1 header and
an identity block (`"NAES"`, major, minor, capabilities) at image offset 32.
The executor's base, limit and owner become `.weak` parameters so a second
instance can serve the AES while existing banked clients stay byte-identical.

Apps include `src/native/aes/aes-client.inc` (`ae_` prefix). The calling
convention matches the clipboard and banked clients: foreground only, IRQs
enabled, `A` = operation, packet in `N_BUFFER`, result in `A`/carry. Drawing
results return a 25-bit dirty-row mask that the client merges into the VDC
mirror update. AES versioning is independent of the kernel ABI; an app whose
required AES minor is absent keeps its local UI.

| Op | Purpose |
|---|---|
| 0–1 | Attach (binds surface and app generation) / status |
| 2–3 | Alert open / step |
| 4 | Event step |
| 5–6 | Menu install / set item state |
| 7–13 | Window create, open, close, delete, set, get, update |
| 14–15 | Object form open / step |
| 16 | Message to an application or accessory |
| 17 | Session record read/write |
| 18–19 | Accessory open / dispatch |

When attach sees a new app generation, the AES discards the previous app's
windows, menu and queue and sends `AC_CLOSE` to accessories.

## Desk accessories

*Revised 2026-09-29 (implemented design):* the accessory slot is bank-1
`$4000..$4fff` (`AC_BASE`, 16 pages, owner 30), reserved when an accessory
is loaded; `$5000..$5fff` holds the AES data segment. The AES moved down one
page to `$8700` (the spare page above VDSVC) for the room the hooks and the
text sub-op need.

- **Image.** An NBK1 PRG for `AC_BASE`: the 32-byte NBK1 header, an identity
  at offset 32 (`"nacc"`, major 1, minor 0, two reserved bytes), and at
  offset 40 four little-endian entry addresses: menu, message, dispatch,
  reset. The app that owns the desktop loads it (GEMDESK, from `DESK1.ACC`
  on its drive, at start); `AE_OP_ACC` (12) with `N_BUFFER[0]=1` checks the
  identity and installs the entries, 0 removes them.
- **Menu.** While the AES parses an app's menu, after the first title's
  items it calls the menu entry, which adds its items (a separator and its
  name) through the export at AES image offset 42 (A/X = NUL-terminated
  text; returns the item's index in A). Only apps with a menu show them.
- **Messages.** Every message the AES queues passes the message entry first
  (`ev_msg_in`, export at offset 44): the accessory takes `MN_SELECTED` for
  its items and every window message for its own windows (carry set), so
  the app never sees them.
- **Dispatch.** At the end of each event sample, after the reply is built,
  the AES calls the dispatch entry. The accessory saves `N_BUFFER[0..18]`
  (the reply), calls AES operations through `aes_entry` (export at offset
  40) to draw its window, ORs the rows they report into the reply's bytes
  15..18 (the client mirrors them to the VDC), and restores the reply. It
  sees the sample's key, pointer and buttons in the reply; a key or a press
  it uses is removed from the reply (its bit in byte 0 cleared), so input
  for an accessory window never reaches the app.
- **Reset.** On an app change the AES discards the app's windows, the
  accessory's included, then calls the reset entry: the accessory forgets
  its windows and stays loaded.

Scheduling is cooperative, as in GEM: an accessory runs only while an AES
app waits in `ae_event`. Accessories must not keep file streams, may not use
zero page beyond `$06..$08`, and cannot own the NMI.

The original plan follows.


An accessory is an NBK1 image (`"NACC"`, at most 16 pages) loaded at bank-1
`$5000`. The AES calls it directly inside bank 1 (init, message, timer
entries). The accessory reaches the AES through a jump table at `AE_BASE+40`.
One accessory is resident at a time; up to four `DESK*.ACC` entries from the
boot device are listed in the Desk menu and loaded on demand.

Scheduling is cooperative, as in GEM: accessories run only while the
foreground app is inside the AES event call, and only AES-linked apps show a
Desk menu. Accessories must not keep file streams between dispatches (the AES
releases owner 29 streams after each dispatch), may not use zero page beyond
`$06..$08`, and cannot own the NMI while the foreground app does.

Across an app change, the AES keeps its code and settings, the accessory
registry, the loaded accessory and its data, and the desktop session record.
The app's windows, menu, surface and queued messages are discarded.

The VT52 terminal is built first as a foreground app reusing the Claude
client's SwiftLink pattern. A polled accessory version follows once ACIA RTS
flow control is verified on the Ultimate modem emulation.

## Window manager

Windows are placed on the 40×25 cell grid; row 0 is the menu bar. Cell
geometry keeps VIC color attributes per window consistent, uses the aligned
fast paths in `graphics-core.inc` and keeps region arithmetic in 8 bits.

- **Records:** 8 × 48 bytes: flags; GEM kind bits (name, closer, fuller,
  mover, sizer, arrows, sliders); current, previous and maximum rectangles;
  slider positions and sizes; app tag; title (copied into the record).
- **Z-order:** an 8-entry stack; at most 7 windows plus the desktop (id 0).
- **Cell ownership map:** 1,000 bytes naming the top window in each cell,
  rebuilt bottom-up. Hit testing is one lookup. Damage is every cell whose
  owner changed plus the visible area of a moved or resized window.
- **Redraw iteration:** `WF_FIRSTXYWH`/`NEXTXYWH` walk the map and emit row
  runs merged downward as rectangles. The AES draws frames; the app receives
  `WM_REDRAW` and clips with the existing `gfx_set_clip` per rectangle.
- **Save-under:** only for drop-down menus and alerts, each at most 250 cells.
- **Move/resize:** XOR outline drag, then one redraw.
- **Messages:** GEM numbering in a 16-entry ring of 8-byte records
  (`MN_SELECTED` 10, `WM_REDRAW` 20 … `WM_MOVED` 28, `AC_OPEN` 40,
  `AC_CLOSE` 41).

## GEM desktop

A new D81 build profile (`GEMDESK`) is built beside the current launcher
(`src/native/desktop.asm`), which stays the default until the new desktop's
workflows replace the launcher's oracles.

- **Icons:** IEC drives, the two Ultimate DOS contexts, trash, and optional
  app shortcuts.
- **Folder windows:** cached directory snapshots in bank-1 allocations
  (at most 16 pages per window, 4 windows). IEC reads use `N_DIRPAGE`.
  Ultimate reads scan the directory cursor and close it, as Files does.
  Icon and text views, sorted by name, type or size (date on Ultimate).
- **Actions:** open apps with `N_REPLACE` and documents with
  `N_DOCREQUEST` and the `files/open-with.inc` rules. Trash, Show
  Info/rename and New Folder reuse the verified Ultimate command code from
  `src/native/files/new-folder.inc`, extracted into a shared include. Deletes
  are confirmed with an alert. Moves within one filesystem use RENAME_FILE;
  other moves are a verified copy and a delete. *Revised 2026-09-26:* IEC
  delete uses the app-side [DOS command library](NATIVE-DOS-COMMANDS.md)
  instead of a kernel service (the kernel has no free bytes); it refuses
  while the kernel holds the drive's command channel.
- **Budget:** about 50 core pages plus a 24-page module window for copy,
  info and open, inside the 96-page slot. Frames, menus and alerts live in
  the AES; caches live in the bank-1 heap. Window state is saved in the AES
  session record before handoff and restored by rescanning on return.

## Dual monitors (decided 2026-09-26)

Marc asked for both modes, chosen in the Control Panel as "Displays: 40 only /
Mirror / Extend" and kept in `DESKTOP.INF`.

**Mirror** shows the VIC desktop on the 80-column screen through the shared
[VDC service](NATIVE-VDC-SERVICE.md) (`VDSVC.PRG`, `BP_MODE` 0: 320×200
doubled to 640×200). Rows are presented only when changed:
- GEMDESK's own drawing marks rows through the graphics library;
- the AES reports the rows it draws in window, alert and event replies, and
  the client ORs them into `ae_dirty`;
- the client calls the app's `ae_present` while menus redraw inside the event
  loop, and the forms library calls it from its own input loop.

Leaving GEMDESK closes the mirror before the pointer (`gm_leave`), which
restores the 80-column screen. Without the component, or with a display
fault, GEMDESK runs on the VIC alone.

**Extend** puts the 80-column screen to the right of the 40-column one, as a
second area of the same desktop. Chosen implementation: a RAM surface.
- A 640×200 hires surface plus 80×25 RGBI attributes (18,000 bytes, 71
  pages) is allocated in bank 1. If it cannot be allocated, GEMDESK falls
  back to Mirror and says so.
- The AES window manager gains a screen per window: 0 VIC (40×25 cells, row
  stride 320), 1 VDC (80×25 cells, row stride 640). Windows open, move and
  close within one screen. Dragging a window's title past the seam moves it
  to the other screen, where it is redrawn; windows never straddle the seam.
- Icons, the menu bar, alerts and dialogs stay on the VIC screen.
- The pointer range becomes 0..959 across both screens. Below 320 the VIC
  sprite shows it; from 320 the VDC service draws its pointer and the sprite
  is hidden.
- The VDC service presents the extended surface 1:1 (a new presenter mode)
  instead of doubling the VIC surface.

**Where the code goes.** All three components involved are nearly full, so
this is part of the design, not an afterthought:
- AESVC has about 230 bytes left. The two-screen window code needs more, so
  the AES first moves rarely used code (for example window creation and
  deletion) into a banked AES overlay.
- VDSVC has 5 bytes left in its 39-page reservation, and since AES minor 7
  (at `$8700`) no spare page before the AES. The 1:1 presenter must replace
  doubled-mode code when the mode is Extend, or AES code must move to an
  overlay so the AES can return to `$8800`.
- GEMDESK has 64 to 98 bytes left after the mirror. Extend's GEMDESK code (the
  Control Panel choice, window screens in the desktop record) goes into the
  dialog modules where possible.

Memory with an REU: roughly 100 main-RAM pages stay free after the extended
surface. Without an REU the VDC screen backup takes 64 pages as well, which
leaves about 40.

## Delivery sequence

Every step keeps the heap, apps, banked, VDC, desktop, pointer, graphics,
clipboard, Files and folder CPU suites and the `native`, `nativedesktop*` and
`nativepointer*` VICE workflows passing.

1. **Persistent executor and AES skeleton:** parameterized executor, ops 0–1.
   Test: the AES survives app exit, a second app attaches, corrupt identity
   and wrong owner are refused, VDSVC coexists, unload returns all pages, and
   existing banked images are byte-identical.
2. **Alerts:** icon, up to 5 lines, 1–3 buttons, keyboard and pointer,
   save-under with exact restoration and dirty-row masks.
3. **Events:** key, button with click count, two rectangles, timer and
   message queue, with idle `N_READY` publication.
4. **Menu bar:** drop-downs, checks, disabled items, shortcuts, keyboard
   menu mode.
5. **Window manager:** randomized comparison with a Python oracle for the
   cell map, redraw rectangles and messages; then a VICE drag workflow.
6. **Objects:** radio buttons, checkboxes, default/cancel buttons, text
   fields bridged to `N_FEDIT`. *Revised 2026-09-26:* built as the app-side
   [forms library](NATIVE-FORMS.md) instead of AES ops 14–15, because the
   AES image is full. It polls input itself, so the menu bar is inactive
   while a form is open.
7. **GEM desktop profile:** drive windows, launch and return with restored
   windows, trash and info on Ultimate.
8. **Accessory slot, Desk menu and Control Panel:** key repeat, double-click,
   mouse speed, colors and clock; settings survive app handoff.
9. **VT52:** foreground app first, then the polled accessory.
10. **Migrations:** Files, Editor and Paint dialogs/menus onto the AES as
    budgets allow; desktop configuration saved to disk.

## Risks

- Redraw speed through the per-byte heap gateway at 1 MHz is unmeasured;
  instruction counts are recorded from step 2.
- The 12 KiB AES code estimate is unproven; a build-time guard enforces it.
- VDSVC has no page of growth left before the AES (`$8700` since minor 7);
  a larger VDSVC fails its fixed load cleanly while the AES is resident.
- Reading the private handle tables to find the AES is not a formal ABI.
- An attached AES image cannot be CRC-checked because it is self-modifying;
  only the identity/header check detects stray writes.
- To be confirmed: key-repeat control, PAL/NTSC jiffy rate, ACIA RTS flow
  control on the Ultimate, VDSVC pointer handling with AES-dirtied rows.
- Extend mode's AES overlay, VDSVC 1:1 presenter and 71-page surface are
  unbuilt; the memory figures above are estimates from the published page
  tables, not measurements.
