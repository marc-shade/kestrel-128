# GEMDESK in VICE x128 — 2026-09-26

The first emulator run of the GEM desktop, on the build whose dialogs are in
modules (`GDDLG.PRG` and `GDSET.PRG`, loaded into GEMDESK's module window when
needed; [NATIVE-MODULES](../../NATIVE-MODULES.md)).

## Evidence

`tests/ci_native_gemdesk_vice.py` → `vice.json`: 4/4 checks. The run uses
VICE x128 with an emulated 1581 (true drive emulation) and a copy of
`gem.d81` (SHA-256 `1a6ac300…`; `gemdesk.prg` `dde03a0f…`, `gddlg.prg` `8a2e93b8…`,
`gdset.prg` `1844c413…`, `aesvc.prg` `c9c36b3d…`). Keys go through the KERNAL key buffer. After each
step, the whole 9,216-byte VIC surface is read through the binary monitor
and compared with the same oracle the CPU tests use
(`tests/native_gemdesk_scene.py`).

1. Cold boot: the kernel starts `browse` (GEMDESK), which loads
   `AESVC.PRG` from the disk. The desktop matches exactly
   ([desktop.png](desktop.png)).
2. The 8 key opens the boot drive. The listing is read independently from
   the D81 directory sectors by the test (track 40, from sector 3). It is
   sorted by name and matches exactly ([drive-8.png](drive-8.png)).
3. Cursor down selects `CALC`, and Return launches it through the
   dispatcher ([calc-selected.png](calc-selected.png)); Calculator runs as
   owner 32.
4. Esc leaves Calculator. The dispatcher starts GEMDESK again; it finds the
   resident AES and reopens the drive window from the AES session, with
   `CALC` still selected, exactly ([back.png](back.png)).

The images are rendered from the captured surfaces by `render_surface.py`.

The same build passes the CPU suites `tests/ci_native_gemdesk.py` (35/35)
and `tests/ci_native_aes.py` (31/31), and the AES's own VICE suite,
`tests/ci_native_aes_vice.py` (5/5, AES 1.6).

## Limits

- An emulator, not a C128: VICE's 1581 and KERNAL, no 1351 mouse, keys
  only. Nothing was run on hardware.
- Pointer workflows, dialogs, Delete, Format and Save Desktop were not
  driven in VICE; only in the CPU model.
