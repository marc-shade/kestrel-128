module_validate:
        ldx #5
module_magic:
        lda N_MHEADER,x
        cmp m_magic,x
        bne module_invalid
        dex
        bpl module_magic
        lda N_MHEADER+7
        bne module_invalid
        lda N_MHEADER+6
        cmp #7
        bcc module_invalid
        cmp #N_ABI_MINOR+1
        bcs module_invalid
        lda N_MHEADER+10
        cmp N_APPHEADER+14
        bne module_invalid
        lda N_MHEADER+11
        cmp N_APPHEADER+15
        bne module_invalid
        lda N_MHEADER+9
        bne +
        lda N_MHEADER+8
        cmp #17
        bcc module_invalid
+       lda N_MHEADER+8
        clc
        adc m_base
        sta m_limit
        lda N_MHEADER+9
        adc m_base+1
        bcs module_invalid
        sta m_limit+1
        cmp field_app_end
        bcc +
        bne module_invalid
        lda m_limit
        bne module_invalid
+       lda N_MHEADER+13
        bne +
        lda N_MHEADER+12
        cmp #16
        bcc module_invalid
+       lda N_MHEADER+12
        cmp N_MHEADER+8
        lda N_MHEADER+13
        sbc N_MHEADER+9
        bcs module_invalid
        lda N_MHEADER+12
        clc
        adc m_base
        sta m_entry
        lda N_MHEADER+13
        adc m_base+1
        sta m_entry+1
        clc
        rts
module_invalid:
        lda #N_BADIMAGE
        sec
        rts
m_magic: .text "nmod"
        .byte 1,1,7,0
