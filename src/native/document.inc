; Private native editor document model: two transactional document contexts.
; A document is a gap buffer over up to 24 owned 4 KiB allocations. Logical
; positions and length are 24-bit; allocated capacity is never logical data.
; Foreground only, decimal mode clear. No MMU or zero-page workspace is borrowed.
; d_slot = 0 / 128, d_pos = logical byte position, d_count = 1..512.
; doc_insert consumes d_input; doc_read returns d_actual bytes in d_output.
; doc_delete removes d_count bytes at d_pos. All preserve d_pos/d_count.
; doc_replace removes d_count bytes and writes d_replace_count (0..512) from
; d_input. It reserves any extra capacity before changing the original span.
; C/A follow the heap ABI. Allocation failure leaves the document unchanged.
; A transfer/handle failure poisons the context, preventing false save success.
.weak
DOC_INPUT_STORAGE=0
DOC_OUTPUT_STORAGE=0
DOC_STATE_STORAGE=0
DOC_TRANSIENT_STORAGE=0
DOC_EXTERNAL_MEMORY=0
DOC_COMPACT=0
DOC_HISTORY=0
DOC_PARTIAL=0                ; 1: a short final chunk may use a run below 4 KiB
doc_storage_read=N_READ
doc_storage_write=N_WRITE
.endweak
D_LEN = 0
D_GAP = 3
D_END = 6
D_CAP = 9
D_DIRTY = 12
D_CHUNKS = 13
D_FAULT = 14
D_BACKING = 15               ; 0 main RAM; 1 shared REU extent (opt-in)
D_HANDLES = 16
D_MAXCHUNKS = 24
D_TAILBANK = 112             ; DOC_PARTIAL: bank/page of the last chunk
D_TAILPAGE = 113

doc_copy3 .macro source,dest
 .if DOC_COMPACT
        #es_copy3 \source,\dest
 .else
        lda \source
        sta \dest
        lda \source+1
        sta \dest+1
        lda \source+2
        sta \dest+2
 .endif
.endm
doc_load3 .macro field, dest
        ldx d_slot
        lda d_states+\field,x
        sta \dest
        lda d_states+\field+1,x
        sta \dest+1
        lda d_states+\field+2,x
        sta \dest+2
.endm
doc_store3 .macro source, field
        ldx d_slot
        lda \source
        sta d_states+\field,x
        lda \source+1
        sta d_states+\field+1,x
        lda \source+2
        sta d_states+\field+2,x
.endm
doc_add3 .macro source,dest
 .if DOC_COMPACT
        #es_add3 \source,\dest
 .else
        clc
        lda \dest
        adc \source
        sta \dest
        lda \dest+1
        adc \source+1
        sta \dest+1
        lda \dest+2
        adc \source+2
        sta \dest+2
 .endif
.endm
doc_sub3 .macro source,dest
 .if DOC_COMPACT
        #es_sub3 \source,\dest
 .else
        sec
        lda \dest
        sbc \source
        sta \dest
        lda \dest+1
        sbc \source+1
        sta \dest+1
        lda \dest+2
        sbc \source+2
        sta \dest+2
 .endif
.endm
doc_cmp3 .macro left,right
 .if DOC_COMPACT
        #es_cmp3 \left,\right
 .else
        lda \left+2
        cmp \right+2
        bne +
        lda \left+1
        cmp \right+1
        bne +
        lda \left
        cmp \right
+
 .endif
.endm

doc_init:
        lda N_CURRENT
        sta d_owner
        lda #0
        tax
doc_init_loop:
        sta d_states,x
        inx
        bne doc_init_loop
        sta d_slot
doc_ok:
        lda #0
        clc
        rts
doc_badarg:
        lda #N_BADARG
        sec
        rts
doc_range:
        lda #N_RANGE
        sec
        rts
doc_corrupt:
        lda #N_CORRUPT
        sec
        rts
doc_fault:
        ldx d_slot
        sta d_states+D_FAULT,x
        sec
        rts
doc_context:
        lda d_slot
        and #$7f
        bne doc_badarg
        ldx d_slot
.if DOC_EXTERNAL_MEMORY
        lda d_states+D_BACKING,x
        cmp #2
        bcs doc_corrupt
        cmp #1
        bne +
        lda d_states+D_CHUNKS,x
        cmp #1
        bne doc_corrupt
+
.endif
        lda d_states+D_FAULT,x
        bne doc_corrupt
        jmp doc_ok
doc_prepare:
        jsr doc_context
        bcs doc_return
        lda #0
        sta d_count+2
        lda d_count+1
        cmp #2
        bcc doc_count_small
        bne doc_badarg
        lda d_count
        bne doc_badarg
