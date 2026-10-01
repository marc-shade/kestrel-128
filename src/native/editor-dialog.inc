; A file field keeps focus after a picker returns, so the user can edit the
; complete returned name before Open confirmation or the exclusive Save As.
ed_browse:
        lda #1
        jsr ed_module_load
        bcs ed_picker_failed
        lda ed_mode
        sta fd_mode
        lda ed_device
        sta fd_device
        lda ed_format
        sta fd_format
        lda ed_field_len
        sta fd_length
        ; FD_NAME_BUFFER aliases this field; the picker commits it on success.
        jsr N_MCALL
        bcs ed_browse_failed
        lda fd_device
        sta ed_device
        lda fd_format
        sta ed_format
        lda fd_type
        sta ed_file_type
        lda fd_length
        sta ed_field_len
        lda #0
        sta N_UIKEY
        jsr ed_field_call
        bcs ed_input_error
        lda #0
        beq ed_browse_status
ed_browse_failed:
        cmp #0
        beq ed_browse_status
        cmp #N_NOMEM
        beq ed_browse_memory
        cmp #N_NOSLOT
        beq ed_browse_memory
        lda #9
        bne ed_browse_status
ed_picker_failed:
        lda #2
        bne ed_browse_status
ed_browse_memory:
        lda #3
ed_browse_status:
        sta ed_status
.if NATIVE_EDITOR_GRAPHICS
        ; Explicit Browse retries may release a previously retained picker.
        ; Let this return try the graphical module again after that cleanup.
        lda #0
        sta eg_attempted
.endif
        ; The dialog has repainted both displays, but never touched document
        ; cursor/cache/viewport state. Redraw it without resetting those values.
        jsr ed_invalidate_pages
        jsr ed_show
        jmp cloop

; A=1 picker, 2 search/renderer, 3 clipboard. A token belongs to exactly one loaded module. Invalidate
; our kind before closing/replacing it; failed loads cannot call a stale token.
ed_module_load:
        sta ed_module_wanted
        cmp ed_module_kind
        beq ed_module_select
        lda ed_module_kind
        cmp #1
        bne ed_module_replace
        ; A failed picker close/free retains descriptors inside its module.
        ; Keep that image available for an explicit Tab retry until all of its
        ; resources have closed; unloading it would lose those descriptors.
        lda fd_iec_handle
        ora bu_cursor
        bne ed_module_retained
        ldx #36
ed_module_cache_check:
        lda b_cache,x
        bne ed_module_retained
        dex
        dex
        dex
        dex
        bpl ed_module_cache_check
ed_module_replace:
.if NATIVE_EDITOR_GRAPHICS
        jsr eg_close_view
        lda #0
        sta eg_attempted
.endif
        lda #0
        sta ed_module_kind
        lda N_MSTATE
        beq +
        jsr N_MCLOSE
        bcs ed_module_return
+       ldy #9
        lda ed_module_wanted
        cmp #1
        beq +
        ldy #19
.if NATIVE_EDITOR_GRAPHICS
        cmp #2
        beq +
        ldy #29
.endif
+       lda #10
        sta N_FNAMELEN
        ldx #9
ed_module_name_copy:
        lda ed_picker_name,y
        sta N_FNAME,x
        dey
        dex
        bpl ed_module_name_copy
        jsr N_MLOAD
        bcs ed_module_return
        lda ed_module_wanted
        sta ed_module_kind
        ldx #2
ed_module_remember:
        lda N_MTOKEN,x
        sta ed_picker_token,x
        dex
        bpl ed_module_remember
ed_module_select:
        ldx #2
ed_module_token:
        lda ed_picker_token,x
        sta N_MTOKEN,x
        dex
        bpl ed_module_token
        clc
ed_module_return:
.if NATIVE_EDITOR_GRAPHICS
        bcc +
        pha
        jsr eg_vdc_close
        pla
        sec
+
.endif
        rts
ed_module_retained:
        lda #N_IOERROR
        sec
        rts

; Directory names may contain raw bytes outside the console's printable
; range. Display dots for those bytes while retaining the exact OPEN target.
ed_safe_puts:
        sta ed_safe_read+1
        stx ed_safe_read+2
ed_safe_read:
        lda $ffff
        beq ed_safe_done
        jsr ed_safe_character
        jsr ed_chrout
        inc ed_safe_read+1
        bne ed_safe_read
        inc ed_safe_read+2
        jmp ed_safe_read
ed_safe_done:
        rts
ed_safe_character:
        cmp #$20
        bcc +
        cmp #$7f
        bcc ed_safe_done
+       lda #$2e
        rts
ed_file_type: .byte 0
ed_picker_name: .text "edpick.prg"
                .text "edfind.prg"
.if NATIVE_EDITOR_GRAPHICS
                .text "edclip.prg"
.endif
ed_picker_token: .fill 3,0
ed_module_kind: .byte 0
ed_module_wanted: .byte 0
