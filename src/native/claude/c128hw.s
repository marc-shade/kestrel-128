; Native Kestrel adaptation; upstream MIT notice in apps/claude/LICENSE.
; ---------------------------------------------------------------------------
; claude-c128 client: VDC screen writes and 6551 ACIA receive.
;
; Both are performance-critical, so they live in assembly and take their
; arguments through fixed zero-page-free globals rather than the C stack.
;
; The VDC is a separate chip with private RAM reached through a two-register
; window at $D600/$D601: write a register number to $D600, wait for bit 7 of
; $D600 to go high, then read or write $D601. Register 31 is a data port that
; auto-increments the update address, so a run of cells costs one address
; setup plus one guarded store per byte.
;
; The ACIA has a one-byte receive buffer. At 38400 baud a byte lands every
; ~260 cycles, which the KERNAL's own interrupts would routinely overrun, so
; reception is driven from NMI (unmaskable) into a 256-byte ring buffer whose
; head and tail wrap for free as single bytes.
; ---------------------------------------------------------------------------

        .export _scr_init, _scr_run, _scr_fill, _scr_clear, _scr_place_cursor
        .export _scr_scroll
        .export _acia_open, _acia_get, _acia_avail, _acia_put, _acia_shutdown
        .export _kb_get, _kbCount
        .export _scr_mirror, _mirrorBuf, _lastAttr, _scr_setglyph
        .export _scrRow, _scrCol, _scrAttr, _scrLen, _scrChar, _scrBuf
        ; Link diagnostics: exported so the emulator harness and the on-screen
        ; status panel can see whether bytes are actually arriving.
        .export _rxHead, _rxTail, _rxCount, _nmiCount, _rxOverruns, _rxDropped
        .import _tm_begin, _tm_end, _tm_run, _tm_fill, _tm_clear, _tm_scroll
        .import _tm_cursor, _tm_glyph
        .import _tm_read, _tm_live
        .import _gui_vdc_owned, _gui_vdc_end, _gui_recovery
        .import _gui_cursor_row, _gui_cursor_col
        .export _scr_sync, videoPhase, videoFault
        .export _mirrorError
        .include "../api.inc"

VDC_ADDR        = $D600         ; register select / status
VDC_DATA        = $D601         ; register data

VDC_R_HSTART    = 18            ; update address high
VDC_R_LSTART    = 19            ; update address low
VDC_R_VSCROLL   = 24            ; bit 7 selects block copy (1) or fill (0)
VDC_R_COUNT     = 30            ; block word count: triggers the block operation
VDC_R_CHARBASE  = 28            ; bits 7-5 = character definition base address
VDC_R_DATA      = 31            ; data port, auto-incrementing
VDC_R_BLKHI     = 32            ; block copy source address high
VDC_R_BLKLO     = 33            ; block copy source address low

; Largest block fill issued at once. The count register is 8-bit, and keeping
; each burst short bounds how long the main loop goes without draining the
; receive ring.
FILL_CHUNK      = 250

SCREEN_BASE     = $0000         ; VDC RAM: character cells
ATTR_BASE       = $0800         ; VDC RAM: attribute cells
COLS            = 80

ACIA_DATA       = $DE00
ACIA_STATUS     = $DE01
ACIA_CMD        = $DE02
ACIA_CTRL       = $DE03

; SwiftLink runs a doubled crystal, so the 6551 baud codes all double:
;   $1C = 9600   $1D = 14400   $1E = 19200   $1F = 38400   (8N1, internal clock)
; The binding limit is not the wire, it is how fast the C128 can parse a frame
; and push it through the VDC at 1MHz. Measured in VICE: 38400 overruns the
; receive ring during a full repaint; 19200 does not.
ACIA_CTRL_VAL   = $1F
; DTR on, receiver interrupt enabled, RTS asserted, transmit interrupt off.
ACIA_CMD_VAL    = $09

NMI_VECTOR      = $0318
; The C128 ROM NMI stub at $FF05 pushes A, X, Y *and* the MMU configuration
; register before dispatching through $0318, then banks in ROM. That differs
; from the C64, where nothing is saved. A handler that pushes its own registers
; and returns with a bare RTI therefore unbalances the stack and returns to a
; garbage address. $FF33 is the KERNAL's matching unwind:
;   PLA / STA $FF00 / PLA / TAY / PLA / TAX / PLA / RTI
NMI_EXIT        = $FF33

        .export _native_video_begin, _native_video_end, _native_quit, _native_border
        .export savedVdc, serialOwned, nmiHandler
        .bss
_native_quit: .res 1
_native_border: .res 1
savedScreen: .res 1
savedKeys: .res 256
savedVdc: .res 37
videoPhase: .res 1
videoFault: .res 1
videoStack: .res 1
videoWait: .res 2
syncRow: .res 1
syncPlane: .res 1
savedControl: .res 1
savedCommand: .res 1
serialOwned: .res 1
_scrRow:        .res 1
_scrCol:        .res 1
_scrAttr:       .res 1
_scrLen:        .res 1
_scrChar:       .res 1
_scrBuf:        .res 256

