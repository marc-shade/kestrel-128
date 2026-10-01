; Blue 40-column bitmap grid with the shared 640-pixel VDC presenter.
; Each dirty character row is uploaded in two checked native transfers.
* = $6080
.include "../api.inc"
sg_begin: jmp sg_start
sg_present: jmp sg_draw
sg_end: jmp sg_close
sg_poll: jmp sg_input
sg_retry: jmp sg_reopen

sg_surface:
        lda N_CURRENT
        sta N_OWNER
        ldx #3
-       lda sg_handle,x
        sta N_HANDLE,x
        dex
        bpl -
        rts
sg_start:
        lda #1
        jsr sg_module
        bcs sg_result
        lda #0
        sta N_BANK
        lda N_CURRENT
        sta N_OWNER
        lda #$c0
        sta N_PAGE
        lda #36
        sta N_PAGES
        jsr N_RESERVE
        bcs sg_result
        ldx #3
-       lda N_HANDLE,x
        sta sg_handle,x
        dex
        bpl -
        lda #0
        sta N_VALUE
        sta N_OFFSET
        sta N_OFFSET+1
        sta N_COUNT
        lda #2
        sta N_COUNT+1
-       jsr N_FILL
        bcs sg_result
        inc N_OFFSET+1
        inc N_OFFSET+1
        lda N_OFFSET+1
        cmp #36
        bne -
        jsr sg_surface
        jsr N_VSHOW
        bcs sg_result
        inc sg_bitmap
        jsr pm_install
        bcs sg_result
        jsr vd_open
        bcc sg_ok
        jsr vd_close
        bcs sg_result
sg_ok:
        lda #0
sg_result:
        sta sg_error
        ldx #0
        rts
sg_close:
        jsr vd_close
        bcs sg_result
        jsr pm_close
        jsr N_VCLOSE
        bcs sg_result
        lda #0
        sta sg_bitmap
        lda sg_handle
        beq sg_ok
        jsr sg_surface
        jsr N_FREE
        bcs sg_result
        lda #0
        sta sg_handle
        beq sg_result
sg_reopen:
        lda #0
        sta sm_display_fault
        jsr vd_close
        bcs sg_result
        jsr vd_open
        bcc sg_ok
        jsr vd_close
        bcs sg_result
        jmp sg_ok

sg_draw:
        lda #0
        sta N_READY
        lda sm_display_fault
        bne sg_result
        lda vd_phase
        beq +
        lda vd_fault
        bne sg_result
+       lda #1
        jsr sg_module
        bcc +
        sta sm_display_fault
        jmp sg_result
+
        lda #0
        sta sg_row
        sta sg_changed
-       ldx sg_row
        lda sg_dirty,x
        beq +
        inc sg_changed
        jsr sg_draw_row
        bcs sg_result
+       inc sg_row
        lda sg_row
        cmp #25
        bne -
        lda vd_live
        beq sg_text
        jsr vm_present
        bcs sg_result
        jmp sg_ok
sg_text:
        ; A clean refusal of the bitmap service keeps the 80-column monitor
        ; usable. No KERNAL output is allowed while its display is retained.
        lda vd_phase
        bne sg_ok
        lda sg_changed
        beq sg_ok
        bit $d7
        bmi +
        jsr $ff5f
+       lda #0
        sta sg_row
-       ldx sg_row
        ldy #0
        clc
        jsr $fff0
        jsr sg_source_row
        lda #0
        sta sg_column
sg_text_char:
        ldx sg_column
sg_console_load:
        lda sg_chars,x
        cmp #$61
        bcc +
        cmp #$7b
        bcs +
        sec
        sbc #32
        bne sg_emit
+       cmp #$41
        bcc sg_emit
        cmp #$5b
        bcs sg_emit
        ora #$80
sg_emit:
        jsr $ffd2
        inc sg_column
        lda sg_column
        cmp #40
        bne sg_text_char
        inc sg_row
        lda sg_row
        cmp #25
        bne -
        jmp sg_ok

sg_source_row:
        lda sg_row
        asl
        tax
        clc
        lda sg_text_rows,x
        adc #<sg_chars
        sta sg_char_load+1
        sta sg_console_load+1
        lda sg_text_rows+1,x
        adc #>sg_chars
        sta sg_char_load+2
        sta sg_console_load+2
        clc
        lda sg_text_rows,x
        adc #<sg_colors
        sta sg_color_load+1
        lda sg_text_rows+1,x
        adc #>sg_colors
        sta sg_color_load+2
        rts
