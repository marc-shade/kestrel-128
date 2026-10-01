; Native Ultimate navigation. Eight complete names per page, with a second
; page buffer so failed/cancelled navigation preserves the previous listing.
; Forward pages consume the owned cursor; back/reopen scans skip exact entries.
.if !FD_EMBEDDED
bu_preferences:
        lda N_BROWSERDEV
        beq bu_default_context
        cmp #3
        bcc bu_preferences_path
bu_default_context:
        lda #1
        sta N_BROWSERDEV
bu_preferences_path:
        jsr bu_path_validate
        jmp b_format_valid
.endif
bu_path_validate:
        lda N_BROWSERLEN
        beq bu_default_path
        lda N_BROWSERPATH
        cmp #$2f
        bne bu_default_path
        ldx #0
bu_path_check:
        lda N_BROWSERPATH,x
        beq bu_default_path
        inx
        cpx N_BROWSERLEN
        bne bu_path_check
        rts
bu_default_path:
        lda #$2f
        sta N_BROWSERPATH
        lda #1
        sta N_BROWSERLEN
        lda #0
        sta N_BROWSERNAME_LEN
        ldx #3
bu_default_position:
        sta N_BROWSERPOS,x
        dex
        bpl bu_default_position
        rts

bu_key:
        cmp #27
        beq bu_workspace
        cmp #$11
        beq bu_down
        cmp #$91
        beq bu_up
        cmp #9
        beq bu_context
.if B_GUI
        cmp #$85
        beq bu_context
.endif
        cmp #13
        beq bu_enter
        and #$df
.if B_COPY
        cmp #$43
        beq fc_begin
.endif
        cmp #$4e
        beq bu_next
        cmp #$42
        beq bu_previous
        cmp #$50
        beq bu_parent
        cmp #$52
        beq bu_rescan
        cmp #$47
        beq bu_prompt_path
        cmp #$46
        beq b_change_format
.if !FD_EMBEDDED
        cmp #$4c
        beq b_usb_begin
        cmp #$49
        beq bu_inspect
.else
        cmp #$53
        beq fd_choose_folder
.endif
        jmp b_loop
bu_workspace:
.if FD_EMBEDDED
        jmp fd_cancel
.else
        jsr bu_close_cursor
        bcs b_redraw
.if FD_RETURN_TO_DESKTOP
        jmp b_workspace
.else
        jmp N_WORKSPACE
.endif
.endif
bu_down:
        lda bu_row
        clc
        adc #1
        cmp bu_count
        bcs bu_next
        sta bu_row
        jmp bu_selection
bu_up:
        lda bu_row
        beq bu_previous
        dec bu_row
bu_selection:
        jsr bu_save_selection
        jmp b_redraw
bu_save_selection:
        clc
        lda bu_row
        adc bu_base
        sta N_BROWSERPOS
        lda bu_base+1
        adc #0
        sta N_BROWSERPOS+1
        lda bu_base+2
        adc #0
        sta N_BROWSERPOS+2
        lda bu_base+3
        adc #0
        sta N_BROWSERPOS+3
        lda bu_count
        beq bu_save_name_length
        lda bu_row
        jsr bu_read_record
        ldx #0
bu_save_name:
        lda N_BUFFER+1,x
        sta N_BROWSERNAME,x
        inx
        cpx N_BUFFER+510
        bne bu_save_name
        txa
bu_save_name_length:
        sta N_BROWSERNAME_LEN
        rts
bu_candidate_current:
        lda N_BROWSERLEN
        sta bu_length
        lda N_BROWSERDEV
        sta bu_device
        ldx #0
bu_candidate_copy:
        lda N_BROWSERPATH,x
        sta bu_path,x
        inx
        cpx bu_length
        bne bu_candidate_copy
        lda #0
        sta bu_resume
        sta bu_target_row
        sta bu_search
        sta bu_found
        rts
