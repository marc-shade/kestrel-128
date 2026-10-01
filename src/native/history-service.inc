; A bounded, transactional span journal. Records use checked native RAM or
; the existing shared REU lease. The extra slot retains an unpublished record;
; failed frees never erase its token. This service performs no document edits.
.include "history-api.inc"
bh_entry:
        cmp #H_CLOSE+1
        bcs bh_badarg
        sta bh_operation
        cmp #H_INFO
        beq bh_info
        cmp #H_BEGIN
        beq bh_begin
        cmp #H_APPEND
        beq bh_append
        cmp #H_SEAL
        beq bh_seal
        cmp #H_ABORT
        beq bh_abort
        cmp #H_UNDO
        beq bh_prepare
        cmp #H_REDO
        beq bh_prepare
        cmp #H_READ
        beq bh_read
        cmp #H_APPLIED
        beq bh_applied
        cmp #H_SAVE
        beq bh_save
        jmp bh_clear
bh_badarg:
        lda #N_BADARG
        sec
        rts
bh_nomem:
        lda #N_NOMEM
        sec
        rts
bh_range:
        lda #N_RANGE
        sec
        rts
bh_ok:
        lda #0
        clc
bh_return:
        rts
bh_info:
        lda #1
        ldx bh_cursor
        cpx bh_saved
        bne +
        lda #0
+       sta N_BUFFER
        stx N_BUFFER+1
        sec
        lda bh_count
        sbc bh_cursor
        sta N_BUFFER+2
        lda #1
        sta N_BUFFER+3
        jmp bh_ok
bh_save:
        lda bh_pending
        ora bh_replay
        bne bh_badarg
        lda bh_cursor
        sta bh_saved
        jmp bh_info

; 9-byte records: kind (0 empty, 1 RAM, 2 REU), opaque token (4/8 bytes).
bh_slot:
        lda bh_index
        asl
        asl
        asl
        clc
        adc bh_index
        tay
        rts
bh_arguments:
        jsr bh_slot
        lda bh_records,y
        cmp #2
        beq bh_reu_arguments
        cmp #1
        bne bh_badarg
        lda #N_APPOWNER
        sta N_OWNER
        ldx #0
-       lda bh_records+1,y
        sta N_HANDLE,x
        iny
        inx
        cpx #4
        bne -
        ldx #1
-       lda bh_offset,x
        sta N_OFFSET,x
        lda bh_size,x
        sta N_COUNT,x
        dex
        bpl -
        lda #1
        clc
        rts
bh_reu_arguments:
        ldx #0
-       lda bh_records+1,y
        sta SM_TOKEN,x
        iny
        inx
        cpx #8
        bne -
        ldx #2
-       lda bh_offset,x
        sta SM_OFFSET,x
        dex
        bpl -
        ldx #1
-       lda bh_size,x
        sta SM_COUNT,x
        dex
        bpl -
        lda #2
        clc
        rts
bh_transfer:
        sta bh_transfer_op      ; 0 read, 1 write
        jsr bh_arguments
        bcs bh_return
        cmp #2
        beq +
        lda bh_offset+2
        bne bh_range
        lda bh_transfer_op
        beq bv_read
        jmp bv_write
+       lda bh_transfer_op
        clc
        adc #SM_READ
        jmp bm_entry
bh_free:
        jsr bh_slot
        lda bh_records,y
        beq bh_ok
        jsr bh_arguments
        bcs bh_return
        cmp #2
        beq +
        jsr bv_free
        jmp ++
+       lda #SM_FREE
        jsr bm_entry
+       bcs bh_return
        jsr bh_slot
        lda #0
        sta bh_records,y
        dec bh_live
        jmp bh_ok
bh_abort:
        lda #0
        sta bh_pending
        sta bh_replay
        lda #H_STEPS
        sta bh_index
        jmp bh_free
bh_clear:
        lda #255
        ldx N_BUFFER
        bne +
        lda #0
+       sta bh_saved
        lda #0
        sta bh_count
        sta bh_cursor
        sta bh_replay
        sta bh_pending
        sta bh_index
        sta bh_error
-       jsr bh_free
        bcc +
        sta bh_error
+       inc bh_index
        lda bh_index
        cmp #H_STEPS+1
        bne -
        lda bh_error
        bne +
        jmp bh_info
+       sec
        rts

