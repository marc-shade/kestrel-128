; Native Kestrel plain-text editor with banked, byte-preserving documents. GPL v3.
.include "api.inc"
.weak
NATIVE_EDITOR_GRAPHICS=0
.endweak
.if NATIVE_EDITOR_GRAPHICS
DOC_COMPACT=1
DOC_HISTORY=1
DOC_PARTIAL=1
ED_ABI=14
GFX_FONT_COLUMNS=1
.include "editor/selection-macros.inc"
ED_PAGES=96
DOC_INPUT_STORAGE=$5000
DOC_OUTPUT_STORAGE=$5200
DOC_STATE_STORAGE=$5700
DOC_TRANSIENT_STORAGE=$5f18
DOC_EXTERNAL_MEMORY=1
doc_storage_read=dm_read
doc_storage_write=dm_write
NK_SAVED_BUFFER=$5600
GFX_TEXT_STORAGE=$5fc0
.else
ED_ABI=7
ED_PAGES=79
.endif
* = N_APPBASE
editor_image:
        .text "napp"
        .byte 1,1,ED_ABI,< (editor_module-editor_image)
        .word editor_module-editor_image
        .byte ED_PAGES,> (editor_module-editor_image)
        .word editor_entry-editor_image
        .word 0
        .text "text editor",0
        .fill N_APPBASE+32-*,0
DOC_REPLACE_EXTERNAL = 1
DOC_REPLACE_SPAN24 = NATIVE_EDITOR_GRAPHICS
.include "document.inc"

; UI navigation can trade a few loop cycles for a smaller executable.
ed_move3 .macro source,dest
 .if NATIVE_EDITOR_GRAPHICS
        #es_copy3 \source,\dest
 .else
        #doc_copy3 \source,\dest
 .endif
.endm

ed_advance3 .macro source,dest
 .if NATIVE_EDITOR_GRAPHICS
        #es_add3 \source,\dest
 .else
        #doc_add3 \source,\dest
 .endif
.endm

ed_retreat3 .macro source,dest
 .if NATIVE_EDITOR_GRAPHICS
        #es_sub3 \source,\dest
 .else
        #doc_sub3 \source,\dest
 .endif
.endm

editor_entry:
        cld
.if NATIVE_EDITOR_GRAPHICS
        jsr eg_workspace
        bcc +
        jmp N_EXIT
+
.endif
        jsr ed_keys_install
        jsr doc_init
        lda #0
        sta ed_active
        jsr ed_reset_view
        lda N_BROWSERFMT
        cmp #3
        bne ed_source_iec
        lda N_BROWSERDEV
        beq ed_source_default
        cmp #3
        bcs ed_source_default
        sta ed_device
        lda #3
        sta ed_format
        jmp ed_source_ready
ed_source_iec:
        lda N_BROWSERDEV
        cmp #8
        bcc ed_source_default
        cmp #31
        bcs ed_source_default
        sta ed_device
        lda N_BROWSERFMT
        cmp #3
        bcs ed_source_default
        sta ed_format
        jmp ed_source_ready
ed_source_default:
        lda N_DEVICE
        sta ed_device
        lda N_APPFORMAT
        sta ed_format
ed_source_ready:
.if NATIVE_EDITOR_GRAPHICS
        lda N_DOCREQUEST
        beq +
        lda #3
        jsr ed_module_load
        bcs ed_picker_failed
        lda #0
        sta ed_clip_key
        jsr N_MCALL
        bcs ed_picker_failed
        ; Match ordinary startup: the display acquires its provider before
        ; document/history backing can retain it without an REU lease.
        jsr ed_show
        jsr dm_ensure
        jmp ed_open_file
+
.endif
        jmp ed_refresh
cloop:
.if NATIVE_EDITOR_GRAPHICS
        jsr dm_ensure
        jsr eg_repair_text
.endif
        lda #1
        sta N_READY
ed_get_key:
.if NATIVE_EDITOR_GRAPHICS
        lda #0
        sta ed_structure
        sta ed_document_changed
        sta eh_warning
.endif
        jsr N_KEYIN
.if NATIVE_EDITOR_GRAPHICS
        jsr eg_input
.endif
        beq cloop
        ldx #0
        stx N_READY
.if !NATIVE_EDITOR_GRAPHICS
        stx ed_structure
        stx ed_document_changed
.else
        cmp #$fe
        beq ed_refresh
        cmp #$ff
        beq ed_cursor_changed
.endif
        ldx ed_mode
        bne ed_prompt_key
.if NATIVE_EDITOR_GRAPHICS
        cmp #12
        beq ed_graphics_retry
        ldx #ED_CLIP_KEY_COUNT-1    ; the clipboard module's keys (X is ed_mode, 0)
-       cmp ed_clip_keys,x
        beq ed_clip_launch
        dex
        bpl -
        inx
.endif
        cmp #27
        beq ed_request_exit
        cmp #$85
        beq ed_prompt_open
        cmp #$86
        beq ed_prompt_save
        cmp #$87
        beq ed_request_new
        cmp #$88
        beq ed_prompt_goto
        cmp #$8c
        beq ed_prompt_device
        cmp #$8b
        beq ed_next_format
        cmp #$89
        beq ed_top
        cmp #$8a
        beq ed_bottom
        cmp #$13
        beq ed_home
        cmp #$05
        beq ed_end
        cmp #$06
        beq ed_search_launch
        cmp #$0e
        beq ed_search_launch
        cmp #$12
        beq ed_search_launch
        cmp #$9d
        beq ed_left
        cmp #$1d
        beq ed_right
        cmp #$91
        beq ed_up
        cmp #$11
        beq ed_down
        cmp #$14
        beq ed_backspace
        cmp #13
        beq ed_enter
        cmp #32
        bcc cloop
        cmp #127
        bcs cloop
        sta d_input
        lda #1
        sta d_count
        lda #0
        sta d_count+1
        jmp ed_insert

ed_prompt_open:
        lda #1
        bne ed_prompt_begin
ed_prompt_save:
        lda #2
        bne ed_prompt_begin
ed_prompt_goto:
        lda #3
        bne ed_prompt_begin
ed_prompt_device:
        lda #4
ed_prompt_begin:
        sta ed_mode
        lda #0
        sta ed_field_len
        sta ed_field
        sta ed_status
        sta ed_file_type
        sta N_UIKEY
        jsr ed_field_call
        bcs ed_input_error
        jmp ed_field_refresh
ed_request_new:
        lda #5
        bne ed_check_dirty
ed_request_exit:
        lda #6
ed_check_dirty:
        sta ed_action
        ldx ed_active
        lda d_states+D_DIRTY,x
        ora d_states+D_FAULT,x
        beq ed_confirmed
        lda #5
        sta ed_mode
        lda #0
        sta ed_status
        jmp ed_field_refresh
