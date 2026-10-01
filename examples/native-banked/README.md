# Native banked REU example

This example builds a native bank-0 app and a separately loaded bank-1 REU
provider. It needs the native ABI 1.12 kernel and an available REU for its
512-byte write/read demonstration. An absent REU produces an error and still
allows a clean exit. It does not modify the shipped suite media.

From the repository root, with Python 3 and 64tass installed:

```sh
python3 examples/native-banked/build.py /tmp/kestrel-banked-demo
python3 native_image.py /tmp/kestrel-banked-demo/BANKDEMO.PRG
python3 native_banked.py /tmp/kestrel-banked-demo/BKREU.PRG
```

Place both PRGs in the same native app source directory or on the same IEC
disk, and launch `BANKDEMO.PRG` through the native app browser. The provider
is not itself a launchable desktop app. The parent uses its original source
location for loading, including an Ultimate absolute path. Return runs the
write/read test; Escape releases the REU arena, closes the provider and exits.
The two consoles show the test count and last native error in hexadecimal.
Error `$15` on startup includes an absent or already-owned REU.

The REU is used as volatile scratch storage under the native arena's ownership
contract. The test leaves its 512-byte pattern in its released allocation.
It preserves bytes outside that allocation and restores its capacity-probe
bytes. A failed restoration retains the context; Escape explicitly retries
cleanup before exit.

`parent.asm` contains only the UI and the bank-0 loader/executor. `provider.asm`
contains the one retained REU arena and its banked callback helper. See the
[banked execution contract](../../docs/NATIVE-BANKED.md) and
[REU API](../../docs/NATIVE-REU.md) before reusing these components.

The example provider uses this small command interface through `bk_call`:

| A | Operation |
|---|---|
| 0–8 | REU open, close, allocate, reserve, free, read, write, stats, release |
| 9 | Copy an 18-byte request from `N_BUFFER` into the provider's retained arguments |
| 10 | Return the arguments and status in the first 29 bytes of `N_BUFFER` |
| 11 | Demonstrate `bk_native`; `N_BUFFER[0]` selects the native service index |

The request is owner (1 byte), pages (LE16), start page (LE16), token (8 bytes),
offset (LE24), and count (LE16). Status returns those 18 bytes, then actual
(LE16), error, total pages (LE16), available pages (LE16), slots, active, busy,
and retained probe state. Read/write payloads occupy the full `N_BUFFER`;
set the retained arguments with operation 9 first. Operation 10 overwrites
the payload, so consume read data before requesting status.

Reproduce the software checks with py65 installed for the CPU tests and
VICE, c1541 and Xvfb for the emulator test:

```sh
python3 tests/ci_native_banked.py --report /tmp/banked-cpu.json
python3 tests/ci_native_banked_sdk.py --report /tmp/banked-sdk.json
python3 tests/ci_native_banked_vice.py --report /tmp/banked-vice.json
```

The tests use private emulator disks and output directories. The existing
VICE harness still has a developer-local CBM helper dependency; removing
that dependency remains SDK portability work.
