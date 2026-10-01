; Shared complete-screen rendering for the VIC and VDC native consoles.
b_draw:
.if B_GUI
        lda fg_searching         ; the resident search modal owns presentation
        beq +
        rts
+
.endif
.if FD_GUI
        jsr pg_draw
.endif
.if B_GUI
        jsr fg_browser_draw
.endif
        lda #0
.if B_GUI
        ora fg_bitmap
.endif
.if FD_GUI
        ora pg_bitmap
.endif
        sta b_screen
b_draw_screen:
.if FD_VDC
        lda b_screen
        beq +
        lda FD_VDC_PHASE
        bne b_screen_done
+
.endif
        lda $d7
        rol
        lda #0
        rol
        cmp b_screen
        beq b_screen_selected
        jsr $ff5f
b_screen_selected:
        lda #$93
        jsr b_usb_chrout
.if !FD_EMBEDDED
        lda b_preview
        beq b_draw_list
        jsr b_view_draw
        jmp b_screen_done
b_draw_list:
.endif
        jsr b_list_draw
b_screen_done:
        inc b_screen
        lda b_screen
        cmp #2
        bne b_draw_screen
.if B_GUI
        jmp fg_focus_footer
.endif
        rts
b_list_draw:
        lda N_BROWSERFMT
        cmp #3
        bne +
        jmp bu_draw
+
        lda #<b_title
        ldx #>b_title
        jsr b_puts
        lda N_BROWSERDEV
        ldx #0
        jsr b_number
        lda #<b_format_text
        ldx #>b_format_text
        jsr b_puts
        ldx N_BROWSERFMT
        lda b_formats_lo,x
        pha
        lda b_formats_hi,x
        tax
        pla
        jsr b_puts
        lda #<b_count_text
        ldx #>b_count_text
        jsr b_puts
        lda b_total
        ldx b_total+1
        jsr b_number
        lda #<b_columns
        ldx #>b_columns
        jsr b_puts
        lda b_busy
        beq b_list_rows
        lda #<b_loading
        ldx #>b_loading
        jmp b_puts
b_list_rows:
        lda b_selected
        and #$f8
        sta b_index
        lda b_selected+1
        sta b_index+1
        lda #0
        sta b_row
b_list_row:
        lda b_index
        cmp b_total
        lda b_index+1
        sbc b_total+1
        bcs b_row_empty
        jsr b_read_record
        lda b_index
        cmp b_selected
        bne b_row_unselected
        lda b_index+1
        cmp b_selected+1
        bne b_row_unselected
        lda #$3e
        bne b_row_marker
b_row_unselected:
        lda #$20
b_row_marker:
        jsr b_usb_chrout
        jsr b_print_name
        lda #$20
        jsr b_usb_chrout
        jsr b_print_type
        lda #$20
        ldx b_record+1
        bmi b_row_closed
        lda #$2a
b_row_closed:
        jsr b_usb_chrout
        lda b_record+1
        and #$40
        beq b_row_unlocked
        lda #$3c
        bne b_row_lock
b_row_unlocked:
        lda #$20
b_row_lock:
        jsr b_usb_chrout
        lda #$20
        jsr b_usb_chrout
        lda b_record+18
        ldx b_record+19
        jsr b_number
        jmp b_row_next
b_row_empty:
        lda b_total
        ora b_total+1
        ora b_row
        bne b_row_next
        lda #<b_empty
        ldx #>b_empty
        jsr b_puts
b_row_next:
        lda #13
        jsr b_usb_chrout
        inc b_index
        bne b_row_advance
        inc b_index+1
b_row_advance:
        inc b_row
        lda b_row
        cmp #8
        bne b_list_row
        lda #<b_help
        ldx #>b_help
        jsr b_puts
        jsr b_show_status
        lda b_prompt
        beq b_list_done
        lda #<b_device_question
        ldx #>b_device_question
        jsr b_puts
        jsr b_device_pointer
        lda #5
        sta N_UIWIDTH
