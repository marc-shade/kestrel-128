; Literal search over the logical document cache. KMP bounds repeated-prefix
; work per input byte; 24-bit positions include files beyond 64 KiB. Queries
; and replacements are printable field bytes, at most 64, with ASCII folding.
ed_search_entry:
        lda ed_s_request
        cmp #14
        beq ed_find_next
        cmp #18
        beq ed_replace_prompt
ed_find_prompt:
        lda #6
        bne ed_search_prompt
ed_replace_prompt:
        lda #7
ed_search_prompt:
        sta ed_mode
        lda ed_s_case
        sta ed_s_pending_case
        ldx ed_s_length
        stx ed_field_len
        lda #0
        sta ed_field,x
ed_search_prefill:
        dex
        bmi ed_search_field
        lda ed_s_query,x
        sta ed_field,x
        jmp ed_search_prefill
ed_search_field:
        lda #0
        sta ed_status
        sta N_UIKEY
        jsr ed_field_call
        bcs ed_input_error
        jmp ed_field_refresh
ed_search_case:
        lda ed_s_pending_case
        eor #1
        sta ed_s_pending_case
        jmp ed_field_refresh
ed_search_enter:
        lda ed_s_pending_case
        sta ed_s_case
        ldx ed_field_len
        stx ed_s_length
ed_search_accept:
        dex
        lda ed_field,x
        sta ed_s_query,x
        jsr ed_search_fold
        sta ed_s_pattern,x
        txa
        bne ed_search_accept
        jsr ed_search_prefix
        lda ed_mode
        cmp #6
        beq ed_find_first
        lda #8
        jmp ed_prompt_begin
ed_replacement_enter:
        ldx ed_field_len
        stx ed_s_new_length
ed_replacement_copy:
        dex
        bmi ed_replacement_ready
        lda ed_field,x
        sta ed_s_replacement,x
        jmp ed_replacement_copy
ed_replacement_ready:
        lda #9
        sta ed_mode
        jmp ed_field_refresh
ed_replace_choice:
        and #$df
        cmp #$4f
        beq ed_replace_one
        cmp #$41
        bne cloop
        lda #2
        bne ed_search_start
ed_replace_one:
        lda #1
        bne ed_search_start
ed_find_next:
        lda ed_s_length
        beq ed_find_prompt
        ; A file picker may have replaced this module since the last search.
        ldx ed_s_length
ed_search_rebuild:
        dex
        lda ed_s_query,x
        jsr ed_search_fold
        sta ed_s_pattern,x
        txa
        bne ed_search_rebuild
        jsr ed_search_prefix
        lda #3
        bne ed_search_start
ed_find_first:
        lda #0
ed_search_start:
        sta ed_s_action          ; 0=find, 1=replace one, 2=all, 3=next
.if NATIVE_EDITOR_GRAPHICS
        jsr es_clear
.endif
        lda ed_active
        sta d_slot
        #doc_load3 D_LEN,ed_length
        lda #0
        sta ed_mode
        sta ed_s_count
        sta ed_s_count+1
        sta ed_s_count+2
        sta ed_s_wrapped
        sta ed_s_ticks
        sta ed_s_matched
        sta ed_goal_valid
        lda #16
        sta ed_status
.if !NATIVE_EDITOR_GRAPHICS
        jsr ed_paint_fields
.endif
        #ed_move3 ed_cursor,ed_probe
        lda ed_s_action
        cmp #2
        bne +
        lda #0
        sta ed_probe
        sta ed_probe+1
        sta ed_probe+2
+       cmp #3
        bne +
        #doc_cmp3 ed_probe,ed_length
        bcs +
        #doc_add3 ed_one,ed_probe
+       #ed_move3 ed_probe,ed_s_start
        #ed_move3 ed_length,ed_s_limit
.if NATIVE_EDITOR_GRAPHICS
        ; Publish the actual starting byte and stop a failed first redraw
        ; before scanning or replacing anything in the document.
        jsr ed_paint_fields
        jsr ed_cancel_check
        bcs ed_search_cancel
.endif
ed_search_scan:
        #doc_cmp3 ed_probe,ed_s_limit
        bcs ed_search_exhausted
        jsr ed_byte_at
        bcs ed_search_read_error
        jsr ed_search_fold
        sta ed_s_byte
        ldx ed_s_matched
ed_search_compare:
        cmp ed_s_pattern,x
        beq ed_search_equal
        cpx #0
        beq ed_search_advance
        lda ed_s_prefix-1,x
        tax
        lda ed_s_byte
        jmp ed_search_compare
ed_search_equal:
        inx
ed_search_advance:
        stx ed_s_matched
        #doc_add3 ed_one,ed_probe
        inc ed_s_ticks
        bne +
        jsr ed_paint_fields
        jsr ed_cancel_check
        bcs ed_search_cancel
