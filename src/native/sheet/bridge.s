.export _sh_api, _sh_recalculate, _sh_clipboard, _fit_cell, _sh_document
.import _sh_number, _wb_open, _busy
.import sg_module
.import _sh_types, _sh_values, _sh_clip_text
.segment "CODE"
_sh_api:
        sta call+1
        asl
        clc
        adc call+1
        adc #$20
        sta call+1
call:   jsr $1c20
        ldx #0
        rts
_sh_recalculate:
        lda #2
        jsr sg_module
        bcc calculate
        pha
        ldx #0
invalid:
        lda #10
        sta _sh_types,x
        lda #0
        sta _sh_values,x
        sta _sh_values+256,x
        sta _sh_values+512,x
        sta _sh_values+768,x
        inx
        bne invalid
        pla
        bne done
calculate:
        jsr $1c62
done:   ldx #0
        rts
_sh_clipboard:
        sta clip_operation
        lda #3
        jsr sg_module
        bcs done
        ldx #31
copy_in:
        lda _sh_clip_text,x
        sta $3a00,x
        dex
        bpl copy_in
        lda clip_operation
        sta $3d0c
        jsr $1c62
        bcs done
        ldx #31
copy_out:
        lda $3a00,x
        sta _sh_clip_text,x
        dex
        bpl copy_out
        lda #0
        beq done
; sh_document: a workbook handed over by a desktop (the document request,
; kind 3; docs/NATIVE-DOCUMENT-LAUNCH.md): SHCLIP claims it into wb_path,
; wb_device and wb_format, then it opens as Open does. 0 when there is none
; (or the request is unusable), else wb_open's result.
_sh_document:
        lda #3
        jsr sg_module
        bcs no_document
        lda #2
        sta $3d0c
        jsr $1c62
        bcs no_document
        lda #1                  ; "Opening cell:"
        sta _busy
        jsr _wb_open
        ldy #0
        sty _busy
        ldx #0
        rts
no_document:
        lda #0
        tax
        rts
.segment "DATA"
clip_operation: .byte 0

; fit_cell: the number in sh_number, when longer than its 8-character cell,
; keeps the decimals that fit, rounded once (half away from zero, on the
; first dropped digit), then loses trailing zeros and a bare point; only an
; integer part too long for the cell stays long.
.segment "CODE"
_fit_cell:
        ldx #0
@point: lda _sh_number,x
        beq @exit               ; no point: an integer, unchanged
        cmp #$2e
        beq @found
        inx
        bne @point
@found: stx point
@length:
        lda _sh_number,x
        beq @measured
        inx
        bne @length
@measured:
        cpx #9
        bcs @long
@exit:  rts                     ; it fits
@long:  lda point               ; keep = 7 - point decimals, ending at 8
        tay
        cmp #7
        bcs @integer
        lda #8
        sta end
        tay
        bne @first
@integer:
        sta end                 ; no decimals: the text ends at the point
        iny
@first: lda _sh_number,y        ; the first dropped digit decides
        cmp #$35
        lda #0
        rol a
        sta up
        ldx end
        lda #0
        sta _sh_number,x
@carry: lda up
        beq @strip
        txa
        beq @insert             ; carried out of the first digit
        dex
        lda _sh_number,x
        cmp #$2d
        beq @sign
        cmp #$2e
        beq @carry
        cmp #$39
        bne @increment
        lda #$30
        sta _sh_number,x
        bne @carry
@increment:
        inc _sh_number,x
        lda #0
        sta up
        beq @strip
@sign:  inx
@insert:                        ; 9.99 -> 10.0: a 1 before the digits
        stx ins
        ldy end
@move:  lda _sh_number,y
        sta _sh_number+1,y
        cpy ins
        beq @moved
        dey
        bne @move
        lda _sh_number
        sta _sh_number+1
@moved: lda #$31
        ldx ins
        sta _sh_number,x
        inc end
@strip: lda point
        cmp #7
        bcs @minus              ; no decimals were kept
@zero:  ldx end
        dex
        lda _sh_number,x
        cmp #$30
        bne @dot
        lda #0
        sta _sh_number,x
        stx end
        beq @zero
@dot:   cmp #$2e
        bne @minus
        lda #0
        sta _sh_number,x
@minus: lda _sh_number          ; "-0" is 0
        cmp #$2d
        bne @done
        lda _sh_number+1
        cmp #$30
        bne @done
        lda _sh_number+2
        bne @done
        lda #$30
        sta _sh_number
        lda #0
        sta _sh_number+1
@done:  rts
.segment "BSS"
point:  .res 1
end:    .res 1
up:     .res 1
ins:    .res 1
