; Resident-kernel half of N_READ/N_WRITE/N_FILL (heap.inc keeps the checks
; and the loop): one transfer step per call. Runs below $4000, so it stays
; mapped under the 16 KiB common window heap_bulk opens.
heap_transfer_step:
        lda #1
        sta hchunk
        lda hbank             ; bank-1 pages under the 16 KiB common window
        beq heap_transfer_run ; ($04..$3f) take the byte path
        lda haddress+1
        cmp #$40
        bcc heap_transfer_byte
heap_transfer_run:
        lda #HEAP_CHUNK_MAX
        ldx hremaining+1
        bne +
        cmp hremaining
        bcc +
        lda hremaining
+       sta hchunk
        jsr heap_bulk
        jmp heap_transferred
heap_transfer_byte:
        lda hbuffer
        sta heap_buffer_read+1
        sta heap_buffer_write+1
        lda hbuffer+1
        sta heap_buffer_read+2
        sta heap_buffer_write+2
        lda hoperation
        beq heap_read_byte
        cmp #2
        beq heap_fill_byte
heap_buffer_read:
        lda N_BUFFER
        jmp heap_write_byte
heap_fill_byte:
        lda N_VALUE
heap_write_byte:
        jsr heap_far_store
        jmp heap_transferred
heap_read_byte:
        jsr heap_far_fetch
heap_buffer_write:
        sta N_BUFFER
heap_transferred:
        clc
        lda haddress
        adc hchunk
        sta haddress
        bcc +
        inc haddress+1
+       clc
        lda hbuffer
        adc hchunk
        sta hbuffer
        bcc +
        inc hbuffer+1
+       sec
        lda hremaining
        sbc hchunk
        sta hremaining
        bcs +
        dec hremaining+1
+       ora hremaining+1      ; Z: the transfer is complete
        rts
