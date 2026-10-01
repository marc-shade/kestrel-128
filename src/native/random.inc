; Random numbers (docs/NATIVE-SERVICES.md), GPL v3: the Atari XBIOS Random
; generator. seed = seed * 3141592621 + 1 (mod 2^32); the result is bits
; 8..31 of the new seed. No kernel calls; any code may include it.
;
; rn_random: A/X/Y = the 24-bit result (low, middle, high). A zero seed is
;            first replaced by one taken from the jiffy clock, the raster
;            and CIA 1 timer A, as TOS seeds from its 200 Hz timer.
; rn_seed:   rn_state (4 bytes, little-endian) may be set directly to repeat
;            a sequence.
rn_random:
        lda rn_state
        ora rn_state+1
        ora rn_state+2
        ora rn_state+3
        bne rn_step
        php                     ; an unseeded generator: the clocks
        sei
        lda $a2
        sta rn_state
        lda $d012
        sta rn_state+1
        lda $dc04
        sta rn_state+2
        lda $a1
        ora #1                  ; never zero
        sta rn_state+3
        plp
rn_step:
        ldx #3                  ; rn_a = seed; seed = 0
-       lda rn_state,x
        sta rn_a,x
        lda #0
        sta rn_state,x
        dex
        bpl -
        ldx #3                  ; rn_b = the multiplier 3141592621 = $bb40e62d
-       lda rn_multiplier,x
        sta rn_b,x
        dex
        bpl -
        ldy #32                 ; shift-and-add, keeping the low 32 bits
rn_bit:
        lsr rn_b+3
        ror rn_b+2
        ror rn_b+1
        ror rn_b
        bcc +
        clc
        lda rn_state
        adc rn_a
        sta rn_state
        lda rn_state+1
        adc rn_a+1
        sta rn_state+1
        lda rn_state+2
        adc rn_a+2
        sta rn_state+2
        lda rn_state+3
        adc rn_a+3
        sta rn_state+3
+       asl rn_a
        rol rn_a+1
        rol rn_a+2
        rol rn_a+3
        dey
        bne rn_bit
        inc rn_state            ; + 1
        bne +
        inc rn_state+1
        bne +
        inc rn_state+2
        bne +
        inc rn_state+3
+       lda rn_state+1
        ldx rn_state+2
        ldy rn_state+3
        rts
rn_multiplier: .byte $2d,$e6,$40,$bb
rn_state: .fill 4,0
rn_a: .fill 4,0
rn_b: .fill 4,0
