# Native REU memory

Desktop, Calculator, Ultimate, Paint, Files, Editor and Claude use an available REU for their saved VDC screens
through the [shared bank-1 VDC component](NATIVE-VDC-SERVICE.md). The same blue
controls work without an REU, using the existing main-RAM backup. With an REU,
Desktop leaves 316, Calculator 300, Ultimate 249, Paint 173, Files 202, Editor 239 and Claude 207 of 426 main-RAM
pages free (Files includes its IEC browser cache; Editor and the shared clipboard are empty) on either
VDC size. The RAM fallback uses another 64 pages with a 16 KiB VDC or 72 with
a 64 KiB VDC. Calculator history, Paint's picture/undo and all VIC surfaces retain their
native heap ownership. Ultimate, Paint and Files keep the same VDC backup while the
picker borrows their display surface. Ultimate allocates picker scratch on
demand; Paint keeps ten scratch pages and Files sixteen for their complete app lifetimes.

`src/native/reu.inc` provides allocation, explicit reservation, free, owner
release, statistics and bounded byte transfers. This is an app-core library
for the current single-foreground-app lifecycle. Include it exactly once in
the retained core; modules call that copy. It does not add a second native
heap bank or grow the resident kernel. Editor also uses this arena for documents,
and [undo records](NATIVE-HISTORY.md) through the [shared memory service](NATIVE-SHARED-MEMORY.md). REU clipboard storage, caches,
suspended apps and a shared scheduled driver remain separate roadmap work.

The [banked SDK example](../examples/native-banked/README.md) also runs this
arena in a retained bank-1 component. Set `RU_BANKED = 1` only under the
[banked executor](NATIVE-BANKED.md): it selects physical bank 1 for the private
probe buffer and bank 0 for `N_BUFFER`. The seven display clients use that mapping inside
`VDSVC.PRG`. Editor retains the component while REU documents or undo history are live, including
after display close. Paint pictures still use main RAM.

## Ownership and calls

Call from the running bank-0 app with the native MMU/common-RAM configuration,
system KERNAL and I/O visible. Foreground calls only: no IRQ/NMI callbacks or
reentrant calls. A busy heap, file service or field service rejects the call.
All entries preserve decimal and interrupt flags and return native error
codes in A with carry set, or A=0/carry clear.

| Entry | Arguments and result |
|---|---|
| `ru_open` | Detect an idle REU; `ru_total` returns capacity in 4 KiB pages |
| `ru_alloc` | `ru_owner` 1–254, `ru_pages` LE16; returns `ru_page` and `ru_handle` |
| `ru_reserve` | Same, with an explicit `ru_page` LE16 start |
| `ru_resize` (optional) | Matching owner/token and requested total `ru_pages`; grow in place or preserve the original extent on failure |
| `ru_free` | Matching `ru_owner` and eight-byte `ru_handle` |
| `ru_release` | Release every allocation with this arena's `ru_owner` |
| `ru_stats` | `ru_available` LE16 pages and `ru_slots` reusable descriptors |
| `ru_read`, `ru_write` | Owner/token, `ru_offset` LE24, `ru_count` LE16 1–512; transfer through `N_BUFFER` |
| `ru_close` | Requires all allocations released; retries a retained probe restoration |

Allocations are contiguous, measured in 4 KiB pages, and are not cleared.
There are 32 descriptors. First fit reuses holes; a reserved interval must be
entirely free. Tokens contain a descriptor slot, a 24-bit generation and the
native app's four-byte allocation handle. Free retains the generation; its
maximum retires the slot until the app allocation ends. Closing/reopening an
arena does not reset generations. The native app handle prevents a token
from becoming valid again after an app reload. A module must keep its arena
and descriptors outside its replaceable window.

Set `RU_INCLUDE_RESIZE=1` to include growth. Equal size succeeds; zero or
shrinking returns `N_BADARG`. Growth beyond capacity or into another extent
returns `N_NOMEM`. A successful resize changes only the descriptor's page
count, preserving its token and every REU byte. The shared service can fall
back to allocate/copy/free when in-place growth is blocked. Other clients
omit this optional code and retain the earlier library's emitted bytes.

