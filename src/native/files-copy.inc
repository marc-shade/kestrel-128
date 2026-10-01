; Native suite file copy. Source bytes are read only. Each new destination is
; created exclusively, closed, reopened and compared against a reopened source.
; No failed write is replayed and no partial destination is deleted. Two owned
; handles stream arbitrary file sizes; the app retains only one 512-byte chunk.
fc_begin:
        lda N_BROWSERFMT
        cmp #3
        beq fc_usb_source
        lda b_total
        ora b_total+1
        beq b_loop
        jsr b_selected_record
        lda b_record+1
        and #$80
        beq fc_unclosed
        lda b_record
        cmp #1
        bcc fc_unsupported
        cmp #4
        bcs fc_unsupported
        sec
        sbc #1
        sta fc_source_type
        jsr b_filename
        lda N_FNAMELEN
        sta fc_source_length
        ldx #15
-       lda N_FNAME,x
        sta fc_source,x
        dex
        bpl -
        jmp fc_source_ready
fc_unclosed:
        lda #$22
        bne fc_selection_error
fc_unsupported:
        lda #$21
fc_selection_error:
        sta b_error
        jmp b_redraw
fc_usb_source:
        lda bu_count
        beq b_loop
        jsr bu_fullname
        bcs fc_selection_error
        lda bu_attribute
        and #$18
        bne fc_unsupported
        lda bu_full_length
        sta fc_source_length
        lda #0
        sta fc_source_type
        ldx #0
-       lda N_UPATH,x
        sta fc_source,x
        inx
        cpx fc_source_length
        bne -
fc_source_ready:
        lda N_BROWSERDEV
        sta fc_source_device
        sta fc_device
        lda N_BROWSERFMT
        sta fc_source_format
        sta fc_format
        cmp #3
        bne +
        ; Ultimate DOS has one file per context; the second context can open
        ; the destination without seeking/replaying writes in the first one.
        lda fc_device
        eor #3
        sta fc_device
+       lda fc_source_type
        sta fc_type
        lda fc_source_length
        sta fc_length
        ldx #0
-       lda fc_source,x
        sta fc_name,x
        inx
        cpx fc_length
        bne -
        lda #0
        sta fc_name,x
        sta fc_status
        sta fc_phase
        sta fc_attempted
        sta fc_prompt
        sta fc_error
        sta fc_dos
        ldx #3
-       sta fc_copied,x
        sta fc_verified,x
        dex
        bpl -
        lda #1
        sta fc_active
        jsr fc_keys_install
        jsr fc_field_init
        jmp fc_redraw

fc_redraw:
        jsr fc_draw
fc_loop:
        lda #1
        sta N_READY
fc_get_key:
        jsr N_KEYIN
.if B_GUI
        jsr fg_input
.endif
        beq fc_loop
        ldx #0
        stx N_READY
.if B_GUI
        cmp #14
        beq fc_redraw
.endif
        ldx fc_prompt
        bne fc_device_key
        cmp #27
        beq fc_leave
        cmp #13
        beq fc_start
        cmp #9
        beq fc_browse
        cmp #$88
        beq fc_browse
        cmp #$85
        beq fc_device_prompt
        cmp #$86
        beq fc_next_format
        cmp #$87
        beq fc_next_type
        sta N_UIKEY
        jsr fc_field_edit
        bcs fc_bad_field
        lda N_UIFLAGS
        and #1
        beq fc_redraw
        jsr fc_reset_result
        jmp fc_redraw
fc_bad_field:
        lda #5
        sta fc_status
        jmp fc_redraw
fc_next_type:
        jsr fc_reset_result
        inc fc_type
        lda fc_type
        cmp #3
        bcc fc_redraw
        lda #0
        sta fc_type
        beq fc_redraw
fc_next_format:
        jsr fc_reset_result
        inc fc_format
        lda fc_format
        cmp #4
        bcc fc_format_advanced
        lda #0
        sta fc_format
        lda N_BOOTDEVICE
        sta fc_device
        ; When leaving USB, retain the basename if it fits an IEC filename.
        lda #0
        sta fc_at
        ldx #0
