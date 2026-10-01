; One app-bound module renders Files, copy forms and the byte viewer. All
; persistent file/directory state stays in the core while the picker replaces it.
fg_gui_entry:
        lda fg_operation
        beq fv_update
        cmp #1
        beq fv_input
        cmp #2
        beq fv_close
        cmp #3
        beq fv_footer
        cmp #5
        beq fv_paused_notice
        lda #0
        sta fv_attempted
        clc
        rts
fv_paused_notice:
        jsr fv_surface
        jsr gfx_bind
        bcs fv_notice_return
        ldx #7
-       lda fv_notice_bounds,x
        sta gfx_x0,x
        dex
        bpl -
        lda #0
        sta gfx_pen
        jsr gfx_rect
        bcs fv_notice_return
        lda #<fv_pause_text
        ldx #>fv_pause_text
        jsr fv_text_source
        lda #8
        ldy #192
        jmp fv_text
fv_notice_return:
        rts
fv_notice_bounds: .word 8,192,312,200
fv_pause_text: .byte 86,68,67,32,112,97,117,115,101,100,59,32,69,115,99,32,114,101,115,116,111,114,101,115,0

fv_close:
        jsr pm_close
        jsr N_VCLOSE
        lda #0
        sta fg_bitmap
        clc
        rts
fv_update:
        ldx #0
-       lda fv_body,x
        sta fv_old_body,x
        lda fv_body+256,x
        sta fv_old_body+256,x
        lda fv_body+512,x
        sta fv_old_body+512,x
        lda fv_body+768,x
        sta fv_old_body+768,x
        inx
        bne -
        lda fv_caret_column
        sta fv_before_caret
        lda ui_selected
        sta fv_before_focus
        jsr fv_collect
        jsr fv_focus_valid
        lda #0
        sta fv_count
        ldx #11
-       jsr fv_enabled
        bcs +
        inc fv_count
        inx
        cpx #19
        bne -
+
        lda fv_attempted
        beq fv_open
        lda fg_bitmap
        beq fv_done
        lda #0
        sta fv_dirty
        lda fv_view
        cmp fv_drawn_view
        bne fv_update_draw
        lda fc_phase
        cmp fv_drawn_phase
        bne fv_update_draw
        lda N_BROWSERFMT
        cmp fv_drawn_format
        bne fv_update_draw
        lda b_busy
        cmp fv_drawn_busy
        bne fv_update_draw
        lda fv_count
        cmp fv_drawn_count
        bne fv_update_draw
        inc fv_dirty
fv_update_draw:
        jsr fv_draw
        bcs fv_failed
        jmp fv_done
fv_open:
        lda #0
        sta fv_dirty
        lda #1
        sta fv_attempted
        lda fg_surface
        bne fv_initialize
        lda N_CURRENT
        sta N_OWNER
        lda #0
        sta N_BANK
        lda #$c0
        sta N_PAGE
        lda #36
        sta N_PAGES
        jsr N_RESERVE
        bcs fv_failed
        ldx #3
-       lda N_HANDLE,x
        sta fg_surface,x
        dex
        bpl -
fv_initialize:
        jsr fv_surface
        lda #0
        sta N_OFFSET
        sta N_OFFSET+1
        sta N_COUNT
        sta N_VALUE
        lda #2
        sta N_COUNT+1
-       lda #0
        ldx N_OFFSET+1
        cpx #32
        bcc +
        lda #$16
+       sta N_VALUE
        jsr N_FILL
        bcs fv_failed
        inc N_OFFSET+1
        inc N_OFFSET+1
        lda N_OFFSET+1
        cmp #36
        bne -
        jsr fv_draw
        bcs fv_failed
        jsr fv_surface
        jsr N_VSHOW
        bcs fv_failed
        lda #1
        sta fg_bitmap
        jsr pm_install
        bcs fv_failed
        lda #0
        sta fg_error
        jmp fv_done
fv_failed:
        sta fg_error
        jsr fv_close
        lda fg_surface
        beq fv_done
        jsr fv_surface
        jsr N_FREE
        bcs fv_done
        lda #0
        sta fg_surface
fv_done:
        clc
        rts
fv_surface:
        lda N_CURRENT
        sta N_OWNER
        ldx #3
