; Foreground 1351 input for native VIC applications. The C128 ROM restores
; CIA1 PRA=$7f after scanning, selecting port 1. Sample once per jiffy in
; raster lines 80..159. Require another 32 raster lines after noticing the
; jiffy: a delayed ROM/observer IRQ may have scanned well after line 255.
; Shared key ownership uses KEYCHK; IRQ vectors, zero page and CIA DDRs stay.
; The two pointer sprites use the owned surface's unused bitmap/pointer tail.
; Call pm_close before any display close, replacement or workspace return.
.weak
PM_KEYS_OWNED=0
PM_KEYS_EXTERNAL=0
PM_SECONDARY=0
.endweak
pm_install:
 .if !PM_KEYS_OWNED
        jsr nk_install
 .endif
        ldx #127
-       lda pm_shape,x
        sta N_BUFFER,x
        dex
        bpl -
        jsr pm_select_surface
        lda #$40
        sta N_OFFSET
        lda #$1f
        sta N_OFFSET+1
        lda #128
        sta N_COUNT
        lda #0
        sta N_COUNT+1
        jsr N_WRITE
        bcs pm_install_return
        lda #$7d
        sta N_BUFFER
        lda #$7e
        sta N_BUFFER+1
        lda #$f8
        sta N_OFFSET
        lda #$23
        sta N_OFFSET+1
        lda #2
        sta N_COUNT
        jsr N_WRITE
        bcs pm_install_return
        php
        sei
        ldy #11
-       ldx pm_registers,y
        lda $d000,x
        sta pm_saved,y
        dey
        bpl -
        lda $0a04
        sta pm_init_saved
        and #$fe               ; bit 0 enables BASIC's sprite motion IRQ hook
        sta $0a04
        lda #1
        sta pm_active
        lda #0
        sta pm_seen
        sta pm_buttons
        sta pm_pending
        sta pm_x+1
        lda #160
        sta pm_x
        sta pm_y
        lda #$ff
        sta pm_tick
        sta pm_arm
        lda $d017
        and #$fc
        sta $d017
        lda $d01b
        and #$fc
        sta $d01b
        lda $d01c
        and #$fc
        sta $d01c
        lda $d01d
        and #$fc
        sta $d01d
        lda #1
        sta $d027              ; sprite 0: white interior, above black outline
        lda #0
        sta $d028
        jsr pm_place
        plp
        clc
pm_install_return:
        rts

pm_close:
        lda pm_active
        beq pm_close_return
        php
        sei
        lda #0
        sta $d015              ; hide before restoring coordinates and format
        sta pm_active
        sta pm_seen
        ldy #11
-       ldx pm_registers,y
        lda pm_saved,y
        sta $d000,x
        dey
        bpl -
        lda pm_init_saved
        sta $0a04
        plp
pm_close_return:
 .if !PM_KEYS_OWNED
        jmp nk_close
 .else
        rts
 .endif

pm_poll:
        lda #0
        sta pm_event
        lda pm_active
        beq pm_poll_return
        bit $d011
        bmi pm_poll_return
        lda $d012
        cmp #80
        bcc pm_poll_return
        cmp #160
        bcs pm_poll_return
        lda $a2
        cmp pm_tick
        beq pm_settling
        sta pm_tick
        lda $d012
        sta pm_sample_line
        lda #1
        sta pm_pending
        rts
pm_settling:
        lda pm_pending
        beq pm_poll_return
        lda $d012
        sec
        sbc pm_sample_line
        cmp #32                ; >=2 ms; no IRQ masking or busy delay
        bcc pm_poll_return
        lda #0
        sta pm_pending
        sta N_READY
        ; Refuse non-ROM CIA configuration rather than changing its ownership.
        lda $dc02
        cmp #$ff
        bne pm_absent
        lda $dc03
        bne pm_absent
        lda $dc00
        cmp #$7f
        bne pm_absent
        lda $d419
        sta pm_pots
        lda $d41a
        sta pm_pots+1
        ; A proportional 1351 produces $40..$bf. Open ports read $ff.
        ldx #1
-       lda pm_pots,x
        cmp #$40
        bcc pm_absent
        cmp #$c0
        bcs pm_absent
        dex
        bpl -
        php
        sei
        lda $d02f
        sta pm_columns
        lda #$ff              ; release both sets of keyboard columns
        sta $dc00
        sta $d02f
        lda $dc01
 .if PM_SECONDARY
        pha
        and #1                ; 1351 right button is port 1 Up
        eor #1
        sta pm_secondary_down
        pla
 .endif
        and #$10              ; port 1 fire is the left mouse button
        eor #$10
        sta pm_down
        lda pm_columns
        sta $d02f
        lda #$7f
        sta $dc00
        plp
        lda pm_seen
        bne pm_move
        inc pm_seen
        lda pm_pots
        sta pm_old
        lda pm_pots+1
        sta pm_old+1
        lda pm_down
        sta pm_buttons        ; held during entry/reconnect cannot launch
        lda #3
        sta $d015
