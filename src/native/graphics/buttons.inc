; Foreground button focus and hit testing on an owned VIC surface.
; Caller supplies ui_rects: eight bytes per half-open unsigned pixel rectangle,
; ui_button_count (at most 32), ui_first/ui_limit, ui_selected and gfx binding.
; Rectangles must be on-screen; ui_paint requires 8-pixel-aligned edges.
; ui_hit: ui_x (word), ui_y (byte) -> X=index or $ff. No heap transfers.
; ui_paint: X=index -> gfx_colors status; all registers/heap args scratch.
.cerror ui_button_count > 32, "button table exceeds indexed coordinate range"
ui_hit:
        ldx ui_first
ui_hit_next:
        cpx ui_limit
        bcs ui_missed
        txa
        asl
        asl
        asl
        tay
        lda ui_x
        cmp ui_rects,y
        lda ui_x+1
        sbc ui_rects+1,y
        bcc ui_hit_skip
        lda ui_x
        cmp ui_rects+4,y
        lda ui_x+1
        sbc ui_rects+5,y
        bcs ui_hit_skip
        lda ui_y
        cmp ui_rects+2,y
        bcc ui_hit_skip
        cmp ui_rects+6,y
        bcc ui_hit_done
ui_hit_skip:
        inx
        bne ui_hit_next
ui_missed:
        ldx #$ff
ui_hit_done:
        rts

ui_paint:
        lda #$1b
        cpx ui_selected
        bne +
        lda #$07
+       sta gfx_color
        txa
        asl
        asl
        asl
        tay
        ldx #0
ui_cells:
        lda ui_rects,y
        sta ui_value
        lda ui_rects+1,y
        lsr
        ror ui_value
        lsr
        ror ui_value
        lsr
        ror ui_value
        lda ui_value
        sta gfx_x0,x
        lda #0
        sta gfx_x0+1,x
        iny
        iny
        inx
        inx
        cpx #8
        bne ui_cells
        jmp gfx_colors

ui_focus:
        stx ui_next
        ldx ui_selected
        cpx ui_next
        bne +
        clc
        rts
+
        lda ui_next
        sta ui_selected
        jsr ui_paint
        bcs ui_focus_done
        ldx ui_selected
        jmp ui_paint
ui_focus_done:
        rts

ui_x: .word 0
ui_y: .byte 0
ui_value: .byte 0
ui_next: .byte 0
ui_first: .byte 0
ui_limit: .byte 0
