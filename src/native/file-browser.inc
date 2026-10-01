; Shared file navigation used by the desktop browser and modal file dialogs.
; FD_EMBEDDED selects return-to-caller behavior and excludes app launch/viewer.
.weak
B_COPY = 0
B_GUI = 0
FD_GUI = 0
FD_VDC = 0
FD_VDC_GUARD = 0
FD_BUFFER_BASE = 0
.endweak
B_RECORD_BYTES=32-12*FD_GUI
.if !FD_EMBEDDED
b_entry:
        cld
.if B_GUI
        lda N_DOCRESUME
        sta fl_resume
        lda #0
        sta N_DOCRESUME
.endif
        lda N_CURRENT
        sta b_owner
        sta N_OWNER
        lda #37                 ; 296 normalized entries, the root D81 maximum
        sta N_PAGES
        lda #1
        sta N_BANK
        jsr N_ALLOC
        bcs b_exit_error
        ldx #3
b_keep_cache:
        lda N_HANDLE,x
        sta b_cache,x
        dex
        bpl b_keep_cache
        lda N_BOOTDEVICE
        sta bu_iec_device
        lda N_BROWSERFMT
        cmp #3
        beq bu_preferences
        lda N_BROWSERDEV
        cmp #8
        bcc b_default_device
        cmp #31
        bcc b_device_valid
b_default_device:
        lda N_DEVICE
        ldx N_APPFORMAT
        cpx #3
        bne +
        lda N_BOOTDEVICE
+
        sta N_BROWSERDEV
b_device_valid:
        lda N_BROWSERFMT
        cmp #3
        bcc b_format_valid
        lda #0
        sta N_BROWSERFMT
.endif
b_format_valid:
.if B_GUI
        jsr fg_init
        bcs b_exit_error
.endif
.if FD_GUI
        jsr pg_init
.endif
        lda N_BROWSERERROR
        sta b_launch_error
        lda #0
        sta N_BROWSERERROR
        sta b_selected
        sta b_selected+1
        jsr b_refresh
.if B_GUI
        jsr fl_restore_selection
.endif
b_redraw:
.if FD_GUI
        lda b_prompt
        cmp #2
        bcc +
        jsr b_usb_draw
        jmp b_loop
+
.endif
        jsr b_draw
b_loop:
        lda bu_pending_key
        beq b_publish_ready
        ldx #0
        stx bu_pending_key
        jmp b_have_key
b_publish_ready:
        lda #1
        sta N_READY
b_get_key:
        jsr N_KEYIN
.if B_GUI
        jsr fg_input
.endif
.if FD_GUI
        jsr pg_input
.if FD_VDC_GUARD
        ; A focus/pointer redraw can fail while pg_input is handling a key.
        ; Recover before its returned action can open a directory or select.
        jsr FD_VDC_GUARD
.endif
.endif
        beq b_loop
b_have_key:
        ldx #0
        stx N_READY
.if B_GUI || FD_GUI
        cmp #14
        beq b_redraw
.endif
        ldx b_prompt
        bne b_prompt_key
.if !FD_EMBEDDED
        ldx b_preview
        bne b_preview_key
.endif
.if B_GUI
        cmp #5                  ; Ctrl-E: selected document in Editor
        beq fl_edit
        cmp #16                 ; Ctrl-P: selected UPNT document in Paint
        beq fl_paint
.endif
        ldx N_BROWSERFMT
        cpx #3
        beq bu_key
        cmp #27
        beq b_workspace
        cmp #$11                ; native cursor down
        beq b_down
        cmp #$91
        beq b_up
        cmp #13
        beq b_enter
        and #$df
.if B_COPY
        cmp #$43
        beq fc_begin
.endif
        cmp #$52
        beq b_rescan
        cmp #$46
        beq b_change_format
        cmp #$44
        beq b_device_prompt
        cmp #$4e
        beq b_next_page
        cmp #$42
        beq b_previous_page
.if !FD_EMBEDDED
        cmp #$41
        beq b_next_app
        cmp #$49
        beq b_inspect
        cmp #$4c
        beq b_usb_begin
.else
        cmp #$53
        beq fd_choose_folder
.endif
        jmp b_loop
b_workspace:
.if B_GUI
        jsr fg_exit
        bcs b_loop
.endif
.if FD_EMBEDDED
        jmp fd_cancel
.else
.if FD_RETURN_TO_DESKTOP
        lda #0
        jmp N_EXIT
.else
        jmp N_WORKSPACE
.endif
.endif
b_exit_error:
.if B_GUI
        pha
        jsr fg_exit
        pla
        bcs b_loop
.endif
.if FD_EMBEDDED
        jmp fd_failure
