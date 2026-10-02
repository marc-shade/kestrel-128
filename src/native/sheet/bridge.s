.export _sh_api, _sh_recalculate, _sh_clipboard, _fit_column, _format_next, _sh_document
.import _sh_number, _wb_open, _busy
.import sg_module
.import _sh_types, _sh_values, _sh_clip_text, _wb_formats
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

; fit_cell(format): the number in sh_number in its column's display format
; (A: 0 every decimal; 1 + N exactly N decimals) and within its 8-character
; cell. The text ends at its limit: 8 characters, or the point when the
; integer part takes 7 or more; with a format, at the format's decimals when
; that is sooner. A longer text keeps the digits before that end, rounded once
; (half away from zero, on the first dropped digit); a shorter one in a
; format gets zeros up to it. Without a format, trailing zeros and a bare
; point are then dropped. An integer part too long for the cell stays long,
; and a minus sign before nothing but zeros is dropped.
.segment "CODE"
; format_next(column): the column's next display format in wb_formats (two
; columns a byte, low nibble first): every decimal, then 0-6 decimals, then
; every decimal again. Returns "Column A decimals: N" (or "all").
_format_next:
        tay
        clc
        adc #$41
        sta format_text+7
        tya
        lsr a
        tax
        lda _wb_formats,x
        bcc @even
        lsr a
        lsr a
        lsr a
        lsr a
@even:  and #$0f
        adc #1                  ; (carry clear: a nibble's lsr shifted out 0s)
        and #7
        sta next
        tya
        lsr a
        lda next
        ldy #$f0                ; even: keep the high nibble
        bcc @store
        asl a
        asl a
        asl a
        asl a
        ldy #$0f                ; odd: keep the low nibble
@store: sta shifted
        tya
        and _wb_formats,x
        ora shifted
        sta _wb_formats,x
        lda next
        beq @all
        adc #$2f                ; (carry clear) 0-6
        sta format_text+19
        lda #0
        sta format_text+20
        beq @text
@all:   lda #$61                ; "all"
        sta format_text+19
        lda #$6c
        sta format_text+20
        sta format_text+21
@text:  lda #<format_text
        ldx #>format_text
        rts

; fit_column(column): fit_cell in that column's format (wb_formats).
_fit_column:
        lsr a
        tax
        lda _wb_formats,x
        bcc @low
        lsr a
        lsr a
        lsr a
        lsr a
@low:   and #$0f
_fit_cell:
        sta fixed
        ldx #0
@point: lda _sh_number,x
        beq @integer            ; no point: it would be at the end
        cmp #$2e
        beq @found
        inx
        bne @point
@integer:
        stx point
        beq @measured           ; (X is the length; never 0)
@found: stx point
@length:
        lda _sh_number,x
        beq @measured
        inx
        bne @length
@measured:
        stx len
        lda point               ; the cell's limit
        cmp #7
        bcs @limit8
        lda #8
@limit8:
        sta end
        ldy fixed
        beq @auto
        dey                     ; Y = the format's decimals
        beq @nodecimals
        tya
        sec
        adc point               ; the point, then the decimals
        bne @want               ; (at least 2)
@nodecimals:
        lda point
@want:  cmp end
        bcs @limit              ; more than the cell holds
        sta end
@limit: lda end
        cmp len
        beq @exit
        bcc @cut
        ldx len                 ; zeros up to the end, after a point
        cpx point
        bne @zeros
        lda #$2e
        sta _sh_number,x
        inx
@zeros: cpx end
        beq @padded
        lda #$30
        sta _sh_number,x
        inx
        bne @zeros
@padded:
        lda #0
        sta _sh_number,x
@exit:  rts
@auto:  lda end
        cmp len
        bcs @exit               ; it fits
@cut:   ldy end
        cpy point
        bne @first
        iny                     ; no decimals kept: the digit after the point
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
@strip: lda fixed               ; a format keeps its zeros
        bne @minus
        lda point
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
@minus: lda _sh_number          ; "-0", "-0.00": no sign
        cmp #$2d
        bne @done
        ldx #0
@digits:
        inx
        lda _sh_number,x
        beq @unsigned
        cmp #$31                ; a digit 1-9 keeps it ("." and 0 are below)
        bcc @digits
        rts
@unsigned:
        ldx #0
@shift: lda _sh_number+1,x
        sta _sh_number,x
        beq @done
        inx
        bne @shift
@done:  rts
.segment "DATA"
format_text: .byte "Column A decimals: all", 0
.segment "BSS"
next:   .res 1
shifted: .res 1
fixed:  .res 1
len:    .res 1
point:  .res 1
end:    .res 1
up:     .res 1
ins:    .res 1
