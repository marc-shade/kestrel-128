# Native applications and checked loading

The native workspace loads separate applications through owned IEC or
Ultimate streams, with the same manifest and checksum checks for both.
Press **C** for the calculator or **B** for the [file/app browser](NATIVE-BROWSER.md).
In the browser, **L** opens an absolute USB app path field.
**F** also selects ULT directory navigation; **Enter** opens the selected folder
or launches the selected native app through the checked loader.
Applications run in native C128 mode, use the kernel's owned RAM services and
return with the workspace's existing allocations intact.
The [blue native desktop](NATIVE-GRAPHICS.md) launches the current seven-app
suite. Further Ultimate/productivity apps remain on the roadmap. This lifecycle supports one foreground application; scheduling and
preserving suspended applications remain open.

ABI 1.14 adds [document launch from Files](NATIVE-DOCUMENT-LAUNCH.md): the
checked system Editor or Paint receives the selected file's exact identity,
then returns to that selection in Files. The request expires after one launch.

## Calculator

The native calculator accepts unsigned integers 0..65535 and the four basic
operations. **Enter** or **=** evaluates, **Del** removes the last entry digit,
**C** clears the current calculation and **Esc** returns to its launcher.
Operations execute in entry order: `5+6*7=` gives `77`. Multiplication/addition
overflow and subtraction below zero show `OVF`; division by zero shows `DIV/0`.
Clear the calculation to continue after an arithmetic error. Esc and history
navigation and saving remain available while an error is displayed.

The last 32 evaluated results are retained in a 512-byte allocation in RAM
bank 1. Eight are visible at once, newest first; **N/B** moves to older/newer
results. Clear keeps the history. Returning from the application releases both
its code allocation and history; reopening starts a new session. Both complete
40- and 80-column screens present the same controls and values. **S** prompts
for a new SEQ filename on the application's source device and disk format.
It exports history oldest first, closes, reopens and verifies every byte.
Existing names are rejected;
Esc cancels the prompt. The [shared field keys](NATIVE-FIELDS.md) provide
caret movement, insertion and forward deletion. See the [native file guide](NATIVE-FILES.md).
When loaded from Ultimate, the calculator instead creates the raw history file
beside its app image, using the selected DOS context. The leaf name remains
1–16 bytes, and the complete path must fit 255 bytes. An overlong path is
rejected before I/O. A failed CLOSE retains the handle; another **S** first
retries that owned CLOSE and permits another save only after cleanup succeeds.
History import, larger/signed/fractional/scientific arithmetic and graphical
controls remain application work.

## Build a native app

`python3 build-native.py` assembles and seals `target/native/calc.prg`,
`target/native/browse.prg` and `target/native/editor.prg`, then adds them as
`CALC`, `BROWSE` and `EDITOR` to the native
disk alongside kernel file `U` and the reserved native boot sector.
The calculator PRG is 3,094 bytes plus its two-byte load
address; it requests 16 pages (4 KiB) for code/data and separately allocates
two bank-1 pages for its history.

Use [`src/native/calc.asm`](../src/native/calc.asm) as an example. Include
[`api.inc`](../src/native/api.inc), assemble at `$6000` with the manifest below,
and seal the resulting image:

```sh
64tass -a myapp.asm -o myapp-unsealed.prg
python3 native_image.py myapp-unsealed.prg myapp.prg
python3 native_image.py myapp.prg
```

The last command validates without writing. The sealer rejects inconsistent
sizes, unsupported ABI/flags, invalid entry points and non-printable title
bytes. Add the sealed PRG to a disk using its normal PRG file type. The current
workspace's C shortcut selects `CALC`; its B browser discovers app images
without requiring a fixed filename. Other native callers can use `N_LAUNCH`
with an explicit device, format and filename.

The PRG starts with little-endian load address `$6000`, followed by this
32-byte manifest. Offsets are relative to `$6000`, excluding the load address.

