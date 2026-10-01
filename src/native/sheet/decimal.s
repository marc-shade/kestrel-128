; Native Sheet decimal arithmetic for the 6502, GPL v3 (docs/NATIVE-SHEET.md).
; The host build of engine.c has the same operations in C; the engine test
; compares both with an exact oracle. A number is a signed 32-bit mantissa
; and 0..6 decimals. Each operation is exact in 64 bits, then rounded once,
; half away from zero, to the most decimals (at most six) that fit 32 bits.
;
; sh_arith(op)  sh_ma/sh_as op sh_mb/sh_bs, op '+', '-', '*' or '/'.
; sh_compare()  -1, 0 or 1 as sh_ma/sh_as is below, equal to or above sh_mb/sh_bs.
; sh_clear()    start a literal: the magnitude is 0.
; sh_digit(d)   magnitude = magnitude*10 + d (sh_status 1 once past 2^40).
; sh_fit(n)     the literal's value with n decimals, sign sh_na.
; Results: the mantissa (A/X/sreg), sh_scale its decimals; sh_status 1 for
; overflow, 2 for division by zero (both return 0).

        .export _sh_arith, _sh_compare, _sh_clear, _sh_digit, _sh_fit
        .import _sh_ma, _sh_mb, _sh_as, _sh_bs, _sh_na, _sh_status, _sh_scale
        .importzp sreg

WA = 0                          ; four 64-bit magnitudes in w, low byte first
WB = 8
WC = 16
WQ = 24

.segment "BSS"
w:      .res 32
nb:     .res 1
decs:   .res 1
drop:   .res 1
count:  .res 1
count2: .res 1
digit:  .res 1
rem:    .res 1
mulk:   .res 1
mcand:  .res 1
phi:    .res 1
carry:  .res 1
op:     .res 1
sx:     .res 1
sc:     .res 1

.ifdef SH_MODULE
.segment "ENGINE"
.else
.segment "CODE"
.endif

; ---- 64-bit helpers: X (and Y) are offsets into w -------------------------
zero:                           ; w[X] = 0
        lda #0
        ldy #8
@l:     sta w,x
        inx
        dey
        bne @l
        rts
copy:                           ; w[X] = w[Y]
        lda #8
        sta count
@l:     lda w,y
        sta w,x
        inx
        iny
        dec count
        bne @l
        rts
add:                            ; w[X] += w[Y]
        lda #8
        sta count
        clc
@l:     lda w,x
        adc w,y
        sta w,x
        inx
        iny
        dec count
        bne @l
        rts
sub:                            ; w[X] -= w[Y] (w[X] >= w[Y])
        lda #8
        sta count
        sec
@l:     lda w,x
        sbc w,y
        sta w,x
        inx
        iny
        dec count
        bne @l
        rts
cmpw:                           ; w[X] ? w[Y]: C set when >=, Z set when equal
        txa
        clc
        adc #7
        tax
        tya
        clc
        adc #7
        tay
        lda #8
        sta count
@l:     lda w,x
        cmp w,y
        bne @d
        dex
        dey
        dec count
        bne @l
@d:     rts
shl:                            ; w[X] = w[X]*2 + C; C = the bit shifted out
        rol w,x
        rol w+1,x
        rol w+2,x
        rol w+3,x
        rol w+4,x
        rol w+5,x
        rol w+6,x
        rol w+7,x
        rts
mulsmall:                       ; w[X] = w[X]*A + Y
        sta mulk
        sty carry
        lda #8
        sta count
@byte:  lda w,x
        sta mcand
        lda #0
        sta phi
        ldy #8
@bit:   asl a                   ; the product so far, times two
        rol phi
        asl mcand
        bcc @next
        clc
        adc mulk
        bcc @next
        inc phi
@next:  dey
        bne @bit
        clc
        adc carry
        sta w,x
        lda phi
        adc #0
        sta carry
        inx
        dec count
        bne @byte
        rts
