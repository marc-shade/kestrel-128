; DESK1.ACC: the Calculator desk accessory (docs/GEM-LAYER-DESIGN.md#desk-accessories).
; An NBK1 image for bank-1 AC_BASE, installed in the AES with AE_OP_ACC. It adds
; "Calculator" to the Desk menu of any AES app, and runs only while that app
; waits in the AES's event call (GEM's cooperative scheduling): a window with a
; display and a 4x4 keypad, used with the pointer, or with 0-9 + - * / = (or
; Return) and C while its window is on top. Numbers are signed 32-bit
; integers; an overflow or a division by zero shows "Error" until C.
; No zero page; every AES call goes through the exports at AE_BASE+40.
.include "api.inc"
.include "aes-api.inc"
AES_ENTRY = AE_BASE+40          ; exports: operations, menu item, ev_msg_in
AES_MENU_ADD = AE_BASE+42
AES_MSG_IN = AE_BASE+44
PAPER = $61                     ; blue ink on white
KEYCOLOR = $0f                  ; black ink on light grey
WIN_X = 22                      ; where the window opens (cells)
WIN_Y = 3
WIN_W = 16
WIN_H = 12

* = AC_BASE
image:
        .text "nbk1"
        .byte 1,1,14,0
        .word end-image
        .byte (end-image+255)/256,1
        .word none-image,0
        ldx #$0e                ; the NBK1 exit stub (unused: the AES calls in)
        jmp $02ab
        .byte 0
        .word 0
        .fill 8,0
identity:
        .text "nacc"
        .byte 1,0,0,0
        .cerror identity-image != 32, "accessory identity must be at offset 32"
entries:
        .word menu,message,dispatch,reset
        .cerror entries-image != 40, "accessory entries must be at offset 40"

none:
        clc
        rts
aes:
        jmp (AES_ENTRY)
menu_add:
        jmp (AES_MENU_ADD)

; ---- menu: a separator and "Calculator" after the Desk title's items --------
menu:
        lda #0
        sta item_ok
        lda #<t_separator
        ldx #>t_separator
        jsr menu_add
        bcs +
        lda #<t_title
        ldx #>t_title
        jsr menu_add
        bcs +
        sta item
        inc item_ok
+       clc
        rts

; ---- message: take the Desk choice and every message for our window ---------
message:
        lda AES_MSG_IN
        sta msg_read+1
        lda AES_MSG_IN+1
        sta msg_read+2
        ldx #7
msg_read:
        lda $ffff,x
        sta msg,x
        dex
        bpl msg_read
        lda msg
        cmp #MN_SELECTED
        bne msg_window
        lda msg+3               ; the Desk title, our item
        bne msg_pass
        lda item_ok
        beq msg_pass
        lda msg+4
        cmp item
        bne msg_pass
        inc want_open
        sec
        rts
msg_window:
        cmp #WM_REDRAW
        bcc msg_pass
        cmp #WM_MOVED+1
        bcs msg_pass
        ldx handle
        beq msg_pass
        cpx msg+3
        bne msg_pass
        cmp #WM_REDRAW
        bne +
        inc want_redraw
+       cmp #WM_TOPPED
        bne +
        inc want_top
+       cmp #WM_CLOSED
        bne +
        inc want_close
+       cmp #WM_MOVED
        bne +
        ldx #3
-       lda msg+4,x
        sta move_rect,x
        dex
        bpl -
        inc want_move
+       sec                     ; the app never sees them
        rts
msg_pass:
        clc
        rts

; ---- reset: a new app; the AES has discarded every window ------------------------
reset:
        lda #0
        sta handle
        sta item_ok
        sta want_open
        sta want_close
        sta want_top
        sta want_move
        sta want_redraw
        clc
        rts

; ---- dispatch: after each event sample, with its reply in N_BUFFER[0..18] --------
dispatch:
        ldx #18
-       lda N_BUFFER,x
        sta reply,x
        dex
        bpl -
        jsr work
        ldx #18
-       lda reply,x
        sta N_BUFFER,x
        dex
        bpl -
        clc
        rts
