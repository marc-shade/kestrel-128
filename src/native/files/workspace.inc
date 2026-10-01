; One owned 16-page workspace, reserved before keyboard or display ownership.
; $5000..$57ff is shared by the mutually exclusive graphics and picker modules:
; graphics body/previous body; picker records, paths and saved caller arguments.
; $5800..$5bff copy/verify scratch, $5c00 keys, $5d00 source name,
; $5e00 byte viewer, $5e80 text renderer. Field descriptors stay in the app.
fg_workspace:
        lda N_CURRENT
        sta N_OWNER
        lda #0
        sta N_BANK
        lda #$50
        sta N_PAGE
        lda #16
        sta N_PAGES
        jsr N_RESERVE
        bcs fg_workspace_done
        lda #0
        sta N_OFFSET
        sta N_OFFSET+1
        sta N_COUNT
        sta N_VALUE
        lda #2
        sta N_COUNT+1
fg_workspace_clear:
        jsr N_FILL
        bcs fg_workspace_done
        inc N_OFFSET+1
        inc N_OFFSET+1
        lda N_OFFSET+1
        cmp #16
        bne fg_workspace_clear
        lda #0
        clc
fg_workspace_done:
        rts