ed_confirmed:
        lda #0
        sta ed_mode
        lda ed_action
        cmp #1
        beq ed_open_file
        cmp #5
        beq ed_new_document
 .if NATIVE_EDITOR_GRAPHICS
        jsr eg_close
        bcs ed_doc_error
        jsr ed_close_owned
        bcs ed_exit          ; native exit quarantines an uncertain file owner
        jsr dm_cleanup
        bcs ed_doc_error
 .endif
ed_exit:
        jsr ed_keys_restore
        lda #0
        jmp N_EXIT
ed_new_document:
        jsr ed_close_owned
        bcs ed_file_close_error
        lda ed_active
        sta d_slot
        jsr doc_dispose
        bcs ed_doc_error
        jsr ed_reset_view
        jmp ed_refresh
ed_reset_view:
.if NATIVE_EDITOR_GRAPHICS
        jsr eh_reset
        jsr es_clear
.endif
        lda #0
        ldx #2
ed_reset_positions:
        sta ed_cursor,x
        sta ed_view,x
        sta ed_horizontal,x
        dex
        bpl ed_reset_positions
        sta ed_name
        sta ed_newline
        sta ed_mode
        sta ed_status
        sta ed_goal_valid
        sta ed_cache_valid
        sta ed_other_valid
        rts

ed_prompt_key:
        cmp #27
        beq ed_prompt_cancel
        ldx ed_mode
        cpx #9
        beq ed_replace_choice
        cpx #5
        bne ed_field_key
        and #$df
        cmp #$59
        beq ed_confirmed
        cmp #$4e
        beq ed_prompt_cancel
        jmp cloop
ed_field_key:
.if NATIVE_EDITOR_GRAPHICS
        cmp #$88
        bne +
        ldx ed_mode
        cpx #3
        bcc ed_browse
+
.endif
        cmp #9
        bne +
        ldx ed_mode
        cpx #6
        beq ed_search_case
        cpx #7
        beq ed_search_case
        cpx #3
        bcs cloop
        jmp ed_browse
+        cmp #13
        beq ed_field_enter
        sta N_UIKEY
        jsr ed_field_call
        bcs ed_input_error
        lda N_UIFLAGS
        beq cloop
        lda #0
        sta ed_status
        jmp ed_field_refresh
ed_input_error:
        lda #12
        sta ed_status
        jmp ed_field_refresh
ed_field_call:
        lda #16
        ldx #3
        ldy ed_mode
        cpy #3
        bcs ed_field_numeric
        ldy ed_format
        cpy #3
        bne ed_field_configured
        lda #255
        ldx #0
        beq ed_field_configured
ed_field_numeric:
        cpy #6
        bcc +
        lda #64
        ldx #0
        beq ed_field_configured
+
        lda #6
        ldx #2
        cpy #4
        bne ed_field_configured
        lda #2
        ldx #1
ed_field_configured:
        sta ed_field_max
        stx ed_field_filter
        jsr ed_field_pointer
        jmp N_FEDIT
ed_field_pointer:
        lda #<ed_field_state
        sta N_UIPTR
        lda #>ed_field_state
        sta N_UIPTR+1
        rts
ed_prompt_cancel:
        lda #0
        sta ed_mode
        sta ed_status
        ldx ed_s_running
        bne ed_search_return
        jmp ed_field_refresh
ed_field_enter:
        lda ed_mode
        cmp #8
        beq ed_replacement_enter
        lda ed_field_len
        beq cloop
        lda ed_mode
        cmp #1
        beq ed_open_confirm
        cmp #2
        beq ed_save_file
        cmp #4
        beq ed_device_enter
        cmp #6
        bcs ed_search_enter
        lda #0
        sta ed_number
        sta ed_number+1
        sta ed_number+2
        tax
ed_hex_parse:
        ldy #4
ed_hex_shift:
        asl ed_number
        rol ed_number+1
        rol ed_number+2
        dey
        bne ed_hex_shift
        lda ed_field,x
        sec
        sbc #$30
        cmp #10
        bcc +
        sbc #7
+       ora ed_number
        sta ed_number
        inx
        cpx ed_field_len
        bne ed_hex_parse
        #doc_cmp3 ed_length,ed_number
        bcc ed_bad_position
 .if NATIVE_EDITOR_GRAPHICS
        jsr es_clear
 .endif
        #ed_move3 ed_number,ed_cursor
        jsr ed_normalize_cursor
        lda #0
        sta ed_mode
        jmp ed_cursor_changed
ed_device_enter:
        lda ed_field
        sec
        sbc #$30
        ldx ed_field_len
        cpx #1
        beq ed_device_check
        asl
        sta ed_number
        asl
        asl
        clc
        adc ed_number
        adc ed_field+1
        sec
        sbc #$30
ed_device_check:
        ldx ed_format
        cpx #3
        bne ed_iec_check
        cmp #1
        bcc ed_bad_position
        cmp #3
        bcs ed_bad_position
        bcc ed_device_keep
ed_iec_check:
        cmp #8
        bcc ed_bad_position
        cmp #31
        bcs ed_bad_position
ed_device_keep:
        sta ed_device
        sta N_BROWSERDEV
        lda ed_format
        sta N_BROWSERFMT
        lda #0
        sta ed_mode
        sta ed_status
        jmp ed_refresh
ed_bad_position:
        lda #4
        sta ed_status
        jmp ed_field_refresh
ed_open_confirm:
        lda #1
        jmp ed_check_dirty
ed_next_format:
        inc ed_format
        lda ed_format
        cmp #4
        bcc +
        lda #0
        sta ed_format
+       lda ed_format
        sta N_BROWSERFMT
        cmp #3
        bne ed_format_iec
        lda #1
        bne ed_format_device
ed_format_iec:
        lda ed_device
        cmp #8
        bcs ed_format_done
        lda #8
ed_format_device:
        sta ed_device
        sta N_BROWSERDEV
ed_format_done:
        jmp ed_refresh

ed_enter:
        lda #1
        sta ed_structure
        lda #13
        ldx ed_newline
        cpx #1
        bne +
        lda #10
+       sta d_input
        lda #1
        cpx #2
        bne +
        lda #10
        sta d_input+1
        lda #2
+       sta d_count
        lda #0
        sta d_count+1
ed_insert:
        #ed_move3 ed_cursor,d_pos
.if NATIVE_EDITOR_GRAPHICS
        jsr eh_insert
.else
        jsr doc_insert
.endif
        bcs ed_doc_error
        lda #1
        sta ed_document_changed
        sta ed_edit_delta
        #doc_add3 d_count,ed_cursor
        jmp ed_cursor_changed
ed_backspace:
        #ed_move3 ed_cursor,ed_scan
        jsr ed_previous_end
        bcs cloop
        #doc_cmp3 ed_scan,ed_line_start
        bcs +
        lda #1
        sta ed_structure
+
        #ed_move3 ed_scan,d_pos
        #ed_move3 ed_cursor,d_count
        #doc_sub3 ed_scan,d_count