div10:                          ; w[X] /= 10; A = the remainder
        lda #0
        sta rem
        lda #64
        sta count
@l:     clc
        jsr shl
        rol rem
        lda rem
        cmp #10
        bcc @n
        sbc #10
        sta rem
        inc w,x                 ; the quotient bit (bit 0 is clear after the shift)
@n:     dec count
        bne @l
        lda rem
        rts
neg4:                           ; w[X..X+3] = its two's complement
        ldy #4
        sec
@l:     lda #0
        sbc w,x
        sta w,x
        inx
        dey
        bne @l
        rts
scaleup:                        ; w[X] *= 10^A
        sta sc
        stx sx
@l:     lda sc
        beq @r
        dec sc
        ldx sx
        lda #10
        ldy #0
        jsr mulsmall
        jmp @l
@r:     rts

; sh_ma -> WA (sh_na), sh_mb -> WB (nb): magnitudes and signs.
loads:  ldx #3
@c:     lda _sh_ma,x
        sta w+WA,x
        lda _sh_mb,x
        sta w+WB,x
        lda #0
        sta w+WA+4,x
        sta w+WB+4,x
        dex
        bpl @c
        lda #0
        sta _sh_na
        sta nb
        lda w+WA+3
        bpl @b
        inc _sh_na
        ldx #WA
        jsr neg4
@b:     lda w+WB+3
        bpl @r
        inc nb
        ldx #WB
        jsr neg4
@r:     rts
; decs = the larger scale; WA and WB scaled to it.
align:  lda _sh_as
        cmp _sh_bs
        bcs @t
        lda _sh_bs
@t:     sta decs
        sec
        sbc _sh_as
        ldx #WA
        jsr scaleup
        lda decs
        sec
        sbc _sh_bs
        ldx #WB
        jmp scaleup

; WA (sign sh_na) with decs decimals -> the result.
fit:    lda #0
        sta drop
        lda decs
        cmp #7
        bcc @try
        sbc #6
        sta drop
@try:   ldx #WC
        ldy #WA
        jsr copy
        lda drop
        beq @check
        sta count2
@d:     dec count2
        beq @last
        ldx #WC
        jsr div10
        jmp @d
@last:  ldx #WC                 ; the first dropped digit decides
        jsr div10
        cmp #5
        bcc @check
        ldx #WC
        lda #1
        tay
        jsr mulsmall            ; plus one
@check: lda w+WC+7
        ora w+WC+6
        ora w+WC+5
        ora w+WC+4
        bne @big
        lda w+WC+3
        bpl @fits
        cmp #$80
        bne @big
        lda _sh_na              ; -2^31 fits
        beq @big
        lda w+WC+2
        ora w+WC+1
        ora w+WC
        beq @fits
@big:   lda drop
        cmp decs
        beq overflow
        inc drop
        jmp @try
@fits:  lda decs
        sec
        sbc drop
        sta decs
@zeros: lda decs                ; trailing zeros go
        beq @done
        ldx #WQ
        ldy #WC
        jsr copy
        ldx #WQ
        jsr div10
        bne @done
        ldx #WC
        ldy #WQ
        jsr copy
        dec decs
        jmp @zeros
@done:  lda w+WC
        ora w+WC+1
        ora w+WC+2
        ora w+WC+3
        beq nothing
        lda decs
        sta _sh_scale
        lda _sh_na
        beq @pos
        ldx #WC
        jsr neg4
@pos:   lda w+WC+3
        sta sreg+1
        lda w+WC+2
        sta sreg
        ldx w+WC+1
        lda w+WC
        rts
overflow:
        lda #1
failed: sta _sh_status
nothing:
        lda #0
        sta _sh_scale
        tax
        sta sreg
        sta sreg+1
        rts

_sh_arith:
        sta op
        lda #0
        sta _sh_status
        jsr loads
        lda op
        cmp #$2d                ; '-': add the negation
        bne @plus
        lda nb
        eor #1
        sta nb
        lda #$2b
        sta op
