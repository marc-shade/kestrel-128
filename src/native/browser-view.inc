; Forward binary inspection, 128 bytes per page with a full 32-bit offset.
b_view_open:
        lda #0
        sta b_error
        sta b_launch_error
        jsr b_open_record
        bcs b_view_failed
        lda #1
        sta b_preview
        lda #0
        sta b_eof
        ldx #3
b_view_zero_offset:
        sta b_next_offset,x
        dex
        bpl b_view_zero_offset
        jsr b_view_read
.if B_GUI
        lda fl_auto
        beq +
        ; Enter/Inspect set this intent on every initial Open. Next-page
        ; reads never pass here, so no second classification can occur.
        jmp fl_associate
+
.endif
        jmp b_redraw
b_view_failed:
        sta b_error
        jmp b_redraw
b_preview_key:
        cmp #27
        beq b_view_back
        cmp #13
        beq b_view_next
        and #$df
        cmp #$4e
        bne b_loop
b_view_next:
        lda b_eof
        bne b_loop
        lda b_open
        beq b_loop
        jsr b_view_read
        jmp b_redraw
b_view_back:
        jsr b_close_file
        lda #0
        sta b_preview
        jmp b_redraw
b_view_read:
        ldx #3
b_view_copy_offset:
        lda b_next_offset,x
        sta b_offset,x
        dex
        bpl b_view_copy_offset
        lda #128
        sta N_FCOUNT
        lda #0
        sta N_FCOUNT+1
        jsr N_FREAD
        sta b_error
        lda N_FACTUAL
        sta b_view_count
        lda N_FEOF
        sta b_eof
        ldx #3
b_view_save_offset:
        lda N_FPOSITION,x
        sta b_next_offset,x
        dex
        bpl b_view_save_offset
        ldx #0
b_view_copy:
        cpx b_view_count
        beq b_view_copied
        lda N_BUFFER,x
        sta b_view_data,x
        inx
        bne b_view_copy
b_view_copied:
        lda b_error
        beq b_view_clean
        lda #1
        sta b_eof
b_view_clean:
        lda b_eof
        beq b_view_read_done
        jsr b_close_file
b_view_read_done:
        rts
b_view_draw:
        lda #<b_file_title
        ldx #>b_file_title
        jsr b_puts
        jsr b_print_name
        lda #<b_offset_title
        ldx #>b_offset_title
        jsr b_puts
        lda #3
        sta b_char
b_view_print_offset:
        ldx b_char
        lda b_offset,x
        jsr b_hex
        dec b_char
        bpl b_view_print_offset
        lda #<b_bytes_title
        ldx #>b_bytes_title
        jsr b_puts
        lda b_view_count
        ldx #0
        jsr b_number
        lda #13
        jsr b_usb_chrout
        lda #13
        jsr b_usb_chrout
        lda #0
        sta b_view_line
b_view_draw_line:
        lda b_view_line
        cmp b_view_count
        bcs b_view_blank_line
        clc
        adc b_offset
        sta b_line_offset
        lda b_offset+1
        adc #0
        jsr b_hex
        lda b_line_offset
        jsr b_hex
        lda #$20
        jsr b_usb_chrout
        lda #0
        sta b_view_column
b_view_hex_byte:
        clc
        lda b_view_line
        adc b_view_column
        cmp b_view_count
        bcs b_view_hex_blank
        tax
        lda b_view_data,x
        jsr b_hex
        jmp b_view_hex_space
b_view_hex_blank:
        lda #$20
        jsr b_usb_chrout
        lda #$20
        jsr b_usb_chrout
b_view_hex_space:
        lda #$20
        jsr b_usb_chrout
        inc b_view_column
        lda b_view_column
        cmp #8
        bne b_view_hex_byte
        lda #$20
        jsr b_usb_chrout
        lda #0
        sta b_view_column
b_view_ascii_byte:
        clc
        lda b_view_line
        adc b_view_column
        cmp b_view_count
        bcs b_view_ascii_blank
        tax
        lda b_view_data,x
        jsr b_safe_character
        jmp b_view_ascii_print
b_view_ascii_blank:
        lda #$20
b_view_ascii_print:
        jsr b_usb_chrout
        inc b_view_column
        lda b_view_column
        cmp #8
        bne b_view_ascii_byte
b_view_blank_line:
        lda #13
        jsr b_usb_chrout
        clc
        lda b_view_line
        adc #8
        sta b_view_line
        cmp #128
        bne b_view_draw_line
        lda #<b_view_help
        ldx #>b_view_help
        jsr b_puts
        lda b_eof
        beq b_view_status
        lda b_error
        bne b_view_status
        lda #<b_view_end
        ldx #>b_view_end
        jsr b_puts
b_view_status:
        jmp b_show_status

b_file_title: .text "file: ",0
b_offset_title: .text 13,"offset: ",0
b_bytes_title: .text "  bytes: ",0
b_view_help: .text 13,"enter/n next page  esc file list",13,0
b_view_end: .text "end of file",13,0
b_preview: .byte 0
b_eof: .byte 0
b_view_count: .byte 0
b_offset: .fill 4,0
b_next_offset: .fill 4,0
b_view_line: .byte 0
b_view_column: .byte 0
b_line_offset: .byte 0
.weak
B_VIEW_STORAGE=0
.endweak
.if B_VIEW_STORAGE
b_view_data=B_VIEW_STORAGE
.else
b_view_data: .fill 128,0
.endif