.if NATIVE_EDITOR_GRAPHICS
        jsr eh_delete
.else
        jsr doc_delete
.endif
        bcs ed_doc_error
        lda #1
        sta ed_document_changed
        lda #$ff
        sta ed_edit_delta
        #ed_move3 ed_scan,ed_cursor
        jmp ed_cursor_changed
ed_doc_error:
        cmp #N_NOMEM
        beq ed_no_memory
        cmp #N_NOSLOT
        beq ed_no_memory
        lda #5
        bne ed_show_error
ed_no_memory:
        lda #3
ed_show_error:
        sta ed_status
        jmp ed_refresh
ed_cursor_changed:
        lda #0
        sta ed_status
        sta ed_goal_valid
        jmp ed_refresh_edit
ed_top:
        lda #0
        sta ed_cursor
        sta ed_cursor+1
        sta ed_cursor+2
        jmp ed_cursor_changed
ed_bottom:
        #ed_move3 ed_length,ed_cursor
        jmp ed_cursor_changed
ed_home:
        #ed_move3 ed_line_start,ed_cursor
        jmp ed_cursor_changed
ed_end:
        #ed_move3 ed_line_end,ed_cursor
        jmp ed_cursor_changed
ed_left:
        #ed_move3 ed_cursor,ed_scan
        jsr ed_previous_end
        bcs cloop
        #ed_move3 ed_scan,ed_cursor
        jmp ed_cursor_changed
ed_right:
        #doc_cmp3 ed_cursor,ed_length
        bcs cloop
        #ed_move3 ed_cursor,ed_fetch
        jsr ed_next_token
        #ed_move3 ed_fetch,ed_cursor
        jmp ed_cursor_changed
ed_keep_column:
        lda ed_goal_valid
        bne +
        #ed_move3 ed_column,ed_goal
        inc ed_goal_valid
+       rts
ed_up:
        jsr ed_keep_column
        #ed_move3 ed_line_start,ed_scan
        jsr ed_previous_end
        bcs cloop
        #ed_move3 ed_scan,ed_target_end
        jsr ed_backward_start
        jmp ed_vertical_target
ed_down:
        jsr ed_keep_column
        #ed_move3 ed_line_end,ed_scan
        #doc_cmp3 ed_scan,ed_length
        bcs cloop
        jsr ed_after_line
        #ed_move3 ed_scan,ed_target_start
        jsr ed_forward_end
        #ed_move3 ed_scan,ed_target_end
        #ed_move3 ed_target_start,ed_scan
ed_vertical_target:
        #doc_add3 ed_goal,ed_scan
        #doc_cmp3 ed_target_end,ed_scan
        bcs +
        #ed_move3 ed_target_end,ed_scan
+       #ed_move3 ed_scan,ed_cursor
        lda #0
        sta ed_status
        jmp ed_refresh_edit

; Two logical 512-byte pages cover a line crossing a page/bank boundary.
; The primary page shares d_output; file operations and edits invalidate both.
; Cursor scans never move the document's gap.
ed_byte_at:
        #doc_cmp3 ed_probe,ed_length
        bcs ed_byte_absent
        lda ed_cache_valid
        beq ed_cache_other
        lda ed_probe+2
        cmp ed_cache_base+2
        bne ed_cache_other
        lda ed_probe+1
        and #$fe
        cmp ed_cache_base+1
        beq ed_cache_ready
ed_cache_other:
        lda ed_other_valid
        beq ed_cache_load
        lda ed_probe+2
        cmp ed_other_base+2
        bne ed_cache_load
        lda ed_probe+1
        and #$fe
        cmp ed_other_base+1
        bne ed_cache_load
        lda #<ed_other_page
        ldx #>ed_other_page
        jmp ed_cache_pointer
ed_cache_load:
        lda ed_cache_valid
        beq ed_cache_read_page
        ldx #0
ed_cache_keep:
        lda d_output,x
        sta ed_other_page,x
        lda d_output+256,x
        sta ed_other_page+256,x
        inx
        bne ed_cache_keep
        #ed_move3 ed_cache_base,ed_other_base
        lda #1
        sta ed_other_valid
ed_cache_read_page:
        lda #0
        sta ed_cache_valid
        sta d_pos
        sta ed_cache_base
        lda ed_probe+1
        and #$fe
        sta d_pos+1
        sta ed_cache_base+1
        lda ed_probe+2
        sta d_pos+2
        sta ed_cache_base+2
        lda #0
        sta d_count
        lda #2
        sta d_count+1
        jsr doc_read
        bcs ed_cache_error
        lda #1
        sta ed_cache_valid
ed_cache_ready:
        lda #<d_output
        ldx #>d_output
ed_cache_pointer:
        stx ed_cache_read+2
        clc
        adc ed_probe
        sta ed_cache_read+1
        lda ed_probe+1
        and #1
        adc ed_cache_read+2
        sta ed_cache_read+2
ed_cache_read:
        lda $ffff
        clc
        rts
ed_cache_error:
        lda #0
        sta ed_cache_valid
        sta ed_other_valid
        lda #5
        sta ed_status
ed_byte_absent:
        lda #0
        sec
        rts
ed_normalize_cursor:
        #ed_move3 ed_cursor,ed_probe
        jsr ed_byte_at
        bcs +
        cmp #10
        bne +
        lda ed_cursor
        ora ed_cursor+1
        ora ed_cursor+2
        beq +
        #ed_retreat3 ed_one,ed_probe
        jsr ed_byte_at
        cmp #13
        bne +
        #doc_add3 ed_one,ed_cursor
+       rts
ed_previous_end:
        lda ed_scan
        ora ed_scan+1
        ora ed_scan+2
        beq ed_previous_none
        #ed_retreat3 ed_one,ed_scan
        #ed_move3 ed_scan,ed_probe
        jsr ed_byte_at
        cmp #10
        bne ed_previous_done
        lda ed_scan
        ora ed_scan+1
        ora ed_scan+2
        beq ed_previous_done
        #ed_retreat3 ed_one,ed_probe
        jsr ed_byte_at
        cmp #13
        bne ed_previous_done
        #ed_move3 ed_probe,ed_scan
ed_previous_done:
        clc
        rts
ed_previous_none:
        sec
        rts
ed_backward_start:
        lda ed_scan
        ora ed_scan+1
        ora ed_scan+2
        beq ed_scan_done
        #ed_move3 ed_scan,ed_probe
        #ed_retreat3 ed_one,ed_probe
        jsr ed_byte_at
        bcs ed_scan_done
        cmp #13
        beq ed_scan_done
        cmp #10
        beq ed_scan_done
        #ed_move3 ed_probe,ed_scan
        jmp ed_backward_start
ed_forward_end:
        #ed_move3 ed_scan,ed_probe
        jsr ed_byte_at
        bcs ed_scan_done
        cmp #13
        beq ed_scan_done
        cmp #10
        beq ed_scan_done
        #doc_add3 ed_one,ed_scan
        jmp ed_forward_end