offsetLo:       .res 1
offsetHi:       .res 1
fillByte:       .res 1
fillCount:      .res 1
fillLeft:       .res 2
oldNmi:         .res 2
oldGate:        .res 2
scrTop:         .res 1          ; scroll: first row of the region
scrBot:         .res 1          ; scroll: last row of the region
scrN:           .res 1          ; scroll: rows to shift by
srcRow:         .res 1
dstRow:         .res 1
rowsLeft:       .res 1
planeHi:        .res 1          ; high byte of the plane being copied
_rxHead:        .res 1
_rxTail:        .res 1
_rxCount:       .res 2          ; bytes accepted from the ACIA
_nmiCount:      .res 2          ; NMIs seen, ours or not
_rxOverruns:    .res 1          ; ACIA reported a dropped byte
_rxDropped:     .res 1          ; receive ring was full; byte discarded
_kbCount:       .res 2          ; keys read from the keyboard, for diagnostics

; The VDC keeps its screen in private RAM that the cartridge bus cannot reach,
; so a host debugging over the network is blind to the 80-column display. The
; C128 itself can read it, so it copies a plane here on request and the host
; reads it back out of ordinary memory.
_lastAttr:      .res 1          ; last attribute byte scr_run wrote
_mirrorBuf:     .res 2048
_mirrorError:   .res 1

rxHead          = _rxHead
rxTail          = _rxTail

; 256 contiguous bytes indexed by a byte, so head/tail wrap on their own.
; Page alignment would only save the indexed page-crossing cycle, and the
; c128 config cannot guarantee it for BSS, so it is not requested.
rxBuf:          .res 256

        .code

; ---------------------------------------------------------------------------
; scr_reg_write: A = value, X = register number
; ---------------------------------------------------------------------------
scrRegWrite:
        stx VDC_ADDR
        jsr scrWait
        sta VDC_DATA
        rts

; Every foreground hardware entry installs an unwind boundary. NMI only
; queues serial bytes and cannot alter these counters or the VDC selector.
scrGate:
        tsx
        inx
        inx
        stx videoStack
        lda videoFault
        beq @ready
        ldx videoStack
        txs
        sec
@ready:
        rts
scrWait:
        pha
        lda #0
        sta videoWait
        sta videoWait+1
@poll: bit VDC_ADDR
        bmi @ready
        dec videoWait
        bne @poll
        dec videoWait+1
        bne @poll
        ldx videoStack
        txs
        lda #1
        sta _native_quit
        sta _gui_recovery
        lda #N_PLATFORM
        sta videoFault
        sec
        rts
@ready:pla
        clc
        rts

; ---------------------------------------------------------------------------
; scrSetAddr: point the VDC update address at offsetHi/offsetLo
; ---------------------------------------------------------------------------
scrSetAddr:
        lda offsetHi
        ldx #VDC_R_HSTART
        jsr scrRegWrite
        lda offsetLo
        ldx #VDC_R_LSTART
        jsr scrRegWrite
        ldx #VDC_R_DATA         ; leave the data port selected
        stx VDC_ADDR
        ; scrRegWrite waits *before* each store, so on return the write to the
        ; address-low register may still be in flight. Without this wait the
        ; very first data write can be issued against the previous update
        ; address, which lost cell 0 of every full-screen clear.
@settle:
        jsr scrWait
        rts

; ---------------------------------------------------------------------------
; scrPut: A = byte -> data port (address auto-increments)
; ---------------------------------------------------------------------------
scrPut:
        jsr scrWait
        sta VDC_DATA
        rts

; ---------------------------------------------------------------------------
; attrToVdc: protocol attribute -> VDC attribute byte.
;
; The VDC attribute is  bit7 alternate charset | bit6 reverse | bit5 underline |
; bit4 blink | bits3-0 colour.
;
; Bit 7 must be set: the C128 keeps 512 character definitions at the base in R28,
; the first 256 being the uppercase/graphics set and the second 256 the
; lowercase set. Everything the bridge sends is encoded as lowercase-set screen
; codes, so without this bit the VDC draws them from the wrong half and text
; comes out as graphics symbols.
;
; Underline and reverse are carried through unchanged; the protocol already
; uses the VDC's own bit positions for them.
; ---------------------------------------------------------------------------
attrToVdc:
        and #$6F                ; colour (3-0), underline (5), reverse (6)
        ora #$80                ; select the lowercase character set
        rts

; ---------------------------------------------------------------------------
; scrRegRead: X = register number -> A
; ---------------------------------------------------------------------------
scrRegRead:
        stx VDC_ADDR
        jsr scrWait
        lda VDC_DATA
        rts

; ---------------------------------------------------------------------------
; fillChunk: A = byte, X = count (1..255), at the current update address.
;
; Uses the VDC's block-fill: write the byte once through the data port, then
; write the remaining count to register 30 and the VDC repeats it at memory
; speed. Writing 2000 cells one at a time takes ~80ms at 1MHz, long enough for
; a 38400-baud sender to overrun a 256-byte receive ring; this takes a fraction
; of that.
; ---------------------------------------------------------------------------
fillChunk:
        sta fillByte
        stx fillCount
        ldy #VDC_R_DATA
        sty VDC_ADDR
