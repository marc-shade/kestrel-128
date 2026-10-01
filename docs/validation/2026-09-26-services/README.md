# Free space, random numbers, the SID bell — 2026-09-26

## What changed

- `dos-command.inc`: `dc_blocks_free` reads the drive's `$` listing on
  secondary address 0 and keeps the number of its last line, the "BLOCKS
  FREE." line. GEMDESK's drive Show Info shows it ("Blocks free").
- `random.inc`: the XBIOS `Random` formula, `seed*3141592621+1`, returning
  bits 8..31. It seeds itself from the clocks when the seed is zero.
- `sound.inc`: the SID bell (voice 1, 880 Hz PAL, decaying triangle). The
  VT52 terminal rings it on BEL.
- Test models:
  - `StreamIEC` sends a `$` listing, with a BLOCKS FREE line from the
    format's capacity (664, 1,328 or 3,160 blocks).
  - The Claude/VT52 `TerminalBus` accepts SID register writes.

## Evidence (Py65, CPU level)

- `tests/ci_native_services.py` → `services.json`: 3/3:
  - 1,000 results against the formula from a fixed seed;
  - the unseeded path;
  - the bell's exact SID writes, in order.
- `tests/ci_native_gemdesk.py` → `gemdesk.json`: 35/35. The drive Show Info
  alert now ends "Blocks free: 624" (664 − 40 on a D64 model).
- `tests/ci_native_vt52.py` → `vt52.json`: 9/9. BEL leaves the SID with the
  bell's frequency and gate.
- `tests/ci_native_files.py` passed with the extended IEC model.

Planted bugs, all caught:

| Planted bug | First failing case |
|---|---|
| Free blocks from the first line, not the last | drive info |
| Wrong multiplier byte | the 1,000-result case |
| Bell gate turned on before the setup | the bell case |

The harness also caught a real bug. The first bell read `$d418` to keep the
filter bits, but SID registers `$d400`–`$d418` are write-only on the chip.
The bell now writes `$0f`.

## Limits

- The bell has not been heard on a SID or in VICE.
- There is no key click or `Dosound` sequencer (no shared timer interrupt).
- `dc_blocks_free` is IEC only.
- No app uses `random.inc` yet.