ed_scan_done:
        rts
ed_after_line:
        #ed_move3 ed_scan,ed_fetch
        jsr ed_next_token
        #ed_move3 ed_fetch,ed_scan
        rts
ed_next_token:
        #ed_move3 ed_fetch,ed_token_start
        #ed_move3 ed_fetch,ed_probe
        jsr ed_byte_at
        bcs ed_token_eof
        sta ed_byte
        #ed_advance3 ed_one,ed_fetch
        lda ed_byte
        cmp #13
        bne ed_token_done
        #ed_move3 ed_fetch,ed_probe
        jsr ed_byte_at
        bcs ed_token_done
        cmp #10
        bne ed_token_done
        #ed_advance3 ed_one,ed_fetch
ed_token_done:
        lda #0
        sta ed_eof
        lda ed_byte
        rts
ed_token_eof:
        lda #1
        sta ed_eof
        lda #0
        sta ed_byte
        rts

ed_refresh:
        lda #1
        sta ed_full
        jsr ed_invalidate_pages
        jmp ed_refresh_prepare
ed_refresh_edit:
        lda ed_structure
.if NATIVE_EDITOR_GRAPHICS
        ora es_active
        ora es_dirty
.endif
        sta ed_full
.if NATIVE_EDITOR_GRAPHICS
        lda #0
        sta es_dirty
.endif
        lda ed_document_changed
        beq ed_refresh_prepare
        jsr ed_invalidate_pages
        jsr ed_adjust_lines
ed_refresh_prepare:
.if NATIVE_EDITOR_GRAPHICS
        jsr eh_notice
.endif
        lda ed_active
        sta d_slot
        #doc_load3 D_LEN,ed_length
        ldx ed_active
        lda d_states+D_FAULT,x
        bne ed_refresh_draw
        jsr ed_locate
        lda ed_full
        bne ed_refresh_draw
        #doc_cmp3 ed_view,ed_last_view
        bne ed_refresh_draw
        #doc_cmp3 ed_horizontal,ed_last_horizontal
        bne ed_refresh_draw
        jsr ed_show_partial
        jmp ed_refresh_done
ed_refresh_draw:
        jsr ed_show
ed_refresh_done:
        #ed_move3 ed_view,ed_last_view
        #ed_move3 ed_horizontal,ed_last_horizontal
        lda ed_cursor_row
        sta ed_last_row
        jmp cloop
ed_locate:
        #ed_move3 ed_cursor,ed_scan
        jsr ed_backward_start
        #ed_move3 ed_scan,ed_line_start
        #ed_move3 ed_cursor,ed_column
        #doc_sub3 ed_scan,ed_column
        #ed_move3 ed_cursor,ed_scan
        jsr ed_forward_end
        #ed_move3 ed_scan,ed_line_end
        #doc_cmp3 ed_column,ed_horizontal
        bcc ed_scroll_left
        #ed_move3 ed_column,ed_number
        #doc_sub3 ed_horizontal,ed_number
        lda ed_number+1
        ora ed_number+2
        bne ed_scroll_right
        lda ed_number
        cmp #38
        bcc ed_fit_vertical
ed_scroll_right:
        #ed_move3 ed_column,ed_horizontal
        #doc_sub3 ed_width_minus_one,ed_horizontal
        jmp ed_fit_vertical
ed_scroll_left:
        #ed_move3 ed_column,ed_horizontal
ed_fit_vertical:
        lda ed_full
        bne ed_find_view
        ldx #0
        ldy #0
ed_cached_line:
        lda ed_line_start
        cmp ed_row_starts,x
        bne ed_cached_next
        lda ed_line_start+1
        cmp ed_row_starts+1,x
        bne ed_cached_next
        lda ed_line_start+2
        cmp ed_row_starts+2,x
        beq ed_cached_found
ed_cached_next:
        inx
        inx
        inx
        iny
        cpy #16
        bne ed_cached_line
ed_find_view:
        #doc_cmp3 ed_line_start,ed_view
        bcc ed_view_at_cursor
        #ed_move3 ed_view,ed_scan
        lda #16
        sta ed_scan_rows
ed_view_check:
        #doc_cmp3 ed_scan,ed_line_start
        beq ed_located
        dec ed_scan_rows
        beq ed_view_bottom
        jsr ed_forward_end
        jsr ed_after_line
        jmp ed_view_check
ed_view_bottom:
        #ed_move3 ed_line_start,ed_scan
        lda #15
        sta ed_scan_rows
ed_view_back:
        jsr ed_previous_end
        bcs ed_view_save
        jsr ed_backward_start
        dec ed_scan_rows
        bne ed_view_back
ed_view_save:
        #ed_move3 ed_scan,ed_view
        lda #15
        sec
        sbc ed_scan_rows
        sta ed_cursor_row
        rts
ed_view_at_cursor:
        #ed_move3 ed_line_start,ed_view
        lda #0
        sta ed_cursor_row
        rts
ed_located:
        lda #16
        sec
        sbc ed_scan_rows
        sta ed_cursor_row
        rts
ed_cached_found:
        sty ed_cursor_row
        rts

ed_invalidate_pages:
        lda #0
        sta ed_cache_valid
        sta ed_other_valid
        rts
; A successful single-byte edit shifts only later line offsets. Structural
; changes rebuild the viewport table during the full render instead.
ed_adjust_lines:
        lda ed_structure
        bne ed_lines_adjusted
        lda ed_last_row
        clc
        adc #1
        sta ed_adjust_row
        asl
        clc
        adc ed_adjust_row
        tax
ed_adjust_line:
        lda ed_edit_delta
        cmp #1
        bne ed_adjust_subtract
        inc ed_row_starts,x
        bne ed_adjust_next
        inc ed_row_starts+1,x
        bne ed_adjust_next
        inc ed_row_starts+2,x
        jmp ed_adjust_next
ed_adjust_subtract:
        lda ed_row_starts,x
        bne ed_adjust_low
        lda ed_row_starts+1,x
        bne ed_adjust_middle
        dec ed_row_starts+2,x
ed_adjust_middle:
        dec ed_row_starts+1,x
ed_adjust_low:
        dec ed_row_starts,x
ed_adjust_next:
        inx
        inx
        inx
        cpx #51
        bcc ed_adjust_line
ed_lines_adjusted:
        rts

; Repaint only the input/status row; document offsets and its read cache
; remain valid while a modal field changes.
ed_field_refresh:
        jsr ed_paint_fields
        jmp cloop
ed_paint_fields:
.if NATIVE_EDITOR_GRAPHICS
        lda #2
        jsr eg_render
        jsr eg_screen_start
.else
        lda #0
.endif
        sta ed_screen
ed_field_screen:
.if NATIVE_EDITOR_GRAPHICS
        lda ed_screen
        cmp #2
        bcs ed_field_screens_done
