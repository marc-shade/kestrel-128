# Wire protocol

A byte stream in both directions over the ACIA. Deliberately small: the C128
decodes it with a resumable state machine in about 200 bytes of C, because bytes
arrive from an NMI ring buffer in arbitrary chunks and any command can be split
across two reads.

Coordinates and run counts use single bytes. Clipboard lengths use two bytes,
least significant byte first.

## Host → client

| Opcode | Name | Payload |
|---|---|---|
| `$01` | `CLEAR` | `attr`: blank the screen in this attribute |
| `$02` | `RUN` | `row, col, attr, len`, then `len` screen codes |
| `$03` | `FILL` | `row, col, attr, len, char`: one character repeated |
| `$04` | `CURSOR` | `row, col`; `$FF $FF` hides it |
| `$05` | `FRAME` | end of frame, no payload |
| `$06` | `BELL` | no payload |
| `$07` | `PANEL` | `row, colour, len`, then `len` screen codes → 40-column panel |
| `$08` | `HELLO` | `cols, rows` |
| `$09` | `BYE` | `magic`: must be `$5A` to act |
| `$0A` | `GLYPH` | `code`, then 8 bitmap bytes → redefine a VDC character |
| `$0D` | `CAPABILITIES` | feature bits; bit 0 permits framed text paste |
| `$0E` | `PASTE_RESULT` | 0 accepted into host input, 1 rejected |
| `$0B` | `SCROLL` | `top, bot, n`: shift rows `top..bot` by `n & $7F`; bit 7 of `n` set means downward |

`BYE` takes a magic byte because a bare opcode is one bit-flip away from ending
the session, and that happened.

An unrecognised opcode makes the client request a repaint, at most once per
cooldown. Reacting to every stray byte turns one desync into a repaint storm,
since each request costs a full 2KB frame.

### Attributes

The `attr` byte is close to a VDC attribute but not identical, so the client
translates:

```
bit 6  reverse
bit 5  underline
bits 3-0  colour (VDC palette index)
```

The client adds bit 7 (alternate character set) unconditionally, because the
C128 keeps 512 glyph definitions and everything here is encoded against the
lowercase half. Without it, text renders as graphics symbols.

## Client → host

Keystrokes are sent raw as PETSCII, one byte each; translation to terminal
input happens on the host, so the key map can change without reflashing a disk.

`$00` is never a keystroke, so it introduces a control byte:

| Sequence | Meaning |
|---|---|
| `$00 $01` | `RESYNC`: "repaint everything, I may have missed bytes" |
| `$00 $02` | `BYE`: client is shutting down |
| `$00 $03` | `CREDIT`: "I have consumed 64 more bytes" |

### Native text clipboard extension

The native client queries `$00 $04` on each Paste request. Only a host that
returns `$0D $01` is eligible for clipboard transfer; older hosts receive no
clipboard payload. Legacy clients never request this extension and receive no
new opcodes.

| Sequence | Payload and meaning |
|---|---|
| `$00 $04` | Request capabilities |
| `$00 $06 lo hi` | Begin a paste of 1–16384 bytes |
| `$00 $05 count data...` | Append 1–64 literal bytes; control escapes have no meaning inside this counted payload |
| `$00 $07` | End and validate the complete paste; host replies with `PASTE_RESULT` |
| `$00 $08` | Abandon the staged paste without delivery |

The host accepts printable ASCII, tab, CR and LF, normalizes CRLF/CR to LF,
and rejects other controls, ESC, NUL and high bytes. It stages the whole item
before queuing one standard bracketed paste (`ESC[200~...ESC[201~`) in key
order, without a trailing Return. A rejected or incomplete item is not sent
to the PTY. Credits may occur between complete packets. BYE drops a draft.

The native RAM clipboard currently holds up to 15 KiB. The client keeps
draining output and sending credits during a paste. Escape cancels before
End; after End the outcome may already be accepted and is reported as
unconfirmed if the acknowledgement is missing. The 20-second/65535-poll
timeout never retries input automatically. Acceptance confirms the host
input queue, not processing or execution by the terminal application.

### Native shutdown handshake