doc_count_small:
        lda d_count
        ora d_count+1
        beq doc_badarg
doc_position:
        #doc_load3 D_LEN,d_limit
        #doc_cmp3 d_limit,d_pos
        bcc doc_range
        jmp doc_ok
doc_return:
        rts

; Free only this context's chunks, retaining any uncertain/unfreed handles.
; It also permits retrying cleanup of a poisoned context.
doc_dispose:
        lda d_slot
        and #$7f
        bne doc_badarg
        ldx d_slot
.if DOC_EXTERNAL_MEMORY
        lda d_states+D_BACKING,x
        bne dm_dispose
.endif
        lda d_states+D_CHUNKS,x
        cmp #D_MAXCHUNKS+1
        bcs doc_corrupt
        sta d_index
doc_dispose_loop:
        lda d_index
        beq doc_disposed
        dec d_index
        jsr doc_handle_index
        lda d_states+D_HANDLES,x
        beq doc_dispose_loop
        jsr doc_get_handle
        jsr N_FREE
        bcs doc_fault
        jsr doc_handle_index
        lda #0
        sta d_states+D_HANDLES,x
        sta d_states+D_HANDLES+1,x
        sta d_states+D_HANDLES+2,x
        sta d_states+D_HANDLES+3,x
        jmp doc_dispose_loop
doc_disposed:
        ldx d_slot
        ldy #128
        lda #0
doc_clear_context:
        sta d_states,x
        inx
        dey
        bne doc_clear_context
        jmp doc_ok

doc_handle_index:
        lda d_index
        asl
        asl
        clc
        adc d_slot
        tax
        rts
doc_get_handle:
        lda d_owner
        sta N_OWNER
.if DOC_COMPACT
        ldy #0
-       lda d_states+D_HANDLES,x
        sta N_HANDLE,y
        inx
        iny
        cpy #4
        bne -
.else
        lda d_states+D_HANDLES,x
        sta N_HANDLE
        lda d_states+D_HANDLES+1,x
        sta N_HANDLE+1
        lda d_states+D_HANDLES+2,x
        sta N_HANDLE+2
        lda d_states+D_HANDLES+3,x
        sta N_HANDLE+3
.endif
        rts

; Select a physical range already bounded by the caller to one 4 KiB chunk.
doc_select:
.if DOC_EXTERNAL_MEMORY
        ldx d_slot
        lda d_states+D_BACKING,x
        bne dm_select
.endif
        lda d_at+2
        asl
        asl
        asl
        asl
        sta d_index
        lda d_at+1
        lsr
        lsr
        lsr
        lsr
        ora d_index
        sta d_index
        ldx d_slot
        cmp d_states+D_CHUNKS,x
        bcs doc_corrupt
        jsr doc_handle_index
        jsr doc_get_handle
        lda d_at
        sta N_OFFSET
        lda d_at+1
        and #15
        sta N_OFFSET+1
        lda d_n
        sta N_COUNT
        lda d_n+1
        sta N_COUNT+1
        jmp doc_ok

; n = min(left,512); limit helpers reduce it at source/destination boundaries.
doc_size:
        lda #0
        sta d_n
        sta d_n+2
        lda #2
        sta d_n+1
        lda d_left+2
        bne doc_size_done
        lda d_left+1
        cmp #2
        bcs doc_size_done
        lda d_left
        sta d_n
        lda d_left+1
        sta d_n+1
doc_size_done:
        rts
doc_forward_limit:
        lda d_at+1
        and #15
        sta d_bound+1
        sec
        lda #0
        sbc d_at
        sta d_bound
        lda #16
        sbc d_bound+1
        sta d_bound+1
        jmp doc_bound_limit
doc_backward_limit:
        lda d_at
        sta d_bound
        lda d_at+1
        and #15
        sta d_bound+1
        ora d_bound
        bne doc_bound_limit
        lda #16
        sta d_bound+1
doc_bound_limit:
        lda d_bound+1
        cmp d_n+1
        bcc doc_use_bound
        bne doc_bound_done
        lda d_bound
        cmp d_n
        bcs doc_bound_done
doc_use_bound:
        lda d_bound
        sta d_n
        lda d_bound+1
        sta d_n+1
doc_bound_done:
        rts

doc_move_forward:
        lda d_left
        ora d_left+1
        ora d_left+2
        beq doc_move_done
        jsr doc_size
        #doc_copy3 d_src,d_at
        jsr doc_forward_limit
        #doc_copy3 d_dst,d_at
        jsr doc_forward_limit
        jsr doc_move_piece
        bcs doc_return
        #doc_add3 d_n,d_src
        #doc_add3 d_n,d_dst
        #doc_sub3 d_n,d_left
        jmp doc_move_forward
