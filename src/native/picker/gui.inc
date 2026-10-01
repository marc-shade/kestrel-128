; Compact shared picker presentation. Directory and field semantics stay in
; file-browser; this renderer uses only the caller's owned VIC surface.
; N_BUFFER is borrowed for each glyph and restored, because Ultimate row
; formatting still consumes the raw filename from that transfer buffer.
pg_init:
        lda #4
        sta pg_focus
        lda #0
        sta pg_bitmap
        sta pg_collect
        sta pg_prompt
        sta pg_busy
pg_retry:
        lda #0
        sta pg_attempted
        rts
pg_close:
        jsr pgm_close
        jsr N_VCLOSE
        lda #0
        sta pg_bitmap
        rts
pg_surface:
        lda N_CURRENT
        sta N_OWNER
        ldx #3
-       lda FD_GUI_SURFACE,x
        sta N_HANDLE,x
        dex
        bpl -
        rts
pg_draw:
        lda pg_collect
        bne pg_return
        lda pg_bitmap
        beq +
        lda pg_prompt
        beq pg_refresh
        cmp b_prompt
        bne pg_refresh
        jsr pg_field
        jmp pg_present
+
        lda pg_attempted
        bne pg_return
        inc pg_attempted
        lda FD_GUI_SURFACE
        bne pg_refresh
        lda N_CURRENT
        sta N_OWNER
        lda #0
        sta N_BANK
        lda #$c0
        sta N_PAGE
        lda #36
        sta N_PAGES
        jsr N_RESERVE
        bcs pg_failed
        ldx #3
-       lda N_HANDLE,x
        sta FD_GUI_SURFACE,x
        dex
        bpl -
pg_refresh:
.if FD_VDC
        jsr FD_VDC_FULL
.endif
        lda b_prompt
        cmp pg_prompt
        beq pg_same_prompt
        sta pg_prompt
        ldx #4
        cmp #0
        beq pg_prompt_focus
        ldx #19
pg_prompt_focus:
        stx pg_focus
pg_same_prompt:
        lda b_busy
        cmp pg_busy
        beq +
        sta pg_busy
        ldx pg_saved_focus
        cmp #0
        beq pg_busy_focus
        ldx pg_focus
        stx pg_saved_focus
        ldx #18
pg_busy_focus:
        stx pg_focus
+
        lda #0
        sta pg_error
        sta pg_top
        sta pg_bottom
        sta pg_edge
        sta pg_inverse
        jsr pg_surface
        lda #0
        sta N_OFFSET
        sta N_OFFSET+1
        sta N_COUNT
        sta N_VALUE
        lda #2
        sta N_COUNT+1
pg_clear:
        jsr N_FILL
        bcs pg_failed
        inc N_OFFSET+1
        inc N_OFFSET+1
        lda N_OFFSET+1
        cmp #30
        bne pg_clear
        ldx #$40
        ldy #1
        lda pg_bitmap
        bne +
        ldx #0
        ldy #2
+       stx N_COUNT
        sty N_COUNT+1
        jsr N_FILL             ; 8,000 bitmap bytes; leave sprite tail intact
        bcs pg_failed
        lda #0
        sta N_OFFSET
        sta N_COUNT
        lda #32
        sta N_OFFSET+1
        lda #2
        sta N_COUNT+1
        lda #$16
        sta N_VALUE
        jsr N_FILL
        bcs pg_failed
        lda #34
        sta N_OFFSET+1
        ldx #$e8
        ldy #1
        lda pg_bitmap
        bne +
        ldx #0
        ldy #2
+       stx N_COUNT
        sty N_COUNT+1
        jsr N_FILL             ; 1,000 color cells; preserve sprite pointers
        bcs pg_failed
        lda #0
        sta b_screen
        sta pg_source_row
        sta pg_column
        lda #1
        sta pg_collect
        jsr b_list_draw
        lda #0
        sta pg_collect
        lda #16
        sta pg_row
        lda #1
        sta pg_column
        lda #<b_focus_help
        ldx #>b_focus_help
        jsr pg_string
        ldx pg_focus
        jsr pg_enabled
        bcc +
        ldx #18
        stx pg_focus