bu_refresh_saved:
        jsr bu_candidate_current
        lda N_BROWSERNAME_LEN
        beq bu_initial_ordinal
        jsr bu_zero_target
        lda #1
        sta bu_search
        jmp bu_scan
bu_initial_ordinal:
        ldx #3
bu_initial_position:
        lda N_BROWSERPOS,x
        sta bu_target,x
        dex
        bpl bu_initial_position
        lda bu_target
        and #7
        sta bu_target_row
        lda bu_target
        and #$f8
        sta bu_target
        jmp bu_scan
bu_zero_target:
        lda #0
        ldx #3
bu_target_byte:
        sta bu_target,x
        dex
        bpl bu_target_byte
        sta bu_target_row
        sta bu_search
        sta bu_found
        rts
bu_rescan:
        jsr bu_candidate_current
        jsr bu_zero_target
        jmp bu_scan_key
bu_context:
        jsr bu_candidate_current
        lda bu_device
        eor #3
        sta bu_device
        jsr bu_zero_target
        jmp bu_scan_key
bu_next:
        lda bu_more
        beq b_loop
        jsr bu_candidate_current
        clc
        lda bu_base
        adc #8
        sta bu_target
        lda bu_base+1
        adc #0
        sta bu_target+1
        lda bu_base+2
        adc #0
        sta bu_target+2
        lda bu_base+3
        adc #0
        sta bu_target+3
        bcs bu_index_error
        lda bu_cursor
        beq bu_scan_key
        lda #1
        sta bu_resume
        bne bu_scan_key
bu_previous:
        lda bu_base
        ora bu_base+1
        ora bu_base+2
        ora bu_base+3
        beq b_loop
        jsr bu_candidate_current
        sec
        lda bu_base
        sbc #8
        sta bu_target
        lda bu_base+1
        sbc #0
        sta bu_target+1
        lda bu_base+2
        sbc #0
        sta bu_target+2
        lda bu_base+3
        sbc #0
        sta bu_target+3
        jmp bu_scan_key
bu_index_error:
        lda #N_RANGE
        sta b_error
        jmp b_redraw
bu_parent:
        jsr bu_candidate_current
        ldx bu_length
        cpx #1
        beq b_loop
        dex
        lda bu_path,x
        cmp #$2f
        bne bu_parent_find
        dex
bu_parent_find:
        lda bu_path,x
        cmp #$2f
        beq bu_parent_found
        dex
        bne bu_parent_find
bu_parent_found:
        inx
        stx bu_length
        jsr bu_zero_target
        jmp bu_scan_key
bu_prompt_path:
        lda N_BROWSERLEN
        sta b_usb_length
        lda N_BROWSERDEV
        sta b_usb_device
        ldx #0
bu_prompt_copy:
        lda N_BROWSERPATH,x
        sta b_usb_path,x
        inx
        cpx b_usb_length
        bne bu_prompt_copy
        lda #3
        sta b_prompt
        lda #0
        sta b_usb_error
        sta N_UIKEY
        jsr b_usb_edit
        bcs b_usb_input_error
        jmp b_usb_refresh
bu_prompt_directory:
        lda b_usb_length
        sta bu_length
        lda b_usb_device
        sta bu_device
        ldx #0
bu_prompt_keep:
        lda b_usb_path,x
        sta bu_path,x
        inx
        cpx bu_length
        bne bu_prompt_keep
        lda #0
        sta b_prompt
        sta bu_resume
        jsr bu_zero_target
bu_scan_key:
        lda #0
        sta b_launch_error
        jsr bu_scan
        jmp b_redraw

bu_select_cursor:
        lda b_owner
        sta N_FOWNER
        ldx #3
bu_cursor_handle:
        lda bu_cursor,x
        sta N_FHANDLE,x
        dex
        bpl bu_cursor_handle
        rts
bu_close_cursor:
        lda bu_cursor
        beq bu_closed
        jsr bu_select_cursor
        jsr N_FCLOSE
        bcs bu_close_error
        lda #0
        sta bu_cursor
bu_closed:
        clc
        rts