bh_begin:
        lda bh_replay
        bne bh_badarg
        ; Save the header before allocation/probe code can use the mailbox.
        ldx #H_HEADER-1
-       lda N_BUFFER,x
        sta bh_header,x
        dex
        bpl -
        jsr bh_abort
        bcs bh_return
        lda bh_count
        sta bh_index
-       jsr bh_free
        bcs bh_return
        inc bh_index
        lda bh_index
        cmp #H_STEPS+1
        bne -
        clc
        ldx #0
        ldy #3
-       lda bh_header+3,x
        adc bh_header+6,x
        sta bh_total,x
        inx
        dey
        bne -
        bcs bh_nomem
        clc
        lda bh_total
        adc #H_HEADER
        sta bh_total
        lda bh_total+1
        adc #0
        sta bh_total+1
        lda bh_total+2
        adc #0
        sta bh_total+2
        bcs bh_nomem
        lda bm_lease
        beq bh_allocate_ram
        ; ceil(bytes / 4096), bounded by the arena's representable extent.
        clc
        lda bh_total
        adc #255
        lda bh_total+1
        adc #15
        sta SM_PAGES
        lda bh_total+2
        adc #0
        bcs bh_nomem
        sta SM_PAGES+1
        ldx #4
-       lsr SM_PAGES+1
        ror SM_PAGES
        dex
        bne -
        lda #SM_ALLOC
        jsr bm_entry
        bcs bh_return
        ldx #7
-       lda SM_TOKEN,x
        sta bh_records+H_STEPS*9+1,x
        dex
        bpl -
        lda #2
        bne bh_allocated
bh_allocate_ram:
        lda bh_total+2
        bne bh_nomem
        lda bh_total
        cmp #1
        lda bh_total+1
        adc #0
        bcs bh_nomem
        beq bh_nomem
        sta N_PAGES
        lda #255
        sta N_BANK
        lda #N_APPOWNER
        sta N_OWNER
        jsr bv_alloc
        bcs bh_return
        ldx #3
-       lda N_HANDLE,x
        sta bh_records+H_STEPS*9+1,x
        dex
        bpl -
        lda #1
bh_allocated:
        sta bh_records+H_STEPS*9
        inc bh_live
        lda #H_STEPS
        sta bh_index
        lda #0
        sta bh_offset
        sta bh_offset+1
        sta bh_offset+2
        sta bh_size+1
        sta bh_size+2
        lda #H_HEADER
        sta bh_size
        ldx #H_HEADER-1
-       lda bh_header,x
        sta N_BUFFER,x
        dex
        bpl -
        lda #1
        jsr bh_transfer
        bcs bh_return
        ldx #2
-       lda bh_size,x
        sta bh_written,x
        dex
        bpl -
        lda #1
        sta bh_pending
        jmp bh_ok

bh_size_check:
        lda H_COUNT
        sta bh_size
        lda H_COUNT+1
        sta bh_size+1
        cmp #2
        bcc +
        bne bh_badarg
        lda bh_size
        bne bh_badarg
+       lda bh_size
        ora bh_size+1
        beq bh_badarg
        lda #0
        sta bh_size+2
        clc
        rts
bh_append:
        lda bh_pending
        beq bh_badarg
        jsr bh_size_check
        bcs bh_return
        ldx #2
-       lda bh_written,x
        sta bh_offset,x
        dex
        bpl -
        jsr bh_extent
        bcs bh_return
        lda #H_STEPS
        sta bh_index
        lda #1
        jsr bh_transfer
        bcs bh_poison
        ldx #2
-       lda bh_next,x
        sta bh_written,x
        dex
        bpl -
        jmp bh_ok
bh_poison:
        pha
        lda #0
        sta bh_pending
        pla
        sec
        rts
bh_extent:
        clc
        ldx #0
        ldy #3
-       lda bh_offset,x
        adc bh_size,x
        sta bh_next,x
        inx
        dey
        bne -
        bcs bh_range
        ldx #2
-       lda bh_total,x
        cmp bh_next,x
        bne +
        dex
        bpl -
+       bcc bh_range
        jmp bh_ok

bh_seal:
        lda bh_pending
        beq bh_badarg
        ldx #2
-       lda bh_written,x
        cmp bh_total,x
        bne bh_badarg
        dex
        bpl -
        ; Remove redo only after a complete replacement record exists.
        lda bh_cursor
        sta bh_index