On F8, the native client sends `$00 $02` once and continues parsing incoming
commands and returning credits. The host stops producing frames, drains the
complete queued stream, and sends `$09 $5A` as its acknowledgement. Credits
in the same packet as the client's BYE are still accepted. The acknowledgement
must follow pending payload bytes; it cannot be inserted into a partial RUN.

The client releases DTR and restores its native state after parsing that BYE.
An empty UART data register alone does not prove the Ultimate's asynchronous
TCP relay has forwarded the client request. A 1200-jiffy deadline (20 seconds)
and a fallback of 65535 polls without a clock change bound the wait. A second
F8 forces return. Host-process exit uses the same host BYE command without
requiring a preceding client request.

The wire bytes remain compatible with the upstream protocol. An older host
that closes without acknowledging F8 will take the client's timeout path.

## Flow control

The host starts its PTY and sends its first frame only after the client announces
itself with `RESYNC`. On the Ultimate, open the native app's serial port before
connecting the Linux bridge; the modem rejects TCP callers while DTR is low.

After that the host stays within a **192-byte window** of what the client has
acknowledged, and the client returns a credit every 64 bytes it consumes.

This is receiver-driven for a specific reason: neither VICE's RS232 emulation nor
the Ultimate's TCP-backed modem paces to the ACIA's nominal baud. Metering the
sender by wall clock does nothing at all: at 38400 and at 1200 bytes/sec the
client dropped *exactly* the same bytes. Only the C128 knows when a byte has
actually been applied.

**A resync must not restore the credit window.** A resync means the client lost
its place, not that its ring is empty; handing back a full window on top of
unread bytes is how the ring overruns, which produces more stray bytes and more
resync requests. Removing one line that did this took drops from 164 to 0.

## Framing and the differ

The host runs a full terminal emulator (pyte), so it always has a complete 80×25
grid of `(screen code, attr)`. Each frame it diffs against what the client is
known to be showing and emits only changed cell runs.

Runs are split on attribute changes, and a stretch of 8 or more identical
characters becomes a `FILL`. Changed spans separated by a gap smaller than the
5-byte run header are merged, since resending a few clean cells is cheaper than
a second header.

An unchanged screen emits a bare `FRAME` byte, which the host suppresses, so an
idle terminal costs nothing.

## Scrolling

Streaming output used to be the worst case: every line of new text shifted the
whole transcript, and the differ resent every shifted row: most of a repaint,
frame after frame. `SCROLL` moves the rows in place instead.

The differ looks for a row shift that explains the frame, then encodes the
frame **both** ways (plain diff, and `SCROLL` plus a diff against the shifted
screen) and sends whichever is smaller. Detection therefore only has to be
good, not perfect: a bad guess costs bytes, never pixels.

Semantics, identical on every client and in `protocol.apply_scroll` (the
reference model the 6502 must match):

- Rows `top..bot` inclusive shift by `n` rows, upward unless bit 7 of the
  count byte is set.
- The `n` rows exposed at the trailing edge **keep their old content**: a
  block copy does not erase its source. The differ models exactly that and
  repaints them in the same frame.
- Bounds that make no sense (`bot` off screen, `n` of 0, `n` larger than the
  region) are ignored by the client, and are a no-op in the model.

On the C128 the shift is the VDC's own block copy (register 24 bit 7, source
in R32/33, count in R30), the same mechanism the KERNAL scrolls with, so the
CPU only issues register writes, ~80 per one-line scroll of both planes. On
the C64 it is a software copy, 80 bytes per row, still far cheaper than
resending the rows over the wire. Measured on a 30-frame scroll-through of an
80×25 screen: 14,010 bytes plain, 696 bytes with `SCROLL`; 3.65 s of wire
time collapsed to 0.18 s.

## Sizes

| | |
|---|---|
| Full repaint | ~2KB, about 0.5s at 38400 baud |
| Typical streaming frame | under 100 bytes |
| One-line scroll of the whole screen | 4 bytes + the new row |
| Glyph upload at startup | 21 glyphs × 10 bytes |
| Status panel, idle | ~82 bytes/sec, 2.1% of the link |
| Idle terminal | 0 bytes |
