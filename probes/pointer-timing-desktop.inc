; Pointer-update timing, bank-0 desktop half. MEASUREMENT BUILD ONLY.
;
; build-native-desktop.py never assembles this file and nothing in target/
; contains it. native_pointer_timing.py copies src/native to a work folder,
; replaces code at five places there with code of the same length (so every
; shipped label keeps its address) and appends this file after the scene:
;
;   desktop.asm             jsr pm_install  -> jsr pt_pm_install
;   desktop.asm             jsr N_KEYIN     -> jsr pt_keyin
;   input/pointer.inc       lda $d419       -> jsr pt_pot_x
;   input/pointer.inc       lda $d41a       -> lda pt_pots+1
;   graphics/vdc-client.inc bp_pointer      -> jmp pt_bp_pointer (5 bytes unused)
;
; Still the shipped path: the 1351 sampling schedule (pm_poll: once per
; jiffy in raster lines 80..159, read 32 lines after the jiffy), the port-1
; presence and button reads, the motion filter (pm_delta), the hit test and
; sprite placement, the op-3 bank call (bp_arguments, the bk_call gate and
; its checks), the service's argument checks, vd_poll (hide and redraw the
; pointer through the real 8563 with its real status handshake), the status
; record and the return.
;
; Not the shipped path: the two pot values, which come from pt_drive instead
; of SID $d419/$d41a (a physical 1351 stays still and is ignored); the key
; PT_KEY, which starts the run; and the CIA2 timer B start/stop/record code.
;
; Counter: CIA2 timer B, one-shot from $ffff, counting phi2 (every 1 MHz
; system cycle, including cycles the VIC steals and IRQ time). Kestrel uses
; only CIA2 port A (VIC bank, IEC) and never enables a CIA2 interrupt, so the
; timer's interrupt mask stays clear and no NMI results; CRB bit 7 (TOD alarm
; select) is kept and PB7 output stays off. The timer is stopped while the
; instrumentation saves counts, so that work is not timed.
;
; Each timed segment starts with pt_start (the timer runs from its STX, then
; RTS) and ends with JSR pt_stop (JSR and LDX before the STX). pt_cal holds
; that empty-segment count; pt_install also times known 1001- and 2002-cycle
; loops at raster line 250, where the VIC steals no cycles.
;
; Per update (op-3 bank call while measuring), three segments with one timer:
;   pre     pt_start .. the service hook (bp_arguments, gate in, op checks)
;   service the service's JSR vd_poll .. its RTS (pointer-timing-service.inc)
;   post    service hook .. bp_invoke's RTS (status record, gate out, copy)
; With E = pt_cal empty count and E1 = the service's own empty count:
;   service cycles = service - E1      (exactly JSR vd_poll + body + RTS)
;   call cycles    = pre + service + post - 2E - E1 - 12
;                  (the shipped bp_pointer through bp_invoke's RTS; 12 is the
;                  JSR pt_bp_shipped and the service hook's extra RTS)

PT_UPDATES = 512                ; recorded updates
PT_KEY   = $54                ; "T"; the shipped desktop ignores it
PT_MAIL  = 48                 ; N_BUFFER+48..54, written by the service hook
PT_X     = 308                ; wiggle origin; x >= 304 hits no card
PT_Y     = 20
PT_YMAX  = 179                ; the whole 16-row pointer stays on the bitmap

; One update into slot X of the first (offset 0) or second (256) page.
pt_put .macro offset
        lda N_BUFFER+PT_MAIL+1
        sta pt_pre_lo+\offset,x
        lda N_BUFFER+PT_MAIL+2
        sta pt_pre_hi+\offset,x
        lda N_BUFFER+PT_MAIL+3
        sta pt_svc_lo+\offset,x
        lda N_BUFFER+PT_MAIL+4
        sta pt_svc_hi+\offset,x
        lda pt_lo
        sta pt_post_lo+\offset,x
        lda pt_hi
        sta pt_post_hi+\offset,x
        lda pt_jiffy
        sta pt_jif+\offset,x
        lda $a2
        sec
        sbc pt_jiffy
        sta pt_irq+\offset,x
.endm

pt_pm_install:
        jsr pt_install
        jmp pm_install

pt_install:
        php
        sei
        lda $dd0f
        sta pt_crb
        and #$80              ; keep the TOD alarm-select bit only
        sta pt_halt
        ora #$19              ; start, one-shot, force load, count phi2
        sta pt_run
        lda pt_halt
        sta $dd0f
        lda #$ff
        sta $dd06
        sta $dd07             ; latch $ffff (also loads the stopped counter)
        lda $d015
        sta pt_sprites
        jsr pt_sync
        jsr pt_start          ; empty segment
        jsr pt_stop
        lda pt_lo
        sta pt_cal
        lda pt_hi
        sta pt_cal+1
        jsr pt_start          ; 1001 cycles
        ldx #200
pt_loop1:
        dex
        bne pt_loop1
        jsr pt_stop
        lda pt_lo
        sta pt_cal+2
        lda pt_hi
        sta pt_cal+3
        jsr pt_start          ; 2002 cycles
        ldx #200
pt_loop2:
        dex
        bne pt_loop2
        ldx #200
pt_loop3:
        dex
        bne pt_loop3
        jsr pt_stop
        lda pt_lo
        sta pt_cal+4
        lda pt_hi
        sta pt_cal+5
        plp
        rts
.cerror (pt_loop1 >> 8) != ((pt_loop1+3) >> 8), "calibration branch crosses a page"
.cerror (pt_loop2 >> 8) != ((pt_loop2+3) >> 8), "calibration branch crosses a page"
.cerror (pt_loop3 >> 8) != ((pt_loop3+3) >> 8), "calibration branch crosses a page"

pt_sync:                      ; return on raster line 250; calibration ends
-       bit $d011             ; before line 48, the first possible badline
        bmi -
        lda $d012
        cmp #250
        bne -
        rts

pt_start:                     ; the timer runs from this STX; the RTS is timed
        ldx pt_run
        stx $dd0f
        rts
pt_stop:                      ; JSR and LDX are timed; keeps A and carry
        ldx pt_halt
        stx $dd0f
        php
        pha
        lda $dd06
        eor #$ff
        sta pt_lo
        lda $dd07
        eor #$ff
        sta pt_hi
        pla
        plp
        rts

pt_keyin:
        jsr N_KEYIN
        beq pt_keyin_return
        cmp #PT_KEY
        bne pt_keyin_return   ; any other key goes on unchanged
        lda pt_phase
        bne +
        inc pt_phase          ; 0 -> 1: approach the wiggle origin
+       lda #0
        sta N_READY           ; as for any key; the loop publishes it again
pt_keyin_return:
        rts

pt_pot_x:
        jsr pt_drive
        lda pt_pots
        rts

; The next sample's counters. Built from pm_old, so the move pm_delta sees
; is exactly the one asked for (two counts per pixel, under PM_JUMP).
pt_drive:
        lda pm_old
        sta pt_pots
        lda pm_old+1
        sta pt_pots+1
        lda pm_seen
        beq pt_drive_return   ; the first sample only takes the baseline
        lda pt_phase
        cmp #1
        beq pt_approach
        cmp #2
        beq pt_wiggle
pt_drive_return:
        rts
pt_approach:                  ; x along y=160 (below the cards), then y at x=308
        sec
        lda #<PT_X
        sbc pm_x
        tay
        lda #>PT_X
        sbc pm_x+1
        bmi pt_left
        bne pt_right5
        tya
        beq pt_vertical
        cmp #6
        bcc pt_set_x
pt_right5:
        lda #5
        bne pt_set_x
pt_left:
        cmp #$ff
        bne pt_left5
        tya
        cmp #$fb
        bcs pt_set_x
pt_left5:
        lda #$fb
        bne pt_set_x
pt_vertical:
        lda pm_y
        sec
        sbc #PT_Y
        beq pt_arrived
        bcc pt_down
        cmp #6                ; above the origin's row: up by min(y-PT_Y, 5)
        bcc +
        lda #5
+       eor #$ff
        clc
        adc #1
        bne pt_set_y
pt_down:
        eor #$ff              ; PT_Y-y
        clc
        adc #1
        cmp #6
        bcc pt_set_y
        lda #5
        bne pt_set_y
pt_arrived:
        lda #2
        sta pt_phase
pt_wiggle:                    ; dx +5/-5, dy 3 (bench_native_perf's desktop wiggle)
        lda pt_ydir
        bmi pt_wiggle_up
        lda pm_y
        cmp #PT_YMAX-2
        bcc pt_wiggle_y
        lda #$fd
        sta pt_ydir
        bne pt_wiggle_y
pt_wiggle_up:
        lda pm_y
        cmp #PT_Y+3
        bcs pt_wiggle_y
        lda #3
        sta pt_ydir
pt_wiggle_y:
        lda pt_ydir
        jsr pt_set_y
        lda pt_driven
        lsr
        lda #5
        bcc +
        lda #$fb
+       inc pt_driven
        bne pt_set_x
        inc pt_driven+1
pt_set_x:                     ; A = signed pixels
        asl
        clc
        adc pm_old
        cmp #$ff              ; $ff reads as no mouse; $7f is the same 7-bit move
        bne +
        lda #$7f
+       sta pt_pots
        rts
pt_set_y:                     ; the 1351's Y counter falls as the pointer moves down
        asl
        eor #$ff
        sec
        adc pm_old+1
        cmp #$ff
        bne +
        lda #$7f
+       sta pt_pots+1
        rts

pt_bp_pointer:
        lda $a2
        sta pt_jiffy
        lda #0
        sta N_BUFFER+PT_MAIL  ; the service hook sets $a5 with its counts
        jsr pt_start          ; pre begins
        jsr pt_bp_shipped
        jsr pt_stop           ; post ends; A and carry are bp_invoke's
        php
        pha
        inc pt_calls
        bne +
        inc pt_calls+1
+       lda pt_phase
        cmp #2
        bne pt_finish_return
        lda N_BUFFER+PT_MAIL
        cmp #$a5
        beq pt_record
        inc pt_missing
        jmp pt_finish_return
pt_record:
        lda N_BUFFER+PT_MAIL+5
        sta pt_svc_cal
        lda N_BUFFER+PT_MAIL+6
        sta pt_svc_cal+1
        ldx pt_count
        lda pt_count+1
        bne pt_record_high
        #pt_put 0
        jmp pt_recorded
pt_record_high:
        #pt_put 256
pt_recorded:
        inc pt_count
        bne +
        inc pt_count+1
+       lda pt_count
        cmp #<PT_UPDATES
        bne pt_finish_return
        lda pt_count+1
        cmp #>PT_UPDATES
        bne pt_finish_return
        lda #3
        sta pt_phase          ; done: pt_drive stops moving the pointer
pt_finish_return:
        pla
        plp
        rts
pt_bp_shipped:                ; the shipped bp_pointer, verbatim
        jsr bp_arguments
        lda #3
        jmp bp_invoke

; Read by the host (VICE monitor or a native capture) after pt_phase is 3.
pt_header:
        .byte $50,$54,$49,$4d ; +0 "PTIM" in ASCII
        .byte 1               ; +4 layout
pt_phase:   .byte 0           ; +5 0 waiting for PT_KEY, 1 approach, 2 measuring, 3 done
pt_count:   .word 0           ; +6 recorded updates
            .word PT_UPDATES    ; +8
pt_driven:  .word 0           ; +10 wiggle samples issued
pt_missing: .byte 0           ; +12 measured calls without the service's counts
pt_crb:     .byte 0           ; +13 CIA2 CRB before setup
pt_halt:    .byte 0           ; +14
pt_run:     .byte 0           ; +15
pt_cal:     .fill 6,0         ; +16 empty, 1001-cycle and 2002-cycle segments
pt_svc_cal: .word 0           ; +22 the service's empty segment
pt_sprites: .byte 0           ; +24 $d015 during calibration
pt_ydir:    .byte 3           ; +25
pt_jiffy:   .byte 0           ; +26
pt_lo:      .byte 0           ; +27
pt_hi:      .byte 0           ; +28
pt_pots:    .word 0           ; +29
pt_calls:   .word 0           ; +31 every op-3 call since the desktop started
            .word pt_pre_lo   ; +33 first array; each holds PT_UPDATES bytes
pt_header_end:
pt_pre_lo:  .fill PT_UPDATES,0
pt_pre_hi:  .fill PT_UPDATES,0
pt_svc_lo:  .fill PT_UPDATES,0
pt_svc_hi:  .fill PT_UPDATES,0
pt_post_lo: .fill PT_UPDATES,0
pt_post_hi: .fill PT_UPDATES,0
pt_jif:     .fill PT_UPDATES,0  ; $a2 when the call began
pt_irq:     .fill PT_UPDATES,0  ; jiffies that passed during the call
pt_arrays_end:
; native_app_pack needs 48 unused bytes after the image in its last page.
pt_tail = (* - N_APPBASE) & 255
.if pt_tail == 0 || pt_tail > 208
        .fill 257-pt_tail,0
.endif