@w1:    jsr scrWait
        lda fillByte
        sta VDC_DATA            ; first copy, address auto-increments
        ldx fillCount
        dex
        beq @done
        ldy #VDC_R_COUNT
        sty VDC_ADDR
@w2:    jsr scrWait
        txa
        sta VDC_DATA            ; block-fill the remainder
@done:  rts

; ---------------------------------------------------------------------------
; fillSpan: fill fillLeft bytes with A from the current update address,
;           in FILL_CHUNK-sized bursts.
; ---------------------------------------------------------------------------
fillSpan:
        sta fillByte
@loop:  lda fillLeft
        ora fillLeft+1
        beq @done
        lda fillLeft+1
        bne @full               ; more than 255 left
        lda fillLeft
        cmp #FILL_CHUNK
        bcc @last
@full:  ldx #FILL_CHUNK
        lda fillLeft
        sec
        sbc #FILL_CHUNK
        sta fillLeft
        lda fillLeft+1
        sbc #0
        sta fillLeft+1
        lda fillByte
        jsr fillChunk
        jmp @loop
@last:  ldx fillLeft
        lda #0
        sta fillLeft
        sta fillLeft+1
        lda fillByte
        jsr fillChunk
@done:  rts

; ---------------------------------------------------------------------------
; calcOffset: offset = scrRow * 80 + scrCol, into offsetHi/offsetLo
; row*80 == row*64 + row*16, which is cheaper than a multiply loop.
; ---------------------------------------------------------------------------
calcOffset:
        lda #0
        sta offsetHi
        lda _scrRow
        asl a                   ; row*2
        asl a                   ; row*4
        rol offsetHi
        asl a                   ; row*8
        rol offsetHi
        asl a                   ; row*16
        rol offsetHi
        sta offsetLo            ; offset = row*16
        lda offsetHi
        pha
        lda offsetLo
        pha                     ; save row*16
        asl a                   ; row*32
        rol offsetHi
        asl a                   ; row*64
        rol offsetHi
        sta offsetLo
        pla
        clc
        adc offsetLo            ; row*64 + row*16 = row*80
        sta offsetLo
        pla
        adc offsetHi
        sta offsetHi
        lda offsetLo
        clc
        adc _scrCol
        sta offsetLo
        lda offsetHi
        adc #0
        sta offsetHi
        rts

; ---------------------------------------------------------------------------
; _scr_run: write scrLen screen codes from scrBuf at (scrRow,scrCol),
;           then the same span in attribute RAM with scrAttr.
; ---------------------------------------------------------------------------
_scr_run:
        jsr _tm_run
        jsr scrGate
        lda _gui_vdc_owned
        beq @hardware
        rts
@hardware:
        jsr clipSpan
        bcc @valid
        rts
@valid:
        lda _scrLen
        bne @go
        rts
@go:    jsr calcOffset
        jsr scrSetAddr
        ldy #0
@chars: lda _scrBuf,y
        jsr scrPut
        iny
        cpy _scrLen
        bne @chars

        jsr calcOffset          ; same span in attribute RAM
        lda offsetHi
        clc
        adc #>ATTR_BASE
        sta offsetHi
        jsr scrSetAddr
        lda _scrAttr
        jsr attrToVdc
        sta _lastAttr           ; the VDC-format byte we actually store
        ldy #0
@attrs: lda _lastAttr
        jsr scrPut
        iny
        cpy _scrLen
        bne @attrs
        rts

; ---------------------------------------------------------------------------
; _scr_fill: scrLen copies of scrChar at (scrRow,scrCol) with scrAttr
; ---------------------------------------------------------------------------
_scr_fill:
        jsr _tm_fill
        jsr scrGate
        lda _gui_vdc_owned
        beq @hardware
        rts
@hardware:
        jsr clipSpan
        bcc @valid
        rts
@valid:
        lda _scrLen
        bne @go
        rts
@go:    jsr calcOffset
        jsr scrSetAddr
        ldx _scrLen
        lda _scrChar
        jsr fillChunk

        jsr calcOffset
        lda offsetHi
        clc
        adc #>ATTR_BASE
        sta offsetHi
        jsr scrSetAddr
        ldx _scrLen
        lda _scrAttr
        jsr attrToVdc
        jsr fillChunk
        rts

; ---------------------------------------------------------------------------
; _scr_clear: blank all 2000 cells and set all 2000 attributes, using the
; VDC block fill rather than a per-cell loop.
; ---------------------------------------------------------------------------
_scr_clear:
        jsr _tm_clear
        jsr scrGate
        lda _gui_vdc_owned
        beq @hardware
        rts
@hardware:
        lda #0
        sta offsetLo
        sta offsetHi
        jsr scrSetAddr
        lda #<2000
        sta fillLeft
        lda #>2000
        sta fillLeft+1
        lda #$20
        jsr fillSpan

        lda #<SCREEN_BASE
        sta offsetLo
        lda #>ATTR_BASE
        sta offsetHi
        jsr scrSetAddr
        lda #<2000
        sta fillLeft
        lda #>2000
        sta fillLeft+1
        lda _scrAttr
        jsr attrToVdc
        jsr fillSpan
        rts