work:
        lda want_open
        beq +
        lda #0
        sta want_open
        jsr open
        bcs work_done
+       lda handle
        beq work_done
        lda want_close
        beq +
        jmp close
+       lda want_move
        beq +
        lda #0
        sta want_move
        lda #WS_SET
        jsr prepare
        lda #WF_CURRXYWH
        sta N_BUFFER+2
        ldx #3
-       lda move_rect,x
        sta N_BUFFER+3,x
        dex
        bpl -
        jsr wcall
+       lda want_top
        beq +
        lda #0
        sta want_top
        jsr top
+       lda want_redraw
        beq +
        lda #0
        sta want_redraw
        jsr draw
+       jmp input
work_done:
        rts

; A = window sub-operation, for our window.
prepare:
        sta N_BUFFER
        lda handle
        sta N_BUFFER+1
        rts
; AE_OP_WINDOW with N_BUFFER prepared; the rows it drew join the reply's, so
; the app mirrors them to the VDC. Carry and A as the AES returns them.
wcall:
        lda #AE_OP_WINDOW
        jsr aes
        php
        bcs +
        ldx #3
-       lda N_BUFFER+4,x
        ora reply+15,x
        sta reply+15,x
        dex
        bpl -
+       plp
        rts

open:
        lda handle
        beq +
        jmp top                 ; already open: bring it to the top
+       lda #WS_CREATE
        sta N_BUFFER
        lda #<(WK_NAME|WK_CLOSER|WK_MOVER)
        sta N_BUFFER+2
        lda #>(WK_NAME|WK_CLOSER|WK_MOVER)
        sta N_BUFFER+3
        ldx #3
-       lda win_rect,x
        sta N_BUFFER+4,x
        dex
        bpl -
        jsr wcall
        bcs open_done           ; no window free: nothing happens
        lda N_BUFFER
        sta handle
        lda #WS_SET
        jsr prepare
        lda #WF_NAME
        sta N_BUFFER+2
        ldx #10
-       lda t_title,x
        sta N_BUFFER+3,x
        dex
        bpl -
        jsr wcall
        lda #WS_OPEN
        jsr prepare
        ldx #3
-       lda win_rect,x
        sta N_BUFFER+2,x
        dex
        bpl -
        jsr wcall               ; (its WM_REDRAW comes back through message)
        clc
open_done:
        rts
top:
        lda #WS_SET
        jsr prepare
        lda #WF_TOP
        sta N_BUFFER+2
        jmp wcall
close:
        lda #0
        sta want_close
        lda #WS_CLOSE
        jsr prepare
        jsr wcall
        lda #WS_DELETE
        jsr prepare
        jsr wcall
        lda #0
        sta handle
        rts

; The work area's origin (cells) into wx/wy.
origin:
        lda #WS_GET
        jsr prepare
        lda #WF_WORKXYWH
        sta N_BUFFER+2
        jsr wcall
        bcs +
        lda N_BUFFER
        sta wx
        lda N_BUFFER+1
        sta wy
+       rts

; Paint the work area: paper, the display, the keypad.
draw:
        jsr origin
        bcs draw_done
        lda #WS_FILL
        jsr prepare
        lda #0
        sta N_BUFFER+2
        lda #PAPER
        sta N_BUFFER+3
        lda #0                  ; clip: the whole screen
        sta N_BUFFER+4
        sta N_BUFFER+5
        lda #40
        sta N_BUFFER+6
        lda #25
        sta N_BUFFER+7
        jsr wcall
        bcs draw_done
        lda #15
        sta key_i
-       jsr draw_key
        bcs draw_done
        dec key_i
        bpl -
        jmp draw_display
draw_done:
        rts
