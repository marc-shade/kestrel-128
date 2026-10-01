; Manual cartridge RTC editing. No host/system-clock or timezone changes.
; Firmware stores a two-digit year relative to 1980: accept 1980..2079.
; SET_TIME uses six binary bytes, with its wire year relative to 1900.
ut_open:
        jsr ug_cleanup
        bcs ug_cleanup_failed
        jsr ut_read
        lda uc_valid
        beq ut_default
        jsr ut_year
        bcs ut_default
        ldx #18
-       lda uc_data,x
        sta ut_edit,x
        dex
        bpl -
        bmi ut_begin
ut_default:
        ldx #18
-       lda ut_initial,x
        sta ut_edit,x
        dex
        bpl -
ut_begin:
        lda ui_selected
        sta ug_saved_focus
        lda #19
        sta ut_field
        lda #0
        sta ut_field+1
        sta ut_field+5
        sta ut_field+6
        sta ug_notice
        lda #2
        sta ug_mode
        lda #17
        sta ui_selected
        lda #$ff
        sta pm_arm
        jmp ut_redraw

ut_key:
        lda ug_key_value
        cmp #27
        beq ut_cancel
        cmp #9
        beq ut_tab
        cmp #13
        beq ut_enter
        ldx ui_selected
        cpx #17
        bne ut_handled
        sta N_UIKEY
        lda #<ut_field
        sta N_UIPTR
        lda #>ut_field
        sta N_UIPTR+1
        jsr N_FEDIT
        bcs ut_handled
        lda N_UIFLAGS
        beq ut_handled
        jmp ut_field_redraw
ut_tab:
        ldx ui_selected
        cpx #17
        bne +
        ldx #9
+       inx
        cpx #12
        bne +
        ldx #17
+       stx ui_selected
        jmp ut_redraw
ut_enter:
        ldx ui_selected
        cpx #17
        bne +
        jsr ut_validate
        bcs ut_invalid
        lda #10
        sta ui_selected
        jmp ut_redraw
+       jmp ug_activate
ut_point:
        lda pm_x+1
        bne ut_point_end
        lda pm_x
        sec
        sbc #16
        bcc ut_point_start
        lsr
        lsr
        lsr
        cmp ut_field
        bcc ut_point_caret
ut_point_end:
        lda ut_field
        jmp ut_point_caret
ut_point_start:
        lda #0
ut_point_caret:
        sta ut_field+1
        jmp ut_redraw
ut_cancel:
        jsr ut_read
        lda #2
        sta ug_notice
        jmp ug_leave_dialog
ut_invalid:
        lda #17
        sta ui_selected
        lda #13
        sta ug_notice
        jmp ut_redraw
; Keystrokes repaint only the date and caret rows; tabs/notices use the
; complete frame path. The shared presenter transfers their dirty VDC rows.
ut_field_redraw:
        jsr ug_collect_body
        lda ug_bitmap
        beq ut_field_console
        jsr ug_select_view
        jsr gfx_bind
        bcs ut_field_failed
        ldx #7
-       lda ut_field_bounds,x
        sta gfx_x0,x
        dex
        bpl -
        lda #0
        sta gfx_pen
        jsr gfx_rect
        bcs ut_field_failed
        ldx #19
-       lda ug_body+72,x
        sta gfx_text_buffer,x
        dex
        bpl -
        lda #20
        sta gfx_text_length
        lda #16
        ldy #72
        jsr ug_text
        bcs ut_field_failed
        ldx #19
-       lda ug_body+108,x
        sta gfx_text_buffer,x
        dex
        bpl -
        lda #20
        sta gfx_text_length
        lda #16
        ldy #80
        jsr ug_text
        bcs ut_field_failed
        jsr ug_vdc_sync
ut_field_console:
        jsr uc_draw_both
        jmp ug_handled
ut_field_failed:
        jsr ug_failed
        jmp ut_field_console
ut_redraw:
        jsr ug_update
        jsr uc_draw_both
ut_handled:
        jmp ug_handled

ut_confirm:
        jsr ut_validate
        bcs ut_invalid
        jsr ut_binary
        ldx #5
