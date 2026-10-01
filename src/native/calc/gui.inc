; Graphical front end for the existing arithmetic/history/file implementation.
; The diagnostic build omits this module. A refused surface uses both consoles.
cg_begin:
        lda #0
        sta cg_bitmap
        sta cg_handle
        sta cg_mode
        sta cg_vdc_attempted
        sta N_BANK
        lda owner
        sta N_OWNER
        lda #$c0
        sta N_PAGE
        lda #36
        sta N_PAGES
        jsr N_RESERVE
        bcs cg_failed
        ldx #3
-       lda N_HANDLE,x
        sta cg_handle,x
        dex
        bpl -
        lda #0
        sta N_OFFSET
        sta N_OFFSET+1
        sta N_COUNT
        sta N_VALUE
        lda #2
        sta N_COUNT+1
-       jsr N_FILL
        bcs cg_failed
        inc N_OFFSET+1
        inc N_OFFSET+1
        lda N_OFFSET+1
        cmp #$24
        bne -
        jsr cg_select_surface
        jsr gfx_bind
        bcs cg_failed
        jsr cg_scene_draw
        bcs cg_failed
        jsr cg_select_surface
        jsr N_VSHOW
        bcs cg_failed
        lda #1
        sta cg_bitmap
        jsr pm_install
        bcc cg_return
cg_failed:
        sta cg_error
        jsr vd_close
        bcs cg_return         ; retain every owner while VDC restoration is pending
        jsr pm_close
        jsr N_VCLOSE
        lda #0
        sta cg_bitmap
        lda cg_handle
        beq cg_return
        jsr cg_select_surface
        jsr N_FREE
        bcs cg_return
        lda #0
        sta cg_handle
cg_return:
        rts

cg_select_surface:
        lda owner
        sta N_OWNER
        ldx #3
-       lda cg_handle,x
        sta N_HANDLE,x
        dex
        bpl -
        rts

cg_redraw:
        lda cg_bitmap
        beq cg_return
        lda save_mode
        cmp cg_mode
        beq cg_dynamic
        sta cg_mode
        lda #$ff
        sta pm_arm
        lda cg_mode
        beq cg_main_focus
        lda ui_selected
        sta cg_saved_focus
        lda #21
        bne cg_mode_focus
cg_main_focus:
        lda cg_saved_focus
cg_mode_focus:
        sta ui_selected
        jsr cg_scene_draw
        bcs cg_failed
cg_dynamic:
        jsr cg_contents
        bcs cg_failed
        lda cg_vdc_attempted
        bne cg_sync
        inc cg_vdc_attempted
        jsr vd_open
        bcc cg_return
        jsr vd_close          ; partial setup rolls back before any text fallback
cg_sync:
        jsr vm_present
        jsr vd_poll
        lda vd_phase
        beq cg_return
        lda vd_fault
        beq cg_return
        jmp cg_status

cg_scene_draw:
        lda #0
        sta cg_history_valid
        ldx #0
        jsr cg_clear_region
        bcs cg_draw_done
        lda #0
        sta gfx_x0
        sta gfx_y0
        lda #40
        sta gfx_x1
        lda #25
        sta gfx_y1
        lda #0
        sta gfx_x1+1
        lda #$16
        sta gfx_color
        jsr gfx_colors
        bcs cg_draw_done
        lda cg_mode
        bne cg_save_scene
        lda #0
        sta ui_first
        lda #21
        sta ui_limit
        jsr cg_main.draw_scene
        jmp cg_scene_result
cg_save_scene:
        lda #21
        sta ui_first
        lda #23
        sta ui_limit
        jsr cg_save.draw_scene
cg_scene_result:
        bcs cg_draw_done
        lda ui_first
        sta cg_index
-       ldx cg_index
        jsr ui_paint
        bcs cg_draw_done
        inc cg_index
        lda cg_index
        cmp ui_limit
        bne -
        clc
cg_draw_done:
        rts