; key_i: its button (3 cells, light grey) and its label.
draw_key:
        ldx key_i
        lda key_x,x
        sta cell_x
        lda key_y,x
        sta cell_y
        lda #WS_FILL
        jsr prepare
        lda #0
        sta N_BUFFER+2
        lda #KEYCOLOR
        sta N_BUFFER+3
        lda wx
        clc
        adc cell_x
        sta N_BUFFER+4
        lda wy
        clc
        adc cell_y
        sta N_BUFFER+5
        lda #3
        sta N_BUFFER+6
        lda #1
        sta N_BUFFER+7
        jsr wcall
        bcs +
        lda #WS_TEXT
        jsr prepare
        ldx cell_x
        inx
        stx N_BUFFER+2
        lda cell_y
        sta N_BUFFER+3
        lda #1
        sta N_BUFFER+4
        ldx key_i
        lda key_labels,x
        sta N_BUFFER+5
        lda #0
        sta N_BUFFER+6
        jmp wcall
+       rts
; The display row: cleared, then the value right-aligned in cells 1..14.
draw_display:
        lda #WS_FILL
        jsr prepare
        lda #0
        sta N_BUFFER+2
        lda #PAPER
        sta N_BUFFER+3
        lda wx
        clc
        adc #1
        sta N_BUFFER+4
        lda wy
        clc
        adc #1
        sta N_BUFFER+5
        lda #14
        sta N_BUFFER+6
        lda #1
        sta N_BUFFER+7
        jsr wcall
        bcs draw_done
        jsr format              ; text[0..text_len)
        lda #WS_TEXT
        jsr prepare
        lda #15
        sec
        sbc text_len
        sta N_BUFFER+2
        lda #1
        sta N_BUFFER+3
        sta N_BUFFER+4
        ldx #0
-       lda text,x
        sta N_BUFFER+5,x
        inx
        cpx text_len
        bne -
        lda #0
        sta N_BUFFER+5,x
        jmp wcall

; ---- input: keys and presses for our window while it is on top ---------------------
input:
        lda #WS_GET
        jsr prepare
        lda #WF_TOP
        sta N_BUFFER+2
        jsr wcall
        bcs input_done
        lda N_BUFFER
        cmp handle
        bne input_done
        lda reply               ; a key the calculator knows
        and #MU_KEYBD
        beq input_button
        lda reply+1
        jsr key_index
        bcs input_button
        jsr press
        lda reply
        and #$ff^MU_KEYBD
        sta reply
input_button:
        lda reply               ; a click on the keypad
        and #MU_BUTTON
        beq input_done
        jsr origin
        bcs input_done
        lda reply+3             ; the pointer's cell
        lsr
        lda reply+2
        ror
        lsr
        lsr
        sec
        sbc wx
        bcc input_done
        cmp #WIN_W
        bcs input_done
        sta cell_x
        lda reply+4
        lsr
        lsr
        lsr
        sec
        sbc wy
        bcc input_done
        cmp #WIN_H-1
        bcs input_done
        sta cell_y
        lda reply               ; inside our work area: the app never sees it
        and #$ff^MU_BUTTON
        sta reply
        ldx #15
-       lda cell_y
        cmp key_y,x
        bne +
        lda cell_x
        sec
        sbc key_x,x
        cmp #3
        bcc input_key
+       dex
        bpl -
input_done:
        rts
input_key:
        txa
        jmp press
; A = a typed key -> X = its keypad index, carry clear; carry set if none.
key_index:
        cmp #13
        bne +
        lda #$3d                ; Return is =
+       cmp #$63                ; c (ASCII), or shifted C (PETSCII)
        beq +
        cmp #$c3
        bne ++
+       lda #$43
+       ldx #15
-       cmp key_labels,x
        beq +
        dex
        bpl -
        sec
        rts
+       clc
        rts

; ---- the calculator ------------------------------------------------------------------
; X = keypad index. Digits build `value` (entering); an operator applies the
; pending one to acc and value; = applies it and ends; C clears everything.
press:
        lda key_labels,x
        cmp #$43                ; C
        bne +
        ldx #11
        lda #0
-       sta value,x             ; value, acc, op, entering, error, (pad)
        dex
        bpl -
        jmp draw_display
+       ldy error
        bne press_done          ; only C leaves an error
        cmp #$30
        bcc press_operator
        cmp #$3a
        bcs press_operator
        and #15
        sta digit
        lda entering
        bne +
        jsr clear_value
        inc entering
