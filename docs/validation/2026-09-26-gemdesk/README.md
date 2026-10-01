# GEM desktop, first build (GEM layer step 7) — 2026-09-26

GEMDESK is a TOS-style desktop on the persistent AES. It runs on a new GEM
boot profile, `target/native-desktop/gem.d81`:
- GEMDESK is written as `browse`, so apps return to it;
- the card launcher is written as `cards`;
- `aesvc.prg` sits beside them.

The regular suite disks are unchanged. See
[GEM-DESKTOP](../../GEM-DESKTOP.md) for the v1 scope and status.

## Evidence

`~/.venvs/uos-tests/bin/python -B tests/ci_native_gemdesk.py` →
`gemdesk.json`, 8/8 cases. Every visible state is compared as a complete
9,216-byte surface against `tests/native_gemdesk_scene.py`, which composes:
- the AES painter's-algorithm window oracle;
- the menu-bar oracle;
- independently drawn icons;
- listing rows formatted from the fixture's directory as `N_DIRPAGE`
  normalizes it.

The cases:
1. Startup: GEMDESK loads `AESVC.PRG` from its boot folder (owner-30 image
   resident), then draws the menu bar and icons.
2. Clicking icons selects and deselects them.
3. A double-click on the boot drive opens "Drive 8" with all 22 entries,
   clipped rows and slider.
4. The down arrow scrolls one row; a click and cursor-down select rows.
5. File:Close (Ctrl-W) closes the window and frees its listing.
6. Desk:About (F1, Return) shows the exact alert; OK restores the desktop
   exactly.
7. Options:Launcher (Ctrl-L) replaces the desktop with `CARDS`.
8. A double-click on a listed file hands `FILE00` on device 8 to the
   dispatcher.

Mutation check: listing rows one row low, and a slider that ignores the
list length, each failed case 3. The source was restored and rebuilt; the
final report is from that build (GEMDESK SHA-256 `e125ba2d…`).

## An AES bug this found

After a press on a window gadget, the app called `ae_event` again with the
button still held. The new wait's first sample took the held button as a
fresh press, so a stray click landed on the list under the arrow. The AES
now works like GEM's screen manager: a press the menu or a frame consumed
stays theirs until release, across waits. The scroll case above is the
regression test; the full AES suite was rerun after the change (31/31, see
`aes.json`).

Image sizes: `AESVC.PRG` 13,966 bytes (55 pages); `GEMDESK` 8,509 bytes
packed (46 pages). The D81 has 2,423 blocks free.

## Limits

- CPU level only; not run in VICE or on a C128.
- Built but untested: drive 9, paging and thumb answers, several windows
  at once, and the error alerts.
- Not built yet: Show Info, Delete, dragging to Trash, View sorting, and
  Ultimate folders. Trash has an icon only.
- Apps launched from GEMDESK get the AES resident, but GEMDESK's windows
  are not restored when it reloads.
