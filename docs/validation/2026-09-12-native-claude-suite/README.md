# Native Claude and Ultimate suite, ABI 1.10

The suite includes a native **Claude** app and a read-only **Ultimate** panel.
Both are actual disk entries on the graphical-desktop and workspace-with-desktop
disks. The five-entry launcher preserves selection through app/workspace returns.
This checkpoint qualifies software on the CPU models and VICE; it contains no
new physical machine interaction and no live AI-service requests.

The Claude client is a native port of Marc Shade's MIT repository at
`b2941591f0caee460dfbfbec7d490a8af00c71a5`. It starts at `$6000`, has a checked
NAPP header, and allocates its BSS, C stack, ring and saved VDC font with its
code. The app uses native keyboard accounting. F8 sends BYE, drains the final
transmitted byte, restores serial/NMI/font/display state, and returns to the
desktop. Escape reaches the host application. The packaged Linux bridge uses
the existing wire protocol and manages the PTY without resetting the C128.

The new resident code fits existing reserved space: 147 query bytes at `$4b00`
and an eight-byte NMI mapping bridge at `$1bf0`. Heap capacity remains 426 pages.
The desktop uses 19 app pages plus 36 surface pages; Claude uses 49 app pages
and Ultimate uses 11. The Claude file is 4,655 bytes, including its PRG load
address; its BSS and stack are allocated without filling the disk with zeros.

| Qualification | Result |
|---|---|
| Frozen inputs | 401 files |
| Independent clean rebuild | 19 identical PRG and disk images |
| Disk extraction | CLAUDE and ULTIMATE match on both suite disks |
| Native CPU regression suites | All 30 pass, including seven Claude workflows, 30 query workflows and eight panel workflow groups |
| Additional desktop CPU workflows | All 24 pass |
| Host rendering checks | 30/30 pass, including captured upstream Claude output |
| Host stream/lifecycle controls | Four pass |
| Full desktop VICE workflows | 40- and 80-column startup; five apps, fallback, resident audits, app/workspace returns |
| Complete rendered VIC pixels | 1,920,000 compared |
| Serial VICE workflows | F8 exit and 80-column/host exit with the status panel |
| Serial receive observations | 459 and 1,603 bytes/NMIs; zero reported ring drops or ACIA overruns |
| Final serial-test state | Full original 4,096-byte lowercase fonts match; host exits 0, original NMI vector/pointer checked, all 426 pages free |

The serial tests run the real packaged bridge and native client against a
deterministic Python program in a PTY. They check complete 80×25 terminal
characters, a custom glyph, keyboard and Escape delivery, Help repaint,
both exit paths, desktop selection and cleanup. These prove the terminal
transport and lifecycle. They do not establish current Claude authentication,
a live model response or native Ultimate modem behavior on physical hardware.
The source data for the host rendering tests includes upstream Claude output.

`inputs/` contains source, tests and images. `inputs.json` pins them.
`cpu-regressions/`, `emulators/`, the host reports and extraction/rebuild records
hold the qualification evidence. The offline audit verifies the recorded input
hashes, app manifests, exact disk entries, all report outcomes, complete desktop
surfaces and rendered pixels, terminal characters, custom glyph and restored
font bytes. NMI restoration was asserted during execution; the serial archives
do not retain separate raw before/after NMI-vector snapshots.

Two development failures remain under `history/`. The first had correct terminal
output but an unjustified minimum receive-count assertion; the test now checks
the transmitted glyph minimum and complete repaint. The second exposed a real
shutdown race: DTR fell before the final BYE byte finished. The fixed client
waits for TDRE and a bounded final character interval before dropping DTR.
Neither failed run is counted as qualification.

```sh
python3 -B docs/validation/2026-09-12-native-claude-suite/verify.py
```

The preceding signed source is `28e867fa658c9e49e1db1f625fdbcdebe9a77918`.
Its [ABI 1.9 physical qualification](../2026-09-12-native-desktop-abi19-hardware/README.md)
remains the physical baseline. The added ABI 1.10 applications require their
own frozen physical qualification. Full desktop/window/input parity, additional
apps and mutating Ultimate controls remain on the OS roadmap.
