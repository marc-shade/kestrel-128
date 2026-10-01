; Fixed 8x8 ASCII labels; bounded input lives inside the calling app.
; gfx_text_buffer[0..gfx_text_length) is at most 64 bytes. Nonprintable
; bytes draw '?'. Uses gfx_pen 0..3 and x0/y0; advances x0, saturating at
; 32767. Colors are unchanged. D/I preserved; other graphics args clobbered.
.weak
GFX_TEXT_STORAGE=0
GFX_FONT_COLUMNS=0
.endweak
gfx_text:
        php
        cld
        jsr gfx_guard
        bcs gfx_text_failed
        lda gfx_bound
        bne +
        lda #N_BADHANDLE
        bne gfx_text_failed
+       lda gfx_pen
        cmp #4
        bcs gfx_text_badarg
        lda gfx_text_length
        cmp #65
        bcc +
gfx_text_badarg:
        lda #N_BADARG
gfx_text_failed:
        jmp gfx_finish
+       sta gfx_text_left
        lda #0
        sta gfx_text_index
        lda gfx_text_left
        beq gfx_text_done
gfx_text_next:
        ldx gfx_text_index
        lda gfx_text_buffer,x
        cmp #32
        bcc gfx_text_unknown
        cmp #127
        bcc gfx_text_code
gfx_text_unknown:
        lda #63
gfx_text_code:
        jsr gfx_load_glyph
        jsr gfx_glyph
        bcs gfx_text_failed
        clc
        lda gfx_x0
        adc #8
        sta gfx_x0
        lda gfx_x0+1
        adc #0
        bvs gfx_text_saturate
        sta gfx_x0+1
        jmp gfx_text_advance
gfx_text_saturate:
        lda #$ff
        sta gfx_x0
        lda #$7f
        sta gfx_x0+1
gfx_text_advance:
        inc gfx_text_index
        dec gfx_text_left
        bne gfx_text_next
gfx_text_done:
        lda #0
        jmp gfx_finish

; A is a printable ASCII code. Cell renderers share this exact decoder.
gfx_load_glyph:
        sec
        sbc #32
.if GFX_FONT_COLUMNS
        tay
.endif
        ldx #0
        stx gfx_text_high
        asl
        rol gfx_text_high
        asl
        rol gfx_text_high
.if GFX_FONT_COLUMNS
        sta gfx_text_load+1
        tya
        clc
        adc gfx_text_load+1
        bcc +
        inc gfx_text_high
+
.else
        asl
        rol gfx_text_high
.endif
        clc
        adc #<gfx_font
        sta gfx_text_load+1
        lda gfx_text_high
        adc #>gfx_font
        sta gfx_text_load+2
        ldx #7-3*GFX_FONT_COLUMNS
gfx_text_load:
        lda gfx_font,x
.if GFX_FONT_COLUMNS
        sta gfx_text_columns,x
.else
        sta gfx_bits,x
.endif
        dex
        bpl gfx_text_load
.if GFX_FONT_COLUMNS
        ldy #7
gfx_text_row:
        lda #0
        ldx #0
gfx_text_column:
        lsr gfx_text_columns,x
        rol
        inx
        cpx #5
        bne gfx_text_column
        asl
        asl
        sta gfx_bits,y
        dey
        bpl gfx_text_row
.endif
        rts

gfx_text_length:.byte 0
.if GFX_TEXT_STORAGE
gfx_text_buffer=GFX_TEXT_STORAGE
.else
gfx_text_buffer:.fill 64,0
.endif
gfx_text_left:  .byte 0
gfx_text_index: .byte 0
gfx_text_high:  .byte 0
.if GFX_FONT_COLUMNS
gfx_text_columns: .fill 5,0
.endif
gfx_font:
.if GFX_FONT_COLUMNS
        .binary "font5.bin"
.else
        .binary "font8.bin"
.endif
gfx_text_end:
