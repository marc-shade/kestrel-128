; Compact 24-bit operations for selection/UI paths. X/Y and A are scratch.
; Compare preserves unsigned carry and equality in Z, including equal values.
es_copy3 .macro source,dest
        ldx #2
-       lda \source,x
        sta \dest,x
        dex
        bpl -
.endm
es_cmp3 .macro left,right
        ldx #2
-       lda \left,x
        cmp \right,x
        bne +
        dex
        bpl -
        lda #0
+
.endm
es_add3 .macro source,dest
        ldx #0
        ldy #3
        clc
-       lda \dest,x
        adc \source,x
        sta \dest,x
        inx
        dey
        bne -
.endm
es_sub3 .macro source,dest
        ldx #0
        ldy #3
        sec
-       lda \dest,x
        sbc \source,x
        sta \dest,x
        inx
        dey
        bne -
.endm
