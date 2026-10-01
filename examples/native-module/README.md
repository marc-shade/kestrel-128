# Native module SDK example

This small application demonstrates the [ABI 1.7 module contract](../../docs/NATIVE-MODULES.md):
one app core keeps its state while a checked module runs inside the app's
existing allocation. It uses the public jump table and both native KERNAL
consoles. The system images are built separately; ABI 1.7 hardware qualification
is still in progress.

From the repository root, with Python 3 and `64tass` installed:

```sh
python3 examples/native-module/build.py /tmp/kestrel-module-example
```

The build emits `MODULEDEMO.PRG`, `COUNTER.PRG`, listings, symbols and a JSON
record of the validated manifests and SHA-256 hashes. It seals the parent
first, binds the module to that parent CRC, then seals the module. Changing
the parent requires rebuilding and installing both files. CRC detects damaged
or mismatched images; it does not authenticate executable code.

Install the two PRGs together on a test IEC disk or in the same Ultimate
folder, and launch `MODULEDEMO.PRG` from the native browser. The example
does not upload, mount or alter any media by itself. The files are PRGs,
including their two-byte load addresses.

| Key | Action |
|---|---|
| Return | Call the loaded module; display its next 8-bit counter value in hexadecimal. |
| R | Explicitly close/check any retained module source, reload `COUNTER.PRG` and reset its counter. |
| Esc | Exit through `N_EXIT`; the browser launcher returns to the browser. |

The initial load is attempted once. After an error, Return performs no file
I/O; R requests another checked attempt. The parent retains all three token
bytes in its core and restores them to `N_MTOKEN` before each call. A warm
call performs no module load. The module returns its value in A and sets
carry when the counter wraps from `$ff` to `$00`. The parent reads
`N_MERROR` separately: a module's carry result is not a gate failure.

`layout.inc` assigns the four-page parent allocation to `$6000..$63ff`.
The core is below `$6300`; the module window is `$6300..$63ff`. Both assembly
files reject overlap at build time, and the host sealers validate the extents.
The kernel also checks the owner, allocation, caller, file, parent binding and
token before module execution. Fixed addresses belong to this example's own
layout, not a general module linker.

The module owns no extra heap blocks or open files. A module that acquires
such resources must release them before replacement. `N_MCLOSE` handles only
its loader source. An uncertain IEC CLOSE remains quarantined under the
current backend contract, so repeated R cannot establish IEC recovery. See
the [remaining recovery work](../../docs/NATIVE-MODULES.md#failed-close-and-remaining-recovery-work).

Run the example's CPU workflows using an interpreter with `py65` installed
and the repository's C128 ROM fixtures:

```sh
python3 tests/ci_native_sdk_module.py --report /tmp/kestrel-module-example-report.json
```

These checks execute the assembled app, module and kernel with modeled
KERNAL file operations and Ultimate registers. They cover three IEC formats,
both DOS contexts, complete 40/80-column screens, counter wrap, cold reload,
original-source lookup, missing/short/corrupt/mismatched modules, stale tokens,
explicit Ultimate CLOSE recovery and final ownership cleanup. They do not
establish emulator timing or physical cartridge behavior.
