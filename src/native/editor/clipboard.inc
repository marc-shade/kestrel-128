; A third checked module stages clipboard transfers while the renderer is
; unloaded. All selection bounds and document contexts remain in the core.
ec_entry:
        lda ed_clip_key
        bne +
        jmp dl_claim
+       cmp #16
        bne +
        jmp ep_print
+
        lda #0
        sta ec_history
        sta ec_left+2
        lda ed_active
        sta d_slot
        lda ed_clip_key
        cmp #26
        beq ec_undo
        cmp #25
        beq ec_undo
        cmp #21
        beq ec_forget
        cmp #11
        bne +
        jsr cp_clear
        bcs ec_error
        lda #26
        jmp ec_status
+       #es_copy3 ed_cursor,ec_start
        lda #0
        sta ec_remove
        sta ec_remove+1
        sta ec_remove+2
        lda es_active
        beq +
        #es_copy3 es_first,ec_start
        #es_copy3 es_limit,ec_remove
        #es_sub3 es_first,ec_remove
+       lda ed_clip_key
        cmp #22
        beq ec_paste
        lda ec_remove
        ora ec_remove+1
        ora ec_remove+2
        bne +
        lda #22
        jmp ec_status
+       #es_copy3 ec_remove,cp_length
        jsr cp_begin
        bcs ec_copy_failed
        #es_copy3 ec_start,ec_position
ec_copy_loop:
        #es_copy3 ec_position,d_pos
        sec
        lda CB_EXPECTED
        sbc CB_WRITTEN
        sta ec_left
        lda CB_EXPECTED+1
        sbc CB_WRITTEN+1
        sta ec_left+1
        jsr ec_chunk
        lda cp_count
        sta d_count
        lda cp_count+1
        sta d_count+1
        lda #0
        sta d_count+2
        jsr doc_read
        bcs ec_copy_abort
        lda #<d_output
        ldx #>d_output
        jsr ec_copy_buffer
        jsr cp_write
        bcs ec_copy_abort
        clc
        lda ec_position
        adc cp_count
        sta ec_position
        lda ec_position+1
        adc cp_count+1
        sta ec_position+1
        bcc +
        inc ec_position+2
+       lda CB_WRITTEN
        cmp CB_EXPECTED
        bne ec_copy_loop
        lda CB_WRITTEN+1
        cmp CB_EXPECTED+1
        bne ec_copy_loop
        jsr cp_commit
        bcs ec_copy_abort
        lda ed_clip_key
        cmp #24
        beq ec_cut
        lda #20
        jmp ec_status
ec_copy_abort:
        pha
        jsr cp_abort
        pla
ec_copy_failed:
        cmp #N_RANGE
        bne ec_error
        lda #24
        jmp ec_status
ec_cut:
        lda #0
        sta ec_insert
        sta ec_insert+1
        sta ec_insert+2
        jsr eh_clip
        bcs ec_error
        lda #20
        jmp ec_changed
ec_paste:
        jsr cp_info
        bcs ec_error
        lda cp_format
        cmp #CB_TEXT
        beq +
        lda #23
        jmp ec_status
+       lda cp_length+2
        bne ec_error
        lda cp_length+1
        cmp #>CB_MAX_BYTES
        bcc +
        bne ec_error
        lda cp_length
        bne ec_error
+       #es_copy3 cp_length,ec_insert
        jsr eh_clip
        bcs ec_error
        lda #21
ec_changed:
        pha
        #es_copy3 ec_start,ed_cursor
        #es_add3 ec_insert,ed_cursor
        jsr es_clear
        lda #1
        sta ed_document_changed
        sta ed_structure
        pla
ec_status:
        sta ed_status
        clc
        rts
ec_error:
        ldx d_slot
        ldy d_states+D_FAULT,x
        beq +
        lda #5
        jmp ec_status
+       ldx #25
        cmp #N_NOMEM
        beq +
        cmp #N_NOSLOT
        bne ++
+       ldx #3
+       stx ed_status
        clc
        rts

ec_forget:
        ldx ed_active
        lda d_states+D_DIRTY,x
        sta N_BUFFER
        lda #H_CLEAR
        jsr bk_call
        bcs ec_error
        lda #29
        jmp ec_status
ec_undo:
        lda eh_available
        beq ec_no_history
        lda ed_active
        sta d_slot
        jsr doc_context
        bcs ec_error
        lda #H_UNDO
        ldx ed_clip_key
        cpx #26
        beq +
        lda #H_REDO
+       jsr bk_call
        bcs ec_no_history
        inc ec_history
        ldx #8
