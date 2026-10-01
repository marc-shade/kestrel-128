; Core-owned checked module identity. Failed loads never retain a callable kind.
sg_module:
        sta sm_wanted
        cmp sm_kind
        beq sm_select
        lda #0
        sta sm_kind
        lda N_MSTATE
        beq +
        jsr N_MCLOSE
        bcs sm_return
+       lda sm_wanted
        cmp #1
        beq +
        ldy #19
        cmp #2
        beq sm_name
        ldy #29
        bne sm_name
+       ldy #9
sm_name:
        ldx #9
-       lda sm_names,y
        sta N_FNAME,x
        dey
        dex
        bpl -
        lda #10
        sta N_FNAMELEN
        jsr N_MLOAD
        bcs sm_return
        lda sm_wanted
        sta sm_kind
        ldx #2
-       lda N_MTOKEN,x
        sta sm_token,x
        dex
        bpl -
sm_select:
        ldx #2
-       lda sm_token,x
        sta N_MTOKEN,x
        dex
        bpl -
        clc
sm_return:
        rts
sm_names: .text "shfont.prgshcalc.prgshclip.prg"
sm_kind: .byte 0
sm_wanted: .byte 0
sm_token: .fill 3,0