bu_close_error:
        sta b_error
        sec
        rts
bu_poll:
.if B_GUI
        lda fg_searching
        beq +
        jmp fn_poll
+
.endif
        lda bu_pending_key
        bne bu_poll_ready
        jsr N_KEYIN
.if FD_GUI
        jsr pg_input
.endif
        cmp #27
        beq bu_poll_cancel
        sta bu_pending_key      ; preserve other input for the normal event loop
bu_poll_ready:
        clc
        rts
bu_poll_cancel:
        sec
        rts

bu_scan:
        lda #1
        sta b_busy
        jsr b_draw
        lda bu_side
        eor #16
        sta bu_new_side
        lda #0
        sta bu_new_count
        sta b_error
        lda bu_resume
        bne bu_read_entry
bu_scan_restart:
        jsr bu_close_cursor
        bcs bu_scan_end
        lda b_owner
        sta N_FOWNER
        lda #0
        sta N_FTYPE
        ldx #3
bu_clear_cursor:
        sta N_FHANDLE,x
        dex
        bpl bu_clear_cursor
        lda bu_device
        sta N_FDEVICE
        lda #3
        sta N_FFORMAT
        lda #2
        sta N_FMODE
        lda bu_length
        sta N_FNAMELEN
        ldx #0
bu_open_path:
        lda bu_path,x
        sta N_UPATH,x
        inx
        cpx bu_length
        bne bu_open_path
        jsr N_FOPEN
        php
        pha
        ldx #3
bu_keep_cursor:
        lda N_FHANDLE,x
        sta bu_cursor,x
        lda bu_target,x
        sta bu_skip,x
        dex
        bpl bu_keep_cursor
        pla
        plp
        bcs bu_scan_failed
        lda N_FNAMELEN
        sta bu_length
        ldx #0
bu_canonical_path:
        lda N_UPATH,x
        sta bu_path,x
        inx
        cpx bu_length
        bne bu_canonical_path
bu_skip_entry:
        lda bu_skip
        ora bu_skip+1
        ora bu_skip+2
        ora bu_skip+3
        beq bu_read_entry
        jsr bu_read_cursor
        bcs bu_scan_failed
        lda N_FEOF
        bne bu_selection_expired
        sec
        lda bu_skip
        sbc #1
        sta bu_skip
        lda bu_skip+1
        sbc #0
        sta bu_skip+1
        lda bu_skip+2
        sbc #0
        sta bu_skip+2
        lda bu_skip+3
        sbc #0
        sta bu_skip+3
        jsr bu_poll
        bcs bu_scan_cancelled
        jmp bu_skip_entry
bu_selection_expired:
        jsr bu_zero_target      ; media changed or the saved selection was stale
        jmp bu_scan_restart
bu_read_cursor:
        jsr bu_select_cursor
        lda #0
        sta N_FCOUNT
        lda #2
        sta N_FCOUNT+1
        jmp N_FREAD
bu_read_entry:
        jsr bu_poll
        bcs bu_scan_cancelled
        jsr bu_read_cursor
        bcs bu_scan_failed
        lda N_FEOF
        sta bu_end
        lda N_FACTUAL
        ora N_FACTUAL+1
        beq bu_scan_complete
        lda N_FACTUAL
        sec
        sbc #1
        sta N_BUFFER+510        ; raw name length, 1..255
        jsr bu_match_saved
        lda bu_new_count
        asl
        clc
        adc bu_new_side
        jsr bu_cache_select
.if FD_EMBEDDED
        lda bu_new_side
        lsr
        clc
        adc bu_new_count
        tax
        lda N_BUFFER+510
        sta fd_lengths,x
        jsr fd_write_cache
.else
        jsr N_WRITE
