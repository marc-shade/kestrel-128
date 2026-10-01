; Shared blue VIC controls, with the existing VDC/text formatter as a client.
ug_init:
        jsr nk_install
        lda #0
        sta ug_attempted
        sta ug_bitmap
        sta ug_mode
        sta ug_notice
        sta ug_vdc_attempted
        sta ui_selected
        rts
ug_update:
        jsr ug_collect_body
        ldx ui_selected
        jsr ug_enabled
        bcc +
        lda uc_page
        sta ui_selected
+       lda ug_attempted
        beq ug_view_open
        lda ug_bitmap
        beq ug_return
        jsr ug_draw
        bcc ug_vdc_sync
        jmp ug_failed
ug_view_open:
        lda #1
        sta ug_attempted
        lda ug_handle
        bne ug_initialize
        lda N_CURRENT
        sta N_OWNER
        lda #0
        sta N_BANK
        lda #$c0
        sta N_PAGE
        lda #36
        sta N_PAGES
        jsr N_RESERVE
        bcs ug_failed
        ldx #3
-       lda N_HANDLE,x
        sta ug_handle,x
        dex
        bpl -
ug_initialize:
        jsr ug_select_view
        lda #0
        sta N_OFFSET
        sta N_OFFSET+1
        sta N_COUNT
        sta N_VALUE
        lda #2
        sta N_COUNT+1
-       lda #0
        ldx N_OFFSET+1
        cpx #32
        bcc +
        lda #$16
+       sta N_VALUE
        jsr N_FILL
        bcs ug_failed
        inc N_OFFSET+1
        inc N_OFFSET+1
        lda N_OFFSET+1
        cmp #36
        bne -
        jsr ug_draw
        bcs ug_failed
        jsr ug_select_view
        jsr N_VSHOW
        bcs ug_failed
        lda #1
        sta ug_bitmap
        jsr pm_install
        bcc ug_vdc_sync
ug_failed:
        sta ug_error
        jsr ug_view_close
        bcs ug_return
        lda ug_handle
        beq ug_return
        jsr ug_select_view
        jsr N_FREE
        bcs ug_return
        lda #0
        sta ug_handle
ug_return:
        rts
ug_view_close:
        jsr vd_close
        bcs ug_return
ug_surface_close:
        jsr pm_close
        jsr N_VCLOSE
        lda #0
        sta ug_bitmap
        clc
        rts
ug_select_view:
        lda N_CURRENT
        sta N_OWNER
        ldx #3
-       lda ug_handle,x
        sta N_HANDLE,x
        dex
        bpl -
        rts

; The component keeps the same surface and original VDC snapshot while the
; picker borrows it. Only the final app close releases that display lifetime.
ug_vdc_sync:
        lda ug_vdc_attempted
        bne ug_vdc_present
        inc ug_vdc_attempted
        jsr vd_open
        bcc ug_return
        jsr vd_close
ug_vdc_present:
        jsr vm_present
        jsr vd_poll
        lda vd_phase
        beq ug_return
        lda vd_fault
        beq ug_return
        lda drive_picker.fd_active
        bne ug_return
        lda #11
        sta ug_notice
        jmp ug_draw
ug_vdc_full:
        lda #1
        sta vm_pending
        ldx #24
-       sta vm_rows,x
        dex
        bpl -
        rts

ug_draw:
        jsr ug_select_view
        jsr gfx_bind
        bcs ug_draw_done
        ldx #7
-       lda ug_frame,x
        sta gfx_x0,x
        dex
        bpl -
        lda #0
        sta gfx_pen
        jsr gfx_rect
        bcs ug_draw_done
        ldx #7
-       lda ug_cells,x
        sta gfx_x0,x
        dex
        bpl -
        lda #$16
        sta gfx_color
        jsr gfx_colors
        bcs ug_draw_done
        lda #<ug_title
        ldx #>ug_title
        jsr ug_copy_text
        lda #8
        ldy #8
        jsr ug_text
        bcs ug_draw_done
        lda #0
        sta ug_index
ug_draw_control:
        ldx ug_index
        jsr ug_enabled
        bcs ug_draw_next
        jsr ui_paint
        bcs ug_draw_done
        lda ug_index
        cmp #17
        beq ug_draw_next
        cmp #16
        beq +
        cmp #12
        bcs ug_draw_next
+
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
        lda #1
        sta gfx_pen
        jsr gfx_rect
        bcs ug_draw_done
        lda ug_index
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
        inc gfx_x0
        bne +
        inc gfx_x0+1
+       inc gfx_y0
        lda gfx_x1
        bne +
        dec gfx_x1+1
+       dec gfx_x1
        dec gfx_y1
        lda #0
        sta gfx_pen
        jsr gfx_rect
        bcs ug_draw_done
        ldx ug_index
        lda ug_labels_lo,x
        pha
        lda ug_labels_hi,x
        tax
        pla
        jsr ug_copy_text
        lda ug_index
        asl
        tax
        lda ug_label_x+1,x
        sta gfx_x0+1
        lda ug_label_x,x
        pha
        ldx ug_index
        ldy ug_label_y,x
        pla
        jsr ug_text_xword
        bcs ug_draw_done
ug_draw_next:
        inc ug_index
        lda ug_index
        cmp #18
        bne ug_draw_control
        lda #<ug_body
        sta ug_body_read+1
        lda #>ug_body
        sta ug_body_read+2
        lda #0
        sta ug_row
