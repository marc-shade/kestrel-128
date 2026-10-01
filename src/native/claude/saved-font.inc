; Saved VDC font in an owned allocation, retained until restoration completes.
; Read/write one complete 512-byte chunk; A is the byte offset's high byte.
.export sf_read, sf_token
.bss
sf_token: .res 4
sf_offset: .res 1
sf_chunk: .res 1
.code
sf_open:
        lda N_CURRENT
        sta N_OWNER
        lda #16
        sta N_PAGES
        lda #$ff
        sta N_BANK
        jsr N_ALLOC
        bcs @return
        ldx #3
@save: lda N_HANDLE,x
        sta sf_token,x
        dex
        bpl @save
        lda #0
@return:ldx #0
        rts
sf_select:
        sta sf_offset
        lda N_CURRENT
        sta N_OWNER
        ldx #3
@token:lda sf_token,x
        sta N_HANDLE,x
        dex
        bpl @token
        lda #0
        sta N_OFFSET
        sta N_COUNT
        lda sf_offset
        sta N_OFFSET+1
        lda #2
        sta N_COUNT+1
        rts
sf_read:
        jsr sf_select
        jmp N_READ
sf_write:
        jsr sf_select
        jmp N_WRITE
sf_close:
        lda sf_token
        beq @done
        lda #0
        jsr sf_select
        jsr N_FREE
        bcs @return
        lda #0
        sta sf_token
@done: clc
@return:rts
