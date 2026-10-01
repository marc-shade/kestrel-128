; Native keyboard ownership. Called once at startup, after relocation.
; $3d1c..$3d1f is reserved kernel metadata, outside the public ABI fields.
native_keycheck_saved = $3d1c
native_key_rejects = $3d1e       ; word, wraps like N_KEYS; reset at native start
native_keyboard_init:
        php
        sei
        lda $033c
        cmp #<native_keycheck
        bne native_keyboard_install
        lda $033d
        cmp #>native_keycheck
        beq native_keyboard_ready ; native restart must not chain to itself
native_keyboard_install:
        lda $033c
        sta native_keycheck_saved
        lda $033d
        sta native_keycheck_saved+1
        lda #<native_keycheck
        sta $033c
        lda #>native_keycheck
        sta $033d
native_keyboard_ready:
        lda #0
        sta native_key_rejects
        sta native_key_rejects+1
        plp
        rts

native_keyboard_end:
