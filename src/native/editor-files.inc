; Transactional Open and exclusive Save As with a complete reopen comparison.
; A failed/cancelled Open discards only the pending context. A failed Save As
; leaves dirty state intact and never retries or deletes partially written data.
ed_close_owned:
.if NATIVE_EDITOR_GRAPHICS
        jsr eg_cleanup
        bcc +
        rts
+
.endif
        lda d_owner
        sta N_FOWNER
        jmp N_FRELEASE
ed_file_open:
        sta N_FMODE
        lda d_owner
        sta N_FOWNER
        lda ed_device
        sta N_FDEVICE
        lda ed_format
        sta N_FFORMAT
        lda ed_field_len
        sta N_FNAMELEN
        lda ed_format
        cmp #3
        bne ed_file_iec
        ldx #0
ed_file_path:
        lda ed_field,x
        sta N_UPATH,x
        inx
        bne ed_file_path
        beq ed_file_type_select
ed_file_iec:
        ldx #15
ed_file_name:
        lda ed_field,x
        sta N_FNAME,x
        dex
        bpl ed_file_name
ed_file_type_select:
        lda ed_file_type
        sta N_FTYPE
        jmp N_FOPEN
ed_io_reset:
        lda #0
        sta ed_mode
        sta ed_status
        sta ed_io_pos
        sta ed_io_pos+1
        sta ed_io_pos+2
        sta ed_io_size+2
        rts
ed_file_close_error:
        lda #9
        sta ed_status
        lda #0
        sta ed_mode
        jmp ed_refresh

ed_open_file:
        jsr ed_io_reset
        jsr ed_close_owned
        bcs ed_file_close_error
        lda ed_active
        eor #$80
        sta ed_pending
        sta d_slot
        jsr doc_dispose
        bcs ed_open_memory_failed
        lda #0
        sta ed_nl_found
        sta ed_nl_value
        lda #1
        sta ed_io_phase
        jsr ed_progress
.if NATIVE_EDITOR_GRAPHICS
        bcs ed_open_cancelled
.endif
        lda #0
        jsr ed_file_open
        bcs ed_open_failed
ed_open_read:
        jsr ed_read_file_chunk
        bcs ed_open_failed
        lda ed_io_size
        ora ed_io_size+1
        beq ed_open_empty_chunk
        lda #<N_BUFFER
        ldx #>N_BUFFER
        ldy #<d_input
        sty doc_local_write+1
        ldy #>d_input
        sty doc_local_write+2
        jsr ed_file_copy
        jsr ed_detect_newline
        #doc_load3 D_LEN,d_pos
        #ed_move3 ed_io_size,d_count
        jsr doc_insert
        bcs ed_open_memory_failed
        jsr ed_io_advance
        jsr ed_cancel_check
        bcs ed_open_cancelled
ed_open_empty_chunk:
        lda ed_io_eof
        bne ed_open_close
        lda ed_io_size
        ora ed_io_size+1
        beq ed_open_failed
        jsr ed_progress_maybe
.if NATIVE_EDITOR_GRAPHICS
        bcs ed_open_cancelled
.endif
        jmp ed_open_read
ed_open_close:
        jsr N_FCLOSE
        bcs ed_open_failed
        ; The new bytes and input CLOSE are complete before disposing the old
        ; context. A failed old-buffer release retains its remaining handles.
        lda ed_active
        sta d_slot
        jsr doc_dispose
        lda #0
        bcc +
        lda #11
+       sta ed_finish_status
        lda ed_pending
        sta ed_active
        sta d_slot
        jsr ed_reset_view
        jsr ed_keep_name
        lda ed_nl_value
        sta ed_newline
        ldx ed_active
        lda #0
        sta d_states+D_DIRTY,x
        lda ed_finish_status
        sta ed_status
        jmp ed_refresh
ed_open_cancelled:
        lda #8
        bne ed_open_rollback
ed_open_failed:
        lda #2
        bne ed_open_rollback
ed_open_memory_failed:
        cmp #N_NOMEM
        beq ed_open_no_memory
        cmp #N_NOSLOT
        beq ed_open_no_memory
        lda #5
        bne ed_open_rollback
ed_open_no_memory:
        lda #3
ed_open_rollback:
        sta ed_status
        jsr ed_close_owned
        bcc +
        lda #9
        sta ed_status
+       lda ed_pending
        sta d_slot
        jsr doc_dispose
        bcc +
        lda #5
        sta ed_status
+       lda ed_active
        sta d_slot
        jmp ed_refresh

ed_save_file:
        jsr ed_io_reset
        lda ed_active
        sta d_slot
        jsr doc_context
        bcs ed_doc_error
        jsr ed_close_owned
        bcs ed_file_close_error
        lda #2
        sta ed_io_phase
        jsr ed_progress
.if NATIVE_EDITOR_GRAPHICS
        bcs ed_save_cancelled
