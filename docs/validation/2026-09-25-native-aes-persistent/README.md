# Persistent AES component (GEM layer step 1) — 2026-09-25

Step 1 of the [GEM layer design](../../GEM-LAYER-DESIGN.md): the banked
executor gains a second, block-scoped instance for owner 30 at bank-1 `$9000`,
and `AESVC.PRG` stays resident across app exits. See
[NATIVE-AES](../../NATIVE-AES.md).

## Evidence

All CPU jobs ran with Py65 (`~/.venvs/uos-tests/bin/python -B`) and wrote the
reports kept here:

| Report | Command | Result |
|---|---|---|
| `aes.json` | `tests/ci_native_aes.py` | 6/6 cases |
| `banked.json` | `tests/ci_native_banked.py` | passed |
| `banked_sdk.json` | `tests/ci_native_banked_sdk.py` | 9 SDK cases |
| `vdc_client.json` | `tests/ci_native_vdc_client.py` | passed |
| `vdc_service.json` | `tests/ci_native_vdc_service.py` | passed |

`ci_native_aes.py` runs several apps in one machine. It covers:

- load, and survival of the component after exit;
- attach from a second app without loading, with counters persisted in the
  bank-1 image and the callback re-patched;
- full unload back to 175/251/32 free;
- a fresh load after unload;
- refusal of a wrong identity and of a zero callback import (the mark of an
  interrupted load) with `N_BADIMAGE`;
- a clean refusal when another owner holds `$9000`;
- corrupt (`N_CHECKSUM`) and missing component files leaving nothing resident.

## Byte identity

The executor parameters are weak defaults, and the attach/detach code
assembles only for a non-app owner. `build-native-desktop.py` and
`build-native.py` reproduced all 59 PRG/D64/D81 images with unchanged SHA-256
values. The native-banked SDK example images (`BANKDEMO.PRG`, `BKREU.PRG`)
built from HEAD and from this change are byte-identical.

Example images from this run: `AESVC.PRG` 196 bytes, CRC16 `$61c6`, SHA-256
`b20e97b1…dbb3`; `AESDEMO.PRG` 2,737 bytes, SHA-256 `e530e7c0…cc76`
(full values in `aes.json`).

## Bugs found and fixed during qualification

- A failed persistent load left its partially written owner-30 image
  resident after the app exited, with a valid header that a later attach
  could adopt. `ae_load` now frees a failed load, and attach refuses a zero
  callback import.
- The caller's stream-ownership signal was lost by that cleanup;
  `ae_stream_taken` now records it before cleanup.

## Limits

No physical C128 run. The AES has not been exercised alongside VDSVC in one
app. Attach cannot CRC-check the live image. Alerts, events, menus, windows
and accessories are later steps.