-       lda fg_surface,x
        sta N_HANDLE,x
        dex
        bpl -
        rts

fv_draw:
        jsr fv_surface
        jsr gfx_bind
        bcs fv_draw_done
        lda fv_dirty
        beq fv_full_draw
        lda fv_before_focus
        cmp ui_selected
        beq fv_rows_begin
        tax
        jsr ui_paint
        bcs fv_draw_done
        ldx ui_selected
        jsr ui_paint
        bcs fv_draw_done
        jmp fv_rows_begin
fv_full_draw:
        lda #255
        sta pm_arm
        ldx #7
-       lda fv_frame,x
        sta gfx_x0,x
        dex
        bpl -
        lda #0
        sta gfx_pen
        jsr gfx_rect
        bcs fv_draw_done
        ldx #7
-       lda fv_cells,x
        sta gfx_x0,x
        dex
        bpl -
        lda #$16
        sta gfx_color
        jsr gfx_colors
        bcs fv_draw_done
        ldx fv_view
        lda fv_title_lo,x
        pha
        lda fv_title_hi,x
        tax
        pla
        jsr fv_text_source
        lda #8
        ldy #8
        jsr fv_text
        bcs fv_draw_done
        lda #0
        sta fv_index
fv_button:
        ldx fv_index
        jsr fv_enabled
        bcs fv_button_next
        jsr ui_paint
        bcs fv_draw_done
        ldx fv_index
        jsr fv_label
        jsr fv_text_source
        lda gfx_text_length
        beq fv_button_next
        jsr fv_bounds
        lda #1
        sta gfx_pen
        jsr gfx_rect
        bcs fv_draw_done
        jsr fv_bounds
        inc gfx_x0
        bne +
        inc gfx_x0+1
+       inc gfx_y0
        lda gfx_x1
        bne +
        dec gfx_x1+1
+       dec gfx_x1
        dec gfx_y1
        lda #0
        sta gfx_pen
        jsr gfx_rect
        bcs fv_draw_done
        jsr fv_bounds
        lda gfx_text_length
        asl
        asl
        asl
        sta fv_width
        clc
        lda gfx_x1
        adc gfx_x0
        sta fv_x
        lda gfx_x1+1
        adc gfx_x0+1
        sta fv_x+1
        sec
        lda fv_x
        sbc fv_width
        sta fv_x
        lda fv_x+1
        sbc #0
        lsr
        sta gfx_x0+1
        ror fv_x
        lda gfx_y0
        clc
        adc #4
        tay
        lda fv_x
        jsr fv_text_word
        bcs fv_draw_done
fv_button_next:
        inc fv_index
        lda fv_index
        cmp #32
        bne fv_button
fv_rows_begin:
        ldx fv_view
        bne +
        lda N_BROWSERFMT
        cmp #3
        bne +
        ldx #6
+
        lda fv_rows_lo,x
        sta fv_row_map+1
        lda fv_rows_hi,x
        sta fv_row_map+2
        lda #0
        sta fv_index
fv_next_row:
        ldx fv_index
fv_row_map:
        lda $ffff,x
        cmp #255
        beq fv_caret_draw
        sta fv_source_row
        jsr fv_row_pointer
        ldx fv_index
        inx
        stx fv_index
        lda fv_row_map+1
        sta fv_y_load+1
        lda fv_row_map+2
        sta fv_y_load+2
fv_y_load:
        lda $ffff,x
        sta fv_y
        inc fv_index
        lda fv_dirty
        bne fv_changed_cells
        ldx #0
fv_row_read:
        lda $ffff,x
        sta gfx_text_buffer,x
        inx
        cpx #38
        bne fv_row_read
-       lda gfx_text_buffer-1,x
        cmp #32
        bne +
        dex
        bne -
        beq fv_next_row
+       stx gfx_text_length
        lda #8
        ldy fv_y
        jsr fv_text
        bcs fv_draw_done
        jmp fv_next_row
fv_changed_cells:
        lda fv_row_read+1
        sta fv_previous_read+1
        lda fv_row_read+2
        clc
        adc #4
        sta fv_previous_read+2
        lda #0
        sta fv_cell
fv_cell_compare:
        ldx fv_cell
