ug_drive_body:
        lda uc_error
        bne ug_drive_error
        lda #<ug_inventory_header
        ldx #>ug_inventory_header
        jsr uc_puts
        lda ud_partial
        beq +
        lda #<ug_partial
        ldx #>ug_partial
        jsr uc_puts
        jmp ug_drive_rows
+       jsr uc_newline
ug_drive_rows:
        lda #0
        sta ug_drive_row
        sta ug_drive_record
-       lda ug_drive_row
        cmp ud_count
        beq ug_console_done
        lda #32
        ldx ug_drive_row
        cpx ud_selected
        bne +
        lda #$3e
+       jsr uc_emit
        lda #32
        jsr uc_emit
        lda ug_drive_row
        clc
        adc #1
        jsr uc_decimal
        lda #<ug_three_spaces
        ldx #>ug_three_spaces
        jsr uc_puts
        ldx ug_drive_record
        lda ud_records,x
        jsr uc_hex
        lda #<ug_five_spaces
        ldx #>ug_five_spaces
        jsr uc_puts
        ldx ug_drive_record
        lda ud_records+1,x
        jsr uc_decimal
        lda #<ug_five_spaces
        ldx #>ug_five_spaces
        jsr uc_puts
        ldx ug_drive_record
        lda ud_records+2,x
        beq +
        lda #<ug_on
        ldx #>ug_on
        bne ug_console_power
+       lda #<ug_off
        ldx #>ug_off
ug_console_power:
        jsr uc_puts
        inc ug_drive_row
        lda ug_drive_record
        clc
        adc #3
        sta ug_drive_record
        jmp -
ug_drive_error:
        jmp uc_show_error
ug_console_done:
        rts

ug_confirm_body:
        lda ud_pending
        cmp #$23
        bne +
        lda #<ug_mount_title
        ldx #>ug_mount_title
        bne ug_confirm_title
+       lda #<ug_eject_title
        ldx #>ug_eject_title
ug_confirm_title:
        jsr uc_puts
        lda ud_id
        jsr uc_decimal
        jsr uc_newline
        jsr uc_newline
        lda ud_pending
        cmp #$23
        bne ug_console_done
        lda #<ud_name
        ldx #>ud_name
        jsr uc_text_source
        lda ud_name_length
        sta uc_text_left
        lda #255
        sta uc_text_limit
        jmp uc_text

ug_console_footer:
        jsr uc_newline
        lda ug_mode
        bne ug_modal_footer
        lda uc_page
        cmp #1
        bne +
        lda #<ug_drive_help
        ldx #>ug_drive_help
        jsr uc_puts
+       lda #<uc_footer
        ldx #>uc_footer
        jsr uc_puts
        jmp ug_footer_focus
ug_modal_footer:
        cmp #2
        bne +
        lda #<ut_help
        ldx #>ut_help
        jsr uc_puts
        jmp ug_footer_focus
+       lda #<ug_confirm_help
        ldx #>ug_confirm_help
        jsr uc_puts
ug_footer_focus:
        lda #<ug_focus_title
        ldx #>ug_focus_title
        jsr uc_puts
        ldx ui_selected
        cpx #16
        bcs +
        cpx #12
        bcc +
        lda #<ug_drive_label
        ldx #>ug_drive_label
        jsr uc_puts
        lda ud_selected
        clc
        adc #1
        jsr uc_decimal
        jmp ug_footer_notice
+       lda ug_labels_lo,x
        pha
        lda ug_labels_hi,x
        tax
        pla
        jsr ug_ascii_puts
ug_footer_notice:
        jsr uc_newline
        ldx ug_notice
        lda ug_notices_lo,x
        pha
        lda ug_notices_hi,x
        tax
        pla
        jsr ug_ascii_puts
        jmp uc_newline
ug_ascii_puts:
        sta ug_console_read+1
        stx ug_console_read+2
ug_console_read:
        lda $ffff
        beq ug_console_done
        jsr uc_ascii
        inc ug_console_read+1
        bne ug_console_read
        inc ug_console_read+2
        bne ug_console_read

ug_inventory_header: .text "slot type   iec   power",13,0
ug_partial: .text "partial: a/b checked; others unknown",13,0
ug_three_spaces: .text "   ",0
ug_five_spaces: .text "     ",0
ug_on: .text "on",13,13,0
ug_off: .text "off",13,13,0
ug_mount_title: .text "mount image on iec ",0
ug_eject_title: .text "eject image from iec ",0
ug_confirm_heading: .text "ultimate ii+",13,13,"change drive media?",13,13,0
ug_drive_help: .text "up/down select  m mount  e eject",13,0
ug_confirm_help: .text "tab choose  enter confirms",13,"esc cancels",13,0
ug_focus_title: .text "focus: ",0
ug_drive_label: .text "drive ",0
ug_drive_row: .byte 0
ug_drive_record: .byte 0