doc_move_backward:
        lda d_left
        ora d_left+1
        ora d_left+2
        beq doc_move_done
        jsr doc_size
        #doc_copy3 d_src,d_at
        jsr doc_backward_limit
        #doc_copy3 d_dst,d_at
        jsr doc_backward_limit
        #doc_sub3 d_n,d_src
        #doc_sub3 d_n,d_dst
        jsr doc_move_piece
        bcs doc_return
        #doc_sub3 d_n,d_left
        jmp doc_move_backward
doc_move_done:
        jmp doc_ok
doc_move_piece:
        #doc_copy3 d_src,d_at
        jsr doc_select
        bcs doc_fault
        jsr doc_storage_read
        bcs doc_fault
        #doc_copy3 d_dst,d_at
        jsr doc_select
        bcs doc_fault
        jsr doc_storage_write
        bcs doc_fault
        rts

; Relocate the gap only for edits. The editor's cursor/viewport can move freely
; without copying document data. Public operations validate d_pos first.
doc_seek_gap:
        #doc_load3 D_GAP,d_dst
        #doc_cmp3 d_pos,d_dst
        beq doc_move_done
        bcc doc_seek_left
        #doc_load3 D_END,d_src
        #doc_copy3 d_pos,d_left
        #doc_sub3 d_dst,d_left
        jsr doc_move_forward
        bcs doc_return
        #doc_store3 d_dst,D_GAP
        #doc_store3 d_src,D_END
        jmp doc_ok
doc_seek_left:
        #doc_copy3 d_dst,d_src
        #doc_load3 D_END,d_dst
        #doc_copy3 d_src,d_left
        #doc_sub3 d_pos,d_left
        jsr doc_move_backward
        bcs doc_return
        #doc_store3 d_src,D_GAP
        #doc_store3 d_dst,D_END
        jmp doc_ok

doc_grow:
        ldx d_slot
.if DOC_EXTERNAL_MEMORY
        lda d_states+D_BACKING,x
        bne dm_grow
        lda d_states+D_CHUNKS,x
        bne +
        lda dm_mode
        cmp #2
        beq dm_grow
+
.endif
.if DOC_PARTIAL
        ; A final chunk below 4 KiB grows in place of appending: positions map
        ; to chunks by P >> 12, so no chunk may follow an unaligned capacity.
        lda d_states+D_CAP+1,x
        and #15
        bne doc_regrow
.endif
        lda d_states+D_CHUNKS,x
        cmp #D_MAXCHUNKS
        bcc doc_allocate
doc_nomem:
        lda #N_NOMEM
        sec
        rts
doc_allocate:
        lda #16
        jsr doc_alloc_run
.if DOC_PARTIAL
        bcc doc_allocated
        ; No complete 4 KiB run is left: start a one-page final chunk. It grows
        ; a page at a time, so it holds exactly what the document needs and
        ; leaves the rest of RAM to the picker and other services.
        lda #1
        jsr doc_alloc_run
.endif
        bcc doc_allocated
doc_alloc_failed:
        rts
; A = pages. C clear with N_HANDLE, or C set with the kernel error in A.
doc_alloc_run:
        sta d_pages
doc_alloc_again:
        lda d_owner
        sta N_OWNER
        lda d_pages
        sta N_PAGES
        lda #$ff
        sta N_BANK
        jsr N_ALLOC
.if DOC_HISTORY
        bcc +
        pha
        jsr eh_relieve
        pla
        bcc doc_alloc_again
+
.endif
        rts
.if DOC_PARTIAL
; Grow the short final chunk (A = its p pages) in place: free it and reserve
; the same start one page longer. The kernel keeps RAM contents across free and
; reserve, and nothing allocates in between (foreground only, no IRQ calls),
; so the bytes never move and the chunk never fragments RAM. If the next page
; is taken, the original range (just freed) is reserved again and growth is
; refused. A failed free or restore poisons the context.
doc_regrow:
        sta d_bound
        ldy d_states+D_CHUNKS,x
        dey
        sty d_index
        jsr doc_handle_index
        jsr doc_get_handle
        jsr N_FREE
        bcs doc_regrow_fault
        lda #1
        sta d_pages                   ; one page longer, then the old length