-       cpx fc_length
        beq fc_leaf_found
        lda fc_name,x
        inx
        cmp #$2f
        bne -
        stx fc_at
        jmp -
fc_leaf_found:
        lda fc_length
        sec
        sbc fc_at
        cmp #17
        bcc +
        lda #0
+       sta fc_length
        ldy #0
        ldx fc_at
-       cpy fc_length
        beq fc_format_init
        lda fc_name,x
        sta fc_name,y
        inx
        iny
        bne -
fc_format_advanced:
        cmp #3
        bne fc_format_init
        lda #1
        sta fc_device
        ldx fc_source_format
        cpx #3
        bne +
        lda fc_source_device
        eor #3
        sta fc_device
+       ldx fc_length
-       lda fc_name,x
        sta fc_name+1,x
        dex
        bpl -
        lda #$2f
        sta fc_name
        inc fc_length
fc_format_init:
        ldx fc_length
        lda #0
        sta fc_name,x
        jsr fc_field_init
        jmp fc_redraw
fc_device_prompt:
        lda #1
        sta fc_prompt
        lda #0
        sta fc_device_length
        sta N_UIKEY
        jsr fc_device_pointer
        jsr N_FEDIT
        jmp fc_redraw
fc_device_key:
        cmp #27
        beq fc_device_cancel
        cmp #13
        beq fc_device_commit
        sta N_UIKEY
        jsr fc_device_pointer
        jsr N_FEDIT
        jmp fc_redraw
fc_device_commit:
        ldx fc_device_length
        beq fc_loop
        lda fc_device_text
        and #15
        cpx #1
        beq fc_device_number
        asl
        sta fc_at
        asl
        asl
        clc
        adc fc_at
        sta fc_at
        lda fc_device_text+1
        and #15
        clc
        adc fc_at
fc_device_number:
        ldx fc_format
        cpx #3
        bne fc_device_iec
        cmp #1
        bcc fc_loop
        cmp #3
        bcs fc_loop
        bcc fc_device_valid
fc_device_iec:
        cmp #8
        bcc fc_loop
        cmp #31
        bcs fc_loop
fc_device_valid:
        sta fc_device
        jsr fc_reset_result
fc_device_cancel:
        lda #0
        sta fc_prompt
        jmp fc_redraw
fc_device_pointer:
        lda #<fc_device_state
        sta N_UIPTR
        lda #>fc_device_state
        sta N_UIPTR+1
        rts
fc_field_init:
        lda #16
        ldx #3
        ldy fc_format
        cpy #3
        bne +
        lda #255
        ldx #0
+       sta fc_max
        stx fc_filter
        lda #0
        sta N_UIKEY
fc_field_edit:
        jsr fc_field_pointer
        jmp N_FEDIT
fc_field_pointer:
        lda #<fc_field
        sta N_UIPTR
        lda #>fc_field
        sta N_UIPTR+1
        rts

fc_browse:
        jsr fc_cleanup
        bcs fc_close_error
.if B_GUI
        jsr fg_picker_load
        bcs fc_picker_failed
        lda fc_status
        cmp #9
        bcc +
        cmp #11
        bcs +
        jsr fc_reset_result
+
.endif
        lda #2
        sta copy_picker.fd_mode
        lda fc_device
        sta copy_picker.fd_device
        lda fc_format
        sta copy_picker.fd_format
        lda fc_length
        sta copy_picker.fd_length
.if B_GUI
        jsr N_MCALL
        jsr fg_picker_done
.else
        jsr copy_picker.fd_run
.endif
        bcs fc_picker_failed
        lda copy_picker.fd_device
        sta fc_device
        lda copy_picker.fd_format
        sta fc_format
        lda copy_picker.fd_length
        sta fc_length
        jsr fc_field_init
        jsr fc_reset_result
        jmp fc_redraw