`ru_actual` reports the completed transfer prefix. It is zero after validation
or platform refusal, and counts only successful DMA chunks after a transfer
fault. A reentrant call preserves the active call's result state. Invalid
owners, tokens, lengths and ranges cause no DMA. Transfers never wrap into
another allocation or expose an unchecked host pointer.

The arena ends with the foreground app allocation. Ordinary clients free
their allocations and close it before exiting. There is no persistent hardware
transaction between calls. A display client has the stronger requirement to
restore the original display before releasing its snapshot or exiting.

## Hardware behavior

The driver supports the usual 128/256/512 KiB REUs and 1/2/4/8/16 MiB
extensions, including compatible Ultimate REU configurations. Detection saves
and restores the two bytes it uses in each tested bank. Distinct byte pairs
distinguish real RAM from an unpopulated 1764 bank's floating data latch.
The original 1700 alias and extended address latches are handled explicitly.

Every DMA uses an immediate stash or fetch of at most 512 bytes, with host
data in the bank-0 transfer buffer (or the private two-byte capacity probe).
Transfers split at 64 KiB edges, covering the REC's 512 KiB counter wrap.
The driver temporarily selects bank 0 for DMA and 1 MHz, then restores the
original `$d506` and `$d030`. It leaves CPU MMU mapping and zero page intact.
The CPU resumes after DMA; the completion status is checked. These bounded
requests cannot provide a software timeout for hardware that holds DMA forever.

An armed command or enabled REU interrupt mask is refused before register
writes or status acknowledgement. Once claimed, the REU is the OS's volatile
arena, not another driver's RAM disk. The driver consumes its completion
status and leaves the command disarmed with FF00 decode disabled. It resets
the REU bank latch to zero; extended bank bits and hidden autoload shadows
cannot be saved by ordinary register reads. This is not transparent borrowing
of arbitrary foreign REU register state. Bytes outside allocated ranges are
preserved, including the capacity probe's temporary writes.

If probe restoration fails, `ru_probe_live` stays set. Calculator retains its
display and app ownership and shows the existing recovery message; Escape
retries. A snapshot read failure similarly retains the original backup and
blocks handoff. RAM fallback occurs only after a clean refusal or recovery.

The protocol references are Commodore's
[RAMDOS sources](https://github.com/mist64/cbmsrc/blob/01bd60f162ef92212ef0cb67546ae8f42be34168/RAMDOS/ramdos12.src)
and VICE's hardware-tested
[REC implementation](https://github.com/VICE-Team/svn-mirror/blob/86fb219f3214bf0dcbb74dc965bde4116109d388/vice/src/c64/cart/reu.c).
No legacy destructive `GETSIZE` routine is called.

## Validation

`tests/ci_native_reu.py` runs the assembled library against an independent
ownership oracle and a REC bus model. `tests/ci_native_reu_vice.py` cold-boots
the native kernel and loads a checked diagnostic app to exercise actual VICE
DMA. Complete REU memory is compared through saved VICE snapshots, independently
of the transfer routines under test. It also checks untouched bank-1 RAM,
MMU/speed restoration, generation reuse, flags and the final byte of 16 MiB.

`tests/ci_native_reu_calc.py` covers the loaded Calculator's snapshots, graphical
controls, verified history export, fallback and retained failures. The complete
desktop workflow accepts `--reu-kib` and compares VDC restoration with the
independent REU snapshot before the next app loads. These checks use private
emulators and disk copies; physical REU and Ultimate testing remains pending.

```sh
python3 build-native-desktop.py
python3 tests/ci_native_reu.py --report /tmp/reu-cpu.json
python3 tests/ci_native_reu_vice.py --report /tmp/reu-vice.json
python3 tests/ci_native_reu_calc.py --report /tmp/reu-calculator.json
python3 tests/ci_native_pointer_iec.py --d81 --80col --vdc64 --reu-kib 16384
```