.endif
        jsr ed_select_screen
        jsr ed_paint_status
 .if NATIVE_EDITOR_GRAPHICS
        lda eg_collect
        bne +
 .endif
        inc ed_screen
        lda ed_screen
        cmp #2
        bne ed_field_screen
 .if NATIVE_EDITOR_GRAPHICS
+
 .endif
.if NATIVE_EDITOR_GRAPHICS
ed_field_screens_done:
        jsr eg_footer
.endif
        rts

ed_show:
.if NATIVE_EDITOR_GRAPHICS
        lda #0
        jsr eg_render
        jsr eg_screen_start
.else
        lda #0
.endif
        sta ed_screen
ed_show_screen:
.if NATIVE_EDITOR_GRAPHICS
        lda ed_screen
        cmp #2
        bcs ed_show_screens_done
.endif
        jsr ed_select_screen
        lda #$93
        jsr ed_chrout
        lda #<ed_title
        ldx #>ed_title
        jsr ed_puts
        jsr ed_heading
        lda #<ed_help
        ldx #>ed_help
        jsr ed_puts
        jsr ed_status_show
        jsr ed_clear_tail
        lda #13
        jsr ed_chrout
        lda #0
        sta ed_row
        sta ed_caret_drawn
        #ed_move3 ed_view,ed_fetch
ed_show_row:
        jsr ed_remember_row
        jsr ed_text_row
        inc ed_row
        lda ed_row
        cmp #16
        bne ed_show_row
        jsr ed_remember_row
        lda #<ed_search_help
        ldx #>ed_search_help
        jsr ed_puts
 .if NATIVE_EDITOR_GRAPHICS
        lda eg_collect
        bne +
 .endif
        inc ed_screen
        lda ed_screen
        cmp #2
        bne ed_show_screen
 .if NATIVE_EDITOR_GRAPHICS
+
 .endif
.if NATIVE_EDITOR_GRAPHICS
ed_show_screens_done:
        lda vd_phase
        bne +
        lda eg_collect
        bne +
        sta eg_text_pending
+
        jsr eg_footer
.endif
        rts

; Cursor moves and edits within one logical line preserve the viewport.
; Redraw the old and new caret rows, plus mutable headings/status. Scrolling,
; line splits/joins, file operations and new documents use the complete path.
ed_show_partial:
.if NATIVE_EDITOR_GRAPHICS
        lda #1
        jsr eg_render
.endif
        lda ed_last_row
        cmp ed_cursor_row
        bcs +
        lda ed_cursor_row
+       clc
        adc #1
        sta ed_row_limit
.if NATIVE_EDITOR_GRAPHICS
        jsr eg_screen_start
.else
        lda #0
.endif
        sta ed_screen
ed_partial_screen:
.if NATIVE_EDITOR_GRAPHICS
        lda ed_screen
        cmp #2
        bcs ed_partial_screens_done
.endif
        jsr ed_select_screen
        ldx #1
        ldy #0
        clc
 .if NATIVE_EDITOR_GRAPHICS
        jsr eg_plot
 .else
        jsr $fff0
 .endif
        lda #<ed_name_text
        ldx #>ed_name_text
        jsr ed_puts
        jsr ed_heading
        jsr ed_paint_status
        lda #0
        sta ed_row
        sta ed_caret_drawn
ed_partial_row:
        lda ed_row
        cmp ed_last_row
        beq ed_partial_paint
        cmp ed_cursor_row
        beq ed_partial_paint
        jmp ed_partial_next
ed_partial_paint:
        jsr ed_row_index
        lda ed_row_starts,x
        sta ed_fetch
        lda ed_row_starts+1,x
        sta ed_fetch+1
        lda ed_row_starts+2,x
        sta ed_fetch+2
        lda ed_row
        clc
        adc #7
        tax
        ldy #0
        clc
 .if NATIVE_EDITOR_GRAPHICS
        jsr eg_plot
 .else
        jsr $fff0
 .endif
        jsr ed_text_row
ed_partial_next:
        inc ed_row
        lda ed_row
        cmp ed_row_limit
        bne ed_partial_row
 .if NATIVE_EDITOR_GRAPHICS
        lda eg_collect
        bne +
 .endif
        inc ed_screen
        lda ed_screen
        cmp #2
        bne ed_partial_screen
 .if NATIVE_EDITOR_GRAPHICS
+
 .endif
.if NATIVE_EDITOR_GRAPHICS
ed_partial_screens_done:
        jsr eg_footer
.endif
        rts
ed_row_index:
        lda ed_row
        asl
        clc
        adc ed_row
        tax
        rts
ed_remember_row:
        jsr ed_row_index
        lda ed_fetch
        sta ed_row_starts,x
        lda ed_fetch+1
        sta ed_row_starts+1,x
        lda ed_fetch+2
        sta ed_row_starts+2,x
        rts

ed_text_row:
        lda #0
        sta ed_row_ended
        sta ed_col
        #ed_move3 ed_horizontal,ed_skip
ed_skip_columns:
        lda ed_skip
        ora ed_skip+1
        ora ed_skip+2
        beq ed_row_prefix
        jsr ed_next_token
        lda ed_eof
        bne ed_skip_ended
        lda ed_byte
        cmp #13
        beq ed_skip_ended
        cmp #10
        beq ed_skip_ended
        #ed_retreat3 ed_one,ed_skip
        jmp ed_skip_columns
ed_skip_ended:
        inc ed_row_ended
ed_row_prefix:
        lda ed_horizontal
        ora ed_horizontal+1
        ora ed_horizontal+2
        beq +
        lda #$3c
        bne ed_prefix_print
+       lda #32
ed_prefix_print:
        jsr ed_chrout
ed_text_column:
        lda ed_row_ended
        bne ed_padding
        jsr ed_next_token
        lda ed_eof
        bne ed_line_ended
        lda ed_byte
        cmp #13
        beq ed_line_ended
        cmp #10
        beq ed_line_ended
        cmp #32
        bcc ed_unprintable
        cmp #127
        bcc ed_text_glyph
ed_unprintable:
        lda #$2e
        bne ed_text_glyph
ed_line_ended:
        inc ed_row_ended
        lda #32
ed_text_glyph:
        jsr ed_cursor_glyph
        jmp ed_column_done
ed_padding:
        lda #32
        jsr ed_chrout
ed_column_done:
        inc ed_col
        lda ed_col
        cmp ed_width
        bne ed_text_column
        lda ed_row_ended
        bne ed_margin_blank
        #ed_move3 ed_fetch,ed_probe
        jsr ed_byte_at
        bcs ed_margin_token
        cmp #13
        beq ed_margin_token
        cmp #10
        beq ed_margin_token
        ; Clip long logical lines; both displays share the horizontal origin.
        #ed_move3 ed_fetch,ed_scan
        jsr ed_forward_end
        jsr ed_after_line
        #ed_move3 ed_scan,ed_fetch
        lda #$3e
        jsr ed_chrout
        jmp ed_row_done