fc_picker_failed:
        cmp #0
        beq fc_redraw
        sta fc_error
        lda #10
        sta fc_status
        jmp fc_redraw

; A completed result belongs to the exact destination used for that operation.
; Editing it must not label a different name/device/type as already verified.
; Retained cleanup errors stay visible until their descriptors are released.
fc_reset_result:
        lda fc_handles
        ora fc_handles+4
.if B_GUI
        bne fc_result_retained
        lda fg_kind
        cmp #2
        bne fc_result_clear
        lda #0
.endif
        ora copy_picker.bu_cursor
        ora copy_picker.fd_iec_handle
        bne fc_result_retained
        ldx #36
-       lda copy_picker.b_cache,x
        bne fc_result_retained
        dex
        dex
        dex
        dex
        bpl -
fc_result_clear:
        lda #0
        sta fc_status
        sta fc_attempted
        sta fc_error
        sta fc_dos
        ldx #7
-       sta fc_copied,x
        dex
        bpl -
fc_result_retained:
        rts

fc_leave:
        jsr fc_cleanup
        bcs fc_close_error
        lda #0
        sta fc_active
        sta b_error
        jsr fc_keys_restore
        jsr b_refresh
        jmp b_redraw

; Keep every close/free descriptor until the service acknowledges release.
; This also makes a cancelled/failed picker recoverable before copying or
; returning to a browser that needs the same file channels.
fc_cleanup:
.if B_GUI
        jsr fg_loader_clean
        bcs fc_cleanup_done
.endif
        jsr bu_close_cursor
        bcs fc_cleanup_done
.if B_GUI
        jsr fg_picker_clean
        bcs fc_cleanup_done
.else
        jsr copy_picker.fd_close_cursors
        bcs fc_cleanup_done
        lda #36
        sta fc_cache_at
fc_cleanup_cache:
        ldx fc_cache_at
        lda copy_picker.b_cache,x
        beq fc_cleanup_next
        ldy #0
-       lda copy_picker.b_cache,x
        sta N_HANDLE,y
        inx
        iny
        cpy #4
        bne -
        lda b_owner
        sta N_OWNER
        jsr N_FREE
        bcs fc_cleanup_done
        ldx fc_cache_at
        lda #0
        sta copy_picker.b_cache,x
fc_cleanup_next:
        dec fc_cache_at
        dec fc_cache_at
        dec fc_cache_at
        dec fc_cache_at
        bpl fc_cleanup_cache
.endif
fc_close_streams:
        ; Close destination first so its result is checked before verification.
        lda #4
        sta fc_slot
        jsr fc_close_one
        bcs fc_cleanup_done
        lda #0
        sta fc_slot
fc_close_one:
        ldx fc_slot
        lda fc_handles,x
        beq fc_close_empty
        jsr fc_select
        jsr N_FCLOSE
        bcs fc_cleanup_done
        ldx fc_slot
        lda #0
        sta fc_handles,x
fc_close_empty:
        clc
fc_cleanup_done:
        rts

fc_start:
        jsr fc_cleanup
        bcs fc_close_error
        lda #0
        sta fc_status
        sta fc_attempted
        sta fc_error
        sta fc_dos
        sta fc_phase
        ldx #3
-       sta fc_copied,x
        sta fc_verified,x
        dex
        bpl -
        lda fc_length
        beq fc_bad_field
        lda fc_format
        cmp #3
        bne fc_copy_open
        lda fc_source_format
        cmp #3
        bne fc_copy_open
        lda fc_source_device
        cmp fc_device
        bne fc_copy_open
        lda #8
        sta fc_status
        jmp fc_redraw
