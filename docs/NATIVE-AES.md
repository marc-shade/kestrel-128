# Native AES component

The AES is the shared service behind the [GEM layer](GEM-LAYER-DESIGN.md).
It now provides a persistent bank-1 component that apps load once and later
apps attach to (step 1), GEM-style alert boxes (step 2, AES minor 1) and an
`evnt_multi`-style event wait with an application message queue (step 3,
minor 2), a GEM menu bar (step 4, minor 3) and GEM windows with working frame
gadgets (step 5, minor 4); minor 7 adds a text sub-op and one desk
accessory slot ([Calculator](GEM-LAYER-DESIGN.md#desk-accessories)). Objects
are a later step.

## What persists

`AESVC.PRG` is an NBK1 image loaded at bank-1 `$8700` (`AE_BASE`) and owned
by owner 30 (`N_AESOWNER`). App cleanup releases only owner 32, so the image
and its state stay resident after `N_EXIT`. The next app attaches to the same
bytes instead of loading them again. `ae_unload` frees the image and returns
its pages. With alerts, events, menus, windows and the shared graphics
library, the text sub-op and the desk-accessory hooks the image is 57 pages
(14,454 bytes) of its 57-page region (`$8700..$bfff`). It started at `$8800`;
minor 7 took the spare page above VDSVC for the text sub-op and the
accessory hooks. Its RAM tables (cell maps, menu text, message queue,
window records) live in a second owner-30 allocation, the 16-page data
segment at bank-1 `$5000..$5fff`. The first attach reserves and clears it.
`ae_unload` first calls `AE_OP_SHUTDOWN`, which closes any open drop-down,
discards an open alert's buffer and frees the segment; it then frees the
image. While resident, the AES therefore holds 57 + 16 pages of the bank-1
heap.

The component's identity block sits at image offset 32: `NAES`, major and
minor version, capability bits. The AES version is independent of the kernel
ABI (`src/native/aes-api.inc`).

## Client

Include `api.inc`, `aes-api.inc` and `aes-client.inc` in the retained app
core. The client is a second, block-scoped instance of the
[banked executor](NATIVE-BANKED.md) configured for owner 30 at `$8700`, so
it coexists with an app's own `$6000` component.

| Entry | Contract |
|---|---|
| `ae_attach` | Adopt the resident AES and register this app. Carry set with `A=N_BADHANDLE`: none is resident. `A=N_BADIMAGE`: the resident image failed validation. |
| `ae_load` | Load `AESVC.PRG` from the owner-32 stream in `N_FHANDLE`, then register. `ae_stream_taken` is nonzero when the loader took the stream (it then closes it); zero means the caller still owns it. A failed load frees any partial image. |
| `ae_call` | `A` = operation, packet in `N_BUFFER`; returns the AES's `A`/carry. |
| `ae_detach` | Forget the attachment before exit; the AES stays resident. |
| `ae_unload` | Free the AES image and its pages. |

Register (`AE_OP_ATTACH`, 0) passes the executor's app cookie (app slot and
allocation generation). The reply in `N_BUFFER` is: major, minor,
capabilities, 0, attach count (word), distinct app count (word), a byte that
is 1 when this attach changed the foreground app, and the current cookie.
`AE_OP_STATUS` (1) returns the same reply without registering.

## Alerts

`ae_alert_open` shows a GEM `form_alert` over the app's VIC surface: set
`ae_surface` to the surface handle, pass the string address in A/X and the
default button (0–3) in Y. The string is ASCII:
`[icon][line|line][button|button]`. Icon 0 is none, 1 note (!), 2 question,
3 stop. Up to 5 lines of 30 characters and 1–3 buttons of 1–10 characters are
accepted, and the alert must fit 250 cells (38 columns wide at most).
Anything else is refused with `N_BADARG` before the surface changes.

The alert is centred on the 40×25 cell grid:
- one-cell margin, the icon in a 2×2-cell area plus a gap column;
- the text lines, a blank row, and a two-row button bar;
- buttons are label+2 cells wide, one cell apart and centred;
- blue ink on white paper with a double frame;
- the default button has a second frame line, and the focused button uses
  the suite's yellow focus colour.

Call `ae_alert_step` for each input: A is the key (0 for none), and the
pointer is in `ae_pointer_x` (word), `ae_pointer_y` and `ae_pointer_buttons`
(bit 0). Keys:

| Key | Effect |
|---|---|
| Tab, cursor right | Move focus right, wrapping |
| Cursor left | Move focus left, wrapping |
| Return | Choose the focused button |
| Escape | Choose the last button |
| 1–3 | Choose that button |

A press over a button focuses it. Releasing over the same button chooses it;
releasing elsewhere does nothing.

Both calls reply in `N_BUFFER`: the chosen button (0 while open), the focused
button, and four bytes of dirty cell rows (bit `r&7` of byte `r>>3`) for an
app that mirrors the surface to the VDC.

Opening saves the covered bitmap and colour bytes into an owner-30
allocation. Choosing a button writes them back exactly and frees it; a failed
restore keeps the alert open for another step. One alert may be open at a
time. When a different app attaches, an open alert's buffer is freed without
restoring, because the old surface no longer exists. The input loop stays in
the app because bank-1 code cannot call `N_KEYIN`.

## Events

`ae_event` waits like GEM `evnt_multi`. Fill `ae_ev_params` (16 bytes) and
call it; the result is in `ae_ev_result` (15 bytes).

Parameter bytes:

| Bytes | Meaning |
|---|---|
| 0 | Event mask: keyboard 1, button 2, rectangle 1 4, rectangle 2 8, message 16, timer 32 |
| 1 | Clicks wanted (1–3) |
| 2, 3 | Button mask and wanted state (bit 0 = left) |
| 4–8 | Rectangle 1: flag (0 = fire inside, 1 = fire outside), then x, y, w, h in cells |
| 9–13 | Rectangle 2, same layout |
| 14–15 | Timer, in jiffies |

Result bytes:

| Bytes | Meaning |
|---|---|
| 0 | Mask of the events that fired |
| 1 | Key |
| 2–3 | Pointer x |
| 4 | Pointer y |
| 5 | Buttons |
| 6 | Click count |
| 7–14 | Message |

The first sample is taken at the call, so the timer runs from the call.
A button already in the wanted state fires at once, as in GEM,
except after a press the menu bar or a window frame consumed. Like GEM's
screen manager, the AES keeps such a press until the button is released,
across waits, so an app never sees a click at an arrow or title it has just
been told about. Presses into
the wanted state are counted until the wanted number arrives or a 20-jiffy
double-click window closes; the count is reported. The window is timed from
the first press, so it also closes when the jiffy clock resets at midnight. Rectangle bounds are
half-open cells. Several events can fire together. At most one message is
delivered per wake.

`ae_post` queues an 8-byte message (`appl_write`). The queue holds 16; a
17th is refused with `N_NOMEM`. When a different app attaches, its queue and
wait state are cleared.

Between samples the client calls `N_KEYIN` with `N_READY` published, so the
app stays responsive to the kernel's idle contract. The pointer comes from
the app's `pm_poll` when it sets `AE_POINTER=1` and includes the 1351 module,
otherwise from `ae_pointer_*`. Time comes from the ROM jiffy clock
(`$a0..$a2`). Each sample is one banked call, so waiting is not free: the
cost per sample has not been measured.

## Menus

`ae_menu_install` draws a GEM menu bar on cell row 0 of `ae_surface`. Pass
the address of a NUL-terminated ASCII spec in A/X. The spec lists menus
separated by `;`; each is a title, `:`, then items separated by `|`. For
example:

`Desk:About...;File:New^N|Open...^O|-|Quit^Q`

In an item, a `^` suffix gives a Ctrl-letter shortcut and `-` alone is a
separator line.

Limits (anything else is refused with `N_BADARG`):
- up to 8 menus and 48 items, 12 items per menu;
- 16 characters per item;
- 400 bytes of text in total;
- every drop-down must fit the 38-column / 250-cell overlay limit;
- an empty spec removes the menu.

The bar's pixels stay on the app's surface, so the app must keep row 0 for
it.

`ae_menu_set` sets an item's state: A = menu, X = item, Y = flags
(1 checked, 2 disabled).

Menu input arrives through `ae_event`; the AES sees each sample before the
app's events:

| Input | Effect |
|---|---|
| F1 | Open the first menu |
| Press on a title | Open that menu |
| Hover | Highlight enabled items |
| Release on an item, or Return | Choose it |
| Cursor up/down | Move over enabled items, wrapping |
| Cursor left/right | Switch menus |
| Escape, or a press outside | Close the menu |
| An enabled item's Ctrl shortcut | Choose it without opening anything |

A disabled item's shortcut reaches the app as an ordinary key. While a menu
is open it owns input, as GEM's screen manager does: no other events are
reported. A choice closes the drop-down and queues `MN_SELECTED` (10), with
the menu in byte 3 and the item in byte 4. The app receives it as a
`MU_MESAG` event.

Drop-downs sit under their titles and are moved left when they would pass
column 40. They have a blank cell row above and below the items, so the
one-pixel frame never crosses item text. They use the same exact save-under
as alerts. Checked items show a check glyph; disabled items and separators
are grey. Every sample reports the cell rows it redrew in result bytes
15–18, and the client ORs them into `ae_dirty` for apps that mirror their
surface to the VDC.

## Windows

`AE_OP_WINDOW` (8) takes a sub-operation in `N_BUFFER[0]` and a handle in
`N_BUFFER[1]`. Every reply ends with four dirty-row bytes at `N_BUFFER[4..7]`.

| Sub-op | Name | Arguments → result |
|---|---|---|
| 0 | create | 2–3 kind (word), 4–7 full rectangle → [0] handle 1–7 (`N_NOSLOT` when all 7 exist) |
| 1 | open | 2–5 rectangle |
| 2 | close | - |
| 3 | delete | (must be closed) |
| 4 | set | 2 field, 3.. value |
| 5 | get | 2 field → [0..3] |
| 6 | find | 1 x, 2 y (cells) → [0] handle, 0 = desktop |
| 7 | fill | 2 pen (0 clear, 1 ink), 3 colour, 4–7 clip rectangle (handle 0 = desktop) |
| 8 | surface | 1–4 the app surface handle; call once before the others |
| 9 | outline | 1–4 x, y, w, h in cells: XOR a one-pixel outline on the surface; the same call again erases it (a client's own drag feedback, as graf_dragbox draws; GEMDESK's row drags use it). An AES built before this sub-op refuses it with `N_BADARG`. |

Kinds are GEM's: name 1, close 2, full 4, move 8, info 16, size 32, up 64,
down 128, vertical slider 256, left 512, right 1024, horizontal slider 2048.
Set fields:
- `WF_NAME` 2 (NUL-terminated, up to 16 characters);
- `WF_CURRXYWH` 5 (a new rectangle; moves or resizes an open window);
- `WF_TOP` 10;
- `WF_HSLIDE` 8 / `WF_VSLIDE` 9 (position 0–255);
- `WF_HSLSIZE` 15 / `WF_VSLSIZE` 16 (size 0–255 of the track);
- `WF_DESKCOLOR` 17, handle 0 only (minor 5): the VIC colour byte of cleared
  desktop cells. The AES repaints every visible desktop cell (pixels cleared)
  and queues `WM_REDRAW` for handle 0 so the app redraws its icons. The
  choice is kept in the image and outlives app changes.

Get fields:
- `WF_WORKXYWH` 4, `WF_CURRXYWH` 5, `WF_PREVXYWH` 6, `WF_FULLXYWH` 7;
- `WF_TOP` 10 (the handle, 0 when none);
- `WF_FIRSTXYWH` 11 / `WF_NEXTXYWH` 12 (see below).

Rectangles are in cells, at least 4×3, inside columns 0–39 and rows 1–24;
row 0 stays free for the menu bar.

Up to 7 windows are open at once. The frame is made of cells:
- a title bar (close box, centred title, full box; the top window's bar is
  in the focus colour);
- an optional info row;
- a right column with up/down arrows and a slider track;
- a bottom row with left/right arrows and a track;
- a size box in the corner, or in the right column's last cell when there
  is no bottom row.

There is no pixel outline around the work area, because the app repaints
work cells. Slider thumbs are `max(1, ⌈track × size / 256⌉)` cells long and
start at `⌊(position × (track − length) + 128) / 256⌋`.

A 1,000-byte cell map names the top window of every cell. Each open, close,
top, move or resize compares the new map with the previous one. The AES
then:
- clears desktop cells that were uncovered;
- redraws the frames of windows whose frame cells changed, whose rectangle
  changed, or whose top status changed, clipped to their visible cells;
- queues `WM_REDRAW` (20): `[20, 0, 0, handle, x, y, w, h]`. It covers the
  changed work cells of each window, and of the desktop as handle 0. A
  redraw already queued for the same handle is merged into one bounding
  rectangle, as GEM does.

The app answers `WM_REDRAW` by painting its work area clipped to the visible
rectangles. The fill sub-op does exactly that for solid areas.
`WF_FIRSTXYWH`/`WF_NEXTXYWH` list the visible rectangles of a window's work
area (handle 0: the desktop cells of rows 1–24): horizontal runs, extended
downward while the rows below hold the same run. Width 0 ends the list, and
any other window operation restarts it.

### Frame gadgets

Frame gadgets work through `ae_event`. After the menu bar, the window
manager sees each sample, and like GEM's screen manager it only reports
what happened; the app acts on it with `wind_set`. Messages are
`[type, 0, 0, handle, data…]`:

| Press on | Message |
|---|---|
| Any cell of a window below the top one | `WM_TOPPED` 21 |
| Close box | `WM_CLOSED` 22 |
| Full box | `WM_FULLED` 23 |
| Arrow | `WM_ARROWED` 24, byte 4 = GEM `WA_*` (0/1 page up/down, 2/3 line up/down, 4/5 page left/right, 6/7 line left/right) |
| Track beside the thumb | `WM_ARROWED` 24, page |
| Title bar (mover), dragged | `WM_MOVED` 28 on release, bytes 4–7 = the new rectangle |
| Size box, dragged | `WM_SIZED` 27 on release, bytes 4–7 = the new rectangle |
| Thumb, dragged | `WM_VSLID` 26 / `WM_HSLID` 25 on release, byte 4 = position 0–255 |

Title and size drags XOR a one-pixel outline that follows the pointer. The
candidate is clamped to the screen (rows 1–24) and to a 4×3 minimum, and is
erased on release. An unchanged drag sends nothing. Slider positions come
from the pointer's cell on the track: the first free cell is 0 and the last
is 255. While a drag is active the window manager owns input. A press in
the top window's work area, or on the desktop, reaches the app as an
ordinary button event.

The test oracle is the painter's algorithm. After any operation and the
demo's redraw responses, the surface must equal drawing the desktop and then
every window bottom to top from scratch. Missing or excess damage fails the
comparison.

### Text (minor 7)

Window sub-op 10 (`WS_TEXT`, GEM's `v_gtext`): `N_BUFFER` 1 handle, 2..3 the
first cell (x, y) counted in the work area, 4 pen, 5.. a NUL-terminated
ASCII string of at most 38 characters. The AES draws it with its 8x8 font
into the window's visible work area only, one visible rectangle at a time,
as the fill sub-op paints; cells keep their colours. The reply carries the
rows drawn. A window that is not open is refused.

## Double-click speed and the keyboard mouse

`AE_OP_DCLICK` (11, minor 6, capability bit 5) is GEM's `evnt_dclick`. Put
0 in `N_BUFFER[0]` to read the speed, or 1 with a speed 0–4 in
`N_BUFFER[1]` to set it; the reply's `N_BUFFER[0]` is the speed. The speeds
are windows of 40, 30, 20 (the default), 15 and 10 jiffies. The setting is
kept in the image and outlives app changes. The client's `ae_dclick` takes A
= speed, or `$ff` to read.

The client's event wait also emulates the mouse from the keyboard, as TOS
does with Alt and the cursor keys. With ALT or C= held (KERNAL `SHFLAG`
bits 8 and 2, checked in the C128 KERNAL `318020-05` key scan):
- the cursor keys move the pointer 8 pixels, clamped to the screen;
- Return presses the button for one sample and releases it on the next;
- with Shift as well, Return holds the button down until the next
  ALT+Shift+Return (a drag lock, as TOS's held Alt+Insert): the cursor keys
  then drag, and every drag the pointer can make (rows, icons, window
  borders, sliders) works from the keyboard.

Those keys are not delivered to the app.

## Desk accessories (minor 7)

`AE_OP_ACC` (12, capability bit 6) installs a desk accessory: `N_BUFFER[0]`
1 checks the image at bank-1 `AC_BASE` (`$4000`; identity `NACC` 1 at offset
32) and takes its four entries (menu, message, dispatch, reset) from offset
40; 0 removes them. The accessory, its exports (image offset 40: the
operation entry, the menu-item call, the queued message) and its scheduling
are described in [GEM-LAYER-DESIGN](GEM-LAYER-DESIGN.md#desk-accessories).
The entries stay installed across app changes; an app change still discards
every window, the accessory's included, and calls its reset entry.

## Session record

`AE_OP_SESSION` (10, minor 5, capability bit 4) keeps a 256-byte record in
the AES data segment. Put 0 in `N_BUFFER+256` to read it into
`N_BUFFER[0..255]` (`ae_session_read`), or 1 to write it from there
(`ae_session_write`). The data segment is cleared once, when first reserved,
so a freshly loaded AES reads zeros. The record survives app changes, unlike
the windows, menu and message queue. GEMDESK uses it to reopen its windows
when a launched program returns ([GEM-DESKTOP](GEM-DESKTOP.md)). The AES
does not interpret it; one record is shared by every app.

## Validation on attach

Attach finds the single owner-30 allocation at bank 1 page `$87` in the
handle table and reads its first 40 bytes through the heap service. It
requires the NBK1 header rules the loader enforces (format, ABI, flags, bank,
page count, entry range, exit stub, zero reserved bytes), the `NAES` identity
and major version, matching page tags, and a nonzero callback import. The
loader writes that import only after the body, CRC and source close have all
succeeded, so a zero import marks an interrupted load. The image cannot be
CRC-checked on attach because the import is live state; a stray write that
keeps the header intact is not detected. Attach then points the import at
the attaching app's executor.

## Example and test

`examples/native-aes` builds `AESDEMO.PRG` and `AESVC.PRG`. The demo attaches
or loads, shows the counters on both screens, and offers status (Return),
exit leaving the AES resident (Esc) and unload (U).

```sh
python3 -B tests/ci_native_aes.py --report /tmp/aes.json
```

The demo's A key shows `[3][Delete NOTES.TXT?|This cannot be undone.]
[Delete|Cancel]` over a fresh surface. The test renders every expected alert
frame independently (`tests/native_aes_scene.py`) and compares complete
surfaces. It covers focus movement with row masks, every choosing key,
pointer press/release, exact restoration of arbitrary pixels and colours,
and refusal of malformed or oversized strings. Planted bugs in the paper
colour, button spacing and restore path each fail it.

The demo's W key opens `Alpha` (title bar, close and full boxes), `Beta`
(info row, vertical bar with a slider at 64/128, size box) and `Gamma`
(horizontal bar with a slider at 200/64, size box). It fills each work area
in its own pen and colour on every `WM_REDRAW`. 1–3 top a window, M moves
and S grows the top window, C closes it, R records its visible rectangles,
and Escape closes and deletes everything. The demo answers the gadget
messages as a GEM app would: top, close, full/previous toggle, move/size to
the reported rectangle, and slider steps (line ±16, page ±64, clamped) or
positions. The window cases check complete
surfaces against the painter's-algorithm oracle and the rectangle lists
against an independent decomposition.

The demo's M key installs
`Desk:About AES...;File:New^N|Open...^O|-|Quit^Q;Options:Grid|Snap` with
Open... disabled; Options:Grid toggles its check. The menu cases compare
complete surfaces against `tests/native_aes_scene.py` for:
- F1 and cursor navigation that skips disabled rows and wraps;
- Return;
- enabled and disabled shortcuts;
- pointer open, hover, release-select and press-outside;
- the check mark after a set;
- Escape.

Planted bugs that make disabled rows selectable, or move the separator one
pixel, each fail the test.

The demo's E key waits with the parameters in `ae_ev_params` (default:
keyboard or 60 jiffies) and P posts a message. The event cases cover:
- the key;
- the timer at exactly 60 jiffies across a 16-bit carry, not at 59;
- single clicks and the already-in-state rule;
- a double-click inside the window, and a single click when it closes;
- rectangle enter/leave at the half-open bound;
- ordered messages and the 17th refused;
- the queue cleared for a new app.

Planted bugs in the click window, the rectangle bound and the timer
comparison each fail the test.

The test runs several apps in one machine and checks:
- the first app loads the component, which survives its exit;
- a second app attaches without loading and sees the persisted counters;
- unload returns every page;
- a wrong identity and a zero callback import are refused with `N_BADIMAGE`;
- an occupied `AE_BASE` range is refused cleanly;
- corrupt and missing `AESVC.PRG` files leave nothing resident.

The [VICE record](validation/2026-09-26-native-aes-vice/README.md) runs the
alert, menu and window demos on an emulated C128 against the same oracles.

Not yet verified: the AES alongside VDSVC in one app, and physical hardware.

The [qualification record](validation/2026-09-25-native-aes-persistent/README.md)
keeps the reports and the byte-identity evidence.
