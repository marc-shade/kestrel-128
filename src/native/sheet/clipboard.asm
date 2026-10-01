*=$adfe
.include "../api.inc"
        .word $ae00
        .byte $4e,$4d,$4f,$44,1,1,13,0
        .word end-$ae00,0,16,0
entry:
        lda N_VALUE
        cmp #2
        beq claim
        cmp #0
        bne paste
        ldx #0
-       lda N_BUFFER,x
        beq copy
        inx
        cpx #32
        bne -
invalid:
        lda #N_BADARG
        sec
        rts
copy:
        stx cp_length
        lda #0
        sta cp_length+1
        sta cp_length+2
        cpx #0
        bne +
        jmp invalid
+       jsr cp_begin
        bcs return
        lda cp_length
        sta cp_count
        lda #0
        sta cp_count+1
        jsr cp_write
        bcs abort
        jmp cp_commit
abort:
        pha
        jsr cp_abort
        bcs +
        pla
        sec
        rts
+       tax
        pla
        txa
        sec
return:
        rts
paste:
        jsr cp_info
        bcs return
        lda cp_format
        cmp #1
        bne invalid
        lda cp_length+1
        ora cp_length+2
        bne invalid
        lda cp_length
        beq invalid
        cmp #32
        bcs invalid
        sta cp_count
        sta length
        lda #0
        sta cp_count+1
        sta cp_offset
        sta cp_offset+1
        sta cp_offset+2
        jsr cp_read
        bcs return
        ldx #0
-       lda N_BUFFER,x
        cmp #32
        bcc invalid
        cmp #127
        bcs invalid
        inx
        cpx length
        bne -
        lda #0
-       sta N_BUFFER,x
        inx
        cpx #32
        bne -
        clc
        rts
length: .byte 0
; N_VALUE 2: claim a workbook handed over by a desktop (document kind 3)
; straight into the core's wb_path, wb_device and wb_format, whose addresses
; the build passes from the core's link (WB_PATH, WB_DEVICE, WB_FORMAT).
claim:
        jmp dl_claim
DL_KIND = 3
DL_NAME = WB_PATH
DL_DEVICE = WB_DEVICE
DL_FORMAT = WB_FORMAT
DL_TYPE = doc_type
DL_LENGTH = doc_length
.include "../document-launch.inc"
doc_type: .byte 0
doc_length: .byte 0
.include "../clipboard.inc"
end:
        .cerror * > $c000, "Sheet clipboard exceeds module window"