fc_copy_open:
        lda #1
        sta fc_phase
        jsr fc_draw
        lda #0
        sta fc_slot
        jsr fc_open
        bcs fc_io_error
        jsr fc_select
        jsr fc_read_chunk
        bcs fc_io_error
        lda fc_size
        ora fc_size+1
        bne fc_destination_open
        lda fc_eof
        beq fc_short_io
        lda fc_format
        cmp #3
        beq fc_destination_open
        ; 1541/1571/1581 DOS clswrt inserts CR when closing a write channel
        ; with no bytes. The current IEC API has no truncate/sector-write
        ; operation. Refuse before create instead of producing a changed copy.
        lda #13
        jmp fc_fail_status
fc_destination_open:
        ; OPEN may overwrite the service buffer, so retain the first read.
        jsr fc_stash
        lda #4
        sta fc_slot
        lda #1
        sta fc_attempted
        jsr fc_open
        bcs fc_io_error
        jmp fc_copy_buffer
fc_copy_chunk:
        jsr fc_cancel
        bcs fc_cancelled
        lda #0
        sta fc_slot
        jsr fc_select
        jsr fc_read_chunk
        bcs fc_io_error
        lda fc_size
        ora fc_size+1
        beq fc_copy_empty
        jsr fc_stash
fc_copy_buffer:
        lda fc_size
        ora fc_size+1
        beq fc_copy_empty
        lda #4
        sta fc_slot
        jsr fc_select
        ; FWRITE may use the shared transfer buffer internally; refill it
        ; from the saved source bytes and compare the acknowledged count.
        ldx #0
-       lda fc_data,x
        sta N_BUFFER,x
        lda fc_data+256,x
        sta N_BUFFER+256,x
        inx
        bne -
        lda fc_size
        sta N_FCOUNT
        lda fc_size+1
        sta N_FCOUNT+1
        jsr N_FWRITE
        bcs fc_io_error
        lda N_FACTUAL
        cmp fc_size
        bne fc_short_io
        lda N_FACTUAL+1
        cmp fc_size+1
        bne fc_short_io
        jsr fc_advance
        bcs fc_short_io
        jsr fc_progress
fc_copy_empty:
        lda fc_eof
        bne fc_copy_close
        lda fc_size
        ora fc_size+1
        bne fc_copy_chunk
fc_short_io:
        lda #N_IOERROR
        jmp fc_io_error
fc_copy_close:
        jsr fc_close_streams
        bcs fc_close_error
        lda #2
        sta fc_phase
        jsr fc_draw
        lda #0
        sta fc_slot
        jsr fc_open
        bcs fc_io_error
        lda #4
        sta fc_slot
        lda #0
        jsr fc_open
        bcs fc_io_error
fc_verify_chunk:
        jsr fc_cancel
        bcs fc_cancelled
        lda #0
        sta fc_slot
        jsr fc_select
        jsr fc_read_chunk
        bcs fc_io_error
        lda fc_size
        ora fc_size+1
        beq fc_verify_empty
        jsr fc_stash
        lda #4
        sta fc_slot
        jsr fc_select
        lda fc_size
        sta N_FCOUNT
        lda fc_size+1
        sta N_FCOUNT+1
        jsr N_FREAD
        bcs fc_io_error
        lda N_FACTUAL
        cmp fc_size
        bne fc_mismatch
        lda N_FACTUAL+1
        cmp fc_size+1
        bne fc_mismatch
        ldx #0
fc_compare:
        lda fc_size+1
        cmp #2
        beq fc_compare_both
        cmp #1
        beq fc_compare_low
        cpx fc_size
        bcs fc_compare_done
fc_compare_low:
        lda N_BUFFER,x
        cmp fc_data,x
        bne fc_mismatch
        lda fc_size+1
        beq fc_compare_next
        cpx fc_size
        bcs fc_compare_next
        bcc fc_compare_high
fc_compare_both:
        lda N_BUFFER,x
        cmp fc_data,x
        bne fc_mismatch
fc_compare_high:
        lda N_BUFFER+256,x
        cmp fc_data+256,x
        bne fc_mismatch
fc_compare_next:
        inx
        bne fc_compare