fv_previous_read:
        lda $ffff,x
        sta fv_old_character
        lda fv_row_read+1
        sta fv_current_read+1
        lda fv_row_read+2
        sta fv_current_read+2
fv_current_read:
        lda $ffff,x
        sta fv_new_character
        cmp fv_old_character
        bne fv_cell_draw
        lda fv_source_row
        cmp #7
        bne fv_cell_next
        lda fv_before_focus
        cmp #25
        bne +
        cpx fv_before_caret
        beq fv_cell_draw
+       lda ui_selected
        cmp #25
        bne fv_cell_next
        cpx fv_caret_column
        bne fv_cell_next
fv_cell_draw:
        jsr fv_cell_bounds
        lda #0
        sta gfx_pen
        jsr gfx_rect
        bcs fv_draw_done
        lda fv_new_character
        cmp #32
        beq fv_cell_next
        sta gfx_text_buffer
        lda #1
        sta gfx_text_length
        sta gfx_pen
        jsr fv_cell_bounds
        jsr gfx_text
        bcs fv_draw_done
fv_cell_next:
        inc fv_cell
        lda fv_cell
        cmp #38
        bne fv_cell_compare
        jmp fv_next_row
fv_caret_draw:
        lda ui_selected
        cmp #25
        bne fv_help_draw
        lda fc_phase
        bne fv_help_draw
        lda fv_caret_column
        cmp #38
        bcs fv_help_draw
        ldx #0
        stx gfx_x0+1
        asl
        rol gfx_x0+1
        asl
        rol gfx_x0+1
        asl
        rol gfx_x0+1
        clc
        adc #8
        sta gfx_x0
        lda gfx_x0+1
        adc #0
        sta gfx_x0+1
        clc
        lda gfx_x0
        adc #8
        sta gfx_x1
        lda gfx_x0+1
        adc #0
        sta gfx_x1+1
        lda #111
        sta gfx_y0
        lda #112
        sta gfx_y1
        lda #0
        sta gfx_y0+1
        sta gfx_y1+1
        lda #1
        sta gfx_pen
        jsr gfx_rect
        bcs fv_draw_done
fv_help_draw:
        lda fv_dirty
        bne fv_draw_complete
        lda #<fv_help
        ldx #>fv_help
        jsr fv_text_source
        lda #8
        ldy #192
        jsr fv_text
        bcs fv_draw_done
fv_draw_complete:
        lda fv_view
        sta fv_drawn_view
        lda fc_phase
        sta fv_drawn_phase
        lda N_BROWSERFMT
        sta fv_drawn_format
        lda b_busy
        sta fv_drawn_busy
        lda fv_count
        sta fv_drawn_count
        clc
fv_draw_done:
        rts
fv_cell_bounds:
        lda #0
        sta gfx_x0+1
        sta gfx_y0+1
        sta gfx_y1+1
        lda fv_cell
        asl
        rol gfx_x0+1
        asl
        rol gfx_x0+1
        asl
        rol gfx_x0+1
        clc
        adc #8
        sta gfx_x0
        lda gfx_x0+1
        adc #0
        sta gfx_x0+1
        clc
        lda gfx_x0
        adc #8
        sta gfx_x1
        lda gfx_x0+1
        adc #0
        sta gfx_x1+1
        lda fv_y
        sta gfx_y0
        clc
        adc #8
        sta gfx_y1
        rts
fv_bounds:
        lda fv_index
        asl
        asl
        asl
        tax
        ldy #0
-       lda ui_rects,x
        sta gfx_x0,y
        inx
        iny
        cpy #8
        bne -
        rts
fv_text_source:
        sta fv_string_read+1
        stx fv_string_read+2
        ldy #0
fv_string_read:
        lda $ffff,y
        beq +
        sta gfx_text_buffer,y
        iny
        cpy #38
        bne fv_string_read
+       sty gfx_text_length
        rts
fv_text:
        ldx #0
        stx gfx_x0+1
fv_text_word:
        sta gfx_x0
        sty gfx_y0
        lda #0
        sta gfx_y0+1
        lda #1
        sta gfx_pen
        jmp gfx_text
