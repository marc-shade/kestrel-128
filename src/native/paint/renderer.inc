pa_redraw:
        lda pa_bitmap
        beq pa_redraw_console
        jsr pa_draw
        bcc +
        jsr pa_view_failed
        jmp pa_redraw_console
+       lda pa_keyboard
        beq pa_redraw_console
        jsr pa_cursor
pa_redraw_console:
        jmp pa_console
pa_draw:
        lda pa_mode
        beq pa_draw_main
        cmp #1
        beq pa_draw_confirm
        jmp pa_draw_save
pa_draw_main:
        jsr pa_select_view
        jsr pa_scene.draw_scene
        bcs pa_draw_done
        lda #0
        sta pa_ui_index
-       ldx pa_ui_index
        jsr ui_paint
        bcs pa_draw_done
        inc pa_ui_index
        lda pa_ui_index
        cmp #7
        bne -
        lda #0
        sta pa_palette_index
pa_palette_next:
        lda pa_palette_index
        asl
        clc
        adc #1
        sta gfx_x0
        clc
        adc #2
        sta gfx_x1
        lda #23
        sta gfx_y0
        lda #25
        sta gfx_y1
        lda #0
        sta gfx_x0+1
        sta gfx_x1+1
        sta gfx_y0+1
        sta gfx_y1+1
        lda pa_palette_index
        cmp #1
        beq +
        ora #$10
+       sta gfx_color
        jsr gfx_colors
        bcs pa_draw_done
        inc pa_palette_index
        lda pa_palette_index
        cmp #16
        bne pa_palette_next
        ldx ui_selected
        jsr pa_focus_paint
        bcs pa_draw_done
        jsr pa_blit
        bcs pa_draw_done
        jmp pa_labels
pa_draw_done:
        rts

; Main buttons use the shared yellow focus colors. A palette cell keeps its
; color and uses a contrasting border. The canvas has no button highlight.
pa_focus_paint:
        cpx #7
        bcc pa_focus_button
        cpx #23
        beq pa_focus_nothing
        bcs pa_focus_button
        stx pa_paint_index
        jsr pa_rect_bounds
        lda #0
        sta gfx_pen
        jsr gfx_rect
        bcs pa_draw_done
        ldx pa_paint_index
        cpx ui_selected
        bne pa_focus_nothing
        jsr pa_rect_bounds
        lda #1
        sta gfx_pen
        jsr gfx_rect
        bcs pa_draw_done
        ldx pa_paint_index
        jsr pa_rect_bounds
        inc gfx_x0
        inc gfx_y0
        dec gfx_x1
        dec gfx_y1
        lda #0
        sta gfx_pen
        jmp gfx_rect
pa_focus_button:
        jmp ui_paint
pa_focus_nothing:
        lda #0
        clc
        rts
pa_rect_bounds:
        txa
        asl
        asl
        asl
        tax
        ldy #0
-       lda ui_rects,x
        sta gfx_x0,y
        inx
        iny
        cpy #8
        bne -
        rts
pa_focus:
        stx pa_next_focus
        ldx ui_selected
        cpx pa_next_focus
        beq pa_focus_nothing
        lda pa_next_focus
        sta ui_selected
        jsr pa_focus_paint
        bcs pa_draw_done
        ldx ui_selected
        jmp pa_focus_paint

pa_labels:
        lda #8
        sta gfx_x0
        lda #20
        sta gfx_y0
        lda #8
        sta gfx_x1
        lda #1
        sta gfx_x1+1
        lda #28
        sta gfx_y1
        lda #0
        sta gfx_x0+1
        sta gfx_y0+1
        sta gfx_y1+1
        sta gfx_pen
        jsr gfx_rect
        bcs pa_draw_done
        jsr pa_make_status
        lda #8
        ldy #20
        jsr pa_text
        bcs pa_draw_done
        jmp pa_message
pa_make_status:
        ldx #21
-       lda pa_status_template,x
        sta gfx_text_buffer,x
        dex
        bpl -
        lda pd_x
        sta pa_number
        lda pd_x+1
        sta pa_number+1
        ldx #2
        jsr pa_decimal
        lda pd_y
        sta pa_number
        lda #0
        sta pa_number+1
        ldx #8
        jsr pa_decimal
        lda pd_pen
        bne +
        ldx #3
-       lda pa_eras_label,x
        sta gfx_text_buffer+12,x
        dex
        bpl -
+       ldx pd_color
        lda pa_hex,x
        sta gfx_text_buffer+21
        lda #22
        sta gfx_text_length
        lda pd_dirty
        beq +
        lda #32
        sta gfx_text_buffer+22
        lda #42
        sta gfx_text_buffer+23
        lda #24
        sta gfx_text_length
+       rts
pa_message:
        lda #8
        sta gfx_x0
        lda #176
        sta gfx_y0
        lda #8
        sta gfx_x1
        lda #1
        sta gfx_x1+1
        lda #184
        sta gfx_y1
        lda #0
        sta gfx_x0+1
        sta gfx_y0+1
        sta gfx_y1+1
        sta gfx_pen
        jsr gfx_rect
        bcs pa_draw_done
        jsr pa_message_pointer
        jsr pa_text_copy
        lda #8
        ldy #176
        jmp pa_text

pa_message_pointer:
        ldy pa_status
        lda pa_messages_lo,y
        ldx pa_messages_hi,y
        rts

