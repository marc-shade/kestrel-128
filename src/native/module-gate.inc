; All gates require an intact original allocation and a caller outside the
; window. The module itself may call normal services, but no module gate.
module_start:
        lda N_MSTATE
        cmp #1
        beq module_start_busy
        cmp #3
        beq module_start_busy
        lda N_BUSY
        ora N_FBUSY
        ora N_UIBUSY
        bne module_start_busy
        tsx
        lda $0103,x            ; original PHP below this JSR
        and #4
        beq +
        lda #N_PLATFORM
        bne module_start_error
+       cld
        lda m_base+1
        beq module_start_argument
        lda $0104,x            ; RTS target must remain in the intact core
        clc
        adc #1
        sta m_return
        lda $0105,x
        adc #0
        sta m_return+1
        cmp #>N_APPBASE
        bcc module_start_argument
        bne +
        lda m_return
        cmp #32
        bcc module_start_argument
+       lda m_return
        cmp m_base
        lda m_return+1
        sbc m_base+1
        bcs module_start_argument
        jsr app_owned
        bcs module_start_error
        ldx #>N_APPBASE
module_pages:
        lda NPAGES0,x
        cmp l_app_handle
        bne module_start_handle
        inx
        cpx field_app_end
        bne module_pages
        lda #0
        sta N_READY
        clc
        rts
module_start_argument:
        lda #N_BADARG
        bne module_start_error
module_start_handle:
        lda #N_BADHANDLE
        bne module_start_error
module_start_busy:
        lda #N_REENTRANT
module_start_error:
        sec
        rts

module_call:
        php
        jsr module_start
        bcs module_gate_error
        lda N_MSTATE
        cmp #2
        bne module_token_error
        ldx #2
module_token:
        lda N_MTOKEN,x
        cmp m_generation,x
        bne module_token_error
        dex
        bpl module_token
        lda m_base
        clc
        adc #16
        sta m_return
        lda m_base+1
        adc #0
        sta m_return+1
        lda m_entry
        cmp m_return
        lda m_entry+1
        sbc m_return+1
        bcc module_token_error
        lda m_entry
        cmp m_limit
        lda m_entry+1
        sbc m_limit+1
        bcs module_token_error
        lda m_limit+1
        cmp field_app_end
        bcc +
        bne module_token_error
        lda m_limit
        bne module_token_error
+
        lda #3
        sta N_MSTATE
        lda #0
        sta N_MERROR
        jsr module_jump
        sta m_result
        php
        pla
        and #1
        sta m_carry
        cld
        lda #$0e
        sta $ff00
        lda #2
        sta N_MSTATE
        lda #0
        sta N_MERROR
        plp
        lsr m_carry
        lda m_result
        rts
module_jump:
        jmp (m_entry)
module_token_error:
        lda #N_BADHANDLE
module_gate_error:
        jmp module_early

; ABI 1.7 repurposes the two reserved NAPP bytes as a LE16 offset.
; The loaded core ends at/before the window, which ends at allocation end.
module_window:
        lda N_APPHEADER+7
        ora N_APPHEADER+11
        beq module_window_ok
        lda N_APPHEADER+6
        cmp #7
        bcc module_window_bad
        lda N_APPHEADER+7
        cmp N_APPHEADER+8
        lda N_APPHEADER+11
        sbc N_APPHEADER+9
        bcc module_window_bad
        lda N_APPHEADER+11
        cmp N_APPHEADER+10
        bcs module_window_bad
        lda N_APPHEADER+7
        sta m_base
        lda N_APPHEADER+11
        clc
        adc #>N_APPBASE
        sta m_base+1
module_window_ok:
        clc
        rts
module_window_bad:
        lda #N_BADIMAGE
        sec
        rts