+       lda #0
        sta pg_control
pg_controls:
        ldx pg_control
        jsr pg_enabled
        bcs pg_control_next
        jsr pg_color
        ldx pg_control
        cpx #4
        bcc pg_button
        cpx #12
        bcc pg_control_next
        cpx #19
        beq pg_control_next
pg_button:
        jsr pg_box
pg_control_next:
        inc pg_control
        lda pg_control
        cmp #20
        bne pg_controls
        lda b_prompt
        beq pg_present
        jsr pg_field
pg_present:
        lda pg_error
        bne pg_failed
        lda pg_bitmap
        bne pg_shown
        jsr pg_surface
        jsr N_VSHOW
        bcs pg_failed
        inc pg_bitmap
        jsr pgm_install
        bcs pg_failed
pg_shown:
.if FD_VDC
        jsr FD_VDC_SYNC
.endif
pg_return:
        rts
pg_failed:
        sta pg_error
.if FD_VDC
        jsr FD_VDC_CLOSE        ; restore graphics before permitting text controls
.endif
        jmp pg_close

; A logical browser row maps to the common 40-column picker layout. Long
; raw names remain intact in the browser; this is a clipped display only.
pg_emit:
        php
        pha
        txa
        pha
        tya
        pha
        lda pg_character
        cmp #13
        bne +
        inc pg_source_row
        lda #0
        sta pg_column
        beq pg_emitted
+       ldx pg_source_row
        lda pg_rows,x
        sta pg_row
        cpx #5
        bcc pg_mapped
        cpx #14
        bcs pg_mapped
        lda N_BROWSERFMT
        cmp #3
        bne pg_mapped
        dec pg_row
        cpx #5
        bne pg_mapped
        lda #25
        sta pg_row
pg_mapped:
        lda b_prompt
        beq +
        lda pg_row
        cmp #7
        bcc +
        lda #25
        sta pg_row
+       lda pg_row
        cmp #25
        bcs pg_emitted
        lda pg_column
        cmp #38
        bcs pg_emitted
        inc pg_column
        lda pg_character
        jsr b_safe_character
        jsr pg_glyph
pg_emitted:
        pla
        tay
        pla
        tax
        pla
        plp
        rts

; Cell coordinates -> byte offset in the surface's 40-column screen plane.
pg_offset:
.if FD_VDC
        ldx pg_row
        lda #1
        sta FD_VDC_ROWS,x
        sta FD_VDC_PENDING
.endif
        lda pg_row
        asl
        asl
        asl
        sta N_OFFSET
        tay
        lda #0
        sta N_OFFSET+1
        asl N_OFFSET
        rol N_OFFSET+1
        asl N_OFFSET
        rol N_OFFSET+1
        tya
        clc
        adc N_OFFSET
        sta N_OFFSET
        bcc +
        inc N_OFFSET+1
+       lda N_OFFSET
        clc
        adc pg_column
        sta N_OFFSET
        bcc +
        inc N_OFFSET+1
+       rts
pg_glyph:
.if FD_GUI_SHARED && GFX_FONT_COLUMNS
        jsr gfx_load_glyph
.else
        sec
        sbc #32
        ldx #0
        stx pg_high
        asl
        rol pg_high
        asl
        rol pg_high
        asl
        rol pg_high
        clc
        adc #<pg_font
        sta pg_font_read+1
        lda pg_high
        adc #>pg_font
        sta pg_font_read+2
.endif
        ldx #7
-       lda N_BUFFER,x
        pha
        dex
        bpl -
        jsr pg_surface
        jsr pg_offset
        ldx #3
-       asl N_OFFSET
        rol N_OFFSET+1
        dex
        bne -
        ldx #7
pg_font_read:
.if FD_GUI_SHARED && GFX_FONT_COLUMNS
        lda gfx_bits,x