-       lda N_BUFFER,x
        sta ec_start,x
        dex
        bpl -
        jsr ec_replace
        bcc +
        pha
        lda #H_ABORT
        jsr bk_call
        pla
        jmp ec_error
+       lda #H_APPLIED
        jsr bk_call
        bcs ec_fault
        ldx ed_active
        lda N_BUFFER
        sta d_states+D_DIRTY,x
        lda #27
        ldx ed_clip_key
        cpx #26
        beq +
        lda #28
+       jmp ec_changed
ec_no_history:
        lda #31
        jmp ec_status

; Reserve capacity before removing any logical bytes. The source is read in
; bounded chunks. As with ordinary document writes, an uncertain transfer
; poisons the document and prevents a false successful Save As.
ec_replace:
        #es_copy3 ec_start,d_pos
        #es_copy3 ec_remove,d_count
        jsr doc_context
        bcs ec_return
        jsr doc_position
        bcs ec_return
        #doc_sub3 d_pos,d_limit
        #doc_cmp3 d_limit,d_count
        bcc ec_range
ec_reserve:
        #doc_load3 D_END,d_limit
        #doc_load3 D_GAP,d_at
        #doc_sub3 d_at,d_limit
        #doc_add3 ec_remove,d_limit
        #doc_cmp3 d_limit,ec_insert
        bcs ec_room
        jsr doc_grow
        bcs ec_return
        jmp ec_reserve
ec_room:
        jsr doc_seek_gap
        bcs ec_return
        #doc_load3 D_GAP,ec_dest
        lda #0
        sta ec_offset
        sta ec_offset+1
        sta ec_offset+2
ec_paste_loop:
        sec
        lda ec_insert
        sbc ec_offset
        sta ec_left
        lda ec_insert+1
        sbc ec_offset+1
        sta ec_left+1
        lda ec_insert+2
        sbc ec_offset+2
        sta ec_left+2
        ora ec_left+1
        ora ec_left
        beq ec_publish
        jsr ec_chunk
        lda ec_history
        beq +
        lda cp_count
        sta H_COUNT
        lda cp_count+1
        sta H_COUNT+1
        lda #H_READ
        jsr bk_call
        jmp ++
+       #es_copy3 ec_offset,cp_offset
        jsr cp_read
+
        bcs ec_fault
        ldx #0
-       lda N_BUFFER,x
        sta d_input,x
        lda N_BUFFER+256,x
        sta d_input+256,x
        inx
        bne -
        #es_copy3 ec_dest,d_at
        lda cp_count
        sta d_left
        lda cp_count+1
        sta d_left+1
        lda #0
        sta d_left+2
        jsr doc_write_input
        bcs ec_return
        #es_copy3 d_at,ec_dest
        clc
        lda ec_offset
        adc cp_count
        sta ec_offset
        lda ec_offset+1
        adc cp_count+1
        sta ec_offset+1
        bcc +
        inc ec_offset+2
+
        jmp ec_paste_loop
ec_publish:
        #doc_store3 ec_dest,D_GAP
        #doc_load3 D_END,d_limit
        #doc_add3 ec_remove,d_limit
        #doc_store3 d_limit,D_END
        #doc_load3 D_LEN,d_limit
        #doc_sub3 ec_remove,d_limit
        #doc_add3 ec_insert,d_limit
        #doc_store3 d_limit,D_LEN
        jmp doc_dirty
ec_fault:
        jmp doc_fault
ec_range:
        lda #N_RANGE
        sec
ec_return:
        rts
ec_chunk:
        lda ec_left+2
        bne ec_chunk_full
        lda ec_left
        ldx ec_left+1
        cpx #2
        bcc +
ec_chunk_full:
        lda #0
        ldx #2
+       sta cp_count
        stx cp_count+1
        rts
; Copy two pages; cp_count bounds what the clipboard is permitted to publish.
ec_copy_buffer:
        sta ec_source+1
        stx ec_source+2
        ldy #0
        ldx #2
ec_source:
        lda $ffff,y
ec_target:
        sta N_BUFFER,y
        iny
        bne ec_source
        inc ec_source+2
        inc ec_target+2
        dex
        bne ec_source
        lda #>N_BUFFER
        sta ec_target+2
        rts
ec_start: .fill 3,0
ec_remove: .fill 3,0
ec_insert: .fill 3,0
ec_position: .fill 3,0
ec_dest: .fill 3,0
ec_offset: .fill 3,0
ec_left: .fill 3,0
ec_history: .byte 0
.include "../clipboard.inc"
DL_KIND=1
DL_NAME=ed_field
DL_LENGTH=ed_field_len
DL_DEVICE=ed_device
DL_FORMAT=ed_format
DL_TYPE=ed_file_type
.include "../document-launch.inc"