.else
        jmp N_EXIT
.endif
b_rescan:
.if B_GUI
        jsr fg_retry
.endif
.if FD_GUI
        jsr pg_retry
.endif
        lda #0
        sta b_launch_error
        jsr b_refresh
        jmp b_redraw
b_change_format:
        lda N_BROWSERFMT
        cmp #3
        bne b_next_format
        jsr bu_close_cursor
        bcs b_redraw
        lda bu_iec_device
        sta N_BROWSERDEV
b_next_format:
        inc N_BROWSERFMT
        lda N_BROWSERFMT
        cmp #4
        bcc b_format_updated
        lda #0
        sta N_BROWSERFMT
b_format_updated:
        cmp #3
        bne b_change_ready
        lda N_BROWSERDEV
        sta bu_iec_device
        lda b_usb_device
        sta N_BROWSERDEV
        lda #0
        sta bu_count
        sta bu_side
        jsr bu_path_validate
b_change_ready:
        lda #0
        sta b_selected
        sta b_selected+1
        jmp b_rescan
b_device_prompt:
        lda #1
        sta b_prompt
        lda #0
        sta b_device_length
        sta N_UIKEY
        jsr b_device_edit
        jmp b_redraw
b_prompt_key:
        ldx b_prompt
        cpx #2
        bcs b_usb_key
        cmp #27
        beq b_prompt_cancel
        cmp #13
        beq b_prompt_enter
        sta N_UIKEY
        jsr b_device_edit
        bcs b_loop
        lda N_UIFLAGS
        beq b_loop
        jmp b_redraw
b_device_edit:
        jsr b_device_pointer
        jmp N_FEDIT
b_device_pointer:
        lda #<b_device_state
        sta N_UIPTR
        lda #>b_device_state
        sta N_UIPTR+1
        rts
b_prompt_enter:
        ldx b_device_length
        beq b_loop
        lda b_device_text
        and #15
        cpx #1
        beq b_device_number
        asl
        sta b_digit
        asl
        asl
        clc
        adc b_digit
        sta b_digit
        lda b_device_text+1
        and #15
        clc
        adc b_digit
b_device_number:
        cmp #8
        bcc b_loop
        cmp #31
        bcs b_loop
        sta N_BROWSERDEV
        lda #0
        sta b_prompt
        sta b_selected
        sta b_selected+1
        jmp b_rescan
b_prompt_cancel:
        lda #0
        sta b_prompt
        jmp b_redraw
b_down:
        inc b_selected
        bne b_selected_changed
        inc b_selected+1
b_selected_changed:
        jsr b_clamp
        jmp b_redraw
b_up:
        lda b_selected
        ora b_selected+1
        beq b_loop
        lda b_selected
        bne b_up_low
        dec b_selected+1
b_up_low:
        dec b_selected
        jmp b_redraw
b_next_page:
        clc
        lda b_selected
        adc #8
        sta b_selected
        bcc b_selected_changed
        inc b_selected+1
        jmp b_selected_changed
b_previous_page:
        sec
        lda b_selected
        sbc #8
        sta b_selected
        lda b_selected+1
        sbc #0
        sta b_selected+1
        bcs b_redraw
        lda #0
        sta b_selected
        sta b_selected+1
        jmp b_redraw
b_clamp:
        lda b_total
        ora b_total+1
        beq b_clamp_zero
        lda b_selected
        cmp b_total
        lda b_selected+1
        sbc b_total+1
        bcc b_clamped
        sec
        lda b_total
        sbc #1
        sta b_selected
        lda b_total+1
        sbc #0
        sta b_selected+1
b_clamped:
        rts
b_clamp_zero:
        sta b_selected
        sta b_selected+1
        rts
.if !FD_EMBEDDED
b_next_app:
        lda b_total
        ora b_total+1
        beq b_no_apps
        lda b_selected
        sta b_saved_selection
        lda b_selected+1
        sta b_saved_selection+1
b_find_app:
        inc b_selected
        bne b_find_app_bound
        inc b_selected+1
b_find_app_bound:
        lda b_selected
        cmp b_total
        lda b_selected+1
        sbc b_total+1
        bcc b_find_app_read
        lda #0
        sta b_selected
        sta b_selected+1
b_find_app_read:
        jsr b_selected_record
        lda b_record+20
        bne b_redraw
        lda b_selected
        cmp b_saved_selection
        bne b_find_app
        lda b_selected+1
        cmp b_saved_selection+1
        bne b_find_app
b_no_apps:
        lda #$20
        sta b_error
        jmp b_redraw
.endif
b_enter:
        lda b_total
        ora b_total+1
        beq b_loop
        jsr b_selected_record
