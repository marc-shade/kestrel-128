; One provider and screen backup survive drawing, dialogs and the picker.
pa_vdc_sync:
        lda pa_bitmap
        ora paint_picker.pg_bitmap
        beq pa_vdc_return
        lda $d015
        and #3
        beq +
        lda #1
+       sta pa_vdc_pointer
        lda pa_vdc_attempted
        bne pa_vdc_present
        inc pa_vdc_attempted
        jsr vd_open
        bcc pa_vdc_pointer_sync
        jsr vd_close
pa_vdc_present:
        jsr vm_present
pa_vdc_pointer_sync:
        jsr vd_poll
        lda vd_phase
        beq pa_vdc_return
        lda vd_fault
        beq pa_vdc_return
        lda paint_picker.fd_active
        bne pa_vdc_return
        lda pa_status
        cmp #14
        beq pa_vdc_return
        lda #14
        sta pa_status
        jmp pa_message
pa_vdc_full:
        lda #1
        sta vm_pending
        ldx #24
-       sta vm_rows,x
        dex
        bpl -
pa_vdc_return:
        rts
pa_vdc_attempted: .byte 0
pa_vdc_pointer: .byte 0