fc_compare_done:
        jsr fc_advance
        bcs fc_mismatch
        jsr fc_progress
fc_verify_empty:
        lda fc_eof
        bne fc_verify_end
        lda fc_size
        ora fc_size+1
        bne fc_verify_chunk
        beq fc_short_io
fc_verify_end:
        ; A final one-byte read proves that the destination has no extra tail,
        ; including the empty-file case and exact multiples of 512 bytes.
        lda #4
        sta fc_slot
        jsr fc_select
        lda #1
        sta N_FCOUNT
        lda #0
        sta N_FCOUNT+1
        jsr N_FREAD
        bcs fc_io_error
        lda N_FACTUAL
        ora N_FACTUAL+1
        bne fc_mismatch
        lda N_FEOF
        beq fc_mismatch
        ldx #3
-       lda fc_copied,x
        cmp fc_verified,x
        bne fc_mismatch
        dex
        bpl -
        jsr fc_close_streams
        bcs fc_close_error
        lda #1
        sta fc_status
        lda #2
        sta fc_attempted
        jmp fc_finished
fc_mismatch:
        lda #7
        bne fc_fail_status
fc_cancelled:
        lda #2
fc_fail_status:
        sta fc_status
        jsr fc_close_streams
        bcs fc_close_error
fc_finished:
        lda #0
        sta fc_phase
        jmp fc_redraw
fc_io_error:
        sta fc_error
        lda N_FDOS
        sta fc_dos
        lda #3
        sta fc_status
        lda fc_error
        cmp #N_BADARG
        bne +
        lda #5
        sta fc_status
+       lda fc_phase
        cmp #1
        bne fc_fail_close
        lda fc_slot
        cmp #4
        bne fc_fail_close
        lda fc_dos
        cmp #63
        bne fc_fail_close
        lda #4
        sta fc_status
        lda #0
        sta fc_attempted
fc_fail_close:
        jsr fc_close_streams
        bcc fc_finished
fc_close_error:
        sta fc_error
        lda N_FDOS
        sta fc_dos
        lda #9
        sta fc_status
        jmp fc_finished

; A=read/exclusive-create, fc_slot=0 source/4 destination. Save the returned
; handle even on failure: an uncertain OPEN must remain owned for cleanup.
fc_open:
        sta N_FMODE
        lda b_owner
        sta N_FOWNER
        ldx #3
        lda #0
-       sta N_FHANDLE,x
        dex
        bpl -
        lda fc_slot
        bne fc_open_destination
        lda fc_source_device
        sta N_FDEVICE
        lda fc_source_format
        sta N_FFORMAT
        lda fc_source_type
        sta N_FTYPE
        lda fc_source_length
        sta N_FNAMELEN
        ldx #0
-       lda fc_source,x
        sta N_UPATH,x
        cpx #16
        bcs +
        sta N_FNAME,x
+       inx
        bne -
        beq fc_open_call
fc_open_destination:
        lda fc_device
        sta N_FDEVICE
        lda fc_format
        sta N_FFORMAT
        lda fc_type
        sta N_FTYPE
        lda fc_length
        sta N_FNAMELEN
        ldx #0
-       lda fc_name,x
        sta N_UPATH,x
        cpx #16
        bcs +
        sta N_FNAME,x
+       inx
        bne -
fc_open_call:
        jsr N_FOPEN
        php
        pha
        ldx fc_slot
        ldy #0
-       lda N_FHANDLE,y
        sta fc_handles,x
        inx
        iny
        cpy #4
        bne -
        pla
        plp
        rts
fc_select:
        lda b_owner
        sta N_FOWNER
        ldx fc_slot
        ldy #0
-       lda fc_handles,x
        sta N_FHANDLE,y
        inx
        iny
        cpy #4
        bne -
        rts
fc_read_chunk:
        lda #0
        sta N_FCOUNT
        lda #2
        sta N_FCOUNT+1
        jsr N_FREAD
        bcs +
        lda N_FACTUAL
        sta fc_size
        lda N_FACTUAL+1
        sta fc_size+1
        lda N_FEOF
        sta fc_eof
        clc
