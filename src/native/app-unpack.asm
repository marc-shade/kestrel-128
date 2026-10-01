; Transient native app startup. The ordinary NAPP loader checks this entire
; file and closes its source before entry. All scratch uses owned allocations.
; The original body expands in its declared bank-0 allocation; the outer NAPP
; header remains its identity. Modules bind to that outer header's checksum.
.include "api.inc"
PK_CODE_BASE=$5000
* = N_APPBASE
        .text "napp"
        .byte 1,1,PK_ABI,<PK_WINDOW
        .word pk_file_end-N_APPBASE
        .byte PK_PAGES,>PK_WINDOW
        .word pk_start-N_APPBASE,0
        .binary PK_HEADER_FILE,16,16
pk_metadata:
        .text "npz2"
        .binary PK_HEADER_FILE
        .word PK_RUNTIME_END,PK_CLEANUP_BASE,pk_payload,PK_PACKED_LENGTH
        .word pk_decoder_image,pk_decoder_end-pk_decoder
pk_start:
        lda N_CURRENT
        cmp #N_APPOWNER
        bne pk_wrong_owner
        lda N_APPSTATE
        cmp #2
        bne pk_wrong_owner
        ldx #13
-       lda N_APPHEADER,x
        cmp pk_expected_header,x
        bne pk_bad_header
        dex
        bpl -
        lda NPAGES0+$60
        beq pk_bad_parent
        cmp #NSLOTS+1
        bcs pk_bad_parent
        sta pk_parent_slot
        sec
        sbc #1
        asl
        asl
        asl
        tax
        lda NHANDLES,x
        cmp #N_APPOWNER
        bne pk_bad_parent
        lda NHANDLES+1,x
        bne pk_bad_parent
        lda NHANDLES+2,x
        cmp #$60
        bne pk_bad_parent
        lda NHANDLES+3,x
        cmp #PK_PAGES
        bne pk_bad_parent
        ldx #PK_PAGES-1
-       lda NPAGES0+$60,x
        cmp pk_parent_slot
        bne pk_bad_parent
        dex
        bpl -
        lda #0
        sta N_READY
        sta N_BANK
        lda #N_APPOWNER
        sta N_OWNER
        lda #>PK_CODE_BASE
        sta N_PAGE
        lda #pk_decoder_pages
        sta N_PAGES
        jsr N_RESERVE
        bcs pk_reserve_failed
        ldx #0
        ldy #pk_decoder_pages
pk_copy_code:
        lda pk_decoder_image,x
pk_copy_code_store:
        sta PK_CODE_BASE,x
        inx
        bne pk_copy_code
        inc pk_copy_code+2
        inc pk_copy_code_store+2
        dey
        bne pk_copy_code
        ldx #3
-       lda N_HANDLE,x
        sta pk_code_handle,x
        dex
        bpl -
        jmp pk_decoder
pk_reserve_failed:
        rts
pk_wrong_owner:
        lda #N_WRONGOWNER
        rts
pk_bad_header:
        lda #N_BADIMAGE
        rts
pk_bad_parent:
        lda #N_BADHANDLE
        rts
pk_expected_header:
        .text "napp"
        .byte 1,1,PK_ABI,<PK_WINDOW
        .word pk_file_end-N_APPBASE
        .byte PK_PAGES,>PK_WINDOW
        .word pk_start-N_APPBASE
pk_parent_slot: .byte 0

pk_decoder_image:
.logical PK_CODE_BASE
pk_decoder:
        tsx
        stx pk_stack
        lda #$ff              ; bank 1 first, then another owned bank-0 extent
        sta N_BANK
        lda #(PK_PACKED_LENGTH+255)/256
        sta N_PAGES
        jsr N_ALLOC
        bcs pk_finish
        ldx #3
-       lda N_HANDLE,x
        sta pk_input_handle,x
        dex
        bpl -
