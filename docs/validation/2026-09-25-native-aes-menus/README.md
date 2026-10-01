# AES menu bar (GEM layer step 4) — 2026-09-25

The persistent AES gains a GEM menu bar (AES minor 3, capability bit 2):
- bank-1 ops 6 (install) and 7 (item flags);
- menu input handled inside the event wait;
- `MN_SELECTED` queued as a message.

See [NATIVE-AES](../../NATIVE-AES.md#menus).

## Evidence

`~/.venvs/uos-tests/bin/python -B tests/ci_native_aes.py` → `aes.json`,
22/22 cases: the 18 earlier cases plus 4 menu cases on the `DisplayBus` VIC
model. Each menu state is compared as a complete surface against
`tests/native_aes_scene.py`, which parses the spec and renders the bar and
drop-downs independently.

The menu cases cover:
- F1 and cursor navigation that skips a disabled item and a separator, and
  wraps;
- Return choosing File:Quit, with exact bar restoration and the save-under
  freed;
- Ctrl-N choosing without drawing;
- disabled Ctrl-O reaching the app as a key;
- pointer press on a title, release keeping it open, hover, and
  press-and-release choosing Options:Grid;
- the check mark drawn after `ae_menu_set`;
- a press outside closing;
- Escape closing first, then reaching the app.

Mutation check: every row selectable, and a separator one pixel low, each
failed the first menu case. The source was restored.

Found while qualifying:
- the drop-down frame crossed the first item's text row, so item repaints
  erased it (fixed with margin rows);
- margin cells kept the app's colour (the drop-down paper is now painted);
- the renderer flagged the demo's 17-character item, over the 16-character
  limit.

`AESVC.PRG`: 9,475 bytes, 38 pages, CRC16 `$df3f`.

## Limits

CPU-level only, no physical C128. No suite app uses the menu yet. The AES
now fills 38 of its 48 pages: the window manager needs the menu text pool
and queues moved into an owner-30 data allocation.