+       rts
fc_stash:
        ldx #0
-       lda N_BUFFER,x
        sta fc_data,x
        lda N_BUFFER+256,x
        sta fc_data+256,x
        inx
        bne -
        rts
fc_advance:
        ldx #0
        lda fc_phase
        cmp #1
        beq +
        ldx #4
+       clc
        lda fc_copied,x
        adc fc_size
        sta fc_copied,x
        lda fc_copied+1,x
        adc fc_size+1
        sta fc_copied+1,x
        lda fc_copied+2,x
        adc #0
        sta fc_copied+2,x
        lda fc_copied+3,x
        adc #0
        sta fc_copied+3,x
        rts
fc_cancel:
        jsr N_KEYIN
.if B_GUI
        jsr fg_input
.endif
        cmp #27
        beq +
        clc
        rts
+       sec
        rts
fc_progress:
        ; Update both displays every 8 KiB. Cancellation is checked for every
        ; chunk, even between redraws and during the reopened comparison.
        ldx #0
        lda fc_phase
        cmp #1
        beq +
        ldx #4
+       lda fc_copied,x
        bne +
        lda fc_copied+1,x
        and #31
        beq fc_draw
+       rts

fc_draw:
.if B_GUI
        jsr fg_copy_draw
.endif
        lda #0
.if B_GUI
        ldx fg_collect
        bne +
        ora fg_bitmap
+
.endif
        sta b_screen
fc_draw_screen:
.if B_GUI
        lda b_screen
        beq +
        lda vd_phase
        bne fc_screen_done
+       lda fg_collect
        bne fc_screen_selected
.endif
        lda $d7
        rol
        lda #0
        rol
        cmp b_screen
        beq +
        jsr $ff5f
+
fc_screen_selected:
        lda #$93
        jsr b_usb_chrout
        lda #<fc_title
        ldx #>fc_title
        jsr b_puts
        lda fc_source_device
        ldx #0
        jsr b_number
        lda #<b_format_text
        ldx #>b_format_text
        jsr b_puts
        ldx fc_source_format
        jsr fc_print_format
        lda #13
        jsr b_usb_chrout
        ; The exact source is retained; long read-only names show their tail.
        lda #39
.if B_GUI
        ldx fg_collect
        beq +
        lda #38
+
.endif
        ldx b_screen
        beq +
        lda #79
+       sta fc_width
        lda #0
        sta fc_at
        lda fc_source_length
        cmp fc_width
        bcc fc_source_text
        beq fc_source_text
        sec
        sbc fc_width
        clc
        adc #1
        sta fc_at
        lda #$3c
        jsr b_usb_chrout
fc_source_text:
        ldx fc_at
        cpx fc_source_length
        beq fc_draw_destination
        lda fc_source,x
        jsr b_safe_character
        jsr b_usb_chrout
        inc fc_at
        jmp fc_source_text
fc_draw_destination:
        lda #<fc_to
        ldx #>fc_to
        jsr b_puts
        lda fc_device
        ldx #0
        jsr b_number
        lda #<b_format_text
        ldx #>b_format_text
        jsr b_puts
        ldx fc_format
        jsr fc_print_format
        lda #<fc_type_title
        ldx #>fc_type_title
        jsr b_puts
        ldx fc_type
        inx
        lda b_types_lo,x
        pha
        lda b_types_hi,x
        tax
        pla
        jsr b_puts
        lda #<fc_name_title
        ldx #>fc_name_title
        jsr b_puts
        jsr fc_field_pointer
        lda fc_width
        sec
        sbc #6
        sta N_UIWIDTH
.if B_GUI
        jsr fg_field_output
.else
        jsr N_FDRAW
.endif
        lda #<fc_help
        ldx #>fc_help
.if B_GUI
        ldy fg_bitmap
        bne fc_gui_help
        ldy fg_collect
        beq fc_help_ready
