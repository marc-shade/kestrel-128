; Keep keyboard, display descriptors and module dispatch in the editor core.
; The search module also owns the graphical renderer; its modal search can
; call that renderer directly without nesting a checked N_MCALL gate.
PM_KEYS_OWNED=1
PM_KEYS_EXTERNAL=1
eg_render:
        ldx eg_collect
        bne eg_return
        sta eg_operation
        jsr eg_ensure
        bcs eg_return
        jsr eg_call
        bcs eg_return
        jmp eg_vdc_sync
eg_ensure:
        lda ed_module_kind
        cmp #2
        beq eg_ready
        lda eg_attempted
        bne eg_unavailable
        lda #2
        jsr ed_module_load
        php
        pha
        lda #1
        sta eg_attempted
        pla
        plp
        rts
eg_unavailable:
        sec
        rts
eg_ready:
        clc
eg_return:
        rts
eg_call:
        lda eg_inside
        bne eg_direct
        lda #1
        sta eg_inside
        jsr N_MCALL
        php
        pha
        lda #0
        sta eg_inside
        pla
        plp
        rts
eg_direct:
        jmp eg_entry
eg_input:
        jsr eg_vdc_guard
        sta eg_key
        lda eg_bitmap
        bne +
        lda es_active
        beq eg_key_return
        lda ed_mode
        bne eg_key_return
        lda eg_key
        beq eg_key_return
        cmp #12
        beq eg_key_return
        cmp #27
        beq eg_selection_clear
        cmp #7
        beq eg_selection_clear
        lda #12
        sta ed_status
        lda #254
        bne eg_selection_result
eg_selection_clear:
        jsr es_clear
        lda #255
eg_selection_result:
        sta eg_key
        jmp eg_key_return
+       lda eg_key
        bne eg_input_call
        bit $d011
        bmi eg_key_return
        lda $d012
        cmp #160
        bcs eg_key_return
        lda $a2
        cmp pm_tick
        bne eg_input_call
        lda pm_pending
        beq eg_key_return
eg_input_call:
        lda #0
        sta N_READY
        lda #3
        sta eg_operation
        jsr eg_call
        bcs eg_key_return
        sta eg_key
eg_key_return:
        jsr eg_vdc_sync
        lda eg_key
        jmp eg_vdc_guard
eg_close:
        jsr eg_vdc_close
        bcs eg_return
eg_close_view:
        lda ed_module_kind
        cmp #2
        bne eg_return
        lda #4
        sta eg_operation
        jmp eg_call
eg_screen_start:
        lda eg_collect
        bne +
        lda vd_phase
        beq eg_screen_bitmap
        lda #2
        rts
eg_screen_bitmap:
        lda eg_bitmap
        rts
+       lda #0
        rts
eg_footer:
        lda vd_phase
        bne eg_return
        lda eg_collect
        bne eg_return
        lda eg_bitmap
        beq eg_return
        lda #7
        sta eg_operation
        jmp eg_call
eg_plot:
        lda eg_collect
        beq +
        bcc eg_plot_set
        ldx eg_row
        ldy eg_column
        rts
eg_plot_set:
        stx eg_row
        sty eg_column
        rts
+       jmp $fff0

; A failed picker keeps its descriptors in that module until Browse retries.
; An uncertain loader source closes through the module service before any
; global file release can invalidate its private descriptor.
eg_cleanup:
        lda ed_module_kind
        cmp #1
        bne eg_cleanup_loader
        lda fd_iec_handle
        ora bu_cursor
        bne eg_cleanup_retained
        ldx #36
-       lda b_cache,x
        bne eg_cleanup_retained
        dex
        dex
        dex
        dex
        bpl -
        clc
        rts
eg_cleanup_loader:
        lda ed_module_kind
        bne eg_ready
        lda N_MSTATE
        beq eg_ready
        jmp N_MCLOSE
eg_cleanup_retained:
        lda #N_IOERROR
        sec
        rts

eg_operation: .byte 0
eg_inside: .byte 0
eg_collect: .byte 0
eg_attempted: .byte 0
eg_bitmap: .byte 0
eg_handle: .fill 4,0
eg_error: .byte 0
eg_key: .byte 0

ed_graphics_retry:
        lda eh_available
        bne +
        sta dm_mode
+
        lda vd_phase
        bne +
        lda #0
        sta eg_vdc_attempted
        sta eg_vdc_warned
+
        lda #0
        sta eg_attempted
        lda eg_bitmap
        bne +
        lda ed_module_kind
        cmp #2
        bne +
        lda #0
        sta eg_started
+       jmp ed_refresh
