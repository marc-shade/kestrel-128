# Paint graphical VDC qualification

Paint now presents its picture viewport, tools, palette, status, Save As,
dirty-picture confirmation and shared file picker on both displays. The VDC
mirrors the 256×144 viewport into the full 320×200 document, with horizontal
doubling at 640×200. A 64 KiB VDC uses color and yellow focus; 16 KiB uses
contrasting monochrome controls. The keyboard brush is visible before the first
mouse movement. Drawing, connected strokes, panning, undo and verified UPNT
file operations retain their existing behavior.

This record follows signed commit
`93d306f827acc7e47695bf41760c294fd18f88e4`, whose Ultimate VDC record has seal
`e7ec10d892da6c0f4b9165ce325655cca0518d1aa4d23eb0fce72defd52085e6`.

## Memory and recovery

Paint retains a 96-page bank-0 executable, 72 pages for the document and undo,
its 36-page VIC surface, and the unchanged 30-page bank-1 VDC provider. Ten
separately owned bank-0 pages at `$5000..$59ff` hold picker, comparison, keyboard
and text scratch. Reservation and zeroing happen before document initialization
or keyboard ownership. Conflicting ownership produces a clean startup failure;
adjacent allocations remain intact. Editable field descriptors and buffers stay
inside the loader's original app handle, as required by the current field API.
Normal app exit frees every owned page and handle.

The three Paint scenes share rectangle and text interpreters to recover code
space. The raw PRG is 24,442 bytes; the packed PRG is 16,730 bytes. There are
88 bytes before the packed-startup cleanup tail. The provider, six other apps,
four app-bound modules and all resident/packed-kernel boot artifacts retain
their exact parent bytes. Only Paint and four suite/workspace disks change
among the 34 native PRG/D64/D81 artifacts. All 34 reproduce in a separate build;
an independently assembled, CRC-sealed raw Paint program exactly matches the
expanded packed program.

REU screen backing leaves 182 main-RAM pages free outside transient file-open
staging and picker caches. RAM screen backing leaves 118 with a 16 KiB VDC or
110 with 64 KiB. This does not move Paint's document or undo into REU memory.
The complete D64 suite retains 134 free blocks; D81 retains 2,630. Seven packed
apps save 35,098 bytes and 139 disk blocks against their current raw programs.
Packing trades startup CPU work for disk space; no hardware speed claim is made.

One VDC provider and original-screen backup survive drawing, dialogs and picker
handoffs. A stalled display blocks drawing and file actions until Escape can
restore the screen. Successful recovery then follows the normal dirty-picture
confirmation, allowing the user to keep unsaved artwork. Repeated failed Escape
attempts retain the document, undo, stack and resource ownership. Refresh (`R`)
can reacquire graphics after fallback. A failed picker surface restores the VDC
before ROM text appears. Missing hardware or an absent/corrupt provider leaves
VIC drawing and usable text controls.

## Software evidence

Seventeen selected jobs have observed terminal zero exit codes and unchanged
input hashes. They cover both VDC sizes, complete graphical panels
and picker canvases, pointer-only and field updates, full-document drawing and
connected strokes, panning across 255/256 and the bottom/right edges, undo,
verified open/save, main-RAM and REU backing, failed display/probe restoration,
component fallback, scratch ownership conflicts, existing document/file/GUI/key
and Ultimate workflows, packed startup, six media images, an exact rebuild,
two VICE workflows and six cold boots.

The selected jobs use two frozen sets, each containing 704 input files. Their
only changed file is the VICE harness. A distinct `paint-app-close` label prevents
app-exit captures from overwriting desktop-exit captures. The keypress observer
also captures restoration before polling the key counter, since that polling
resumes the CPU and could run past the checkpoint. It keeps the CPU stopped
until the host key is released. Both desktop and app observations now require
the actual CPU program counter and MMU bank at the restoration entry; a previous
hit count alone is insufficient. Raw register catalogs and values are retained.

Both affected VICE workflows were rerun after these corrections. The other
fifteen jobs retain their original results; every production, build and other
test input is identical. Both input manifests, the original harness and exact
diff are archived. The audit requires that this harness is the sole changed
input and verifies the captured PC and bank. Superseded VICE status, logs and
the intermediate failed checkpoint report are retained but do not count toward
the selected results. The monitor response format follows the
[VICE binary monitor documentation](https://vice-emu.sourceforge.io/vice_13.html).

Independent CPU oracles compare complete Paint and picker VIC surfaces and VDC
bitmaps/attributes. Picker field edits require fewer than 6,000 VDC writes;
pointer motion requires no more than 96. The provider and snapshot tokens are
retained across file dialogs, with complete document/undo and preference checks.
REU tests include 128 KiB and 16 MiB expansions, exact preservation outside the
screen allocation, failed snapshot reads and failed capacity-probe restoration.
Owned-bus tests reject writes into another allocation during Paint startup.

The private D64/1541 workflow starts in 40-column mode with a 64 KiB VDC. The
private D81/1581 workflow starts in 40-column mode with a 16 KiB VDC and 16 MiB
REU. Real host mouse and ROM keyboard input exercise drawing, palette selection,
undo/redo, Save As, duplicate-name rejection, cancellation, dirty Open, the
shared picker, complete reload and return to the graphical desktop. D64 saves
to a private device-9 data disk; D81 saves to its private suite image. Every
shipped file is preserved and the exact expected UPNT file is the only addition.
VICE does not emulate the cartridge UCI target here; CPU device models cover
that transport. Six generated images also cold-boot through their entry paths.

The standalone audit independently reconstructs the two drawn document pixels,
compares every captured document byte and visible viewport cell, encodes both
saved UPNT files, decodes packed programs, parses disk chains/BAMs, and checks
complete palette canvases and VDC mirror pixels. It verifies exact screen and
register backups, all REU snapshot bytes, observer scratch restoration and final
heap cleanup. Full UI text and layout are additionally checked by the archived
runtime oracles. Exact case, image, canvas and restoration counts are in
`audit.json`.

## Reproduction and limits

`inputs.tar.gz` holds frozen source, test, build and target files. The jobs
archive retains exact commands, reports, terminal status and logs, including
the separately assembled expanded program. `outputs.tar.gz` holds private
emulator disks, raw surfaces, palette canvases, observation guards and snapshots.
Parent and rebuilt images have separate archives. Every archive has an exact
per-file manifest; `SHA256SUMS` seals the complete record.

Run the standalone audit using standard Python without an emulator:

```sh
python3 -B verify.py
```

Runtime reproduction requires the documented 64tass/cc65, VICE and Py65 tools.
The jobs retain their actual Python paths. Allocate each emulator's private X
display before starting another. The VICE harness still uses the developer-local
CBM helper; the required KERNAL ROM is identified by hash and not redistributed.

No physical hardware I/O, deployment or push was performed. The hardware boot
image has not been updated by this milestone. Editor, Files and Claude VDC
migration, native 640-column widgets, document backing, scheduling, general
memory placement, remaining Paint tools and formats, hardware qualification and
the rest of the completion roadmap remain open. Keep this sealed record
immutable.