; ---------------------------------------------------------------------------
; _scr_scroll: shift rows scrRow..scrCol (top..bottom, inclusive) by the count
; in scrLen, whose bit 7 set means downward. Uses the VDC's block copy - the
; same mechanism the C128 KERNAL scrolls its own screen with - so the CPU only
; issues register writes and the VDC moves the bytes at memory speed. Both
; planes move: characters at SCREEN_BASE and attributes at ATTR_BASE.
;
; The copy is row by row (80 bytes per operation) rather than one large block:
; source and destination rows never overlap within an operation, so walking
; the rows in the safe order (ascending for up, descending for down) makes
; direction handling trivial and leaves nothing depending on how the VDC's
; internal pointers advance between chained counts.
;
; The n rows exposed at the trailing edge are NOT cleared: a block copy does
; not erase its source, the bridge models exactly that, and its same-frame
; diff repaints them. Bounds that make no sense are ignored - a corrupted
; scroll can smear the picture no worse than a corrupted run, and HELP or the
; next full repaint recovers it.
; ---------------------------------------------------------------------------
_scr_scroll:
        jsr _tm_scroll
        jsr scrGate
        lda _gui_vdc_owned
        beq @hardware
        rts
@hardware:
        lda _scrRow
        sta scrTop
        lda _scrCol
        sta scrBot
        cmp #25
        bcs @out                ; bottom row off screen
        lda _scrLen
        and #$7F
        sta scrN
        beq @out                ; a shift of zero rows
        lda scrBot
        sec
        sbc scrTop
        bcc @out                ; top below bottom
        cmp scrN
        bcc @out                ; shift larger than the region
        sec
        sbc scrN
        clc
        adc #1
        sta rowsLeft            ; rows that actually move: bot-top+1-n

        ; Block COPY mode on (R24 bit 7), preserving the scroll bits below it.
        ldx #VDC_R_VSCROLL
        jsr scrRegRead
        ora #$80
        ldx #VDC_R_VSCROLL
        jsr scrRegWrite

        lda _scrLen
        bmi @down
        ; Up: destination rows ascend from the top, source n rows below.
        lda scrTop
        sta dstRow
        clc
        adc scrN
        sta srcRow
@uploop:
        jsr copyRowPlanes
        inc srcRow
        inc dstRow
        dec rowsLeft
        bne @uploop
        beq @restore
@down:
        ; Down: destination rows descend from the bottom, source n rows above.
        lda scrBot
        sta dstRow
        sec
        sbc scrN
        sta srcRow
@dnloop:
        jsr copyRowPlanes
        dec srcRow
        dec dstRow
        dec rowsLeft
        bne @dnloop
@restore:
        ; Back to block FILL mode: every fill in this file depends on it.
        ldx #VDC_R_VSCROLL
        jsr scrRegRead
        and #$7F
        ldx #VDC_R_VSCROLL
        jsr scrRegWrite
@out:   rts

; ---------------------------------------------------------------------------
; copyRowPlanes: copy row srcRow to row dstRow in both VDC planes.
; ---------------------------------------------------------------------------
copyRowPlanes:
        lda #>SCREEN_BASE
        jsr copyRow80
        lda #>ATTR_BASE
        jsr copyRow80
        rts

; ---------------------------------------------------------------------------
; copyRow80: one 80-byte row, srcRow -> dstRow, in the plane whose base high
; byte is in A. Destination goes to the update address (R18/19), source to the
; block start (R32/33); writing the count to R30 performs the copy. Requires
; R24 bit 7 set. Clobbers _scrRow/_scrCol as calcOffset scratch - _scr_scroll
; has already copied its arguments out of them.
; ---------------------------------------------------------------------------
copyRow80:
        sta planeHi
        lda dstRow
        sta _scrRow
        lda #0
        sta _scrCol
        jsr calcOffset
        lda offsetHi
        clc
        adc planeHi
        ldx #VDC_R_HSTART
        jsr scrRegWrite
        lda offsetLo
        ldx #VDC_R_LSTART
        jsr scrRegWrite

        lda srcRow
        sta _scrRow
        jsr calcOffset
        lda offsetHi
        clc
        adc planeHi
        ldx #VDC_R_BLKHI
        jsr scrRegWrite
        lda offsetLo
        ldx #VDC_R_BLKLO
        jsr scrRegWrite

        lda #COLS
        ldx #VDC_R_COUNT
        jsr scrRegWrite
        rts

; ---------------------------------------------------------------------------
; _scr_place_cursor: VDC registers 14/15 hold the cursor position
; ---------------------------------------------------------------------------
_scr_place_cursor:
        jsr _tm_cursor
        jsr scrGate
        lda _gui_vdc_owned
        beq @hardware
        rts
@hardware:
        lda _scrRow
        cmp #25
        bcs @hide
        lda _scrCol
        cmp #80
        bcs @hide
        jsr calcOffset
        lda offsetHi
        ldx #14
        jsr scrRegWrite
        lda offsetLo
        ldx #15
        jsr scrRegWrite
        lda #$60                ; blinking cursor, first raster zero
        bne @mode
