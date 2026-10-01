; Resident teardown survives app release and needs no file or heap operation.
display_restore:
        lda v_tag
        beq display_restored
        php
        sei
        lda $dd00
        and #$fc
        ora v_bank
        sta $dd00
        lda v_d018
        sta $d018
        lda v_d016
        sta $d016
        lda #$ff
        sta $d012
        lda v_d011
        sta $d011
        lda $01
        and #$f9
        ora v_port
        sta $01
        lda #0
        sta $d8
        sta v_tag
        plp
display_restored:
        rts
v_tag:  .byte 0
v_d011: .byte 0
v_d016: .byte 0
v_d018: .byte 0
v_bank: .byte 0
v_port: .byte 0
native_display_restore_end:
