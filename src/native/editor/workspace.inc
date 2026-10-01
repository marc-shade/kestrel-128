; Retained document buffers and keyboard backup precede mutually exclusive
; graphical body/cache and picker paths. Reserve before keys or documents.
; $5000..$55ff document buffers, $5600 keys, $5700 document contexts;
; $5800..$5f17 graphical body/cache or inactive picker records/retained paths;
; $5f18..$5f3e document scratch, $5f40..$5f68 VDC status, $5f69..$5f9b
; editor row starts, $5fc0..$5fff text scratch. All remain owned across modules.
eg_workspace:
        lda N_CURRENT
        sta N_OWNER
        lda #0
        sta N_BANK
        lda #$50
        sta N_PAGE
        lda #16
        sta N_PAGES
        jsr N_RESERVE
        bcs eg_workspace_done
        lda #0
        sta N_OFFSET
        sta N_OFFSET+1
        sta N_COUNT
        sta N_VALUE
        lda #2
        sta N_COUNT+1
eg_workspace_clear:
        jsr N_FILL
        bcs eg_workspace_done
        inc N_OFFSET+1
        inc N_OFFSET+1
        lda N_OFFSET+1
        cmp #16
        bne eg_workspace_clear
        lda #0
        clc
eg_workspace_done:
        rts
