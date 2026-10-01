draw_scene:
        jsr gfx_bind
        bcs scene_return
        lda #<scene_commands
        sta scene_read+1
        lda #>scene_commands
        sta scene_read+2
        lda #scene_commands_count
        sta scene_remaining
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
        jmp draw_text_scene
scene_return:
        rts
scene_read:
        lda scene_commands,x
        rts
scene_remaining:.byte 0