fv_row_pointer:
        ; Row*40, without borrowing the kernel's transfer buffer or zero page.
        ldx #0
        stx fv_address+1
        asl
        rol fv_address+1
        asl
        rol fv_address+1
        asl
        rol fv_address+1
        sta fv_address
        sta fv_row_offset
        lda fv_address+1
        sta fv_row_offset+1
        asl fv_address
        rol fv_address+1
        asl fv_address
        rol fv_address+1
        clc
        lda fv_address
        adc fv_row_offset
        sta fv_address
        lda fv_address+1
        adc fv_row_offset+1
        sta fv_address+1
        clc
        lda fv_address
        adc #<fv_body
        sta fv_row_read+1
        sta fv_body_write+1
        lda fv_address+1
        adc #>fv_body
        sta fv_row_read+2
        sta fv_body_write+2
        rts

; The normal text formatter supplies the data, so bitmap labels do not become
; a second directory parser or filename source. Every output stays bounded.
fv_collect:
        lda #32
        ldx #0
-       sta fv_body,x
        sta fv_body+256,x
        sta fv_body+512,x
        sta fv_body+768,x
        inx
        bne -
        stx fv_row
        stx fv_column
        stx b_screen
        lda #255
        sta fv_caret_column
        lda #1
        sta fg_collect
        lda fm_active
        beq +
        jmp fm_collect
+
        lda fg_mode
        beq fv_browser_collect
        lda fc_prompt
        beq fv_copy_collect
        lda #4
        sta fv_view
        lda #<fc_device_state
        ldx #>fc_device_state
        jsr fv_form_pointer
        lda #<fv_copy_device_caption
        ldx #>fv_copy_device_caption
        jmp fv_form_collect
fv_copy_collect:
        lda #1
        sta fv_view
        jsr fc_draw
        jmp fv_collected
fv_browser_collect:
        lda b_preview
        beq +
        lda #5
        sta fv_view
        jsr b_view_draw
        jmp fv_collected
+       lda b_prompt
        beq fv_list_collect
        cmp #1
        bne fv_path_collect
        lda #2
        sta fv_view
        lda #<b_device_state
        ldx #>b_device_state
        jsr fv_form_pointer
        lda #<fv_device_caption
        ldx #>fv_device_caption
        jmp fv_form_collect
fv_path_collect:
        lda #3
        sta fv_view
        lda #<b_usb_state
        ldx #>b_usb_state
        jsr fv_form_pointer
        lda #<fv_path_caption
        ldx #>fv_path_caption
fv_form_collect:
        jsr b_puts
        lda fv_view
        cmp #3
        bne +
        lda #13
        jsr fv_emit
        lda #<fv_dos_caption
        ldx #>fv_dos_caption
        jsr b_puts
        lda b_usb_device
        ldx #0
        jsr b_number
+       lda #7
        sta fv_row
        lda #0
        sta fv_column
        lda #38
        sta N_UIWIDTH
        lda fv_field_state
        sta N_UIPTR
        lda fv_field_state+1
        sta N_UIPTR+1
        jsr fv_field
        jmp fv_collected
fv_form_pointer:
        sta fv_field_state
        stx fv_field_state+1
        rts
fv_list_collect:
        lda #0
        sta fv_view
        jsr b_list_draw
fv_collected:
        lda #0
        sta fg_collect
        rts
fv_emit:
        php
        sta fv_character
        pha
        txa
        pha
        tya
        pha
        lda fv_character
        cmp #$93
        bne +
        lda #0
        sta fv_row
        sta fv_column
        beq fv_emit_done
+       cmp #13
        beq fv_newline
        cmp #$12
        beq fv_emit_done
        cmp #$92
        beq fv_emit_done
        lda fv_row
        cmp #25
        bcs fv_emit_done
        lda fv_column
        cmp #40
        bcs fv_emit_done
        lda fv_row
        jsr fv_row_pointer
        lda fv_character
        cmp #$61
        bcc +
        cmp #$7b
        bcs +
        and #$df
+       cmp #32
        bcc fv_dot
        cmp #127
        bcc +
fv_dot:
        lda #46
+       ldx fv_column
fv_body_write:
        sta $ffff,x
        inc fv_column
        bne fv_emit_done
fv_newline:
        inc fv_row
        lda #0
        sta fv_column
fv_emit_done:
        pla
        tay
        pla
        tax
        pla
        plp
        rts