.if FD_EMBEDDED
        jmp fd_choose_iec
.else
        lda b_record+20
.if B_GUI
        bne +
        lda #1
        sta fl_auto
        jmp b_view_open
+
.else
        beq b_view_open
.endif
.if B_GUI
        jsr fg_exit
        bcs b_loop
.endif
        jsr b_filename
        lda N_FNAMELEN
        sta N_NAMELEN
        ldx #15
b_launch_name:
        lda N_FNAME,x
        sta N_APPNAME,x
        dex
        bpl b_launch_name
        lda N_BROWSERDEV
        sta N_DEVICE
        lda N_BROWSERFMT
        sta N_APPFORMAT
        jmp N_REPLACE
b_inspect:
.if B_GUI
        lda #0
        sta fl_auto
.endif
        lda b_total
        ora b_total+1
        beq b_loop
        jsr b_selected_record
        jmp b_view_open

.endif

; Refresh takes a bounded directory snapshot. File bytes are never written.
b_refresh:
        lda N_BROWSERFMT
        cmp #3
        bne +
        jmp bu_refresh_saved
+
        lda #0
        sta b_total
        sta b_total+1
        sta b_error
        sta b_page
        lda #1
        sta b_busy
        jsr b_draw
b_scan_page:
        lda b_owner
        sta N_FOWNER
        lda N_BROWSERDEV
        sta N_FDEVICE
        lda N_BROWSERFMT
        sta N_FFORMAT
        lda b_page
        sta N_DPAGE
.if FD_EMBEDDED
        lda #0
        ldx #3
-       sta N_FHANDLE,x
        dex
        bpl -
.endif
        jsr N_DIRPAGE
        bcs b_scan_failed
        lda N_DNEXT
        sta b_next
        lda N_DCOUNT
        beq b_scan_done
        ldx #0
b_page_copy:
        lda N_BUFFER,x
        sta b_page_data,x
        inx
        bne b_page_copy
        stx b_scan_offset
b_scan_record:
        ldx b_scan_offset
        lda b_page_data,x
        beq b_scan_next
        ldy #0
b_record_copy:
        lda b_page_data,x
        sta b_record,y
        inx
        iny
        cpy #B_RECORD_BYTES
        bne b_record_copy
.if !FD_GUI
        lda #0
        sta b_record+20
        sta b_record+21
.endif
.if !FD_EMBEDDED
        jsr b_probe_app
.endif
        lda b_total
        sta b_index
        lda b_total+1
        sta b_index+1
        jsr b_cache_select
        ldx #B_RECORD_BYTES-1
b_record_store:
        lda b_record,x
        sta N_BUFFER,x
        dex
        bpl b_record_store
.if FD_EMBEDDED
        jsr fd_write_cache
.else
        jsr N_WRITE
.endif
        bcs b_exit_error
        inc b_total
        bne b_scan_next
        inc b_total+1
b_scan_next:
        clc
        lda b_scan_offset
        adc #32
        sta b_scan_offset
        bne b_scan_record
        lda b_next
        cmp #$ff
        beq b_scan_done
        sta b_page
        jmp b_scan_page
b_scan_failed:
        sta b_error
        lda N_FHANDLE
        beq b_scan_done
.if FD_EMBEDDED
        ldx #3
-       lda N_FHANDLE,x
        sta fd_iec_handle,x
        dex
        bpl -
.endif
        lda b_error
        jmp b_exit_error         ; uncertain metadata cleanup remains owned
b_scan_done:
        lda #0
        sta b_busy
        jmp b_clamp

b_cache_select:
        lda b_owner
        sta N_OWNER
.if !FD_EMBEDDED
        ldx #3
b_cache_handle:
        lda b_cache,x
        sta N_HANDLE,x
        dex
        bpl b_cache_handle
.endif
.if FD_GUI
        lda b_index
        sta N_OFFSET
        lda b_index+1
        sta N_OFFSET+1
        ldx #0
fd_packed_page:
        lda N_OFFSET
        sec
        sbc #12
        tay
        lda N_OFFSET+1
        sbc #0
        bcc fd_packed_cell
        sty N_OFFSET
        sta N_OFFSET+1
        inx
        bne fd_packed_page
fd_packed_cell:
        lda N_OFFSET
        asl
        asl
        sta N_COUNT
        asl
        asl
        clc
        adc N_COUNT
        sta N_OFFSET
        stx N_OFFSET+1
        lda #20
        sta N_COUNT
.else
        lda b_index
        sta N_OFFSET
        lda b_index+1
        sta N_OFFSET+1
        ldx #5
