pa_request_close:
        lda #1
        bne pa_dirty_action
pa_open_start:
        lda #2
pa_dirty_action:
        sta pa_action
        lda pd_dirty
        bne pa_confirm_start
        lda pa_action
        cmp #1
        beq pa_exit
        jmp pa_open_picker
pa_confirm_start:
        lda #1
        sta pa_mode
        lda #25
        bne pa_dialog_controls
pa_save_start:
        jsr pa_cleanup
        bcs pa_cleanup_error
        jsr pa_field_init
        bcs pa_field_error
        lda #2
        sta pa_mode
        lda #24
pa_dialog_controls:
        sta ui_selected
        lda #24
        sta ui_first
        lda #26
        sta ui_limit
        lda #0
        sta pa_segment
        sta pd_stroke
        sta pa_status
        lda #$ff
        sta pm_arm
        lda pa_bitmap
        beq +
        lda pm_seen
        bne +
        lda #0
        sta $d015
+       jmp pa_redraw
pa_confirm_key:
        cmp #27
        beq pa_cancel_dialog
        cmp #13
        beq pa_dialog_activate
        cmp #9
        beq pa_dialog_toggle
        cmp #$11
        beq pa_dialog_toggle
        cmp #$91
        beq pa_dialog_toggle
        cmp #$1d
        beq pa_dialog_toggle
        cmp #$9d
        beq pa_dialog_toggle
        and #$df
        cmp #$4b
        beq pa_cancel_dialog
        cmp #$44
        beq pa_dialog_accept
        cmp #$4f
        bne pa_dialog_done
        ldx pa_action
        cpx #2
        bne pa_dialog_done
pa_dialog_accept:
        lda #24
        sta ui_selected
        jmp pa_dialog_activate
pa_dialog_toggle:
        lda ui_selected
        eor #1
        tax
        jsr pa_choose_focus
        jmp pa_console
pa_dialog_activate:
        lda ui_selected
        cmp #25
        beq pa_cancel_dialog
        lda pa_mode
        cmp #2
        beq pa_save_execute
        lda pa_action
        cmp #1
        beq pa_exit
        jsr pa_normal_controls
        jmp pa_open_picker
pa_cancel_dialog:
        jsr pa_normal_controls
        jmp pa_redraw
pa_dialog_done:
        rts
pa_save_key:
        cmp #27
        beq pa_cancel_dialog
        cmp #13
        beq pa_dialog_activate
        cmp #9
        beq pa_save_picker
        sta N_UIKEY
        jsr pa_field_edit
        bcs pa_field_error
        lda N_UIFLAGS
        beq pa_dialog_done
        ldx #24
        jsr pa_choose_focus
        lda pa_bitmap
        beq +
        jsr pa_update_field
        bcs pa_field_error
+       jmp pa_console
pa_field_error:
        sta pa_error
        lda #12
        jmp pa_result

pa_field_init:
        lda pf_length
        sta pa_field_length
        lda #16
        ldx #3
        ldy pf_format
        cpy #3
        bne +
        lda #255
        ldx #0
+       sta pa_field_max
        stx pa_field_filter
        lda #0
        sta N_UIKEY
        sta pa_field_view
pa_field_edit:
        lda #<pa_field
        sta N_UIPTR
        lda #>pa_field
        sta N_UIPTR+1
        jsr N_FEDIT
        bcs pa_dialog_done
        lda pa_field_length
        sta pf_length
        lda #0
        clc
        rts

pa_save_picker:
        lda #2
        bne pa_pick
pa_open_picker:
        lda #1