.else
        lda $ffff,x
.endif
        ora pg_edge
        eor pg_inverse
        sta N_BUFFER,x
        dex
        bpl pg_font_read
        lda N_BUFFER
        ora pg_top
        sta N_BUFFER
        lda N_BUFFER+7
        ora pg_bottom
        sta N_BUFFER+7
        lda #8
        sta N_COUNT
        lda #0
        sta N_COUNT+1
        jsr N_WRITE
        bcc +
        sta pg_error
+       ldx #0
-       pla
        sta N_BUFFER,x
        inx
        cpx #8
        bne -
        rts
pg_color:
        stx pg_paint
        lda #$1b
        cpx #4
        bcc +
        cpx #12
        bcs +
        lda #$16
+       cpx pg_focus
        bne +
        lda #$07
+       sta N_VALUE
        lda pg_y0,x
        sta pg_row
pg_color_row:
        ldx pg_paint
        lda pg_x0,x
        sta pg_column
        jsr pg_surface
        jsr pg_offset
        lda N_OFFSET+1
        clc
        adc #32
        sta N_OFFSET+1
        ldx pg_paint
        lda pg_x1,x
        sec
        sbc pg_column
        sta N_COUNT
        lda #0
        sta N_COUNT+1
        jsr N_FILL
        bcc +
        sta pg_error
+       inc pg_row
        ldx pg_paint
        lda pg_row
        cmp pg_y1,x
        bne pg_color_row
        rts
pg_box:
        lda pg_y0,x
        sta pg_row
        lda pg_labels,x
        sta pg_label_at
        cpx #16
        bne +
        lda b_prompt
        beq +
        lda #pg_ok_text-pg_text
        sta pg_label_at
+
pg_box_row:
        lda #0
        sta pg_top
        sta pg_bottom
        ldx pg_control
        lda pg_x0,x
        sta pg_column
        lda pg_row
        cmp pg_y0,x
        bne +
        lda #255
        sta pg_top
+       lda pg_row
        clc
        adc #1
        cmp pg_y1,x
        bne +
        lda #255
        sta pg_bottom
pg_box_cell:
+       lda #0
        sta pg_edge
        ldx pg_control
        lda pg_column
        cmp pg_x0,x
        bne +
        lda #$80
        sta pg_edge
+       lda pg_column
        clc
        adc #1
        cmp pg_x1,x
        bne +
        inc pg_edge
+       lda #32
        ldy pg_edge
        bne pg_box_glyph
        ldy pg_top
        bne pg_box_glyph
        ldy pg_bottom
        bne pg_box_glyph
        ldy pg_label_at
        lda pg_text,y
        beq +
        inc pg_label_at
        bne pg_box_glyph
+       lda #32
pg_box_glyph:
        jsr pg_glyph
        inc pg_column
        ldx pg_control
        lda pg_column
        cmp pg_x1,x
        bne pg_box_cell
        inc pg_row
        lda pg_row
        cmp pg_y1,x
        bne pg_box_row
        lda #0
        sta pg_edge
        sta pg_top
        sta pg_bottom
        rts

; X=control. Carry clear means available; hit testing does no I/O.
pg_enabled:
        cpx #20
        bcs pg_disabled
        cpx #18
        beq pg_enabled_yes
        lda b_busy
        bne pg_disabled
        lda b_prompt
        beq pg_normal
        cpx #19
        beq pg_enabled_yes
        cpx #16
        beq pg_enabled_yes
        cmp #3
        bne pg_disabled
        cpx #3
        beq pg_enabled_yes
        bne pg_disabled
pg_normal:
        cpx #19
        beq pg_disabled
        cpx #17
        bne +
        lda fd_mode
        cmp #2
        bne pg_disabled
+       cpx #4
        bcc pg_format_enabled
        cpx #12
        bcc pg_row_enabled
        cpx #16
        beq pg_row_enabled
        cpx #14
        bcs pg_enabled_yes