ed_margin_token:
        jsr ed_next_token
        lda #32
        jsr ed_cursor_glyph
        jmp ed_row_done
ed_margin_blank:
        lda #32
        jsr ed_chrout
ed_row_done:
        rts

ed_heading:
        lda ed_name
        bne ed_named
        lda #<ed_untitled
        ldx #>ed_untitled
        bne ed_name_print
ed_named:
        lda #<ed_name
        ldx #>ed_name
ed_name_print:
        ldy #32
        pha
        lda ed_screen
        beq +
        ldy #72
+       pla
        jsr ed_tail_puts
        ldx ed_active
        lda d_states+D_DIRTY,x
        beq +
        lda #$2a
        jsr ed_chrout
+       jsr ed_clear_tail
        lda #<ed_bytes_text
        ldx #>ed_bytes_text
        jsr ed_puts
        #ed_move3 ed_length,ed_print_number
        jsr ed_hex24
        lda #<ed_at_text
        ldx #>ed_at_text
        jsr ed_puts
        #ed_move3 ed_cursor,ed_print_number
        jsr ed_hex24
        lda #<ed_iec_text
        ldx #>ed_iec_text
        ldy ed_format
        cpy #3
        bne +
        lda #<ed_dos_text
        ldx #>ed_dos_text
+
        jsr ed_puts
        lda ed_device
        ldx #$30
ed_tens:
        cmp #10
        bcc +
        sbc #10
        inx
        bne ed_tens
+       pha
        txa
        jsr ed_chrout
        pla
        ora #$30
        jsr ed_chrout
        lda #32
        jsr ed_chrout
        ldx ed_format
        lda ed_format_lo,x
        pha
        lda ed_format_hi,x
        tax
        pla
        jsr ed_puts
        jsr ed_clear_tail
        rts

ed_select_screen:
.if NATIVE_EDITOR_GRAPHICS
        lda eg_collect
        beq +
        lda #40
        sta ed_columns
        lda #38
        sta ed_width
        rts
+
.endif
        lda $d7
        rol
        lda #0
        rol
        cmp ed_screen
        beq +
        jsr $ff5f
+       lda #40
        ldx ed_screen
        beq +
        lda #80
+       sta ed_columns
        sec
        sbc #2
        sta ed_width
        rts
ed_paint_status:
        ldx #6
        ldy #0
        clc
 .if NATIVE_EDITOR_GRAPHICS
        jsr eg_plot
 .else
        jsr $fff0
 .endif
        jsr ed_status_show
        jmp ed_clear_tail
; Header/status strings leave the final column blank. Erase a shortened
; value through column width-2, avoiding an automatic wrap or linked line.
ed_clear_tail:
        sec
 .if NATIVE_EDITOR_GRAPHICS
        jsr eg_plot
 .else
        jsr $fff0
 .endif
        sty ed_blank_left
        lda ed_columns
        sec
        sbc #1
        sec
        sbc ed_blank_left
        sta ed_blank_left
        beq ed_tail_cleared
ed_clear_space:
        lda #32
        jsr ed_chrout
        dec ed_blank_left
        bne ed_clear_space
ed_tail_cleared:
        rts

ed_cursor_glyph:
        sta ed_glyph
.if NATIVE_EDITOR_GRAPHICS
        jsr es_glyph
        bcc ed_inverse_glyph
.endif
        lda ed_caret_drawn
        bne ed_plain_glyph
        #doc_cmp3 ed_cursor,ed_token_start
        bcc ed_plain_glyph
        lda ed_eof
        bne ed_caret_eof
        #doc_cmp3 ed_cursor,ed_fetch
        bcs ed_plain_glyph
        jmp ed_caret_here
ed_caret_eof:
        #doc_cmp3 ed_cursor,ed_length
        bne ed_plain_glyph
ed_caret_here:
        inc ed_caret_drawn
ed_inverse_glyph:
        lda #$12
        jsr ed_chrout
        lda ed_glyph
        jsr ed_chrout
        lda #$92
        jmp ed_chrout
ed_plain_glyph:
        lda ed_glyph
        jmp ed_chrout
ed_puts:
        sta ed_text_read+1
        stx ed_text_read+2
ed_text_read:
        lda $ffff
        beq +
        jsr ed_chrout
        inc ed_text_read+1
        bne ed_text_read
        inc ed_text_read+2
        jmp ed_text_read
+       rts
; CHROUT toggles QTSW on a quote. Text display owns this console state, so
; clear quote mode before emitting a glyph/control; a quoted caret must not
; print the reverse-on/off control codes as document characters.
ed_chrout:
.if NATIVE_EDITOR_GRAPHICS
        pha
        lda eg_collect
        beq +
        pla
        jmp eg_emit
+       pla
.endif
        pha
        lda #0
        sta $f4
        pla
        jmp $ffd2

; C128 function keys normally expand programmable strings. Give each of the
; ten definitions one code while this app owns the foreground, and restore
; all 256 original bytes on every controlled exit. The IRQ cannot observe a
; partially installed length/string table. $d1/$d2 are expansion count/index.
.if NATIVE_EDITOR_GRAPHICS
ed_keys_install = nk_install
ed_keys_restore = nk_close
.else
ed_keys_install:
        php
        sei
        ldx #0
ed_keys_save_loop:
        lda $1000,x
        sta ed_saved_keys,x
        inx
        bne ed_keys_save_loop
        ldx #9
ed_keys_set_loop:
        lda #1
        sta $1000,x
        lda ed_key_codes,x
        sta $100a,x
        dex
        bpl ed_keys_set_loop
        lda #0
        sta $d1
        sta $d2
        plp
        rts
ed_keys_restore:
        php
        sei
        ldx #0
ed_keys_restore_loop:
        lda ed_saved_keys,x
        sta $1000,x
        inx
        bne ed_keys_restore_loop
        lda #0
        sta $d1
        sta $d2
        plp
        rts
.endif
ed_hex24:
        lda #2
        sta ed_hex_index
ed_hex_byte:
        ldx ed_hex_index
        lda ed_print_number,x
        pha
        lsr
        lsr
        lsr
        lsr
        jsr ed_hex_digit
        pla
        and #15
        jsr ed_hex_digit
        dec ed_hex_index
        bpl ed_hex_byte
        rts
ed_hex_digit:
        cmp #10
        bcc +
        adc #6
+       adc #$30
        jmp ed_chrout
ed_status_show:
.if NATIVE_EDITOR_GRAPHICS
        lda eg_collect
        beq +
        lda ed_mode
        beq ed_normal_status
        lda ed_status
        bne ed_normal_status
        rts
+
.endif
        lda ed_status
        cmp #12
        bcs ed_normal_status
        cmp #3
        beq ed_normal_status
        cmp #9
        beq ed_normal_status
        cmp #4
        beq ed_normal_status
        lda ed_mode
        beq ed_normal_status
        cmp #9
        beq ed_replace_choice_show
        cmp #5
        bne ed_field_show
        lda #<ed_discard_text
        ldx #>ed_discard_text
        jmp ed_puts
