draw_text_scene:
        lda #<text_commands
        sta text_read+1
        lda #>text_commands
        sta text_read+2
        lda #text_commands_count
        sta text_remaining
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
        lda text_commands,x
        rts
text_remaining: .byte 0
