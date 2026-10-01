# Files graphical VDC qualification

Files now presents its file list, byte viewer, editable paths, copy/verification
dialog and destination picker on both displays. The VIC surface is 320×200;
the shared VDC presenter doubles pixels horizontally to 640×200. A 64 KiB VDC
uses color and yellow focus. A 16 KiB VDC uses white graphics on blue with
reversed focus. Mouse and keyboard actions use the same application state.

This is a software checkpoint for the intended blue native desktop. The older
green desktop and the native diagnostic workspace remain separate paths.
Claude remains included in the suite. Editor and Claude VDC migration and
the broader completion roadmap remain open. No physical C128, Ultimate HTTP
endpoint, serial bridge or external account was accessed by these checks.

## Parent and implementation

The parent is signed commit `c9ed6c581570071c6ef33ab065314ddbf73fe4ed`.
Its Paint VDC record has seal
`cfe221b2212e99b9017fd36299e9a35403c553ef9c7f8517ad63228edc896cae`.
All earlier sealed records and the four pre-existing untracked files were
preserved. This checkpoint requires native ABI 1.12 without changing the
resident kernel, the VDC provider or the 426-page managed heap.

Files keeps its 96-page bank-0 app allocation. Its expanded core is 13,998 PRG
bytes, stored in 9,829 packed bytes. Graphics and picker modules alternate at
`$96ac`. The picker ends at `$be99`, leaving 359 bytes before `$c000`; the
graphics module ends at `$b3bd`. Both modules carry their own CRC and the
packed parent app's checked identity.

Sixteen explicitly reserved bank-0 pages at `$5000..$5fff` hold scratch storage:

| Range | Contents |
|---|---|
| `$5000..$57ff` | GUI current/previous text body, or the inactive picker's records and retained paths |
| `$5800..$5bff` | Copy/verification transfer buffer and picker scratch |
| `$5c00..$5cff` | Original function-key definitions |
| `$5d00..$5dff` | Complete raw source name |
| `$5e00..$5e7f` | Byte-viewer data |
| `$5e80..$5ebf` | Graphics text buffer |
| `$5ec0..$5fff` | Spare |

All pages are zeroed before keyboard or display ownership. A conflicting owner
refuses startup and retains its bytes, handle, pre-existing stream and input
state. Editable fields stay inside the checked app allocation. The usual
37-page IEC cache, 36-page VIC surface and 30-page bank-1 VDC component remain
separate. Files leaves 211 managed pages with REU screen backing, 147 with
16 KiB VDC RAM backing, or 139 with 64 KiB VDC RAM backing, before additional
directory caches. App cleanup returns all 426 pages.

One VDC provider and original-screen backup survive graphics/picker module
replacement. Pointer coordinates are copied from the active module into
retained core state. Rows and pointer pixels update incrementally. Failed
display restoration pauses file actions, preserving the exact copy/verify
position, open streams, destination bytes and stack. Escape restores before
normal cancellation or app replacement; R reacquires graphics after fallback.
Picker input is guarded both before and after redraws. A module error survives
VDC cleanup instead of being mistaken for Cancel. Replacement arguments are
prepared only after display cleanup can succeed.

## Frozen checks and captured results

The record retains 713 hashed inputs and twenty selected terminal jobs. The
CPU checks cover both VDC sizes, complete independent VIC/VDC images, byte
viewing, 255-byte fields, mouse and Tab controls, copy/verification cancellation,
cross-backend paths, exclusive creation, missing/corrupt components, picker
surface refusal, workspace conflicts, and exact display/input/owner cleanup.
REU cases cover 128 KiB and 16 MiB backing, retained snapshots across picker
swaps, failed snapshot reads and failed capacity-probe restoration. Normal
copy regressions include complete 66,058-byte files and reopened mismatch
detection. Packed startup checks retain their interrupt coverage.

The independent rebuild reproduces all 34 native PRG and disk artifacts.
Only Files, its two modules and the four suite/workspace disk images change
from the parent. The other six packed apps, kernels, Editor modules and VDC
provider retain their exact program bytes. Every file chain, allocation bit
and shipped payload is checked on six disks, including a fully allocated D81
and three deliberately corrupted images. The suite has 140 free D64 blocks
and 2,636 free D81 blocks before user documents.