.endif
        lda #1
        jsr ed_file_open
        bcc ed_save_write
        lda N_FDOS
        cmp #63
        bne ed_save_failed
        lda #6
        bne ed_save_cleanup
ed_save_write:
        #ed_move3 ed_io_pos,d_pos
        lda #0
        sta d_count
        lda #2
        sta d_count+1
        jsr doc_read
        bcs ed_save_failed
        lda d_actual
        sta ed_io_size
        lda d_actual+1
        sta ed_io_size+1
        ora ed_io_size
        beq ed_save_written
        lda #<N_BUFFER
        sta doc_local_write+1
        lda #>N_BUFFER
        sta doc_local_write+2
        lda #<d_output
        ldx #>d_output
        jsr ed_file_copy
        lda ed_io_size
        sta N_FCOUNT
        lda ed_io_size+1
        sta N_FCOUNT+1
        jsr N_FWRITE
        bcs ed_save_failed
        lda N_FACTUAL
        cmp ed_io_size
        bne ed_save_failed
        lda N_FACTUAL+1
        cmp ed_io_size+1
        bne ed_save_failed
        jsr ed_io_advance
        jsr ed_cancel_check
        bcs ed_save_cancelled
        jsr ed_progress_maybe
.if NATIVE_EDITOR_GRAPHICS
        bcs ed_save_cancelled
.endif
        jmp ed_save_write
ed_save_written:
        jsr N_FCLOSE
        bcs ed_save_failed
        jsr ed_io_reset
        lda #3
        sta ed_io_phase
        jsr ed_progress
.if NATIVE_EDITOR_GRAPHICS
        bcs ed_save_cancelled
.endif
        lda #0
        jsr ed_file_open
        bcs ed_save_failed
ed_verify_read:
        jsr ed_read_file_chunk
        bcs ed_save_failed
        lda #<ed_verify_data
        sta doc_local_write+1
        lda #>ed_verify_data
        sta doc_local_write+2
        lda #<N_BUFFER
        ldx #>N_BUFFER
        jsr ed_file_copy
        #ed_move3 ed_io_pos,d_pos
        lda #0
        sta d_count
        lda #2
        sta d_count+1
        jsr doc_read
        bcs ed_save_failed
        lda d_actual
        cmp ed_io_size
        bne ed_save_failed
        lda d_actual+1
        cmp ed_io_size+1
        bne ed_save_failed
        jsr ed_verify_chunk
        bcs ed_save_failed
        jsr ed_io_advance
        jsr ed_cancel_check
        bcs ed_save_cancelled
        lda ed_io_eof
        bne ed_verify_done
        lda ed_io_size
        ora ed_io_size+1
        beq ed_save_failed
        jsr ed_progress_maybe
.if NATIVE_EDITOR_GRAPHICS
        bcs ed_save_cancelled
.endif
        jmp ed_verify_read
ed_verify_done:
        #doc_cmp3 ed_io_pos,ed_length
        bne ed_save_failed
        jsr N_FCLOSE
        bcs ed_save_failed
        ldx ed_active
        lda #0
        sta d_states+D_DIRTY,x
.if NATIVE_EDITOR_GRAPHICS
        jsr eh_save
.endif
        jsr ed_keep_name
        lda #1
        sta ed_status
        jmp ed_refresh
ed_save_cancelled:
        lda #10
        bne ed_save_cleanup
ed_save_failed:
        lda #7
ed_save_cleanup:
        sta ed_status
        jsr ed_close_owned
        bcc +
        lda #9
        sta ed_status
+       jmp ed_refresh
ed_keep_name:
        ldx #0
ed_keep_name_loop:
        lda ed_field,x
        sta ed_name,x
        inx
        bne ed_keep_name_loop
        rts
ed_read_file_chunk:
        lda #0
        sta N_FCOUNT
        lda #2
        sta N_FCOUNT+1
        jsr N_FREAD
        bcs +
        lda N_FACTUAL
        sta ed_io_size
        lda N_FACTUAL+1
        sta ed_io_size+1
        lda N_FEOF
        sta ed_io_eof
        clc
+       rts
ed_file_copy:
        sta doc_local_read+1
        stx doc_local_read+2
        lda ed_io_size
        sta d_n
        lda ed_io_size+1
        sta d_n+1
        ora d_n
        beq +
        jmp doc_local_copy
+       rts
ed_io_advance:
        #doc_add3 ed_io_size,ed_io_pos
        rts
ed_verify_chunk:
        lda #<ed_verify_data
        sta ed_verify_file+1
        lda #>ed_verify_data
        sta ed_verify_file+2
        lda #<d_output
        sta ed_verify_doc+1
        lda #>d_output
        sta ed_verify_doc+2
        lda ed_io_size
        sta ed_compare_left
        lda ed_io_size+1
        sta ed_compare_left+1
        ora ed_compare_left
        beq ed_compare_ok
        ldx #0
ed_verify_file:
        lda $ffff,x
