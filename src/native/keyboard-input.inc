; GETIN returns through the ROM gateway with the caller's $0e mapping.
; Place foreground code in the spare service interval to keep the callback
; visible under BASIC ROM without reserving another heap page.
native_keyin:
        jsr $ffe4
        beq native_no_key
        sta N_LASTKEY
        ldx #0
        stx N_READY
        inc N_KEYS
        bne native_key_done
        inc N_KEYS+1
native_key_done:
        lda N_LASTKEY
native_no_key:
        rts
native_keyin_end:
