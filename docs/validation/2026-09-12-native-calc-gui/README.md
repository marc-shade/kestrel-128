# Native graphical Calculator qualification — 2026-09-12

The Calculator in both native desktop suite disks now uses the blue bitmap,
yellow focused buttons and shared 1351 input. The keypad, history paging,
verified history export and Save/Cancel dialog operate alongside the VDC text
view. Desktop and Calculator share pointer and scene code; a small button
library supplies hit testing and focus colors. See the
[app guide](../../NATIVE-CALCULATOR.md) and [screenshot](calculator.png).

Base: signed local commit `9d2b36234e490f4c682df346e09d903271471263`.
No physical C128 I/O, deployment, modem changes or push occurred. The broad
GEOS/Wheels/desktop/Ultimate/expansion roadmap remains active.

## Reproducibility and scope

425 frozen inputs reproduce all 21 native PRG/D64 images exactly, including
both suite disks. The integrated main build has the same 21 hashes. Only the
suite Calculator, Desktop and their two disk images change program/image
bytes; both resident kernels, the diagnostic Calculator and the other apps
retain their prior bytes. All packaged apps are extracted and compared.

Calculator is 9,354 PRG bytes, 37 app pages, plus two history pages and the
36-page surface; 351 managed pages remain free while graphics is active.
Its SHA-256 is `cec610120f3fc9d56c6d89e5d8e8b06458cf6465d15c472b47b57afa9e733bbd`.
Desktop remains 23 app pages. A refused display or occupied surface uses both
text consoles and releases any temporary surface. The desktop is reloaded
when Calculator closes.

## Qualification

- 43 assembled CPU groups: Calculator 7, shared pointer 12, desktop 24. These
  include 16,384 mouse counter pairs, arithmetic/error cases, every keypad
  control, drag cancellation, keyboard focus, full history, saving/collisions,
  cancellation, failed writes, filename editing and resource restoration.
  The original text Calculator also passes its arithmetic/history/export suite.
- Actual VICE mouse and ROM keyboard workflows pass from both 40- and
  80-column boot configurations. Each opens and returns from all five apps,
  computes `12 + 30 = 42`, saves `GUIHIST`, cancels another save and restores
  all 256 ROM function-key bytes after each app. Every original disk file is
  preserved; the sole new file is the SEQ payload `42` followed by CR.
- The shared CPU-capture workflow and the complete keyboard desktop workflow
  pass, including missing-surface fallback and recovery. Together the audit
  checks 57 full VIC palette frames, or 3,648,000 pixels, with complete bitmap
  data and VDC mirrors. This includes 10 Calculator frames with visible mouse
  pointers and two without a mouse.
- 426 CPU captures comprise 1,393 chunks and 649,858 payload bytes. All 1,704
  borrowed-state comparisons match; no final capture is rejected. Resident
  code and final release of all 426 pages and 32 handles are checked.

The initial runs retained in `preliminary.tar.gz` failed test-fixture
assumptions: a real mouse move crossed Newer and changed focus; page-table
bytes contain handle tags rather than owner IDs; and the Files oracle still
used the diagnostic browser's labels. The corrected checks retain exact
surface and file comparisons. These are not qualified runs.

The fixed window is an application front end. Movable/overlapping windows,
remaining graphical apps, a graphical VDC desktop, physical input/timing,
scientific Calculator modes and persistent sessions remain open.

## Audit

```sh
python3 -B verify.py
```

The archive stores all 8,810 original payload files (34,759,641 bytes) in
lossless tar/gzip files to avoid thousands of duplicate repository entries.
Each member has its own size and SHA-256 in the corresponding `*-files.json`.
The auditor extracts only validated regular files into a temporary directory,
checks the raw captures, independently reconstructs pixels, validates NAPP
headers, compares disk contents and verifies rebuild hashes. `SHA256SUMS`
seals this record, including archives, manifests, auditor, reports and images.
A normal audit does not modify the record. `--record` is refused after sealing.

CPU models, VICE video and physical hardware are distinct evidence. This
checkpoint qualifies the first two; physical C128 deployment is pending.