.if B_GUI
        jsr fg_field_output
.else
 .if FD_GUI
        jsr pg_field_output
 .else
        jsr N_FDRAW
 .endif
.endif
b_list_done:
        rts
b_print_name:
        lda #0
        sta b_char
b_name_show:
        ldx b_char
        lda b_record+2,x
        cmp #$a0
        bne b_name_visible
        lda #$20
b_name_visible:
        jsr b_safe_character
        jsr b_usb_chrout
        inc b_char
        lda b_char
        cmp #16
        bne b_name_show
        rts
.if FD_EMBEDDED
b_safe_character = FD_SAFE_CHARACTER
.else
b_safe_character:
        cmp #$20
        bcc b_character_dot
        cmp #$7f
        bcc b_character_ready
b_character_dot:
        lda #$2e
b_character_ready:
        rts
.endif
b_print_type:
.if !FD_EMBEDDED
        lda b_record+20
        beq b_disk_type
        lda #<b_type_app
        ldx #>b_type_app
        jmp b_puts
b_disk_type:
.endif
        ldx b_record
        lda b_types_lo,x
        pha
        lda b_types_hi,x
        tax
        pla
        jmp b_puts
b_show_status:
        lda b_error
        bne b_have_status
        lda b_launch_error
        beq b_status_done
b_have_status:
        sta b_status_code
        ldx #b_status_end-b_status_codes-1
b_status_find:
        cmp b_status_codes,x
        beq b_status_found
        dex
        bpl b_status_find
        lda #<b_unknown_error
        ldx #>b_unknown_error
        jsr b_puts
        lda b_status_code
        jmp b_hex
b_status_found:
        lda b_status_lo,x
        pha
        lda b_status_hi,x
        tax
        pla
        jmp b_puts
b_status_done:
        rts
b_puts:
        sta b_text_read+1
        stx b_text_read+2
b_text_read:
        lda $ffff
        beq b_text_done
        jsr b_usb_chrout
        inc b_text_read+1
        bne b_text_read
        inc b_text_read+2
        jmp b_text_read
b_text_done:
        rts
b_hex:
        pha
        lsr
        lsr
        lsr
        lsr
        jsr b_nibble
        pla
        and #15
b_nibble:
        cmp #10
        bcc b_hex_digit
        clc
        adc #7
b_hex_digit:
        clc
        adc #$30
.if B_GUI || FD_GUI
        jmp b_usb_chrout
.else
        jmp $ffd2
.endif
b_number:
        sta b_num
        stx b_num+1
        lda #0
        sta b_num_pos
        sta b_num_started
b_number_digit:
        lda #0
        sta b_digit
b_number_subtract:
        ldx b_num_pos
        lda b_num
        cmp b_powers_lo,x
        lda b_num+1
        sbc b_powers_hi,x
        bcc b_number_emit
        sec
        lda b_num
        sbc b_powers_lo,x
        sta b_num
        lda b_num+1
        sbc b_powers_hi,x
        sta b_num+1
        inc b_digit
        bne b_number_subtract
b_number_emit:
        lda b_digit
        ora b_num_started
        bne b_number_nonzero
        ldx b_num_pos
        cpx #4
        bne b_number_next
b_number_nonzero:
        lda #1
        sta b_num_started
        lda b_digit
        clc
        adc #$30
        jsr b_usb_chrout
b_number_next:
        inc b_num_pos
        lda b_num_pos
        cmp #5
        bne b_number_digit
        rts

b_title:
.if FD_EMBEDDED
        .text "kestrel choose a file",13,13,"device: ",0
.else
        .text "kestrel files and apps",13,13,"device: ",0
.endif
b_format_text: .text "   format: ",0
b_count_text: .text 13,"files: ",0
b_columns: .text 13," name             type   blocks",13,0
b_loading: .text "reading directory...",0
b_empty: .text "no files",0
b_help:
.if FD_EMBEDDED
        .text 13,"up/down select  n/b page",13
.if FD_GUI
b_focus_help: .text "tab controls  enter activate",13
.else
        .text "enter choose  r refresh",13
.endif
        .text "d device  f format  esc cancel",13
        .text "s use device for save as",13,13,0
.else
        .text 13,"up/down select  n/b page  a next app",13
        .text "enter open  i inspect  r refresh",13
.if B_COPY
        .text "d device  f format  esc desktop",13
        .text "c copy  * unclosed  < locked",13,13,0
.else
        .text "d device  f format  esc workspace",13
        .text "* unclosed  < locked  l usb app",13,13,0
.endif
.endif
b_device_question: .text 13,"device (8-30): ",0
b_format64: .text "d64",0
b_format71: .text "d71",0
b_format81: .text "d81",0
b_formats_lo: .byte <b_format64,<b_format71,<b_format81
b_formats_hi: .byte >b_format64,>b_format71,>b_format81
b_type_del: .text "del",0
b_type_seq: .text "seq",0
b_type_prg: .text "prg",0
b_type_usr: .text "usr",0
b_type_rel: .text "rel",0
b_type_cbm: .text "cbm",0
b_type_unknown: .text "???",0
.if !FD_GUI
b_type_app: .text "app",0
.endif
b_types_lo: .byte <b_type_del,<b_type_seq,<b_type_prg,<b_type_usr,<b_type_rel,<b_type_cbm,<b_type_unknown,<b_type_unknown
b_types_hi: .byte >b_type_del,>b_type_seq,>b_type_prg,>b_type_usr,>b_type_rel,>b_type_cbm,>b_type_unknown,>b_type_unknown
b_bad_name: .text "invalid name or device",0
b_no_handle: .text "no file handle available",0
b_bad_directory: .text "invalid disk directory",0
.if !FD_GUI
b_bad_image: .text "invalid application image",0
.endif
b_disk_error: .text "disk i/o error",0
.if !FD_GUI
b_short_image: .text "application file is incomplete",0
b_long_image: .text "application file has extra data",0
b_checksum_error: .text "application checksum failed",0
.endif
b_channels_error: .text "disk channel is in use",0
.if !FD_GUI
b_no_apps_text: .text "no native applications found",0
.endif
b_unsupported_text: .text "file type cannot be opened",0
b_unclosed_text: .text "file is not closed",0
b_unknown_error: .text "error ",0
.if FD_GUI
b_status_codes: .byte 1,3,9,$11,$15,$21,$22,$23
b_status_end:
b_status_lo: .byte <b_bad_name,<b_no_handle,<b_bad_directory,<b_disk_error,<b_channels_error,<b_unsupported_text,<b_unclosed_text,<bu_long_path
b_status_hi: .byte >b_bad_name,>b_no_handle,>b_bad_directory,>b_disk_error,>b_channels_error,>b_unsupported_text,>b_unclosed_text,>bu_long_path
.else
b_status_codes: .byte 1,3,9,$10,$11,$12,$13,$14,$15,$20,$21,$22
b_status_end:
b_status_lo: .byte <b_bad_name,<b_no_handle,<b_bad_directory,<b_bad_image,<b_disk_error,<b_short_image,<b_long_image,<b_checksum_error,<b_channels_error,<b_no_apps_text,<b_unsupported_text,<b_unclosed_text
b_status_hi: .byte >b_bad_name,>b_no_handle,>b_bad_directory,>b_bad_image,>b_disk_error,>b_short_image,>b_long_image,>b_checksum_error,>b_channels_error,>b_no_apps_text,>b_unsupported_text,>b_unclosed_text
.endif
b_powers_lo: .byte <10000,<1000,<100,<10,<1
b_powers_hi: .byte >10000,>1000,>100,>10,>1
b_screen: .byte 0
b_row: .byte 0
b_char: .byte 0
b_status_code: .byte 0
b_num: .word 0
b_num_pos: .byte 0
b_num_started: .byte 0
b_digit: .byte 0