.endif
 .if B_GUI
        bcs bu_scan_failed       ; preserve the published page on cache errors
 .else
        bcs b_exit_error
 .endif
        inc bu_new_count
        lda bu_end
        bne bu_scan_complete
        lda bu_new_count
        cmp #8
        bne bu_read_entry
        lda bu_search
        beq bu_commit
        lda bu_found
        bne bu_commit
        lda #0
        sta bu_new_count
        clc
        lda bu_target
        adc #8
        sta bu_target
        lda bu_target+1
        adc #0
        sta bu_target+1
        lda bu_target+2
        adc #0
        sta bu_target+2
        lda bu_target+3
        adc #0
        sta bu_target+3
        bcc bu_read_entry
        lda #N_RANGE
        bne bu_scan_failed
bu_scan_complete:
        jsr bu_close_cursor
        bcs bu_scan_end
        lda bu_search
        beq bu_commit
        lda bu_found
        bne bu_commit
.if B_GUI
        lda bu_search
        cmp #2
        bne +
        jsr fn_wrap
        bcs bu_scan_end
        jmp bu_scan_restart
+
.endif
        jsr bu_zero_target      ; selected name disappeared: show the first page
        sta bu_new_count
        jmp bu_scan_restart
bu_commit:
        lda bu_length
        sta N_BROWSERLEN
        lda bu_device
        sta N_BROWSERDEV
        sta b_usb_device
        lda bu_new_side
        sta bu_side
        lda bu_new_count
        sta bu_count
        lda bu_end
        eor #1
        sta bu_more
        lda bu_target_row
        cmp bu_count
        bcc +
        lda #0
+       sta bu_row
        ldx #3
bu_commit_position:
        lda bu_target,x
        sta bu_base,x
        dex
        bpl bu_commit_position
        ldx #0
bu_commit_path:
        lda bu_path,x
        sta N_BROWSERPATH,x
        inx
        cpx bu_length
        bne bu_commit_path
        jsr bu_save_selection
        jmp bu_scan_end
bu_scan_cancelled:
        lda #$24
bu_scan_failed:
        sta bu_failure
        jsr bu_close_cursor
        lda bu_failure
        sta b_error
bu_scan_end:
        lda #0
        sta b_busy
        lda b_error
        cmp #1
        rts

bu_match_saved:
.if B_GUI
        lda bu_search
        cmp #2
        bne +
        jmp fn_ultimate_match
+
.endif
        lda bu_search
        beq bu_match_done
        lda N_BUFFER+510
        cmp N_BROWSERNAME_LEN
        bne bu_match_done
        ldx #0
bu_match_byte:
        lda N_BUFFER+1,x
        cmp N_BROWSERNAME,x
        bne bu_match_done
        inx
        cpx N_BROWSERNAME_LEN
        bne bu_match_byte
        lda #1
        sta bu_found
        lda bu_new_count
        sta bu_target_row
bu_match_done:
        rts

; A is the banked cache page: 0..15 or 16..31. Each record uses two pages.
bu_cache_select:
        sta N_OFFSET+1
        lda #0
        sta N_OFFSET
        sta N_COUNT
        lda #2
        sta N_COUNT+1
        lda b_owner
        sta N_OWNER
.if FD_EMBEDDED
        lsr N_OFFSET+1
        lda #1
        sta N_COUNT+1
        jmp fd_cache_select
.else
        ldx #3
bu_cache_handle:
        lda b_cache,x
        sta N_HANDLE,x
        dex
        bpl bu_cache_handle
        rts
.endif
bu_read_record:
.if FD_EMBEDDED
        sta fd_record_at
        lda bu_side
        lsr
        clc
        adc fd_record_at
        sta fd_record_at
        lda fd_record_at
        and #7
.endif
        asl
        clc
        adc bu_side
        jsr bu_cache_select
.if FD_EMBEDDED
        jsr fd_read_cache
        bcs b_exit_error
        ldx fd_record_at
        lda fd_lengths,x
        sta N_BUFFER+510
.else
        jsr N_READ
        bcs b_exit_error
.endif
        rts
bu_fullname:
        lda bu_row
        jsr bu_read_record
        lda N_BUFFER
        sta bu_attribute
        lda N_BUFFER+510
        sta bu_name_length
        lda N_BROWSERLEN
        sta bu_full_length
        ldx #0
bu_full_parent:
        lda N_BROWSERPATH,x
        sta N_UPATH,x
        inx
        cpx N_BROWSERLEN
        bne bu_full_parent
        lda N_UPATH-1,x
        cmp #$2f
        beq bu_join_name
        cpx #255
        beq bu_path_too_long
        lda #$2f
        sta N_UPATH,x
        inc bu_full_length
bu_join_name:
        lda bu_full_length
        clc
        adc bu_name_length
        bcs bu_path_too_long
        sta bu_full_length
        ldx N_BROWSERLEN
        lda N_UPATH-1,x
        cmp #$2f
        beq +
        inx
+       ldy #0
bu_full_leaf:
        lda N_BUFFER+1,y
        sta N_UPATH,x
        inx
        iny
        cpy bu_name_length
        bne bu_full_leaf
        ldx #0
bu_display_leaf:
        lda #$a0
        cpx bu_name_length
        bcs +
        lda N_BUFFER+1,x
+       sta b_record+2,x
        inx
        cpx #16
        bne bu_display_leaf
        clc
        rts
bu_path_too_long:
        lda #$23
        sec
        rts
bu_inspect:
        lda #1
        bne bu_open_selected
bu_enter:
        lda #0
bu_open_selected:
        sta bu_inspection
        lda bu_count
        beq b_loop
        jsr bu_fullname
        bcs bu_open_error
        lda bu_attribute
        and #$10
        bne bu_child
        lda bu_attribute
        and #8
        beq bu_file
        lda #$21
        bne bu_open_error
bu_child:
        lda bu_full_length
        sta bu_length
        lda N_BROWSERDEV
        sta bu_device
        ldx #0
bu_child_path:
        lda N_UPATH,x
        sta bu_path,x
        inx
        cpx bu_length
        bne bu_child_path
        lda #0
        sta bu_resume
        jsr bu_zero_target
        jmp bu_scan_key
bu_file:
.if FD_EMBEDDED
        jmp fd_choose_ultimate
.else
        jsr bu_close_cursor
        bcs b_redraw
        lda b_owner
        sta N_FOWNER
        lda N_BROWSERDEV
        sta N_FDEVICE
        lda #3
        sta N_FFORMAT
        lda bu_full_length
        sta N_FNAMELEN
        lda #0
        sta N_FMODE
        sta N_FTYPE
        ldx #3
bu_file_arguments:
        sta N_FHANDLE,x
        sta b_next_offset,x
        dex
        bpl bu_file_arguments
        jsr N_FOPEN
        php
        pha
        lda N_FHANDLE
        sta b_open
        pla
        plp
        bcs bu_file_failed
        lda #0
        sta b_error
        sta b_launch_error
        jsr b_view_read
        lda bu_inspection
        ora b_error
        bne bu_show_file
        lda b_view_count
        cmp #34
        bcc bu_show_file
        ldx #5
bu_app_header:
        lda b_view_data,x
        cmp b_app_magic,x
        bne bu_show_file
        dex
        bpl bu_app_header
        jsr b_close_file
.if B_GUI
        jsr fg_exit
        bcs b_loop
.endif
        lda bu_full_length
        sta N_NAMELEN
        lda N_BROWSERDEV
        sta N_DEVICE
        lda #3
        sta N_APPFORMAT
        jmp N_REPLACE
bu_show_file:
.if B_GUI
        lda #1
        sta b_preview
        lda bu_inspection
        bne +
        jmp fl_associate
+
.endif
        lda #1
        sta b_preview
        jmp b_redraw
bu_file_failed:
        pha
        jsr b_close_file
        pla
.endif
bu_open_error:
        sta b_error
        jmp b_redraw

bu_draw:
        lda #<bu_title
        ldx #>bu_title
        jsr b_puts
        lda N_BROWSERDEV
        ldx #0
        jsr b_number
        lda #<bu_path_title
        ldx #>bu_path_title
        jsr b_puts
        lda #33