ed_verify_doc:
        cmp $ffff,x
        bne ed_compare_failed
        inx
        bne +
        inc ed_verify_file+2
        inc ed_verify_doc+2
+       lda ed_compare_left
        bne +
        dec ed_compare_left+1
+       dec ed_compare_left
        lda ed_compare_left
        ora ed_compare_left+1
        bne ed_verify_file
ed_compare_ok:
        clc
        rts
ed_compare_failed:
        sec
        rts

; Preserve all imported bytes, and use the first CR/LF convention for Enter.
; A CR at the end of a transfer remains pending until the next byte or EOF.
ed_detect_newline:
        lda ed_nl_found
        cmp #2
        beq ed_nl_done
        lda #<d_input
        sta ed_nl_read+1
        lda #>d_input
        sta ed_nl_read+2
        lda ed_io_size
        sta ed_nl_left
        lda ed_io_size+1
        sta ed_nl_left+1
        ldx #0
ed_nl_read:
        lda $ffff,x
        ldy ed_nl_found
        bne ed_nl_after_cr
        cmp #13
        beq ed_nl_cr
        cmp #10
        beq ed_nl_lf
        jmp ed_nl_next
ed_nl_cr:
        inc ed_nl_found
        jmp ed_nl_next
ed_nl_lf:
        lda #1
        sta ed_nl_value
        bne ed_nl_fixed
ed_nl_after_cr:
        cmp #10
        bne ed_nl_fixed
        lda #2
        sta ed_nl_value
ed_nl_fixed:
        lda #2
        sta ed_nl_found
ed_nl_done:
        rts
ed_nl_next:
        inx
        bne +
        inc ed_nl_read+2
+       lda ed_nl_left
        bne +
        dec ed_nl_left+1
+       dec ed_nl_left
        lda ed_nl_left
        ora ed_nl_left+1
        bne ed_nl_read
        rts
ed_cancel_check:
        jsr N_KEYIN
.if NATIVE_EDITOR_GRAPHICS
        jsr eg_input
.endif
        cmp #27
        beq +
        clc
        rts
+       sec
        rts
ed_progress_maybe:
        lda ed_io_pos
        bne +
        lda ed_io_pos+1
        and #31
        bne +
        jmp ed_progress
+
.if NATIVE_EDITOR_GRAPHICS
        clc
.endif
        rts
ed_progress:
.if NATIVE_EDITOR_GRAPHICS
        lda #6
        jsr eg_render
        jsr eg_screen_start
.else
        lda #0
.endif
        sta ed_screen
ed_progress_screen:
.if NATIVE_EDITOR_GRAPHICS
        lda ed_screen
        cmp #2
        bcs ed_progress_done
        lda eg_collect
        bne ed_progress_selected
.endif
        lda $d7
        rol
        lda #0
        rol
        cmp ed_screen
        beq +
        jsr $ff5f
+
ed_progress_selected:
        lda #$93
        jsr ed_chrout
        ldx ed_io_phase
        dex
        lda ed_progress_lo,x
        pha
        lda ed_progress_hi,x
        tax
        pla
        jsr ed_puts
        lda #<ed_field
        ldx #>ed_field
        jsr ed_safe_puts
        lda #<ed_progress_count
        ldx #>ed_progress_count
        jsr ed_puts
        #ed_move3 ed_io_pos,ed_print_number
        jsr ed_hex24
        lda #<ed_progress_cancel
        ldx #>ed_progress_cancel
        jsr ed_puts
.if NATIVE_EDITOR_GRAPHICS
        lda eg_collect
        bne +
.endif
        inc ed_screen
        lda ed_screen
        cmp #2
        bne ed_progress_screen
.if NATIVE_EDITOR_GRAPHICS
+
ed_progress_done:
        ; A failed progress redraw must pause before the next file transfer.
        ; Return Escape to the caller's existing cancel/rollback path.
        lda #0
        jsr eg_vdc_guard
        cmp #27
        beq +
        clc
        rts
+       sec
.endif
        rts
ed_opening: .text "opening: ",0
ed_saving: .text "saving new file: ",0
ed_verifying: .text "reopening and comparing: ",0
ed_progress_count: .text 13,13,"bytes: ",0
ed_progress_cancel: .text 13,13,"esc cancels after the current transfer",0
ed_progress_lo: .byte <ed_opening,<ed_saving,<ed_verifying
ed_progress_hi: .byte >ed_opening,>ed_saving,>ed_verifying
ed_io_pos: .fill 3,0
ed_io_size: .fill 3,0
ed_io_eof: .byte 0
ed_io_phase: .byte 0
ed_pending: .byte 128
ed_finish_status: .byte 0
ed_compare_left: .word 0
ed_nl_found: .byte 0
ed_nl_value: .byte 0
ed_nl_left: .word 0
; Saving never inserts document bytes. Its reopen comparison can reuse the
; insertion buffer while doc_read fills d_output and borrows N_BUFFER.
ed_verify_data = d_input