ug_draw_row:
        ldx #0
ug_body_read:
        lda ug_body,x
        sta gfx_text_buffer,x
        inx
        cpx #36
        bne ug_body_read
ug_trim_row:
        lda gfx_text_buffer-1,x
        cmp #32
        bne +
        dex
        bne ug_trim_row
        beq ug_row_next
+
        stx gfx_text_length
        lda ug_row
        asl
        asl
        asl
        clc
        adc #56
        tay
        lda #16
        jsr ug_text
        bcs ug_draw_done
ug_row_next:
        lda ug_body_read+1
        clc
        adc #36
        sta ug_body_read+1
        bcc +
        inc ug_body_read+2
+       inc ug_row
        lda ug_row
        cmp #12
        bne ug_draw_row
        lda ug_mode
        beq +
        cmp #2
        bne ug_drive_question
        lda #<ut_question
        ldx #>ut_question
        bne ug_draw_question
ug_drive_question:
        lda #<ug_question
        ldx #>ug_question
ug_draw_question:
        jsr ug_copy_text
        lda #16
        ldy #32
        jsr ug_text
        bcs ug_draw_done
+       ldx ug_notice
        lda ug_notices_lo,x
        pha
        lda ug_notices_hi,x
        tax
        pla
        jsr ug_copy_text
        lda #8
        ldy #192
        jsr ug_text
ug_draw_done:
        rts
ug_copy_text:
        sta ug_string_read+1
        stx ug_string_read+2
        ldx #0
ug_string_read:
        lda $ffff,x
        beq +
        sta gfx_text_buffer,x
        inx
        cpx #38
        bne ug_string_read
+       stx gfx_text_length
        rts
ug_text:
        ldx #0
        stx gfx_x0+1
ug_text_xword:
        sta gfx_x0
        sty gfx_y0
        lda #0
        sta gfx_y0+1
        lda #1
        sta gfx_pen
        jmp gfx_text

; C clear means a currently visible control; X remains the index.
ug_enabled:
        cpx #18
        bcs ug_disabled
        lda ug_mode
        beq ug_main_enabled
        cmp #2
        bne +
        cpx #17
        beq ug_allowed
+
        cpx #10
        bcc ug_disabled
        cpx #12
        bcs ug_disabled
        clc
        rts
ug_main_enabled:
        cpx #16
        bne +
        lda uc_page
        cmp #3
        beq ug_allowed
        bne ug_disabled
+       cpx #17
        beq ug_disabled
        cpx #8
        bcs ug_drive_enabled
        lda uc_page
        cmp #3
        bne ug_allowed
        cpx #5
        beq ug_disabled
        cpx #6
        beq ug_disabled
ug_allowed:
        clc
        rts
ug_drive_enabled:
        lda uc_page
        cmp #1
        bne ug_disabled
        cpx #10
        bcc ug_allowed
        cpx #12
        bcc ug_disabled
        txa
        sec
        sbc #12
        cmp ud_count
        bcc ug_allowed
ug_disabled:
        sec
        rts

; The console formatter also supplies the graphical body's bounded text.
uc_emit:
        php
        pha
        lda ug_collect
        beq +
        pla
        plp
        jmp ug_emit
+       pla
        plp
        jmp $ffd2
ug_emit:
        sta ug_character
        php
        pha
        txa
        pha
        tya
        pha
        lda ug_row
        cmp #12
        bcs ug_emit_done
        lda ug_character
        cmp #13
        beq ug_emit_newline
        ldx ug_column
        cpx #36
        bcs ug_emit_done
        cmp #32
        bcc ug_emit_done
        cmp #127
        bcc ug_body_write
        lda #$2e
ug_body_write:
        sta ug_body
        inc ug_body_write+1
        bne +
        inc ug_body_write+2
+       inc ug_column
        bne ug_emit_done
ug_emit_newline:
        lda #36
        sec
        sbc ug_column
        clc
        adc ug_body_write+1
        sta ug_body_write+1
        bcc +
        inc ug_body_write+2
+       lda #0
        sta ug_column
        inc ug_row
ug_emit_done:
        pla
        tay
        pla
        tax
        pla
        plp
        rts
ug_collect_body:
        lda #32
        ldx #0
-       sta ug_body,x
        sta ug_body+256,x
        inx
        bne -
        lda #<ug_body
        sta ug_body_write+1
        lda #>ug_body
        sta ug_body_write+2
        lda #0
        sta ug_row
        sta ug_column
        lda #1
        sta ug_collect
        lda ug_mode
        bne ug_collect_confirm
        lda uc_page
        cmp #1
        beq ug_collect_drives
        jsr uc_draw
        jmp ug_collected
ug_collect_drives:
        jsr ug_drive_body
        jmp ug_collected
ug_collect_confirm:
        cmp #2
        bne +
        jsr ut_body
        jmp ug_collected
+       jsr ug_confirm_body
ug_collected:
        lda #0
        sta ug_collect
        rts

ug_frame: .word 0,0,320,200
ug_cells: .word 0,0,40,25
ug_attempted: .byte 0
ug_vdc_attempted: .byte 0
ug_bitmap: .byte 0
ug_handle: .fill 4,0
ug_error: .byte 0
ug_mode: .byte 0
ug_notice: .byte 0
ug_collect: .byte 0
ug_character: .byte 0
ug_column: .byte 0
ug_row: .byte 0
ug_index: .byte 0
ug_body=$5200