@plus:  lda op
        cmp #$2b
        bne @times
        jsr align
        lda _sh_na
        cmp nb
        bne @differ
        ldx #WA
        ldy #WB
        jsr add
        jmp fit
@differ:
        ldx #WA
        ldy #WB
        jsr cmpw
        bcs @alarger
        ldx #WB
        ldy #WA
        jsr sub
        ldx #WA
        ldy #WB
        jsr copy
        lda nb
        sta _sh_na
        jmp fit
@alarger:
        ldx #WA
        ldy #WB
        jsr sub
        jmp fit
@times: lda _sh_na
        eor nb
        sta _sh_na
        lda op
        cmp #$2a
        bne @divide
        ldx #WQ                 ; by bytes of WB, most significant first
        jsr zero
        lda #3
        sta count2
@m:     ldx #6
@s:     lda w+WQ,x
        sta w+WQ+1,x
        dex
        bpl @s
        lda #0
        sta w+WQ
        ldx #WC
        ldy #WA
        jsr copy
        ldx count2
        lda w+WB,x
        ldx #WC
        ldy #0
        jsr mulsmall
        ldx #WQ
        ldy #WC
        jsr add
        dec count2
        bpl @m
        ldx #WA
        ldy #WQ
        jsr copy
        lda _sh_as
        clc
        adc _sh_bs
        sta decs
        jmp fit
@divide:
        lda w+WB
        ora w+WB+1
        ora w+WB+2
        ora w+WB+3
        bne @nonzero
        lda #2
        jmp failed
@nonzero:                       ; (|a|*10^bs)/(|b|*10^as)
        lda _sh_bs
        ldx #WA
        jsr scaleup
        lda _sh_as
        ldx #WB
        jsr scaleup
        ldx #WQ
        jsr zero
        ldx #WC
        jsr zero
        lda #64
        sta count2
@b:     clc                     ; shift and subtract: WQ quotient, WC remainder
        ldx #WA
        jsr shl
        ldx #WC
        jsr shl
        clc
        ldx #WQ
        jsr shl
        ldx #WC
        ldy #WB
        jsr cmpw
        bcc @nb
        ldx #WC
        ldy #WB
        jsr sub
        inc w+WQ
@nb:    dec count2
        bne @b
        lda w+WQ+7
        ora w+WQ+6
        ora w+WQ+5
        ora w+WQ+4
        beq @fraction
        jmp overflow
@fraction:
        lda #7                  ; seven decimals; fit rounds at six or fewer
        sta count2
@f:     ldx #WC
        lda #10
        ldy #0
        jsr mulsmall
        lda #0
        sta digit
@g:     ldx #WC
        ldy #WB
        jsr cmpw
        bcc @h
        ldx #WC
        ldy #WB
        jsr sub
        inc digit
        jmp @g
@h:     ldx #WQ
        lda #10
        ldy digit
        jsr mulsmall
        dec count2
        bne @f
        ldx #WA
        ldy #WQ
        jsr copy
        lda #7
        sta decs
        jmp fit

_sh_compare:
        jsr loads
        lda _sh_na
        cmp nb
        beq @same
        lda _sh_na              ; signs differ: the negative one is lower
        bne @below
        beq @above
@same:  jsr align
        ldx #WA
        ldy #WB
        jsr cmpw
        beq @equal
        bcs @larger
        lda _sh_na              ; a smaller magnitude
        bne @above
        beq @below
@larger:
        lda _sh_na
        bne @below
@above: lda #1
        ldx #0
        rts
@below: lda #$ff
        tax
        rts
@equal: lda #0
        tax
        rts

_sh_clear:
        lda #0
        sta _sh_status
        ldx #WA
        jmp zero

_sh_digit:
        tay
        lda w+WA+5
        beq @ok
        lda #1
        sta _sh_status
        rts
@ok:    ldx #WA
        lda #10
        jmp mulsmall

_sh_fit:
        sta decs
        lda #0
        sta _sh_status
        jmp fit