doc_regrow_reserve:
        ldx d_slot
        lda d_owner
        sta N_OWNER
        lda d_states+D_TAILBANK,x
        sta N_BANK
        lda d_states+D_TAILPAGE,x
        sta N_PAGE
        lda d_bound
        clc
        adc d_pages
        sta N_PAGES
        jsr N_RESERVE
        bcc doc_regrow_kept
        dec d_pages
        beq doc_regrow_reserve        ; restore the range just freed
doc_regrow_fault:
        jmp doc_fault
doc_regrow_kept:
        ldx d_slot
        dec d_states+D_CHUNKS,x
        lda d_pages
        bne doc_allocated             ; one page longer: record it, shift the tail
        jsr doc_keep_handle           ; restored: new generation, same bytes
        jmp doc_nomem
.endif
doc_allocated:
.if DOC_PARTIAL
        jsr doc_keep_handle
        jmp doc_grown
; Append N_HANDLE (N_BANK/N_PAGE from N_ALLOC or N_RESERVE) as the last chunk.
doc_keep_handle:
        ldx d_slot
        lda N_BANK
        sta d_states+D_TAILBANK,x
        lda N_PAGE
        sta d_states+D_TAILPAGE,x
.else
        ldx d_slot
.endif
        lda d_states+D_CHUNKS,x
        sta d_index
        inc d_states+D_CHUNKS,x
        jsr doc_handle_index
.if DOC_COMPACT
        ldy #0
-       lda N_HANDLE,y
        sta d_states+D_HANDLES,x
        inx
        iny
        cpy #4
        bne -
.else
        lda N_HANDLE
        sta d_states+D_HANDLES,x
        lda N_HANDLE+1
        sta d_states+D_HANDLES+1,x
        lda N_HANDLE+2
        sta d_states+D_HANDLES+2,x
        lda N_HANDLE+3
        sta d_states+D_HANDLES+3,x
.endif
.if DOC_PARTIAL
        rts
.endif
doc_grown:
        #doc_load3 D_CAP,d_src
        #doc_copy3 d_src,d_dst
        clc
        lda d_dst+1
.if DOC_PARTIAL
        adc d_pages
.else
        adc #16
.endif
        sta d_dst+1
        bcc +
        inc d_dst+2
+       #doc_store3 d_dst,D_CAP
        #doc_copy3 d_src,d_left
        #doc_load3 D_END,d_at
        #doc_sub3 d_at,d_left
        jsr doc_move_backward
        bcs doc_return
        ; Destination is the old gap end plus one page group after the copy.
        #doc_store3 d_dst,D_END
        jmp doc_ok

doc_insert:
        jsr doc_prepare
        bcs doc_return
doc_insert_check:
        #doc_load3 D_END,d_limit
        #doc_load3 D_GAP,d_at
        #doc_sub3 d_at,d_limit
        #doc_cmp3 d_limit,d_count
        bcs doc_insert_room
        jsr doc_grow
.if DOC_PARTIAL
        bcc doc_insert_check          ; a partial final chunk grows one page per call
        rts
.else
        bcs doc_return
.endif
doc_insert_room:
        jsr doc_seek_gap
        bcs doc_return
        #doc_load3 D_GAP,d_at
        #doc_copy3 d_count,d_left
        jsr doc_write_input
        bcs doc_return
        #doc_store3 d_at,D_GAP
        #doc_load3 D_LEN,d_limit
        #doc_add3 d_count,d_limit
        #doc_store3 d_limit,D_LEN
doc_dirty:
        ldx d_slot
        lda #1
        sta d_states+D_DIRTY,x
        jmp doc_ok

; Write d_left bytes at d_at without publishing new logical document bounds.
; A failed heap transfer poisons the context, as with a failed gap move.
doc_write_input:
        lda #0
        sta d_actual
        sta d_actual+1
        lda d_left
        ora d_left+1
        beq doc_write_done
doc_insert_loop:
        jsr doc_size
        jsr doc_forward_limit
        jsr doc_input_to_buffer
        jsr doc_select
        bcs doc_fault
        jsr doc_storage_write
        bcs doc_fault
        #doc_add3 d_n,d_at
        #doc_sub3 d_n,d_left
        jsr doc_actual_add
        lda d_left
        ora d_left+1
        bne doc_insert_loop
doc_write_done:
        jmp doc_ok

doc_delete:
        jsr doc_prepare
        bcs doc_return
        #doc_sub3 d_pos,d_limit
        #doc_cmp3 d_limit,d_count
        bcc doc_range
        jsr doc_seek_gap
        bcs doc_return
        #doc_load3 D_END,d_limit
        #doc_add3 d_count,d_limit
        #doc_store3 d_limit,D_END
        #doc_load3 D_LEN,d_limit
        #doc_sub3 d_count,d_limit
        #doc_store3 d_limit,D_LEN
        jmp doc_dirty

