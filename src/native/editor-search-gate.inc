; The module owns its complete modal interaction and returns before normal
; document input resumes. The query and case choice persist across picker use.
ed_search_launch:
        sta ed_s_request
        lda #2
        jsr ed_module_load
        bcs ed_picker_failed
        lda #1
        sta ed_s_running
.if NATIVE_EDITOR_GRAPHICS
        lda #5
        sta eg_operation
        jsr eg_call
.else
        jsr N_MCALL
.endif
        php
        lda #0
        sta ed_s_running
        sta ed_mode
        plp
        bcc +
        sta ed_module_kind
        jmp ed_picker_failed
+
        jmp ed_refresh
ed_search_return:
        clc
        rts
ed_search_help: .text "ctrl-f find ctrl-n next ctrl-r replace",13
                .text "tab in query: case / ignore case",0
ed_s_query: .fill 64,0
ed_s_length: .fill 3,0
ed_s_case: .byte 0
ed_s_pending_case: .byte 0
ed_s_action: .byte 0
ed_s_count: .fill 3,0
ed_s_running: .byte 0
ed_s_request: .byte 0
