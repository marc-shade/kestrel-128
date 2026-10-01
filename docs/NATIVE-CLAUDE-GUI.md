# Claude session controls and terminal views

Claude shares the suite's blue bitmap, icon buttons and yellow focus. The
VIC shows Connect, Repaint, Desktop, a view selector and Prev/Next. The view
selector cycles between the status panel, the terminal's left 40 columns and
its right 40 columns. Prev/Next show rows 1–16 or 10–25. Every terminal cell,
attribute, cursor position and custom glyph is retained across view changes.

The VDC shows the same graphical controls on the launch page and while local
controls are open. During a connected session it shows the complete 80×25 text
terminal. **Ctrl+Help or the right mouse button** opens or closes local controls.
The visible **Terminal** button and Escape return to the full terminal. A
64 KiB VDC displays the suite colors; a 16 KiB VDC uses white graphics on blue
with reverse focus. The VIC terminal viewport remains usable on its own.

On the launch page, Tab/arrows select a control and Enter/Space activates it.
Return initially selects Connect. Escape and F8 return to the desktop. An
unavailable or busy modem appears on the second status page.

During a session, ordinary keys, Tab, arrows, Escape and F1–F7 reach the host.
Help requests a repaint. While local controls are open, Tab/arrows select and
Enter/Space activates; Escape closes the controls. Mouse buttons work alongside
keyboard input. F8 and Desktop request acknowledged shutdown; another F8 forces
host-session closure. Display recovery still has to finish before app exit.

Incoming output continues while the VDC shows controls. The app updates its
retained terminal, then restores the current cells, attributes, live font and
cursor when returning to text. A view change between a RUN header and its last
payload byte preserves the parser's pending command. No host protocol change
or extra pause acknowledgement is required.

## Memory and display ownership

The cc65 image embeds a 64tass GUI at `$6080`, after native startup at `$6020`.
`native_claude_scene.py` generates the frame and button states. Runs encode a
count and value; literal blocks keep mixed bitmap data compact. Both encodings
may cross the native transfer buffer boundary.

The app owns 96 pages, including serial buffers, BSS, C stack
and packed-startup cleanup tail. A separate 16-page allocation retains the
original VDC font until restoration succeeds. It reserves 16 bank-0 pages at `$5000` for the
live font, allocates 16 bank-1 pages for terminal cells/attributes, and reserves
36 pages at `$c000` for the optional VIC bitmap. The full terminal allocation
has separate checked handles and never overlaps the bank-1 display service.
The resident kernel and 426-page heap are unchanged.

`VDSVC.PRG` supplies VDC graphics from the app's original system volume. Keep it
beside Claude when copying the app. Its 39-page bank-1 image owns a 64-page
monochrome or 72-page color screen snapshot, using the shared REU arena when
available and checked main RAM otherwise. With REU backing, Claude leaves
207 main-RAM pages free; with a RAM snapshot it leaves 143 or 135 pages.
These counts assume an empty clipboard.
A clean model allocation refusal retains the original VDC terminal and VIC
status panel. A missing or invalid display service keeps the VIC controls and
text terminal available. An uncertain source CLOSE retains its owners.

The foreground renders one dirty visible row per input poll after draining
received bytes. The NMI handler only queues serial input; it never calls the
native APIs or accesses the VDC. The unchanged bridge window permits 192 bytes
in flight, replenished in 64-byte credits. No credits are sent while a
synchronous display call is in progress, so the 255-byte usable receive ring
can hold that entire window while the component runs in bank 1.

Claude saves all 256 programmable-key bytes and installs the shared KEYCHK
filter in the unused tail. The shared filter verifies every decoded key
against its matrix row and column, rejecting mouse signals and stale nested
scan results. Ctrl+Help uses the scan's modifier flags. The Commodore ROM contract is documented in
[source provenance](COMMODORE-SOURCE-REFERENCE.md); the right-button line also
matches [VICE's 1351 implementation](https://raw.githubusercontent.com/VICE-Team/svn-mirror/main/vice/src/joyport/mouse_1351.c).

VDC port waits are bounded. A graphics fault keeps the terminal, snapshot,
component and callbacks owned while Escape retries restoration. During active
recovery, serial output can still update the retained terminal. On final exit,
serial shuts down first; the snapshot, original font and display registers
must be restored before callbacks, keys, bitmap and model allocations are
released. The blue desktop regains control only after that cleanup succeeds.

## Qualification

The [display qualification](validation/2026-09-14-native-claude-displays/README.md)
records loaded-CPU tests and private VICE cold boots. Tests cover complete
VIC/VDC surfaces, all 256 glyph codes, attributes, both terminal halves/pages,
split commands across view changes, real ROM keyboard and mouse input, paced
serial NMI through bank-1 graphics calls, clean fallbacks and retained failures.
The TCP/PTY fixture sends deterministic terminal output; it sends no model
requests. Both cold-boot display choices return to the blue suite desktop with
font, keys, NMI and all app pages restored.

The current suite keeps 96 free D64 blocks and 2,592 free D81 blocks. This work does not
install a physical build. Physical serial/mouse qualification, an authenticated
Claude session, wider display modes, independent desktop windows, REU/image clipboard formats
and the remaining [OS roadmap](IMPLEMENTATION-ROADMAP.md) remain open.

The [shared text clipboard](NATIVE-CLIPBOARD.md) adds Copy and Paste to local
controls. Copy exports the full retained terminal as ASCII rows; Paste uses
the negotiated, acknowledged bridge extension. Ctrl-C/Ctrl-V remain terminal
keys when local controls are closed.

The [shared clipboard qualification](validation/2026-09-14-native-shared-clipboard/README.md)
records the exact software inputs, app handoffs, failure recovery and cold-boot
emulator workflows for this version. Physical deployment remains pending.
