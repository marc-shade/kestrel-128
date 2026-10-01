; Shared interpreters for the three Paint scenes. A/X=data, Y=command count.
pa_scene_rects:
        sta scene_read+1
        stx scene_read+2
        sty scene_remaining
        jsr gfx_bind
        bcs scene_return
scene_next:
        ldx #7
scene_copy:
        jsr scene_read
        sta gfx_x0,x
        dex
        bpl scene_copy
        ldx #8
        jsr scene_read
        bne scene_colors
        inx
        jsr scene_read
        sta gfx_pen
        jsr gfx_rect
        jmp scene_result
scene_colors:
        cmp #2
        beq scene_clip
        inx
        jsr scene_read
        sta gfx_color
        jsr gfx_colors
        jmp scene_result
scene_clip:
        jsr gfx_set_clip
scene_result:
        bcs scene_return
        clc
        lda scene_read+1
        adc #10
        sta scene_read+1
        bcc +
        inc scene_read+2
+       dec scene_remaining
        bne scene_next
        lda #0
        clc
scene_return:
        rts
scene_read:
        lda $ffff,x
        rts
scene_remaining:.byte 0

pa_scene_text:
        sta text_read+1
        stx text_read+2
        sty text_remaining
text_scene_next:
        ldx #3
text_scene_coords:
        jsr text_read
        sta gfx_x0,x
        dex
        bpl text_scene_coords
        ldx #4
        jsr text_read
        sta gfx_pen
        inx
        jsr text_read
        sta gfx_text_length
        lda #6
        jsr text_advance
        ldx #0
text_scene_copy:
        jsr text_read
        sta gfx_text_buffer,x
        inx
        cpx gfx_text_length
        bne text_scene_copy
        jsr gfx_text
        bcs text_scene_done
        lda gfx_text_length
        jsr text_advance
        dec text_remaining
        bne text_scene_next
        lda #0
        clc
        rts
text_scene_done:
        rts
text_advance:
        clc
        adc text_read+1
        sta text_read+1
        bcc +
        inc text_read+2
+       rts
text_read:
        lda $ffff,x
        rts
text_remaining: .byte 0
