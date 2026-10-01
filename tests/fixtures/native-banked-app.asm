; VICE qualification fixture. Uses the checked native app and stream lifecycle.
.include "../../src/native/api.inc"
* = N_APPBASE
app_image:
        .text "napp"
        .byte 1,1,12,0
        .word app_end-app_image
        .byte (app_end-app_image+255)/256,0
        .word app_entry-app_image,0
        .text "banked check",0
        .fill N_APPBASE+32-*,0
app_entry:
        cld
        lda N_DEVICE
        sta N_FDEVICE
        lda N_APPFORMAT
        sta N_FFORMAT
        lda #9
        sta N_FNAMELEN
        ldx #8
-       lda check_name,x
        sta N_FNAME,x
        dex
        bpl -
        lda #32
        sta N_FOWNER
        lda #1
        sta N_FTYPE
        lda #0
        sta N_FMODE
        jsr N_FOPEN
        bcs +
        jsr bk_load
+       sta check_load_error
check_loop:
        lda #1
        sta N_READY
        jsr N_KEYIN
        beq check_loop
        cmp #27
        beq check_exit
        lda #0
        sta N_READY
        php
        lda check_flags
        ora #$20
        pha
        plp
        lda check_operation
        jsr bk_call
        sta check_result
        php
        pla
        sta check_status
        plp
        inc check_serial
        jmp check_loop
check_exit:
        jsr bk_close
        bcs check_loop
        lda #0
        jmp N_EXIT
check_name: .text "bkreu.prg"
check_operation: .byte 0
check_flags: .byte 0
check_result: .byte 0
check_status: .byte 0
check_serial: .byte 0
check_load_error: .byte 0
.include "../../src/native/banked.inc"
.include "../../src/native/banked-load.inc"
app_end:
