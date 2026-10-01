; Association code shares the existing checked module window with the
; renderer and picker. All launch/exit actions happen after N_MCALL returns.
fl_restore_selection:
        lda fl_resume
        beq fl_return
        lda #0
        jsr fl_call
        bcc fl_return
        sta b_error
fl_return:
        rts
fl_edit:
        lda #2
        bne fl_action
fl_paint:
        lda #3
        bne fl_action
fl_associate:
        jsr fl_identify
        beq fl_redraw
        clc
        adc #1
fl_action:
        jsr fl_call
        bcs fl_error
        cmp #0
        beq fl_redraw
        jsr fg_exit
        bcs fl_error
        lda #1
        sta N_DOCRETURN
        lda #$80
        sta N_DOCREQUEST
        jmp N_REPLACE
fl_error:
        sta b_error
fl_redraw:
        jmp b_redraw
fl_call:
        sta fl_operation
        jsr b_close_file
        jsr bu_close_cursor
        bcs fl_return
        jsr fg_close_view
        jsr fg_picker_clean
        bcs fl_return
        lda #0
        sta fg_attempted
        lda #3
        jsr fg_load
        bcs fl_return
        jmp N_MCALL
fl_operation: .byte 0
fl_auto: .byte 0
fl_resume: .byte 0
fl_picture: .byte $55,$50,$4e,$54
fl_workbook_sig: .byte $55,$53,$48,$54
fl_middle: .byte 0

fl_capture:
        lda N_BROWSERFMT
        cmp #3
        bne +
        lda #0
        sta N_DOCTYPE
        jmp bu_save_selection
+       lda b_record
        sec
        sbc #1
        sta N_DOCTYPE
        jsr b_filename
        lda N_FNAMELEN
        sta N_BROWSERNAME_LEN
        ldx #15
-       lda N_FNAME,x
        sta N_BROWSERNAME,x
        dex
        bpl -
        lda b_selected
        sta N_BROWSERPOS
        lda b_selected+1
        sta N_BROWSERPOS+1
        lda #0
        sta N_BROWSERPOS+2
        sta N_BROWSERPOS+3
        rts

fl_identify:
        lda b_error
        bne fl_unknown
        lda b_view_count
        cmp #4
        bcc fl_extension
        ldx #3
-       lda b_view_data,x
        cmp fl_picture,x
        bne fl_workbook
        dex
        bpl -
        lda #2
        rts
fl_workbook:                    ; USHT: a Sheet workbook (kind 3)
        ldx #3
-       lda b_view_data,x
        cmp fl_workbook_sig,x
        bne fl_extension
        dex
        bpl -
        lda #3
        rts
fl_extension:
        jsr fl_capture
        ldx N_BROWSERNAME_LEN
        cpx #5                  ; require a nonempty stem before the suffix
        bcc fl_unknown
        dex
        lda N_BROWSERNAME,x
        and #$df
        cmp #$54
        beq fl_text_suffix
        cmp #$51
        bne fl_unknown
        lda #$45
        ldy #$53
        bne fl_suffix
fl_text_suffix:
        lda #$58
        ldy #$54
fl_suffix:
        sta fl_middle
        dex
        lda N_BROWSERNAME,x
        and #$df
        cmp fl_middle
        bne fl_unknown
        sty fl_middle
        dex
        lda N_BROWSERNAME,x
        and #$df
        cmp fl_middle
        bne fl_unknown
        dex
        lda N_BROWSERNAME,x
        cmp #$2e
        bne fl_unknown
        lda #1
        rts
fl_unknown:
        lda #0
        rts