.if FD_GUI
        ldx pg_collect
        beq +
        lda #32
+
.endif
        ldx b_screen
        beq +
        lda #73
+       sta bu_width
        lda N_BROWSERLEN
        sec
        sbc bu_width
        bcc bu_path_start
        beq bu_path_start
        clc
        adc #1
        sta bu_at
        lda #$3c
        jsr b_usb_chrout
        jmp bu_path_show
bu_path_start:
        lda #0
        sta bu_at
bu_path_show:
        ldx bu_at
        cpx N_BROWSERLEN
        beq bu_page_title
        lda N_BROWSERPATH,x
        jsr b_safe_character
        jsr b_usb_chrout
        inc bu_at
        bne bu_path_show
bu_page_title:
        lda #<bu_page_text
        ldx #>bu_page_text
        jsr b_puts
        jsr bu_page_number
        lda #<bu_columns
        ldx #>bu_columns
        jsr b_puts
        lda #0
        sta bu_draw_row
bu_draw_line:
        lda b_busy
        bne bu_draw_blank
        lda bu_draw_row
        cmp bu_count
        bcs bu_draw_blank
        jsr bu_read_record
        lda #32
        ldx bu_draw_row
        cpx bu_row
        bne +
        lda #$3e
+       jsr b_usb_chrout
        lda #$46
        ldx N_BUFFER
        txa
        and #$10
        beq bu_draw_file
        lda #$44
        bne bu_draw_kind
bu_draw_file:
        lda #$46
bu_draw_kind:
        jsr b_usb_chrout
        lda #32
        jsr b_usb_chrout
        lda N_BUFFER+510
        sta bu_name_length
        sec
        sbc bu_width
        bcc bu_name_start
        beq bu_name_start
        clc
        adc #1
        sta bu_at
        lda #$3c
        jsr b_usb_chrout
        jmp bu_name_show
bu_name_start:
        lda #0
        sta bu_at
bu_name_show:
        ldx bu_at
        cpx bu_name_length
        beq bu_draw_blank
        lda N_BUFFER+1,x
        jsr b_safe_character
        jsr b_usb_chrout
        inc bu_at
        bne bu_name_show
bu_draw_blank:
        lda #13
        jsr b_usb_chrout
        inc bu_draw_row
        lda bu_draw_row
        cmp #8
        bne bu_draw_line
        lda #<bu_help
        ldx #>bu_help
        jsr b_puts
        lda b_busy
        beq bu_draw_status
        lda #<bu_scanning
        ldx #>bu_scanning
        jmp b_puts
bu_draw_status:
        lda b_error
        cmp #$23
        beq bu_draw_long
        cmp #$24
        beq bu_draw_cancel
        ora b_launch_error
        bne b_show_status
        lda #<bu_last_page
        ldx #>bu_last_page
        ldy bu_more
        beq +
        lda #<bu_more_pages
        ldx #>bu_more_pages
+       jmp b_puts
bu_draw_long:
        lda #<bu_long_path
        ldx #>bu_long_path
        jmp b_puts
bu_draw_cancel:
        lda #<bu_cancelled
        ldx #>bu_cancelled
        jmp b_puts

; Print (base / 8) + 1 in decimal, retaining the complete 32-bit page index.
bu_page_number:
        ldx #3
bu_page_copy:
        lda bu_base,x
        sta bu_number,x
        dex
        bpl bu_page_copy
        ldy #3
bu_page_shift:
        lsr bu_number+3
        ror bu_number+2
        ror bu_number+1
        ror bu_number
        dey
        bne bu_page_shift
        ldx #0
bu_page_increment:
        inc bu_number,x
        bne bu_number_begin
        inx
        cpx #4
        bne bu_page_increment
bu_number_begin:
        lda #0
        sta bu_power
        sta bu_started
bu_number_digit:
        lda #0
        sta bu_digit
