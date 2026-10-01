# Native keyboard scanning

Both native kernels validate the C128 ROM scanner's key index before it
publishes a character. Indices 0–87 reach the previously installed key-check
callback unchanged. Index 88 is the null sentinel; indices 88–255 are
rejected, with the ROM's normal scan-column cleanup.

The guard preserves A, X, Y and flags when chaining a valid callback. It
resides below `$4000`, where it remains visible when the ROM scans with
MMU configuration `$00`. Startup saves the existing callback under an
interrupt mask and does not chain the guard to itself on native restart.
The kernel owns this hook for its lifetime. It does not replace the ROM's
modifier, repeat, function-key or queue handling.

The foreground GETIN wrapper moves into spare service space. It retains
native input counting and readiness behavior, including the existing ROM
function-string GETIN behavior of clearing the interrupt-disable flag.
There is no new app ABI entry or heap reservation; capacity remains 426
pages. This resident guard did not change the app images, including Claude.

## Pointer clients

All seven graphical suite apps own the complete ROM function-key table while
their controls are active. They install ten one-byte function definitions and
a shared filter at `$1014` in the unused table tail. That code remains visible
during the ROM scan and chains the resident guard. It does not change an IRQ
vector, zero-page workspace or MMU mapping.

The filter rechecks every decoded key with interrupts masked. A row must be
high with all columns released and low with the candidate's column selected.
This rejects mouse/joystick signals and stale scan results. Accepted keys
chain with A/X/Y/P preserved; CIA columns are restored. The previous callback
and all 256 table bytes are restored together when the client closes. Editor,
Files and Paint retain key ownership while changing their views or dialogs.

The original C128 ROM enables interrupts before scanning. A nested scan can
clear the outer scan's extended-matrix flag, causing Control alone to decode
as keypad 5, minus or period. A VICE 16 KiB/D64 Copy run captured period at the
ROM queue store with index 82, modifiers 4 and CIA columns `$f7`. Explicitly
nesting the original ROM scanner reproduces that state and all three false
characters. The matrix check rejects them while retaining actual keypad keys.
The [clipboard qualification](validation/2026-09-14-native-shared-clipboard/README.md)
checks all 11 nested scan positions and all 88 key positions with plain,
Shift and Control input in both mappings for every graphical app. The CPU
fixture models the nested scanner, not the raster/IEC timing that triggers it.

The [Paint and shared-input qualification](validation/2026-09-13-native-paint/README.md)
covers 768 filter cases in both ROM and app mappings, Calculator and Paint
mouse workflows, keyboard controls and complete restoration. It does not
establish the source of the earlier physical Down/Insert events below.
Simultaneous typing while a button is held and physical mouse/adapter testing
remain open.

## Diagnostic state

Reserved kernel metadata now holds these internal fields. Apps must not
write them; they are not a new public keyboard API.

| Address | Meaning |
|---|---|
| `$3d1c..$3d1d` | Saved ROM/extension key-check callback |
| `$3d1e..$3d1f` | Rejected scan count, 16-bit little endian |

The rejection count resets at native startup and wraps after 65,535, like
`N_KEYS`. Rejected events do not increment `N_KEYS` or become `N_LASTKEY`.
The count is retained to make rejected activity observable. The strict
capture comparison still checks these bytes; no exception hides their changes.

## Evidence and limits

The [physical input trace](validation/2026-09-12-native-input-trace/README.md)
recorded two index-89 Insert events alongside four valid-index Down events.
The pinned [Commodore source](https://github.com/mist64/cbmsrc/blob/01bd60f162ef92212ef0cb67546ae8f42be34168/EDITOR_C128/ed7.src)
places the shifted table's first byte immediately after the normal table's
sentinel. A normal-table lookup at index 89 therefore reads `$94` (Insert).

CPU tests reproduce that ROM behavior with a modeled row signal. In VICE,
an emulated port-1 joystick Down produces Insert through the original
callback; the guard rejects the same input and records it. Real X keyboard
cursor events still navigate the desktop. These controlled reproductions
do not establish the physical machine's initiating signal. The guard accepts
valid Down index 7, so it does not resolve or conceal those physical events.

The [guard qualification](validation/2026-09-12-native-keyboard-guard/README.md)
also covers modifiers, keypad and function keys, queue/counter behavior,
both memory mappings, callback preservation, complete resident/display
comparisons and the five-app workflow with two Claude serial lifetimes.
This is software qualification. Native physical serial operation and an
authenticated Claude session remain unverified.

```sh
python3 -B tests/ci_native_keyboard.py --report /tmp/kestrel-keyboard.json
python3 -u tests/ci_native_keyboard_iec.py
python3 -u tests/ci_native_suite_iec.py
```

The CPU check requires py65. The emulator checks require VICE and Xvfb;
the suite check also requires the bridge dependency. They use disposable
emulators and make no physical cartridge connection or model request.