-       lda bh_index
        cmp bh_count
        beq bh_seal_full
        jsr bh_free
        bcs bh_broken
        inc bh_index
        jmp -
bh_seal_full:
        lda bh_saved
        cmp bh_cursor
        bcc +
        beq +
        lda #255
        sta bh_saved
+       lda bh_cursor
        cmp #H_STEPS
        bne bh_publish
        lda #0
        sta bh_index
        jsr bh_free
        bcs bh_broken
        ldx #0
-       lda bh_records+9,x
        sta bh_records,x
        inx
        cpx #(H_STEPS-1)*9
        bne -
        lda #0
        sta bh_records+(H_STEPS-1)*9
        dec bh_cursor
        lda bh_saved
        cmp #255
        beq bh_publish
        dec bh_saved          ; the evicted clean baseline becomes $ff
bh_publish:
        lda bh_cursor
        sta bh_index
        jsr bh_slot
        ldx #0
-       lda bh_records+H_STEPS*9,x
        sta bh_records,y
        iny
        inx
        cpx #9
        bne -
        lda #0
        sta bh_records+H_STEPS*9
        sta bh_pending
        inc bh_cursor
        lda bh_cursor
        sta bh_count
        jmp bh_info
bh_broken:
        ; A partial redo/oldest cleanup invalidates the list, but every
        ; remaining token is retained and reclaimed before another BEGIN.
        pha
        lda #0
        sta bh_cursor
        sta bh_count
        sta bh_pending
        sta bh_replay
        lda #255
        sta bh_saved
        pla
        sec
        rts

bh_prepare:
        lda bh_replay
        ora bh_pending
        bne bh_badarg
        lda bh_cursor
        ldx bh_operation
        cpx #H_REDO
        beq +
        cmp #0
        beq bh_range
        sec
        sbc #1
        jmp ++
+       cmp bh_count
        bcs bh_range
+       sta bh_index
        lda #0
        sta bh_offset
        sta bh_offset+1
        sta bh_offset+2
        sta bh_size+1
        sta bh_size+2
        lda #H_HEADER
        sta bh_size
        lda #0
        jsr bh_transfer
        bcs bh_return
        ldx #H_HEADER-1
-       lda N_BUFFER,x
        sta bh_header,x
        dex
        bpl -
        lda #H_HEADER
        sta bh_offset
        lda bh_operation
        sec
        sbc #H_UNDO-1
        sta bh_replay
        cmp #2
        bne bh_prepare_undo
        clc
        ldx #0
        ldy #3
-       lda bh_offset,x
        adc bh_header+3,x
        sta bh_offset,x
        inx
        dey
        bne -
        jmp bh_prepare_limit
bh_prepare_undo:
        ldx #2
-       lda bh_header+3,x
        sta N_BUFFER+6,x
        lda bh_header+6,x
        sta N_BUFFER+3,x
        dex
        bpl -
bh_prepare_limit:
        clc
        ldx #0
        ldy #3
-       lda bh_offset,x
        adc N_BUFFER+6,x
        sta bh_total,x
        inx
        dey
        bne -
        bcs bh_badarg
        jmp bh_ok
bh_read:
        lda bh_replay
        beq bh_badarg
        jsr bh_size_check
        bcs bh_return
        jsr bh_extent
        bcs bh_return
        lda #0
        jsr bh_transfer
        bcs bh_return
        ldx #2
-       lda bh_next,x
        sta bh_offset,x
        dex
        bpl -
        jmp bh_ok
bh_applied:
        lda bh_replay
        beq bh_badarg
        ldx #2
-       lda bh_offset,x
        cmp bh_total,x
        bne bh_badarg
        dex
        bpl -
        lda bh_replay
        cmp #2
        beq +
        dec bh_cursor
        jmp ++
+       inc bh_cursor
+       lda #0
        sta bh_replay
        jmp bh_info

bh_operation: .byte 0
bh_transfer_op: .byte 0
bh_error: .byte 0
bh_index: .byte 0
bh_live: .byte 0
bh_count: .byte 0
bh_cursor: .byte 0
bh_saved: .byte 0
bh_pending: .byte 0
bh_replay: .byte 0
bh_header: .fill H_HEADER,0
bh_offset: .fill 3,0
bh_written: .fill 3,0
bh_total: .fill 3,0
bh_next: .fill 3,0
bh_size: .fill 3,0
bh_records: .fill (H_STEPS+1)*9,0
