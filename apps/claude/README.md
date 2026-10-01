# Claude for Kestrel

Claude is a native C128 app in the Kestrel suite. Select **Claude** on the desktop,
or press **A**. It provides [graphical session controls](../../docs/NATIVE-CLAUDE-GUI.md)
on both displays, a complete 80-column VDC terminal, and paged left/right
terminal views on the VIC. Claude Code runs on your Linux host, using
that host's login, project directory and normal Claude permissions.

Build the suite with `python3 -B build-native-desktop.py`. This requires cc65
(`cl65` and `ld65`) in addition to Python 3, 64tass and VICE's `c1541`.
Both native desktop and workspace D64/D81 images contain `CLAUDE` and its
`VDSVC.PRG` graphics service. Keep them together when copying the app.

On the Linux host, install the bridge dependency in a virtual environment:

```sh
python3 -m venv .venv-claude
.venv-claude/bin/python -m pip install -r apps/claude/requirements.txt
```

Install and sign in to Claude Code on that host first; its `claude` command
must be on PATH. The bridge starts that command in an 80×25 PTY after the
C128 completes its handshake. `--command` selects another terminal
program when diagnosing the connection. The protocol sends terminal cells
and keystrokes; the client does not store an API key on the C128.

Configure the Ultimate modem for **DE00/NMI**, **38400 baud**, TCP port **3000**,
and dropping the connection when DTR goes low. Launch the app from the running
Kestrel desktop and press **Return** to open the modem. When the C128 shows
**waiting for the Linux bridge**, start the bridge on Linux:

```sh
.venv-claude/bin/python apps/claude/run.py --connect C128_ADDRESS:3000 --cwd /path/to/project
```

Replace `C128_ADDRESS` with the Ultimate's address. This order matters: the
Ultimate rejects an incoming connection while the C128 has DTR low. The app
refuses an already active serial port and reports an unavailable port on its
launch page.

| Key | Action |
|---|---|
| Return on the launch page | Open the configured serial connection |
| F8 | End the terminal session and return to the desktop |
| Escape on the launch page | Return to the desktop |
| Escape during a session | Send Escape to Claude |
| Help during a session | Request a full repaint and rearm modem answering |
| Ctrl+Help during a session | Enter or leave local graphical controls |
| Right mouse button during a session | Enter or leave local graphical controls |
| Tab/arrows in local controls | Select an enabled button |
| Enter/Space in local controls | Activate the selected button |
| Escape in local controls | Return keyboard focus to the terminal |

Connect, Repaint and Desktop also accept a port-1 1351 mouse. The view button
cycles through the status panel and the left/right terminal halves. Prev/Next
show rows 1–16 or 10–25. **Terminal** returns from the blue VDC controls to the
complete text screen. Incoming output continues into the retained terminal
while controls are open. The active VIC/color-VDC control is yellow; the
16 KiB VDC uses reverse focus. Ordinary terminal keys,
including Tab, Escape and F1–F7, retain their host meanings while local controls
are closed. The 80-column terminal keeps its full 80×25 area.

Returning closes the host PTY session. Start the bridge again for a new
session; the launcher does not run a host service automatically. The supplied
bridge uses only its selected serial TCP connection. It does not mount disks,
reset the C128 or change Ultimate settings.

On F8, the client continues receiving queued output until the host acknowledges
shutdown. If the host does not respond, the client returns after at most 20
seconds of the running C128 clock; a second F8 returns immediately. A stopped
clock also has a bounded polling fallback. If the display cannot be restored,
the app retains its saved state and waits for Escape or Desktop to retry before
returning to Kestrel.

The native port saves and restores the borrowed lowercase VDC font, affected
display registers, console selection, border, cc65 zero page and NMI vector.
It uses Kestrel keyboard accounting and releases its entire app allocation on
return. Bells flash the VIC border. Screen runs are clipped before touching
VDC RAM, and serial transmission waits are bounded.

This port is based on [marc-shade/claude-c128](https://github.com/marc-shade/claude-c128)
at `b2941591f0caee460dfbfbec7d490a8af00c71a5`. [UPSTREAM.json](UPSTREAM.json)
records original file hashes; [LICENSE](LICENSE) retains Marc Shade's MIT
notice. Native adaptations live in `src/native/claude/`; host adaptations
live in this directory's `host/`. [PROTOCOL.md](PROTOCOL.md) describes the wire
format. The upstream BASIC-started client and reset/bootstrap helpers are
not part of the native launch path.

Native qualification is tracked separately from upstream hardware claims.
The earlier Kestrel ABI 1.9 physical pass does not qualify this ABI 1.13 serial app.

The [initial software qualification](../../docs/validation/2026-09-12-native-claude-suite/README.md)
passes 30 native CPU suites, 34 host checks and four VICE workflows. The
[lifecycle update](../../docs/validation/2026-09-12-native-claude-lifecycle/README.md)
verifies handshake-controlled startup and acknowledged F8 shutdown.

Run `python3 -u tests/ci_native_suite_iec.py` for the shared five-app VICE
workflow. It uses a fixed PTY fixture and checks two Claude sessions, F8 and
host exit, font/NMI restoration and complete memory recovery. It requires
VICE, Xvfb and the bridge dependency, and sends no Claude model requests.
The [suite record](../../docs/validation/2026-09-12-native-suite-workflow/README.md)
also retains a physical attempt that stopped before app launch because input
changed during the initial desktop capture. Native physical modem testing
and an actual authenticated Claude session remain unverified.

The [follow-up input diagnostic](../../docs/validation/2026-09-12-native-input-trace/README.md)
recorded six ROM-produced and consumed keys during a CPU capture. The input
signal's source remains unknown. It also exposed mapped BASIC ROM in a host
read of high memory; that diagnostic requires corrected bank access before
reuse. The original physical deployment was restored, and temporary-file
cleanup completed after the failed run.


The native client temporarily defines the ten C128 programmable keys as single
key codes, including F8 and Help. This prevents the ROM's default `MONITOR` macro
from replacing F8. All 256 bytes of the original definition table are restored
on every exit, alongside the existing font, NMI, display and zero-page state.
The graphical app reserves 96 pages, 16 pages for the original font, 16 pages for its live font, 16 for terminal
cells/attributes and an optional 36-page surface. VDC controls also use the
33-page shared component and a screen backup in REU or main RAM. See the
[display qualification](../../docs/validation/2026-09-14-native-claude-displays/README.md).
The earlier [desktop pointer workflow](../../docs/validation/2026-09-12-native-pointer/README.md)
checks real ROM F8 return after launching Claude with the mouse.

Local controls now provide [Copy and Paste](../../docs/NATIVE-CLIPBOARD.md).
The clipboard survives app exits. Paste requires the matching bridge update
and sends validated ASCII as one bracketed paste, without a trailing Return.
