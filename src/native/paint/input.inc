; Foreground controls. Mouse gestures snapshot once; every keyboard point is
; its own undoable stroke. Cursor sprites are owned by the shared driver.
pa_normal_controls:
        lda #0
        sta pa_mode
        sta ui_first
        sta pa_segment
        sta pd_stroke
        lda #24
        sta ui_limit
        lda #23
        sta ui_selected
        lda #1
        sta pa_keyboard
        lda #$ff
        sta pm_arm
        rts
pa_key:
        ldx vd_phase
        beq +
        ldx vd_fault
        beq +
        cmp #27
        bne pa_vdc_key_blocked
        pha
        jsr vd_close
        pla
        bcs pa_vdc_key_blocked
+       ldx pa_mode
        beq pa_main_key
        cpx #2
        beq pa_save_key
        jmp pa_confirm_key
pa_main_key:
        cmp #9
        beq pa_tab
        cmp #13
        beq pa_enter
        cmp #32
        beq pa_keyboard_point
        cmp #$11
        beq pa_down
        cmp #$91
        beq pa_up
        cmp #$1d
        beq pa_right
        cmp #$9d
        beq pa_left
        cmp #$13
        beq pa_home
        cmp #$2b
        beq pa_next_ink
        cmp #$2d
        beq pa_previous_ink
        cmp #$61
        bcc +
        cmp #$7b
        bcs +
        and #$df
+       cmp #$52
        beq pa_display_refresh
        ldx #6
-       cmp pa_button_keys,x
        beq pa_activate
        dex
        bpl -
        rts
pa_tab:
        ldx ui_selected
        inx
        cpx #24
        bcc +
        ldx #0
+       jsr pa_choose_focus
        jmp pa_console
pa_enter:
        ldx ui_selected
        jmp pa_activate
pa_activate:
        cpx #23
        beq pa_keyboard_point
        cpx #7
        bcc pa_tool
        txa
        sec
        sbc #7
        sta pd_color
        jmp pa_tool_changed
pa_tool:
        txa
        beq pa_pen
        cmp #1
        beq pa_eraser
        cmp #2
        beq pa_undo
        cmp #3
        beq pa_clear
        cmp #4
        beq pa_save_start
        cmp #5
        beq pa_open_start
        jmp pa_request_close
pa_pen:
        lda #1
        sta pd_pen
        jmp pa_tool_changed
pa_eraser:
        lda #0
        sta pd_pen
        jmp pa_tool_changed
pa_next_ink:
        inc pd_color
        lda pd_color
        and #15
        sta pd_color
        jmp pa_tool_changed
pa_previous_ink:
        dec pd_color
        lda pd_color
        and #15
        sta pd_color
pa_tool_changed:
        lda #0
        sta pd_stroke
        sta pa_segment
        sta pa_status
        jmp pa_refresh_labels
pa_undo:
        jsr pd_undo
        bcs pa_drawing_error
        jmp pa_document_changed
pa_clear:
        jsr pd_clear
        bcs pa_drawing_error
pa_document_changed:
        lda #0
        sta pa_status
        sta pa_segment
        lda pa_bitmap
        beq pa_refresh_labels
        jsr pa_blit
        bcs pa_drawing_error
        jmp pa_refresh_labels
pa_home:
        lda #0
        sta pd_x
        sta pd_x+1
        sta pd_y
        beq pa_moved_key
pa_down:
        lda pd_y
        cmp #199
        beq pa_input_done
        inc pd_y
        bne pa_moved_key
pa_up:
        lda pd_y
        beq pa_input_done
        dec pd_y
        jmp pa_moved_key
pa_right:
        lda pd_x+1
        beq +
        lda pd_x
        cmp #63
        beq pa_input_done
+       inc pd_x
        bne pa_moved_key
        inc pd_x+1
        bne pa_moved_key
pa_left:
        lda pd_x
        ora pd_x+1
        beq pa_input_done
        lda pd_x
        bne +
        dec pd_x+1
+       dec pd_x
pa_moved_key:
        lda #1
        sta pa_keyboard
        lda #0
        sta pa_segment
        sta pd_stroke
        sta pa_status
        ldx #23
        jsr pa_choose_focus
        jsr pa_pan
        jsr pa_cursor
        jmp pa_refresh_labels
