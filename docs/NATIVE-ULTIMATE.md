# Native Ultimate file backend

Native ABI **1.3** adds Ultimate DOS to the existing owned file service. The
editor can open and save USB files without routing their data through an
emulated IEC drive. ABI **1.4** routes application loading through the same
owned service. **L** in Files and Apps launches an absolute USB app path, and
a USB-loaded calculator saves history beside its image. ABI **1.5** adds owned
directory cursors and native USB folder navigation. The editor's Open/Save As
fields now offer **Tab** for a [shared picker](NATIVE-FILE-DIALOGS.md), qualified
through the [USB/IEC picker checkpoint](validation/2026-09-10-native-file-dialogs/README.md).
Boot still uses IEC.
Shared GUI input, control/network/RTC services and capability discovery
remain required by the [completion roadmap](IMPLEMENTATION-ROADMAP.md).

In the editor, press **F6** until the status line shows **DOS:01 ULT**.
F1 opens an absolute path such as `/Usb0/Notes/Example.txt`; F3 saves to a new
path. F8 selects DOS context 1 or 2. Neither context's current directory is
changed. Long paths show a leading `<` and their tail when they exceed the
screen row; all bytes remain in the field. Returning to the browser preserves
the Ultimate data context, folder and complete selected filename. **F** in the
browser cycles back to the boot IEC device and D64 geometry.
The editor's data backend is independent of its app-image source; loading its
PRG through USB preserves valid browser data preferences until F6/F8 changes them.

## File API

The entry points and owner/generation handle format are unchanged. Include
[`api.inc`](../src/native/api.inc) and require ABI minor 3 in the app manifest.

| Mailbox | Ultimate meaning |
|---|---|
| `N_FFORMAT` | 3 when opening an Ultimate file |
| `N_FDEVICE` | DOS context 1 or 2 |
| `N_FNAMELEN` | 1–255 bytes |
| `N_UPATH` (`$4e00`) | Exact path bytes, starting with `/`; no NUL within the declared length |
| `N_FMODE` | 0 read, 1 exclusively create a new read/write firmware file; ABI 1.5 mode 2 opens a directory cursor |
| `N_FTYPE` | Valid values 0–2; raw file bytes are independent of the CBM type |
| `N_USTATUS` (`$4f00`) | Up to 31 status bytes plus a NUL terminator |

`N_FREAD`, `N_FWRITE`, `N_FCLOSE` and `N_FRELEASE` dispatch using the owned
descriptor; later changes to the input device/format fields cannot redirect
an open handle. Two streams are available in total, shared with IEC. One
stream may use IEC while the other uses Ultimate. Each Ultimate context can
have at most one owned file. `N_DIRPAGE` remains IEC-only and rejects format 3.
The ABI 1.4 loader consumes one slot during loading and closes it before entry.
It uses `N_APPFORMAT=3`, `N_DEVICE=1/2`, `N_NAMELEN` and `N_UPATH`; see the
[app contract](NATIVE-APPS.md) for source and boot-device fields.

Transfers use `N_BUFFER` and counts 1–512. Read extent and position are 32-bit;
the requested position increment must not wrap. Read requests are clipped to
the remaining extent. Success returns the exact count, updated position and
EOF flag. A failed Ultimate transfer returns zero actual bytes and retains an
uncertain handle; bytes remaining in the transfer buffer are not valid output.

All native file calls require foreground execution with IRQs enabled, MMU
`$0e`, the standard native common area, and the console unredirected. The
Ultimate code borrows no zero-page bytes, changes no MMU register and opens
no KERNAL channels. Native IRQs remain serviceable during cartridge polling.
The common file-service lock rejects reentry before issuing a command.

## Directory cursors (ABI 1.5)

Require ABI minor 5, set format 3, mode 2, owner, DOS context, path length and
`N_UPATH`, then call `N_FOPEN`. The service checks that the context has no open
file, saves its original CWD, changes to the requested directory and opens the
firmware snapshot. Successful OPEN returns the canonical absolute path in
`N_UPATH` and `N_FNAMELEN`. Original and resulting paths must each fit 255 bytes.
The cursor uses one of the two shared stream handles; only one native directory
cursor can exist at a time.