| Offset | Size | Meaning |
|---|---|---|
| 0 | 4 | Unshifted bytes `NAPP` (`4e 41 50 50`) |
| 4 | 1 | Image format: 1 |
| 5 | 1 | Native kernel ABI major: 1 |
| 6 | 1 | Required ABI minor: 0..14; IEC streams require 1, directory/handoff/source-format fields require 2, Ultimate streams/path mailboxes require 3, Ultimate app loading/boot-device field require 4, Ultimate directory cursors and retained browser paths/names require 5; shared focused fields require 6; application modules require 7; owned display presentation requires 8; desktop session selection requires 9; Ultimate queries/NMI bridge require 10; Ultimate commands require 11; boot-format field requires 12; shared clipboard session fields require 13; document launch requires 14 |
| 7 | 1 | Zero for minor 0..6; minor 7 module-window offset low byte |
| 8 | 2 | Image byte count, including the manifest, excluding the PRG address |
| 10 | 1 | Total allocated pages, 1..96 |
| 11 | 1 | Zero for minor 0..6; minor 7 module-window offset high byte |
| 12 | 2 | Entry offset from `$6000`; at least 32 and below image length |
| 14 | 2 | CRC16-CCITT, little-endian |
| 16 | 16 | Printable PETSCII/ASCII title with zero padding |

All words are little-endian. The image must contain at least one executable
byte after its manifest, fit its declared allocation and end exactly at the
declared byte count. CRC16 uses polynomial `$1021`, initial `$ffff`, no final
XOR, over the entire declared image with checksum bytes 14/15 treated as zero.
The checksum detects damaged images; it is not an application signature.

The current [ABI 1.7 module service](NATIVE-MODULES.md) uses an optional
window beyond the loaded core and within its allocation. Zero/zero keeps the
older manifest behavior. The editor now uses a separate `EDPICK.PRG`. All
22 CPU suites, ten emulator workflows and complete physical USB/IEC workflows
pass in the [module checkpoint](validation/2026-09-11-native-modules/README.md).

## Launch, execution and return

`N_LAUNCH` at `$1c38` uses these source arguments:

| Backend | Source arguments |
|---|---|
| IEC | `N_APPFORMAT` 0 D64, 1 D71 or 2 root D81; `N_DEVICE` 8..30; `N_NAMELEN` 1..16; `N_APPNAME` |
| Ultimate | `N_APPFORMAT` 3; `N_DEVICE` DOS context 1 or 2; `N_NAMELEN` 1..255; raw absolute path in `N_UPATH` |

The format selects both the loader backend and the source context visible to
the app. IEC geometry must match the disk because OPEN checks its sector-chain
extent. IEC names must be printable and cannot contain wildcards or DOS command
separators. Ultimate ignores `N_APPNAME` and uses the exact declared path bytes.
Both paths use the shared file service and its 512-byte buffer. The loader
never passes an unchecked PRG address to KERNAL LOAD.

The kernel checks the manifest before reserving code memory. The fixed slot
is bank 0 `$6000..$bfff`, up to 24 KiB, entirely below native editor/KERNAL ROM.
It reserves the declared range through the heap, initializes all declared pages
to zero, copies only the bounded image, requires EOF at its exact end and
checks the CRC before entering any app instruction. Existing allocations in
the requested range cause allocation failure and remain intact.

The loader requires the normal native MMU/common/zero-page/stack configuration,
enabled interrupts and the keyboard/screen as default input/output. It needs
one of the two shared stream slots and owns its handle as app owner 32.
An existing native IEC stream on the same device may share its command lease;
foreign files on that device remain rejected. An Ultimate launch may coexist
with another owner's stream on the other context. Foreign open files and busy
UCI transactions are preserved. The loader closes its stream before app entry,
and the file service restores borrowed KERNAL parameters around IEC calls.
No private LFNs 120/121 are used.

The app enters with MMU `$0e`, decimal mode clear and owner ID in `N_CURRENT`.
Use that owner for every heap call. ID 32 is reserved for the current app in
this initial implementation; owner 16 belongs to the workspace. Owner 31 is reserved for the
[shared clipboard library](NATIVE-CLIPBOARD.md); applications must not manage
its allocations directly. The code
allocation is itself owned by the app. APIs and execution are foreground-only,
and nested launches are rejected. The [native file service](NATIVE-FILES.md)
provides owned IEC and Ultimate handles. Direct raw KERNAL file use still requires the app
to close its own files.