pa_keyboard_point:
        lda #0
        sta pd_stroke
        sta pa_segment
        sta pa_status
        lda #1
        sta pa_keyboard
        ldx #23
        jsr pa_choose_focus
        jsr pd_point
        bcs pa_drawing_error
        lda pa_bitmap
        beq +
        jsr pa_point_cell
        jsr pa_cell
        bcs pa_drawing_error
+       jsr pa_cursor
        jmp pa_refresh_labels
pa_display_refresh:
        lda vd_phase
        bne +
        lda #0
        sta pa_vdc_attempted
+       jmp pa_redraw
pa_vdc_key_blocked:
pa_input_done:
        rts
pa_drawing_error:
        sta pa_error
        lda #9
        sta pa_status
        lda pa_error
        jsr pa_view_failed
        jmp pa_console
pa_choose_focus:
        lda pa_bitmap
        bne +
        stx ui_selected
        clc
        rts
+       jmp pa_focus
pa_refresh_labels:
        lda pa_bitmap
        beq +
        jsr pa_labels
        bcs pa_drawing_error
+       jmp pa_console

pa_point_cell:
        lda pd_x
        sta pa_cell_x
        lda pd_x+1
        lsr
        ror pa_cell_x
        lsr pa_cell_x
        lsr pa_cell_x
        lda pd_y
        lsr
        lsr
        lsr
        sta pa_cell_y
        rts
pa_pan:
        jsr pa_point_cell
        lda #0
        sta pa_panned
        lda pa_cell_x
        sec
        sbc pa_view_x
        bcc pa_pan_left
        cmp #32
        bcc pa_pan_vertical
        lda pa_cell_x
        sec
        sbc #31
        bcs pa_pan_x
pa_pan_left:
        lda pa_cell_x
pa_pan_x:
        sta pa_view_x
        inc pa_panned
pa_pan_vertical:
        lda pa_cell_y
        sec
        sbc pa_view_y
        bcc pa_pan_up
        cmp #18
        bcc pa_pan_done
        lda pa_cell_y
        sec
        sbc #17
        bcs pa_pan_y
pa_pan_up:
        lda pa_cell_y
pa_pan_y:
        sta pa_view_y
        inc pa_panned
pa_pan_done:
        lda pa_bitmap
        beq pa_input_done
        lda pa_panned
        beq pa_input_done
        jmp pa_blit

; Logical document position is visible even with no mouse attached. The
; shared driver remains the sole owner of saved sprite configuration.
pa_cursor:
        lda pa_bitmap
        beq pa_input_done
        lda pa_mode
        bne pa_input_done
        lda pa_view_x
        asl
        asl
        asl
        sta pa_shift
        lda pd_x
        sec
        sbc pa_shift
        sta pm_x
        lda pd_x+1
        sbc #0
        sta pm_x+1
        lda pm_x
        clc
        adc #8
        sta pm_x
        bcc +
        inc pm_x+1
+       lda pa_view_y
        asl
        asl
        asl
        sta pa_shift
        lda pd_y
        sec
        sbc pa_shift
        clc
        adc #32
        sta pm_y
        jsr pm_place
        lda #3
        sta $d015
        rts

pa_mouse:
        lda vd_phase
        beq +
        lda vd_fault
        bne pa_input_done
+       lda #0
        sta pm_moved
        jsr pm_poll
        lda N_READY
        bne pa_input_done       ; no SID/absence sample in this poll
        lda pm_seen
        bne pa_mouse_present
        lda #0
        sta pa_segment
        sta pd_stroke
        lda pa_keyboard
        beq pa_input_done
        jmp pa_cursor
pa_mouse_present:
        lda pm_event
        beq +
        ldx pm_hit
        jsr pa_choose_focus
+       lda pa_mode
        beq pa_mouse_main
        lda pm_event
        cmp #2
        bne pa_input_done
        jmp pa_dialog_activate
