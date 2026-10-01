; Forward LZSA2 raw-block decoder for the native boot and app-startup wrappers.
;
; Independent implementation written from the LZSA2 block format description.
; The LZSA2 format is Emmanuel Marty's (the LZSA project); no code from that
; project is used here. SPDX-License-Identifier: GPL-3.0-or-later
;
; Contract with the including wrapper:
;   jsr DECOMPRESS_LZSA2 decodes one raw block and returns (rts) at its end
;   marker. The wrapper then checks input length, output length and CRC.
;   boot_get    returns the next input byte in A; keeps X, Y and carry.
;   boot_put    writes A to the output and advances it; keeps X, Y and carry.
;   boot_write  is a wrapper "sta abs" whose operand is the output address.
;   boot_match  validates the match source held in COPY_MATCH_LOOP+1/+2
;               before any byte of that match is read; keeps A and P.
;   boot_bad    is jumped to for encodings a valid block never contains.
; No zero-page cells are used: state lives here, and the match source is
; the operand of the self-modifying load at COPY_MATCH_LOOP. Binary mode
; (D clear) is required. The first repeat offset is zero, so a repeat match
; before any offset names the output position itself, which boot_match
; rejects like any other source that is not already decoded.

DECOMPRESS_LZSA2:
        lda #0
        sta lz_nibble_ready
        sta lz_offset
        sta lz_offset+1
lz_command:
        jsr boot_get
        sta lz_token
        and #$18                ; literal count field
        beq lz_read_offset
        cmp #$18
        beq lz_long_literals
        lsr
        lsr
        lsr
        jsr lz_short_count
        bne lz_copy_literals    ; always (count is 1 or 2)
lz_long_literals:
        lda #18
        jsr lz_long_count
        beq lz_bad              ; the literal form of the end marker is reserved
lz_copy_literals:
        jsr lz_count_pages
-       jsr boot_get
        jsr boot_put
        dey
        bne -
        dec lz_count+1
        bne -

; Offset selector XYZ: 00Z 5-bit, 01Z 9-bit, 10Z 13-bit, 110 16-bit, 111 repeat.
lz_read_offset:
        lda lz_token
        asl
        bcs lz_offset_1xx
        asl
        bcs lz_offset_9
        jsr lz_nibble_offset    ; A = $e0 | nibble<<1 | !Z
        ldx #$ff
        bne lz_store_offset     ; always
lz_offset_9:
        asl                     ; carry = Z
        ldx #$ff
        bcc +
        dex                     ; high byte is $fe when Z is set
+       jsr boot_get
        jmp lz_store_offset
lz_offset_1xx:
        asl
        bcs lz_offset_11x
        jsr lz_nibble_offset    ; high byte before the 512 bias
        sec
        sbc #2
        tax
        jsr boot_get
        jmp lz_store_offset
lz_offset_11x:
        asl                     ; carry = Z: set means repeat offset
        bcs lz_have_offset
        jsr boot_get
        tax
        jsr boot_get
lz_store_offset:
        sta lz_offset
        stx lz_offset+1
lz_have_offset:
        clc
        lda boot_write+1
        adc lz_offset
        sta COPY_MATCH_LOOP+1
        lda boot_write+2
        adc lz_offset+1
        sta COPY_MATCH_LOOP+2
        lda lz_token
        and #7                  ; match length field, minus the minimum of 2
        cmp #7
        beq lz_long_match
        adc #2                  ; carry is clear after cmp
        jsr lz_short_count
        bne lz_copy_match       ; always (count is 2..8)
lz_long_match:
        lda #24
        jsr lz_long_count
        bne lz_copy_match
        rts                     ; end marker
lz_copy_match:
        jsr boot_match
        jsr lz_count_pages
COPY_MATCH_LOOP:
        lda $ffff
        jsr boot_put
        inc COPY_MATCH_LOOP+1
        bne +
        inc COPY_MATCH_LOOP+2
+       dey
        bne COPY_MATCH_LOOP
        dec lz_count+1
        bne COPY_MATCH_LOOP
        jmp lz_command

lz_bad:
        jmp boot_bad

; A = count 0..255 with no high byte; returns Z clear when A is nonzero.
lz_short_count:
        sta lz_count
        ldx #0
        stx lz_count+1
        tax
        rts

; Extended count. A = the value a whole extra byte is added to (18 for
; literals, 24 for matches); the nibble form adds to A-15. Returns the count
; in lz_count with Z set only for the end marker (extra byte giving 256).
lz_long_count:
        sta lz_count
        lda #0
        sta lz_count+1
        jsr lz_nibble
        cmp #15
        beq lz_count_byte
        adc lz_count            ; carry is clear: nibble < 15
        sbc #14                 ; carry still clear: subtracts 15
        sta lz_count
        rts                     ; Z clear: count is at least 3
lz_count_byte:
        jsr boot_get
        clc
        adc lz_count
        sta lz_count
        bcc lz_count_done       ; 18..255 or 24..255
        beq lz_count_done       ; exactly 256: end marker, count 0
        lsr
        bne lz_bad              ; only 257 selects a 16-bit count
        jsr boot_get
        sta lz_count
        jsr boot_get
        sta lz_count+1
        ora lz_count
        beq lz_bad              ; a zero 16-bit count is invalid
lz_count_done:
        lda lz_count
        ora lz_count+1
        rts

; Y = low count, and the high count is biased so "dey / dec high" loops
; run exactly lz_count times for any nonzero count.
lz_count_pages:
        ldy lz_count
        beq +
        inc lz_count+1
+       rts

; A = $e0 | nibble<<1 | inverted Z: the high bits shared by the 5-bit
; offset (its low byte) and the 13-bit offset (its high byte, before bias).
lz_nibble_offset:
        jsr lz_nibble
        sta lz_scratch
        lda lz_token
        and #$20
        cmp #$20                ; carry = Z
        lda lz_scratch
        rol
        eor #$e1
        rts

; Nibbles come high half first; the low half is kept for the next request.
lz_nibble:
        lsr lz_nibble_ready
        bcs +
        inc lz_nibble_ready
        jsr boot_get
        sta lz_nibble_byte
        lsr
        lsr
        lsr
        lsr
        rts
+       lda lz_nibble_byte
        and #$0f
        rts

lz_token:        .byte 0
lz_count:        .word 0
lz_offset:       .word 0
lz_nibble_ready: .byte 0
lz_nibble_byte:  .byte 0
lz_scratch:      .byte 0
