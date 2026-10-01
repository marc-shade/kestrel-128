; The shared module includes search plus the blue editor presentation.
eg_entry:
        lda eg_operation
        cmp #3
        beq eg_input_entry
        cmp #4
        beq eg_vclose
        cmp #5
        beq ed_search_entry
        cmp #7
        beq eg_footer_draw
        cmp #8
        beq eg_paused_notice
        jmp eg_update

eg_paused_notice:
        jsr eg_surface
        jsr gfx_bind
        bcs eg_notice_return
        ldx #7
-       lda eg_notice_bounds,x
        sta gfx_x0,x
        dex
        bpl -
        lda #0
        sta gfx_pen
        jsr gfx_rect
        bcs eg_notice_return
        lda #<eg_pause_text
        ldx #>eg_pause_text
        ldy dm_fault
        beq +
        lda #<eg_memory_pause_text
        ldx #>eg_memory_pause_text
+
        jsr eg_text_source
        lda #8
        ldy #192
        jmp eg_text
eg_notice_return:
        rts
eg_notice_bounds: .word 8,192,312,200
eg_pause_text: .byte 86,68,67,32,112,97,117,115,101,100,59,32,69,115,99,32,114,101,115,116,111,114,101,115,0
eg_memory_pause_text: .byte 82,69,85,32,112,97,117,115,101,100,59,32,69,115,99,32,114,101,115,116,111,114,101,115,0

eg_update:
        jsr es_bounds
        lda #0
        sta eg_busy
        lda eg_operation
        cmp #6
        bne +
        lda #1
        sta eg_busy
        jmp eg_collected
+       lda ed_s_running
        beq +
        lda ed_mode
        bne +
        lda ed_status
        cmp #16
        bne +
        lda #2
        sta eg_busy
+       lda #1
        sta eg_collect
        lda eg_started
        beq eg_collect_full
        lda eg_operation
        beq eg_collect_full
        cmp #1
        beq eg_collect_partial
        jsr ed_paint_fields
        jmp eg_collect_done
eg_collect_partial:
        jsr ed_show_partial
        jmp eg_collect_done
eg_collect_full:
        lda #32
        ldx #0
-       sta eg_body,x
        sta eg_body+256,x
        sta eg_body+512,x
        sta eg_body+768,x
        inx
        bne -
        jsr ed_show
eg_collect_done:
        lda #0
        sta eg_collect
eg_collected:
        lda ed_mode
        sta eg_view
        lda eg_busy
        beq +
        clc
        adc #9
        sta eg_view
+       lda eg_view
        cmp eg_last_view
        beq eg_focus_valid
        lda #255
        sta pm_arm
        ldx #6
        lda eg_view
        beq eg_focus_default
        ldx #11
        cmp #5
        bne +
        ldx #15
+       cmp #9
        bne +
        ldx #13
+       cmp #10
        bcc eg_focus_default
        ldx #20
eg_focus_default:
        stx ui_selected
eg_focus_valid:
        ldx ui_selected
        jsr eg_enabled
        bcc +
        ldx #6
        stx ui_selected
+
        lda eg_view
        beq eg_field_done
        cmp #5
        beq eg_field_done
        cmp #9
        beq eg_field_done
        lda #1
        sta eg_collect
        lda #24
        sta eg_row
        lda #0
        sta eg_column
        sta eg_reverse
        jsr ed_field_pointer
        lda #38
        sta N_UIWIDTH
        jsr eg_field
        lda #24
        jsr eg_row_pointer
        lda ui_selected
        cmp #11
        bne +
        ldx eg_caret_column
        lda eg_body+960,x
        ora #128
        sta eg_body+960,x
+       lda eg_busy
        beq +
        lda #6
        sta eg_row
        lda #0
        sta eg_column
        lda eg_busy
        cmp #1
        bne eg_search_position
        lda #<eg_bytes
        ldx #>eg_bytes
        jsr ed_puts
        #es_copy3 ed_io_pos,ed_print_number
        jmp eg_progress_number
