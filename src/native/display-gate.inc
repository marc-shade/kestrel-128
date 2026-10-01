; Experimental public presentation gates, GPL v3.
display_show:
        php
        jsr heap_enter
        bcc *+5
        jmp heap_enter_failed
        lda N_FBUSY
        ora N_UIBUSY
        ora v_tag
        beq +
        lda #N_REENTRANT
        bne display_error
+       tsx
        lda $0101,x
        and #4
        bne display_platform
        jsr app_owned
        bcs display_error
        lda N_OWNER
        cmp N_CURRENT
        beq +
        lda #N_WRONGOWNER
        bne display_error
+       jsr heap_handle
        bcs display_error
        jsr heap_check_record
        bcs display_error
        jmp display_prepare
display_platform:
        lda #N_PLATFORM
display_error:
        jmp heap_finish
native_display_gate_end:
