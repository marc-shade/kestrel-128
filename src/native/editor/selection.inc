; Text selection and atomic replacement in the checked renderer module.
; Ctrl-B marks/ends a range, Ctrl-A selects all, Ctrl-G/Escape clears it.
es_bounds:
        lda es_active
        beq es_return
        #es_cmp3 ed_cursor,es_anchor
        bcc es_reverse
        #es_copy3 es_anchor,es_first
        #es_copy3 ed_cursor,es_limit
        rts
es_reverse:
        #es_copy3 ed_cursor,es_first
        #es_copy3 es_anchor,es_limit
es_return:
        rts

es_key:
        lda ed_mode
        ora eg_busy
        bne es_unhandled
        lda eg_key
        cmp #1
        beq es_all
        cmp #2
        beq es_mark_key
        cmp #7
        beq es_clear_key
        lda es_active
        beq es_unhandled
        lda eg_key
        cmp #27
        beq es_clear_key
        ldx #7
-       cmp es_motion,x
        beq es_move_key
        dex
        bpl -
        cmp #20
        beq es_delete_key
        cmp #13
        beq es_enter_key
        cmp #32
        bcc es_unhandled
        cmp #127
        bcs es_unhandled
        sta d_input
        lda #1
        bne es_replace
es_unhandled:
        clc
        rts
es_mark_key:
        lda es_mark
        eor #1
        sta es_mark
        beq es_changed
        #es_copy3 ed_cursor,es_anchor
        lda #1
        sta es_active
        bne es_changed
es_all:
        lda #0
        sta es_anchor
        sta es_anchor+1
        sta es_anchor+2
        sta es_mark
        #es_copy3 ed_length,ed_cursor
        lda #1
        sta es_active
        bne es_changed
es_clear_key:
        jsr es_clear
es_changed:
        lda #1
        sta es_dirty
        lda #255
es_handled:
        sta eg_key
        sec
        rts
es_move_key:
        lda es_mark
        bne es_unhandled
        jsr es_bounds
        jsr es_clear
        lda eg_key
        cmp #$9d
        bne +
        #es_copy3 es_first,ed_cursor
        jmp es_changed
+       cmp #$1d
        bne es_unhandled
        #es_copy3 es_limit,ed_cursor
        jmp es_changed
es_enter_key:
        ldx ui_selected
        cpx #6
        bne es_unhandled
        lda #13
        ldx ed_newline
        cpx #1
        bne +
        lda #10
+       sta d_input
        lda #1
        cpx #2
        bne es_replace
        lda #10
        sta d_input+1
        lda #2
        bne es_replace
es_delete_key:
        jsr es_bounds
        #es_cmp3 es_first,es_limit
        bne +
        jsr es_clear
        jmp es_unhandled
+       lda #0
es_replace:
        sta d_replace_count
        ldx #6
        jsr eg_focus
        bcs eg_input_zero
        lda #0
        sta d_replace_count+1
        sta d_replace_count+2
        jsr es_bounds
        #es_copy3 es_first,d_pos
        #es_copy3 es_limit,d_count
        #es_sub3 es_first,d_count
        lda ed_active
        sta d_slot
        jsr eh_replace
        bcs es_replace_error
        #es_copy3 es_first,ed_cursor
        #es_add3 d_replace_count,ed_cursor
        lda #1
        sta ed_document_changed
        sta ed_structure
        jsr es_clear
        jmp es_changed
es_replace_error:
        cmp #N_NOMEM
        beq es_memory_error
        cmp #N_NOSLOT
        beq es_memory_error
        lda #5
        bne es_error
es_memory_error:
        lda #3
es_error:
        sta ed_status
        lda #254
        bne es_handled

; Once a document press starts, the drag owns the release even outside the
; document rectangle. A disconnected pointer ends the drag at the last range.
es_mouse:
        lda ed_mode
        ora eg_busy
        bne es_unhandled
        lda es_drag
        bne es_drag_poll
        lda pm_event
        cmp #1
        bne es_unhandled
        lda pm_buttons
        beq es_unhandled
        lda pm_arm
        cmp #6
        bne es_unhandled
        jsr eg_document_click
        #es_copy3 ed_cursor,es_anchor
        lda #0
        sta es_mark
        lda #1
        sta es_active
        sta es_drag
        jmp es_changed
es_drag_poll:
        lda pm_seen
        beq es_drag_end
        lda pm_buttons
        beq es_drag_end
        #es_copy3 ed_cursor,es_previous
        jsr es_point
        #es_cmp3 ed_cursor,es_previous
        bne es_changed
        lda #0
        beq es_handled
es_drag_end:
        lda #0
        sta es_drag
        lda #255
        sta pm_arm
        jsr es_bounds
        #es_cmp3 es_first,es_limit
        bne es_changed
        jsr es_clear
        jmp es_changed

; Clamp the pointer to the view, and advance one logical row per sample when
; it is above/below the view. ed_locate scrolls to the resulting caret.
es_point:
        lda pm_y
        sta es_y
        cmp #56
        bcs +
        lda #56
+       cmp #184
        bcc +
        lda #183
+       sta pm_y
        jsr eg_document_click
        lda es_y
        sta pm_y
        cmp #56
        bcc es_point_up
        cmp #184
        bcc es_point_horizontal
        #es_copy3 eg_click_start,ed_scan
        jsr ed_forward_end
        jsr ed_after_line
        jmp es_point_row
es_point_up:
        #es_copy3 eg_click_start,ed_scan
        jsr ed_previous_end
        bcs es_point_horizontal
        jsr ed_backward_start
es_point_row:
        #es_copy3 ed_scan,eg_click_start
        jsr ed_forward_end
        jsr eg_click_position
es_point_horizontal:
        lda pm_x+1
        bne es_normalize
        lda pm_x
        cmp #8
        bcs es_normalize
        lda ed_horizontal
        ora ed_horizontal+1
        ora ed_horizontal+2
        beq es_normalize
        #es_sub3 ed_one,ed_number
        jmp eg_click_position
es_normalize:
        rts

es_motion: .byte $89,$8a,$13,$05,$9d,$1d,$91,$11
es_previous: .fill 3,0
es_y: .byte 0