pg_format_enabled:
        cpx #0
        beq pg_enabled_yes
        cpx #2
        beq pg_enabled_yes
        lda N_BROWSERFMT
        cmp #3
        beq +
        cpx #1
        beq pg_enabled_yes
        bne pg_disabled
+       cpx #1
        bne pg_enabled_yes
pg_disabled:
        sec
        rts
pg_row_enabled:
        txa
        sec
        sbc #4
        cpx #16
        bne +
        lda #0
+       sta pg_row_index
        lda N_BROWSERFMT
        cmp #3
        bne +
        lda pg_row_index
        cmp bu_count
        rts
+       lda b_selected
        and #$f8
        clc
        adc pg_row_index
        cmp b_total
        lda b_selected+1
        sbc b_total+1
        rts
pg_enabled_yes:
        clc
        rts
pg_hit:
        lda pgm_x+1
        lsr
        lda pgm_x
        ror
        lsr
        lsr
        sta pg_hit_x
        lda pgm_y
        lsr
        lsr
        lsr
        sta pg_hit_y
        ldx #0
pg_hit_next:
        jsr pg_enabled
        bcs +
        lda pg_hit_x
        cmp pg_x0,x
        bcc +
        cmp pg_x1,x
        bcs +
        lda pg_hit_y
        cmp pg_y0,x
        bcc +
        cmp pg_y1,x
        bcc pg_hit_done
+       inx
        cpx #20
        bne pg_hit_next
        ldx #255
pg_hit_done:
        rts
pg_input:
.if FD_VDC_GUARD
        jsr FD_VDC_GUARD
.endif
        sta pg_key
.if FD_VDC
        lda FD_VDC_PHASE
        beq +
        lda FD_VDC_FAULT
        beq +
        lda pg_key
        cmp #27
        beq pg_key_return
        jmp pg_no_key
+
.endif
        lda pg_bitmap
        beq pg_key_return
        lda pg_key
        beq pg_mouse
        ldx #255
        stx pgm_arm
        cmp #9
        beq pg_tab
        cmp #13
        beq pg_enter
        cmp #$11
        beq pg_arrow
        cmp #$91
        bne pg_key_return
pg_arrow:
        lda b_prompt
        bne pg_key_return
        lda #16
        sta pg_focus
pg_key_return:
.if FD_VDC
        jsr FD_VDC_SYNC
.endif
        lda pg_key
        cmp #$85
        bne +
        lda #9
+       rts
pg_tab:
        ldx pg_focus
-       inx
        cpx #20
        bcc +
        ldx #0
+       jsr pg_enabled
        bcs -
        jsr pg_focus_set
pg_no_key:
.if FD_VDC
        jsr FD_VDC_SYNC
.endif
        lda #0
        rts
pg_enter:
        ldx pg_focus
        cpx #19
        beq pg_key_return
        jsr pg_activate
        rts
pg_mouse:
        jsr pgm_poll
        lda pgm_event
        beq pg_no_key
        ldx pgm_hit
        jsr pg_enabled
        bcs pg_no_key
        jsr pg_focus_set
        lda pgm_event
        cmp #2
        bne pg_no_key
        ldx pg_focus
        cpx #19
        bne +
        jsr pg_field_click
        lda #14
        rts
+       jsr pg_activate
        ldx pg_focus
        cpx #4
        bcc +
        cpx #12
        bcs +
        lda #14               ; row click selects; Choose/Enter opens it
+       rts
pg_focus_set:
        cpx pg_focus
        beq +
        lda pg_focus
        stx pg_focus
        tax
        jsr pg_color
        ldx pg_focus
        jsr pg_color
+       rts
pg_activate:
        jsr pg_enabled
        bcs pg_no_key
        cpx #4
        bcc pg_action
        cpx #12
        bcs pg_action
        txa
        sec
        sbc #4
        sta bu_row
        sta pg_row_index
        lda b_selected
        and #$f8
        ora pg_row_index
        sta b_selected
        lda #13
        rts
pg_action:
        lda pg_actions,x
        rts

; The shared field editor keeps the full 255-byte path. Only the VIC viewport
; and caret are drawn here; the VDC still uses the kernel's field renderer.
pg_field_output:
        lda pg_collect
        bne +
        jmp N_FDRAW
+       clc
        rts
pg_field_pointer:
        lda b_prompt
        cmp #1
        beq +
        jmp b_usb_pointer
+       jmp b_device_pointer
pg_string:
        sta pg_string_read+1
        stx pg_string_read+2
pg_string_read:
        lda $ffff
        beq pg_string_done
        cmp #13
        beq pg_string_done
        jsr b_safe_character
        jsr pg_glyph
        inc pg_string_read+1
        bne +
        inc pg_string_read+2
+       inc pg_column
        lda pg_column
        cmp #39
        bcc pg_string_read
pg_string_done:
        lda pg_column
        cmp #39
        bcs +
        lda #32
        jsr pg_glyph
        inc pg_column
        bne pg_string_done
+       rts
pg_field:
        lda #7
        sta pg_row
        lda #1
        sta pg_column
        lda #<pg_path_title
        ldx #>pg_path_title
        ldy b_prompt
        cpy #1
        bne +
        lda #<pg_device_title
        ldx #>pg_device_title
+       jsr pg_string
        lda b_prompt
        cmp #2
        bcc +
        lda #13
        sta pg_column
        lda b_usb_device
        ora #$30
        jsr pg_glyph
+       lda #14
        sta pg_row
        lda #1
        sta pg_column
        lda #<pg_field_help
        ldx #>pg_field_help
        ldy b_usb_error
        beq +
        ldy b_prompt
        cpy #2
        bcc +
        lda #<b_usb_bad_path
        ldx #>b_usb_bad_path
        ldy b_usb_error
        cpy #2
        bne +
        lda #<b_usb_bad_input
        ldx #>b_usb_bad_input
+       jsr pg_string
        jsr pg_field_pointer
        lda N_UIPTR
        sta pg_state_read+1
        sta pg_state_write+1
        lda N_UIPTR+1
        sta pg_state_read+2
        sta pg_state_write+2
        ldx #5
pg_state_read:
        lda $ffff,x
        sta pg_field_data,x
        dex
        bpl pg_state_read
        lda pg_field_data+3
        sta pg_field_read+1
        lda pg_field_data+4
        sta pg_field_read+2
        lda pg_field_data
        sec
        sbc #36
        bcs +
        lda #255
+       clc
        adc #1
        cmp pg_field_data+5
        bcs +
        sta pg_field_data+5
+       lda pg_field_data+1
        cmp pg_field_data+5
        bcs +
        sta pg_field_data+5
+       lda pg_field_data+1
        sec
        sbc pg_field_data+5
        cmp #36
        bcc +
        lda pg_field_data+1
        sec
        sbc #35
        sta pg_field_data+5
+       lda pg_field_data+5
        ldx #5
pg_state_write:
        sta $ffff,x
        lda pg_field_data+1
        sec
        sbc pg_field_data+5
        clc
        adc #2
        sta pg_caret
        lda #10
        sta pg_row
        lda #1
        sta pg_column
        lda #32
        ldx pg_field_data+5
        beq +
        lda #$3c
+       jsr pg_glyph
        lda #0
        sta pg_field_at
pg_field_next:
        inc pg_column
        lda #0
        sta pg_inverse
        lda pg_column
        cmp pg_caret
        bne +
        lda #255
        sta pg_inverse
+       lda pg_field_at
        clc
        adc pg_field_data+5
        bcs pg_field_blank
        cmp pg_field_data
        bcs pg_field_blank
        tax
pg_field_read:
        lda $ffff,x
        jsr b_safe_character
        jmp pg_field_emit
pg_field_blank:
        lda #32
