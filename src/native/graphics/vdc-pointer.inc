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
        jsr vd_pointer_step
        bcc vd_poll_done
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
        bcc vd_pointer_mask
        jsr vd_pointer_read
vd_pointer_mask:
        lda vd_pointer_line
        clc
        adc vd_pointer_shift
        tay
        lda vd_under,x
        eor vd_mask_hi,y
        sta vd_mask
        lda vd_under+1,x
        eor vd_mask_lo,y
        sta vd_mask+1
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
        lda vd_under,x
        sta vd_mask
        lda vd_under+1,x
        sta vd_mask+1
        jsr vd_pointer_next
        bne vd_pointer_restore_row
        lda #0
        sta vd_pointer_visible
        rts
; The background at vd_addr -> the row's slot X = vd_pointer_at. This and
; vd_pointer_next run for every pointer row, so the data accesses are inline.
; Setting R18/R19 reloads the 8563's read latch (the capture probe reads
; right after its seek on the reference C128), so no priming read is needed.
vd_pointer_read:
        jsr vd_seek
        ldx vd_pointer_at
        bit $d600
        bmi +
        jsr vd_wait
+       lda $d601
        sta vd_under,x
        lda vd_count
        lsr
        bcs vd_pointer_read_done ; one byte at column 79
        bit $d600
        bmi +
        jsr vd_wait
+       lda $d601
        sta vd_under+1,x
vd_pointer_read_done:
        rts
; Write the row's bytes (vd_mask), then step to the next. Each screen row
; keeps its saved bytes in slot (row mod 16)*2, so an old and a new pointer
; share slots safely.
vd_pointer_next:
        jsr vd_seek
        lda vd_mask
        bit $d600
        bmi +
        jsr vd_wait
+       sta $d601
        lda vd_count
        lsr
        bcs vd_pointer_written ; one byte at column 79
        lda vd_mask+1
        bit $d600
        bmi +
        jsr vd_wait
+       sta $d601
vd_pointer_written:
        lda vd_addr
        clc
        adc #80
        sta vd_addr
        bcc +
        inc vd_addr+1
+       inc vd_pointer_line
        lda vd_pointer_at
        clc
        adc #2
        and #31
        sta vd_pointer_at
        dec vd_pointer_rows
        rts
; A move of a shown pointer to an overlapping place: both two bytes wide,
; byte columns at most one apart, first rows less than 16 apart. Every row
; either pointer covers is visited once, in the direction of the move so a
; row's slot is reused only after the row 16 away has restored from it. A row
; both cover takes one write run (old background byte, if any, and the new
; pointer) and reads at most the one byte the old pointer did not hold.
; Carry set: not such a move, and nothing has changed.
vd_get .macro
        bit $d600
        bmi +
        jsr vd_wait
+       lda $d601
.endm
vd_put .macro
        bit $d600
        bmi +
        jsr vd_wait
+       sta $d601
.endm
vd_pointer_step:
        lda vd_pointer_visible
        beq vd_step_refused
        lda pm_seen
        beq vd_step_refused
        jsr vd_pointer_span      ; the shown pointer
        lda vd_count
        cmp #2
        bne vd_step_refused
        lda vd_column
        sta vd_old_column
        lda vd_pointer_rows
        sta vd_old_rows
        lda vd_pointer_y
        sta vd_old_y
        lda vd_pointer_x
        sta vd_prev_x
        lda vd_pointer_x+1
        sta vd_prev_x+1
        lda pm_x
        sta vd_pointer_x
        lda pm_x+1
        sta vd_pointer_x+1
        lda pm_y
        sta vd_pointer_y
        jsr vd_pointer_span      ; the new pointer
        lda vd_count
        cmp #2
        bne vd_step_restore
        lda vd_column
        sec
        sbc vd_old_column
        sta vd_step_dc
        beq +
        cmp #1
        beq +
        cmp #$ff
        bne vd_step_restore
+       lda vd_pointer_y
        sec
        sbc vd_old_y
        bcs vd_step_down
        cmp #$f1
        bcs vd_step_up
vd_step_restore:
        lda vd_prev_x
        sta vd_pointer_x
        lda vd_prev_x+1
        sta vd_pointer_x+1
        lda vd_old_y
        sta vd_pointer_y
vd_step_refused:
        sec
        rts
vd_step_down:
        cmp #16
        bcs vd_step_restore
        lda #1
        sta vd_step_dir
        lda vd_old_y          ; first row: the old pointer's
        sta vd_step_row
        jsr vd_step_end
        sec
        sbc vd_old_y
        bne vd_step_start
vd_step_up:
        lda #$ff
        sta vd_step_dir
        jsr vd_step_end
        sec
        sbc vd_pointer_y
        tax
        clc
        adc vd_pointer_y
        sec
        sbc #1
        sta vd_step_row       ; first row: the last either covers
        txa