eg_search_position:
        lda #<eg_search_byte
        ldx #>eg_search_byte
        jsr ed_puts
        #es_copy3 ed_probe,ed_print_number
eg_progress_number:
        jsr ed_hex24
-       lda eg_column
        cmp #40
        beq +
        lda #32
        jsr eg_emit
        lda eg_row
        cmp #6
        beq -
+       lda #0
        sta eg_collect
eg_field_done:
        lda eg_started
        beq eg_vopen
        lda eg_bitmap
        beq eg_done
        lda #0
        sta eg_full_draw
        lda eg_view
        cmp eg_last_view
        bne +
        lda eg_more
        cmp eg_last_more
        bne +
        lda ed_io_phase
        cmp eg_last_phase
        beq eg_update_draw
+       inc eg_full_draw
eg_update_draw:
        jsr eg_draw
        bcs eg_failed
        jmp eg_done

eg_vopen:
        lda #1
        sta eg_started
        sta eg_full_draw
        lda eg_handle
        bne eg_initialize
        lda N_CURRENT
        sta N_OWNER
        lda #0
        sta N_BANK
        lda #$c0
        sta N_PAGE
        lda #36
        sta N_PAGES
        jsr N_RESERVE
        bcs eg_failed
        ldx #3
-       lda N_HANDLE,x
        sta eg_handle,x
        dex
        bpl -
eg_initialize:
        jsr eg_surface
        lda #0
        sta N_OFFSET
        sta N_OFFSET+1
        sta N_COUNT
        lda #2
        sta N_COUNT+1
-       lda #0
        ldx N_OFFSET+1
        cpx #32
        bcc +
        lda #$16
+       sta N_VALUE
        jsr N_FILL
        bcs eg_failed
        inc N_OFFSET+1
        inc N_OFFSET+1
        lda N_OFFSET+1
        cmp #36
        bne -
        jsr eg_draw
        bcs eg_failed
        jsr eg_surface
        lda eg_bitmap
        bne +
        jsr N_VSHOW
        bcs eg_failed
+
        lda #1
        sta eg_bitmap
        jsr pm_install
        bcs eg_failed
        lda #0
        sta eg_error
eg_done:
        clc
        rts
eg_failed:
        sta eg_error
        jsr eg_vdc_close
        jsr eg_vclose
        jmp eg_release_surface
eg_vclose:
        jsr pm_close
        lda ed_module_wanted
        cmp #3
        beq eg_done
        jsr N_VCLOSE
        lda #0
        sta eg_bitmap
        jmp eg_done
eg_release_surface:
        lda eg_handle
        beq eg_done
        jsr eg_surface
        jsr N_FREE
        bcs eg_done
        lda #0
        sta eg_handle
        jmp eg_done
eg_surface:
        lda N_CURRENT
        sta N_OWNER
        ldx #3
-       lda eg_handle,x
        sta N_HANDLE,x
        dex
        bpl -
        rts

; Every text cell is aligned. Write its complete eight-byte glyph directly
; through the owned transfer API; caret cells invert the same glyph bytes.
eg_draw:
        jsr eg_surface
        jsr gfx_bind
        bcs eg_draw_return
        lda eg_full_draw
        beq eg_draw_rows
        lda #255
        sta pm_arm
        ldx #7
-       lda eg_frame,x
        sta gfx_x0,x
        dex
        bpl -
        lda #0
        sta gfx_pen
        jsr gfx_rect
        bcs eg_draw_return
        ldx #7
-       lda eg_cells,x
        sta gfx_x0,x
        dex
        bpl -
        lda #$16
        sta gfx_color
        jsr gfx_colors
        bcs eg_draw_return
        lda #0
        sta eg_index
