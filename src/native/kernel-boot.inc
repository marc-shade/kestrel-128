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
        jsr rc_probe
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

; REU module cache (module-cache.inc): find an idle REU and its size with
; two-byte DMA probes at offset 0 of each power-of-two bank, restoring every
; probed byte. With 512 KiB or more, reserve its top 64 KiB bank: publish
; N_RCACHE and write an empty directory. Otherwise N_RCACHE stays zero.
RC_PROBEBUF = N_BUFFER             ; +0/1 data, +2/3 bank 0, +4/5 bank N
rc_probe:
        lda #0
        sta N_RCACHE
        sta rc_bank
        lda $df01
        bmi rc_probe_done       ; busy or absent: no cache
        lda $df09
        and #$e0
        bne rc_probe_done
        lda $df09
        and #31
        cmp #31
        bne rc_probe_done
        lda $df0a
        and #63
        cmp #63
        bne rc_probe_done
        jsr rc_probe_read
        bcs rc_probe_done
        lda RC_PROBEBUF
        sta RC_PROBEBUF+2
        lda RC_PROBEBUF+1
        sta RC_PROBEBUF+3
        lda #$55
        ldx #$aa
        jsr rc_probe_write
        bcs rc_probe_restore
        jsr rc_probe_read
        bcs rc_probe_restore
        lda RC_PROBEBUF
        cmp #$55
        bne rc_probe_restore
        lda RC_PROBEBUF+1
        cmp #$aa
        bne rc_probe_restore
        lda #1
        sta rc_probe_bank
rc_probe_next:
        lda rc_probe_bank
        sta rc_bank
        jsr rc_probe_read
        bcs rc_probe_restore
        lda RC_PROBEBUF
        sta RC_PROBEBUF+4
        lda RC_PROBEBUF+1
        sta RC_PROBEBUF+5
        lda #$a5
        ldx #$5a
        jsr rc_probe_write
        bcs rc_probe_restore
        jsr rc_probe_read
        bcs rc_probe_restore
        lda RC_PROBEBUF            ; a missing bank does not keep both bytes
        cmp #$a5
        bne rc_probe_limit
        lda RC_PROBEBUF+1
        cmp #$5a
        bne rc_probe_limit
        lda #0                  ; a wrapped bank changed bank 0's marker
        sta rc_bank
        jsr rc_probe_read
        bcs rc_probe_restore
        lda RC_PROBEBUF
        cmp #$55
        bne rc_probe_limit
        lda RC_PROBEBUF+1
        cmp #$aa
        bne rc_probe_limit
        jsr rc_probe_restore_n
        bcs rc_probe_restore
        asl rc_probe_bank
        bne rc_probe_next
        lda #0                  ; 256 banks, 16 MiB
        beq rc_probe_size
rc_probe_limit:
        jsr rc_probe_restore_n
        bcs rc_probe_restore
        lda rc_probe_bank
rc_probe_size:
        sta rc_probe_banks      ; 0 means 256
        jsr rc_probe_restore
        bcs rc_probe_done
        lda rc_probe_banks
        beq +
        cmp #8
        bcc rc_probe_done       ; below 512 KiB: no cache
+       sec
        sbc #1
        sta rc_bank             ; top bank
        lda #0
        ldx #1
        jsr rc_probe_write      ; empty directory: count 0, next unit 1
        bcs rc_probe_done
        lda #16
        sta N_RCACHE
rc_probe_done:
        rts
rc_probe_restore_n:
        lda rc_probe_bank
        sta rc_bank
        lda RC_PROBEBUF+4
        ldx RC_PROBEBUF+5
        jmp rc_probe_write
rc_probe_restore:
        lda #0
        sta rc_bank
        lda RC_PROBEBUF+2
        ldx RC_PROBEBUF+3
        jsr rc_probe_write
        lda #0
        sta rc_bank
        rts
rc_probe_read:
        lda #$91
        bne rc_probe_dma
rc_probe_write:
        sta RC_PROBEBUF
        stx RC_PROBEBUF+1
        lda #$90
rc_probe_dma:
        ldx #<RC_PROBEBUF
        stx rc_host
        ldx #>RC_PROBEBUF
        stx rc_host+1
        ldx #0
        stx rc_reu
        stx rc_reu+1
        stx rc_length+1
        ldx #2
        stx rc_length
        jmp rc_dma
rc_probe_bank: .byte 0
rc_probe_banks: .byte 0
