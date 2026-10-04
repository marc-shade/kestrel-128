; Cold-boot code, GPL v3. It runs once from the boot staging pages, after
; the resident low section image and before the system section image, and is reused
; by the heap with them. Nothing resident may call into this file after boot.
; Entered from native_start (resident, below $4000) with the native map set.
native_boot:
        jsr native_relocate
        jsr native_keyboard_init
        lda #0
        sta $d030               ; both displays: remain at 1 MHz
        sta N_READY
        sta N_KEYS
        sta N_KEYS+1
        sta ui_status
        sta N_CURRENT
        sta N_APPSTATE
        sta N_EXITCODE
        sta N_APPERROR
        sta N_UIBUSY
        sta N_BROWSERERROR
        sta N_BROWSERNAME_LEN
        ldx #4
native_browser_position:
        sta N_DESKTOPSEL,x       ; reset selection and four-byte browser position
        sta N_DOCREQUEST,x       ; reset the complete one-launch document packet
        dex
        bpl native_browser_position
        lda #NATIVE_BOOT_FORMAT
        sta N_BOOTFORMAT
        sta N_BROWSERFMT
        sta N_APPFORMAT
        lda #1
        sta N_BROWSERLEN
        lda #$2f
        sta N_BROWSERPATH
        lda $ba
        sta N_DEVICE
        sta ui_system_device
        sta N_BOOTDEVICE
        sta N_BROWSERDEV
        jsr heap_init
        jsr sys_install
        jmp native_resume

; Copy the resident low section before initializing or allocating memory.
; The source extends into initially free RAM and must never be used again
; once the heap owns it. Preserve D/I and reset the operands for repeat entry.
native_relocate:
        php
        cld
        ldx #0
        ldy #native_low_pages
native_relocate_byte:
        lda N_RELOCBASE,x
native_relocate_store:
        sta N_LOWBASE,x
        inx
        bne native_relocate_byte
        inc native_relocate_byte+2
        inc native_relocate_store+2
        dey
        bne native_relocate_byte
        lda #>N_RELOCBASE
        sta native_relocate_byte+2
        lda #>N_LOWBASE
        sta native_relocate_store+2
        plp
        rts

; Native keyboard ownership (keyboard.inc). Called once, after relocation.
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

; Page tables: every page reserved, then the two managed pools free.
heap_init:
        lda #0
        sta N_BUSY
        sta N_ERROR
        ldx #0
heap_clear_handles:
        sta NHANDLES,x
        inx
        bne heap_clear_handles
        lda #$ff
heap_reserve_pages:
        sta NPAGES0,x
        sta NPAGES1,x
        inx
        bne heap_reserve_pages
        lda #0
        ldx #N_FIRST0
heap_free_zero:
        sta NPAGES0,x
        inx
        cpx #$ff
        bne heap_free_zero
        ldx #N_FIRST1
heap_free_one:
        sta NPAGES1,x
        inx
        cpx #$ff
        bne heap_free_one
        rts

; Copy the system section image to N_SYSBASE. Preserve D/I; the image carries
; all of the section's initial state (the workspace's handles and bank).
sys_install:
        php
        ldx #0
sys_install_byte:
        lda native_sys_image,x
sys_install_store:
        sta N_SYSBASE,x
        inx
        bne sys_install_byte
        inc sys_install_byte+2
        inc sys_install_store+2
        lda sys_install_store+2
        cmp #>N_SYSLIMIT
        bne sys_install_byte
        lda #>native_sys_image
        sta sys_install_byte+2
        lda #>N_SYSBASE
        sta sys_install_store+2
        plp
        rts
