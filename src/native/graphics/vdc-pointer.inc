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
vd_pointer_draw_row:
        jsr vd_read_block
        ldx vd_pointer_line
        lda vd_pointer_hi,x
        sta vd_mask
        lda vd_pointer_lo,x
        sta vd_mask+1
        lda #0
        sta vd_mask+2
        ldx vd_pointer_shift
        beq +
-       lsr vd_mask
        ror vd_mask+1
        ror vd_mask+2
        dex
        bne -
+       ldy #0
        ldx vd_pointer_at
-       lda N_BUFFER,y
        sta vd_under,x
        eor vd_mask,y
        sta N_BUFFER,y
        inx
        iny
        cpy vd_count
        bne -
        stx vd_pointer_at
        jsr vd_write_block
        jsr vd_next_row
        inc vd_pointer_line
        dec vd_pointer_rows
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
vd_pointer_restore_row:
        ldy #0
        ldx vd_pointer_at
-       lda vd_under,x
        sta N_BUFFER,y
        inx
        iny
        cpy vd_count
        bne -
        stx vd_pointer_at
        jsr vd_write_block
        jsr vd_next_row
        dec vd_pointer_rows
        bne vd_pointer_restore_row
        lda #0
        sta vd_pointer_visible
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
        cmp #3
        bcc +
        lda #3
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
        lda #0
        sta vd_pointer_line
        sta vd_pointer_at
        rts

