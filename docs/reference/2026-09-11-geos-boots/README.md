# GEOS128 reference boot observations

Disposable copies of the inventoried `GEOS128.D64` reach the visible desktop
in VICE 3.10 with initial `-80col` and `-40col` settings. Both runs use a
1541 on device 8, the explicit 16 KiB VDC setting and warp mode. The original
disk and both working copies remain byte-identical, with SHA-256
`8a624171f77de414789b46225d4a2a58b8185990f67405b8aacdaaad8e1b0a2c`.
No physical C128 or uOS program image is used by these reference runs.

The desktop shows disk `System 128`, 16 files, zero selected, 123 Kbytes used
and 43 Kbytes free. Its visible menus are geos, file, view, disk, select, page
and options. The first page includes GEOS128, GEOboot128, 128 Configure,
128 Desktop, 128 Joystick, MPS-803, Preference Manager and Pad Color Manager.
The Configure/Desktop icons carry a `2.0` label; an About/version dialog has
not been opened, so the executable's actual runtime version remains unverified.

| Initial setting | Final host capture | Outcome |
|---|---|---|
| `-80col` | [Desktop capture](initial/80/host-display-090.png) | Visible desktop; original and working disk unchanged |
| `-40col` | [Desktop capture](retry40/40/host-display-090.png) | Visible desktop; original and working disk unchanged |

These are boot observations. Mouse/keyboard interaction, menus, app launch,
file changes, preferences, display switching and return behavior still need
their own comparison workflows. No uOS functional or GEOS binary-compatibility
claim follows from a reference-system boot. Warp timing is not a hardware
performance measurement.

The first attempt at the 40-column run used an unsupported `+80col` option.
VICE exited before boot. Its exact script, report and diagnostic are retained
under `initial`; the completed 80-column part of that invocation remains valid.
Local VICE help confirmed `-40col`, and `retry40` records a fresh private run
with that option. Its console's generic “both boots” completion message refers
to a script default; the report correctly contains only the requested 40-column
retry.

[observations.json](observations.json) records the original evidence paths,
launched commands, executable/support-file hashes and hashes of the seven ROM
files named in VICE's startup logs. The logs also record `VDC64KB=0`.
Each completed run retains host screenshots and CPU-visible MMU/VIC register
snapshots at 30, 60 and 90 seconds, plus the selected-display exit screenshot.
The original reports retain hashes for complete RAM-bank and VDC captures;
those dumps and disk images remain in the private evidence directories and
are not included here. The executed capture scripts are retained unchanged.

`SHA256SUMS` covers every retained file except itself. The next reference gate
is an authentic input workflow that establishes the running version and then
launches, edits, saves and returns from a named application on a disposable
data disk. The [local fixture inventory](../../REFERENCE-FIXTURES.md) and
[completion roadmap](../../IMPLEMENTATION-ROADMAP.md) track that remaining work.