; Render the VIC field viewport without switching consoles or issuing CHROUT.
; The VDC formatter independently updates its own viewport afterwards.
fv_field:
        lda N_UIPTR
        sta fv_state_read+1
        sta fv_state_write+1
        sta fv_field_state
        lda N_UIPTR+1
        sta fv_state_read+2
        sta fv_state_write+2
        sta fv_field_state+1
        ldx #7
fv_state_read:
        lda $ffff,x
        sta fv_field_data,x
        dex
        bpl fv_state_read
        lda fv_field_data+3
        sta fv_field_read+1
        lda fv_field_data+4
        sta fv_field_read+2
        lda N_UIWIDTH
        sec
        sbc #2
        sta fv_field_capacity
        lda fv_field_data
        sec
        sbc fv_field_capacity
        bcs +
        lda #255
+       clc
        adc #1
        cmp fv_field_data+5
        bcs +
        sta fv_field_data+5
+
        lda fv_field_data+1
        cmp fv_field_data+5
        bcs +
        sta fv_field_data+5
+       lda fv_field_data+1
        sec
        sbc fv_field_data+5
        cmp fv_field_capacity
        bcc +
        lda fv_field_data+1
        sec
        sbc fv_field_capacity
        clc
        adc #1
        sta fv_field_data+5
+       lda fv_field_data+5
        ldx #5
fv_state_write:
        sta $ffff,x
        lda #32
        ldx fv_field_data+5
        beq +
        lda #$3c
+       jsr fv_emit
        lda fv_field_data+1
        sec
        sbc fv_field_data+5
        clc
        adc fv_column
        sta fv_caret_column
        lda fv_column
        sta fv_field_column
        lda #0
        sta fv_field_index
fv_field_next:
        lda fv_field_index
        clc
        adc fv_field_data+5
        bcs fv_field_blank
        cmp fv_field_data
        bcs fv_field_blank
        tax
fv_field_read:
        lda $ffff,x
        jmp fv_field_emit
fv_field_blank:
        lda #32
fv_field_emit:
        jsr fv_emit
        inc fv_field_index
        lda fv_field_index
        cmp fv_field_capacity
        bne fv_field_next
        lda fv_field_data
        sec
        sbc fv_field_data+5
        cmp fv_field_capacity
        beq +
        bcc +
        lda #$3e
        bne fv_field_tail
+       lda #32
fv_field_tail:
        jmp fv_emit

fv_focus_valid:
        lda fc_phase
        cmp fv_previous_phase
        beq fv_phase_done
        tax
        lda fv_previous_phase
        stx fv_previous_phase
        cpx #0
        beq fv_phase_finished
        cmp #0
        bne fv_phase_done
        lda ui_selected
        sta fv_saved_focus
        jmp fv_phase_done
fv_phase_finished:
        lda fv_saved_focus
        sta ui_selected
fv_phase_done:
        lda b_selected
        and #7
        ldx N_BROWSERFMT
        cpx #3
        bne +
        lda bu_row
+       sta fv_row_selected
        lda fv_view
        cmp fv_previous_view
        beq fv_check_follow
        sta fv_previous_view
        lda #1
        sta fv_follow
        lda fv_view
        beq fv_follow_row
        cmp #1
        beq fv_default_field
        cmp #5
        bne fv_default_field
        lda #22
        bne fv_new_focus
fv_default_field:
        lda #25
        bne fv_new_focus
fv_check_follow:
        lda fv_view
        bne fv_check_focus
        lda fv_follow
        beq fv_check_focus
fv_follow_row:
        lda fv_row_selected
        clc
        adc #11
fv_new_focus:
        sta ui_selected
fv_check_focus:
        lda b_busy
        bne +
        lda #0
        sta fv_follow
+       ldx ui_selected
        jsr fv_enabled
        bcc fv_focus_done
        ldx #0
-       jsr fv_enabled
        bcc +
        inx
        cpx #32
        bne -
        ldx #0
+       stx ui_selected
fv_focus_done:
        rts
fv_enabled:
        lda fv_view
        cmp #7
        bcc +
        jmp fm_enabled
+       lda fv_view
        beq fv_browser_enabled
        cmp #1
        beq fv_copy_enabled
        cmp #5
        beq fv_viewer_enabled
        cpx #25
        bcc +
        cpx #28
        bcc fv_enabled_yes