@hide:  lda #$20                ; documented VDC cursor-off mode
@mode:  ldx #10
        jmp scrRegWrite

; ---------------------------------------------------------------------------
; _scr_init: leave the KERNAL's 80-column setup in place and just clear.
; ---------------------------------------------------------------------------
_scr_init:
        jsr scrGate
        ; Register 24 bit 7 chooses block COPY (1) or block FILL (0). The
        ; KERNAL may leave either set, and every fill below depends on it.
        ldx #VDC_R_VSCROLL
        jsr scrRegRead
        and #$7F
        ldx #VDC_R_VSCROLL
        jsr scrRegWrite
        jsr _scr_clear
        rts

; ---------------------------------------------------------------------------
; _acia_init: configure the ACIA and hook NMI
; ---------------------------------------------------------------------------
_acia_open:
        ; Leave an active serial owner untouched. Floating $ff/$ff is absent,
        ; and so is any read that changes: with no ACIA the I/O1 bus returns
        ; whatever the VIC last fetched, which can look like an active port.
        lda ACIA_CTRL
        sta savedControl
        lda ACIA_CMD
        sta savedCommand
        and savedControl
        cmp #$ff
        beq @floating
        ldx #15
@stable:
        lda ACIA_CTRL
        cmp savedControl
        bne @floating
        lda ACIA_CMD
        cmp savedCommand
        bne @floating
        dex
        bpl @stable
        bmi @steady             ; always: X wrapped to $ff
@floating:
        jmp @absent
@steady:
        lda savedCommand
        and #1
        bne @busy
        lda #ACIA_CTRL_VAL
        sta ACIA_CTRL
        cmp ACIA_CTRL
        bne @probe_failed
        php
        sei
        lda #0
        sta rxHead
        sta rxTail
        sta _native_quit
        sta ACIA_CMD            ; interrupt source disabled while installing
        lda ACIA_STATUS
        lda ACIA_DATA
        lda NMI_VECTOR
        sta oldNmi
        lda NMI_VECTOR+1
        sta oldNmi+1
        lda $3d3e
        sta oldGate
        lda $3d3f
        sta oldGate+1
        lda #<nmiHandler
        sta $3d3e
        lda #>nmiHandler
        sta $3d3f
        lda #<$1bf0
        sta NMI_VECTOR
        lda #>$1bf0
        sta NMI_VECTOR+1
        lda #1
        sta serialOwned
        lda #ACIA_CMD_VAL
        sta ACIA_CMD
        cmp ACIA_CMD
        bne @command_failed
        plp
        lda #0
        tax
        rts
@command_failed:
        plp
        jsr _acia_shutdown
        jmp @absent
@probe_failed:
        lda savedControl
        sta ACIA_CTRL
@absent:
        lda #2
        ldx #0
        rts
@busy:  lda #1
        ldx #0
        rts

_acia_shutdown:
        lda serialOwned
        beq @out
        ; TDRE means the data register is empty, not that its final byte has
        ; left the shift register. Drain any final credits before releasing
        ; the port. main.c separately waits for the host's BYE acknowledgement;
        ; this short UART delay cannot drain the Ultimate's TCP relay.
        ldx #0
        ldy #0
@drain: lda ACIA_STATUS
        and #$10
        bne @tail
        dex
        bne @drain
        dey
        bne @drain             ; bounded even if the cartridge stops responding
@tail:  ldx #120               ; > one 38400-baud character at the native 1 MHz
@bits:  dex
        bne @bits
        php
        sei
        lda #0                  ; drop DTR; no receiver NMI can retain app code
        sta ACIA_CMD
        lda ACIA_STATUS
        lda ACIA_DATA
        lda oldNmi
        sta NMI_VECTOR
        lda oldNmi+1
        sta NMI_VECTOR+1
        lda oldGate
        sta $3d3e
        lda oldGate+1
        sta $3d3f
        lda savedControl
        sta ACIA_CTRL
        lda savedCommand        ; original idle command has DTR clear
        sta ACIA_CMD
        lda #0
        sta serialOwned
        plp
@out:   rts

; ---------------------------------------------------------------------------
; nmiHandler: entered from the ROM stub at $FF05, which has already saved
; A, X, Y and the MMU config and banked in ROM. So registers are free to
; clobber and we must leave through NMI_EXIT, never a bare RTI.
;
; A non-serial NMI requests foreground teardown, which restores the previous
; vector and app resources before returning to the native desktop.
; ---------------------------------------------------------------------------
nmiHandler:
        inc _nmiCount
        bne @nooc1
        inc _nmiCount+1
@nooc1:
        lda ACIA_STATUS         ; reading clears the ACIA interrupt flag
        tax                     ; keep the full status for the overrun check
        and #$08                ; receiver data register full?
        beq @chain
        txa
        and #$04                ; overrun: a byte was lost before we read it
        beq @store
        inc _rxOverruns
@store:
        lda ACIA_DATA           ; reading clears RDRF and re-arms the NMI line
        ldx rxHead
        inx
        cpx rxTail              ; would this write lap the unread tail?
        beq @ringfull
        dex
        sta rxBuf,x
        inx
        stx rxHead              ; 256-byte ring: wraps on its own
        inc _rxCount
        bne @nooc2
        inc _rxCount+1
