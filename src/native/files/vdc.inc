; Core state outlives the mutually exclusive graphics/picker modules.
fg_select_surface:
        lda N_CURRENT
        sta N_OWNER
        ldx #3
-       lda fg_surface,x
        sta N_HANDLE,x
        dex
        bpl -
        rts
fg_vdc_sync:
        lda #0
        sta N_READY
        lda fg_bitmap
        bne fg_graphical_pointer
        lda fg_kind
        cmp #2
        bne fg_no_surface
        lda copy_picker.pg_bitmap
        beq fg_no_surface
        lda copy_picker.picker_gui.pgm_seen
        sta fg_pointer_visible
        lda copy_picker.picker_gui.pgm_x
        sta fg_pointer_x
        lda copy_picker.picker_gui.pgm_x+1
        sta fg_pointer_x+1
        lda copy_picker.picker_gui.pgm_y
        jmp fg_pointer_y_ready
fg_graphical_pointer:
        lda pm_seen
        sta fg_pointer_visible
        lda pm_x
        sta fg_pointer_x
        lda pm_x+1
        sta fg_pointer_x+1
        lda pm_y
fg_pointer_y_ready:
        sta fg_pointer_y
        lda fg_vdc_attempted
        bne fg_vdc_present
        inc fg_vdc_attempted
        jsr vd_open
        bcc fg_pointer_sync
        jsr vd_close
fg_vdc_present:
        jsr vm_present
fg_pointer_sync:
        jmp vd_poll
fg_no_surface:
        lda vd_phase
        beq fg_vdc_return
        jmp vd_close
fg_vdc_full:
        lda #1
        sta vm_pending
        ldx #24
-       sta vm_rows,x
        dex
        bpl -
fg_vdc_return:
        rts

; Retain an in-progress copy at its current chunk while display recovery is
; pending. Returning key zero here would let fc_cancel continue file I/O.
fg_vdc_guard:
        sta fg_guard_key
        lda vd_phase
        beq fg_guard_return
        lda vd_fault
        beq fg_guard_return
        lda fg_kind
        cmp #1
        bne fg_guard_key_ready
        lda fg_vdc_warned
        bne fg_guard_key_ready
        inc fg_vdc_warned
        lda #0
        sta N_READY
        lda #5
        sta fg_operation
        jsr fg_call
fg_guard_key_ready:
        lda fg_guard_key
        cmp #27
        bne fg_guard_wait
        jsr vd_close
        bcc fg_guard_return
fg_guard_wait:
        lda #1
        sta N_READY
        jsr N_KEYIN
        sta fg_guard_key
        lda #0
        sta N_READY
        jmp fg_guard_key_ready
fg_guard_return:
        lda fg_guard_key
        rts
fg_vdc_attempted: .byte 0
fg_vdc_warned: .byte 0
fg_guard_key: .byte 0
fg_pointer_visible: .byte 0
fg_pointer_x: .word 0
fg_pointer_y: .byte 0