+       cmp #3
        bne fv_enabled_no
        cpx #19
        beq fv_enabled_yes
        bne fv_enabled_no
fv_viewer_enabled:
        cpx #22
        beq fv_enabled_yes
        cpx #0
        beq fv_enabled_yes
        bne fv_enabled_no
fv_copy_enabled:
        lda fc_phase
        beq +
        cpx #24
        beq fv_enabled_yes
        bne fv_enabled_no
+       cpx #0
        beq fv_enabled_yes
        cpx #19
        bcc fv_enabled_no
        cpx #26
        bcc fv_enabled_yes
        bcs fv_enabled_no
fv_browser_enabled:
        cpx #31
        beq fv_enabled_yes
        cpx #30
        beq fv_usb_button
        cpx #28
        bcc +
        cpx #30
        bcs fv_enabled_no
        lda b_busy
        bne fv_enabled_no
        lda N_BROWSERFMT
        cmp #3
        bne fl_gui_iec
        lda bu_count
        bne fv_enabled_yes
        beq fv_enabled_no
fl_gui_iec:
        lda b_total
        ora b_total+1
        bne fv_enabled_yes
        beq fv_enabled_no
+
        cpx #3
        beq fv_usb_button
        cpx #4
        beq fv_usb_button
        cpx #11
        bcc fv_enabled_yes
        cpx #19
        bcs fv_enabled_no
        lda b_busy
        bne fv_enabled_no
        txa
        sec
        sbc #11
        sta fv_check_row
        lda N_BROWSERFMT
        cmp #3
        bne +
        lda fv_check_row
        cmp bu_count
        bcc fv_enabled_yes
        bcs fv_enabled_no
+       lda b_selected
        and #$f8
        clc
        adc fv_check_row
        cmp b_total
        lda b_selected+1
        sbc b_total+1
        bcc fv_enabled_yes
        bcs fv_enabled_no
fv_usb_button:
        lda N_BROWSERFMT
        cmp #3
        bne fv_enabled_no
fv_enabled_yes:
        clc
        rts
fv_enabled_no:
        sec
        rts

fv_input:
        lda fv_view
        bne fv_hot_done         ; browser-only shortcuts
        lda fg_key
        cmp #6                  ; Ctrl-F: find a filename
        bne +
        jmp fn_begin
+       cmp #11                 ; Ctrl-K: create an Ultimate folder
        bne +
        jmp fm_begin
+       cmp #18                 ; Ctrl-R: rename the selected Ultimate entry
        bne +
        jmp fr_rename
+       cmp #4                  ; Ctrl-D: delete the selected Ultimate entry
        bne fv_hot_done
        jmp fr_delete
fv_hot_done:
        lda fg_key
        beq fv_mouse
        lda #255
        sta pm_arm
        lda fg_key
        cmp #9
        beq fv_tab
        cmp #13
        beq fv_activate_focus
        lda fv_view
        cmp #3
        bne +
        lda fg_key
        cmp #$85
        bne fv_passthrough
        lda #9
        clc
        rts
+       lda fv_view
        bne fv_copy_key
        lda #1
        sta fv_follow
        bne fv_passthrough
fv_copy_key:
        cmp #5
        beq fv_passthrough
        lda fg_key
        cmp #27
        beq fv_passthrough
        cmp #$85
        bcs fv_passthrough
        lda ui_selected
        cmp #25
        bne fv_no_key
fv_passthrough:
        lda fg_key
        clc
        rts
fv_tab:
        ldx ui_selected
-       inx
        cpx #32
        bcc +
        ldx #0
+       jsr fv_enabled
        bcs -
        jmp fv_set_focus
fv_activate_focus:
        ldx ui_selected
        cpx #11
        bcc +
        cpx #19
        bcs +
        jsr fv_activate
        jmp fv_return_enter
+
        jmp fv_activate
fv_mouse:
        jsr pm_poll
        lda pm_event
        beq fv_no_key
        lda #0
        sta N_READY
        ldx pm_hit
        cpx #255
        beq fv_no_key
        lda pm_event
        cmp #2
        bne fv_set_focus
        jsr fv_set_focus
        lda fg_bitmap
        beq fv_redraw_key
        ldx pm_hit
        jmp fv_activate