@nooc2:
        jmp NMI_EXIT
@ringfull:
        ; Dropping here would corrupt the screen silently, so it is counted.
        ; The byte is discarded rather than overwriting unread data; the client
        ; can recover the whole picture with a resync.
        inc _rxDropped
        jmp NMI_EXIT
@chain:
        lda $dd0d               ; acknowledge non-serial CIA2/RESTORE event
        lda #1                  ; foreground teardown instead of BASIC warm start
        sta _native_quit
        jmp NMI_EXIT

; ---------------------------------------------------------------------------
; _acia_avail: A = 1 when a byte is waiting
; ---------------------------------------------------------------------------
_acia_avail:
        ldx #0
        lda rxHead
        cmp rxTail
        beq @empty
        lda #1
        rts
@empty: lda #0
        rts

; ---------------------------------------------------------------------------
; _acia_get: A = next byte (call only when _acia_avail returned 1)
; ---------------------------------------------------------------------------
_acia_get:
        ldx #0
        ldy rxTail
        lda rxBuf,y
        iny
        sty rxTail
        rts

; ---------------------------------------------------------------------------
; _acia_put: transmit A, waiting for the transmitter to drain
; ---------------------------------------------------------------------------
_acia_put:
        pha
        lda _native_quit
        bne @abandon
        ldx #0
        ldy #0
@wait:  lda ACIA_STATUS
        and #$10
        bne @send
        dex
        bne @wait
        dey
        bne @wait
        lda #2                  ; bounded timeout; foreground always regains control
        sta _native_quit
@abandon:
        pla
        rts
@send:  pla
        sta ACIA_DATA
        rts

; ---------------------------------------------------------------------------
; _kb_get: next key in PETSCII, or 0 if none.
;
; Calls the KERNAL's GETIN ($FFE4) rather than cc65's kbhit()/cgetc(). GETIN is
; the documented non-blocking read and it takes the C128's keyboard buffer and
; its count ($034A/$D0) into account itself, which conio did not appear to do
; here: keys placed in that buffer were never returned, so nothing was ever
; transmitted while the receive direction worked perfectly.
; ---------------------------------------------------------------------------
_kb_get:
        jsr _gui_poll           ; bounded drawing and mouse actions, no key count
        cmp #0
        bne @mouse
        lda #1
        sta $3d12               ; each poll follows all effects of the previous key
        jsr $1c3b               ; native N_KEYIN and shared event accounting
        cmp #0
        beq @none
        inc _kbCount
        bne @none
        inc _kbCount+1
@none:  jsr _gui_key            ; local controls only while explicitly selected
@mouse: ldx #0
        rts

; ---------------------------------------------------------------------------
; _scr_mirror: copy one VDC plane into _mirrorBuf.
;   _scrChar = 0 -> character cells at VDC $0000
;   _scrChar = 1 -> attribute cells at VDC $0800
; Copies 2048 bytes, which covers the 2000 used by an 80x25 screen.
; ---------------------------------------------------------------------------
        .importzp ptr1

; _scrChar = 2 additionally means "dump VDC registers 0..36 into mirrorBuf",
; which is the only way for a host on the far side of the cartridge bus to see
; how the VDC is actually configured (where the screen and attribute RAM live,
; and whether attributes are enabled at all).
_scr_mirror:
        lda #N_PLATFORM
        sta _mirrorError
        lda _gui_vdc_owned
        beq @hardware
        lda _scrChar
        cmp #2
        bcs @refused
        jmp scrMirrorModel
@refused:
        rts
@hardware:
        jsr scrGate
        lda #<_mirrorBuf
        sta ptr1
        lda #>_mirrorBuf
        sta ptr1+1
        lda _scrChar
        cmp #3
        bne @notaddr
        ; Mode 3: copy 2048 bytes from the arbitrary VDC address in
        ; _scrRow (high) / _scrCol (low). Lets the host read back character
        ; definitions, which live in VDC RAM and are otherwise invisible.
        lda _scrRow
        sta offsetHi
        lda _scrCol
        sta offsetLo
        jmp @copy
@notaddr:
        cmp #2
        bne @plane
        ldx #0
@reg:   txa
        pha
        jsr scrRegRead          ; X = register number -> A
        sta _mirrorBuf,x
        pla
        tax
        inx
        cpx #37
        bne @reg
        lda #0
        sta _mirrorError
        rts
@plane:
        lda #0
        sta offsetLo
        ldx _scrChar
        beq @chars
        lda #>ATTR_BASE
        .byte $2C                       ; skip the next two bytes (BIT abs)
@chars: lda #>SCREEN_BASE
        sta offsetHi
@copy:
        jsr scrSetAddr                  ; leaves the data port selected
        ; The VDC data port is pipelined: the first read after setting the
        ; update address returns the previously latched byte, not the one at
        ; the new address. Throw it away, then re-point and read for real.
@pre:   jsr scrWait
        lda VDC_DATA
        jsr scrSetAddr
        ldx #8                          ; 8 pages = 2048 bytes