-       lda ut_actual,x
        sta ut_wanted,x
        sta N_BUFFER+2,x
        dex
        bpl -
        lda #1
        sta N_BUFFER
        lda #$27
        sta N_BUFFER+1
        lda #6
        sta N_FCOUNT
        lda #0
        sta N_FCOUNT+1
        sta ug_mode             ; consume confirmation before any I/O
        lda #$ff
        sta pm_arm
        jsr ud_packet
        bcs ut_unknown
        ; A success status or the SET reply is not evidence of persistence.
        ; Independently query and validate the observed date/time instead.
        jsr ut_read
        lda uc_valid
        beq ut_unknown
        jsr ut_year
        bcs ut_unknown
        jsr ut_binary
        lda #3                  ; exact time or at most two advancing seconds
        sta ut_tries
ut_compare:
        ldx #5
-       lda ut_wanted,x
        cmp ut_actual,x
        bne ut_different
        dex
        bpl -
        lda #16
        bne ut_result
ut_different:
        dec ut_tries
        beq ut_mismatch
        jsr ut_tick
        jmp ut_compare
ut_mismatch:
        lda #15
        bne ut_result
ut_unknown:
        lda #14
ut_result:
        sta ug_notice
        jmp ug_leave_dialog

ut_read:
        lda #0
        sta uc_valid
        lda #N_U_TIME
        jsr uc_query
        bcs +
        jsr uc_parse_time
+       rts
ut_validate:
        lda #0
        sta uc_valid
        sta uc_error
        sta uc_length+1
        lda ut_field
        sta uc_length
        ldx #18
-       lda ut_edit,x
        sta uc_data,x
        dex
        bpl -
        jsr uc_parse_time
        lda uc_valid
        beq ut_bad
        ; Retain the requested month's actual length for readback rollover.
        lda uc_days
        sta ut_days
ut_year:
        lda uc_data
        cmp #$31
        bne +
        lda uc_data+1
        cmp #$39
        bne ut_bad
        ldx #2
        jsr uc_pair
        cmp #80
        bcc ut_bad
        clc
        rts
+       cmp #$32
        bne ut_bad
        lda uc_data+1
        cmp #$30
        bne ut_bad
        ldx #2
        jsr uc_pair
        cmp #80
        rts
ut_bad:
        sec
        rts

ut_binary:
        ldy #5
-       ldx ut_offsets,y
        jsr uc_pair
        sta ut_actual,y
        dey
        bpl -
        lda uc_data
        cmp #$32
        bne +
        lda ut_actual
        clc
        adc #100
        sta ut_actual
+       rts
ut_tick:
        ldx #5
-       inc ut_wanted,x
        lda ut_wanted,x
        cmp ut_limits-3,x
        bcc ut_tick_done
        lda #0
        sta ut_wanted,x
        dex
        cpx #3
        bcs -
        inc ut_wanted+2
        lda ut_wanted+2
        cmp ut_days
        bcc ut_tick_done
        beq ut_tick_done
        lda #1
        sta ut_wanted+2
        inc ut_wanted+1
        lda ut_wanted+1
        cmp #13
        bcc ut_tick_done
        lda #1
        sta ut_wanted+1
        inc ut_wanted
ut_tick_done:
        rts

ut_body:
        lda #<ut_format
        ldx #>ut_format
        jsr uc_puts
        lda #<ut_edit
        ldx #>ut_edit
        jsr uc_text_source
        lda ut_field
        sta uc_text_left
        lda #19
        sta uc_text_limit
        jsr uc_text
        lda ui_selected
        cmp #17
        bne ut_body_done
        lda ut_field+1
        sta ut_at
-       lda ut_at
        beq +
        lda #32
        jsr uc_emit
        dec ut_at
        jmp -
+       lda #$5e
        jsr uc_emit
        jsr uc_newline
ut_body_done:
        rts

ut_field_bounds: .word 16,72,176,88
ut_initial: .text "2000/01/01 00:00:00"
ut_format: .text "yyyy/mm/dd hh:mm:ss  (1980-2079)",13,13,0
ut_heading: .text "ultimate ii+",13,13,"set cartridge clock",13,13,0
ut_help: .text "tab choose  enter applies",13,"esc cancels  ctrl-u clears field",13,0
ut_field: .byte 19,0,19
        .word ut_edit
        .byte 0,0,0
ut_edit: .fill 20,0             ; the field service also writes its NUL terminator
ut_offsets: .byte 2,5,8,11,14,17
ut_limits: .byte 24,60,60
ut_actual: .fill 6,0
ut_wanted: .fill 6,0
ut_tries: .byte 0
ut_days: .byte 0
ut_at: .byte 0
