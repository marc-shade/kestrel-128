# Claude controls and retained terminal — 2026-09-14

Pass. Claude uses the suite's blue icon controls on both displays, keeps its
complete 80×25 terminal while controls cover the VDC, and exposes both terminal
halves and all rows on the VIC. Ctrl+Help or right-click opens local controls;
Terminal/Escape returns to the current full text screen. The green workspace
remains the explicit diagnostic/recovery view of the same OS.

[View the real VICE controls capture](claude-controls.png).

This checkpoint starts at signed commit
`84fac1ef9190f4f7f56741419ad58d91024b641e`. The prior shared REU document record
has SHA256SUMS hash
`197e30cfbb31e8613fa51b5d95cebdff34bf6f30039997925d549416c3d4103c`.
The previous record and four pre-existing untracked user files are preserved.

## Evidence

* 18 completed jobs: 35 named loaded-CPU cases, two private VICE cold boots,
  and complete disk-chain/BAM/payload checks across six boot images.
* Initial 40-column/16 KiB VDC and 80-column/64 KiB VDC sessions exercise the
  packaged app, real ROM Ctrl+Help, left/right 1351 buttons, TCP/PTY rendering,
  incoming output while controls cover the screen, and acknowledged return to
  the blue desktop. Both processes finish and their private disks stay intact.
* 36 independently checked canvases contain 3,328,000 compared pixels.
  All 438 CPU captures restore their borrowed scratch, resident and metadata
  bytes. Original font and NMI state return exactly; all 426 pages are free
  after returning through the desktop to the diagnostic workspace.
* CPU cases cover all 256 glyph codes, raw colors/attributes, both terminal
  halves/pages, cursor, clipping, scrolling, a split RUN across view changes,
  keyboard focus, absent/busy serial ports, clean memory/service refusals and
  retained display/source-CLOSE failures. REU tests cover 128 KiB and 16 MiB
  backing plus failed snapshot reads and recovery.
* A 3,228-byte paced stream produces 122 serial NMIs inside the bank-1 display
  service and 371 during native transfers. The receive ring peaks at the
  unchanged 192-byte host window, with no drops or overruns.
* An independent build reproduces all 34 native program/disk artifacts and
  generated assembly sources. Only Claude and the four suite/workspace disks
  change; all 29 other native artifacts, including the kernel, VDC provider
  and other app programs, retain their previous bytes.

The 94-page app separately owns 16 font pages, 16 terminal pages and a 36-page
bitmap. The shared provider occupies 33 pages. A REU snapshot leaves 231 main
RAM pages free; RAM snapshots leave 167 pages for a 16 KiB VDC or 159 for a
64 KiB VDC. The suite retains 124 free D64 blocks and 2,620 D81 blocks.

## Replay and provenance

Run the standard-library-only offline check from this directory:

```sh
python3 -B verify.py
```

`SHA256SUMS` covers every record file. `inputs.tar.gz` contains the final 745
input files. `executions.json` records each immutable test snapshot; matching
final input bytes are reused by path and hash, while twelve differing input
blobs are stored in `execution-blobs.tar.gz`. All five execution generations
share the exact same 363 production source/build/host/image identities.
The paired `*-files.json` manifests verify archive membership, sizes and hashes.

`jobs.tar.gz` holds commands, reports, logs, before/after input hashes and the
independent rebuild record. `outputs.tar.gz` retains private VICE disks, raw
CPU observations, canvases, screenshots and TCP/PTY logs. The standalone PNG
is the unchanged `dev5-vice64/claude-right-button-controls.png` capture.
`parent-images.tar.gz` and `rebuilt-images.tar.gz` support the byte comparison.
`changes.json` identifies the exact changes applied to the source checkout.

The ten earlier development jobs are excluded from qualification. Initial
retained-terminal tests predated the VDC integration; development also exposed
an incorrect temporary heap argument definition, startup test budget, a
right-button release being interpreted as a second click, and a stale error
flag after restoration. The final source uses the shared ABI definitions and
corrected input/recovery logic. A memory-refusal fixture initially occupied the
packer's scratch pages; the corrected fixture reaches the app's font/cell
allocation paths and verifies both clean refusal and partial-allocation cleanup.
These attempts remain in `development.tar.gz`; no failed attempt was overwritten.

This is software qualification. The fixture makes no Claude model requests.
Physical serial/mouse use and an authenticated Claude session remain unverified.
No physical deployment was performed. An uncertain component source CLOSE
retains its owners and waits for external recovery rather than discarding state.
The wider OS, office-app, windowing, clipboard, scheduling and expansion roadmap
remains open; this checkpoint completes the initial graphical migration of the
six current suite apps.