+       lda ed_s_matched
        cmp ed_s_length
        bne ed_search_scan
        #ed_move3 ed_probe,ed_s_match
        #doc_sub3 ed_s_length,ed_s_match
        lda ed_s_action
        beq ed_search_found
        cmp #3
        beq ed_search_found
        jsr ed_search_replace
        bcs ed_search_replace_error
        #doc_add3 ed_one,ed_s_count
        #ed_move3 ed_s_match,ed_cursor
        lda ed_s_action
        cmp #1
        beq ed_search_replaced
        #ed_move3 ed_s_match,ed_probe
        #doc_add3 ed_s_new_length,ed_probe
        #ed_move3 ed_length,ed_s_limit
        lda #0
        sta ed_s_matched
        jsr ed_cancel_check
        bcs ed_search_cancel
        jmp ed_search_scan
ed_search_exhausted:
        lda ed_s_action
        cmp #2
        beq ed_search_replaced
        lda ed_s_wrapped
        bne ed_search_not_found
        inc ed_s_wrapped
        lda ed_s_start
        ora ed_s_start+1
        ora ed_s_start+2
        beq ed_search_not_found
        ; Include tails of matches starting before the original cursor. A
        ; start-only upper bound would miss overlaps crossing that position.
        #ed_move3 ed_s_start,ed_s_limit
        #doc_add3 ed_s_length,ed_s_limit
        #doc_sub3 ed_one,ed_s_limit
        #doc_cmp3 ed_s_limit,ed_length
        bcc +
        #ed_move3 ed_length,ed_s_limit
+       lda #0
        sta ed_probe
        sta ed_probe+1
        sta ed_probe+2
        sta ed_s_matched
        jmp ed_search_scan
ed_search_found:
        #ed_move3 ed_s_match,ed_cursor
        lda #13
        clc
        adc ed_s_wrapped
        bne ed_search_finish
ed_search_not_found:
        lda #15
        bne ed_search_finish
ed_search_replaced:
        lda #17
        bne ed_search_finish
ed_search_cancel:
        lda #18
        ldx ed_s_count
        bne ed_search_finish
        ldx ed_s_count+1
        bne ed_search_finish
        ldx ed_s_count+2
        bne ed_search_finish
        lda #8
        bne ed_search_finish
ed_search_read_error:
        lda #5
        bne ed_search_finish
ed_search_replace_error:
        cmp #N_NOMEM
        beq +
        cmp #N_NOSLOT
        bne ed_search_read_error
+       lda #19
        ldx ed_s_count
        bne ed_search_finish
        ldx ed_s_count+1
        bne ed_search_finish
        ldx ed_s_count+2
        bne ed_search_finish
        lda #3
ed_search_finish:
        sta ed_status
        jmp ed_search_return

ed_search_replace:
        ldx ed_s_new_length
ed_search_input:
        dex
        bmi +
        lda ed_s_replacement,x
        sta d_input,x
        jmp ed_search_input
+       #ed_move3 ed_s_match,d_pos
        #ed_move3 ed_s_length,d_count
        #ed_move3 ed_s_new_length,d_replace_count
.if NATIVE_EDITOR_GRAPHICS
        jsr eh_replace
.else
        jsr doc_replace
.endif
        bcs +
        #doc_load3 D_LEN,ed_length
        jsr ed_invalidate_pages
        clc
+       rts

ed_search_fold:
        ldy ed_s_case
        beq +
        cmp #$61
        bcc +
        cmp #$7b
        bcs +
        and #$df
+       rts

; Prefix table for the folded pattern; length is nonzero at acceptance.
ed_search_prefix:
        lda #0
        sta ed_s_prefix
        ldx #1
        ldy #0
ed_prefix_next:
        cpx ed_s_length
        beq ed_prefix_done
        lda ed_s_pattern,x
ed_prefix_compare:
        cmp ed_s_pattern,y
        beq ed_prefix_equal
        cpy #0
        beq ed_prefix_store
        pha
        lda ed_s_prefix-1,y
        tay
        pla
        jmp ed_prefix_compare
ed_prefix_equal:
        iny
ed_prefix_store:
        tya
        sta ed_s_prefix,x
        inx
        jmp ed_prefix_next
ed_prefix_done:
        rts

ed_find_text: .text "find ",0
ed_replace_text: .text "repl ",0
ed_case_text: .text "case: ",0
ed_any_text: .text "any: ",0
ed_with_text: .text "with: ",0
ed_replace_choice_text: .text "replace: o one / a all / esc cancel",0
ed_found_text: .text "found at cursor; ctrl-n finds next",0
ed_wrapped_text: .text "found after wrap; ctrl-n finds next",0
ed_not_found_text: .text "no match; document kept",0
ed_search_busy_text: .text "working; esc stops. changed: ",0
ed_replaced_text: .text "replaced (hex): ",0
ed_search_cancel_text: .text "cancelled; changes kept (hex): ",0
ed_search_memory_text: .text "no memory; changes kept (hex): ",0
ed_s_pattern: .fill 64,0
ed_s_prefix: .fill 64,0
ed_s_replacement: .fill 64,0
ed_s_new_length: .fill 3,0
ed_s_start: .fill 3,0
ed_s_limit: .fill 3,0
ed_s_match: .fill 3,0
ed_s_wrapped: .byte 0
ed_s_matched: .byte 0
ed_s_ticks: .byte 0
ed_s_byte: .byte 0
