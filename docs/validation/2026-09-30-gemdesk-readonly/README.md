# GEMDESK Show Info: Read-only on IEC files; printing in its own module — 2026-09-30

## Change

GEMDESK ([GEM-DESKTOP](../../GEM-DESKTOP.md)):

- **Read-only in Show Info** can now be ticked or cleared on IEC files. CBM
  DOS has no lock command, so the lock bit (bit 6 of the entry's type byte)
  is changed where the drive keeps it: the directory chain (18/1 on a D64
  or D71, 40/3 on a D81) is read through a `#` buffer channel (`U1`) until a
  closed file has the name, that sector is written back (`B-P 0`, its 256
  bytes, `U2`) with the bit set or clear, and read again (`U1`) to prove it;
  then the drive is listed again. A refusal (a write-protected disk answers
  26) is shown with the drive's status line and changes nothing. With a
  name change in the same dialog, the file is renamed first and the lock is
  set by the new name; a failed rename withdraws the lock.
- **Module layout**: a module cannot load another, so Show Info (GDDLG)
  leaves the request in the core (`gm_lock_want`, `gm_lock_name`), and the
  core runs the lock in GDDSK afterwards. To make room, printing and Print
  Screen moved from GDDSK into a new module, `GDPRT.PRG`; GDDSK's buffer
  channel routines are shared through `src/native/gemdesk-sector.inc`. The
  core now ends at `$b1e2`, and the largest module (GDFMT) leaves it 188
  bytes to grow (75 before).

## Tests changed

- The drive model (`tests/ci_native_files.py`) now lets a written directory
  sector set or clear its files' locks, as the drive's listing then shows
  them (`StreamIEC.directory_written`).
- Two fixtures had one row too many for their window once `GDPRT.PRG` was on
  the disk (a row below the window cannot be clicked): the Delete fixture
  drops `GDPRT.PRG` and the print fixture drops `GDDSK.PRG`, which printing
  no longer needs. The print VICE test reads the band counter from GDPRT's
  listing.

## Evidence

The suites ran in a scratch copy whose images and tests are byte-identical to
this commit's ([build hashes](build-hashes.json): only the GEMDESK core, its
modules and `gem.d81` changed).

- **GEMDESK CPU set** (`tests/sweep_native.py --group cpu --only …`): 12/12
  over two runs. [Run 1](cpu-summary-run1.json): 10/12; the desktop suite
  failed because the new lock case left KEEP locked for the Trash case after
  it, and the print suite because its listing had one row too many (both
  test fixes, above). [Rerun](cpu-summary-rerun.json) of those two after
  the fixes: 2/2 ([desktop report](ci_native_gemdesk.json): Show Info
  unlocks LOCKED with exactly `U1:2 0 18 1`, `B-P:2 0`, `U2:2 0 18 1`,
  `U1:2 0 18 1`, the drive then deletes it; KEEP is locked the same way; a
  write-protected disk shows `26,WRITE PROTECT ON,18,01` and keeps the lock).
- **VICE**: 9/9 over two runs. [Run 1](vice-summary-run1.json): 8/9; the
  print test looked up its band counter in GDDSK's listing, now GDPRT's
  (fixed); [rerun](vice-summary-print-rerun.json): 1/1. The new
  [read-only test](ci_native_gemdesk_lock_vice.json): x128 with true-drive
  1581s; Show Info from the keyboard (Tab, Space, Return) ticks Read-only on
  NOTES in drive 9; Show Info reads it back ticked; after the emulator
  exits the D81's entry reads `$C1` (the other file unchanged, `$82`) and
  c1541 lists `seq<`.
- **Mutation check**: a build whose lock code keeps the bit (`and #$ff` for
  `and #$bf`) fails the unlock case on the sector byte.

## Not verified

- The full CPU sweep has not run on this commit, only the GEMDESK set. The
  shared drive model (`tests/ci_native_files.py`) changed only on its `U2`
  path, which only GEMDESK's disk copy and lock send.

- Nothing has run on the physical C128 or a real 1541/1571/1581. VICE's
  true-drive 1581 covers the D81 directory (40/3); the D64/D71 chain (18/1)
  ran only in the CPU model's DOS.
- A file whose entry is in a later directory sector is found by following
  the chain; the tests' files are all in the first sector.
- Two files with the same name: the first closed one in the directory is
  changed (as the DOS itself finds the first).