The private D64/1541 workflow starts in 40-column mode with a 64 KiB VDC. The
D81/1581 workflow starts in 40-column mode with a 16 KiB VDC and 16 MiB REU.
Each launches Files with the mouse, pages and selects directory entries,
edits a destination, cancels one picker, chooses another drive through the
picker, copies `EDFIND.PRG` to `FSCOPY`, reopens and verifies it, and returns to
the blue desktop. Independent disk decoding compares both complete copied
PRGs and every pre-existing system file. Full VIC and VDC palette canvases
include both actual pointers. Every VDC snapshot is compared at the executing
restore checkpoint, with register-catalog evidence of the CPU PC and MMU.
App and desktop restores use distinct evidence labels.

Six additional cold boots cover direct suite, standalone diagnostic and
workspace-with-suite disks on D64 and D81, including input and launcher return.
The offline audit independently rechecks archive hashes, native headers and
CRCs, packed payloads, module binding, file chains/BAMs, copied files, captured
palette pixels, VDC restore bytes and complete REU snapshots. See `audit.json`
for the measured counts and `jobs.json` for every command and result.

The measured total is 95 CPU/boot cases, 102 complete palette canvases and
9,792,000 independently compared pixels. Four VDC restoration checkpoints
match exactly, including 33,554,432 bytes decoded from the two complete REU
snapshots. Both copied PRGs contain all 11,359 bytes. The twenty passing jobs
exclude the two failed initial checks and four interrupted test attempts.

## Observer and oracle corrections

An initial copy-regression check still expected the pre-graphical picker's
text help. Its expectation now uses the shared picker oracle on both text
widths; the default 80-column oracle behavior is unchanged. The shared picker
still displays graphical Tab-focus help when bitmap controls are unavailable;
its existing text shortcuts remain functional. Selecting fallback help for
the active presentation is recorded as a remaining roadmap item.

An initial D64 Files-load observation stopped while a native transfer exposed
bank 1 and checked the kernel signature through the temporary CPU mapping.
The pointer workflow now identifies the signature in physical bank 0 for
read-only pause batches. The native capture's separate CPU-mapping, idle,
ownership and borrowed-byte checks remain required before injecting a capture.
The monitor records the bank and observed signature. Actual restoration
checkpoints retain the guarded PC/MMU observation used by the parent record.
Monitor memory banks and register responses follow the
[VICE binary monitor contract](https://vice-emu.sourceforge.io/vice_13.html).

The final input set differs from the first frozen set only in the two test/
observer files, their two shared helpers and a roadmap note. `input-generations`
metadata, both manifests, previous source text and their complete diff are in
`jobs.tar.gz`. Copy, rebuild and both Files VICE workflows run against the
final inputs; sixteen other passing jobs retain their original frozen inputs.
Failed original copy and D64 observer logs are retained separately and are
not counted as passing jobs. No frozen input directory was edited.

Two CPU job managers later terminated with exit code 143. Their test processes
were confirmed absent before resuming interrupted or unstarted checks as
individual supervised commands against the same immutable input directories.
Completed jobs were retained. The original interrupted status/log files and
manager observations remain archived; replacement controller summaries record
the termination explicitly. The cause of the host termination is unknown.

## Reproduction and limits

Run `python3 verify.py` in this directory to verify the sealed record using
only the standard library. `SHA256SUMS` covers every record file; the verifier
also checks each archive member against its manifest. Native CPU checks use
the recorded py65 environment; VICE checks need the recorded tools and a C128
KERNAL ROM whose hash is retained without redistributing that ROM. The current
VICE launcher depends on the local `cbm` helper under
`<home>/.claude/skills/commodore-basic/bin/`; replacing that environment
dependency remains portability work.

These results are CPU-model and private-emulator evidence. The physical boot
image was not updated. Display timing, authentic Ultimate/serial hardware,
Editor/Claude display migration, document backing, app scheduling and the
remaining OS and expansion roadmap still need implementation or qualification.
