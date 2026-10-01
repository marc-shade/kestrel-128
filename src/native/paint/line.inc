; Connected pencil/eraser segments. Endpoints are image pixels. One caller's
; stroke may contain many segments; pd_stroke controls the single undo copy.
pd_line:
        lda pd_end_x+1
        cmp #2
        bcs pd_line_bad
        cmp #1
        bne +
        lda pd_end_x
        cmp #64
        bcs pd_line_bad
+       lda pd_end_y
        cmp #200
        bcs pd_line_bad
        jsr pd_point          ; validates the start and tool before any segment
        bcs pd_line_return
        lda pd_changed
        sta pd_line_changed
        lda #1
        sta pd_sx
        sta pd_sy
        sec
        lda pd_end_x
        sbc pd_x
        sta pd_dx
        lda pd_end_x+1
        sbc pd_x+1
        sta pd_dx+1
        bpl +
        lda #$ff
        sta pd_sx
        lda #0
        sec
        sbc pd_dx
        sta pd_dx
        lda #0
        sbc pd_dx+1
        sta pd_dx+1
+       lda pd_end_y
        sec
        sbc pd_y
        bcs +
        lda #$ff
        sta pd_sy
        lda pd_y
        sec
        sbc pd_end_y
+       sta pd_dy
        lda pd_dx
        sec
        sbc pd_dy
        sta pd_line_error
        lda pd_dx+1
        sbc #0
        sta pd_line_error+1
pd_line_next:
        lda pd_x
        cmp pd_end_x
        bne pd_line_advance
        lda pd_x+1
        cmp pd_end_x+1
        bne pd_line_advance
        lda pd_y
        cmp pd_end_y
        bne pd_line_advance
        lda #0
        clc
pd_line_return:
        rts
pd_line_bad:
        lda #N_BADARG
        sec
        rts
pd_line_advance:
        lda pd_line_error
        asl
        sta pd_twice
        lda pd_line_error+1
        rol
        sta pd_twice+1
        ; Twice(error) > -dy, evaluated as a bounded signed sum > 0.
        lda pd_twice
        clc
        adc pd_dy
        sta pd_test
        lda pd_twice+1
        adc #0
        bmi pd_line_y
        ora pd_test
        beq pd_line_y
        lda pd_line_error
        sec
        sbc pd_dy
        sta pd_line_error
        lda pd_line_error+1
        sbc #0
        sta pd_line_error+1
        lda pd_sx
        bmi pd_line_left
        inc pd_x
        bne pd_line_y
        inc pd_x+1
        bne pd_line_y
pd_line_left:
        lda pd_x
        bne +
        dec pd_x+1
+       dec pd_x
pd_line_y:
        ; Twice(error) < dx, evaluated as dx - twice(error) > 0.
        lda pd_dx
        sec
        sbc pd_twice
        sta pd_test
        lda pd_dx+1
        sbc pd_twice+1
        bmi pd_line_pixel
        ora pd_test
        beq pd_line_pixel
        lda pd_line_error
        clc
        adc pd_dx
        sta pd_line_error
        lda pd_line_error+1
        adc pd_dx+1
        sta pd_line_error+1
        lda pd_y
        clc
        adc pd_sy
        sta pd_y
pd_line_pixel:
        jsr pd_point
        bcs pd_line_return
        lda pd_changed
        ora pd_line_changed
        sta pd_line_changed
        jmp pd_line_next
pd_end_x: .word 0
pd_end_y: .byte 0
pd_line_changed: .byte 0
pd_dx: .word 0
pd_dy: .byte 0
pd_sx: .byte 0
pd_sy: .byte 0
pd_line_error: .word 0
pd_twice: .word 0
pd_test: .byte 0
