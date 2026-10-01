; Full 320x200 hires bitmap and 40x25 color cells in an owned 36-page block.
; Document and undo remain separate from presentation. All calls are foreground
; with decimal mode clear. The first changed point in a stroke snapshots undo.
pd_init:
        lda #0
        sta pd_dirty
        sta pd_undo_valid
        sta pd_stroke
        sta pd_slot
pd_alloc_next:
        lda N_CURRENT
        sta N_OWNER
        lda #1
        sta N_BANK
        lda #36
        sta N_PAGES
        jsr N_ALLOC
        bcs pd_return
        ldx pd_slot
        ldy #0
-       lda N_HANDLE,y
        sta pd_handles,x
        inx
        iny
        cpy #4
        bne -
        stx pd_slot
        cpx #8
        bne pd_alloc_next
        jmp pd_blank
pd_return:
        rts

; X is the byte offset of the handle: 0 current, 4 undo, 8 staging.
pd_select:
        lda N_CURRENT
        sta N_OWNER
        ldy #0
-       lda pd_handles,x
        sta N_HANDLE,y
        inx
        iny
        cpy #4
        bne -
        rts
pd_transfer_size:
        lda #0
        sta N_COUNT
        lda #2
        sta N_COUNT+1
        rts
pd_offset:
        lda #0
        sta N_OFFSET
        lda pd_page
        sta N_OFFSET+1
        rts

pd_blank:
        lda #0
        sta pd_page
pd_blank_chunk:
        ldx #0
        jsr pd_select
        jsr pd_transfer_size
        jsr pd_offset
        lda #0
        ldx pd_page
        cpx #32
        bcc +
        lda #$10
+       sta N_VALUE
        jsr N_FILL
        bcs pd_return
        inc pd_page
        inc pd_page
        lda pd_page
        cmp #36
        bne pd_blank_chunk
        lda #0
        clc
        rts

pd_snapshot:
        lda #0
        sta pd_undo_valid       ; a failed partial copy cannot be offered as undo
        sta pd_page
pd_snapshot_chunk:
        ldx #0
        jsr pd_select
        jsr pd_transfer_size
        jsr pd_offset
        jsr N_READ
        bcs pd_return
        ldx #4
        jsr pd_select
        jsr N_WRITE
        bcs pd_return
        inc pd_page
        inc pd_page
        lda pd_page
        cmp #36
        bne pd_snapshot_chunk
        lda pd_dirty
        sta pd_undo_dirty
        lda #1
        sta pd_undo_valid
        lda #0
        clc
        rts
pd_undo:
        lda #0
        sta pd_stroke
        lda pd_undo_valid
        beq pd_no_change
        ldx #3
-       lda pd_handles,x
        ldy pd_handles+4,x
        sta pd_handles+4,x
        tya
        sta pd_handles,x
        dex
        bpl -
        lda pd_dirty
        ldy pd_undo_dirty
        sta pd_undo_dirty
        sty pd_dirty
pd_no_change:
        lda #0
        clc
        rts
pd_clear:
        ; Clearing a blank picture must preserve a preceding useful undo.
        lda #0
        sta pd_page
pd_clear_check:
        ldx #0
        jsr pd_select
        jsr pd_transfer_size
        jsr pd_offset
        jsr N_READ
        bcs pd_return
        lda #0
        ldx pd_page
        cpx #32
        bcc +
        lda #$10
+       ldx #0
-       cmp N_BUFFER,x
        bne pd_clear_changed
        cmp N_BUFFER+256,x
        bne pd_clear_changed
        inx
        bne -
        inc pd_page
        inc pd_page
        lda pd_page
        cmp #36
        bne pd_clear_check
        jmp pd_no_change
pd_clear_changed:
        jsr pd_snapshot
        bcs pd_return
        lda #0
        sta pd_stroke
        lda #1
        sta pd_dirty
        jmp pd_blank

; pd_x/pd_y are image coordinates. pd_pen=0 clears, 1 draws with pd_color.
; Carry reports heap/input error; pd_changed reports a successful changed point.
pd_point:
        lda #0
        sta pd_changed
        lda pd_x+1
        cmp #2
        bcs pd_bad_point
        cmp #1
        bne +
        lda pd_x
        cmp #64
        bcs pd_bad_point