bu_number_compare:
        ldy bu_power
        lda bu_number
        cmp bu_powers,y
        lda bu_number+1
        sbc bu_powers+1,y
        lda bu_number+2
        sbc bu_powers+2,y
        lda bu_number+3
        sbc bu_powers+3,y
        bcc bu_number_emit
        sec
        lda bu_number
        sbc bu_powers,y
        sta bu_number
        lda bu_number+1
        sbc bu_powers+1,y
        sta bu_number+1
        lda bu_number+2
        sbc bu_powers+2,y
        sta bu_number+2
        lda bu_number+3
        sbc bu_powers+3,y
        sta bu_number+3
        inc bu_digit
        bne bu_number_compare
bu_number_emit:
        lda bu_digit
        ora bu_started
        bne bu_number_print
        lda bu_power
        cmp #36
        bne bu_number_next
bu_number_print:
        lda #1
        sta bu_started
        lda bu_digit
        clc
        adc #$30
        jsr b_usb_chrout
bu_number_next:
        clc
        lda bu_power
        adc #4
        sta bu_power
        cmp #40
        bne bu_number_digit
        rts

bu_title:
.if FD_EMBEDDED
        .text "kestrel choose a file",13,13,"dos: ",0
.else
        .text "kestrel files and apps",13,13,"dos: ",0
.endif
bu_path_title: .text "   format: ult",13,"path: ",0
bu_page_text: .text 13,"page: ",0
bu_columns: .text 13,"  kind name",13,0
bu_help:
.if FD_EMBEDDED
        .text 13,"up/down select  n/b page",13
.if FD_GUI
        .text "tab controls  enter activate",13
        .text "g path  p parent  f1 dos  f format",13
.else
        .text "enter choose  p parent  r refresh",13
        .text "g path  tab dos  f format",13
.endif
        .text "s use folder for save as  esc cancel",13,0
.else
        .text 13,"up/down select  n/b page",13
        .text "enter open  i inspect  p parent",13
.if B_GUI
        .text "r refresh  g path  f1 dos",13
.else
        .text "r refresh  g path  tab dos",13
.endif
.if B_COPY
        .text "c copy  f format  esc desktop",13,0
.else
        .text "f format  esc workspace  l usb app",13,0
.endif
.endif
bu_scanning: .text "reading directory... esc cancels",0
bu_more_pages: .text "more entries - n for next page",0
bu_last_page: .text "end of directory",0
bu_long_path: .text "path too long; cannot open this name",0
bu_cancelled: .text "scan cancelled; previous page retained",0
bu_path_help:
.if B_GUI || FD_GUI
        .text "enter browse f1 dos ctrl-u clr esc",0
.else
        .text "enter browse tab dos ctrl-u clr esc",0
.endif
bu_powers: .dword 1000000000,100000000,10000000,1000000,100000,10000,1000,100,10,1
bu_cursor: .fill 4,0
bu_base: .fill 4,0
bu_target: .fill 4,0
bu_skip: .fill 4,0
bu_number: .fill 4,0
bu_count: .byte 0
bu_row: .byte 0
bu_side: .byte 0
bu_more: .byte 0
bu_length: .byte 0
bu_device: .byte 0
bu_iec_device: .byte 8
bu_target_row: .byte 0
bu_resume: .byte 0
bu_search: .byte 0
bu_found: .byte 0
bu_new_side: .byte 0
bu_new_count: .byte 0
bu_end: .byte 0
bu_failure: .byte 0
bu_pending_key: .byte 0
bu_attribute: .byte 0
bu_name_length: .byte 0
bu_full_length: .byte 0
bu_inspection: .byte 0
bu_width: .byte 0
bu_at: .byte 0
bu_draw_row: .byte 0
bu_power: .byte 0
bu_started: .byte 0
bu_digit: .byte 0
.if FD_BUFFER_BASE
bu_path=FD_BUFFER_BASE+256
.else
bu_path: .fill 256,0
.endif
