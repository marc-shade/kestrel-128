; Cold native boot wrapper. The decoder lives in the future low kernel area;
; compressed input lives at the top of the future app heap, ending at or below
; $c000, so the decoded kernel and its boot staging may extend past $6000.
; Neither remains resident.
; No decoded instruction runs until bounds, length and CRC16 all agree.
BOOT_INPUT = ($c000-BOOT_LENGTH) & $ff00
* = $1c01
        .word basic_end
        .word 10
        .byte $9e
        .text " 7184"
        .byte 0
basic_end:
        .word 0
* = $1c10
boot_entry:
        bit $d505
        bvc +
        rts
+       php
        sei
        cld
        lda $ff00
        pha
        lda #$0e
        sta $ff00
        lda #<decoder_image
        sta boot_copy_read+1
        lda #>decoder_image
        sta boot_copy_read+2
        lda #$13
        sta boot_copy_write+2
        lda #>(decoder_end+255)
        sta boot_copy_end+1
        jsr boot_copy
        lda #<boot_payload
        sta boot_copy_read+1
        lda #>boot_payload
        sta boot_copy_read+2
        lda #>BOOT_INPUT
        sta boot_copy_write+2
        lda #>(BOOT_INPUT+BOOT_LENGTH+255)
        sta boot_copy_end+1
        jsr boot_copy
        jmp decoder
boot_copy:
        ldy #0
boot_copy_read:
        lda $ffff,y
boot_copy_write:
        sta $1300,y
        iny
        bne boot_copy_read
        inc boot_copy_read+2
        inc boot_copy_write+2
        lda boot_copy_write+2
boot_copy_end:
        cmp #$ff
        bne boot_copy_read
        rts
decoder_image:
.logical $1300
decoder:
        tsx
        stx boot_stack
        jsr DECOMPRESS_LZSA2
        jmp boot_finished
.include "lzsa2-decode.inc"
; The decoder (lzsa2-decode.inc) needs X, Y and carry kept across these calls.
boot_get:
        php
        lda boot_read+2
        cmp #>(BOOT_INPUT+BOOT_LENGTH)
        bcc boot_read
        bne boot_bad
        lda boot_read+1
        cmp #<(BOOT_INPUT+BOOT_LENGTH)
        bcs boot_bad
boot_read:
        lda BOOT_INPUT
        inc boot_read+1
        bne +
        inc boot_read+2
+       plp
        rts
boot_put:
        sta boot_value
        php
        tya
        pha
        lda boot_value
        jsr boot_put_body
        pla
        tay
        plp
        rts
boot_put_body:
        pha
        lda boot_write+2
        cmp #>BOOT_END
        bcc +
        bne boot_bad
        lda boot_write+1
        cmp #<BOOT_END
        bcs boot_bad
+       pla
boot_write:
        sta $1c01
        eor boot_crc+1
        sta boot_crc+1
        ldy #8
-       asl boot_crc
        rol boot_crc+1
        bcc +
        lda boot_crc
        eor #$21
        sta boot_crc
        lda boot_crc+1
        eor #$10
        sta boot_crc+1
+       dey
        bne -
        inc boot_write+1
        bne +
        inc boot_write+2
+       rts

; A match may overlap its output, but its first byte must already be decoded.
; Source and destination then advance together; boot_put checks every write.
boot_match:
        php
        pha
        lda COPY_MATCH_LOOP+2
        cmp #>$1c01
        bcc boot_bad
        bne +
        lda COPY_MATCH_LOOP+1
        cmp #<$1c01
        bcc boot_bad
+       lda COPY_MATCH_LOOP+2
        cmp boot_write+2
        bcc +
        bne boot_bad
        lda COPY_MATCH_LOOP+1
        cmp boot_write+1
        bcs boot_bad
+       pla
        plp
        rts
boot_finished:
        lda boot_read+1
        cmp #<(BOOT_INPUT+BOOT_LENGTH)
        bne boot_bad
        lda boot_read+2
        cmp #>(BOOT_INPUT+BOOT_LENGTH)
        bne boot_bad
        lda boot_write+1
        cmp #<BOOT_END
        bne boot_bad
        lda boot_write+2
        cmp #>BOOT_END
        bne boot_bad
        lda boot_crc
        cmp #<BOOT_EXPECTED_CRC
        bne boot_bad
        lda boot_crc+1
        cmp #>BOOT_EXPECTED_CRC
        bne boot_bad
        pla
        sta $ff00
        plp
        jmp $1c10
boot_bad:
        ldx boot_stack
        txs
        ; Leave an empty BASIC program and a terminator at the SYS return.
        lda #0
        sta $1c01
        sta $1c02
        sta $1c0b
        sta $1c0c
        sta $1c0d
        pla
        sta $ff00
        plp
        ldx #0
-       lda boot_message,x
        beq +
        jsr $ffd2
        inx
        bne -
+       rts
boot_stack: .byte 0
boot_value: .byte 0
boot_crc: .word $ffff
boot_message: .byte 13
        .text "boot error - reload",13,0
decoder_end:
        .cerror decoder_end > $1c00, "boot decoder overlaps decoded kernel"
.here
        .fill (decoder_end-decoder+255)/256*256-(decoder_end-decoder),0
boot_payload:
        .binary BOOT_PACKED_FILE
boot_file_end:
        .cerror boot_file_end > BOOT_INPUT, "packed file overlaps input scratch"
        .cerror BOOT_INPUT+BOOT_LENGTH > $c000, "packed input exceeds visible app RAM"
        .cerror BOOT_END > BOOT_INPUT || BOOT_END < $1c10, "decoded kernel overlaps the packed input"