Set `N_FCOUNT=512` for every directory `N_FREAD`. Each successful call returns
one complete packet: the attribute byte followed by 1–255 raw filename bytes.
`N_FACTUAL` is 2–256, with no terminator. Embedded NUL, slash or backslash,
oversized packets and failed status replies are errors. The 32-bit
`N_FPOSITION` counts entries consumed. EOF returns zero bytes on later calls
without another command. An empty OPEN sets EOF without issuing READ_DIR.
Do not interpret the file byte-count or IEC page-record layout as this format.

Forward reads continue one READ_DIR transaction. While packets remain pending,
other Ultimate operations return `N_CHANNELS` before touching or poisoning
their handles; IEC transfers can continue. Before the first READ or after EOF,
the other DOS context can service a file, but the directory's context stays
reserved until CLOSE. This is a foreground service, with no background broker.

EOF leaves the cursor owned. `N_FCLOSE` cancels only its active transaction,
confirms transport idle, restores the original CWD and compares GET_PATH with
every saved byte. Failed cancellation or restoration retains the handle for
checked cleanup. `N_FRELEASE` closes an owned directory before other owned
Ultimate files, regardless of slot order. Transfer errors are not replayed.

The inspected firmware has no explicit directory CLOSE and no query for an
idle foreign directory snapshot. OPEN therefore claims the selected context's
idle directory snapshot for Kestrel. The service preserves foreign open files and
active transactions; it cannot promise to preserve an undetectable idle
snapshot from another client. This ownership limit must be addressed when a
shared broker or background applications are introduced.

The [browser](NATIVE-BROWSER.md) is the first cursor consumer. It retains eight
complete names per page and fills a second buffer before publishing navigation.
Failed or cancelled scans preserve the previous visible page and selection.
App returns search for the complete selected filename, so a saved file that
reorders the listing does not silently select a different app.

## Ownership and error handling

Before claiming a DOS context, FILE_INFO must explicitly report `85` (no file
open). A foreign open file or non-idle UCI transaction is refused; the backend
does not abort or close that foreign resource. Once OPEN is sent, ownership
remains recorded until a checked CLOSE succeeds or reports `84` (no file to
close). Even a plain-text OPEN rejection retains its handle for that cleanup.

An owned timeout or malformed response sends ABORT without replaying the
request. Polling, packet count, response storage and status storage are bounded.
The first nonzero status across response packets is retained. Short reads,
excess response bytes and malformed statuses fail instead of masquerading as
EOF. FILE_INFO supplies the checked extent; an empty READ status is accepted
only when every requested byte arrived.

The current [owned-abort follow-up](validation/2026-09-11-native-owned-abort/README.md)
also observes completion of that native-owned abort before returning the error.
It waits for transport idle or a second bounded timeout, preserving the
initiating `$ff`/`$fc` status and making no further submission inside the wait.
This lets immediate explicit directory cleanup proceed after a delayed abort.
If the abort never completes, the error still returns within the bound and the
owner remains retained for later checked recovery. Foreign transactions still
receive no abort. The changed kernel passes 24 CPU suites and ten emulator
workflows. The first physical USB attempt failed during a saved-file reopen
through DOS context 2. The full unmodified retry passes, including complete
readback of ten files, native cleanup and restoration of the desktop and DOS
paths. Physical IEC qualification also passes with independent readback of all
four document-disk files and full restoration/cleanup. Neither the synthetic
delays nor these passing runs establish the initiating cause of the earlier USB failures.

Writes preserve the source bytes, split a full 512-byte request into **511 + 1**,
seek back and compare a complete read of the same extent. This is the
workaround for physical USB write corruption found with the earlier C64-mode
file service. Short writes and mismatches poison the handle. Creation rejects
components longer than 127 bytes before I/O because of the inspected firmware's
creation-buffer limit. Read paths retain the full transport-bound name and may
still encounter firmware lookup limits.

