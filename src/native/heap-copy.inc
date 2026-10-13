; The MMU half of a heap transfer step, in the system section ($0c00..$0fff):
; bank-0 RAM below $4000, mapped under the 16 KiB common window it opens.
; hchunk (1..HEAP_CHUNK_MAX) bytes between far haddress and hbuffer under one MMU
; switch with IRQs off, instead of a KERNAL far call per byte. The bottom
; 16 KiB stays common (as for bank-1 code), so N_BUFFER and this code remain
; mapped; the caller keeps bank-1 addresses at or above $4000.
HEAP_CHUNK_MAX = 32            ; about 700 cycles with IRQs off
heap_bulk:
        lda haddress
        sta heap_bulk_read+1
        sta heap_bulk_write+1
        sta heap_bulk_fill+1
        lda haddress+1
        sta heap_bulk_read+2
        sta heap_bulk_write+2
        sta heap_bulk_fill+2
        lda hbuffer
        sta heap_bulk_buffer+1
        sta heap_bulk_source+1
        lda hbuffer+1
        sta heap_bulk_buffer+2
        sta heap_bulk_source+2
        ldx #$3f              ; all RAM, bank 0 or 1
        lda hbank
        beq +
        ldx #$7f
+       ldy #0
        php
        sei
        lda $d506
        pha
        ora #3
        sta $d506
        lda $ff00
        pha
        stx $ff00
        lda hoperation
        beq heap_bulk_read
        cmp #2
        beq heap_bulk_value
heap_bulk_source:
        lda N_BUFFER,y
heap_bulk_write:
        sta $ffff,y
        iny
        cpy hchunk
        bne heap_bulk_source
        beq heap_bulk_done
heap_bulk_value:
        lda N_VALUE
heap_bulk_fill:
        sta $ffff,y
        iny
        cpy hchunk
        bne heap_bulk_fill
        beq heap_bulk_done
heap_bulk_read:
        lda $ffff,y
heap_bulk_buffer:
        sta N_BUFFER,y
        iny
        cpy hchunk
        bne heap_bulk_read
heap_bulk_done:
        pla
        sta $ff00
        pla
        sta $d506
        plp
        rts
heap_bulk_end:
