; Standalone native SDK example. BKREU.PRG is loaded directly into bank 1.
.include "api.inc"
* = N_APPBASE
app_image:
        .text "napp"
        .byte 1,1,12,0
        .word app_end-app_image
        .byte (app_end-app_image+255)/256,0
        .word app_entry-app_image,0
        .text "banked demo",0
        .fill N_APPBASE+32-*,0
app_entry:
        cld
        lda N_DEVICE
        sta N_FDEVICE
        lda N_APPFORMAT
        sta N_FFORMAT
        cmp #3
        bne demo_iec_name
        ldx #0
        stx demo_path_length
-       lda N_SOURCEPATH,x
        sta N_UPATH,x
        cmp #$2f
        bne +
        txa
        clc
        adc #1
        sta demo_path_length
+       inx
        cpx N_NAMELEN
        bne -
        lda demo_path_length
        clc
        adc #9
        bcs demo_argument
        sta N_FNAMELEN
        ldx demo_path_length
        ldy #0
-       lda demo_name,y
        sta N_UPATH,x
        inx
        iny
        cpy #9
        bne -
        beq demo_open
demo_iec_name:
        lda #9
        sta N_FNAMELEN
        ldx #8
-       lda demo_name,x
        sta N_FNAME,x
        dex
        bpl -
demo_open:
        lda #N_APPOWNER
        sta N_FOWNER
        lda #1
        sta N_FTYPE
        lda #0
        sta N_FMODE
        ldx #3
-       sta N_FHANDLE,x       ; early OPEN refusal may not produce a new token
        dex
        bpl -
        jsr N_FOPEN
        php
        pha
        ldx #3
-       lda N_FHANDLE,x
        sta demo_file,x
        dex
        bpl -
        pla
        plp
        bcs demo_failed
        jsr bk_load
        php
        pha
        lda bk_file
        ora bk_state
        beq +                 ; preflight refusal leaves the stream with caller
        lda #0
        sta demo_file
+       pla
        plp
        bcs demo_failed
        lda #N_APPOWNER
        sta N_BUFFER
        ldx #17
        lda #0
-       sta N_BUFFER,x
        dex
        bne -
        lda #9
        jsr bk_call
        bcs demo_failed
        lda #1
        sta demo_arena        ; failed open can retain probe restoration work
        lda #0
        jsr bk_call
        bcs demo_failed
        lda #1
        sta demo_active
        lda #0
        beq demo_failed
demo_argument:
        lda #N_BADARG
demo_failed:
        sta demo_error
        jsr demo_draw
input_loop:
        lda #1
        sta N_READY
        jsr N_KEYIN
        beq input_loop
        ldx #0
        stx N_READY
        cmp #27
        beq demo_exit
        cmp #13
        bne input_loop
        lda demo_active
        beq input_loop
        jsr demo_test
        sta demo_error
        jsr demo_draw
        jmp input_loop
demo_exit:
        jsr demo_cleanup
        bcs demo_failed
        lda #0
        jmp N_EXIT

demo_test:
        lda #8                ; previous test allocations, if any
        jsr bk_call
        bcs demo_test_return
        lda #10
        jsr bk_call
        lda #1
        sta N_BUFFER+1
        lda #0
        sta N_BUFFER+2
        lda #9
        jsr bk_call
        lda #2
        jsr bk_call
        bcs demo_test_return
        lda #10
        jsr bk_call
        lda #0
        sta N_BUFFER+13
        sta N_BUFFER+14
        sta N_BUFFER+15
        sta N_BUFFER+16
        lda #2
        sta N_BUFFER+17
        lda #9
        jsr bk_call
        ldx #0
-       txa
        sta N_BUFFER,x
        eor #$55
        sta N_BUFFER+256,x
        inx
        bne -
        lda #6
        jsr bk_call
        bcs demo_test_return
        lda #0
        ldx #0
-       sta N_BUFFER,x
        sta N_BUFFER+256,x
        inx
        bne -
        lda #5
        jsr bk_call
        bcs demo_test_return
        ldx #0
-       txa
        cmp N_BUFFER,x
        bne demo_mismatch
        eor #$55
        cmp N_BUFFER+256,x
        bne demo_mismatch
        inx
        bne -
        inc demo_passes
        lda #4
        jmp bk_call
demo_mismatch:
        lda #N_CORRUPT
        sec
demo_test_return:
        rts
demo_cleanup:
        lda demo_active
        beq +
        lda #8
        jsr bk_call
        bcs demo_test_return
        lda #0
        sta demo_active
+       lda demo_arena
        beq +
        lda #1
        jsr bk_call
        bcs demo_test_return
        lda #0
        sta demo_arena
+       jsr bk_close
        bcs demo_test_return
        lda demo_file
        beq +
        ldx #3
-       lda demo_file,x
        sta N_FHANDLE,x
        dex
        bpl -
        lda #N_APPOWNER
        sta N_FOWNER
        jsr N_FCLOSE
        bcs demo_test_return
        lda #0
        sta demo_file
+       clc
        rts

demo_draw:
        lda #0
        sta demo_screen
demo_draw_screen:
        lda $d7
        rol
        lda #0
        rol
        cmp demo_screen
        beq +
        jsr $ff5f
+       lda #$93
        jsr $ffd2
        lda #<demo_title
        ldx #>demo_title
        jsr demo_puts
        lda demo_passes
        jsr demo_hex
        lda #<demo_error_text
        ldx #>demo_error_text
        jsr demo_puts
        lda demo_error
        jsr demo_hex
        lda #<demo_help
        ldx #>demo_help
        jsr demo_puts
        inc demo_screen
        lda demo_screen
        cmp #2
        bne demo_draw_screen
        rts
demo_puts:
        sta demo_put+1
        stx demo_put+2
demo_put:
        lda $ffff
        beq +
        jsr $ffd2
        inc demo_put+1
        bne demo_put
        inc demo_put+2
        bne demo_put
+       rts
demo_hex:
        pha
        lsr
        lsr
        lsr
        lsr
        jsr demo_digit
        pla
        and #15
demo_digit:
        tax
        lda demo_digits,x
        jmp $ffd2
demo_file: .fill 4,0
demo_path_length: .byte 0
demo_arena: .byte 0
demo_active: .byte 0
demo_error: .byte 0
demo_passes: .byte 0
demo_screen: .byte 0
demo_name: .text "bkreu.prg"
demo_digits: .text "0123456789abcdef"
demo_title: .text "banked memory demo",13,"passed tests (hex): $",0
demo_error_text: .text 13,"last error (hex): $",0
demo_help: .text 13,13,"return: 512-byte reu write/read test",13
           .text "esc: release resources and exit",13,0
.include "banked.inc"
.include "banked-load.inc"
app_end:
.cerror app_end > N_APPLIMIT, "example parent exceeds its slot"