+       lda pd_y
        cmp #200
        bcs pd_bad_point
        lda pd_color
        cmp #16
        bcs pd_bad_point
        lda pd_pen
        cmp #2
        bcs pd_bad_point
        lda pd_y
        lsr
        lsr
        lsr
        tax
        lda pd_x
        and #$f8
        clc
        adc pd_bitmap_lo,x
        sta pd_bit_offset
        lda pd_x+1
        adc pd_bitmap_hi,x
        sta pd_bit_offset+1
        lda pd_y
        and #7
        ora pd_bit_offset
        sta pd_bit_offset
        ; The cell column is nine-bit x divided by eight.
        lda pd_x
        sta pd_column
        lda pd_x+1
        lsr
        ror pd_column
        lsr pd_column
        lsr pd_column
        lda pd_column
        clc
        adc pd_color_lo,x
        sta pd_color_offset
        lda #$20
        adc pd_color_hi,x
        sta pd_color_offset+1
        ldx #0
        jsr pd_select
        lda #1
        sta N_COUNT
        lda #0
        sta N_COUNT+1
        lda pd_bit_offset
        sta N_OFFSET
        lda pd_bit_offset+1
        sta N_OFFSET+1
        jsr N_READ
        bcs pd_return
        lda N_BUFFER
        sta pd_old_bit
        ldx pd_pen
        beq pd_erase_bit
        lda pd_x
        and #7
        tax
        lda pd_masks,x
        ora pd_old_bit
        jmp pd_keep_bit
pd_bad_point:
        lda #N_BADARG
        sec
        rts
pd_erase_bit:
        lda pd_x
        and #7
        tax
        lda pd_masks,x
        eor #$ff
        and pd_old_bit
pd_keep_bit:
        sta pd_new_bit
        lda pd_color_offset
        sta N_OFFSET
        lda pd_color_offset+1
        sta N_OFFSET+1
        jsr N_READ
        bcs pd_return
        lda N_BUFFER
        sta pd_old_color
        ldx pd_pen
        beq pd_keep_color
        and #15
        sta pd_new_color
        lda pd_color
        asl
        asl
        asl
        asl
        ora pd_new_color
pd_keep_color:
        sta pd_new_color
        cmp pd_old_color
        bne pd_change
        lda pd_new_bit
        cmp pd_old_bit
        beq pd_no_change
pd_change:
        lda pd_stroke
        bne pd_write_point
        jsr pd_snapshot
        bcs pd_return
        lda #1
        sta pd_stroke
pd_write_point:
        ldx #0
        jsr pd_select
        lda #1
        sta N_COUNT
        lda #0
        sta N_COUNT+1
        lda pd_bit_offset
        sta N_OFFSET
        lda pd_bit_offset+1
        sta N_OFFSET+1
        lda pd_new_bit
        sta N_BUFFER
        jsr N_WRITE
        bcs pd_return
        lda #1
        sta pd_dirty
        lda pd_color_offset
        sta N_OFFSET
        lda pd_color_offset+1
        sta N_OFFSET+1
        lda pd_new_color
        sta N_BUFFER
        jsr N_WRITE
        bcs pd_return
        lda #1
        sta pd_changed
        lda #0
        clc
        rts

pd_handles: .fill 12,0
pd_dirty: .byte 0
pd_undo_dirty: .byte 0
pd_undo_valid: .byte 0
pd_stroke: .byte 0
pd_changed: .byte 0
pd_slot: .byte 0
pd_page: .byte 0
pd_x: .word 0
pd_y: .byte 0
pd_pen: .byte 1
pd_color: .byte 1
pd_column: .byte 0
pd_bit_offset: .word 0
pd_color_offset: .word 0
pd_old_bit: .byte 0
pd_new_bit: .byte 0
pd_old_color: .byte 0
pd_new_color: .byte 0
pd_masks: .byte $80,$40,$20,$10,8,4,2,1
pd_bitmap_lo: .for row=0,row<25,row+=1
        .byte <(row*320)
        .endfor
pd_bitmap_hi: .for row=0,row<25,row+=1
        .byte >(row*320)
        .endfor
pd_color_lo: .for row=0,row<25,row+=1
        .byte <(row*40)
        .endfor
pd_color_hi: .for row=0,row<25,row+=1
        .byte >(row*40)
        .endfor