eg_draw_buttons:
        ldx eg_index
        jsr eg_enabled
        bcs eg_button_next
        cpx #6
        beq eg_button_next
        jsr ui_paint
        bcs eg_draw_return
        ldx eg_index
        jsr eg_label
        jsr eg_text_source
        lda gfx_text_length
        beq eg_button_next
        jsr eg_bounds
        lda #1
        sta gfx_pen
        jsr gfx_rect
        bcs eg_draw_return
        jsr eg_bounds
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
        bcs eg_draw_return
        jsr eg_bounds
        lda gfx_text_length
        asl
        asl
        asl
        sta eg_text_width
        clc
        lda gfx_x0
        adc gfx_x1
        sta eg_text_x
        lda gfx_x0+1
        adc gfx_x1+1
        sta eg_text_x+1
        sec
        lda eg_text_x
        sbc eg_text_width
        sta eg_text_x
        lda eg_text_x+1
        sbc #0
        lsr
        ror eg_text_x
        sta gfx_x0+1
        lda eg_text_x
        sta gfx_x0
        lda gfx_y0
        clc
        adc #4
        sta gfx_y0
        lda #1
        sta gfx_pen
        jsr gfx_text
        bcs eg_draw_return
eg_button_next:
        inc eg_index
        lda eg_index
        cmp #ui_button_count
        bne eg_draw_buttons
        lda #<eg_help
        ldx #>eg_help
        jsr eg_text_source
        lda #8
        ldy #192
        jsr eg_text
        bcs eg_draw_return
        lda eg_view
        beq eg_draw_rows
        jsr eg_caption
        jsr eg_text_source
        lda #16
        ldy #72
        jsr eg_text
        bcs eg_draw_return
eg_draw_rows:
        lda #0
        sta eg_mapping
eg_map_next:
        ldx eg_mapping
        lda eg_maps,x
        cmp #255
        beq eg_mapped
        sta eg_source_row
        lda eg_maps+1,x
        sta eg_target_row
        lda eg_maps+2,x
        sta eg_source_column
        lda eg_maps+3,x
        sta eg_target_column
        lda eg_maps+4,x
        sta eg_left
        lda eg_view
        beq eg_map_visible
        lda eg_source_row
        cmp #7
        bcc eg_map_visible
        cmp #8
        bcc eg_map_visible
        cmp #21
        bcc eg_map_advance
eg_map_visible:
        jsr eg_copy_row
        bcs eg_draw_return
eg_map_advance:
        lda eg_mapping
        clc
        adc #5
        sta eg_mapping
        jmp eg_map_next
eg_mapped:
        lda eg_view
        beq eg_status_main
        lda #6
        sta eg_source_row
        lda #15
        sta eg_target_row
        lda #0
        sta eg_source_column
        lda #1
        sta eg_target_column
        lda #38
        sta eg_left
        jsr eg_copy_row
        bcs eg_draw_return
        lda eg_view
        cmp #5
        beq eg_draw_remember
        cmp #9
        beq eg_draw_remember
        lda #24
        sta eg_source_row
        lda #12
        sta eg_target_row
        lda #0
        sta eg_source_column
        lda #1
        sta eg_target_column
        lda #38
        sta eg_left
        jsr eg_copy_row
        bcs eg_draw_return
        lda ed_mode
        cmp #6
        beq eg_case_draw
        cmp #7
        bne eg_draw_remember
eg_case_draw:
        ; Case selection can change without changing the modal layout.
        ldx #7
-       lda eg_case_region,x
        sta gfx_x0,x
        dex
        bpl -
        lda #0
        sta gfx_pen
        jsr gfx_rect
        bcs eg_draw_return
        lda #<eg_case_exact
        ldx #>eg_case_exact
        ldy ed_s_pending_case
        beq +
        lda #<eg_case_any
        ldx #>eg_case_any
+       jsr eg_text_source
        lda #16
        ldy #88
        jsr eg_text
        bcs eg_draw_return
        jmp eg_draw_remember
eg_status_main:
        lda #6
        sta eg_source_row
        lda #23
        sta eg_target_row
        lda #0
        sta eg_source_column
        sta eg_target_column
        lda #40
        sta eg_left
        jsr eg_copy_row
        bcs eg_draw_return
eg_draw_remember:
        lda eg_view
        sta eg_last_view
        lda eg_more
        sta eg_last_more
        lda ed_io_phase
        sta eg_last_phase
        clc
eg_draw_return:
        rts

