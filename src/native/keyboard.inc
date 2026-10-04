; Native keyboard ownership, installed once at startup by native_keyboard_init
; (kernel-boot.inc). $3d1c..$3d1f is reserved kernel metadata, outside the
; public ABI fields.
native_keycheck_saved = $3d1c
native_key_rejects = $3d1e       ; word, wraps like N_KEYS; reset at native start