pk_stage_block:
        jsr pk_chunk
        lda #<N_BUFFER
        sta pk_stage_store+1
        lda #>N_BUFFER
        sta pk_stage_store+2
        lda N_COUNT
        sta pk_left
        lda N_COUNT+1
        sta pk_left+1
pk_stage_read:
        lda pk_payload
pk_stage_store:
        sta N_BUFFER
        inc pk_stage_read+1
        bne +
        inc pk_stage_read+2
+       inc pk_stage_store+1
        bne +
        inc pk_stage_store+2
+       lda pk_left
        bne +
        dec pk_left+1
+       dec pk_left
        lda pk_left
        ora pk_left+1
        bne pk_stage_read
        jsr pk_select_input
        jsr N_WRITE
        bcs pk_finish
        jsr pk_advance
        lda pk_offset+1
        cmp #>PK_PACKED_LENGTH
        bne pk_stage_block
        lda pk_offset
        cmp #<PK_PACKED_LENGTH
        bne pk_stage_block
        lda #0
        sta pk_offset
        sta pk_offset+1
        jsr DECOMPRESS_LZSA2
        jmp boot_finished

; Input allocations are accessed only through the bounded native transfer API.
pk_chunk:
        sec
        lda #<PK_PACKED_LENGTH
        sbc pk_offset
        sta N_COUNT
        lda #>PK_PACKED_LENGTH
        sbc pk_offset+1
        cmp #2
        bcc +
        lda #0
        sta N_COUNT
        lda #2
+       sta N_COUNT+1
        rts
pk_select_input:
        lda #N_APPOWNER
        sta N_OWNER
        ldx #3
-       lda pk_input_handle,x
        sta N_HANDLE,x
        dex
        bpl -
        lda pk_offset
        sta N_OFFSET
        lda pk_offset+1
        sta N_OFFSET+1
        rts
pk_advance:
        clc
        lda pk_offset
        adc N_COUNT
        sta pk_offset
        lda pk_offset+1
        adc N_COUNT+1
        sta pk_offset+1
        rts

.include "lzsa2-decode.inc"

; The decoder's carry and X/Y counts survive native refill calls.
boot_get:
        php
        txa
        pha
        tya
        pha
        lda pk_consumed+1
        cmp #>PK_PACKED_LENGTH
        bcc +
        bne boot_bad
        lda pk_consumed
        cmp #<PK_PACKED_LENGTH
        bcs boot_bad
+       lda pk_buffered
        ora pk_buffered+1
        bne pk_read_byte
        jsr pk_chunk
        jsr pk_select_input
        jsr N_READ
        bcs pk_finish
        lda N_COUNT
        sta pk_buffered
        lda N_COUNT+1
        sta pk_buffered+1
        jsr pk_advance
        lda #<N_BUFFER
        sta pk_read_byte+1
        lda #>N_BUFFER
        sta pk_read_byte+2
pk_read_byte:
        lda N_BUFFER
        sta pk_value
        inc pk_read_byte+1
        bne +
        inc pk_read_byte+2
+       inc pk_consumed
        bne +
        inc pk_consumed+1
+       lda pk_buffered
        bne +
        dec pk_buffered+1
+       dec pk_buffered
        pla
        tay
        pla
        tax
        plp
        lda pk_value
        rts
boot_put:
        sta pk_value
        php
        tya
        pha
        lda pk_value
        jsr pk_put_body
        pla
        tay
        plp
        rts
pk_put_body:
        pha
        lda boot_write+2
        cmp #>PK_RAW_END
        bcc +
        bne boot_bad
        lda boot_write+1
        cmp #<PK_RAW_END
        bcs boot_bad
+       pla
boot_write:
        sta N_APPBASE+32
        eor pk_crc+1
        sta pk_crc+1
        ldy #8
-       asl pk_crc
        rol pk_crc+1
        bcc +
        lda pk_crc
        eor #$21
        sta pk_crc
        lda pk_crc+1
        eor #$10
        sta pk_crc+1
