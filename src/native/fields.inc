; Native foreground field editing. State and text belong to the running app.
; No heap allocation, key polling, file I/O or document buffer is involved.
field_start:
        lda N_UIBUSY
        ora N_BUSY
        ora N_FBUSY
        beq +
        lda #N_REENTRANT
        bne field_start_error
+       lda N_CURRENT
        cmp #N_APPOWNER
        bne field_wrong_owner
        lda N_APPSTATE
        cmp #2
        bne field_wrong_owner
        tsx
        lda $0103,x             ; caller's PHP, beneath this JSR return address
        and #4
        beq +
        lda #N_PLATFORM
        bne field_start_error
+       cld
        lda #1
        sta N_UIBUSY
        lda #0
        sta N_UIFLAGS
        jsr app_owned
        bcs field_start_failed
        lda N_UIPTR
        sta field_record_read+1
        sta field_record_write+1
        sta field_pointer
        lda N_UIPTR+1
        sta field_record_read+2
        sta field_record_write+2
        sta field_pointer+1
        lda #UI_STATE_BYTES-1
        jsr field_span
        bcs field_start_failed
        ldx #UI_STATE_BYTES-1
field_copy_record:
field_record_read:
        lda $ffff,x
        sta field_state,x
        dex
        bpl field_copy_record
        lda field_state+UI_MAXIMUM
        beq field_bad_state
        cmp field_state+UI_LENGTH
        bcc field_bad_state
        lda field_state+UI_FILTER
        cmp #4
        bcs field_bad_state
        lda field_state+UI_BUFFER
        sta field_pointer
        sta field_read+1
        sta field_write+1
        lda field_state+UI_BUFFER+1
        sta field_pointer+1
        sta field_read+2
        sta field_write+2
        lda field_state+UI_MAXIMUM
        jsr field_span
        bcs field_start_failed
        ; The record and buffer intervals must be disjoint. FIELD_LAST is
        ; the inclusive last buffer address computed by FIELD_SPAN.
        lda N_UIPTR
        cmp field_last
        lda N_UIPTR+1
        sbc field_last+1
        bcc field_check_overlap
        bne field_start_ready
        lda N_UIPTR
        cmp field_last
        bne field_start_ready
field_check_overlap:
        lda N_UIPTR
        clc
        adc #UI_STATE_BYTES-1
        tax
        lda N_UIPTR+1
        adc #0
        sta field_last+1
        txa
        cmp field_pointer
        lda field_last+1
        sbc field_pointer+1
        bcs field_bad_state
field_start_ready:
        clc
        rts
field_wrong_owner:
        lda #N_WRONGOWNER
        bne field_start_error
field_bad_handle:
        lda #N_BADHANDLE
        bne field_start_failed
field_bad_state:
        lda #N_BADARG
field_start_failed:
        dec N_UIBUSY
field_start_error:
        sta N_UIERROR
        sec
        rts

; A is the inclusive last offset (at most 255). Validate every touched
; page against the loader's current handle before any caller RAM is written.
field_span:
        clc
        adc field_pointer
        sta field_last
        lda field_pointer+1
        adc #0
        bcs field_range
        sta field_last+1
        cmp field_app_end
        bcs field_range
        ldx field_pointer+1
        cpx #>N_APPBASE
        bcc field_range
field_page:
        lda NPAGES0,x
        cmp l_app_handle
        bne field_span_handle
        cpx field_last+1
        beq +
        inx
        bne field_page
+       clc
        rts
field_span_handle:
        lda #N_BADHANDLE
        sec
        rts
field_range:
        lda #N_RANGE
        sec
        rts

field_edit:
        php
        jsr field_start
        bcs field_early
        lda N_UIKEY
        beq field_initialize
        lda field_state+UI_LENGTH
        cmp field_state+UI_CARET
        bcc field_invalid
        lda N_UIKEY
        cmp #$9d
        beq field_left
        cmp #$1d
        beq field_right
        cmp #$13
        beq field_home
        cmp #1
        beq field_home
        cmp #5
        beq field_end
        cmp #20
        beq field_backspace
        cmp #4
        beq field_delete
        cmp #21
        beq field_clear
        cmp #$94
        bne +
        lda #32