eg_copy_row:
        lda eg_source_row
        jsr eg_row_pointer
        ldx eg_source_row
        lda eg_cache_lo,x
        sta eg_old_read+1
        sta eg_cache_write+1
        lda eg_cache_hi,x
        sta eg_old_read+2
        sta eg_cache_write+2
        ldx eg_source_column
eg_row_read:
        lda $ffff,x
        sta eg_cell
        lda eg_full_draw
        bne eg_cell_full
        lda eg_cell
eg_old_read:
        cmp $ffff,x
        beq eg_cell_next
        jmp eg_cell_write
eg_cell_full:
        lda eg_cell
        cmp #32
        beq eg_cell_next
eg_cell_write:
        jsr eg_write_cell
        bcs eg_copy_return
eg_cell_next:
        ldx eg_source_column
        lda eg_cell
eg_cache_write:
        sta $ffff,x
        inc eg_source_column
        inc eg_target_column
        dec eg_left
        beq eg_copy_done
        ldx eg_source_column
        jmp eg_row_read
eg_copy_done:
        clc
eg_copy_return:
        rts

eg_write_cell:
        ldx eg_target_row
        lda #1
        sta vm_rows,x
        sta vm_pending
        lda eg_cell
        and #127
        jsr gfx_load_glyph
        lda #0
        bit eg_cell
        bpl +
        lda #255
+       sta eg_inverse
        ldx #7
eg_glyph_read:
        lda gfx_bits,x
        eor eg_inverse
        sta N_BUFFER,x
        dex
        bpl eg_glyph_read
        lda eg_target_row
        ldx #0
        stx N_OFFSET+1
        asl
        rol N_OFFSET+1
        asl
        rol N_OFFSET+1
        asl
        rol N_OFFSET+1
        sta N_OFFSET
        sta eg_row_offset
        lda N_OFFSET+1
        sta eg_row_offset+1
        asl N_OFFSET
        rol N_OFFSET+1
        asl N_OFFSET
        rol N_OFFSET+1
        clc
        lda N_OFFSET
        adc eg_row_offset
        sta N_OFFSET
        lda N_OFFSET+1
        adc eg_row_offset+1
        sta N_OFFSET+1
        clc
        lda N_OFFSET
        adc eg_target_column
        sta N_OFFSET
        bcc +
        inc N_OFFSET+1
+       asl N_OFFSET
        rol N_OFFSET+1
        asl N_OFFSET
        rol N_OFFSET+1
        asl N_OFFSET
        rol N_OFFSET+1
        lda #8
        sta N_COUNT
        lda #0
        sta N_COUNT+1
        jmp N_WRITE

eg_bounds:
        lda eg_index
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
eg_text_source:
        sta eg_string_read+1
        stx eg_string_read+2
        ldy #0
eg_string_read:
        lda $ffff,y
        beq +
        sta gfx_text_buffer,y
        iny
        cpy #38
        bne eg_string_read
+       sty gfx_text_length
        rts
eg_text:
        sta gfx_x0
        sty gfx_y0
        lda #0
        sta gfx_x0+1
        sta gfx_y0+1
        lda #1
        sta gfx_pen
        jmp gfx_text

eg_caption:
        ldx eg_view
        cpx #10
        bne +
        lda #<eg_opening
        ldx #>eg_opening
        ldy ed_io_phase
        cpy #1
        beq eg_label_return
        lda #<eg_saving
        ldx #>eg_saving
        cpy #2
        beq eg_label_return
        lda #<eg_verifying
        ldx #>eg_verifying
        rts
+       lda eg_title_lo,x
        pha
        lda eg_title_hi,x
        tax
        pla
        rts

eg_label:
        cpx #14
        bne +
        lda ed_mode
        cmp #6
        beq eg_label_case
        cmp #7
        beq eg_label_case
+       lda eg_label_lo,x
        pha
        lda eg_label_hi,x
        tax
        pla
eg_label_return:
        rts
eg_label_case:
        lda #<eg_case
        ldx #>eg_case
        rts

