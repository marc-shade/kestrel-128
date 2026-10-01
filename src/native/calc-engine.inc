; Native calculator arithmetic adapted from the calculator of Scott Hutter's
; UltOS (GPL v3 or later; see ACKNOWLEDGEMENTS.md).
; State lives in app RAM, never in the native KERNAL/BASIC zero page.
; Addition overflow and subtraction underflow are explicit OVF results.
c_clear:
        lda #$00
        sta c_acc
        sta c_acc+1
        sta c_ent
        sta c_ent+1
        sta c_elen
        sta c_pen
        sta c_err
        lda #$01
        sta c_fresh
        jsr c_show
        jmp cloop

; A = digit character ($30-$39): ent = ent*10 + digit (capped)
c_dig:
        sta c_tmp2                      ; save the digit char before A is used
        lda c_fresh
        beq _dg_cont
        lda #$00
        sta c_ent
        sta c_ent+1
        sta c_elen
        sta c_fresh
_dg_cont:
        lda c_elen
        cmp #$08
        bcs _dg_rej                     ; entry cap: ignore the key
        lda c_tmp2
        sec
        sbc #$30
        sta c_tmp2                      ; digit 0-9
        ; reject if ent > 6553, or ent = 6553 and digit > 5 (ent*10+digit > 65535)
        lda c_ent+1
        cmp #$19                        ; high byte of 6553 ($1999)
        bcc _dg_ok
        bne _dg_rej
        lda c_ent
        cmp #$99
        bcc _dg_ok
        bne _dg_rej
        lda c_tmp2
        cmp #$06
        bcc _dg_ok
_dg_rej:
        jmp cloop
_dg_ok:                                 ; ent = ent*8 + ent*2 + digit
        lda c_ent
        sta c_tmp
        lda c_ent+1
        sta c_tmp+1
        asl c_tmp
        rol c_tmp+1                     ; *2
        asl c_tmp
        rol c_tmp+1                     ; *4
        asl c_tmp
        rol c_tmp+1                     ; *8
        lda c_ent
        asl a
        sta c_rem
        lda c_ent+1
        rol a
        sta c_rem+1                     ; ent*2
        lda c_tmp
        clc
        adc c_rem
        sta c_tmp
        lda c_tmp+1
        adc c_rem+1
        sta c_tmp+1
        lda c_tmp
        clc
        adc c_tmp2
        sta c_ent
        lda c_tmp+1
        adc #$00
        sta c_ent+1
        inc c_elen
        jsr c_show
        jmp cloop

; DEL: ent = ent/10, one digit off
c_del:
        lda c_elen
        beq _cd_x
        jsr c_div10
        dec c_elen
        jsr c_show
_cd_x:  jmp cloop

; A = op 1-4: fold any pending op first, then pend this one. With no
; typed entry (elen=0, fresh=1 — right after '=' or another op) the
; accumulator is KEPT: '+1=' after '9=' continues from 9, not 0.
c_op:
        sta c_opkey
        lda c_elen
        beq _cop_ent                    ; no entry: keep acc, just pend
        lda c_pen
        beq _cop_take
        jsr c_fold
        bcs _cop_err
        jmp _cop_ent
_cop_take:                              ; first op with a typed entry: acc = ent
        lda c_ent
        sta c_acc
        lda c_ent+1
        sta c_acc+1
_cop_ent:
        lda c_opkey
        sta c_pen
        lda #$00
        sta c_ent
        sta c_ent+1
        sta c_elen
        lda #$01
        sta c_fresh
        jsr c_show
        jmp cloop
_cop_err:                               ; fold latched an error
        lda #$00
        sta c_pen
        sta c_elen
        sta c_ent
        sta c_ent+1
        lda #$01
        sta c_fresh
        jsr c_show
        jmp cloop

; '=' / RETURN: fold the pending pair
c_eq:
        lda c_pen
        beq _ce_show                    ; nothing pending: just show
        jsr c_fold
        bcs _ce_err
        lda #$00
        sta c_pen
        sta c_elen
        sta c_ent
        sta c_ent+1
        lda #$01
        sta c_fresh
        jsr c_show
        jmp cloop
_ce_err:                                ; c_fold latched the error, keep acc
        lda #$00
        sta c_pen
        sta c_elen
        sta c_ent
        sta c_ent+1
        lda #$01
        sta c_fresh
        jsr c_show
        jmp cloop
_ce_show:
        jsr c_show
        jmp cloop

; fold: acc = acc OP ent (op in c_pen). C=1 on error (c_err latched).
c_fold:
        lda c_pen
        cmp #$01
        beq _f_add
        cmp #$02
        beq _f_sub
        cmp #$03
        beq _f_mul
        cmp #$04
        beq _f_div
        clc
        rts
_f_add:
        lda c_acc
        clc
        adc c_ent
        sta c_acc
        lda c_acc+1
        adc c_ent+1
        sta c_acc+1
        bcc _native_arithmetic_ok
        jmp _native_arithmetic_overflow