@page:  ldy #0
@byte:  jsr scrWait
        lda VDC_DATA
        sta (ptr1),y
        iny
        bne @byte
        inc ptr1+1
        dex
        bne @page
        lda #0
        sta _mirrorError
        rts

scrMirrorModel:
        lda #<_mirrorBuf
        sta ptr1
        lda #>_mirrorBuf
        sta ptr1+1
        lda #0
        sta syncRow
        ldx #47
@pad:  sta _mirrorBuf+2000,x
        dex
        bpl @pad
@row:  lda syncRow
        ldx _scrChar
        jsr _tm_read
        bcs @return
        ldy #0
@copy: lda N_BUFFER,y
        sta (ptr1),y
        iny
        cpy #80
        bne @copy
        lda ptr1
        clc
        adc #80
        sta ptr1
        bcc @next
        inc ptr1+1
@next: inc syncRow
        lda syncRow
        cmp #25
        bne @row
        lda #0
        sta _mirrorError
@return:rts

; ---------------------------------------------------------------------------
; _scr_setglyph: redefine one character in the lowercase bank.
;   _scrChar = character code, _scrBuf[0..7] = the 8 pixel rows.
;
; The VDC holds its character definitions in its own RAM at the base named by
; R28 bits 7-5, 16 bytes per definition. The first 256 are the uppercase and
; graphics set, the second 256 the lowercase set we render into, so the target
; is base + $1000 + code*16. Rows 8-15 are outside an 8-pixel character box and
; are cleared so a previous definition cannot bleed through.
; ---------------------------------------------------------------------------
_scr_setglyph:
        jsr _tm_glyph
        jsr scrGate
        lda _gui_vdc_owned
        beq @hardware
        rts
@hardware:
        ldx #VDC_R_CHARBASE
        jsr scrRegRead
        ; The base is (bits 7-5) << 13, so its high byte is exactly those bits
        ; left in place: (R28 & $E0) >> 5 << 5.
        and #$E0
        clc
        adc #$10                ; + $1000 -> the lowercase bank
        sta offsetHi            ; high byte of the lowercase bank base

        ; offset = base + code*16, computed as a separate 16-bit product so the
        ; base is not shifted along with the code.
        lda _scrChar
        asl a
        asl a
        asl a
        asl a
        sta offsetLo            ; low byte  = (code << 4) & $F0
        lda _scrChar
        lsr a
        lsr a
        lsr a
        lsr a                   ; high byte = code >> 4
        clc
        adc offsetHi
        sta offsetHi

        jsr scrSetAddr
        ldy #0
@rows:  lda _scrBuf,y
        jsr scrPut
        iny
        cpy #8
        bne @rows
        lda #0                  ; clear the unused rows 8-15
@blank: jsr scrPut
        lda #0
        iny
        cpy #16
        bne @blank
        rts

; Clip untrusted runs before calculating a VDC address. Still consume the
; complete wire payload in C, even when only a prefix fits in this row.
clipSpan:
        lda _scrRow
        cmp #25
        bcs @bad
        lda _scrCol
        cmp #80
        bcs @bad
        lda #80
        sec
        sbc _scrCol
        cmp _scrLen
        bcs @fits
        sta _scrLen
@fits:  lda _scrLen
        beq @bad
        clc
        rts
@bad:   sec
        rts

_native_video_begin:
        jsr sf_open
        bcc @font_owned
        rts
@font_owned:
        jsr scrGate
        ; Native GETIN expands the ROM's programmable keys. Deliver one
        ; protocol key each; in particular stock F8 expands to MONITOR+CR.
        php
        sei
        ldx #0
@keys: lda $1000,x
        sta savedKeys,x
        inx
        bne @keys
        ldx #9
@key:  lda #1
        sta $1000,x
        lda nativeKeys,x
        sta $100a,x
        dex
        bpl @key
        lda #0
        sta $d1
        sta $d2
        plp
        lda $d7
        sta savedScreen
        lda $d020
        sta _native_border
        lda #1
        sta videoPhase
        ldx #0
@save:  cpx #31                  ; never read the data port as a register
        beq @next
        jsr scrRegRead
        sta savedVdc,x
@next:  inx
        cpx #37
        bne @save
        lda #2
        sta videoPhase
        lda savedScreen
        bpl @forty
        jsr $ff5f
@forty: lda #$93
        jsr $ffd2
        jsr fontAddress
        lda offsetHi
        sta _gui_font_hi
        jsr scrSetAddr
        ; Prime the VDC read latch, then re-point as in upstream scr_mirror.
@prime: jsr scrWait
        lda VDC_DATA
        jsr scrSetAddr
        lda #0
        sta sf_chunk
@chunk:
        lda #<N_BUFFER
        sta ptr1
        lda #>N_BUFFER
        sta ptr1+1
        ldx #2
@page:  ldy #0
@read:  jsr scrWait
        lda VDC_DATA
        sta (ptr1),y
        iny
        bne @read
        inc ptr1+1
        dex
        bne @page
        lda sf_chunk
        jsr sf_write
        bcc @saved
        ldx #0
        rts