pm_poll_return:
        rts
pm_absent:
        lda #0
        sta pm_seen
        sta pm_buttons
        sta $d015
        lda #$ff
        sta pm_arm
        rts
pm_move:
        lda #0
        sta pm_moved
        lda pm_pots
        ldy pm_old
        jsr pm_delta
        sty pm_old
        bcc pm_vertical
        inc pm_moved
        clc
        adc pm_x
        sta pm_x
        txa
        adc pm_x+1
        sta pm_x+1
        bmi pm_left
        cmp #1
        bcc pm_vertical
        bne pm_right
        lda pm_x
        cmp #64
        bcc pm_vertical
pm_right:
        lda #1
        sta pm_x+1
        lda #63
        bne pm_set_x
pm_left:
        lda #0
        sta pm_x+1
pm_set_x:
        sta pm_x
pm_vertical:
        lda pm_pots+1
        ldy pm_old+1
        jsr pm_delta
        sty pm_old+1
        bcc pm_hit_test
        inc pm_moved
        sta pm_step
        stx pm_step+1
        lda pm_y
        sec
        sbc pm_step
        tay
        lda #0
        sbc pm_step+1
        bmi pm_top
        bne pm_bottom
        cpy #200
        bcc pm_set_y
pm_bottom:
        ldy #199
        bne pm_set_y
pm_top:
        ldy #0
pm_set_y:
        sty pm_y
pm_hit_test:
        jsr pm_place
        jsr pm_find_hit        ; caller returns X=index or $ff
        stx pm_hit
        cpx #pm_control_count
        bcs pm_button
        lda pm_moved
        beq pm_button
        lda #1
        sta pm_event
pm_button:
        lda pm_down
        cmp pm_buttons
        beq pm_poll_return
        sta pm_buttons
        cmp #0
        beq pm_release
        lda pm_hit
        sta pm_arm
        cmp #pm_control_count
        bcs pm_poll_return
        lda #1
        sta pm_event
        rts
pm_release:
        ldx pm_arm
        lda #$ff
        sta pm_arm
        cpx #pm_control_count
        bcs pm_poll_return
        cpx pm_hit
        bne pm_poll_return
        lda #2
        sta pm_event
        rts

; Signed 7-bit circular displacement, one pixel per two counter units.
; Ignore +/-1 without advancing the old counter so subpixel motion accumulates.
; A=new, Y=old -> signed X:A, Y=next old, carry=movement.
pm_delta:
        sty pm_previous
        sta pm_sample
        sec
        sbc pm_previous
        and #$7f
        ldx #0
        cmp #2
        bcc pm_no_delta
        cmp #127
        beq pm_no_delta
        cmp #64
        bcc pm_positive
        ora #$80
        sec
        ror
        dex
        bne pm_delta_done
pm_positive:
        lsr
pm_delta_done:
        ldy pm_sample
        sec
        rts
pm_no_delta:
        txa
        clc
        rts

pm_place:
        lda pm_x
        clc
        adc #24
        sta $d000
        sta $d002
        lda pm_x+1
        adc #0
        beq +
        lda #3
+       sta pm_high
        lda $d010
        and #$fc
        ora pm_high
        sta $d010
        lda pm_y
        clc
        adc #50
        sta $d001
        sta $d003
        rts

pm_active: .byte 0
pm_seen: .byte 0
pm_tick: .byte 0
pm_pending: .byte 0
pm_sample_line: .byte 0
pm_x: .word 0
pm_y: .byte 0
pm_old: .word 0
pm_pots: .word 0
pm_buttons: .byte 0
pm_down: .byte 0
 .if PM_SECONDARY
pm_secondary_down: .byte 0
 .endif
pm_arm: .byte $ff
pm_hit: .byte $ff
pm_event: .byte 0             ; 0=idle, 1=focus hit, 2=activate hit
pm_moved: .byte 0
pm_step: .word 0
pm_columns: .byte 0
pm_previous: .byte 0
pm_sample: .byte 0
pm_high: .byte 0
pm_init_saved: .byte 0
pm_registers: .byte $00,$01,$02,$03,$10,$15,$17,$1b,$1c,$1d,$27,$28
pm_saved: .fill 12,0
pm_shape:
.include "../desktop/pointer-shape.inc"
.if !PM_KEYS_EXTERNAL
.include "keys.inc"
.endif
