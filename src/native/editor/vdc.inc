; Core state outlives the mutually exclusive graphics/picker modules.
eg_select_surface:
        lda N_CURRENT
        sta N_OWNER
        ldx #3
-       lda eg_handle,x
        sta N_HANDLE,x
        dex
        bpl -
        rts
eg_vdc_sync:
        lda #0
        sta N_READY
        lda eg_bitmap
        bne eg_graphical_pointer
        lda ed_module_kind
        cmp #1
        bne eg_no_surface
        lda pg_bitmap
        beq eg_no_surface
        lda picker_gui.pgm_seen
        sta eg_pointer_visible
        lda picker_gui.pgm_x
        sta eg_pointer_x
        lda picker_gui.pgm_x+1
        sta eg_pointer_x+1
        lda picker_gui.pgm_y
        jmp eg_pointer_y_ready
eg_graphical_pointer:
        lda pm_seen
        sta eg_pointer_visible
        lda pm_x
        sta eg_pointer_x
        lda pm_x+1
        sta eg_pointer_x+1
        lda pm_y
eg_pointer_y_ready:
        sta eg_pointer_y
        lda eg_vdc_attempted
        bne eg_vdc_present
        inc eg_vdc_attempted
        jsr vd_open
        bcc eg_pointer_sync
        jsr eg_vdc_close
eg_vdc_present:
        jsr vm_present
eg_pointer_sync:
        jmp vd_poll
eg_no_surface:
        lda vd_phase
        beq eg_vdc_return
        jmp eg_vdc_close
eg_vdc_full:
        lda #1
        sta vm_pending
        ldx #24
-       sta vm_rows,x
        dex
        bpl -
eg_vdc_return:
        rts

; Retain edits, search and file I/O at their current step while display
; recovery is pending. Key zero would let ed_cancel_check continue the work.
eg_vdc_guard:
        sta eg_guard_key
        lda dm_fault
        bne eg_guard_warning
        lda vd_phase
        beq eg_guard_return
        lda vd_fault
        beq eg_guard_return
eg_guard_warning:
        lda ed_module_kind
        cmp #2
        bne eg_guard_key_ready
        lda eg_vdc_warned
        bne eg_guard_key_ready
        inc eg_vdc_warned
        lda #0
        sta N_READY
        lda #8
        sta eg_operation
        jsr eg_call
eg_guard_key_ready:
        lda eg_guard_key
        cmp #27
        bne eg_guard_wait
        lda dm_fault
        beq +
        jsr dm_stop
        bcs eg_guard_wait
+
        jsr eg_vdc_close
        bcs eg_guard_wait
        ; A recovered Escape reaches the core without another module input
        ; dispatch. Honor the document's selection before considering exit.
        lda ed_mode
        bne eg_guard_return
        lda es_active
        beq eg_guard_return
        jsr es_clear
        lda #255
        sta eg_last_view       ; replace the pause notice when staying in the document
        sta eg_guard_key
        bne eg_guard_return
eg_guard_wait:
        lda #1
        sta N_READY
        jsr N_KEYIN
        sta eg_guard_key
        lda #0
        sta N_READY
        jmp eg_guard_key_ready
eg_guard_return:
        lda eg_guard_key
        rts

; Restore can return into a partial modal redraw. Repaint the full text view
; only after the current file/search operation has returned to the input loop.
eg_vdc_close:
        lda vd_phase
        beq +
        lda #1
        sta eg_text_pending
+       jmp vd_close
eg_repair_text:
        lda vd_phase
        bne eg_vdc_return
        lda eg_text_pending
        beq eg_vdc_return
        lda #0
        sta eg_text_pending
        jmp ed_show
eg_text_pending: .byte 0
eg_vdc_attempted: .byte 0
eg_vdc_warned: .byte 0
eg_guard_key: .byte 0
eg_pointer_visible: .byte 0
eg_pointer_x: .word 0
eg_pointer_y: .byte 0