@saved:inc sf_chunk
        inc sf_chunk
        lda sf_chunk
        cmp #16
        bne @chunk
        lda #3
        sta videoPhase
        lda #0
        ldx #12
        jsr scrRegWrite
        inx
        jsr scrRegWrite
        ldx #21
        jsr scrRegWrite
        ldx #27
        jsr scrRegWrite
        lda #8
        ldx #20
        jsr scrRegWrite
        lda savedVdc+25
        and #$7f
        ora #$40
        ldx #25
        jsr scrRegWrite
        lda #0
        ldx #26
        jsr scrRegWrite
        jsr _tm_begin
        lda #0
        tax
        clc
        rts

fontAddress:
        lda #0
        sta offsetLo
        lda savedVdc+28
        and #$e0
        clc
        adc #$10
        sta offsetHi
        rts

_native_video_end:
        jsr _acia_shutdown
        jsr _gui_vdc_end
        bcc @display_closed
        rts                    ; provider recovery retains all callbacks/buffers
@display_closed:
        lda #0
        sta videoFault
        jsr scrGate
        lda videoPhase
        cmp #3
        bcc @font_restored
        jsr fontAddress
        jsr scrSetAddr
        lda #0
        sta sf_chunk
@chunk:lda sf_chunk
        jsr sf_read
        bcc @loaded
        ldx #0
        rts
@loaded:
        lda #<N_BUFFER
        sta ptr1
        lda #>N_BUFFER
        sta ptr1+1
        ldx #2
@page:  ldy #0
@write: lda (ptr1),y
        jsr scrPut
        iny
        bne @write
        inc ptr1+1
        dex
        bne @page
        inc sf_chunk
        inc sf_chunk
        lda sf_chunk
        cmp #16
        bne @chunk
@font_restored:
        ; Once restored, a later heap-free retry must not read a released font.
        lda videoPhase
        cmp #3
        bcc @mode
        lda #2
        sta videoPhase
@mode:  lda videoPhase
        cmp #2
        bcc @mode_restored
        ldy #0
@reg:   ldx restoreRegs,y
        lda savedVdc,x
        jsr scrRegWrite
        iny
        cpy #restoreCount
        bne @reg
@mode_restored:
        jsr _gui_end            ; release graphics only after the font/mode restore
        ; Keep native key handling until every retained allocation closes.
        jsr _tm_end
        bcs @retained
        jsr sf_close
        bcs @retained
        lda videoPhase
        beq @done
        lda savedScreen
        cmp $d7
        beq @screen_restored
        jsr $ff5f              ; ROM swapper only exchanges editor locals/maps
@screen_restored:
        lda _native_border
        sta $d020
        php
        sei
        ldx #0
@keys: lda savedKeys,x
        sta $1000,x
        inx
        bne @keys
        lda #0
        sta $d1
        sta $d2
        plp
        lda #0
        sta videoPhase
        sta _gui_recovery
@done: lda #0
        tax
        clc
        rts
@retained:
        ldx #0
        sec
        rts

; Paint the complete retained terminal after restoring a graphical overlay.
; Parser arguments stay intact even when the view changes mid-command.
_scr_sync:
        lda #0
        sta videoFault
        jsr scrGate
        lda _tm_live
        bne @model
        lda #N_BADARG
        sec
        rts
@model:jsr fontAddress
        jsr scrSetAddr
        lda #0
        sta ptr1
        lda #$50
        sta ptr1+1
        ldx #16
@page: ldy #0
@font: lda (ptr1),y
        jsr scrPut
        iny
        bne @font
        inc ptr1+1
        dex
        bne @page
        lda #0
        sta syncPlane
@plane:lda #0
        sta syncRow
@row:  lda syncRow
        ldx syncPlane
        jsr _tm_read
        bcs @return
        lda N_OFFSET
        sta offsetLo
        lda N_OFFSET+1
        sta offsetHi
        jsr scrSetAddr
        ldy #0
@cell: lda N_BUFFER,y
        jsr scrPut
        iny
        cpy #80
        bne @cell
        inc syncRow
        lda syncRow
        cmp #25
        bne @row
        inc syncPlane
        lda syncPlane
        cmp #2
        bne @plane
        lda _gui_cursor_row
        cmp #25
        bcs @hide
        lda _gui_cursor_col
        cmp #80
        bcs @hide
        ; Read computes row*80 without changing the protocol argument globals.
        lda _gui_cursor_row
        ldx #0
        jsr _tm_read
        bcs @return
        lda N_OFFSET
        clc
        adc _gui_cursor_col
        pha
        lda N_OFFSET+1
        adc #0
        ldx #14
        jsr scrRegWrite
        pla
        inx
        jsr scrRegWrite
        lda #$60
        bne @cursor
@hide: lda #$20
@cursor:ldx #10
        jsr scrRegWrite
        lda #0
        clc
@return:rts

.rodata
        .import _gui_poll, _gui_key, _gui_end, _gui_font_hi
nativeKeys: .byte $85,$89,$86,$8a,$87,$8b,$88,$8c,$83,$84
restoreRegs: .byte 10,11,12,13,14,15,20,21,24,25,26,27,28,29,32,33,18,19
restoreCount = *-restoreRegs

.include "saved-font.inc"
