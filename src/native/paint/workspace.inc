; Direct scratch is separately owned below the executable window. Field
; descriptors and their editable buffers remain in the loader's app handle.
; $5000..$53ff picker cache scratch, $5400..$55ff file comparison,
; $5600..$56ff keyboard backup, $5700..$5913 picker data, $5940..$597f text.
pa_work_init:
        lda N_CURRENT
        sta N_OWNER
        lda #0
        sta N_BANK
        lda #$50
        sta N_PAGE
        lda #10
        sta N_PAGES
        jsr N_RESERVE
        bcs pa_work_return
        lda #0
        sta N_OFFSET
        sta N_OFFSET+1
        sta N_COUNT
        sta N_VALUE
        lda #2
        sta N_COUNT+1
pa_work_clear:
        jsr N_FILL
        bcs pa_work_return
        inc N_OFFSET+1
        inc N_OFFSET+1
        lda N_OFFSET+1
        cmp #10
        bne pa_work_clear
        lda #0
        clc
pa_work_return:
        rts