cg_contents:
        lda cg_mode
        bne cg_filename
        ldx #8
        jsr cg_clear_region
        bcs cg_draw_done
        lda #<dispbuf
        ldx #>dispbuf
        jsr cg_copy_text
        lda #24
        ldy #48
        jsr cg_text
        bcs cg_draw_done
        lda cg_history_valid
        beq cg_history_redraw
        lda history_count
        cmp cg_history_count
        bne cg_history_redraw
        lda history_head
        cmp cg_history_head
        bne cg_history_redraw
        lda history_view
        cmp cg_history_view
        beq cg_status
cg_history_redraw:
        lda #1
        sta cg_history_valid
        lda history_count
        sta cg_history_count
        lda history_head
        sta cg_history_head
        lda history_view
        sta cg_history_view
        ldx #16
        jsr cg_clear_region
        bcs cg_draw_done
        lda history_count
        bne cg_history
        lda #<cg_empty
        ldx #>cg_empty
        jsr cg_copy_text
        lda #192
        ldy #80
        jsr cg_text
        bcs cg_draw_done
        jmp cg_status
cg_history:
        lda #0
        sta cg_row
cg_history_next:
        lda history_view
        clc
        adc cg_row
        cmp history_count
        bcs cg_status
        sta history_ordinal
        lda history_head
        sec
        sbc #1
        sec
        sbc history_ordinal
        and #31
        jsr history_offset
        jsr history_select
        jsr N_READ
        bcs history_failure
        ldx #0
-       lda N_BUFFER,x
        cmp #$20
        beq +
        sta gfx_text_buffer,x
        inx
        cpx #8
        bne -
+       stx gfx_text_length
        lda cg_row
        asl
        asl
        clc
        adc cg_row
        asl
        clc
        adc #76
        tay
        lda #192
        jsr cg_text
        bcs cg_draw_done
        inc cg_row
        lda cg_row
        cmp #8
        bne cg_history_next
        jmp cg_status
cg_filename:
        ldx #32
        jsr cg_clear_region
        bcs cg_draw_done
        lda #<save_name
        ldx #>save_name
        jsr cg_copy_text
        lda #32
        ldy #88
        jsr cg_text
        bcs cg_draw_done
        lda save_cursor
        asl
        asl
        asl
        clc
        adc #32
        sta gfx_x0
        clc
        adc #8
        sta gfx_x1
        lda #0
        sta gfx_x0+1
        sta gfx_x1+1
        sta gfx_y0+1
        sta gfx_y1+1
        lda #88
        sta gfx_y0
        lda #96
        sta gfx_y1
        lda #2
        sta gfx_pen
        jsr gfx_rect
        bcs cg_draw_done
cg_status:
        ldx #24
        jsr cg_clear_region
        bcs cg_draw_done
        lda vd_phase
        beq +
        lda vd_fault
        beq +
        lda #<cg_vdc_help
        ldx #>cg_vdc_help
        bne cg_status_text
+
        lda #<cg_help
        ldx #>cg_help
        ldy save_mode
        beq +
        lda #<cg_save_help
        ldx #>cg_save_help
        bne cg_status_text
+       ldy save_status
        beq cg_status_text
        dey
        lda save_messages_lo,y
        ldx save_messages_hi,y
cg_status_text:
        jsr cg_copy_text
        lda #8
        ldy #192
        jmp cg_text

; Clear a declared region; graphics calls preserve the bound surface/clip.
cg_clear_region:
        ldy #0
-       lda cg_regions,x
        sta gfx_x0,y
        inx
        iny
        cpy #8
        bne -
        lda #0
        sta gfx_pen
        jmp gfx_rect

cg_copy_text:
        sta cg_read+1
        stx cg_read+2
        ldx #0
        ldy #0
cg_read:
        lda $ffff,y
        beq cg_copied
        iny
        cmp #13
        beq cg_read
        sta gfx_text_buffer,x
        inx
        cpx #38
        bne cg_read
cg_copied:
        stx gfx_text_length
        rts
cg_text:
        sta gfx_x0
        sty gfx_y0
        lda #0
        sta gfx_x0+1
        sta gfx_y0+1
        lda #1
        sta gfx_pen
        jmp gfx_text

cg_mouse:
        jsr pm_poll
        lda pm_event
        beq cg_mouse_sync
        ldx pm_hit
        jsr ui_focus
        bcs cg_input_failed