pa_draw_confirm:
        jsr pa_select_view
        jsr pa_confirm_scene.draw_scene
        bcs pa_draw_done
        jsr pa_dialog_buttons
        bcs pa_draw_done
        lda #<pa_discard
        ldx #>pa_discard
        ldy pa_action
        cpy #2
        bne +
        lda #<pa_open_label
        ldx #>pa_open_label
+       jsr pa_text_copy
        lda #68
        ldx pa_action
        cpx #2
        bne +
        lda #80
+       ldy #104
        jsr pa_text
        bcs pa_draw_done
        lda #<pa_close_question
        ldx #>pa_close_question
        ldy pa_action
        cpy #2
        bne +
        lda #<pa_open_question
        ldx #>pa_open_question
+       jsr pa_text_copy
        lda #32
        ldy #72
        jsr pa_text
        bcs pa_draw_done
        jmp pa_message
pa_draw_save:
        jsr pa_select_view
        jsr pa_save_scene.draw_scene
        bcs pa_draw_done
        jsr pa_dialog_buttons
        bcs pa_draw_done
        jsr pa_make_destination
        lda #32
        ldy #48
        jsr pa_text
        bcs pa_draw_done
        jsr pa_update_field
        bcs pa_draw_done
        jmp pa_message
pa_update_field:
        lda #32
        sta gfx_x0
        lda #72
        sta gfx_y0
        lda #32
        sta gfx_x1
        lda #1
        sta gfx_x1+1
        lda #80
        sta gfx_y1
        lda #0
        sta gfx_x0+1
        sta gfx_y0+1
        sta gfx_y1+1
        sta gfx_pen
        jsr gfx_rect
        bcs pa_draw_done
        jsr pa_filename
        lda #32
        ldy #72
        jsr pa_text
        bcs pa_draw_done
        lda pa_field_caret
        sec
        sbc pa_field_view
        asl
        asl
        asl
        clc
        adc #32
        sta gfx_x0
        lda #0
        adc #0
        sta gfx_x0+1
        lda gfx_x0
        clc
        adc #8
        sta gfx_x1
        lda gfx_x0+1
        adc #0
        sta gfx_x1+1
        lda #72
        sta gfx_y0
        lda #80
        sta gfx_y1
        lda #0
        sta gfx_y0+1
        sta gfx_y1+1
        lda #2
        sta gfx_pen
        jmp gfx_rect
pa_dialog_buttons:
        ldx #24
        jsr ui_paint
        bcs pa_draw_done
        ldx #25
        jmp ui_paint
pa_make_destination:
        ldx #12
-       lda pa_destination_template,x
        sta gfx_text_buffer,x
        dex
        bpl -
        lda pf_device
        sta pa_number
        lda #0
        sta pa_number+1
        ldx #7
        jsr pa_decimal
        lda pf_format
        asl
        asl
        tax
        ldy #11
-       lda pa_formats,x
        sta gfx_text_buffer,y
        inx
        iny
        cpy #14
        bne -
        sty gfx_text_length
        rts
pa_filename:
        lda pa_field_caret
        cmp pa_field_view
        bcs +
        sta pa_field_view
+       sec
        sbc pa_field_view
        cmp #32
        bcc +
        lda pa_field_caret
        sec
        sbc #31
        sta pa_field_view
+       ldx #31
        lda #32
-       sta gfx_text_buffer,x
        dex
        bpl -
        ldx pa_field_view
        ldy #0
-       cpx pf_length
        beq +
        lda pf_name,x
        jsr pa_safe_character
        sta gfx_text_buffer,y
        inx
        iny
        cpy #32
        bne -
+       lda #32
        sta gfx_text_length
        rts

pa_decimal:
        lda #48
        sta gfx_text_buffer,x
-       lda pa_number+1
        bne +
        lda pa_number
        cmp #100
        bcc pa_tens
+       lda pa_number
        sec
        sbc #100
        sta pa_number
        lda pa_number+1
        sbc #0
        sta pa_number+1
        inc gfx_text_buffer,x
        jmp -
pa_tens:
        inx
        lda #48
        sta gfx_text_buffer,x
-       lda pa_number
        cmp #10
        bcc +
        sec
        sbc #10
        sta pa_number
        inc gfx_text_buffer,x
        jmp -
+       inx
        lda pa_number
        clc
        adc #48
        sta gfx_text_buffer,x
        rts
pa_text_copy:
        sta pa_text_read+1
        stx pa_text_read+2
        ldx #0
pa_text_read:
        lda $ffff,x
        beq +
        sta gfx_text_buffer,x
        inx
        cpx #32
        bne pa_text_read
+       stx gfx_text_length
        rts
pa_text:
        sta gfx_x0
        sty gfx_y0
        lda #0
        sta gfx_x0+1
        sta gfx_y0+1
        lda #1
        sta gfx_pen
        jmp gfx_text

pa_ui_index: .byte 0
pa_palette_index: .byte 0
pa_paint_index: .byte 0
pa_next_focus: .byte 0
pa_number: .word 0
ui_selected: .byte 23
pa_status_template: .byte 88,58,48,48,48,32,89,58,48,48,48,32,80,101,110,32,32,73,110,107,58,49
pa_eras_label: .byte 69,114,97,115
pa_hex: .text "0123456789abcdef"
.include "messages.inc"