eg_enabled:
        lda eg_busy
        beq +
        cpx #20
        beq eg_enabled_yes
        sec
        rts
+       lda ed_mode
        bne eg_enabled_modal
        cpx #0
        beq eg_enabled_yes
        cpx #5
        beq eg_enabled_yes
        cpx #6
        beq eg_enabled_yes
        lda eg_more
        bne eg_enabled_more
        cpx #1
        bcc eg_enabled_no
        cpx #5
        bcc eg_enabled_yes
        sec
        rts
eg_enabled_more:
        cmp #4
        bne +
        cpx #27
        bcc eg_enabled_no
        cpx #30
        bcc eg_enabled_yes
        bcs eg_enabled_no
+
        cmp #3
        bne +
        cpx #24
        bcc eg_enabled_no
        cpx #27
        bcc eg_enabled_yes
        bcs eg_enabled_no
+       cmp #2
        bne +
        cpx #21
        bcc eg_enabled_no
        cpx #24
        bcc eg_enabled_yes
        bcs eg_enabled_no
+       cpx #7
        bcc eg_enabled_no
        cpx #11
        bcc eg_enabled_yes
        sec
        rts
eg_enabled_modal:
        cmp #5
        beq eg_enabled_confirm
        cmp #9
        beq eg_enabled_choice
        cpx #11
        bcc eg_enabled_no
        cpx #14
        bcc eg_enabled_yes
        bne eg_enabled_no
        lda ed_mode
        cmp #3
        bcc eg_enabled_yes
        cmp #6
        beq eg_enabled_yes
        cmp #7
        beq eg_enabled_yes
        sec
        rts
eg_enabled_confirm:
        cpx #15
        beq eg_enabled_yes
        cpx #16
        beq eg_enabled_yes
        sec
        rts
eg_enabled_choice:
        cpx #13
        beq eg_enabled_yes
        cpx #17
        beq eg_enabled_yes
        cpx #18
        beq eg_enabled_yes
eg_enabled_no:
        sec
        rts
eg_enabled_yes:
        clc
        rts

; Mouse hover changes control focus; a release inside the armed rectangle
; activates it. Document clicks choose a byte using the retained line table.
eg_input_entry:
        lda eg_busy
        beq +
        lda eg_key
        beq eg_mouse
        cmp #27
        beq eg_input_return
        jmp eg_input_zero
+       lda eg_key
        beq eg_mouse
        lda #0
        sta es_drag
        lda #255
        sta pm_arm
        jsr es_key
        bcs eg_input_return
        lda eg_key
        cmp #9
        beq eg_tab
        cmp #13
        beq eg_activate
        cmp #32
        bcc eg_input_return
        cmp #127
        bcs eg_input_return
        ldx #6
        lda ed_mode
        beq +
        cmp #5
        beq eg_input_return
        cmp #9
        beq eg_input_return
        ldx #11
+       jsr eg_focus
        jmp eg_input_return
eg_mouse:
        jsr pm_poll
        lda pm_pending
        bne eg_input_zero
        jsr es_mouse
        bcs eg_input_return
        lda pm_event
        beq eg_input_zero
        ldx pm_hit
        jsr eg_focus
        lda pm_event
        cmp #2
        bne eg_input_zero
eg_activate:
        ldx ui_selected
        cpx #5
        beq eg_more_toggle
        cpx #6
        beq eg_document_action
        cpx #11
        beq eg_field_action
        lda ui_keys,x
        sta eg_key
        cpx #0                 ; Close retains its normal app-exit action
        beq eg_input_return
        jsr es_key
        jmp eg_input_return
eg_field_action:
        lda eg_key
        bne eg_input_return
        lda pm_x
        sta eg_click_column
        lda pm_x+1
        lsr
        ror eg_click_column
        lsr eg_click_column
        lsr eg_click_column
        lda eg_click_column
        sec
        sbc #2
        bcs +
        lda #0
+       cmp #36
        bcc +
        lda #35
+       clc
        adc ed_field_views
        bcs eg_field_end
        cmp ed_field_len
        bcc +