cg_mouse_sync:
        jsr cg_sync
        lda pm_event
        cmp #2
        bne cg_no_mouse
        ldx pm_hit
        lda ui_keys,x
        rts
cg_input_failed:
        jsr cg_failed
        jsr c_show
cg_no_mouse:
        lda #0
        rts

; Preserve typed arithmetic and Enter =. Tab/arrows focus; Space activates.
; In the filename dialog Tab selects Save/Cancel and Enter confirms that choice.
cg_key:
        sta cg_key_value
        lda cg_bitmap
        beq cg_key_return
        lda cg_key_value
        cmp #9
        beq cg_next
        ldx save_mode
        bne cg_dialog_key
        cmp #$11
        beq cg_next
        cmp #$1d
        beq cg_next
        cmp #$91
        beq cg_previous
        cmp #$9d
        beq cg_previous
        cmp #32
        bne +
        ldx ui_selected
        lda ui_keys,x
        sta cg_key_value
+       cmp #13
        bne +
        lda #$3d
+       cmp #$61
        bcc +
        cmp #$7b
        bcs +
        and #$df
+       ldx #20
-       cmp ui_keys,x
        beq cg_key_focus
        dex
        bpl -
        bmi cg_key_return
cg_dialog_key:
        cmp #13
        bne cg_key_return
        ldx ui_selected
        lda ui_keys,x
        sta cg_key_value
        bne cg_key_return
cg_key_focus:
        jsr ui_focus
        bcs cg_key_failed
        jsr cg_sync
cg_key_return:
        lda cg_key_value
        clc
        rts
cg_next:
        ldx ui_selected
        inx
        cpx ui_limit
        bcc cg_focus_only
        ldx ui_first
        bcs cg_focus_only
cg_previous:
        ldx ui_selected
        cpx ui_first
        bne +
        ldx ui_limit
+       dex
cg_focus_only:
        jsr ui_focus
        bcs cg_key_failed
        jsr cg_sync
        sec
        rts
cg_key_failed:
        jsr cg_failed
        jsr c_show
+       sec
        rts

pm_control_count=ui_button_count
pm_select_surface=cg_select_surface
pm_find_hit:
        lda pm_x
        sta ui_x
        lda pm_x+1
        sta ui_x+1
        lda pm_y
        sta ui_y
        jmp ui_hit

cg_bitmap: .byte 0
cg_handle: .fill 4,0
cg_error: .byte 0
cg_mode: .byte 0
cg_saved_focus: .byte 14
cg_index: .byte 0
cg_row: .byte 0
cg_key_value: .byte 0
cg_vdc_attempted: .byte 0
cg_exit_error: .byte 0
cg_stack: .byte 0
cg_history_valid: .byte 0
cg_history_count: .byte 0
cg_history_head: .byte 0
cg_history_view: .byte 0
cg_regions:
        .word 0,0,320,200
        .word 24,48,168,56
        .word 192,76,304,156
        .word 8,192,312,200
        .word 32,88,168,96
cg_help: .byte 84,97,98,47,97,114,114,111,119,115,32,109,111,118,101,32,32,83,112,97,99,101,32,112,114,101,115,115,101,115,0
cg_save_help: .byte 69,110,116,101,114,32,115,97,118,101,115,32,32,32,69,115,99,32,99,97,110,99,101,108,115,0
cg_empty: .byte 78,111,32,114,101,115,117,108,116,115,0
cg_vdc_help: .byte 56,48,45,99,111,108,32,112,97,117,115,101,100,59,32,69,115,99,32,114,101,116,114,105,101,115,32,114,101,116,117,114,110,0

cg_main .block
.include "../graphics/scene-rect.inc"
.include "../graphics/scene-text.inc"
.include "main-scene.inc"
.endblock
cg_save .block
.include "../graphics/scene-rect.inc"
.include "../graphics/scene-text.inc"
.include "save-scene.inc"
.endblock
.include "buttons.inc"
.include "../graphics/buttons.inc"
ui_selected: .byte 14
.include "../graphics/graphics-core.inc"
.include "../graphics/text-core.inc"
.include "../input/pointer.inc"
vm_select_surface=cg_select_surface
BP_MODE=0
bp_select_surface=cg_select_surface
.include "../graphics/vdc-client.inc"