Errors use the native file result (`N_IOERROR`, `N_CHANNELS`, argument/owner/
generation errors). `N_FDOS` holds the most recent numeric Ultimate status,
or `$ff` when absent/nonnumeric. `N_FSTATUS` adds transport detail: `$fe` absent,
`$ff` timeout, `$fc` malformed/oversized response, `$e2` foreign busy transaction,
`$e5` short read, `$e6` verification mismatch. Check the returned carry/A result;
an empty successful READ can legitimately leave `N_FDOS=$ff`.

Ultimate CLOSE can be retried while the context remains owned. IEC uncertain
close retains its stricter quarantine behavior. No new owner may claim either
retained stream. The editor retains dirty state after any failed save and
clears it only after CLOSE, reopen, a complete document comparison and read
CLOSE all succeed. Failed/cancelled saves may leave a partial file. Neither
the service nor the editor retries a write, overwrites an existing file or
deletes that partial output. This is not a power-loss durability guarantee.

## Resident memory and verification

Bank-0 `$4000..$4fff` is reserved for the native Ultimate service, command and
verification buffers, and path/status mailboxes. The allocator manages 175
bank-0 pages and 251 bank-1 pages: **426 pages / 109,056 bytes**. Startup stages
the low kernel at `$5000..$54ff`, then releases those five pages for allocation.
The workspace's 8 KiB bank-0 block uses RAM beneath ROM at `$df00..$feff`,
leaving the application slot at `$6000` available. See the generated
[`layout.json`](../target/native/layout.json) and [kernel contract](NATIVE-KERNEL.md).

```sh
python3 build-native.py
python3 tests/ci_native_ultimate.py --report /tmp/native-ultimate.json
python3 tests/ci_native_editor_ultimate.py --report /tmp/native-editor-ultimate.json
python3 tests/ci_native_loader_ultimate.py --report /tmp/native-loader-ultimate.json
python3 tests/ci_native_usb_apps.py --report /tmp/native-usb-apps.json
python3 tests/ci_native_directory_ultimate.py --report /tmp/native-directory-ultimate.json
python3 tests/ci_native_browser_ultimate.py --report /tmp/native-browser-ultimate.json
python3 -u tests/run_ci.py native nativeeditor nativeeditor71 nativeeditor81
python3 -u hw_ultimate_check.py --native-ultimate
python3 -u hw_ultimate_check.py --native-usb-apps
python3 -u hw_ultimate_check.py --native-usb-browser
```

`--native-usb-browser` refuses to run until an independent directory reference
is available (see [NATIVE-EDITOR](NATIVE-EDITOR.md)).

CPU checks compose the native C128 MMU/ROM bus with the existing independent
UCI register/FIFO and DOS byte model. They cover fragmented binary reads,
16 MiB extent carry, 255-byte paths, IRQs, foreign resources, mixed backends,
timeouts, status errors, short/corrupt writes, and the complete editor workflow
beyond 64 KiB. The
[physical checkpoint](validation/2026-09-09-native-ultimate/README.md) records
the reference C128/Ultimate II+ workflow, both DOS contexts, complete VIC/VDC
screens, preserved workspace RAM and independent closed-file byte comparisons.
Opening 66,053 bytes took 38.311 seconds; verified Save As of 66,056 bytes took
78.891 seconds. These workflow measurements include the harness's quiet and
polling intervals. The editor's later
[incremental redraw checkpoint](validation/2026-09-09-native-redraw/README.md)
addresses field/document input cost. The storage checkpoint
does not qualify additional cartridge models or every firmware revision.
The [USB app checkpoint](validation/2026-09-09-native-usb-apps/README.md)
records the shared loader, full-path launch field, calculator save/recovery
and USB-loaded editor against the later ABI 1.4 kernel.

Protocol references: [Ultimate DOS](https://1541u-documentation.readthedocs.io/en/master/uci/ultimate_dos_target.html)
and [UCI registers and queues](https://1541u-documentation.readthedocs.io/en/latest/uci/core_uci_architecture.html).

The [ABI 1.5 directory checkpoint](validation/2026-09-10-native-directories/README.md)
records owned cursors, complete names, folder navigation and selection after
app saves reorder the listing, with CPU, emulator and physical qualification.