pa_mouse_main:
        lda pm_event
        ora pm_moved
        beq pa_mouse_stroke
        lda #0
        sta pa_keyboard
        lda pm_hit
        cmp #23
        bne pa_mouse_tool
        jsr pa_mouse_endpoint
        lda pa_segment
        bne pa_mouse_stroke
        jsr pa_endpoint_to_point
        jsr pa_refresh_labels
        jmp pa_mouse_stroke
pa_mouse_tool:
        lda pm_event
        cmp #2
        beq +
        cmp #1
        bne pa_mouse_stroke
        jsr pa_console
        jmp pa_mouse_stroke
+
        ldx pm_hit
        cpx #23
        bcs pa_input_done
        jsr pa_activate
pa_mouse_stroke:
        lda pm_buttons
        beq pa_stroke_ended
        lda pm_arm
        cmp #23
        bne pa_stroke_ended
        lda pm_hit
        cmp #23
        bne pa_segment_ended
        jsr pa_mouse_endpoint
        lda pa_segment
        bne +
        jsr pa_endpoint_to_point
+       jsr pa_point_cell
        lda pa_cell_x
        sta pa_first_x
        lda pa_cell_y
        sta pa_first_y
        jsr pd_line
        bcs pa_drawing_error
        lda #1
        sta pa_segment
        lda pd_line_changed
        bne +
        lda pm_moved
        beq pa_input_done
        jmp pa_refresh_labels
+
        lda #0
        sta pa_status
        jsr pa_segment_blit
        bcs pa_drawing_error
        jmp pa_refresh_labels
pa_stroke_ended:
        lda #0
        sta pd_stroke
pa_segment_ended:
        lda #0
        sta pa_segment
        rts
pa_mouse_endpoint:
        lda pa_view_x
        asl
        asl
        asl
        sta pa_shift
        lda pm_x
        sec
        sbc #8
        sta pd_end_x
        lda pm_x+1
        sbc #0
        sta pd_end_x+1
        lda pd_end_x
        clc
        adc pa_shift
        sta pd_end_x
        bcc +
        inc pd_end_x+1
+       lda pa_view_y
        asl
        asl
        asl
        sta pa_shift
        lda pm_y
        sec
        sbc #32
        clc
        adc pa_shift
        sta pd_end_y
        rts
pa_endpoint_to_point:
        lda pd_end_x
        sta pd_x
        lda pd_end_x+1
        sta pd_x+1
        lda pd_end_y
        sta pd_y
        rts
pa_segment_blit:
        jsr pa_point_cell
        lda pa_cell_x
        cmp pa_first_x
        bcs +
        ldx pa_first_x
        sta pa_first_x
        txa
+       sta pa_last_x
        lda pa_cell_y
        cmp pa_first_y
        bcs +
        ldx pa_first_y
        sta pa_first_y
        txa
+       sta pa_last_y
        lda pa_first_y
        sta pa_cell_y
pa_blit_cells_row:
        lda pa_first_x
        sta pa_cell_x
-       jsr pa_cell
        bcs pa_input_done
        lda pa_cell_x
        cmp pa_last_x
        beq +
        inc pa_cell_x
        bne -
+       lda pa_cell_y
        cmp pa_last_y
        beq pa_blit_cells_done
        inc pa_cell_y
        bne pa_blit_cells_row
pa_blit_cells_done:
        lda #0
        clc
        rts

 .if ui_button_count<20
pm_control_count=20
 .else
pm_control_count=ui_button_count
 .endif
pm_select_surface=pa_select_view
pm_find_hit:
        lda paint_picker.fd_active
        beq +
        jmp paint_picker.pg_hit
+
        lda pm_x
        sta ui_x
        lda pm_x+1
        sta ui_x+1
        lda pm_y
        sta ui_y
        jmp ui_hit
pa_mode: .byte 0               ; 0 canvas, 1 dirty confirmation, 2 Save As
pa_status: .byte 0
pa_error: .byte 0
pa_keyboard: .byte 1
pa_segment: .byte 0
pa_panned: .byte 0
pa_shift: .byte 0
pa_first_x: .byte 0
pa_first_y: .byte 0
pa_last_x: .byte 0
pa_last_y: .byte 0
