# Native blue Ultimate drive controls

The Ultimate app now uses the blue suite controls and shared mouse, with
identification, Drives, Network and Clock pages. The Drives page opens the
shared image picker and presents a complete path and IEC destination before
mount/eject. Cancel is selected initially. Each confirmation refreshes the
inventory, protects boot/source addresses and previously observed system slots,
and refuses ambiguous/off/unsupported drives and open files. An accepted
request is labeled as accepted; the reference firmware does not report the
subsystem result, so mounted-media verification remains open.

This is a local software checkpoint based on
`f5d9b9a57de5ead6883deddf295df4d2c157f898`. No physical hardware I/O or push was
performed. The full OS roadmap and physical native suite remain unfinished.

## Implementation and memory

ABI 1.11 adds `N_UCOMMAND=$1c71`, sharing the existing bounded file/query
transport. `N_FCOUNT` is the number of body bytes after the two-byte header:
0–510. Invalid lengths and wrap are rejected before sending; the response
replaces the buffer. Transport serialization does not supply command-specific
resource policy. The native app supplies the drive checks and never replays an
uncertain operation.

The 56-byte command service fits reserved memory at `$4b93..$4bca`. The 25-byte
keyboard-input wrapper moves to `$49e4..$49fc`. The heap remains 426 pages.
Ultimate occupies 20,616 bytes / 81 pages, plus its 36-page bitmap and lazy
picker caches. Cleanup releases the app and surface; an uncertain picker close
retains ownership and blocks mount/eject/exit until explicit Refresh recovers.
The picker temporarily uses both text displays and then restores the blue view.

## Qualification

- 32 kernel/app CPU suites completed. The first SDK invocation lacked
  the isolated example inputs; its failure is retained in `core-cpu.tar.gz`.
  The five unchanged example sources were copied and all 15 SDK workflows pass
  in `cpu/sdk.json`. The other 31 suites pass in the original batch.
- 27 targeted application groups pass: drive policy 11, graphical controls 8,
  and the existing complete panel/invalid-response workflows 8. These include
  255-byte paths, full request/reply limits, both DOS contexts, default Cancel,
  changed destinations, foreign files, target rejection, long display data,
  and retained picker-abort recovery.
- Full mouse workflows pass with both 40- and 80-column boot defaults, across
  Calculator, Editor, Files, Ultimate, Claude and Paint. The keyboard-only full
  suite also passes. All 107 complete 320×200 palette frames are rechecked
  offline (6,848,000 pixels), including 20 Ultimate frames and 24 Paint frames.
  Calculator history and Paint files are reopened and compared in the private
  D64s. App input, display state, resident code and all 426 pages return intact.
- The shared desktop/Ultimate workflow passes two actual TCP/PTY Claude
  lifetimes, including acknowledged F8 and host exit. Shutdown outcome is read
  at a VICE execution checkpoint before `native_video_end`, while Claude still
  owns its allocation. The next desktop may reuse that memory. Fonts and NMI
  state match their original bytes afterward; both host processes exit normally.
- Raw CPU observations contain 917 captures, 3,076 chunks,
  1,440,243 payload bytes and 3,668 matching borrower pairs.
  No rejected capture is used as passing evidence.

The frozen archive contains 471 inputs. Independent frozen and main builds
reproduce all 22 PRG/D64 images exactly. Six images change from the baseline:
two kernels, the Ultimate PRG and three D64 images. The auditor checks complete
disk contents, checksums, pixel planes, input restoration, running code and
serial shutdown evidence from the retained raw files.

## Retained development failures and limits

`preliminary.tar.gz` retains the earlier builds and runs: assembler/validator
integration failures, fixture corrections, the first mouse focus/mapping checks,
the initial Paint pointer-settling assertion, and serial test setup/lifetime
failures. Mouse movement now requires a coherent, settled position before the
first capture; failed readbacks are not replaced. Stock GTK maps C128 Tab to
host F10. The serial bridge uses the system Python with its existing `pyte`
dependency, and shutdown observation precedes allocation reuse.

Native physical drive operations, mounted-media identity, dirty-image handling,
drive settings, image creation, graphical VDC presentation and the broader
roadmap remain open. A physical suite attempt additionally needs the qualified
bank-aware high-RAM diagnostic and a transport-specific live shutdown observer.
The existing physical bridge factory does not supply that observer and is
refused before this workflow starts. Historical sealed records are unchanged.

## Recheck

Run `python3 verify.py` here for the offline archive, frame and lifecycle audit.
`SHA256SUMS` seals every other file in this directory. `rebuild.py` records the
separate build comparisons; it refuses to write into a sealed record.