fc_gui_help:
        lda #<fc_graphical_help
        ldx #>fc_graphical_help
fc_help_ready:
.endif
        jsr b_puts
        lda fc_prompt
        beq fc_draw_progress
        lda #<fc_device_question
        ldx #>fc_device_question
        jsr b_puts
        jsr fc_device_pointer
        lda #5
        sta N_UIWIDTH
.if B_GUI
        jsr fg_field_output
.else
        jsr N_FDRAW
.endif
fc_draw_progress:
.if B_GUI
        lda fg_collect
        beq +
        lda #14
        sta fv_row
        lda #0
        sta fv_column
        beq fc_progress_positioned
+
.endif
        ldx #14
        ldy #0
        clc
        jsr $fff0
fc_progress_positioned:
        lda #<fc_copied_title
        ldx #>fc_copied_title
        jsr b_puts
        ldx #3
-       lda fc_copied,x
        sta bu_number,x
        dex
        bpl -
        jsr bu_number_begin
        lda #<fc_verified_title
        ldx #>fc_verified_title
        jsr b_puts
        ldx #3
-       lda fc_verified,x
        sta bu_number,x
        dex
        bpl -
        jsr bu_number_begin
        lda #13
        jsr b_usb_chrout
        ldx fc_status
        lda fc_phase
        beq +
        clc
        adc #10
        tax
+       lda fc_status_lo,x
        pha
        lda fc_status_hi,x
        tax
        pla
        jsr b_puts
        lda fc_error
        beq fc_draw_partial
        lda #<fc_error_title
        ldx #>fc_error_title
        jsr b_puts
        lda fc_error
        jsr b_hex
        lda #<fc_dos_title
        ldx #>fc_dos_title
        jsr b_puts
        lda fc_dos
        ldx #0
        jsr b_number
fc_draw_partial:
        lda fc_phase
        bne fc_draw_busy
        lda fc_attempted
        cmp #1
        bne fc_screen_done
        lda #<fc_partial
        ldx #>fc_partial
        jsr b_puts
        jmp fc_screen_done
fc_draw_busy:
        lda #<fc_cancel_help
        ldx #>fc_cancel_help
        jsr b_puts
fc_screen_done:
.if B_GUI
        lda fg_collect
        bne fc_screen_return
.endif
        inc b_screen
        lda b_screen
        cmp #2
        bne fc_draw_screen
.if B_GUI
        jsr fg_focus_footer
.endif
fc_screen_return:
        rts
fc_print_format:
        cpx #3
        bne +
        lda #<fc_ult
        ldx #>fc_ult
        jmp b_puts
+       lda b_formats_lo,x
        pha
        lda b_formats_hi,x
        tax
        pla
        jmp b_puts

; The ROM expands function keys through $1000. Own that table only while the
; copy dialog (including its picker) is active, and restore it before any
; browser rescan, app launch or desktop return can take place.
fc_keys_install:
.if B_GUI
        rts
fc_keys_restore:
        rts
.else
        php
        sei
        ldx #0
-       lda $1000,x
        sta fc_saved_keys,x
        inx
        bne -
        ldx #9
-       lda #1
        sta $1000,x
        lda fc_key_codes,x
        sta $100a,x
        dex
        bpl -
        lda #0
        sta $d1
        sta $d2
        plp
        rts
fc_keys_restore:
        php
        sei
        ldx #0
-       lda fc_saved_keys,x
        sta $1000,x
        inx
        bne -
        lda #0
        sta $d1
        sta $d2
        plp
        rts
.endif
fc_title: .text "kestrel copy a file",13,13,"from: ",0
fc_to: .text 13,13,"to: ",0
fc_type_title: .text "  type: ",0
fc_name_title: .text 13,13,"name: ",0
fc_help: .text 13,13,"enter copy  tab browse  esc file list",13
        .text "f1 device/dos  f3 format  f5 file type",13
        .text "ctrl-u clear name",13,0
