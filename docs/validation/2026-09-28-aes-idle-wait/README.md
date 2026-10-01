# AES input wait: no AES call while nothing can change — 2026-09-28

## Problem

The idle wait added in `55ebe4b` sampled the AES on every jiffy tick when an
app asked for `MU_BUTTON` or `MU_TIMER`, and on every completed 1351 read.
Under VICE both suites that run the AES failed on the committed build, and
both pass on `ef57914`:
- `ci_native_aes_vice.py` failed at the menu stage: the key `M` was consumed,
  but `N_READY` was never seen ([report](aes-vice-before.json)).
- `ci_native_gemdesk_vice.py` failed at boot ([report](gemdesk-vice-before.json)).

Measured in VICE with `N_READY`, jiffy and program-counter samples:
- The wait returned on every tick, and GEMDESK never idled: `N_READY` was 0
  in 100/100 samples, and no program counter fell in the wait.
- The pointer had not moved, no rows were dirty and nothing was pending.
- VICE's monitor pauses land at a fixed point of the frame (49 of 80 PC
  samples fell in two tiny copy loops). A loop that works once per tick
  stays in phase with it.

On the C128, DMA sampling is not in phase: the same build measured 98/300
there.

## Change (`src/native/aes-client.inc`)

The wait keeps `N_READY` published and makes no AES call until something can
change the result:
- a key, or a keyboard click still counting;
- a 1351 read that moved the pointer or changed the button (`AE_POINTER` 1),
  or changed `ae_pointer_*` (`AE_POINTER` 0);
- a jiffy tick, only while `MU_TIMER` is requested or within 48 ticks after a
  press (the AES's longest double-click window is 40), so clicks can still
  be counted and reported.

An idle GEMDESK makes no AES calls. The code fits in the slack before
GEMDESK's page-aligned table; GDDLG and GDSET are unchanged in size.

`N_READY` is published for the whole wait and cleared only when the wait
returns for a sample. `N_KEYIN` still clears it for a consumed key, and
`pm_poll` clears it while it reads the port.

A first version cleared `N_READY` right after `N_KEYIN`. Idle passes then spent
most of their time unpublished. On the C128 the held probe needed 400–500 busy
retries per VDC capture with it (20–60 with the tick-sampling build), and a
`--mirror` run with that build passed three checks before my one-hour timeout
killed it ([partial report](hw-mirror-partial-ready.json); the machine was
restored by hand: drive A 1541 and empty, upload deleted, reset).

## Evidence

Build: `gemdesk.prg` `9f760745f394…`, `gem.d81` `06bfe2f8…`. Every other app is
byte-identical to `7564321`.

| Suite | Result |
|---|---|
| `ci_native_aes.py` (timers, double clicks, pointer events, menus, windows) | 31/31 ([report](aes.json)) |
| `ci_native_gemdesk.py` (including the 80-column mirror) | 45/45 ([report](gemdesk.json)) |
| `ci_native_aes_vice.py` | 5/5 ([report](aes-vice.json)) |
| `ci_native_gemdesk_vice.py` | 8/8 ([report](gemdesk-vice.json)) |
| C128, keyboard workflow | 7/7: boot, listing, Calculator and back, the Editor graphical with the 80-column mirror live and an exact surface, back, Paint ([report](hw-keyboard.json)) |
| C128, `--mirror` | 6/6, colours included: desktop, drive window, open menu, closed menu, alert, closed alert. 0 probe busy retries at every capture ([report](hw-mirror.json)) |

On the C128 both runs restored drive A, deleted the upload and reset.

## Earlier: the 80-column mirror on the C128 with the committed GEMDESK `72578322`

`hw_native_gem_check.py --mirror` with the committed image (`gem.d81`
`4743563d…`) passed all six checks, colours included
([report](hw-mirror-committed-gemdesk.json)): desktop, drive window, open
menu, closed menu, alert, closed alert.

The held probe now does what `vd_read_seek` does before reading VDC memory:
address, one read, address again. The two reads per attempt still disagreed
in some attempts, so read glitches remain. Every check passed on an attempt
whose read matched exactly: "menu closed" took 4 attempts; "alert" and
"alert closed" took 2 each. The stale attribute cells seen in the two
earlier runs did not appear.

## Limits

- The intermediate GEMDESK `1a4251c5…` passed the keyboard workflow on the
  C128 (7/7) but was superseded before a complete mirror run.
- The held capture still reads some chunks one address late: 3 of 7 double
  reads disagreed in the final run. The cause is not known, and retries absorb
  it.