fv_set_focus:
        ; Explicit mouse/Tab focus supersedes any earlier keyboard request
        ; to follow a file row, including a key that caused no redraw.
        lda #0
        sta fv_follow
        cpx ui_selected
        beq fv_no_key
        stx fv_next_focus
        lda ui_selected
        sta fv_old_focus
        jsr fv_surface
        jsr gfx_bind
        bcs fv_focus_failed
        ldx fv_next_focus
        jsr ui_focus
        bcs fv_focus_failed
        lda fv_old_focus
        cmp #25
        beq fv_focus_repaint
        lda ui_selected
        cmp #25
        bne fv_focus_footer
fv_focus_repaint:
        lda #0
        sta fv_dirty
        jsr fv_draw
        bcs fv_focus_failed
fv_focus_footer:
        jsr fv_footer
        jmp fv_no_key
fv_focus_failed:
        jsr fv_failed
        jmp fv_redraw_key
fv_activate:
        jsr fv_enabled
        bcs fv_no_key
        cpx #25
        beq fv_field_activate
        cpx #11
        bcc fv_button_activate
        cpx #19
        bcs fv_button_activate
        txa
        sec
        sbc #11
        ldx N_BROWSERFMT
        cpx #3
        bne +
        sta bu_row
        jsr bu_save_selection
        jmp fv_redraw_key
+       sta fv_check_row
        lda b_selected
        and #$f8
        clc
        adc fv_check_row
        sta b_selected
        jmp fv_redraw_key
fv_field_activate:
        lda fg_key
        bne fv_return_enter
        ; A click chooses a caret from the exact field viewport, not a label.
        lda pm_x+1
        sta fv_x+1
        lda pm_x
        sec
        sbc #8
        sta fv_x
        lda fv_x+1
        sbc #0
        lsr
        ror fv_x
        lsr
        ror fv_x
        lsr
        ror fv_x
        lda fv_x
        sec
        sbc fv_field_column
        bcs +
        lda #0
+       clc
        adc fv_field_data+5
        bcs fv_caret_end
        cmp fv_field_data
        bcc +
fv_caret_end:
        lda fv_field_data
+       pha
        lda fv_field_state
        sta fv_caret_write+1
        lda fv_field_state+1
        sta fv_caret_write+2
        pla
        ldx #1
fv_caret_write:
        sta $ffff,x
        jmp fv_redraw_key
fv_button_activate:
        cpx #31
        bne +
        jmp fn_begin
+
        cpx #30
        bne +
        jmp fm_begin
+
        lda fv_view
        cmp #5
        bne +
        cpx #22
        beq fv_return_enter
+       lda fv_view
        cmp #3
        bne +
        cpx #19
        bne +
        lda #9
        bne fv_input_return
+       cpx #1
        bne +
        lda N_BROWSERFMT
        cmp #3
        bne +
        lda #9
        bne fv_input_return
+       lda fv_button_keys,x
        bne fv_input_return
fv_no_key:
        lda #0
        clc
        rts
fv_return_enter:
        lda #13
        bne fv_input_return
fv_redraw_key:
        lda #14
fv_input_return:
        clc
        rts
pm_select_surface = fv_surface
pm_control_count = 32
pm_find_hit:
        lda pm_x
        sta ui_x
        lda pm_x+1
        sta ui_x+1
        lda pm_y
        sta ui_y
        lda #0
        sta ui_first
        lda #32
        sta ui_limit
-       jsr ui_hit
        cpx #255
        beq +
        jsr fv_enabled
        bcc +
        inx
        stx ui_first
        jmp -
+       rts

fv_label:
        lda fv_view
        cmp #7
        bcc fm_label_other
        cmp #8
        bne +
        cpx #26
        bne +
        lda #<fn_find_text
        ldx #>fn_find_text
        rts
+
        cpx #26
        bne fm_label_back
        ldx fv_view
        cpx #9                  ; Rename and Delete act under their own title
        bcc +
        lda fv_title_lo,x
        pha
        lda fv_title_hi,x
        tax
        pla
        rts
+       lda #<fm_create_text
        ldx #>fm_create_text
        rts
fm_label_back:
        cpx #27
        bne fm_label_other
        lda #<fm_back_text
        ldx #>fm_back_text
        rts