+       jsr times10_add         ; value*10 + digit, unless it would overflow
        jmp draw_display
press_operator:
        pha
        lda op                  ; the pending operation first
        beq +
        lda entering
        beq ++
        jsr apply
        jmp ++
+       ldx #3                  ; none pending: value becomes the left operand
-       lda value,x
        sta acc,x
        dex
        bpl -
+       pla
        cmp #$3d                ; =
        bne +
        lda #0
+       sta op
        lda #0
        sta entering
        ldx #3                  ; show the result
-       lda acc,x
        sta value,x
        dex
        bpl -
        jmp draw_display
press_done:
        rts
clear_value:
        lda #0
        sta value
        sta value+1
        sta value+2
        sta value+3
        rts

; value = value*10 + digit (value >= 0 while typing); ignored past 2147483647.
times10_add:
        ldx #3
-       lda value,x
        sta work4,x
        dex
        bpl -
        jsr shift_left          ; value*2
        bcs t10_over
        jsr shift_left          ; *4
        bcs t10_over
        clc                     ; *5
        ldx #0
        ldy #4
-       lda value,x
        adc work4,x
        sta value,x
        inx
        dey
        bne -
        bcs t10_over
        jsr shift_left          ; *10
        bcs t10_over
        clc                     ; (no compare in this carry chain)
        lda value
        adc digit
        sta value
        bcc +
        inc value+1
        bne +
        inc value+2
        bne +
        inc value+3
+       lda value+3             ; past 2147483647 the sign bit turns on
        bmi t10_over
        rts
t10_over:
        ldx #3                  ; keep the number as it was
-       lda work4,x
        sta value,x
        dex
        bpl -
        rts
shift_left:                     ; value <<= 1; carry = the bit out (or a sign change)
        asl value
        rol value+1
        rol value+2
        rol value+3
        rts

; acc = acc (op) value, signed; error on overflow or a division by zero.
apply:
        lda op
        cmp #$2b                ; +
        bne +
        clc
        ldx #0
        ldy #4
-       lda acc,x
        adc value,x
        sta acc,x
        inx
        dey
        bne -
        bvs apply_error
        rts
+       cmp #$2d                ; -
        bne +
        sec
        ldx #0
        ldy #4
-       lda acc,x
        sbc value,x
        sta acc,x
        inx
        dey
        bne -
        bvs apply_error
        rts
+       pha                     ; * and / work on magnitudes
        lda acc+3
        eor value+3
        sta sign
        jsr abs_acc
        jsr abs_value
        pla
        cmp #$2a                ; *
        bne apply_divide
        jsr multiply
        bcs apply_error
        jmp apply_sign
apply_divide:
        lda value
        ora value+1
        ora value+2
        ora value+3
        beq apply_error
        jsr divide
apply_sign:
        lda acc+3               ; a magnitude of 2^31 fits only as a negative
        bpl +
        lda sign
        bpl apply_error
        lda acc+2
        ora acc+1
        ora acc
        bne apply_error
        lda acc+3
        cmp #$80
        bne apply_error
        rts                     ; -2147483648
+       lda sign
        bpl +
        jmp negate_acc
+       rts
apply_error:
        lda #1
        sta error
        rts
abs_acc:
        lda acc+3
        bpl +
negate_acc:
        sec
        ldx #0
        ldy #4
-       lda #0
        sbc acc,x
        sta acc,x
        inx
        dey
        bne -
+       rts
abs_value:
        lda value+3
        bpl +
        sec
        ldx #0
        ldy #4
-       lda #0
        sbc value,x
        sta value,x
        inx
        dey
        bne -
+       rts
; acc = acc * value (unsigned); carry set when the product needs more than 32 bits.
multiply:
        ldx #3
-       lda acc,x
        sta work4,x
        lda #0
        sta acc,x
        dex
        bpl -
        lda #32
        sta count
mul_bit:
        asl acc                 ; acc <<= 1, overflow check
        rol acc+1
        rol acc+2
        rol acc+3
        bcs mul_over
        asl work4               ; the multiplicand's next bit, high first
        rol work4+1
        rol work4+2
        rol work4+3
        bcc +
        clc
        ldx #0
        ldy #4