+       dey
        bne -
        inc boot_write+1
        bne +
        inc boot_write+2
+       rts
boot_match:
        php
        pha
        lda COPY_MATCH_LOOP+2
        cmp #>(N_APPBASE+32)
        bcc boot_bad
        bne +
        lda COPY_MATCH_LOOP+1
        cmp #<(N_APPBASE+32)
        bcc boot_bad
+       lda COPY_MATCH_LOOP+2
        cmp boot_write+2
        bcc +
        bne boot_bad
        lda COPY_MATCH_LOOP+1
        cmp boot_write+1
        bcs boot_bad
+       pla
        plp
        rts
boot_finished:
        lda pk_consumed
        cmp #<PK_PACKED_LENGTH
        bne boot_bad
        lda pk_consumed+1
        cmp #>PK_PACKED_LENGTH
        bne boot_bad
        lda boot_write+1
        cmp #<PK_RAW_END
        bne boot_bad
        lda boot_write+2
        cmp #>PK_RAW_END
        bne boot_bad
        lda pk_crc
        cmp #<PK_BODY_CRC
        bne pk_checksum
        lda pk_crc+1
        cmp #>PK_BODY_CRC
        bne pk_checksum
        lda #0
        beq pk_finish
pk_checksum:
        lda #N_CHECKSUM
        bne pk_finish
boot_bad:
        lda #N_BADIMAGE
pk_finish:
        sta pk_result
        ldx pk_stack
        txs
        ldx #pk_cleanup_end-pk_cleanup-1
-       lda pk_cleanup_image,x
        sta PK_CLEANUP_BASE,x
        dex
        bpl -
        lda pk_result
        sta pk_cleanup_result+1
        ldx #3
-       lda pk_input_handle,x
        sta pk_cleanup_input,x
        lda pk_code_handle,x
        sta N_HANDLE,x
        dex
        bpl -
        lda #N_APPOWNER
        sta N_OWNER
        jmp pk_cleanup
pk_stack: .byte 0
pk_code_handle: .fill 4,0
pk_input_handle: .fill 4,0
pk_offset: .word 0
pk_consumed: .word 0
pk_buffered: .word 0
pk_left: .word 0
pk_value: .byte 0
pk_result: .byte 0
pk_crc: .word $ffff

; This is copied to unused owned app memory before freeing its caller. The
; input token survives code release; failure returns to normal app cleanup.
pk_cleanup_image:
.logical PK_CLEANUP_BASE
pk_cleanup:
        jsr N_FREE
        bcs pk_cleanup_return
        lda pk_cleanup_input
        beq pk_cleanup_result
        ldx #3
-       lda pk_cleanup_input,x
        sta N_HANDLE,x
        dex
        bpl -
        jsr N_FREE
        bcs pk_cleanup_return
pk_cleanup_result:
        lda #0
        bne pk_cleanup_return
        clc
        jmp PK_RAW_ENTRY
pk_cleanup_return:
        rts
pk_cleanup_input: .fill 4,0
pk_cleanup_end:
        .cerror pk_cleanup_end>PK_CLEANUP_BASE+48, "startup cleanup exceeds reserved tail"
.here
pk_decoder_end:
        .fill (-*) & $ff,0
pk_decoder_padded_end:
pk_decoder_pages=(pk_decoder_padded_end-pk_decoder)/256
        .cerror pk_decoder_padded_end>N_APPBASE, "startup decoder exceeds temporary code area"
.here
pk_payload:
        .binary PK_PACKED_FILE
pk_file_end:
        .cerror pk_file_end>PK_CLEANUP_BASE, "packed file overlaps cleanup scratch"
        .cerror PK_RAW_END>PK_CLEANUP_BASE, "decoded body overlaps cleanup scratch"
        .cerror PK_RUNTIME_END>PK_CLEANUP_BASE, "runtime data overlaps cleanup scratch"