ed_replace_choice_show:
        lda #<ed_replace_choice_text
        ldx #>ed_replace_choice_text
        jmp ed_puts
ed_field_show:
        tax
        dex
        lda ed_prompt_lo,x
        pha
        lda ed_prompt_hi,x
        tax
        pla
        ldy ed_mode
        cpy #4
        bne +
        ldy ed_format
        cpy #3
        bne +
        lda #<ed_context_text
        ldx #>ed_context_text
+
        jsr ed_puts
        lda ed_mode
        cmp #6
        bcc +
        cmp #8
        bcs +
        lda #<ed_case_text
        ldx #>ed_case_text
        ldy ed_s_pending_case
        beq ed_case_show
        lda #<ed_any_text
        ldx #>ed_any_text
ed_case_show:
        jsr ed_puts
+
        jsr ed_field_pointer
        ldy #16
        lda ed_screen
        beq +
        ldy #56
+       lda ed_mode
        cmp #3
        bcs +
        tya
        sec
        sbc #7
        tay
+       sty N_UIWIDTH
        jsr N_FDRAW
        lda #<ed_field_help
        ldx #>ed_field_help
        ldy ed_mode
        cpy #3
        bcs +
        lda #<ed_file_help
        ldx #>ed_file_help
+       jmp ed_puts
ed_normal_status:
        ldx ed_status
        lda ed_status_lo,x
        pha
        lda ed_status_hi,x
        tax
        pla
        jsr ed_puts
        lda ed_status
        cmp #16
        bcc +
.if NATIVE_EDITOR_GRAPHICS
        cmp #20
        bcs +
.endif
        #ed_move3 ed_s_count,ed_print_number
        jmp ed_hex24
+       rts

; Keep long paths on one row. Display their tail with '<' when clipped;
; the complete 255-byte value is retained for OPEN and Save As.
ed_tail_puts:
        sta ed_tail_scan+1
        sta ed_tail_pointer
        stx ed_tail_scan+2
        stx ed_tail_pointer+1
        sty ed_tail_limit
        ldx #0
ed_tail_scan:
        lda $ffff,x
        beq ed_tail_length
        inx
        bne ed_tail_scan
ed_tail_length:
        cpx ed_tail_limit
        bcc ed_tail_full
        beq ed_tail_full
        txa
        sec
        sbc ed_tail_limit
        clc
        adc #1
        clc
        adc ed_tail_pointer
        sta ed_tail_pointer
        bcc +
        inc ed_tail_pointer+1
+       lda #$3c
        jsr ed_chrout
ed_tail_full:
        lda ed_tail_pointer
        ldx ed_tail_pointer+1
        jmp ed_safe_puts

ed_title: .text "kestrel text editor",13
ed_name_text: .text "name: ",0
ed_untitled: .text "untitled",0
ed_bytes_text: .text 13,"bytes: ",0
ed_at_text: .text " at: ",0
ed_iec_text: .text " iec:",0
ed_dos_text: .text " dos:",0
ed_help: .text 13,"f1 open f3 save as f5 new f7 go to",13
         .text "f2 top f4 end f6 format f8 device",13
         .text "arrows move  del erase  esc return",13,0
ed_discard_text: .text "discard document changes? y/n",0
ed_open_text: .text "open: ",0
ed_save_text: .text "save as: ",0
ed_goto_text: .text "byte (hex): ",0
ed_device_text: .text "iec device: ",0
ed_context_text: .text "dos context: ",0
ed_field_help: .text " enter/esc",0
ed_file_help: .text " enter/esc tab files",0
ed_prompt_lo: .byte <ed_open_text,<ed_save_text,<ed_goto_text,<ed_device_text
              .byte 0,<ed_find_text,<ed_replace_text,<ed_with_text
ed_prompt_hi: .byte >ed_open_text,>ed_save_text,>ed_goto_text,>ed_device_text
              .byte 0,>ed_find_text,>ed_replace_text,>ed_with_text
ed_d64: .text "d64",0
ed_d71: .text "d71",0
ed_d81: .text "d81",0
ed_ultimate: .text "ult",0
ed_format_lo: .byte <ed_d64,<ed_d71,<ed_d81,<ed_ultimate
ed_format_hi: .byte >ed_d64,>ed_d71,>ed_d81,>ed_ultimate
ed_ready_text: .text "home: line start  ctrl-e: line end",0
ed_saved_text: .text "saved and reopened: all bytes verified",0
ed_io_error: .text "disk error; document kept",0
ed_memory_text: .text "not enough memory; document kept",0
ed_range_text: .text "position or device is out of range",0
ed_fault_text: .text "document memory error; cannot save",0
ed_exists_text: .text "file exists; choose another name",0
ed_partial_text: .text "save failed; file may be partial",0
ed_cancelled_text: .text "cancelled; document kept",0
ed_close_text: .text "disk close failed; document kept",0
ed_cancelled_save: .text "cancelled; partial file may remain",0
ed_old_cleanup: .text "opened; old buffer cleanup failed",0
ed_input_text: .text "input unavailable; esc returns",0
ed_status_lo: .byte <ed_ready_text,<ed_saved_text,<ed_io_error,<ed_memory_text,<ed_range_text
              .byte <ed_fault_text,<ed_exists_text,<ed_partial_text,<ed_cancelled_text,<ed_close_text
              .byte <ed_cancelled_save,<ed_old_cleanup,<ed_input_text
              .byte <ed_found_text,<ed_wrapped_text,<ed_not_found_text,<ed_search_busy_text
              .byte <ed_replaced_text,<ed_search_cancel_text,<ed_search_memory_text
.if NATIVE_EDITOR_GRAPHICS
              .byte <ed_clip_copied,<ed_clip_pasted,<ed_clip_select,<ed_clip_empty,<ed_clip_large,<ed_clip_error,<ed_clip_cleared
              .byte <eh_undone,<eh_redone,<eh_cleared,<eh_unavailable,<eh_empty
              .byte <ep_printed_text,<ep_absent_text
.endif
ed_status_hi: .byte >ed_ready_text,>ed_saved_text,>ed_io_error,>ed_memory_text,>ed_range_text
              .byte >ed_fault_text,>ed_exists_text,>ed_partial_text,>ed_cancelled_text,>ed_close_text
              .byte >ed_cancelled_save,>ed_old_cleanup,>ed_input_text
              .byte >ed_found_text,>ed_wrapped_text,>ed_not_found_text,>ed_search_busy_text
              .byte >ed_replaced_text,>ed_search_cancel_text,>ed_search_memory_text
.if NATIVE_EDITOR_GRAPHICS
              .byte >ed_clip_copied,>ed_clip_pasted,>ed_clip_select,>ed_clip_empty,>ed_clip_large,>ed_clip_error,>ed_clip_cleared
              .byte >eh_undone,>eh_redone,>eh_cleared,>eh_unavailable,>eh_empty
              .byte >ep_printed_text,>ep_absent_text
