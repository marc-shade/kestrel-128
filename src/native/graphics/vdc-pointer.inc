; A=row, X=byte column -> linear bitmap address, preserving Y.
vd_xy:
        stx vd_column
        ldx #0
        stx vd_addr+1
        asl
        rol vd_addr+1
        asl
        rol vd_addr+1
        asl
        rol vd_addr+1
        asl
        rol vd_addr+1
        sta vd_math
        ldx vd_addr+1
        stx vd_math+1
        asl
        rol vd_addr+1
        asl
        rol vd_addr+1
        clc
        adc vd_math
        sta vd_addr
        lda vd_addr+1
        adc vd_math+1
        clc
        adc vd_base
        sta vd_addr+1
        lda vd_addr
        clc
        adc vd_column
        sta vd_addr
        bcc +
        inc vd_addr+1
+       rts
vd_next_row:
        lda vd_addr
        clc
        adc #80
        sta vd_addr
        bcc +
        inc vd_addr+1
+       rts

vd_poll:
        lda vd_live
        beq vd_poll_done
        lda vd_fault
        bne vd_poll_done
        lda pm_seen
        cmp vd_pointer_visible
        bne vd_pointer_change
        lda pm_seen
        beq vd_poll_done
        lda pm_x
        cmp vd_pointer_x
        bne vd_pointer_change
        lda pm_x+1
        cmp vd_pointer_x+1
        bne vd_pointer_change
        lda pm_y
        cmp vd_pointer_y
        beq vd_poll_done
vd_pointer_change:
        jsr vd_gate
        lda #0
        sta vd_old_rows       ; nothing to reuse unless a shown pointer is hidden
        jsr vd_hide_pointer
        lda pm_seen
        beq vd_poll_done
        lda pm_x
        sta vd_pointer_x
        lda pm_x+1
        sta vd_pointer_x+1
        lda pm_y
        sta vd_pointer_y
        jsr vd_pointer_geometry
        lda vd_pointer_y
        sec
        sbc vd_old_y
        sta vd_old_y          ; now the new pointer's first row within the old
        lda vd_column
        cmp vd_old_column
        beq vd_pointer_draw_row
        lda #0
        sta vd_old_rows
vd_pointer_draw_row:
        ; A row the hidden pointer covered in the same byte column now holds
        ; exactly its saved background, so that is reused, not read back.
        ldx vd_pointer_at
        lda vd_pointer_line
        clc
        adc vd_old_y
        cmp vd_old_rows
        bcs vd_pointer_read
        lda vd_under,x
        sta N_BUFFER
        lda vd_under+1,x
        sta N_BUFFER+1
        bcc vd_pointer_mask   ; carry is still clear from the compare
vd_pointer_read:
        jsr vd_read_block
vd_pointer_mask:
        ldx vd_pointer_line
        lda vd_pointer_hi,x
        sta vd_mask
        lda vd_pointer_lo,x
        sta vd_mask+1
        ldx vd_pointer_shift
        beq +
-       lsr vd_mask
        ror vd_mask+1
        dex
        bne -
+       ldx vd_pointer_at
        ldy #0
-       lda N_BUFFER,y
        sta vd_under,x
        eor vd_mask,y
        sta N_BUFFER,y
        inx
        iny
        cpy vd_count
        bne -
        jsr vd_pointer_next
        bne vd_pointer_draw_row
        lda #1
        sta vd_pointer_visible
vd_poll_done:
        clc
        rts
vd_hide_pointer:
        lda vd_pointer_visible
        beq vd_poll_done
        jsr vd_pointer_geometry
        lda vd_pointer_rows
        sta vd_old_rows
        lda vd_column
        sta vd_old_column
        lda vd_pointer_y
        sta vd_old_y
vd_pointer_restore_row:
        ldx vd_pointer_at
        ldy #0
-       lda vd_under,x
        sta N_BUFFER,y
        inx
        iny
        cpy vd_count
        bne -
        jsr vd_pointer_next
        bne vd_pointer_restore_row
        lda #0
        sta vd_pointer_visible
        rts
; Write the row, then step to the next. Each screen row keeps its saved bytes
; in slot (row mod 16)*2, so an old and a new pointer share slots safely.
vd_pointer_next:
        jsr vd_write_block
        jsr vd_next_row
        inc vd_pointer_line
        lda vd_pointer_at
        clc
        adc #2
        and #31
        sta vd_pointer_at
        dec vd_pointer_rows
        rts
vd_pointer_geometry:
        lda vd_pointer_x
        asl
        and #7
        sta vd_pointer_shift
        lda vd_pointer_x+1
        lsr
        lda vd_pointer_x
        ror
        lsr                   ; logical x*2/8 = x/4, full 640-pixel address range
        tax
        lda #80
        stx vd_column
        sec
        sbc vd_column
        cmp #2                ; the shape never reaches a third byte
        bcc +
        lda #2
+       sta vd_count
        lda #200
        sec
        sbc vd_pointer_y
        cmp #16
        bcc +
        lda #16
+       sta vd_pointer_rows
        lda vd_pointer_y
        jsr vd_xy
        lda vd_pointer_y
        and #15
        asl
        sta vd_pointer_at
        lda #0
        sta vd_pointer_line
        rts