sg_draw_row:
        jsr sg_source_row
        lda #<N_BUFFER
        sta sg_store+1
        lda #>N_BUFFER
        sta sg_store+2
        lda #0
        sta sg_column
sg_char:
        ldx sg_column
sg_char_load:
        lda sg_chars,x
        cmp #32
        bcc sg_question
        cmp #127
        bcc +
sg_question:
        lda #63
+       sec
        sbc #32
        ldx #0
        stx sg_high
        asl
        rol sg_high
        asl
        rol sg_high
        asl
        rol sg_high
        clc
        adc #<sg_font
        sta sg_font_load+1
        lda sg_high
        adc #>sg_font
        sta sg_font_load+2
        ldx #7
sg_font_load:
        lda sg_font,x
sg_store:
        sta N_BUFFER,x
        dex
        bpl sg_font_load
        clc
        lda sg_store+1
        adc #8
        sta sg_store+1
        bcc +
        inc sg_store+2
+       inc sg_column
        lda sg_column
        cmp #40
        bne sg_char
        jsr sg_surface
        lda sg_row
        asl
        tax
        lda sg_bitmap_rows,x
        sta N_OFFSET
        lda sg_bitmap_rows+1,x
        sta N_OFFSET+1
        lda #64
        sta N_COUNT
        lda #1
        sta N_COUNT+1
        jsr N_WRITE
        bcs sg_row_return
        ldx #39
sg_color_load:
        lda sg_colors,x
        sta N_BUFFER,x
        dex
        bpl sg_color_load
        jsr sg_surface
        lda sg_row
        asl
        tax
        lda sg_text_rows,x
        sta N_OFFSET
        lda sg_text_rows+1,x
        clc
        adc #$20
        sta N_OFFSET+1
        lda #40
        sta N_COUNT
        lda #0
        sta N_COUNT+1
        jsr N_WRITE
        bcs sg_row_return
        ldx sg_row
        lda #1
        sta vm_rows,x
        sta vm_pending
        lda #0
        sta sg_dirty,x
sg_row_return:
        rts

sg_input:
        jsr pm_poll
        jsr vd_poll
        lda pm_hit
        sta sg_hit
        lda pm_event
        cmp #2
        beq +
        lda #0
+       ldx #0
        rts
pm_find_hit:
        ; Stable hit IDs: six toolbar buttons, then all 48 visible cells.
        lda pm_x+1
        sta sg_high
        lda pm_x
        lsr sg_high
        ror
        lsr
        lsr
        sta sg_column
        lda pm_y
        lsr
        lsr
        lsr
        cmp #2
        beq sg_toolbar_hit
        ldx #$ff
        ldy sg_mode
        bne sg_hit_done
        sec
        sbc #6
        cmp #12
        bcs sg_hit_done
        asl
        asl
        clc
        adc #6
        sta sg_high
        lda sg_column
        sec
        sbc #3
        bcc sg_hit_done
        ldx #0
-       cmp #9
        bcc +
        sec
        sbc #9
        inx
        bne -
+       cpx #4
        bcs sg_no_hit
        txa
        clc
        adc sg_high
        tax
        rts
sg_toolbar_hit:
        ldx #5
-       lda sg_column
        cmp sg_button_left,x
        bcc +
        cmp sg_button_right,x
        bcc sg_hit_done
+       dex
        bpl -
sg_no_hit:
        ldx #$ff
sg_hit_done:
        rts
sg_button_left: .byte 0,6,12,18,24,34
sg_button_right:.byte 5,12,18,24,31,40
pm_control_count=54
pm_select_surface=sg_surface
.include "../input/pointer.inc"
BP_MODE=0
BP_TRACK_DIRTY=0
bp_select_surface=sg_surface
.include "../graphics/vdc-client.inc"
sg_vdc_fault=vd_fault
sg_vdc_live=vd_live
sg_mouse_x=pm_x
sg_mouse_y=pm_y
sg_handle: .fill 4,0
sg_bitmap: .byte 0
sg_error: .byte 0
sg_mode: .byte 0
sg_hit: .byte $ff
sg_row: .byte 0
sg_column: .byte 0
sg_high: .byte 0
sg_changed: .byte 0
sg_dirty: .fill 25,0
sg_chars: .fill 1000,32
sg_colors: .fill 1000,$16
sg_text_rows:
        .for row=0,row<25,row+=1
        .word row*40
        .endfor
sg_bitmap_rows:
        .for row=0,row<25,row+=1
        .word row*320
        .endfor
sg_font=$ae11                   ; the module window ($ae00), its 16-byte header and rts
sm_display_fault: .byte 0
.include "modules.inc"