eg_field_end:
        lda ed_field_len
+       sta ed_field_cursor
        jsr ed_paint_fields
        jmp eg_input_zero
eg_document_action:
        lda eg_key
        bne eg_input_return
        jsr eg_document_click
        lda #255
        sta eg_key
        jmp eg_input_return
eg_more_toggle:
        inc eg_more
        lda eg_more
        cmp #5
        bcc +
        lda #0
        sta eg_more
+
        lda #1
        sta eg_full_draw
        jsr eg_draw
        bcs eg_input_failed
        jmp eg_input_zero
eg_tab:
        ldx ui_selected
-       inx
        cpx #ui_button_count
        bcc +
        ldx #0
+       jsr eg_enabled
        bcs -
        jsr eg_focus
eg_input_zero:
        lda #0
        sta eg_key
eg_input_return:
        lda eg_key
        clc
        rts
eg_input_failed:
        jsr eg_failed
        lda #0
        sta eg_key
        rts
eg_focus:
        cpx ui_selected
        beq eg_focus_done
        stx eg_new_focus
        lda ui_selected
        sta eg_old_focus
        stx ui_selected
        ldx eg_old_focus
        cpx #6
        beq +
        jsr ui_paint
        bcs eg_input_failed
+       ldx ui_selected
        cpx #6
        beq +
        jsr ui_paint
        bcs eg_input_failed
+       lda eg_old_focus
        cmp #11
        beq eg_focus_field
        lda ui_selected
        cmp #11
        bne eg_focus_footer
eg_focus_field:
        lda #2
        sta eg_operation
        jsr eg_update
eg_focus_footer:
        jsr eg_footer_draw
eg_focus_done:
        clc
        rts

eg_document_click:
        lda pm_y
        lsr
        lsr
        lsr
        sec
        sbc #7
        sta eg_click_row
        asl
        clc
        adc eg_click_row
        tax
        lda ed_row_starts,x
        sta ed_scan
        sta eg_click_start
        lda ed_row_starts+1,x
        sta ed_scan+1
        sta eg_click_start+1
        lda ed_row_starts+2,x
        sta ed_scan+2
        sta eg_click_start+2
        jsr ed_forward_end
        lda pm_x
        sta eg_click_column
        lda pm_x+1
        lsr
        ror eg_click_column
        lsr eg_click_column
        lsr eg_click_column
        lda eg_click_column
        beq +
        dec eg_click_column
+       #es_copy3 ed_horizontal,ed_number
        clc
        lda ed_number
        adc eg_click_column
        sta ed_number
        bcc +
        inc ed_number+1
        bne +
        inc ed_number+2
+
eg_click_position:
        #es_copy3 eg_click_start,ed_cursor
        #es_add3 ed_number,ed_cursor
        #es_cmp3 ed_cursor,ed_scan
        bcc +
        #es_copy3 ed_scan,ed_cursor
+       jmp ed_normalize_cursor

pm_control_count=ui_button_count
pm_select_surface=eg_surface
pm_find_hit:
        lda pm_x
        sta ui_x
        lda pm_x+1
        sta ui_x+1
        lda pm_y
        sta ui_y
        lda #0
        sta ui_first
        lda #ui_button_count
        sta ui_limit
-       jsr ui_hit
        cpx #ui_button_count
        bcs +
        jsr eg_enabled
        bcc +
        inx
        stx ui_first
        jmp -
+       rts

eg_footer_draw:
        lda vd_phase
        bne eg_footer_done
        lda eg_bitmap
        beq eg_footer_done
        lda #1
        sta ed_screen
        jsr ed_select_screen
        ldx #23
        ldy #0
        clc
        jsr $fff0
        lda #<eg_console_help
        ldx #>eg_console_help
        jsr ed_puts
        jsr ed_clear_tail
        ldx #24
        ldy #0
        clc
        jsr $fff0
        lda #<eg_focus_caption
        ldx #>eg_focus_caption
        jsr ed_puts
        ldx ui_selected
        cpx #6
        bne +
        lda #<eg_document
        ldx #>eg_document
        jmp eg_footer_name
