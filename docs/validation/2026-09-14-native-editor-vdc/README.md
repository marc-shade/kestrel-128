# Native Editor on VIC and VDC — 2026-09-14

Editor now carries its blue document view, caret, yellow focused controls,
file dialogs, search and shared picker onto the VDC. A 64 KiB VDC shows color;
a 16 KiB VDC uses white on blue and reversed focus. The complete 40-column
graphical surface is mirrored at 640×200. This is a software qualification;
these images have not been deployed or qualified on the physical C128.

The parent is signed commit `0e1704f6a522f130936dfe200e3421be9258c10f`.
The previous Files record has SHA256SUMS digest
`c3efc55ba8eb7c767a9761cc331c19571d7055553c1d7114ddb97fe067c987d4`.
The kernel, banked VDC provider, diagnostic Editor and six other app programs
remain byte-identical. Only suite Editor, its two modules and four
suite/workspace disk images change among the 34 native artifacts.

## Storage and recovery

The ABI 1.12 Editor keeps its 96-page application allocation. Before changing
keys or initializing documents, it reserves and zeroes sixteen bank-0 pages
at `$5000..$5fff`. Document transfer buffers, read cache and saved keys remain
available while graphics and picker alternate in one checked module window.
The inactive graphics body/cache and picker scratch share the upper half of
that workspace. Editable fields and live descriptors stay in the app.

The expanded core PRG is 14,076 bytes, packed to 9,500. The module window starts
at `$96fa`; the 10,223-byte picker payload ends at `$bee9`, with 279 bytes before
`$c000`. Search and graphics use 9,634 bytes, ending at `$bc9c`. Both modules
bind to the same core checksum and load beside the original Editor source.
The VDC service, screen snapshot, surface handle and normalized pointer survive
successful picker swaps. USB installations include matching `EDITOR`,
`EDPICK.PRG`, `EDFIND.PRG` and `VDSVC.PRG`.

Failed display updates pause file transfers and search before continuing past
the displayed position. While restoration is blocked, ordinary keys and
repeated failed Escape attempts preserve document contexts, transfer buffers,
output bytes, streams, owner records, handle tokens, keys and stack. A successful
Escape restores the display before entering the existing cancellation path.
The input loop repaints the complete text view after restoration; Ctrl-L can
reacquire graphics. Module errors retain their original error value through
display cleanup, and app exit waits for successful restoration before releasing
owners.

Search shows its current hexadecimal byte position. The first redraw occurs
after initializing that position and before scanning. A partial Replace All
check stops at byte 256 with exactly 26 replacements; ignored input cannot
change them, and cancellation followed by Save As writes those exact bytes.
The busy dialog retains its preceding document background while logical
replacement and search positions advance. The oracle checks that background
separately from the actual document bytes and progress.

Documents still use main RAM in 4 KiB chunks. The measurements below are for
an otherwise empty Editor, then a transactional Open while retaining a dirty
four-byte old document. They are not a universal maximum file size.

| Screen backing | Initial free heap pages | Pending Open bytes before memory refusal |
|---|---:|---:|
| 16 KiB VDC, main RAM | 184 | 36,864 |
| 64 KiB VDC, main RAM | 176 | 36,864 |
| REU screen snapshot | 248 | 53,248 |

All three refusals preserve the old document and allow a subsequent verified
Save As. The earlier 66 KiB graphical-document result predates this VDC
provider and does not apply with it active. REU-backed documents remain
required work on the completion roadmap.

## Evidence

The selected 28 jobs include 53 counted CPU cases and two complete VICE
desktop → Editor → picker → verified Save As → Find → desktop workflows.
The CPU checks cover both VDC capacities and addressing modes, mouse and
keyboard controls, long Ultimate paths, source-directory reloads, file
cancellation, exact retained recovery, module/surface refusal, REU lifetimes,
scratch conflicts, packed startup and memory-limit rollback.

The D64/1541 workflow uses a color 64 KiB VDC and a separate device-9 data disk.
The D81/1581 workflow uses a 16 KiB VDC and a 16 MiB REU, saving on device 8.
Both begin in 40-column mode. Independent disk parsing recovers the complete
ten-byte `GUINOTE` file from each run and preserves every shipped file.
All application allocations are released after returning to the workspace;
programmable keys, callback and borrowed capture regions are restored.

The offline audit compares 74 complete VIC/VDC canvases, totaling 7,104,000
pixels. It compares four exact VDC screen restorations and independently
decodes 33,554,432 REU bytes from the two restoration snapshots. The monitor
proof checks the stopped program counter and MMU configuration, in addition
to checkpoint metadata. Desktop and app restore labels are distinct.

An independent rebuild reproduces all 34 native PRG/disk artifacts and
reassembles the expanded Editor core. The standalone verifier validates
packed programs, both module bindings, all six disk directories, file chains,
boot sectors and allocation maps. The suite has 144 free D64 blocks and
2,640 free D81 blocks.

## Input generations and retained attempts

`inputs.tar.gz` contains the 722 final input files. The selected source-recovery
job used a development checkout whose captured runtime inputs all match those
final inputs. The completed D81/REU job used the same program bytes, runner,
scenes and capture helpers; only the unused CPU recovery test differs, to bind
its original graphical base before monkeypatching. Its original source and
runtime manifest remain in `jobs.tar.gz`. These two passing runs are retained
without repeating them. The other 26 jobs use the final frozen checkout.

`development.tar.gz` preserves the earlier source generations, passing and
failed development reports, diagnostics and the interrupted D64 attempt.
That host runner ended with signal 143 after the Find dialog; the signal's
origin is unknown. Its emulator and private X server were confirmed absent
before a later workflow began. The incomplete attempt is excluded from all
passing workflow and canvas counts. The final D64 workflow uses a separately
supervised process and its own disk and capture directory.

The initial development failures also exposed two production defects:
partial text repaint after restoration and one extra 512-byte file transfer
after a failed progress update. The fixes and passing follow-ups are retained.
Other failures were oracle issues: service-return scratch was mistaken for
ownership data, an unchanged search screen performed no VDC write, busy search
was checked as a live document viewport, and a monkeypatched recovery class
recursed. Those failed attempts are not counted as passes.

## Reproduction

Run the archive-only audit with the standard library:

```sh
python3 verify.py
```

`SHA256SUMS` seals every other record file. Each archive has a complete
member-size and SHA-256 manifest. `jobs.json`, the job status files, commands,
logs, build report and original inherited statuses preserve what was run.
`outputs.tar.gz` contains the completed VICE observations;
`rebuilt-images.tar.gz` and `parent-images.tar.gz` support byte comparisons.

CPU reruns need Py65; builds need Python, 64tass, cc65 and c1541. VICE runs also
need Xvfb, ImageMagick and the recorded C128 ROM. The ROM is identified in
provenance and is not redistributed as a standalone input. The current VICE
launcher still depends on the local `cbm` helper under
`<home>/.claude/skills/commodore-basic/bin`; removing that dependency remains
a tooling task.

Claude VDC controls, REU document backing, clipboard, undo, window management,
scheduling, office apps, printing, expansion drivers and physical qualification
remain open in the full [implementation roadmap](../../IMPLEMENTATION-ROADMAP.md).