.weak
DOC_REPLACE_EXTERNAL = 0
.endweak
.if !DOC_REPLACE_EXTERNAL
.include "document-replace.inc"
.endif

doc_read:
        jsr doc_prepare
        bcs doc_return
        #doc_copy3 d_limit,d_left
        #doc_sub3 d_pos,d_left
        #doc_cmp3 d_left,d_count
        bcc doc_read_short
        #doc_copy3 d_count,d_left
doc_read_short:
        #doc_copy3 d_pos,d_cur
        lda #0
        sta d_actual
        sta d_actual+1
doc_read_loop:
        lda d_left
        ora d_left+1
        beq doc_move_done
        jsr doc_size
        #doc_copy3 d_cur,d_at
        #doc_load3 D_GAP,d_limit
        #doc_cmp3 d_cur,d_limit
        bcs doc_read_after_gap
        #doc_sub3 d_cur,d_limit
        lda d_limit+2
        bne doc_read_mapped
        lda d_limit
        sta d_bound
        lda d_limit+1
        sta d_bound+1
        jsr doc_bound_limit
        jmp doc_read_mapped
doc_read_after_gap:
        #doc_load3 D_END,d_bound3
        #doc_sub3 d_limit,d_bound3
        #doc_add3 d_bound3,d_at
doc_read_mapped:
        jsr doc_forward_limit
        jsr doc_select
        bcs doc_fault
        jsr doc_storage_read
        bcs doc_fault
        jsr doc_buffer_to_output
        #doc_add3 d_n,d_cur
        #doc_sub3 d_n,d_left
        jsr doc_actual_add
        jmp doc_read_loop

doc_actual_add:
        clc
        lda d_actual
        adc d_n
        sta d_actual
        lda d_actual+1
        adc d_n+1
        sta d_actual+1
        rts
doc_input_to_buffer:
        clc
        lda #<d_input
        adc d_actual
        sta doc_local_read+1
        lda #>d_input
        adc d_actual+1
        sta doc_local_read+2
        lda #<N_BUFFER
        sta doc_local_write+1
        lda #>N_BUFFER
        sta doc_local_write+2
        jmp doc_local_copy
doc_buffer_to_output:
        lda #<N_BUFFER
        sta doc_local_read+1
        lda #>N_BUFFER
        sta doc_local_read+2
        clc
        lda #<d_output
        adc d_actual
        sta doc_local_write+1
        lda #>d_output
        adc d_actual+1
        sta doc_local_write+2
doc_local_copy:
        lda d_n
        sta d_bytes
        lda d_n+1
        sta d_bytes+1
        ldx #0
doc_local_read:
        lda $ffff,x
doc_local_write:
        sta $ffff,x
        inx
        bne +
        inc doc_local_read+2
        inc doc_local_write+2
+       lda d_bytes
        bne +
        dec d_bytes+1
+       dec d_bytes
        lda d_bytes
        ora d_bytes+1
        bne doc_local_read
        rts

.if DOC_TRANSIENT_STORAGE
d_slot=DOC_TRANSIENT_STORAGE
d_owner=d_slot+1
d_pos=d_slot+2
d_count=d_slot+5
d_actual=d_slot+8
d_at=d_slot+10
d_cur=d_slot+13
d_src=d_slot+16
d_dst=d_slot+19
d_left=d_slot+22
d_n=d_slot+25
d_limit=d_slot+28
d_bound3=d_slot+31
d_bound=d_slot+34
d_bytes=d_slot+36
d_index=d_slot+38
d_pages=d_slot+39
.else
d_slot: .byte 0
d_owner: .byte 0
d_pos: .fill 3,0
d_count: .fill 3,0
d_actual: .word 0
d_at: .fill 3,0
d_cur: .fill 3,0
d_src: .fill 3,0
d_dst: .fill 3,0
d_left: .fill 3,0
d_n: .fill 3,0
d_limit: .fill 3,0
d_bound3: .fill 3,0
d_bound: .word 0
d_bytes: .word 0
d_index: .byte 0
d_pages: .byte 0
.endif
.if DOC_STATE_STORAGE
d_states=DOC_STATE_STORAGE
.else
d_states: .fill 256,0
.endif
.if DOC_INPUT_STORAGE
d_input=DOC_INPUT_STORAGE
.else
d_input: .fill 512,0
.endif
.if DOC_OUTPUT_STORAGE
d_output=DOC_OUTPUT_STORAGE
.else
d_output: .fill 512,0
.endif