fm_label_other:
        lda fv_view
        cmp #5
        bne +
        cpx #22
        bne +
        lda #<fv_next
        ldx #>fv_next
        rts
+       lda fv_view
        cmp #3
        bne +
        cpx #19
        bne +
        lda #<fv_dos
        ldx #>fv_dos
        rts
+       lda fv_view
        cmp #1
        bne +
        lda fc_phase
        beq +
        cpx #24
        bne +
        lda #<fv_cancel
        ldx #>fv_cancel
        rts
+       lda fv_label_lo,x
        pha
        lda fv_label_hi,x
        tax
        pla
        rts
fv_footer:
        lda vd_phase
        bne fv_no_key
        ldx #24
        ldy #0
        clc
        jsr $fff0
        lda #79
        sta fv_footer_left
-       lda #32
        jsr b_usb_chrout
        dec fv_footer_left
        bne -
        ldx #23
        ldy #0
        clc
        jsr $fff0
        lda #<fv_help
        ldx #>fv_help
        jsr fv_console_puts
        lda #13
        jsr b_usb_chrout
        lda #<fv_focus
        ldx #>fv_focus
        jsr fv_console_puts
        ldx ui_selected
        cpx #25
        beq fv_footer_field
        cpx #11
        bcc +
        cpx #19
        bcs +
        lda #<fv_row_label
        ldx #>fv_row_label
        jmp fv_footer_text
+       jsr fv_label
        jmp fv_footer_text
fv_footer_field:
        lda #<fv_field_label
        ldx #>fv_field_label
fv_footer_text:
        jsr fv_console_puts
        lda #0
        clc
        rts
fv_console_puts:
        sta fv_console_read+1
        stx fv_console_read+2
fv_console_read:
        lda $ffff
        beq +
        cmp #$61
        bcc fv_console_emit
        cmp #$7b
        bcs fv_console_emit
        and #$df
fv_console_emit:
        jsr b_usb_chrout
        inc fv_console_read+1
        bne fv_console_read
        inc fv_console_read+2
        jmp fv_console_read
+       rts

fv_button_keys: .byte 27,$44,$46,$47,$50,$52,$42,$4e,13,$49,$43
        .fill 8,0
        .byte $85,$86,$87,$88,13,27,13,13,27,5,16,11,6
fv_frame: .word 0,0,320,200
fv_cells: .word 0,0,40,25
fv_attempted: .byte 0
fv_view: .byte 0
fv_previous_view: .byte 255
fv_previous_phase: .byte 0
fv_saved_focus: .byte 25
fv_follow: .byte 1
ui_selected: .byte 11
fv_row_selected: .byte 0
fv_check_row: .byte 0
fv_index: .byte 0
fv_y: .byte 0
fv_x: .word 0
fv_width: .byte 0
fv_row: .byte 0
fv_column: .byte 0
fv_character: .byte 0
fv_address: .word 0
fv_row_offset: .word 0
fv_caret_column: .byte 255
fv_field_state: .word 0
fv_field_data: .fill 8,0
fv_field_index: .byte 0
fv_field_capacity: .byte 0
fv_field_column: .byte 0
fv_next_focus: .byte 0
fv_old_focus: .byte 0
fv_footer_left: .byte 0
fv_dirty: .byte 0
fv_count: .byte 0
fv_drawn_view: .byte 255
fv_drawn_phase: .byte 255
fv_drawn_format: .byte 255
fv_drawn_busy: .byte 255
fv_drawn_count: .byte 255
fv_before_caret: .byte 255
fv_before_focus: .byte 0
fv_source_row: .byte 0
fv_cell: .byte 0
fv_old_character: .byte 0
fv_new_character: .byte 0
fv_body=$5000
fv_old_body=$5400
; Modal dialog/search paths and status borrow idle copy scratch. Dialogs open
; only from the browser, never during a copy; the picker is another module.
fm_path=FC_DATA_STORAGE
fm_status=FC_DATA_STORAGE+256
.include "new-folder.inc"
.include "find-name.inc"
.include "buttons.inc"
.include "../graphics/buttons.inc"
.include "../graphics/graphics-core.inc"
.include "../graphics/text-core.inc"
.include "../input/pointer.inc"
