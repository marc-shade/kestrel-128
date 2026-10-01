; Native Kestrel ABI 1.7 module example, GPL v3.
.include "api.inc"
.include "layout.inc"
* = N_APPBASE
app_image:
        .text "napp"
        .byte 1,1,7,<(DEMO_WINDOW-N_APPBASE)
        .word app_end-app_image
        .byte DEMO_PAGES,>(DEMO_WINDOW-N_APPBASE)
        .word app_entry-app_image
        .word 0                ; build.py seals the app before binding its module
        .text "module demo",0
        .fill N_APPBASE+32-*,0

app_entry:
        cld
        jsr load_module        ; one initial attempt; R is an explicit retry
        jsr draw
input_loop:
        lda #1
        sta N_READY
        jsr N_KEYIN
        beq input_loop
        ldx #0
        stx N_READY
        cmp #$1b
        beq exit
        cmp #13
        beq call_key
        cmp #$52               ; unshifted PETSCII R
        beq reload_key
        cmp #$72
        bne input_loop
reload_key:
        jsr load_module
        jmp redraw
call_key:
        jsr call_module
redraw:
        jsr draw
        jmp input_loop
exit:
        lda #0
        jmp N_EXIT             ; one-way exit releases the app and its module

load_module:
        lda #0
        sta token
        sta token+1
        sta token+2
        sta result
        sta module_carry
        sta error
        sta status
        jsr N_MCLOSE           ; check retained loader cleanup before loading
        bcs load_failed
        ldx #module_name_end-module_name-1
copy_name:
        lda module_name,x
        sta N_FNAME,x
        dex
        bpl copy_name
        lda #module_name_end-module_name
        sta N_FNAMELEN
        jsr N_MLOAD             ; original app source, even if data CWD changed
        bcs load_failed
        ldx #2
save_token:
        lda N_MTOKEN,x
        sta token,x            ; retain all 24 bits outside the module window
        dex
        bpl save_token
        rts
load_failed:
        sta error
        lda #1
        sta status
        rts

call_module:
        lda token
        ora token+1
        ora token+2
        beq call_done          ; Return does not retry a failed load
        ldx #2
restore_token:
        lda token,x
        sta N_MTOKEN,x
        dex
        bpl restore_token
        jsr N_MCALL
        sta call_value
        php                    ; module A/carry are separate from N_MERROR
        pla
        and #1
        sta call_carry
        lda N_MERROR
        sta error
        bne call_failed
        lda call_value
        sta result             ; a gate error must not become a counter value
        lda call_carry
        sta module_carry
        beq call_status
        lda #3                 ; this module reports counter wrap with carry
call_status:
        sta status
call_done:
        rts
call_failed:
        lda #0
        sta token
        sta token+1
        sta token+2
        lda #2
        sta status
        rts

draw:
        lda #0
        sta screen
draw_screen:
        lda $d7                ; C128 KERNAL's current display bit
        rol
        lda #0
        rol
        cmp screen
        beq display_ready
        jsr $ff5f              ; SWAPPER: select the other native console
display_ready:
        lda #$93
        jsr $ffd2
        lda #<title
        ldx #>title
        jsr puts
        lda result
        jsr hex_byte
        lda #13
        jsr $ffd2
        lda status
        asl
        tay
        lda status_text,y
        ldx status_text+1,y
        jsr puts
        lda error
        beq draw_help
        jsr hex_byte
draw_help:
        lda #<help
        ldx #>help
        jsr puts
        inc screen
        lda screen
        cmp #2
        bne draw_screen
        rts

puts:
        sta puts_read+1
        stx puts_read+2
puts_read:
        lda $ffff
        beq puts_done
        jsr $ffd2              ; KERNAL may change A/X/Y
        inc puts_read+1
        bne puts_read
        inc puts_read+2
        bne puts_read
puts_done:
        rts
hex_byte:
        sta hex_value
        lsr
        lsr
        lsr
        lsr
        jsr hex_digit
        lda hex_value
        and #15
hex_digit:
        tax
        lda hex_digits,x
        jmp $ffd2

token:          .fill 3,0
result:         .byte 0
call_value:     .byte 0
call_carry:     .byte 0
module_carry:   .byte 0
error:          .byte 0
status:         .byte 0
screen:         .byte 0
hex_value:      .byte 0
hex_digits:     .text "0123456789abcdef"
module_name:    .text "counter.prg"
module_name_end:
title:          .text "module demo",13,"counter (hex): $",0
status_text:    .word ready_text,load_text,call_text,wrapped_text
ready_text:     .text "ready",0
load_text:      .text "load error $",0
call_text:      .text "call error $",0
wrapped_text:   .text "counter wrapped",0
help:           .text 13,13,"return: call loaded module",13
                .text "r: reload counter.prg",13,"esc: exit",13,0
app_end:
.cerror app_end > DEMO_WINDOW, "parent core overlaps its module window"