Return with a balanced **RTS**, A holding the application's result, or use
**JMP N_EXIT** (`$1c3e`) to return from any app call depth. N_EXIT restores the
saved caller stack. The kernel first closes every native file owned by the
app, then releases its code and banked data. Each service preflights its owned
records before cleanup. If corruption or a file error prevents cleanup, the
owner and slot remain retained and further launches are rejected. This is
resource discipline, not memory isolation from
arbitrary machine code. Apps must respect the native ABI and private regions.

`N_LAUNCH` returns carry clear/A=0 after successful loading and lifecycle
cleanup. The app's own result is separate in `N_EXITCODE`; the workspace shows
it when the loader itself succeeded. Loader/cleanup failures return carry set
and their error in A and `N_APPERROR`. Decimal and interrupt flags are preserved;
masked-interrupt callers are rejected before I/O. A/X/Y are otherwise scratch.
Reentrant launch rejection preserves the existing lifecycle/error context;
use the returned carry/A result for that rejected call.

ABI 1.2 adds two one-way exits, using the same stack restoration and cleanup:

* **JMP N_REPLACE** (`$1c53`) requests a new app using the launch source
  arguments above, including N_UPATH for Ultimate. It sets N_ACTION=1 and N_EXITCODE=0.
* **JMP N_WORKSPACE** (`$1c56`) requests the memory workspace. It sets
  N_ACTION=2 and N_EXITCODE=0.

Both require a running app. `N_LAUNCH` returns to its caller after cleanup;
it does not automatically execute N_ACTION. A dispatcher must check carry
before acting on the request. A fresh launch clears N_ACTION, and normal
RTS/N_EXIT leaves it zero. Never follow a handoff after failed cleanup.
The workspace's browser dispatcher loads requested apps only after releasing
the browser's code/cache. A target's normal return reloads BROWSE from the
boot device, preserving the selected data device/format. A target load failure
with completed cleanup reopens BROWSE with the error. Browser-load failures
or retained resources return an error to the workspace. The C shortcut always
selects CALC on the boot volume, independently of the browser's data device.
ABI 1.12 pairs `N_BOOTDEVICE` with read-only `N_BOOTFORMAT` at `$3de4`:
0 D64, 1 D71, 2 D81. The launcher requires minor 12 and restores this pair
when launching a system app; the browser retains the chosen data format.
ABI 1.4 exposes that boot IEC device in `N_BOOTDEVICE`; `N_DEVICE` may now be
an Ultimate context. Apps that use their source for subsequent I/O must inspect
`N_APPFORMAT`, even if they require an older ABI minor. The image validator
accepts older manifests; it cannot infer an app's assumptions about its source.
ABI 1.5 additionally retains the Ultimate browser folder and full selected name.
The browser searches by name on return, preserving selection when file creation
changes directory order; if that name disappeared, it selects the first page.

`N_KEYIN` at `$1c3b` calls native GETIN, returns A=0 when there is no key, and
accounts for consumed keys in `N_KEYS`/`N_LASTKEY`. Applications set `N_READY=1`
only when idle and accepting input, and clear it while processing. These are
foreground observation fields, not an event queue or scheduler.
N_KEYIN clears N_READY before publishing a consumed key, so a new key count
cannot be mistaken for completion using the previous iteration's ready flag.

