# Commodore source reference for native Kestrel

The user-supplied [mist64/cbmsrc collection](https://github.com/mist64/cbmsrc)
is pinned at commit
[`01bd60f162ef92212ef0cb67546ae8f42be34168`](https://github.com/mist64/cbmsrc/tree/01bd60f162ef92212ef0cb67546ae8f42be34168).
The inspected checkout is `<home>/code/cbmsrc`. Its catalog identifies
`KERNAL_C128_05` and `EDITOR_C128` with ROM revision 318020-05, the revision
used by the local native CPU and VICE tests.

## Verified interrupt behavior

The [KERNAL interrupt dispatcher](https://github.com/mist64/cbmsrc/blob/01bd60f162ef92212ef0cb67546ae8f42be34168/KERNAL_C128_05/interrupt.src#L74)
saves A, X, Y and the interrupted MMU mapping, then selects `sysbnk` before
calling the indirect IRQ handler. The
[declaration of `sysbnk`](https://github.com/mist64/cbmsrc/blob/01bd60f162ef92212ef0cb67546ae8f42be34168/KERNAL_C128_05/declare.src#L681)
is `$00`: RAM bank 0, system ROMs and I/O. The return path restores the saved
mapping and registers before RTI.

The [editor IRQ path](https://github.com/mist64/cbmsrc/blob/01bd60f162ef92212ef0cb67546ae8f42be34168/EDITOR_C128/ed1.src#L297)
reaches `CLI` before scanning keys, including when `graphm=$ff` leaves VIC
management to the application. In the tested ROM, that instruction is at
`$c229`. A nested interrupt can therefore save `$00` while an outer frame
still holds the application's `$0e` mapping. The observer's historical
`foreground_mmu` field describes the interrupted context.

The [retained correlation](validation/2026-09-12-native-capture-context/cbmsrc-reference/result/report.json)
assembles two source excerpts with supplied symbol addresses: 38 bytes at
`$ff17` and 32 bytes at `$c214`. All 70 bytes match the local ROM. This is an
excerpt comparison; it does not rebuild the complete ROM or identify the ROM
installed on the physical C128. Source-file and ROM hashes are retained in
[the provenance record](validation/2026-09-12-native-capture-context/cbmsrc-reference/provenance.json).
The accompanying [validation record](validation/2026-09-12-native-capture-context/README.md)
includes forced nested RAM/VDC captures and complete foreground returns in VICE.

## Implementation references

| Reference in the pinned collection | Kestrel work it informs | Required validation |
|---|---|---|
| `KERNAL_C128_05/interrupt.src`, `EDITOR_C128/ed1.src`, `ed3.src` | Native IRQ chaining, mapping preservation, keyboard scanning and repeat handling | Nested interrupts, complete stack return, input during observation, keyboard/joystick interaction |
| `EDITOR_C128/ed2.src`, `ed6.src` | VDC line copy/fill, character and attribute access | Busy-state bounds, address preservation, 16/64 KiB configurations and physical display results |
| `KERNAL_C128_05/serial.src`, `DOS_1571_05`, `DOS_1581` | IEC and drive-specific serial/burst operations | Capability negotiation, correct geometry, timeout/recovery and per-drive physical qualification |
| `RAMDOS/ramdos12.src` | Commodore REU RAM-disk implementation and C128 integration | Owned memory, capacity/address boundaries, preservation, absent-device behavior and real REU transfers |

These references guide the existing
[completion roadmap](IMPLEMENTATION-ROADMAP.md). Each driver still requires
its own implementation and acceptance evidence.

To replay the excerpt comparison with the pinned checkout and local ROM:

```sh
python3 -B docs/validation/2026-09-12-native-capture-context/cbmsrc-reference/correlate.py \
  --cbmsrc <home>/code/cbmsrc \
  --rom /usr/share/vice/C128/kernal-318020-05.bin \
  --work /tmp/kestrel-cbmsrc-correlation
```
