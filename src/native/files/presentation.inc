; Files retains all browser/copy state in its core. The graphics and picker
; occupy one checked module window; never replace a picker with live handles.
fg_init:
        jsr fg_workspace
        bcs fg_return
        jsr nk_install
        lda #0
        sta fg_attempted
        sta fg_kind
        sta fg_bitmap
        sta fg_picker_active
        sta fg_error
        sta fg_searching
        jsr fg_ensure_gui
        clc
        rts
fg_retry:
        lda vd_phase
        bne +
        lda #0
        sta fg_vdc_attempted
        sta fg_vdc_warned
+       lda #0
        sta fg_attempted
        lda fg_bitmap
        bne +
        lda fg_kind
        cmp #1
        bne +
        lda #4
        sta fg_operation
        jmp fg_call
+
        rts
fg_browser_draw:
        lda fg_collect
        bne fg_return
        lda #0
        sta fg_mode
        jmp fg_draw
fg_copy_draw:
        lda fg_collect
        bne fg_return
        lda #1
        sta fg_mode
fg_draw:
        jsr fg_ensure_gui
        bcs fg_return
        lda #0
        sta fg_operation
        jsr fg_call
        bcs fg_return
        jmp fg_vdc_sync
fg_ensure_gui:
        lda fg_kind
        cmp #1
        beq fg_token
        lda fg_attempted
        bne fg_unavailable
        lda #1
        sta fg_attempted
        jsr fg_picker_clean
        bcs fg_failed
        lda #1
        jmp fg_load
fg_unavailable:
        sec
fg_return:
        rts
fg_input:
        jsr fg_vdc_guard
        sta fg_key
        lda fg_bitmap
        beq fg_key_return
        lda fg_key
        bne fg_input_call
        ; A completed sample needs no further module calls this jiffy.
        ; The module gate itself takes raster time: let pm_poll establish
        ; and check the conversion delay after that gate, not before it.
        bit $d011
        bmi fg_key_return
        lda $d012
        cmp #160
        bcs fg_key_return
        lda $a2
        cmp pm_tick
        bne fg_input_call
        lda pm_pending
        beq fg_key_return
fg_input_call:
        ; A checked module call changes gate scratch even when it only polls
        ; the pointer. Publish idle again after the complete call returns.
        lda #0
        sta N_READY
        lda #1
        sta fg_operation
        jsr fg_call
        bcs fg_key_return
        sta fg_key
fg_key_return:
        jsr fg_vdc_sync
        lda fg_key
        jmp fg_vdc_guard
fg_close_view:
        lda fg_kind
        cmp #1
        bne fg_close_done
        lda #2
        sta fg_operation
        jsr fg_call
fg_close_done:
        jsr N_VCLOSE
        lda #0
        sta fg_bitmap
        rts
fg_exit:
        jsr vd_close
        bcs fg_return
        jsr fg_close_view
        jmp nk_close

fg_picker_load:
        jsr fg_close_view
        lda #0
        sta fg_attempted
        lda #2
        jsr fg_load
        bcs fg_return
        lda #1
        sta fg_picker_active
        clc
        rts
fg_picker_done:
        php
        pha
        lda #0
        sta fg_picker_active
        sta fg_attempted
        pla
        plp
        rts

fg_load:
        sta fg_wanted
        cmp fg_kind
        beq fg_token
        lda #0
        sta fg_kind
        lda N_MSTATE
        beq +
        jsr N_MCLOSE
        bcs fg_failed
+       lda #10
        sta N_FNAMELEN
        ldy #9
        lda fg_wanted
        cmp #1
        beq +
        ldy #19
        cmp #2
        beq +
        ldy #29
+       ldx #9
-       lda fg_names,y
        sta N_FNAME,x
        dey
        dex
        bpl -
        jsr N_MLOAD
        bcs fg_failed
        lda fg_wanted
        sta fg_kind
        ldx #2
-       lda N_MTOKEN,x
        sta fg_generation,x
        dex
        bpl -
fg_token:
        ldx #2
-       lda fg_generation,x
        sta N_MTOKEN,x
        dex
        bpl -
        clc
        rts
fg_failed:
        sta fg_error
        jsr vd_close
        lda fg_error
        sec
        rts
fg_call:
        jsr fg_token
        jmp N_MCALL
fg_field_output:
        lda fg_collect
        beq +
        jmp fv_field
+       lda vd_phase
        bne fg_return
        jmp N_FDRAW
fg_focus_footer:
        lda vd_phase
        bne fg_return
        lda fg_bitmap
        beq fg_return
        lda #3
        sta fg_operation
        jmp fg_call

fg_picker_clean:
        lda fg_kind
        cmp #2
        beq +
        jmp fg_loader_clean
+       jsr copy_picker.fd_close_cursors
        bcs fg_return
        lda #36
        sta fc_cache_at
        jmp fg_cache_next
fg_loader_clean:
        lda fg_kind
        bne fg_loader_done
        lda N_MSTATE
        beq fg_loader_done
        jmp N_MCLOSE
fg_loader_done:
        clc
        rts
fg_cache_next:
        ldx fc_cache_at
        lda copy_picker.b_cache,x
        beq fg_cache_advance
        ldy #0
-       lda copy_picker.b_cache,x
        sta N_HANDLE,y
        inx
        iny
        cpy #4
        bne -
        lda b_owner
        sta N_OWNER
        jsr N_FREE
        bcs fg_return
        ldx fc_cache_at
        lda #0
        sta copy_picker.b_cache,x
fg_cache_advance:
        dec fc_cache_at
        dec fc_cache_at
        dec fc_cache_at
        dec fc_cache_at
        bpl fg_cache_next
        clc
        rts

fg_names: .text "fsview.prg","fspick.prg","fsopen.prg"
fg_generation: .fill 3,0
fg_kind: .byte 0
fg_wanted: .byte 0
fg_operation: .byte 0
fg_attempted: .byte 0
fg_bitmap: .byte 0
fg_picker_active: .byte 0
fg_error: .byte 0
fg_mode: .byte 0
fg_key: .byte 0
fg_collect: .byte 0
fg_searching: .byte 0
fg_surface: .fill 4,0