pa_pick:
        sta pa_picker_mode
        jsr pa_cleanup
        bcs pa_cleanup_error
        jsr pa_surface_close
        lda pa_picker_mode
        sta paint_picker.fd_mode
        lda pf_device
        sta paint_picker.fd_device
        lda pf_format
        sta paint_picker.fd_format
        lda pf_length
        sta paint_picker.fd_length
        jsr paint_picker.fd_run
        sta pa_picker_error
        lda #0
        rol
        sta pa_picker_failed
        jsr pa_cleanup
        bcs pa_pick_cleanup_error
        lda pa_picker_failed
        bne pa_picker_return
        lda paint_picker.fd_device
        sta pf_device
        lda paint_picker.fd_format
        sta pf_format
        lda paint_picker.fd_length
        sta pf_length
        lda paint_picker.fd_type
        sta pf_type
        jsr pa_field_init
        bcc pa_picker_return
pa_pick_cleanup_error:
        sta pa_picker_error
        lda #1
        sta pa_picker_failed
pa_picker_return:
        jsr pa_view_open
        lda pa_picker_failed
        beq pa_picked
        lda pa_picker_error
        sta pa_error
        beq +
        lda #12
        sta pa_status
        bne pa_picker_redraw
+       lda #3
        sta pa_status
pa_picker_redraw:
        jmp pa_redraw
pa_picked:
        lda pa_picker_mode
        cmp #2
        beq pa_picker_redraw
pa_load_document:
        lda #11
        sta pa_status
        jsr pa_redraw
        jsr pf_load
        bcs pa_file_error
        lda #2
        bne pa_result
pa_save_execute:
        lda pf_length
        beq pa_dialog_done
        jsr pa_normal_controls
        lda #2
        sta pa_picker_mode
        lda #10
        sta pa_status
        jsr pa_redraw
        lda #0
        sta pf_type
        jsr pf_save
        bcs pa_file_error
        lda #1
pa_result:
        sta pa_status
        jmp pa_redraw
pa_file_error:
        sta pa_error
        cmp #PF_ERR_CANCEL
        bne +
        lda #3
        bne pa_result
+       cmp #PF_ERR_FORMAT
        bne +
        lda #5
        bne pa_result
+       cmp #PF_ERR_CHECKSUM
        bne +
        lda #6
        bne pa_result
+       cmp #PF_ERR_MISMATCH
        bne +
        lda #7
        bne pa_result
+       lda pf_dos
        cmp #63
        bne +
        lda #4
        bne pa_result
+       lda #8
        bne pa_result
pa_cleanup_error:
        sta pa_error
        lda #13
        bne pa_result
pa_exit:
        jsr pa_cleanup
        bcs pa_cleanup_error
        jsr pa_view_close
        bcc +
        jmp pa_console
+       jsr pa_keys_restore
        lda #0
        jmp N_EXIT

; The picker can retain a failed close/cache free. Retry those exact resources
; before a new operation or app exit; never replay an earlier write.
pa_cleanup:
        jsr pf_cleanup
        bcs pa_cleanup_done
        jsr paint_picker.fd_close_cursors
        bcs pa_cleanup_done
        lda #0
        sta pa_cache_at
-       ldx pa_cache_at
        lda paint_picker.b_cache,x
        beq +
        jsr paint_picker.fd_cache_handle
        lda N_CURRENT
        sta N_OWNER
        jsr N_FREE
        bcs pa_cleanup_done
        ldx pa_cache_at
        lda #0
        sta paint_picker.b_cache,x
+       lda pa_cache_at
        clc
        adc #4
        sta pa_cache_at
        cmp #40
        bne -
        lda #0
        clc
pa_cleanup_done:
        rts

pa_keys_install=nk_install
pa_keys_restore=nk_close
pa_safe_character:
        cmp #32
        bcc +
        cmp #127
        bcc pa_cleanup_done
+       lda #46
        rts
pa_action: .byte 0
pa_picker_mode: .byte 0
pa_picker_error: .byte 0
pa_picker_failed: .byte 0
pa_cache_at: .byte 0
pa_field:
pa_field_length: .byte 0
pa_field_caret: .byte 0
pa_field_max: .byte 16
        .word pf_name
        .byte 0,0
pa_field_filter: .byte 3
pa_field_view: .byte 0
pa_saved_keys=nk_saved_keys
pa_keys_callback=nk_saved_callback
pa_key_filter_image=nk_filter_image
