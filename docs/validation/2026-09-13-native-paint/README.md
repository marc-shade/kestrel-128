# Native Paint and shared input qualification — 2026-09-13

Paint is the sixth icon on the intended blue uOS desktop. Its blue controls
include pencil/eraser strokes, a 16-color palette, a visible keyboard brush,
viewport scrolling, one-step undo/redo, verified Save As, staged Open, and
unsaved-picture prompts. See the [app guide](../../NATIVE-PAINT.md),
[desktop screenshot](desktop.png), [Paint screenshot](paint.png), and
[Save As screenshot](save-dialog.png).

Desktop, Calculator and Paint share the pointer and ROM key-check filter.
The filter rejects ambiguous port-1 button transitions and
restores the prior callback and complete function-key table at close. Paint
retains keyboard ownership across its text file picker. The filter follows
the matrix/callback contract in the pinned Commodore editor source; no ROM
implementation was copied. It changes no IRQ vector or MMU mapping.

Base: signed local commit `e9a504034a581e1ba479d7ca6a865f6e44b6d48b`.
No physical C128 I/O, deployment, modem changes or push occurred. The broad
GEOS/Wheels/desktop/Ultimate/expansion roadmap remains active.

## Reproducibility and memory

452 frozen inputs reproduce all 22 top-level native PRG/D64 images exactly.
The integrated main build has the same hashes. Paint is added to both suite
disks; Desktop, graphical Calculator and those disks change their bytes.
Both resident kernels, the diagnostic Calculator, Editor, Files, Ultimate,
Claude and the other existing program images retain their prior bytes.
The auditor extracts every packaged app and compares it with its PRG.

| App | PRG bytes | App pages | Other drawing allocations | Free managed pages |
|---|---:|---:|---|---:|
| Desktop | 6,612 | 26 | 36-page surface | 364 |
| Calculator | 9,917 | 39 | 2-page history, 36-page surface | 349 |
| Paint | 22,465 | 88 | Two 36-page documents, 36-page surface | 230 |

Paint opens through a separate 36-page staging document. Picker caches are
temporary. The image remains a full 320×200 hires picture; its VIC editing
viewport is 256×144. The VDC supplies text controls and status. An occupied
or unsupported graphics surface retains coordinate-based drawing and file
operations on both text consoles.

## Qualification

- 85 assembled CPU groups: document 13, file engine 14, Paint GUI 5, Ultimate
  picker/GUI 3, shared key filter 3, pointer 13, Desktop 27 and Calculator 7.
  These cover pixel/cell boundaries, connected lines in every octant,
  no-op undo preservation, viewport edges, all 16,384 pointer counter pairs,
  gestures/reconnection, fallback, file corruption and transfer failures,
  cancellation, exclusive creation, full 255-byte Ultimate paths, arithmetic,
  history and complete resource restoration.
- The filter suite executes 768 scan/key/button combinations in ROM and app
  mappings: 702 chain to the prior callback and 66 reject ambiguous input.
  Registers, flags, mapping, CIA columns, callback and table are checked.
- Actual VICE mouse and ROM keyboard workflows pass from both 40- and
  80-column boot configurations. Each opens and returns from all six apps,
  saves Calculator's exact `42` plus CR to `GUIHIST`, draws a two-color Paint
  document, undoes/redoes, saves and verifies `PAINTPIC`, rejects an existing
  destination, cancels another save, clears and reopens the saved picture
  through the shared picker. Every original disk file is preserved; the only
  additions are the exact history and 9,016-byte UPNT picture.
- The keyboard-only workflow covers the six apps, drawing without a mouse,
  unsaved-picture Keep/Discard controls, occupied-surface fallback, retained
  selection and recovery. The complete palette audit covers 87 frames,
  including 24 Paint frames: 5,568,000 independently reconstructed pixels.
  Full bitmap, document and VDC bytes are also compared.

624 CPU captures contain 2,112 chunks and 992,486 payload bytes; all 2,496
borrowed-state comparisons match. `audit.json` records the per-run totals.
Every qualified CPU capture retains and compares the complete borrowed state;
resident code and final recovery of all 426 pages and 32 handles are checked.
Capture admission waits for an idle point before the initial snapshot; it
never replaces a rejected readback. Both final mouse runs required zero
admission deferrals.

## Development evidence and limits

`preliminary.tar.gz` preserves the earlier runs and logs. The initial pointer
fixture moved over the newly added Paint card; its initial-selection assumption
was corrected using real keyboard Home input. Two runs stopped during initial
resident capture when pointer sampling changed readiness: the first rejected
a changed readback, and the next refused a busy initial state. Both are
preserved. Other runs exposed real mouse-button
transitions decoded as ordinary keys in Paint, and later Calculator. The
Paint-only fix passed its focused and 80-column workflows; moving that fix
into shared input produced the final images qualified here. Earlier passing
images remain preliminary evidence. The engine CPU runners retain the scope
labels from their initial document/file development; the separate final GUI
suites qualify the implemented interface. The original prototype PRGs were rebuilt during development
and are not claimed as frozen inputs. The first final pointer/desktop CPU
processes exited with status 143; fresh complete runs supply the qualification.

This is an initial APP-PAINT milestone. More tools/patterns, selection and
clipboard, zoom, multiple undo levels, image interchange, printing, graphical
VDC editing and window management remain open. Simultaneous typing while the
mouse button is held is not qualified. Software reproductions do not establish
the origin of earlier physical Down/Insert events. The bank-aware high-RAM
diagnostic blocker and native physical input/device qualification remain open.

## Audit

```sh
python3 -B verify.py
```

Lossless tar/gzip archives preserve 25,552 original payload files containing
78,988,705 bytes. Each member
has a size and SHA-256 in its corresponding `*-files.json`. The auditor accepts
only validated regular relative paths, checks captures and borrower bytes,
reconstructs complete palette frames, validates NAPP headers and disk contents,
and compares both rebuild reports. `SHA256SUMS` seals every record file.
A normal audit leaves the record unchanged; `--record` is refused after sealing.

CPU models, VICE video and physical hardware are separate evidence. This
checkpoint qualifies the first two. The older green installation remains
restored; the blue native interface is the intended common desktop as features
and applications continue to migrate.
