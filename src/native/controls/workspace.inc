; Own and initialize buffers outside the executable slot before using them.
; $5000 query/picker scratch (512), $5200 panel body (512), $5400 saved keys,
; $5500 retained picker paths (768), $5800 picker pages/path/record (532),
; $5a20 model (64), $5a60 status (32), $5ac0 graphical text (64).
; The final app-owner release frees this allocation after display/key cleanup.
ug_workspace:
        lda N_CURRENT
        sta N_OWNER
        lda #0
        sta N_BANK
        lda #$50
        sta N_PAGE
        lda #11
        sta N_PAGES
        jsr N_RESERVE
        bcs ug_workspace_done
        lda #0
        sta N_OFFSET
        sta N_OFFSET+1
        sta N_COUNT
        sta N_VALUE
        lda #1
        sta N_COUNT+1
-       jsr N_FILL
        bcs ug_workspace_done
        inc N_OFFSET+1
        lda N_OFFSET+1
        cmp #11
        bne -
        lda #0
        clc
ug_workspace_done:
        rts
