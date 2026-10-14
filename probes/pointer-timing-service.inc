; Pointer-update timing, bank-1 VDC service half. MEASUREMENT BUILD ONLY.
;
; Never part of target/vdsvc.prg. native_pointer_timing.py replaces two
; instructions of a copy of vdc-service.asm with ones of the same length and
; appends this file before bv_end:
;
;   bv_pointer  jsr vd_poll        -> jsr pt_svc_poll
;   bv_open     jmp bv_scene_open  -> jmp pt_svc_open
;
; vd_poll itself (pointer hide and redraw through the 8563) is the shipped
; code, called from here instead of from bv_pointer. A vd_poll failure
; returns here too: vd_gate keeps the stack depth of vd_poll's own caller.
; See pointer-timing-desktop.inc for the counter and the segments.

pt_svc_open:                  ; op 1: the parent already latched $ffff
        php
        sei
        lda $dd0f
        and #$80
        sta pt_svc_halt
        ora #$19
        sta pt_svc_run
        jsr pt_svc_sync
        jsr pt_svc_start
        jsr pt_svc_stop
        lda pt_svc_lo
        sta pt_svc_cal
        lda pt_svc_hi
        sta pt_svc_cal+1
        plp
        jmp bv_scene_open

pt_svc_poll:
        ldx pt_svc_halt
        stx $dd0f             ; pre ends
        lda $dd06
        eor #$ff
        sta N_BUFFER+48+1
        lda $dd07
        eor #$ff
        sta N_BUFFER+48+2
        jsr pt_svc_start      ; service begins
        jsr vd_poll           ; shipped
        jsr pt_svc_stop       ; service ends; keeps A and carry
        php
        pha
        lda pt_svc_lo
        sta N_BUFFER+48+3
        lda pt_svc_hi
        sta N_BUFFER+48+4
        lda pt_svc_cal
        sta N_BUFFER+48+5
        lda pt_svc_cal+1
        sta N_BUFFER+48+6
        lda #$a5
        sta N_BUFFER+48
        pla
        plp
        jsr pt_svc_start      ; post begins; LDX/STX keep A and carry
        rts

pt_svc_sync:
-       bit $d011
        bmi -
        lda $d012
        cmp #250
        bne -
        rts
pt_svc_start:
        ldx pt_svc_run
        stx $dd0f
        rts
pt_svc_stop:
        ldx pt_svc_halt
        stx $dd0f
        php
        pha
        lda $dd06
        eor #$ff
        sta pt_svc_lo
        lda $dd07
        eor #$ff
        sta pt_svc_hi
        pla
        plp
        rts
pt_svc_halt: .byte 0
pt_svc_run:  .byte 0
pt_svc_lo:   .byte 0
pt_svc_hi:   .byte 0
pt_svc_cal:  .word 0