+       jsr field_filter
        bcs field_finish
        sta field_character
        lda field_state+UI_LENGTH
        cmp field_state+UI_MAXIMUM
        beq field_finish
        tax
field_insert_shift:
        cpx field_state+UI_CARET
        beq field_insert_character
        dex
        jsr field_read
        inx
        jsr field_write
        dex
        jmp field_insert_shift
field_insert_character:
        lda field_character
        jsr field_write
        inc field_state+UI_LENGTH
        inc field_state+UI_CARET
        lda #3
        bne field_changed
field_initialize:
        lda field_state+UI_LENGTH
        sta field_state+UI_CARET
        lda #0
        sta field_state+UI_VIEW40
        sta field_state+UI_VIEW80
        jmp field_terminate
field_left:
        lda field_state+UI_CARET
        beq field_finish
        dec field_state+UI_CARET
        jmp field_moved
field_right:
        lda field_state+UI_CARET
        cmp field_state+UI_LENGTH
        beq field_finish
        inc field_state+UI_CARET
        jmp field_moved
field_home:
        lda #0
        beq field_set_caret
field_end:
        lda field_state+UI_LENGTH
field_set_caret:
        cmp field_state+UI_CARET
        beq field_finish
        sta field_state+UI_CARET
field_moved:
        lda #2
        sta N_UIFLAGS
        jmp field_finish
field_backspace:
        lda field_state+UI_CARET
        beq field_finish
        dec field_state+UI_CARET
        lda #2
        sta N_UIFLAGS
field_delete:
        lda field_state+UI_CARET
        cmp field_state+UI_LENGTH
        beq field_finish
        tax
field_delete_shift:
        inx
        jsr field_read
        dex
        jsr field_write
        inx
        cpx field_state+UI_LENGTH
        bne field_delete_shift
        dec field_state+UI_LENGTH
        lda N_UIFLAGS
        ora #1
        bne field_changed
field_clear:
        lda field_state+UI_LENGTH
        beq field_finish
        lda #1
        ldx field_state+UI_CARET
        beq +
        ora #2
+       ldx #0
        stx field_state+UI_LENGTH
        stx field_state+UI_CARET
field_changed:
        sta N_UIFLAGS
field_terminate:
        ldx field_state+UI_LENGTH
        lda #0
        jsr field_write
field_finish:
        ldx #UI_STATE_BYTES-1
field_copy_back:
        lda field_state,x
field_record_write:
        sta $ffff,x
        dex
        bpl field_copy_back
        lda #0
        sta N_UIERROR
        dec N_UIBUSY
        plp
        lda #0
        clc
        rts
field_invalid:
        lda #N_BADARG
field_failed:
        sta N_UIERROR
        dec N_UIBUSY
field_early:
        plp
        sec
        rts

field_filter:
        cmp #32
        bcc field_filter_reject
        cmp #127
        bcs field_filter_reject
        ldx field_state+UI_FILTER
        beq field_filter_accept
        cpx #3
        beq field_filter_iec
        cmp #$30
        bcc field_filter_reject
        cmp #$3a
        bcc field_filter_accept
        cpx #1
        beq field_filter_reject
        and #$df
        cmp #$41
        bcc field_filter_reject
        cmp #$47
        bcs field_filter_reject
field_filter_accept:
        clc
        rts
field_filter_iec:
        ldx #field_forbidden_end-field_forbidden-1
field_filter_name:
        cmp field_forbidden,x
        beq field_filter_reject
        dex
        bpl field_filter_name
        clc
        rts
field_filter_reject:
        sec
        rts
field_read:
        lda $ffff,x
        rts
field_write:
        sta $ffff,x
        rts
field_forbidden: .text "*?,:/",$5c,"@#$"
field_forbidden_end:
field_state: .fill UI_STATE_BYTES,0
field_pointer: .word 0
field_last: .word 0
field_app_end: .byte 0
field_character: .byte 0
field_capacity: .byte 0
field_view_index: .byte 0
field_at: .byte 0
field_left_count: .byte 0
field_columns: .byte 0
