; Replace one validated logical span. An allocation failure leaves its bytes,
; gap and length unchanged. No allocation is needed when the replacement fits
; in the current gap plus the removed span, even if the heap is exhausted.
 .weak
DOC_REPLACE_SPAN24=0
 .endweak
doc_replace:
        lda d_replace_count+2
        bne doc_badarg
        lda d_replace_count+1
        cmp #2
        bcc +
        bne doc_badarg
        lda d_replace_count
        bne doc_badarg
+
.if DOC_REPLACE_SPAN24
        ; Selection removes a logical 24-bit span; only inserted payloads
        ; are bounded by the 512-byte transfer buffer. Ordinary read/insert
        ; calls retain their original bounded-count validation.
        jsr doc_context
        bcs doc_return
        jsr doc_position
.else
        jsr doc_prepare
.endif
        bcs doc_return
        #doc_sub3 d_pos,d_limit
        #doc_cmp3 d_limit,d_count
        bcc doc_range
doc_replace_check:
        #doc_load3 D_END,d_limit
        #doc_load3 D_GAP,d_at
        #doc_sub3 d_at,d_limit
        #doc_add3 d_count,d_limit
        #doc_cmp3 d_limit,d_replace_count
        bcs doc_replace_room
        jsr doc_grow
.if DOC_PARTIAL
        bcc doc_replace_check         ; a partial final chunk grows one page per call
        rts
.else
        bcs doc_return
.endif
doc_replace_room:
        jsr doc_seek_gap
        bcs doc_return
        #doc_load3 D_GAP,d_at
        #doc_copy3 d_replace_count,d_left
        jsr doc_write_input
        bcs doc_return
        #doc_store3 d_at,D_GAP
        #doc_load3 D_END,d_limit
        #doc_add3 d_count,d_limit
        #doc_store3 d_limit,D_END
        #doc_load3 D_LEN,d_limit
        #doc_sub3 d_count,d_limit
        #doc_add3 d_replace_count,d_limit
        #doc_store3 d_limit,D_LEN
        jmp doc_dirty
d_replace_count: .fill 3,0