pg_field_emit:
        jsr pg_glyph
        inc pg_field_at
        lda pg_field_at
        cmp #36
        bne pg_field_next
        lda #0
        sta pg_inverse
        inc pg_column
        lda pg_field_data
        sec
        sbc pg_field_data+5
        cmp #37
        lda #32
        bcc +
        lda #$3e
+       jmp pg_glyph
pg_field_click:
        lda pg_hit_x
        sec
        sbc #2
        bcs +
        lda #0
+       cmp #36
        bcc +
        lda #35
+       clc
        adc pg_field_data+5
        bcs +
        cmp pg_field_data
        bcc pg_field_cursor
+       lda pg_field_data
pg_field_cursor:
        sta pg_field_data+1
        ldx #1
        jmp pg_state_write

pg_rows: .byte 1,25,5,6,7,8,9,10,11,12,13,14,15,16,25,25,25,25,25,24,25,25,25,25,25
pg_x0: .byte 1,11,20,29, 1,1,1,1,1,1,1,1, 1,11,20,29, 1,14,29, 1
pg_x1: .byte 10,19,28,38, 39,39,39,39,39,39,39,39, 10,19,28,38, 12,27,38, 39
pg_y0: .byte 2,2,2,2, 8,9,10,11,12,13,14,15, 17,17,17,17, 20,20,20, 10
pg_y1: .byte 5,5,5,5, 9,10,11,12,13,14,15,16, 20,20,20,20, 23,23,23, 11
pg_actions: .byte $52,$44,$46,9, 0,0,0,0,0,0,0,0, $50,$47,$42,$4e, 13,$53,27,0
pg_labels: .byte pg_refresh_text-pg_text,pg_device_text-pg_text,pg_format_text-pg_text,pg_dos_text-pg_text,0,0,0,0,0,0,0,0,pg_parent_text-pg_text,pg_path_text-pg_text,pg_prev_text-pg_text,pg_next_text-pg_text,pg_choose_text-pg_text,pg_here_text-pg_text,pg_cancel_text-pg_text,0
pg_text:
pg_refresh_text: .text "refresh",0
pg_device_text: .text "device",0
pg_format_text: .text "format",0
pg_dos_text: .text "dos 1/2",0
pg_parent_text: .text "parent",0
pg_path_text: .text "path",0
pg_prev_text: .text "prev",0
pg_next_text: .text "next",0
pg_choose_text: .text "choose",0
pg_ok_text: .text "ok",0
pg_here_text: .text "use here",0
pg_cancel_text: .text "cancel",0
pg_device_title: .text "device (8-30):",0
pg_path_title: .text "path on dos ",0
pg_field_help: .text "enter ok  ctrl-u clear  esc cancel",0
pg_busy: .byte 0
pg_saved_focus: .byte 0
pg_prompt: .byte 0
pg_bitmap: .byte 0
pg_attempted: .byte 0
pg_error: .byte 0
pg_collect: .byte 0
pg_focus: .byte 4
pg_control: .byte 0
pg_paint: .byte 0
pg_label_at: .byte 0
pg_row: .byte 0
pg_source_row: .byte 0
pg_column: .byte 0
pg_character: .byte 0
pg_high: .byte 0
pg_top: .byte 0
pg_bottom: .byte 0
pg_edge: .byte 0
pg_inverse: .byte 0
pg_hit_x: .byte 0
pg_hit_y: .byte 0
pg_row_index: .byte 0
pg_key: .byte 0
pg_field_data: .fill 6,0
pg_field_at: .byte 0
pg_caret: .byte 0
.if FD_GUI_SHARED
pg_font=gfx_font
pgm_close=pm_close
pgm_install=pm_install
pgm_poll=pm_poll
pgm_x=pm_x
pgm_y=pm_y
pgm_event=pm_event
pgm_hit=pm_hit
pgm_arm=pm_arm

.else
PM_KEYS_OWNED=1
PM_KEYS_EXTERNAL=1
pg_font: .binary "../graphics/font8.bin"
pgm_control_count=20
pgm_select_surface=pg_surface
pgm_find_hit=pg_hit
.include "pointer.inc"
.endif