b_cache_offset:
        asl N_OFFSET
        rol N_OFFSET+1
        dex
        bne b_cache_offset
        lda #32
        sta N_COUNT
.endif
        lda #0
        sta N_COUNT+1
.if FD_EMBEDDED
        jmp fd_cache_select
.else
        rts
.endif
b_selected_record:
        lda b_selected
        sta b_index
        lda b_selected+1
        sta b_index+1
b_read_record:
        jsr b_cache_select
.if FD_EMBEDDED
        jsr fd_read_cache
.else
        jsr N_READ
.endif
        bcs b_exit_error
        ldx #B_RECORD_BYTES-1
b_record_loaded:
        lda N_BUFFER,x
        sta b_record,x
        dex
        bpl b_record_loaded
        rts
b_filename:
        ldx #15
b_filename_byte:
        lda b_record+2,x
        sta N_FNAME,x
        dex
        bpl b_filename_byte
        ; Only trailing $a0 bytes are directory padding. An embedded $a0
        ; must reach filename validation instead of selecting a shorter name.
        ldx #16
b_filename_trim:
        lda N_FNAME-1,x
        cmp #$a0
        bne b_filename_done
        dex
        bne b_filename_trim
b_filename_done:
        stx N_FNAMELEN
        rts
.if !FD_EMBEDDED
b_open_record:
        lda #0
        sta b_open
        sta N_FHANDLE
        sta N_FHANDLE+1
        sta N_FHANDLE+2
        sta N_FHANDLE+3
        sta N_FMODE
        lda b_record+1
        and #$80
        beq b_unclosed
        lda b_record
        cmp #1
        bcc b_unsupported
        cmp #4
        bcs b_unsupported
        sec
        sbc #1
        sta N_FTYPE
        jsr b_filename
        lda b_owner
        sta N_FOWNER
        lda N_BROWSERDEV
        sta N_FDEVICE
        lda N_BROWSERFMT
        sta N_FFORMAT
        jsr N_FOPEN
        bcs b_open_failed
        inc b_open
        rts
b_open_failed:
        ldx N_FHANDLE
        bne b_exit_error
        sec
        rts
b_unclosed:
        lda #$22
        sec
        rts
b_unsupported:
        lda #$21
        sec
        rts
b_close_file:
        lda b_open
        beq b_file_closed
        jsr N_FCLOSE
        bcs b_exit_error
        lda #0
        sta b_open
b_file_closed:
        rts
b_probe_app:
        lda b_record
        cmp #2
        bne b_probe_done
        lda b_record+1
        and #$80
        beq b_probe_done
        jsr b_open_record
        bcs b_probe_error
        lda #34
        sta N_FCOUNT
        lda #0
        sta N_FCOUNT+1
        jsr N_FREAD
        bcs b_probe_read_error
        lda N_FACTUAL
        cmp #34
        bne b_probe_close
        ldx #5
b_probe_magic:
        lda N_BUFFER,x
        cmp b_app_magic,x
        bne b_probe_close
        dex
        bpl b_probe_magic
        inc b_record+20         ; discovery only: the loader validates full image/CRC
b_probe_close:
        jmp b_close_file
b_probe_read_error:
        sta b_record+21
        jmp b_probe_close
b_probe_error:
        sta b_record+21
b_probe_done:
        rts

.endif

.include "browser-ui.inc"
.if !FD_EMBEDDED
.include "browser-view.inc"
.endif
.include "browser-usb.inc"
.include "browser-ultimate.inc"

.if !FD_GUI
b_app_magic: .byte 0,$60,$4e,$41,$50,$50
.endif
b_cache:
.if FD_EMBEDDED
        .fill 40,0
.else
        .fill 4,0
.endif
b_owner: .byte 0
b_total: .word 0
b_selected: .word 0
.if !FD_GUI
b_saved_selection: .word 0
.endif
b_index: .word 0
b_page: .byte 0
b_next: .byte 0
b_scan_offset: .byte 0
b_busy: .byte 0
b_error: .byte 0
b_launch_error: .byte 0
.if !FD_GUI
b_open: .byte 0
.endif
b_prompt: .byte 0
b_device_state:
b_device_length: .byte 0
b_device_cursor: .byte 0
        .byte 2
        .word b_device_text
b_device_views: .fill 2,0
        .byte 1
b_device_text: .fill 3,0
.if FD_BUFFER_BASE
b_record=FD_BUFFER_BASE+512
b_page_data=FD_BUFFER_BASE
.else
b_record: .fill B_RECORD_BYTES,0
 .if B_GUI
b_page_data=B_PAGE_STORAGE
 .else
b_page_data: .fill 256,0
 .endif
.endif
