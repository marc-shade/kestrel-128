; The VDC mirrors controls/status. If VIC presentation is unavailable, both
; text consoles retain file operations and coordinate-based keyboard tools.
pa_console:
        jsr pa_vdc_sync
        lda pa_bitmap
        sta pa_screen
pa_console_next:
        lda pa_screen
        beq +
        lda vd_phase
        beq +
        rts
+       lda $d7
        rol
        lda #0
        rol
        cmp pa_screen
        beq +
        jsr $ff5f
+       lda #$93
        jsr $ffd2
        lda #<pa_console_title
        ldx #>pa_console_title
        jsr pa_puts
        lda pa_mode
        beq pa_console_main
        cmp #1
        beq pa_console_confirm
        lda #<pa_console_save
        ldx #>pa_console_save
        jsr pa_puts
        jsr pa_make_destination
        jsr pa_put_buffer
        jsr pa_newline
        jsr pa_newline
        lda #<pa_field
        sta N_UIPTR
        lda #>pa_field
        sta N_UIPTR+1
        lda #34
        sta N_UIWIDTH
        jsr N_FDRAW
        lda #<pa_console_save_help
        ldx #>pa_console_save_help
        jsr pa_puts
        jmp pa_console_focus
pa_console_confirm:
        lda #<pa_console_unsaved
        ldx #>pa_console_unsaved
        jsr pa_puts
        lda #<pa_close_question
        ldx #>pa_close_question
        ldy pa_action
        cpy #2
        bne +
        lda #<pa_open_question
        ldx #>pa_open_question
+       jsr pa_put_ascii
        jsr pa_newline
        jsr pa_newline
        lda #<pa_console_confirm_help
        ldx #>pa_console_confirm_help
        jsr pa_puts
        jmp pa_console_focus
pa_console_main:
        jsr pa_make_status
        jsr pa_put_buffer
        lda #<pa_console_help
        ldx #>pa_console_help
        jsr pa_puts
        lda pa_bitmap
        bne pa_console_focus
        lda #<pa_console_no_bitmap
        ldx #>pa_console_no_bitmap
        jsr pa_puts
pa_console_focus:
        lda #<pa_console_focus_label
        ldx #>pa_console_focus_label
        jsr pa_puts
        ldy ui_selected
        lda pa_focus_lo,y
        ldx pa_focus_hi,y
        jsr pa_put_ascii
pa_console_status:
        jsr pa_newline
        jsr pa_newline
        jsr pa_message_pointer
        jsr pa_put_ascii
        inc pa_screen
        lda pa_screen
        cmp #2
        bne pa_console_next
        rts
pa_put_ascii:
        jsr pa_text_copy
pa_put_buffer:
        lda #0
        sta pa_text_index
-       ldx pa_text_index
        cpx gfx_text_length
        beq pa_console_done
        lda gfx_text_buffer,x
        cmp #$61
        bcc +
        cmp #$7b
        bcs +
        and #$df
+       jsr $ffd2
        inc pa_text_index
        bne -
pa_console_done:
        rts
pa_newline:
        lda #13
        jmp $ffd2
pa_puts:
        sta pa_console_read+1
        stx pa_console_read+2
pa_console_read:
        lda $ffff
        beq pa_console_done
        jsr $ffd2
        inc pa_console_read+1
        bne pa_console_read
        inc pa_console_read+2
        jmp pa_console_read
pa_screen: .byte 0
pa_text_index: .byte 0
pa_console_title: .text "paint - 320 x 200 hires",13,13,0
pa_console_help: .text 13,13,"p pencil e eraser u undo c clear",13
        .text "s save o open esc close",13
        .text "arrows move space draw +/- ink",13
        .text "tab controls enter activate",13,0
pa_console_no_bitmap: .text 13,"bitmap display unavailable",13,0
pa_console_focus_label: .text 13,"focus: ",0
pa_console_unsaved: .text "unsaved picture",13,13,0
pa_console_confirm_help: .text "tab/arrows choose enter confirms",13,"esc keeps picture",13,0
pa_console_save: .text "save as (new file)",13,0
pa_console_save_help: .text 13,13,"tab browse enter save esc cancel",13,"ctrl-u clears name",13,0
