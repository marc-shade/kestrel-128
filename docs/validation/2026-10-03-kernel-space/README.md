# Kernel space: system section at $0c00, boot-only code in staging (2026-10-03)

## Why

On 2026-10-02 the resident kernel had 15 free bytes in total (main section 6,
direct-desktop main 4, low section 8, service region 7, measured from
`target/native/layout.json`). The remaining README features (an REU module
cache, app windows and switching) need new kernel code, so space came first.

## Change

- **System section** at `$0c00..$0fff` ([NATIVE-KERNEL](../../NATIVE-KERNEL.md)):
  C128 RAM used only by the KERNAL's RS-232 buffers (while device 2 is open;
  the native system never opens it) and BASIC's sprite definition area. It is
  bank-0 RAM below `$4000`, so its code runs under the native map with no
  gate. The text-mode **memory workspace** (draw loop, keys 1/2/A/F/W/V, the
  8 KiB pattern test, screen output and its strings and state) moved there
  unchanged; only the branches that now cross sections became jumps. It uses
  860 of 1,024 bytes.
- **Boot-only code** (startup, relocation, keyboard ownership, `heap_init` and
  `sys_install`) moved from the resident regions into boot staging
  (`kernel-boot.inc`), after the low-section image. A small `native_start`
  stays below `$4000`: SYS enters with BASIC's map, where the staging
  addresses are BASIC ROM.
- **Boot wrapper**: the compressed boot places its packed input at the top of
  app RAM (`BOOT_INPUT`, `$9d00`), not at `$6000`, and checks that the decoded
  kernel ends below it, so staging may grow to `N_STAGELIMIT` (`$8000`).
- `layout.json` adds `boot_start`, `boot_end`, `sys_image_start`,
  `sys_start`, `sys_end`, `sys_limit`, `staging_limit` and `free_pages`, and
  drops `keyboard_start`/`keyboard_end` (keyboard installation is boot code
  now; the resident guard `native_keycheck` is unchanged).
- The heap keeps all 426 pages; public entries, the app slot and every app
  image are unchanged.

## Space (from `layout.json` and `kestrel.sym`)

| Region | 2026-10-02 free | Now free |
|---|---:|---:|
| Main section, workspace kernel (before `$3800`) | 6 | 1,005 |
| Main section, direct-desktop kernel | 4 | 1,001 |
| Low section (before the NMI bridge at `$1bf0`) | 8 | 50 |
| Service region (below `$4bfc`, and before `$5000`) | 7 | 49 + 7 |
| System section `$0c00..$0fff` | n/a | 164 |

BASIC's run-time stack at `$0800..$09ff` (512 bytes) is also unused natively
and is documented as the next region for resident growth; nothing uses it
yet. The kernel PRG is 16,747 bytes (from 15,617) and ends at `$5d6a`.

## Designs tried first

The first designs put a 4 KiB or 2.8 KiB "kernel extension" into heap pages
and called it through a bank-switching gate. Each failed the CPU sweep on a
capacity edge that the suites pin, so none of them shipped:

1. Bank-1 `$ef00..$feff`: the shared clipboard avoids the app component window
   `$6000..$bfff` and needs 60 contiguous pages below or above it; its high
   range fell from 63 to 47 pages (`ci_native_clipboard`,
   `ci_native_clipboard_apps --case large`).
2. Bank-1 `$5000..$5fff`: collided with the AES data tables (`AE_DATA`) and
   left room for fourteen of the sixteen 16-page chunks a 64 KiB no-REU Editor
   document needs (`ci_native_aes`, `ci_native_editor_gui --case large`,
   `ci_native_document`).
3. Bank-0 `$f400..$feff`: cost one chunk with both diagnostic workspace blocks
   held, and with a 66,053-byte document open the file picker's directory
   limit fell from at least 296 entries to fewer than 175
   (`ci_native_picker_gui --case large`).

Any heap reservation costs some workload at an exact edge; the system section
costs none. The KX gate and its test were removed; the boot-wrapper and
boot-only changes from that work remain.

## Tests

- `ci_native_relocation`: 17 cases; new: the system section copy for D/I
  flags 0/4/8/12 with and without IRQs, exact image bytes, nothing written
  outside `$0c00..$0fff` but the routine's own operands.
- `ci_native_heap`: the test machine's boot sequence adds `sys_install`.
- `ci_native_running_layout` and the VICE suites that audit running kernel
  bytes (`--running-layout`, keyboard, pointer, transport) include the system
  section, so a KERNAL write into it during those workflows fails them. The
  first VICE run failed those audits: the dispatcher's `ui_system_device` and
  `ui_browser_stage` stayed in the main section, and the one declared range
  that used to cover them (`ui_handles..ui_test_operation`) moved to the
  system section. They are now declared mutable in their own right.
- `ci_native_keyboard`: keyboard installation is located in boot staging.
- `ci_native_boot_pack`: the packed input address comes from `BOOT_INPUT`.
  A flipped bit inside an LZSA match over a run of equal bytes can decode to
  the identical kernel; the reference unpacker now decides each case, and the
  6502 decoder must refuse every flip that changes the output and boot the
  exact CRC-checked kernel otherwise.
- VICE, real C128 ROMs: `ci_native` (cold boot, workspace in the system
  section on both screens, both banks' 8 KiB blocks, calculator) and
  `ci_native_boot_vice` (four kernels).

- `native_input_capture_vice` (`ci_native_desktop_iec --input-during-capture`)
  reads `hbyte` from the symbol table instead of a fixed `$17d0`; the low
  section's layout moved when `heap_init` left it.

Full sweep on the final images (`tests/sweep_native.py` through the resumable
driver, from a snapshot of this tree):

- CPU group: 322/322 passed (three chunks).
- VICE group: 59/59 passed. The first pass failed 23 jobs on the
  running-layout declaration above; after the fix, 56 passed in a three-way
  parallel run, and the remaining three passed run one at a time: two had
  lost their VICE monitor connection under the parallel load, and one needed
  the `hbyte` change. Every `.prg`, `.d64` and `.d81` in the commit is
  byte-identical to the swept snapshot.

## Not verified

- Nothing has run on the physical C128. That the ROM leaves `$0c00..$0fff`
  alone is checked by reading the C128 memory map and by VICE workflows with
  the running-layout audit, not on hardware.
- An app that opens RS-232 device 2 through the KERNAL would overwrite the
  workspace code; no shipped app does, and nothing enforces it.