_f_sub:
        lda c_acc
        sec
        sbc c_ent
        sta c_acc
        lda c_acc+1
        sbc c_ent+1
        sta c_acc+1
        bcs _native_arithmetic_ok
_native_arithmetic_overflow:
        lda #2
        sta c_err
        sec
        rts
_native_arithmetic_ok:
        clc
        rts
_f_mul:
        jsr umul32                      ; 32-bit product: low c_tmp, high c_rem
        lda c_tmp
        sta c_acc
        lda c_tmp+1
        sta c_acc+1
        lda c_rem
        ora c_rem+1
        beq _fm_ok
        lda #$02                        ; OVF
        sta c_err
        sec
        rts
_fm_ok: clc
        rts
_f_div:
        lda c_ent
        ora c_ent+1
        bne _fd_go
        lda #$01                        ; DIV/0
        sta c_err
        sec
        rts
_fd_go: lda c_acc
        sta c_tmp
        lda c_acc+1
        sta c_tmp+1
        jsr udiv                        ; c_tmp / c_ent -> c_divs, c_rem
        lda c_divs
        sta c_acc
        lda c_divs+1
        sta c_acc+1
        clc
        rts

; ---------- 16-bit arithmetic ----------
; 16/16 unsigned divide: dividend c_tmp, divisor c_ent,
; quotient -> c_divs, remainder -> c_rem. c_tmp and c_ent destroyed.
udiv:
        lda #$00
        sta c_divs
        sta c_divs+1
        sta c_rem
        sta c_rem+1
        ldx #$10
_ud_l:  asl c_divs
        rol c_divs+1
        asl c_tmp
        rol c_tmp+1                     ; shift the FULL 16-bit dividend
        rol c_rem
        rol c_rem+1
        bcs _ud_do                      ; 17th bit set: rem > any 16-bit divisor
        lda c_rem
        sec
        sbc c_ent
        tay
        lda c_rem+1
        sbc c_ent+1
        bcc _ud_n
_ud_do: lda c_rem
        sec
        sbc c_ent
        tay
        lda c_rem+1
        sbc c_ent+1
        sta c_rem+1
        sty c_rem
        inc c_divs
_ud_n:  dex
        bne _ud_l
        rts

; c_ent = c_ent / 10 (DEL backspace)
c_div10:
        lda c_ent
        sta c_tmp
        lda c_ent+1
        sta c_tmp+1
        lda #$0a
        sta c_ent
        lda #$00
        sta c_ent+1
        jsr udiv
        lda c_divs
        sta c_ent
        lda c_divs+1
        sta c_ent+1
        rts

; 32-bit product of c_acc * c_ent -> low word c_tmp, high word c_rem.
; c_ent destroyed (shifted out).
umul32:
        lda #$00
        sta c_tmp
        sta c_tmp+1
        sta c_rem
        sta c_rem+1
        ldx #$10
_um_l:  asl c_tmp                       ; product <<= 1 (32-bit)
        rol c_tmp+1
        rol c_rem
        rol c_rem+1
        lda c_ent+1                     ; test the multiplier's current bit15
        bpl _um_s
        lda c_tmp                       ; product += acc
        clc
        adc c_acc
        sta c_tmp
        lda c_tmp+1
        adc c_acc+1
        sta c_tmp+1
        lda c_rem
        adc #$00
        sta c_rem
        lda c_rem+1
        adc #$00
        sta c_rem+1
_um_s:  asl c_ent                       ; multiplier <<= 1
        rol c_ent+1
        dex
        bne _um_l
        rts


fmt_dec:
        lda c_tmp
        ora c_tmp+1
        bne _fd_nz
        lda #$30
        sta dispbuf
        lda #$00
        sta dispbuf+1
        rts
_fd_nz: lda #$00                       ; digit count (NOT Y: d10tmp's tay
        sta c_tmp2                      ; clobbers Y — count lives in c_tmp2)
_fd_l:  jsr d10tmp
        lda c_rem
        clc
        adc #$30
        pha                             ; digits pushed least-significant first
        inc c_tmp2
        lda c_tmp
        ora c_tmp+1
        bne _fd_l
        ldy #$00
_fd_c:  pla
        sta dispbuf,y
        iny
        dec c_tmp2
        bne _fd_c
        lda #$00
        sta dispbuf,y
        rts

; c_tmp = c_tmp / 10, c_rem = c_tmp mod 10 (fixed divisor; the shifted
; remainder stays under 20, so the 17th-bit carry never fires)
d10tmp:
        lda #$00
        sta c_rem
        sta c_rem+1
        ldx #$10
_d1l:   asl c_tmp
        rol c_tmp+1                     ; shift the FULL 16-bit dividend
        rol c_rem
        rol c_rem+1
        lda c_rem
        sec
        sbc #$0a
        tay
        lda c_rem+1
        sbc #$00
        bcc _d1n
        sta c_rem+1
        sty c_rem
        inc c_tmp
_d1n:   dex
        bne _d1l
        rts
