# Incomplete cartridge uploads and desktop recovery

The first IEC qualification failed before reaching the native boot marker.
No editor operation or save was performed. Later read-only cartridge metadata
showed that the data disk upload contained 63,488 of 174,848 bytes. The native
system disk, subsequent legacy system disk, and both recovery program uploads
were zero-byte files. Their HTTP controls had returned success.

| Cartridge file | Role | Observed bytes |
|---|---|---:|
| `/Temp/temp009A` | Failed IEC data disk | 63,488 |
| `/Temp/temp009B` | Failed IEC native disk | 0 |
| `/Temp/temp009C` | Automatic legacy restoration disk | 0 |
| `/Temp/temp009D` | Automatic restoration loader | 0 |
| `/Temp/temp009E` | Explicit recovery loader | 0 |
| `/Temp/temp0098` | Intact deployed disk from the USB run | 174,848 |
| `/Temp/temp0099` | Intact deployed loader from the USB run | 2,036 |

The original failed run is retained in `hardware-iec-boot-timeout`. Its report
was written before its restoration exception and does not claim restoration.
Subsequent observations and recovery records are separate files. Nothing in
that failed directory contributes a passing native-editor qualification.

## Recovery evidence

A single CPU resume and a later cartridge reinitialization/program reload
both returned HTTP 200 with empty error arrays, but the desktop vector stayed
zero. BASIC screen capture then showed an empty program after the runner's
LOAD/RUN sequence. A full RAM comparison found old loader bytes with changes
at the BASIC link and `$0a00..$0bff`; a two-byte repair was not attempted.

Direct `LOAD"UOS",8,1` against the zero-byte mounted image returned FILE NOT
FOUND. The byte check withheld RUN. The old loader RAM observation and its
hash are retained. After remounting `/Temp/temp0098` without an upload, the
same IEC command loaded all 2,034 payload bytes correctly. Only then was RUN
issued. The desktop became live, all nine saved settings bytes were restored,
and the complete drive snapshot matched the one taken before the failed run.

`boot-existing-recovery.json` records that successful recovery. The shared
`basic-loaded-program.bin` filename contains this final, correct load; the
earlier failed-load hash matches the separately retained full RAM capture in
`boot-diagnostics/uos-fields-boot-diagnostic-5i06qp8m`. The verifier checks both
versions rather than treating the shared filename as two observations.

The first resume report predates per-request start/acknowledgement flags and
retains its original response-only schema. Later recovery records journal
each request before sending and retain the response status/body. Intermediate
source snapshots are in `boot-recovery-harness`; the original 99-file USB and
failed-IEC harness can be reconstructed from its preserved manifest and the
two saved original files. The current qualification harness has 102 files.

## Temporary storage and new safeguards

Older firmware's `/Temp` accumulation is documented upstream. The reference
device reports REST API version 0.1; `/v1/info` is unavailable, so these records
do not establish an exact firmware version. The partial-then-empty uploads,
followed by complete uploads after reclaiming space, support temporary-storage
exhaustion as the cause. [Ultimate temporary-storage documentation](https://1541u-documentation.readthedocs.io/en/latest/howto/assembly.html)

Three unmounted images from the preceding completed IEC qualification were
read in full and compared with their archived native disk, saved document disk
and unchanged deployed disk. Only those exact files, `/Temp/temp0094`,
`/Temp/temp0093` and `/Temp/temp0095`, were removed. All 524,544 bytes read before
removal are archived. Missing-file responses confirm removal, and the desktop,
settings, drive mounts and both DOS paths were preserved. One TCP connection
timeout happened before any request bytes were sent; no uncertain write was
replayed.

The revised IEC harness checks each uploaded disk's stored size before boot.
It prepares and independently reads back a complete recovery loader before
switching disks. Restoration reuses the original mounted system disk and that
verified loader, avoiding new restoration uploads. After independent saved-file
verification, the workflow removes its own temporary system/data images and
recovery loader. Original failure and restoration errors remain separately
recorded even when restoration fails.

Eleven local upload tests cover success responses with zero, partial and extra
data; control/JSON failures; lost responses; and invalid existing recovery
files. Five orchestration tests cover loader verification failure, either disk
upload failing, an editor failure and a missing recovery file. All pass along
with the eight existing transport tests. They perform no hardware I/O.

`verify-boot-recovery.py` audits the retained failure, successful recovery,
reclamation bytes and harness versions without accessing the cartridge. The
new full IEC run passes the regular screen, memory, ownership and independent
saved-file checks. It restores the original desktop and removes all three of
its private temporary files after independent readback.
