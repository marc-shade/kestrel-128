display_close:
        php
        jsr heap_enter
        bcc *+5
        jmp heap_enter_failed
        lda N_FBUSY
        ora N_UIBUSY
        beq +
        lda #N_REENTRANT
        jmp heap_finish
+       jsr app_owned
        bcc *+5
        jmp heap_finish
        jsr display_restore
        jmp heap_success
native_display_close_end:
