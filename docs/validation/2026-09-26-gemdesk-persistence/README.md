# GEMDESK persistence, desktop colour and Format — 2026-09-26

## What changed

- **AES 1.5:**
  - `AE_OP_SESSION` (10): a 256-byte record in the data segment that
    outlives app changes;
  - `WF_DESKCOLOR` (17) on handle 0: the desktop colour, repainted by the AES,
    with `WM_REDRAW` so apps redraw their icons. The choice is kept in the
    image.

  `AESVC.PRG` is 14,029 bytes; its code ends at `$becb`.
- **GEMDESK:**
  - a 64-byte desktop record (preferences, colour, windows), written to the
    AES session before a launch and restored on return;
  - Options:Save Desktop writes the record to DESKTOP.INF, which a cold start
    reads;
  - a desktop colour choice in Preferences;
  - File:Format, which sends `N0:NAME,ID`.
- **GEMDESK memory:** the image had grown 6 bytes past its slot. The
  visible-row buffer now shares storage with the sort buffer, and the sort
  order with the directory-page buffer; none of them are live at the same
  time. The core now ends at `$bd07`.
- **Test model:** `StreamIEC` formats (`N0:` erases the device's files).

## Evidence

Py65 at CPU level, in a scratch copy of the tree identical to this commit's
`src/`, `tests/` and build script. Images: `gemdesk.prg` `8581c3b7…`,
`aesvc.prg` `c2ab49fa…`.

- `tests/ci_native_gemdesk.py` → `gemdesk.json`: 32/32. The new cases:
  - Relaunch: after a launch, a second GEMDESK starts on the same machine
    with the AES resident, as the dispatcher does. The drive window comes
    back with its rectangle and selection.
  - The desktop colour repaints the desktop and its icons.
  - Save Desktop writes exactly the expected 64 bytes, after scratching the
    old file.
  - A cold start from DESKTOP.INF reopens the window with its sort, colour
    and confirm setting. The confirm setting is proven by an unasked delete.
  - Format: the empty-name refusal, drive choice, fields, confirmation, the
    exact `N0:BLANK,B1`, and the listing emptied (a locked file included).
- `tests/ci_native_aes.py` → `aes.json`: 31/31 on this AES.

Planted bugs, each in a rebuilt copy of the tree:

| Planted bug | First failing case |
|---|---|
| Windows not restored from the session | windows back after the launch |
| Format's confirmation defaults to Format | format confirm |
| AES paints the desktop in its fixed colour | grey desktop |
| Save Desktop skips scratching the old file | Options:Save Desktop (the scratch command is missing) |

A real bug was found by the cold-start case: DESKTOP.INF was read, but its
bytes and count were checked after `N_FCLOSE`, which reuses them. They are
now copied first.

## Limits

- CPU level only; not run in VICE or on a C128, and DESKTOP.INF has not been
  written to a real drive.
- One session record is shared by every AES app.
- Only the top window's place in the stack is kept; the others reopen in
  slot order.
- A window whose drive fails is dropped without a message.
- Format shows no progress and does not verify.
