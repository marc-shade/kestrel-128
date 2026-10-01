# Native desktop mouse and app returns — 2026-09-12

The blue native desktop now accepts a port-1 proportional 1351 mouse. Its five
icon buttons select on movement and open on left-button release over the same
button where the press began. Dragging away cancels the launch; a stationary
pointer preserves keyboard selection. Calculator, Editor, Files, Ultimate and
Claude all return to this desktop. Both suite disks include the change.

The pointer uses two single-color sprites in the existing surface's unused
padding, with no new heap allocation or resident kernel service. The desktop
restores the twelve sprite registers it changes and BASIC's sprite-hook flag
before app/workspace handoff or graphics failure. The PRG is 5,815 bytes and
reserves 23 pages; its 36-page surface leaves 367 pages free. The VIC shows the
graphical pointer; the VDC mirrors app selection in its keyboard text controls.

Mouse input is read once per jiffy in raster lines 80–159, after another 32
raster lines have elapsed since noticing that jiffy. A later ROM interrupt
restarts the settling interval; late frames are skipped. This accommodates
delayed keyboard scanning without an IRQ hook or blocking delay. The driver
preserves CIA directions/keyboard columns, rejects non-ROM CIA configurations,
baselines newly attached counters, filters +/-1 counter jitter and clamps both
axes. Disconnecting cancels an armed click, and a held button during entry or
reconnection cannot launch an app.

Real ROM input exposed a Claude issue: stock F8 expands to `MONITOR` followed
by Return. The client now supplies single-code definitions for all ten
programmable keys and restores all 256 original definition bytes on exit.
Its PRG is 4,930 bytes and reserves 51 pages. The serial verifier now observes
the acknowledged close result at a VICE execution checkpoint before cleanup;
reading freed terminal BSS after desktop replacement is no longer valid.

The CPU checks pass 12 pointer cases, 24 desktop cases and 11 Claude cases.
They execute all 16,384 circular counter pairs and 221 modeled pointer input
frames, covering gestures, bounds, keyboard selection, delayed scans, foreign
configuration refusal and restoration. The Claude CPU run is reused after the
final pointer-only timing adjustment: its test, workspace kernel and Claude PRG
remain byte-identical, as recorded in `provenance.json`.

VICE runs real host mouse/button and ROM keyboard events, with either console
selected at boot. Each run opens all five apps, checks normal returns including
actual F8, verifies every original function-key table, then exits to the
workspace with all 426 pages free. Thirty complete desktop frame pairs include
1,920,000 verified VIC palette-index pixels, including the cursor, plus full
VDC text. The two runs contain 284 CPU captures, 914 chunks, 425,800 payload
bytes and 1,136 matching borrower before/after pairs, with no rejected captures.
SID emulation remains enabled during warp, and the harness drains initial X
mouse-grab movement before taking long captures. See the recorded screenshots
in `vice40/desktop.png` and `vice80/desktop.png`.

A separate TCP/PTY Claude workflow verifies the actual serial NMI path,
keyboard delivery, Help repaint, glyphs, acknowledged closure, font/vector
restoration, host-process exit and final heap release. Its four CPU captures
contain eight chunks, 3,004 payload bytes and sixteen matching borrower pairs.
This uses a local PTY fixture; authenticated Claude qualification remains open.

`preliminary/` retains the disabled-BASIC-hook failure, the real F8 macro
failure and a capture affected by late pointer input. A focused negative
control confirms the preceding driver read both POT registers immediately
after noticing a jiffy; the new CPU case requires the full settling interval.
Pinned Commodore keyboard/IRQ source is in `references/cbmsrc/`.

`inputs/` freezes 414 source, helper and generated files. The main checkout
rebuilt all 21 PRG/D64 images byte for byte, as did a clean copy of the frozen
source. Only Desktop, Claude and the two
suite disks change program/image bytes relative to signed base
`5742c726b6ccdb7f962ef5d93209d30116674214`; both kernels and all other app PRGs
are unchanged. The signed checkpoint is local; nothing was pushed or deployed.

Run `python3 -B verify.py` to audit the sealed files, input hashes, packaged
apps, CPU reports, capture chunks/restoration, full rendered frames, serial
close checkpoint and final memory state. `main-rebuild.json` records the
integration comparison. No physical C128 access or modem configuration change
occurred. Physical mouse/adapters, port 2, right-button menus, object dragging,
shared widgets/windows and a graphical VDC desktop remain roadmap work.