vd_step_start:
        sta vd_step_rows
        ldx vd_column         ; base byte column: the leftmost of the two
        lda vd_step_dc
        bpl +
        lda #1
        sta vd_step_old
        lda #0
        sta vd_step_new
        beq vd_step_base
+       lda #0
        sta vd_step_new
        sta vd_step_old
        lda vd_step_dc
        beq vd_step_base
        sta vd_step_new
        ldx vd_old_column
vd_step_base:
        lda vd_step_row
        jsr vd_xy
        lda vd_addr
        sta vd_step_addr
        lda vd_addr+1
        sta vd_step_addr+1
vd_step_each:
        lda vd_step_row
        and #15
        asl
        sta vd_pointer_at
        tax
        lda vd_step_row
        sec
        sbc vd_pointer_y
        cmp vd_pointer_rows
        bcc vd_step_new_row
        lda vd_step_old       ; the old pointer alone: its background
        jsr vd_step_seek
        ldx vd_pointer_at
        lda vd_under,x
        #vd_put
        lda vd_under+1,x
        #vd_put
        jmp vd_step_next
vd_step_new_row:
        clc
        adc vd_pointer_shift
        sta vd_pointer_line   ; mask table index
        lda vd_step_row
        sec
        sbc vd_old_y
        cmp vd_old_rows
        bcs vd_step_fresh
        lda vd_step_dc
        beq vd_step_same
        bmi vd_step_left
        lda vd_under,x        ; one byte right: old byte 1 is new byte 0
        sta vd_step_under
        lda vd_under+1,x
        sta vd_under,x
        lda #2
        jsr vd_step_seek
        ldx vd_pointer_at
        #vd_get
        sta vd_under+1,x
        lda #0
        jsr vd_step_seek
        lda vd_step_under
        #vd_put
        jsr vd_step_draw
        jmp vd_step_next
vd_step_left:
        lda vd_under+1,x      ; one byte left: old byte 0 is new byte 1
        sta vd_step_under
        lda vd_under,x
        sta vd_under+1,x
        lda #0
        jsr vd_step_seek
        ldx vd_pointer_at
        #vd_get
        sta vd_under,x
        lda #0
        jsr vd_step_seek
        jsr vd_step_draw
        lda vd_step_under
        #vd_put
        jmp vd_step_next
vd_step_fresh:
        lda vd_step_new       ; the new pointer alone
        jsr vd_step_seek
        ldx vd_pointer_at
        #vd_get
        sta vd_under,x
        #vd_get
        sta vd_under+1,x
        lda vd_step_new
vd_step_same:                 ; same column: A = 0, the slot already holds it
        jsr vd_step_seek
        jsr vd_step_draw
vd_step_next:
        dec vd_step_rows
        beq vd_step_done
        lda vd_step_dir
        bmi +
        inc vd_step_row
        lda vd_step_addr
        clc
        adc #80
        sta vd_step_addr
        bcc vd_step_jump
        inc vd_step_addr+1
        bcs vd_step_jump
+       dec vd_step_row
        lda vd_step_addr
        sec
        sbc #80
        sta vd_step_addr
        bcs vd_step_jump
        dec vd_step_addr+1
vd_step_jump:
        jmp vd_step_each
vd_step_done:
        clc
        rts
; The row after the last either pointer covers.
vd_step_end:
        lda vd_old_y
        clc
        adc vd_old_rows
        sta vd_step_old
        lda vd_pointer_y
        clc
        adc vd_pointer_rows
        cmp vd_step_old
        bcs +
        lda vd_step_old
+       rts
; A = byte offset from the row's base column -> R18/R19, then R31 selected.
; Clobbers X and Y.
vd_step_seek:
        clc
        adc vd_step_addr
        tay
        lda vd_step_addr+1
        adc #0
        ldx #18
        stx $d600
        #vd_put
        inx
        stx $d600
        tya
        #vd_put
        ldx #31
        stx $d600
        rts
; The new pointer's two bytes over the slot's background.
vd_step_draw:
        ldx vd_pointer_at
        ldy vd_pointer_line
        lda vd_under,x
        eor vd_mask_hi,y
        #vd_put
        lda vd_under+1,x
        eor vd_mask_lo,y
        #vd_put
        rts
vd_pointer_geometry:
        jsr vd_pointer_span
        lda vd_pointer_y
        jsr vd_xy
        lda vd_pointer_y
        and #15
        asl
        sta vd_pointer_at
        lda #0
        sta vd_pointer_line
        rts
; Shift, byte column (also left in X), byte count and rows of the pointer
; at vd_pointer_x/y.
vd_pointer_span:
        lda vd_pointer_x
        asl
        and #7
        asl
        asl
        asl
        sta vd_pointer_shift  ; shift 0, 2, 4 or 6 -> mask table offset shift*8
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
        rts
