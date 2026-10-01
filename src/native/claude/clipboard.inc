; Local clipboard operations. Terminal keys remain untouched outside controls.
cg_clip_copy:
        lda cg_font_ram
        beq cg_clip_failed
        lda #<2025
        sta cp_length
        lda #>2025
        sta cp_length+1
        lda #0
        sta cp_length+2
        sta cg_clip_row
        jsr cp_begin
        bcs cg_clip_failed
cg_clip_copy_row:
        lda cg_clip_row
        ldx #0
        jsr cg_terminal_read
        bcs cg_clip_abort
        ldy #79
-       ldx N_BUFFER,y
        lda cg_clip_ascii,x
        sta N_BUFFER,y
        dey
        bpl -
        lda #10
        sta N_BUFFER+80
        lda #81
        sta cp_count
        lda #0
        sta cp_count+1
        jsr cp_write
        bcs cg_clip_abort
        inc cg_clip_row
        lda cg_clip_row
        cmp #25
        bne cg_clip_copy_row
        jsr cp_commit
        bcs cg_clip_abort
        lda #5
        bne cg_clip_notice
cg_clip_abort:
        jsr cp_abort
cg_clip_failed:
        lda #8
cg_clip_notice:
        sta cg_clip_status
        inc cg_controls_dirty
        jmp cg_zero

; C-callable: return an error byte in A, X=0. Each chunk checks publication
; identity so copying another item cannot splice it into an in-flight paste.
gui_clip_prepare:
        jsr cp_info
        bcs cg_clip_return
        lda cp_format
        cmp #CB_TEXT
        bne cg_clip_bad
        lda cp_length+2
        bne cg_clip_bad
        lda cp_length
        ora cp_length+1
        beq cg_clip_bad
        ldx #2
-       lda CB_SEQUENCE,x
        sta cg_clip_sequence,x
        lda #0
        sta cg_clip_offset,x
        dex
        bpl -
        clc
cg_clip_return:
        ldx #0
        rts
cg_clip_bad:
        lda #N_BADHANDLE
        sec
        bcs cg_clip_return
gui_clip_chunk:
        ldx #2
-       lda CB_SEQUENCE,x
        cmp cg_clip_sequence,x
        bne cg_clip_bad
        lda cg_clip_offset,x
        sta cp_offset,x
        dex
        bpl -
        sec
        lda cp_length
        sbc cg_clip_offset
        sta cg_clip_count
        lda cp_length+1
        sbc cg_clip_offset+1
        bne cg_clip_full
        lda cg_clip_count
        beq cg_clip_return
        cmp #65
        bcc +
cg_clip_full:
        lda #64
+       sta cp_count
        sta cg_clip_count
        lda #0
        sta cp_count+1
        jsr cp_read
        bcs cg_clip_return
        clc
        lda cg_clip_offset
        adc cg_clip_count
        sta cg_clip_offset
        bcc +
        inc cg_clip_offset+1
+       lda #0
        beq cg_clip_return
cg_clip_row: .byte 0
cg_clip_count: .byte 0
cg_clip_status: .byte 0
cg_paste_active: .byte 0
cg_clip_offset: .fill 3,0
cg_clip_sequence: .fill 3,0
.include "../clipboard.inc"
.include "clipboard-ascii.inc"
