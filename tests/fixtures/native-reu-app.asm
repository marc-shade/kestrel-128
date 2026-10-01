; VICE-only NAPP fixture, loaded through the actual checked app/file lifecycle.
.include "../../src/native/api.inc"
* = N_APPBASE
app_image:
        .text "napp"
        .byte 1,1,0,0
        .word app_end-app_image
        .byte (app_end-app_image+255)/256,0
        .word app_entry-app_image,0
        .text "reu check",0
        .fill N_APPBASE+32-*,0
app_entry:
        cld
        lda N_CURRENT
        sta ru_owner
check_loop:
        lda #1
        sta N_READY
        jsr N_KEYIN
        beq check_loop
        cmp #27
        beq check_exit
        lda #0
        sta N_READY
        lda check_operation
        cmp #9
        bcs check_loop
        asl
        tax
        lda check_entries,x
        sta check_call+1
        lda check_entries+1,x
        sta check_call+2
        php
        lda check_flags
        ora #$20
        pha
        plp
check_call:
        jsr $ffff
        sta check_result
        php
        pla
        sta check_status
        plp
        inc check_serial
        jmp check_loop
check_exit:
        lda #0
        jmp N_EXIT
check_entries: .word ru_open,ru_close,ru_alloc,ru_reserve,ru_free,ru_read,ru_write,ru_stats,ru_release
check_operation: .byte 0
check_flags: .byte 0
check_result: .byte 0
check_status: .byte 0
check_serial: .byte 0
.include "../../src/native/reu.inc"
app_end:
