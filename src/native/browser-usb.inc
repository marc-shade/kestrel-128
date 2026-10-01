; Checked application launch by absolute Ultimate path. This field preserves
; the IEC browser's cache/selection; directory navigation is a separate service.
.if !FD_GUI
b_usb_begin:
        lda #2
        sta b_prompt
        lda #0
        sta b_usb_error
        sta N_UIKEY
        jsr b_usb_edit
        bcs b_usb_input_error
        jmp b_usb_refresh
.endif
b_usb_key:
        cmp #27
        beq b_usb_cancel
        cmp #13
        beq b_usb_enter
        cmp #9
        beq b_usb_context
.if B_GUI
        cmp #$85
        beq b_usb_context
.endif
        sta N_UIKEY
        jsr b_usb_edit
        bcs b_usb_input_error
        lda N_UIFLAGS
        beq b_loop
        jmp b_usb_changed
b_usb_context:
        lda b_usb_device
        eor #3
        sta b_usb_device
        jmp b_usb_changed
b_usb_changed:
        lda #0
        sta b_usb_error
b_usb_refresh:
        jsr b_usb_draw
        jmp b_loop
b_usb_input_error:
        lda #2
        sta b_usb_error
        bne b_usb_refresh
b_usb_edit:
        jsr b_usb_pointer
        jmp N_FEDIT
b_usb_pointer:
        lda #<b_usb_state
        sta N_UIPTR
        lda #>b_usb_state
        sta N_UIPTR+1
        rts
b_usb_cancel:
        lda #0
        sta b_prompt
        beq b_usb_refresh
b_usb_enter:
        lda b_usb_length
        beq b_usb_invalid
        lda b_usb_path
        cmp #$2f
        beq b_usb_launch
b_usb_invalid:
        lda #1
        sta b_usb_error
        bne b_usb_refresh
b_usb_launch:
        lda b_prompt
        cmp #3
        bne +
        jmp bu_prompt_directory
+
.if !FD_EMBEDDED
 .if B_GUI
        jsr fg_exit
        bcs b_loop
 .endif
        lda b_usb_length
        sta N_NAMELEN
        lda b_usb_device
        sta N_DEVICE
        lda #3
        sta N_APPFORMAT
        ldx #0
b_usb_copy:
        lda b_usb_path,x
        sta N_UPATH,x
        inx
        cpx b_usb_length
        bne b_usb_copy
        jmp N_REPLACE
.else
        jmp b_loop
.endif

; Only rows 20/21 change while this field is active. Each row leaves its last
; column blank, avoiding KERNAL linked-line wrapping on either display.
b_usb_draw:
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
b_usb_screen:
.if FD_VDC
        lda b_screen
        beq +
        lda FD_VDC_PHASE
        bne b_usb_screen_done
+
.endif
        lda $d7
        rol
        lda #0
        rol
        cmp b_screen
        beq +
        jsr $ff5f
+       lda #39
        ldx b_screen
        beq +
        lda #79
+       sta b_usb_width
        lda #20
        sta b_usb_row
b_usb_clear_row:
        ldx b_usb_row
        ldy #0
        clc
        jsr $fff0
        lda b_usb_width
        sta b_usb_blank
b_usb_clear:
        lda #32
        jsr b_usb_chrout
        dec b_usb_blank
        bne b_usb_clear
        inc b_usb_row
        lda b_usb_row
        cmp #22
        bne b_usb_clear_row
        lda b_prompt
        beq b_usb_screen_done
        ldx #20
        ldy #0
        clc
        jsr $fff0
        lda #<b_usb_label
        ldx #>b_usb_label
        jsr b_puts
        lda b_usb_device
        ora #$30
        jsr b_usb_chrout
        lda #$3a
        jsr b_usb_chrout
        lda #32
        jsr b_usb_chrout
        lda b_usb_width
        sec
        sbc #7                 ; 32 or 72 field cells, including edge markers
        sta N_UIWIDTH
        jsr b_usb_pointer
        jsr N_FDRAW
        bcc b_usb_controls
        lda #2
        sta b_usb_error
b_usb_controls:
        ldx #21
        ldy #0
        clc
        jsr $fff0
        lda #<b_usb_help
        ldx #>b_usb_help
        ldy b_prompt
        cpy #3
        bne +
        lda #<bu_path_help
        ldx #>bu_path_help
+
        ldy b_usb_error
        beq +
        lda #<b_usb_bad_path
        ldx #>b_usb_bad_path
+       cpy #2
        bne +
        lda #<b_usb_bad_input
        ldx #>b_usb_bad_input
+       jsr b_puts
b_usb_screen_done:
        inc b_screen
        lda b_screen
        cmp #2
        bne b_usb_screen
.if B_GUI
        jmp fg_focus_footer
.endif
        rts
b_usb_chrout:
.if FD_GUI
        sta pg_character
        lda pg_collect
        beq +
        lda pg_character
        jmp pg_emit
+       lda pg_character
.endif
.if B_GUI
        php
        pha
        lda fg_collect
        beq +
        pla
        plp
        jmp fv_emit
+       pla
        plp
.endif
        pha
        lda #0
        sta $f4                ; filenames cannot leave ROM quote mode active
        pla
        jmp $ffd2

b_usb_label: .text "usb",0
.if FD_GUI
b_usb_help=bu_path_help
.else
b_usb_help:
.if B_GUI
        .text "enter run f1 dos ctrl-u clr esc",0
.else
        .text "enter run tab dos ctrl-u clr esc",0
.endif
.endif
b_usb_bad_path: .text "absolute path required",0
b_usb_bad_input: .text "input unavailable; esc returns",0
b_usb_state:
b_usb_length: .byte 6
b_usb_cursor: .byte 6
        .byte 255
        .word b_usb_path
b_usb_views: .fill 2,0
        .byte 0
b_usb_device: .byte 1
b_usb_error: .byte 0
b_usb_width: .byte 0
b_usb_row: .byte 0
b_usb_blank: .byte 0
b_usb_path: .byte $2f,$55,$73,$62,$30,$2f
        .fill 250,0
