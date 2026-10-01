; Checked transient module; return to the core before replacing the app.
fl_entry:
        lda fl_operation
        beq fl_restore_selection_module
        sec
        sbc #1
fl_open:
        sta N_DOCKIND
        lda N_BROWSERFMT
        cmp #3
        beq fl_ultimate
        lda b_total
        ora b_total+1
        beq fl_no_document
        jsr fl_read_record
        bcs fl_failed
        lda b_record+1
        and #$80
        beq fl_unclosed
        lda b_record
        cmp #1
        bcc fl_unsupported
        cmp #4
        bcs fl_unsupported
        jmp fl_selected
fl_ultimate:
        lda bu_count
        beq fl_no_document
        jsr bu_fullname
        bcs fl_failed
        lda bu_attribute
        and #$18               ; directory and volume entries are not documents
        bne fl_unsupported
fl_selected:
        jsr fl_capture
        lda b_open
        beq +
        jsr N_FCLOSE
        bcs fl_failed
        lda #0
        sta b_open
+
        jsr bu_close_cursor
        bcs fl_failed
        lda N_BOOTDEVICE
        sta N_DEVICE
        lda N_BOOTFORMAT
        sta N_APPFORMAT
        ldx #5
        ldy #5
        lda N_DOCKIND
        cmp #1
        beq +
        dex                     ; "paint"
        ldy #10
        cmp #2
        beq +
        ldy #15                 ; "sheet"
+       txa
        clc
        adc #1
        sta N_NAMELEN
-       lda fl_apps,y
        sta N_APPNAME,x
        dey
        dex
        bpl -
        lda N_DOCKIND
        clc
        rts
fl_unclosed:
        lda #$22
        bne fl_failed
fl_unsupported:
        lda #$21
fl_failed:
        sec
        rts
fl_no_document:
        lda #0
        clc
        rts

fl_read_record:
        lda b_selected
        sta b_index
        lda b_selected+1
        sta b_index+1
        jsr b_cache_select
        jsr N_READ
        bcs fl_failed
        ldx #31
-       lda N_BUFFER,x
        sta b_record,x
        dex
        bpl -
        clc
        rts

; The Ultimate navigator already restores raw names across rescans. IEC
; returns find the same name first, falling back to the clamped prior ordinal.
fl_restore_selection_module:
        lda fl_resume
        beq fl_restore_done
        lda #0
        sta fl_resume
        lda N_BROWSERFMT
        cmp #3
        beq fl_restore_done
        lda N_BROWSERNAME_LEN
        beq fl_restore_done
        lda N_BROWSERPOS
        sta b_selected
        lda N_BROWSERPOS+1
        sta b_selected+1
        jsr b_clamp
        ldx #1
-       lda b_selected,x
        sta b_saved_selection,x
        lda #0
        sta b_selected,x
        dex
        bpl -
fl_find_name:
        lda b_selected
        cmp b_total
        lda b_selected+1
        sbc b_total+1
        bcs fl_restore_ordinal
        jsr fl_read_record
        bcs fl_failed
        jsr b_filename
        lda N_FNAMELEN
        cmp N_BROWSERNAME_LEN
        bne fl_next_name
        tax
-       dex
        lda N_FNAME,x
        cmp N_BROWSERNAME,x
        bne fl_next_name
        cpx #0
        bne -
        beq fl_restore_done
fl_next_name:
        inc b_selected
        bne fl_find_name
        inc b_selected+1
        jmp fl_find_name
fl_restore_ordinal:
        ldx #1
-       lda b_saved_selection,x
        sta b_selected,x
        dex
        bpl -
fl_restore_done:
        lda #0
        clc
        rts
fl_apps: .text "editorpaintsheet"