| Address | Field |
|---|---|
| `$3d20` | N_CURRENT: active owner, or zero |
| `$3d21..$3d22` | N_DEVICE, N_NAMELEN |
| `$3d23` | N_APPSTATE: 0 idle, 1 loading, 2 running, 3 cleanup, 4 retained cleanup error |
| `$3d24` | N_EXITCODE: last app return value |
| `$3d25` | N_DOSCODE: first nonzero DOS diagnostic from failed loader file calls; `$ff` may mean nonnumeric/absent Ultimate status |
| `$3d26` | N_IOSTATUS: first nonzero serial/transport diagnostic from failed loader file calls |
| `$3d27` | N_APPERROR: stable loader/cleanup result |
| `$3d28` | N_ACTION: 0 normal return, 1 replace request, 2 workspace request |
| `$3d29..$3d2a` | N_BROWSERDEV, N_BROWSERFMT: browser preferences |
| `$3d2b` | N_BROWSERERROR: pending dispatcher error shown by BROWSE |
| `$3d2c` | N_APPFORMAT: application's source geometry/backend, 0..3 |
| `$3d2d` | N_BOOTDEVICE: boot IEC device, independent of the current app source |
| `$3de4` | N_BOOTFORMAT: ABI 1.12 boot geometry, 0 D64 / 1 D71 / 2 D81; read-only for apps |
| `$3de5..$3dff` | ABI 1.13 private shared clipboard session; use the clipboard library |
| `$3d2e` | N_BROWSERLEN: retained Ultimate path length, 1..255 |
| `$3d2f` | N_DESKTOPSEL: ABI 1.9 desktop session selection, 0 Calculator / 1 Editor / 2 Files; clear on native restart |
| `$3d30..$3d33` | N_BROWSERPOS: selected directory ordinal, little-endian 32-bit |
| `$3d34` | N_BROWSERNAME_LEN: selected raw name length, 0 when empty |
| `$3d9a..$3d9e` | ABI 1.14 document request, kind, IEC type, Files return and selection-resume flags; see [document launch](NATIVE-DOCUMENT-LAUNCH.md) |
| `$3e00..$3eff` | N_BROWSERNAME: complete retained raw name |
| `$4a00..$4aff` | N_BROWSERPATH: complete retained canonical path |
| `$3d40..$3d4f` | N_APPNAME |
| `$3d60..$3d7f` | N_APPHEADER: last manifest read; valid for a running app |

Existing heap errors retain their values. Loader errors are hexadecimal:
`10` bad image/ABI/address, `11` file/DOS failure, `12` premature EOF (including an empty file),
`13` declared end without EOF, `14` checksum mismatch and `15` channel/default
I/O conflict. N_APPERROR stays separate from the heap's N_ERROR so subsequent
statistics or cleanup do not erase the loader result.
The first loader failure also survives a later cleanup failure. Ultimate CLOSE
can be retried while owned; an uncertain IEC CLOSE quarantines the stream and
retains the app's owner/code instead of replaying the operation.

## Verification and remaining scope

The [ABI 1.6 field checkpoint](validation/2026-09-10-native-fields/README.md)
passes twenty CPU suites, all ten native emulator workflows and full physical
USB/IEC checks. Real browser dispatch verifies that app memory handles remain
distinct from closed source-file handles when their generations diverge.

```sh
python3 tests/ci_native_apps.py --report /tmp/native-apps.json
python3 tests/ci_native_calc.py --report /tmp/native-calc.json
python3 tests/ci_native_loader_ultimate.py --report /tmp/native-loader-ultimate.json
python3 tests/ci_native_usb_apps.py --report /tmp/native-usb-apps.json
python3 -u tests/run_ci.py native
python3 -u hw_ultimate_check.py --native
python3 -u hw_ultimate_check.py --native-usb-apps
```

CPU tests need Py65. They cover the 24 KiB bound, malformed/short/long/damaged
images, channel conflicts and I/O faults, BSS initialization, owner cleanup,
stack-restoring exit, calculator arithmetic/history and complete text screens.
The emulator loads the real app through the native disk/KERNAL path. Hardware
testing retains live workspace allocations while running the calculator,
reads its bank-1 history independently, rejects a damaged app, checks a valid
app's return error and reloads the good calculator before putting the machine's
drive state back. See the [earlier app checkpoint](validation/2026-09-09-native-apps/README.md)
and the [file-service/export checkpoint](validation/2026-09-09-native-files/README.md)
for their respective tested images and outcomes.

See the [browser checkpoint](validation/2026-09-09-native-browser/README.md)
for directory discovery, renamed-app dispatch and source-format export results.

The [USB app checkpoint](validation/2026-09-09-native-usb-apps/README.md)
records the shared loader and USB launch/save workflows against exact images.
Multiple executable banks, cooperative scheduling,
shared display/input widgets, history import and richer banked
document editing remain work.

The [ABI 1.5 directory checkpoint](validation/2026-09-10-native-directories/README.md)
records owned cursors, complete names, folder navigation and selection after
app saves reorder the listing, with CPU, emulator and physical qualification.
The editor now requires minor 5 and includes a [shared file picker](NATIVE-FILE-DIALOGS.md)
that preserves its document while browsing. The
[picker checkpoint](validation/2026-09-10-native-file-dialogs/README.md) records
CPU, emulator and physical USB/IEC qualification.