.endif
ed_one: .byte 1,0,0
.if NATIVE_EDITOR_GRAPHICS
ed_key_codes = nk_codes
ed_saved_keys = nk_saved_keys
.else
ed_key_codes: .byte $85,$89,$86,$8a,$87,$8b,$88,$8c,$83,$84
ed_saved_keys: .fill 256,0
.endif
ed_width_minus_one: .byte 37,0,0
ed_active: .byte 0
ed_cursor: .fill 3,0
ed_length: .fill 3,0
ed_view: .fill 3,0
ed_horizontal: .fill 3,0
ed_line_start: .fill 3,0
ed_line_end: .fill 3,0
ed_column: .fill 3,0
ed_goal: .fill 3,0
ed_goal_valid: .byte 0
ed_probe: .fill 3,0
ed_scan: .fill 3,0
ed_fetch: .fill 3,0
ed_token_start: .fill 3,0
ed_target_start: .fill 3,0
ed_target_end: .fill 3,0
ed_skip: .fill 3,0
ed_number: .fill 3,0
ed_print_number: .fill 3,0
ed_cache_base: .fill 3,0
ed_cache_valid: .byte 0
ed_byte: .byte 0
ed_eof: .byte 0
ed_glyph: .byte 0
ed_caret_drawn: .byte 0
ed_hex_index: .byte 0
ed_scan_rows: .byte 0
ed_screen: .byte 0
ed_width: .byte 0
ed_row: .byte 0
ed_col: .byte 0
ed_row_ended: .byte 0
ed_mode: .byte 0
ed_action: .byte 0
ed_status: .byte 0
ed_device: .byte 8
ed_format: .byte 0
ed_newline: .byte 0
ed_name: .fill 256,0
ed_field: .fill 256,0
ed_field_state:
ed_field_len: .byte 0
ed_field_cursor: .byte 0
ed_field_max: .byte 16
        .word ed_field
ed_field_views: .fill 2,0
ed_field_filter: .byte 3
ed_tail_pointer: .word 0
ed_tail_limit: .byte 0
ed_structure: .byte 0
ed_full: .byte 0
ed_last_view: .fill 3,0
ed_last_horizontal: .fill 3,0
ed_cursor_row: .byte 0
ed_last_row: .byte 0
ed_row_limit: .byte 0
ed_columns: .byte 0
ed_blank_left: .byte 0
ed_document_changed: .byte 0
ed_edit_delta: .byte 0
ed_adjust_row: .byte 0
.if NATIVE_EDITOR_GRAPHICS
ed_row_starts=$5f69
.else
ed_row_starts: .fill 51,0
.endif
ed_other_base: .fill 3,0
ed_other_valid: .byte 0
.if NATIVE_EDITOR_GRAPHICS
ed_other_page=$5400
.else
ed_other_page: .fill 512,0
.endif
.include "editor-search-gate.inc"
.include "editor-files.inc"
.include "editor-dialog.inc"
.if NATIVE_EDITOR_GRAPHICS
.include "editor/selection-state.inc"
.include "editor/clipboard-gate.inc"
.include "editor/history.inc"
.include "editor/presentation.inc"
.include "editor/workspace.inc"
.include "input/keys.inc"
.include "editor/vdc.inc"
.include "editor/memory.inc"
BP_MODE=0
BP_HISTORY=1
BP_SHARED_MEMORY=1
BP_STATE_STORAGE=$5f40
BP_POINTER_STATE=eg_pointer_visible
BP_POINTER_X=eg_pointer_x
BP_POINTER_Y=eg_pointer_y
bp_select_surface=eg_select_surface
.include "graphics/vdc-client.inc"
.endif
FD_EMBEDDED = 1
FD_DIRECT_PAGES = 6
FD_GUI = NATIVE_EDITOR_GRAPHICS
.if NATIVE_EDITOR_GRAPHICS
FD_GUI_SURFACE = eg_handle
FD_BUFFER_BASE = $5800
FD_RETAINED_STORAGE = $5b00
FD_VDC=1
FD_VDC_PHASE=vd_phase
FD_VDC_FAULT=vd_fault
FD_VDC_ROWS=vm_rows
FD_VDC_PENDING=vm_pending
FD_VDC_FULL=eg_vdc_full
FD_VDC_SYNC=eg_vdc_sync
FD_VDC_CLOSE=eg_vdc_close
FD_VDC_GUARD=eg_vdc_guard
.endif
FD_NAME_BUFFER = ed_field
FD_SCRATCH0 = d_input
FD_SCRATCH1 = d_output
FD_SCRATCH2 = ed_other_page
FD_SCRATCH3 = ed_verify_data
FD_SAFE_CHARACTER = ed_safe_character
editor_module:
        .text "nmod"
        .byte 1,1,ED_ABI,0
        .word editor_end-editor_module
        .word 0                ; build binds the module to the sealed core CRC
        .word fd_run-editor_module
        .word 0                ; build seals the independent module CRC
.include "file-dialog.inc"
editor_end:
        .cerror * > N_APPBASE+ED_PAGES*256, "editor must leave RAM for large documents and dialogs: ", editor_end-editor_module, " available ", N_APPBASE+ED_PAGES*256-editor_module

; A second on-disk module uses the same reserved window. Both are assembled
; here so forward references bind to one exact core. The builder splits these
; two payloads and seals each against the core CRC; only one is loaded at once.
        .logical editor_module
editor_search_module:
        .text "nmod"
        .byte 1,1,ED_ABI,0
        .word editor_search_end-editor_search_module
        .word 0
.if NATIVE_EDITOR_GRAPHICS
        .word eg_entry-editor_search_module
.else
        .word ed_search_entry-editor_search_module
.endif
        .word 0
.include "editor-search.inc"
.include "document-replace.inc"
.if NATIVE_EDITOR_GRAPHICS
.include "editor/gui.inc"
.endif
editor_search_end:
        .cerror * > N_APPBASE+ED_PAGES*256, "search exceeds the editor module window: ", editor_search_end, " core ", editor_module
        .here

.if NATIVE_EDITOR_GRAPHICS
        .cerror N_APPBASE+ED_PAGES*256 > $c000, "editor overlaps surface: ", editor_module-editor_image, " / ", editor_search_end-editor_image, " / ", ED_PAGES
.endif

.if NATIVE_EDITOR_GRAPHICS
        .logical editor_module
editor_clipboard_module:
        .text "nmod"
        .byte 1,1,ED_ABI,0
        .word editor_clipboard_end-editor_clipboard_module
        .word 0
        .word ec_entry-editor_clipboard_module
        .word 0
.include "editor/clipboard.inc"
.include "editor/print.inc"
editor_clipboard_end:
        .cerror * > $c000, "clipboard exceeds the Editor module window"
        .here
.endif
