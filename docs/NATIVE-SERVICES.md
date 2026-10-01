# Small system services

Libraries that native apps include directly. They make no kernel calls and
keep no resident state, so they cost no kernel bytes. They cover TOS's XBIOS
`Random` and the bell part of its sound support.

## Random numbers (`random.inc`)

`jsr rn_random` returns a 24-bit random number in A (low), X and Y (high).
It is the Atari XBIOS generator:

    seed = seed × 3141592621 + 1   (mod 2^32)
    result = bits 8..31 of seed

The 32-bit seed is `rn_state` (little-endian). Set it to repeat a sequence.
While it is zero, the first call seeds it from the jiffy clock (`$a2`, `$a1`),
the raster line and CIA 1 timer A. TOS seeds from its 200 Hz timer in the
same spirit.

## The bell (`sound.inc`)

`jsr sd_bell` plays a short tone on SID voice 1:
- 880 Hz on a PAL C128 (frequency word 14985), triangle wave;
- attack 2 ms, decay 750 ms, sustain 0, so the note fades by itself;
- volume 15, with the filter off: SID registers `$d400`–`$d418` are write-only,
  so `$d418` is written, not read and changed.

It turns the gate off first, so each call restarts the envelope. The VT52
terminal rings it for BEL. On an NTSC machine the same word gives about
860 Hz.

`jsr sd_click` plays a key click: noise on voice 1 at frequency word `$4000`,
attack 2 ms, decay 6 ms, sustain 0, volume 15. GEMDESK plays it for each
key when the Control Panel's Key click is on.

There is no `Dosound` sequencer, system-wide key click or sound service with
timing yet; those need a timer interrupt the native kernel does not share.

## Verification

`tests/ci_native_services.py` assembles each library on its own and runs it
in Py65. It checks:
- 1,000 consecutive results from a fixed seed against the formula above;
- the unseeded path's seed;
- the exact SID register writes of the bell, in order.

Two planted bugs, a wrong multiplier byte and the gate turned on before the
setup, both fail it. `tests/ci_native_vt52.py` checks that BEL reaches the
bell. Nothing here has been heard on a SID or in VICE.
