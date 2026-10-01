; Select storage at the input loop before any document stream can be open.
; A clean optional-service refusal keeps RAM documents; an uncertain restore
; retains the provider and blocks input until Escape can close the lease.
.include "../shared-memory-api.inc"
dm_ensure:
        lda dm_mode
        bne dm_ok
        inc dm_mode
        lda bk_state
        bne dm_check
        jsr bp_load
        bcs dm_optional_close
dm_check:
        lda #H_INFO
        jsr bk_call
        bcs dm_optional_close
        lda N_BUFFER+3
        cmp #1
        bne dm_optional_close
        ldx ed_active
        lda d_states+D_DIRTY,x
        sta N_BUFFER
        lda #H_CLEAR
        jsr bk_call
        bcs dm_optional_close
        lda #1
        sta eh_available
        lda #SM_INFO
        jsr bk_call
        bcs dm_optional_close
        lda SM_TOKEN
        cmp #SM_VERSION
        bne dm_optional_close
        lda #1
        sta dm_lease
        lda #SM_OPEN
        jsr bk_call
        bcs dm_stop
        inc dm_mode
dm_ok:
        lda #0
        clc
        rts
dm_optional_close:
        lda bp_started
        bne dm_ok
        jmp vd_close
dm_stop:
        lda dm_lease
        beq dm_ok
        lda #SM_CLOSE
        jsr bk_call
        bcs dm_failed
        lda #0
        sta dm_lease
        sta dm_fault
        jmp dm_optional_close
dm_failed:
        sta dm_fault
        sec
        rts
dm_cleanup:
        jsr eh_close
        bcs dm_return
        lda #0
        sta d_slot
        jsr doc_dispose
        bcs dm_return
        lda #128
        sta d_slot
        jsr doc_dispose
        bcs dm_return
        jsr dm_stop
        bcs dm_return
        jmp vd_close
dm_return:
        rts

dm_dispose:
        cmp #1
        bne doc_corrupt
        lda d_states+D_CHUNKS,x
        cmp #1
        bne doc_corrupt
        jsr dm_select
        lda #SM_FREE
        jsr bk_call
        bcs doc_fault
        jmp doc_disposed
dm_select:
        lda d_slot
        clc
        adc #7
        tax
        ldy #7
-       lda d_states+D_HANDLES,x
        sta SM_TOKEN,y
        dex
        dey
        bpl -
        ldx #2
-       lda d_at,x
        sta SM_OFFSET,x
        dex
        bpl -
        lda d_n
        sta SM_COUNT
        lda d_n+1
        sta SM_COUNT+1
        jmp doc_ok
dm_read:
        ldx d_slot
        lda d_states+D_BACKING,x
        beq +
        lda #SM_READ
        jmp bk_call
+       jmp N_READ
dm_write:
        ldx d_slot
        lda d_states+D_BACKING,x
        beq +
        lda #SM_WRITE
        jmp bk_call
+       jmp N_WRITE
dm_grow:
        jsr dm_select
        ldx d_slot
        lda d_states+D_CAP+1,x
        sta SM_PAGES
        lda d_states+D_CAP+2,x
        sta SM_PAGES+1
        ldy #4
-       lsr SM_PAGES+1
        ror SM_PAGES
        dey
        bne -
        inc SM_PAGES
        bne +
        inc SM_PAGES+1
+       lda SM_PAGES+1
        cmp #16              ; capacity must remain representable in 24 bits
        bcs doc_nomem
        lda d_states+D_BACKING,x
        beq +
        lda #SM_RESIZE
        bne ++
+       lda #SM_ALLOC
+       jsr bk_call
        bcs dm_return
        ldx d_slot
        lda #1
        sta d_states+D_BACKING,x
        sta d_states+D_CHUNKS,x
        ldy #0
-       lda SM_TOKEN,y
        sta d_states+D_HANDLES,x
        inx
        iny
        cpy #8
        bne -
.if DOC_PARTIAL
        lda #16              ; one 4 KiB unit (doc_grown adds d_pages)
        sta d_pages
.endif
        jmp doc_grown
dm_mode: .byte 0              ; 0 undecided, 1 RAM, 2 shared REU
dm_lease: .byte 0
dm_fault: .byte 0
