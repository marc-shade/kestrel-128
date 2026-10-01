; Foreground ownership of the ROM function-key table and mouse-line KEYCHK
; filter. A client that keeps a text picker active may own this independently
; of its sprite/display lifetime; ordinary pointer clients install/close here.
.weak
NK_SAVED_BUFFER=0
.endweak
nk_install:
        lda nk_active
        bne nk_return
        php
        sei
        ldx #0
-       lda $1000,x
        sta nk_saved_keys,x
        inx
        bne -
        ldx #9
-       lda #1
        sta $1000,x
        lda nk_codes,x
        sta $100a,x
        dex
        bpl -
        lda #0
        sta $d1
        sta $d2
        ldx #0
-       lda nk_filter_image,x
        sta pk_entry,x
        inx
        cpx #pk_end-pk_entry
        bne -
        lda $033c
        sta nk_saved_callback
        sta pk_next
        lda $033d
        sta nk_saved_callback+1
        sta pk_next+1
        lda #<pk_entry
        sta $033c
        lda #>pk_entry
        sta $033d
        lda #1
        sta nk_active
        plp
nk_return:
        rts
nk_close:
        lda nk_active
        beq nk_return
        php
        sei
        lda #0
        sta nk_active
        lda nk_saved_callback
        sta $033c
        lda nk_saved_callback+1
        sta $033d
        ldx #0
-       lda nk_saved_keys,x
        sta $1000,x
        inx
        bne -
        lda #0
        sta $d1
        sta $d2
        plp
        rts
nk_active: .byte 0
nk_codes: .byte $85,$89,$86,$8a,$87,$8b,$88,$8c,$83,$84
.if NK_SAVED_BUFFER
nk_saved_keys=NK_SAVED_BUFFER
.else
nk_saved_keys: .fill 256,0
.endif
nk_saved_callback: .word 0
.include "key-filter.inc"
