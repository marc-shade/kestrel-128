# Native keyboard guard — 2026-09-12

Both native kernels reject ROM keyboard scan indices outside the C128's
88-key matrix. Valid callbacks retain their registers and flags; normal
function-key, modifier, repeat and GETIN behavior remains in the ROM.
Rejected activity increments a separate kernel counter. No app ABI entry,
app image or heap reservation changes. The suite remains at ABI 1.10 with
426 managed pages.

This is software qualification. No physical run or Claude model request was
made. The earlier physical diagnostic recorded both index-89 Insert and
valid-index Down events; the physical input signal's source remains unknown.
The guard passes valid Down events. The high-memory host-read limitation in
that diagnostic also remains open.

## Implementation and inputs

The change follows signed commit `2eba45b3cb5fd6cfe93639759aec0c6a0795f9f3`.
`inputs/` freezes 391 main-checkout files, with hashes in
`frozen-inputs.json`. The private software candidate and main rebuild produce
the same 19 PRG/disk images. All app PRGs are unchanged from the base.

The callback at `$353d` stays below BASIC ROM. It rejects indices 88–255,
increments the 16-bit counter at `$3d1e` under an interrupt mask, and restores
the ROM scan column. Valid indices chain to the saved callback at `$3d1c`.
Startup installs the hook atomically, resets the count, and handles repeated
native startup without chaining to itself. The counter wraps like `N_KEYS`.
The strict capture still compares these bytes; rejected activity is not
exempted from state comparisons.

The unchanged GETIN wrapper moves into the spare service interval after
Ultimate queries. The new layout records and checks the callback and service
boundaries. The maximum main-code address remains below `$3800`; the service
stays below `$4bfc`. No extra RAM page is reserved.

| Image | SHA-256 |
|---|---|
| Desktop kernel | `78232acf4269a8ac435e12445a9b735146ed98373b41d0e5a5ce719fa0bc6fd1` |
| Desktop suite disk | `fbe9ef13380edc94cc0ffc8c2137f555df8c87f11e5ff80e3b749cd8ffd16531` |
| Workspace kernel | `5e088ca4ead945a60d56b875ec0acf9be97f437c7ab533c2d22156b0bade9db3` |

## CPU checks

`keyboard-cpu-qualified.json` retains ten groups across both kernels. They
execute the local C128 ROM scanner, with BASIC ROM visible under MMU `$00`,
and model keyboard columns plus an external row signal. A low row produces
index 89 and Insert through the original ROM callback; the guard rejects it.
Releasing the signal and typing an ordinary Down still works.

Sixty real-ROM cases cover letters, Shift/Control, dedicated cursors, keypad,
Tab, Escape, Help and function keys across both kernels and mappings.
Another 4,096 callback cases cover every index and four flag combinations.
Further checks cover callback preservation, repeat timing, queued function
text, both counters' carry/wrap behavior and restart. The limited CIA model
is not proof of a physical signal source.

The retained regressions pass four startup cases, eleven Claude lifecycle
cases, nine relocation/IRQ/staging cases, 48 capture/restore cases, seven
running-layout controls and 24 desktop cases. `main-rebuild.json` records
the exact 19-image main/private comparison.

## VICE controls

`vice-keyboard/` retains the final keyboard/joystick test. A private X display
receives actual synthetic keyboard events. Keyset 1 maps host `j` to an
emulated port-1 joystick Down; the disposable emulator has an explicit
joystick attached to that port. The fixture temporarily disables key repeat
for single presses under warp, then restores the original setting.

| Event | Guard | Consumed keys | Rejected scans | Last consumed key |
|---|---|---|---|---|
| Keyboard Down | Enabled | 0 → 1 | 0 | Down |
| Keyboard Up | Enabled | 1 → 2 | 0 | Up |
| Joystick Down | Enabled | 2 | 0 → 1 | Up |
| Joystick Down | Original ROM callback | 2 → 3 | 1 | Insert |
| Joystick Down | Reinstalled | 3 | 1 → 2 | Insert |
| Keyboard Down | Enabled | 3 → 4 | 2 | Down |

This negative control reproduces the unwanted Insert and distinguishes it
from normal keyboard navigation. It does not establish which devices were
connected to the physical C128 or why its valid-index Down events occurred.
All resident bytes, the complete VIC bitmap and the VDC desktop screen match
after the controls. The record contains 15 captures, 52 chunks and 24,774
payload bytes, with 60 matching borrower pairs.

`vice-suite/` retains the full shared workflow: Calculator, Editor, Files,
Ultimate and two Claude serial lifetimes, including acknowledged F8 and host
exit. Font/NMI state restores, receive counters report no overruns or drops,
and the final workspace has all 426 pages free. Its 135 captures contain
403 chunks and 183,389 payload bytes, with 540 matching borrower pairs.
Every bridge and emulator process finished. The host PTY runs the fixed
fixture, without authenticating to Claude or making a model request.

`preliminary/` retains three terminal fixture/environment failures: a numpad
mapping that did not produce the requested joystick event; an incorrectly
typed resource-set request rejected before boot; and a bridge started with
a Python environment missing pyte. They are not passing device controls.
The final joystick fixture uses an integer resource value and explicit
keyset, and the full suite uses the installed bridge dependency. Runtime
images were unchanged across these emulator attempts.

## Offline audit

```sh
python3 -B docs/validation/2026-09-12-native-keyboard-guard/verify.py
```

The offline audit verifies the seal and frozen inputs, exact images and
boundaries, CPU reports, raw capture chunks and borrower pairs, both VICE
resident comparisons, complete desktop surfaces, keyboard control counts,
serial/font/NMI outcomes and final heap recovery. It performs no network,
hardware operation or emulator run.