.if B_GUI
fc_graphical_help: .text 13,13,"f7 browse  esc file list",13
        .text "f1 device/dos  f3 format  f5 file type",13
        .text "ctrl-u clear name",13,0
.endif
fc_device_question: .text "device/dos: ",0
fc_ult: .text "ult",0
fc_copied_title: .text "copied: ",0
fc_verified_title: .text 13,"verified: ",0
fc_ready: .text "new files only; choose a new name",0
fc_success: .text "copy closed, reopened and verified",0
fc_cancel_text: .text "copy cancelled",0
fc_failed_text: .text "file i/o failed",0
fc_exists_text: .text "file exists; choose another name",0
fc_bad_text: .text "invalid name, type or device",0
fc_unsupported_text: .text "file type cannot be copied",0
fc_mismatch_text: .text "reopened files do not match",0
fc_context_text: .text "use the other dos context (f1)",0
fc_close_text: .text "close failed; retry copy/browse/back",0
fc_picker_text: .text "destination picker failed; f7 retries",0
fc_copy_text: .text "copying to a new file...",0
fc_verify_text: .text "reopening and comparing every byte...",0
fc_empty_text: .text "zero-byte iec create is unsupported",0
fc_partial: .text 13,"new file may be incomplete",0
fc_cancel_help: .text 13,"esc cancels after the current transfer",0
fc_error_title: .text 13,"error: ",0
fc_dos_title: .text "  dos: ",0
fc_status_lo: .byte <fc_ready,<fc_success,<fc_cancel_text,<fc_failed_text,<fc_exists_text,<fc_bad_text,<fc_unsupported_text,<fc_mismatch_text,<fc_context_text,<fc_close_text,<fc_picker_text,<fc_copy_text,<fc_verify_text,<fc_empty_text
fc_status_hi: .byte >fc_ready,>fc_success,>fc_cancel_text,>fc_failed_text,>fc_exists_text,>fc_bad_text,>fc_unsupported_text,>fc_mismatch_text,>fc_context_text,>fc_close_text,>fc_picker_text,>fc_copy_text,>fc_verify_text,>fc_empty_text
fc_active: .byte 0
fc_prompt: .byte 0
fc_status: .byte 0
fc_phase: .byte 0
fc_attempted: .byte 0
fc_error: .byte 0
fc_dos: .byte 0
fc_source_device: .byte 0
fc_source_format: .byte 0
fc_source_type: .byte 0
fc_source_length: .byte 0
fc_device: .byte 0
fc_format: .byte 0
fc_type: .byte 0
fc_field:
fc_length: .byte 0
fc_caret: .byte 0
fc_max: .byte 16
        .word fc_name
fc_views: .fill 2,0
fc_filter: .byte 3
fc_device_state:
fc_device_length: .byte 0
        .byte 0,2
        .word fc_device_text
        .byte 0,0,1
fc_device_text: .fill 3,0
fc_at: .byte 0
fc_cache_at: .byte 0
fc_slot: .byte 0
fc_handles: .fill 8,0
fc_size: .word 0
fc_eof: .byte 0
fc_width: .byte 0
fc_copied: .fill 4,0
fc_verified: .fill 4,0
.weak
FC_SOURCE_STORAGE=0
FC_DATA_STORAGE=0
.endweak
.if FC_SOURCE_STORAGE
fc_source=FC_SOURCE_STORAGE
.else
fc_source: .fill 256,0
.endif
fc_name: .fill 256,0
.if FC_DATA_STORAGE
fc_data=FC_DATA_STORAGE
.else
fc_data:
.if B_GUI
        .fill 1024,0            ; copy/verify use 512; picker borrows two buffers
.else
        .fill 2048,0
.endif
.endif
.if !B_GUI
fc_key_codes: .byte $85,$89,$86,$8a,$87,$8b,$88,$8c,$83,$84
fc_saved_keys: .fill 256,0

.endif