-       lda acc,x
        adc value,x
        sta acc,x
        inx
        dey
        bne -
        bcs mul_over
+       dec count
        bne mul_bit
        clc
        rts
mul_over:
        sec
        rts
; acc = acc / value (unsigned), truncated; remainder in work4.
divide:
        lda #0
        sta work4
        sta work4+1
        sta work4+2
        sta work4+3
        lda #32
        sta count
div_bit:
        asl acc
        rol acc+1
        rol acc+2
        rol acc+3
        rol work4
        rol work4+1
        rol work4+2
        rol work4+3
        sec
        ldx #0
        ldy #4
-       lda work4,x
        sbc value,x
        sta sub4,x
        inx
        dey
        bne -
        bcc +
        ldx #3
-       lda sub4,x
        sta work4,x
        dex
        bpl -
        inc acc
+       dec count
        bne div_bit
        rts

; value -> text[0..text_len): "Error", or a signed decimal.
format:
        lda error
        beq +
        ldx #4
-       lda t_error,x
        sta text,x
        dex
        bpl -
        lda #5
        sta text_len
        rts
+       ldx #3
-       lda value,x
        sta acc4,x
        dex
        bpl -
        lda value+3
        sta fsign
        bpl +
        sec                     ; the magnitude (2^31 comes out right unsigned)
        ldx #0
        ldy #4
-       lda #0
        sbc acc4,x
        sta acc4,x
        inx
        dey
        bne -
+       lda #0
        sta digits
fmt_digit:                      ; acc4 /= 10, the remainder is the next digit
        lda #0
        sta rem
        ldx #32
-       asl acc4
        rol acc4+1
        rol acc4+2
        rol acc4+3
        rol rem
        lda rem
        cmp #10
        bcc +
        sbc #10
        sta rem
        inc acc4
+       dex
        bne -
        lda rem
        ora #$30
        ldx digits
        sta digit_stack,x
        inc digits
        lda acc4
        ora acc4+1
        ora acc4+2
        ora acc4+3
        bne fmt_digit
        ldx #0
        lda fsign
        bpl +
        lda #$2d
        sta text
        inx
+       ldy digits
-       lda digit_stack-1,y
        sta text,x
        inx
        dey
        bne -
        stx text_len
        rts

; ---- data ---------------------------------------------------------------------------
t_separator: .byte $2d,0
t_title: .byte 67,97,108,99,117,108,97,116,111,114,0   ; ASCII (the build converts .text to PETSCII)
t_error: .byte 69,114,114,111,114
key_labels: .byte $37,$38,$39,$2f,$34,$35,$36,$2a,$31,$32,$33,$2d,$30,$43,$3d,$2b   ; ASCII "789/456*123-0C=+"
key_x: .byte 1,5,9,13, 1,5,9,13, 1,5,9,13, 1,5,9,13
key_y: .byte 3,3,3,3, 5,5,5,5, 7,7,7,7, 9,9,9,9
win_rect: .byte WIN_X,WIN_Y,WIN_W,WIN_H
item: .byte 0
item_ok: .byte 0
handle: .byte 0
want_open: .byte 0
want_close: .byte 0
want_top: .byte 0
want_move: .byte 0
want_redraw: .byte 0
move_rect: .fill 4,0
msg: .fill 8,0
reply: .fill 19,0
wx: .byte 0
wy: .byte 0
cell_x: .byte 0
cell_y: .byte 0
key_i: .byte 0
digit: .byte 0
sign: .byte 0
count: .byte 0
value: .fill 4,0                ; C clears these 12 bytes together
acc: .fill 4,0
op: .byte 0
entering: .byte 0
error: .byte 0
        .byte 0
work4: .fill 4,0
sub4: .fill 4,0
acc4: .fill 4,0
fsign: .byte 0
rem: .byte 0
digits: .byte 0
digit_stack: .fill 10,0
text: .fill 12,0
text_len: .byte 0
end:
        .cerror end > AC_BASE+AC_PAGES*256, "the accessory exceeds its slot"
