; Coordinated views: retain the entire terminal while local controls own VDC.
cg_vdc_sync:
        lda cg_recovery
        bne cg_vdc_return
        lda cg_bitmap
        beq cg_vdc_close
        lda cg_font_ram
        beq cg_vdc_close
        lda cg_live
        cmp #1
        bne cg_vdc_show
        lda cg_menu
        beq cg_vdc_close
cg_vdc_show:
        lda cg_vdc_attempted
        bne cg_vdc_present
        inc cg_vdc_attempted
        inc cg_vdc_owned
        jsr vd_open
        bcc cg_vdc_present
        ; A clean refusal leaves the full text terminal available.
        jsr cg_vdc_release
        bcs cg_vdc_failed
        rts
cg_vdc_present:
        lda cg_vdc_owned
        beq cg_vdc_return
        jsr vm_present
        bcs cg_vdc_failed
        jsr vd_poll
        bcs cg_vdc_failed
cg_vdc_return:
        rts
cg_vdc_failed:
        sta cg_error
        lda #1
        sta cg_recovery
        sta cg_controls_dirty
        lda #2
        sta cg_focus
        sec
        rts
cg_vdc_close:
        lda #0
        sta cg_vdc_attempted
cg_vdc_release:
        lda cg_vdc_owned
        beq cg_vdc_closed
        jsr vd_close
        bcs cg_vdc_failed
        jsr cg_terminal_restore
        bcs cg_vdc_failed
        lda #0
        sta cg_vdc_owned
        sta cg_error
cg_vdc_closed:
        lda #0
        sta cg_recovery
        clc
        rts
cg_terminal_restore:
        jsr $ffff               ; c128hw's bounded model-to-terminal restore
        rts
cg_vdc_mark_row:
        ldx cg_row
        lda #1
        sta vm_rows,x
        sta vm_pending
        rts
cg_vdc_controls:
        lda #1
        sta vm_pending
        ldx #4
-       sta vm_rows,x
        dex
        bpl -
        ldx #23
-       sta vm_rows,x
        dex
        cpx #20
        bne -
        rts

cg_vdc_owned: .byte 0
cg_vdc_attempted: .byte 0
cg_recovery: .byte 0
cg_retiring: .byte 0
BP_MODE=0
BP_TRACK_DIRTY=0
bp_select_surface=cg_surface
.include "../graphics/vdc-client.inc"
