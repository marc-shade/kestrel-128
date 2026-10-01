# Acknowledgements

Kestrel 128 stands on other people's work. This page names where its ideas,
formats and tools come from. Kestrel 128 itself is licensed under the GNU
General Public License, version 3 or later ([LICENSE](LICENSE)).

## Where it started

- **UltOS** by Scott Hutter ([xlar54/uos-master](https://github.com/xlar54/uos-master)),
  a graphical desktop for the Commodore 64 and the Ultimate cartridge line,
  published under the GPL (version 3 or later). Kestrel 128 began as a fork of
  UltOS; the native C128 system grew beside it and replaced it. The
  calculator's arithmetic (`src/native/calc-engine.inc`) is adapted from
  UltOS's calculator.

## Designs it follows

- **Atari TOS and GEM** (Atari Corporation; GEM by Digital Research). The
  desktop, the AES (menus, windows, alerts, forms, events) and the desk
  accessory follow their behavior; [TOS-PARITY](docs/TOS-PARITY.md) and
  [GEM-LAYER-DESIGN](docs/GEM-LAYER-DESIGN.md) record the comparison. No TOS
  or GEM code is used.
- **GEOS 128** (Berkeley Softworks), with **Wheels** and **MegaPatch 3**, as
  reference points for a C128 desktop ([MEGAPATCH-3-PARITY](docs/MEGAPATCH-3-PARITY.md),
  [WHEELS-PARITY](docs/WHEELS-PARITY.md)). No GEOS code is used.
- **The Commodore 128 KERNAL and screen editor sources**, as collected in
  [mist64/cbmsrc](https://github.com/mist64/cbmsrc), for the ROM behavior the
  kernel relies on ([COMMODORE-SOURCE-REFERENCE](docs/COMMODORE-SOURCE-REFERENCE.md)).

## Formats and hardware

- **LZSA2**, the block compression format of Emmanuel Marty's
  [LZSA](https://github.com/emmanuel-marty/lzsa). Kestrel 128 packs its apps
  and boot files in this format with its own compressor and 6502 decoder,
  written from the format description.
- **The Ultimate II+ cartridge** by Gideon Zweijtzer
  ([1541ultimate](https://github.com/GideonZ/1541ultimate)): its command
  interface, USB storage, REST API and FTP server are what the Ultimate app,
  USB storage support and the hardware checks talk to.

## Kestrel 128's own components

- **claude-c128** ([marc-shade/claude-c128](https://github.com/marc-shade/claude-c128)),
  MIT license: the Claude terminal app and its host bridge
  ([apps/claude](apps/claude/README.md)).
- The 8×8 and 5-pixel fonts are original drawings; no ROM font is copied
  (`src/native/graphics/font.py`).

## Tools

- [64tass](https://sourceforge.net/projects/tass64/), the 6502 assembler.
- [cc65](https://cc65.github.io/), the C compiler and linker for Sheet and the
  Claude client.
- [VICE](https://vice-emu.sourceforge.io/), whose x128 and c1541 run the
  emulator tests and build the disk images.
- [py65](https://github.com/mnaberez/py65), the 6502 simulator behind the CPU
  tests, and [pyte](https://github.com/selectel/pyte), the terminal emulator
  inside the Claude host bridge.