+       cpx #11
        bne +
        lda #<eg_field_label
        ldx #>eg_field_label
        jmp eg_footer_name
+       jsr eg_label
eg_footer_name:
        jsr ed_puts
        jsr ed_clear_tail
eg_footer_done:
        clc
        rts

; Bounded console collection preserves raw printable case and reverse cells.
eg_emit:
        php
        sta eg_character
        pha
        txa
        pha
        tya
        pha
        lda eg_character
        cmp #$93
        bne +
        lda #0
        sta eg_row
        sta eg_column
        sta eg_reverse
        beq eg_emit_done
+       cmp #13
        beq eg_newline
        cmp #$12
        bne +
        lda #128
        sta eg_reverse
        bne eg_emit_done
+       cmp #$92
        bne +
        lda #0
        sta eg_reverse
        beq eg_emit_done
+       lda eg_row
        cmp #25
        bcs eg_emit_done
        lda eg_column
        cmp #40
        bcs eg_emit_done
        lda eg_row
        jsr eg_row_pointer
        lda eg_character
        cmp #32
        bcc eg_dot
        cmp #127
        bcc +
eg_dot:
        lda #46
+       ora eg_reverse
        ldx eg_column
eg_body_write:
        sta $ffff,x
        inc eg_column
        lda eg_column
        cmp #40
        bne eg_emit_done
eg_newline:
        inc eg_row
        lda #0
        sta eg_column
eg_emit_done:
        pla
        tay
        pla
        tax
        pla
        plp
        rts

eg_row_pointer:
        ldx #0
        stx eg_address+1
        asl
        rol eg_address+1
        asl
        rol eg_address+1
        asl
        rol eg_address+1
        sta eg_address
        sta eg_row_offset
        lda eg_address+1
        sta eg_row_offset+1
        asl eg_address
        rol eg_address+1
        asl eg_address
        rol eg_address+1
        clc
        lda eg_address
        adc eg_row_offset
        sta eg_address
        lda eg_address+1
        adc eg_row_offset+1
        sta eg_address+1
        clc
        lda eg_address
        adc #<eg_body
        sta eg_row_read+1
        sta eg_body_write+1
        lda eg_address+1
        adc #>eg_body
        sta eg_row_read+2
        sta eg_body_write+2
        rts

eg_field:
        lda N_UIPTR
        sta eg_state_read+1
        sta eg_state_write+1
        sta eg_field_state
        lda N_UIPTR+1
        sta eg_state_read+2
        sta eg_state_write+2
        sta eg_field_state+1
        ldx #7
eg_state_read:
        lda $ffff,x
        sta eg_field_data,x
        dex
        bpl eg_state_read
        lda eg_field_data+3
        sta eg_field_read+1
        lda eg_field_data+4
        sta eg_field_read+2
        lda N_UIWIDTH
        sec
        sbc #2
        sta eg_field_capacity
        lda eg_field_data
        sec
        sbc eg_field_capacity
        bcs +
        lda #255
+       clc
        adc #1
        cmp eg_field_data+5
        bcs +
        sta eg_field_data+5
+
        lda eg_field_data+1
        cmp eg_field_data+5
        bcs +
        sta eg_field_data+5
+       lda eg_field_data+1
        sec
        sbc eg_field_data+5
        cmp eg_field_capacity
        bcc +
        lda eg_field_data+1
        sec
        sbc eg_field_capacity
        clc
        adc #1
        sta eg_field_data+5
+       lda eg_field_data+5
        ldx #5
eg_state_write:
        sta $ffff,x
        lda #32
        ldx eg_field_data+5
        beq +
        lda #$3c
+       jsr eg_emit
        lda eg_field_data+1
        sec
        sbc eg_field_data+5
        clc
        adc eg_column
        sta eg_caret_column
        lda eg_column
        sta eg_field_column
        lda #0
        sta eg_field_index
eg_field_next:
        lda eg_field_index
        clc
        adc eg_field_data+5
        bcs eg_field_blank
        cmp eg_field_data
        bcs eg_field_blank
        tax
eg_field_read:
        lda $ffff,x
        jmp eg_field_emit
eg_field_blank:
        lda #32
eg_field_emit:
        jsr eg_emit
        inc eg_field_index
        lda eg_field_index
        cmp eg_field_capacity
        bne eg_field_next
        lda eg_field_data
        sec
        sbc eg_field_data+5
        cmp eg_field_capacity
        beq +
        bcc +
        lda #$3e
        bne eg_field_tail
+       lda #32
eg_field_tail:
        jmp eg_emit


eg_started: .byte 0
eg_busy: .byte 0
eg_view: .byte 0
eg_last_view: .byte 255
eg_more=$5fb5                 ; retain the selected toolbar across module loads
eg_last_more: .byte 0
eg_last_phase: .byte 0
eg_full_draw: .byte 0
eg_mapping: .byte 0
eg_source_row: .byte 0
eg_target_row: .byte 0
eg_source_column: .byte 0
eg_target_column: .byte 0
eg_left: .byte 0
eg_cell: .byte 0
eg_inverse: .byte 0
eg_row: .byte 0
eg_column: .byte 0
eg_reverse: .byte 0
eg_character: .byte 0
eg_address: .word 0
eg_row_offset: .word 0
eg_index: .byte 0
eg_text_width: .byte 0
eg_text_x: .word 0
eg_old_focus: .byte 0
eg_new_focus: .byte 0
eg_click_row: .byte 0
eg_click_column: .byte 0
eg_click_start: .fill 3,0
eg_caret_column: .byte 0
eg_field_state: .word 0
eg_field_data: .fill 8,0
eg_field_capacity: .byte 0
eg_field_column: .byte 0
eg_field_index: .byte 0
ui_selected: .byte 6
eg_body=$5800
eg_cache=$5c00
eg_cache_lo: .byte <(eg_cache+0),<(eg_cache-5),<(eg_cache+34),<(eg_cache+0),<(eg_cache+0),<(eg_cache+0),<(eg_cache+74),<(eg_cache+114),<(eg_cache+154),<(eg_cache+194),<(eg_cache+234),<(eg_cache+274),<(eg_cache+314),<(eg_cache+354),<(eg_cache+394),<(eg_cache+434),<(eg_cache+474),<(eg_cache+514),<(eg_cache+554),<(eg_cache+594),<(eg_cache+634),<(eg_cache+674),<(eg_cache+714),<(eg_cache+0),<(eg_cache+754)
eg_cache_hi: .byte >(eg_cache+0),>(eg_cache-5),>(eg_cache+34),>(eg_cache+0),>(eg_cache+0),>(eg_cache+0),>(eg_cache+74),>(eg_cache+114),>(eg_cache+154),>(eg_cache+194),>(eg_cache+234),>(eg_cache+274),>(eg_cache+314),>(eg_cache+354),>(eg_cache+394),>(eg_cache+434),>(eg_cache+474),>(eg_cache+514),>(eg_cache+554),>(eg_cache+594),>(eg_cache+634),>(eg_cache+674),>(eg_cache+714),>(eg_cache+0),>(eg_cache+754)
eg_frame: .word 0,0,320,200
eg_cells: .word 0,0,40,25
eg_case_region: .word 16,88,296,96
; source row, target row, source column, target column, length.
eg_maps: .byte 1,1,5,1,34,2,5,0,0,40
         .byte 7,7,0,0,40,8,8,0,0,40,9,9,0,0,40,10,10,0,0,40
         .byte 11,11,0,0,40,12,12,0,0,40,13,13,0,0,40,14,14,0,0,40
         .byte 15,15,0,0,40,16,16,0,0,40,17,17,0,0,40,18,18,0,0,40
         .byte 19,19,0,0,40,20,20,0,0,40,21,21,0,0,40,22,22,0,0,40,255
.include "selection.inc"
.include "buttons.inc"
.include "../graphics/buttons.inc"
.include "../graphics/graphics-core.inc"
.include "../graphics/text-core.inc"
.include "../input/pointer.inc"
