; UPNT v1 streams. Save creates exclusively, closes, reopens and compares all
; bytes. Load validates a separate allocation before replacing the document.
; UI supplies pf_device/format/type/name/length; no live streams at entry.
PF_ERR_CANCEL=$80
PF_ERR_FORMAT=$81
PF_ERR_CHECKSUM=$82
PF_ERR_MISMATCH=$83
pf_save:
        jsr pf_begin
        bcs pf_return
        lda #<pf_crc_document
        ldx #>pf_crc_document
        jsr pf_regions
        bcs pf_failed
        lda pf_crc
        sta pf_header+12
        lda pf_crc+1
        sta pf_header+13
        lda #1
        jsr pf_open
        bcs pf_failed
        ldx #15
-       lda pf_header,x
        sta N_BUFFER,x
        dex
        bpl -
        lda #16
        sta N_FCOUNT
        lda #0
        sta N_FCOUNT+1
        jsr N_FWRITE
        bcs pf_failed
        lda #<pf_write_body
        ldx #>pf_write_body
        jsr pf_regions
        bcs pf_failed
        jsr pf_close
        bcs pf_failed
        lda #0
        jsr pf_open
        bcs pf_failed
        jsr pf_read_header
        bcs pf_failed
        ldx #15
-       lda N_BUFFER,x
        cmp pf_header,x
        bne pf_mismatch
        dex
        bpl -
        lda #<pf_verify_body
        ldx #>pf_verify_body
        jsr pf_regions
        bcs pf_failed
        jsr pf_eof
        bcs pf_failed
        jsr pf_close
        bcs pf_failed
        lda #0
        sta pd_dirty
        sta pd_stroke
        lda #1
        sta pd_undo_dirty       ; undo differs from this newly saved version
        lda #0
        clc
pf_return:
        rts
pf_mismatch:
        lda #PF_ERR_MISMATCH
        bne pf_failed

pf_load:
        jsr pf_begin
        bcs pf_return
        lda #36
        sta N_PAGES
        lda #1
        sta N_BANK
        lda N_CURRENT
        sta N_OWNER
        jsr N_ALLOC
        bcs pf_failed
        ldx #3
-       lda N_HANDLE,x
        sta pd_handles+8,x
        dex
        bpl -
        ; Initialize non-file padding in the staging image as well.
        lda #0
        sta pf_page
pf_stage_blank:
        ldx #8
        jsr pd_select
        lda #0
        sta N_OFFSET
        sta N_COUNT
        sta N_VALUE
        lda pf_page
        sta N_OFFSET+1
        cmp #32
        bcc +
        lda #$10
        sta N_VALUE
+       lda #2
        sta N_COUNT+1
        jsr N_FILL
        bcs pf_failed
        inc pf_page
        inc pf_page
        lda pf_page
        cmp #36
        bne pf_stage_blank
        lda #0
        jsr pf_open
        bcs pf_failed
        jsr pf_read_header
        bcs pf_failed
        ldx #11
-       lda N_BUFFER,x
        cmp pf_header,x
        bne pf_bad_format
        dex
        bpl -
        lda N_BUFFER+14
        ora N_BUFFER+15
        bne pf_bad_format
        lda N_BUFFER+12
        sta pf_wanted_crc
        lda N_BUFFER+13
        sta pf_wanted_crc+1
        lda #<pf_load_body
        ldx #>pf_load_body
        jsr pf_regions
        bcs pf_failed
        jsr pf_eof
        bcs pf_failed
        lda pf_crc
        cmp pf_wanted_crc
        bne pf_bad_checksum
        lda pf_crc+1
        cmp pf_wanted_crc+1
        bne pf_bad_checksum
        jsr pf_close
        bcs pf_failed
        ; The former document becomes undo only after all input/close checks.
        ldx #4
        jsr pd_select
        jsr N_FREE
        bcs pf_failed
        ldx #3
-       lda pd_handles,x
        sta pd_handles+4,x
        lda pd_handles+8,x
        sta pd_handles,x
        lda #0
        sta pd_handles+8,x
        dex
        bpl -
        lda pd_dirty
        sta pd_undo_dirty
        lda #1
        sta pd_undo_valid
        lda #0
        sta pd_dirty
        sta pd_stroke
        clc
        rts
pf_bad_format:
        lda #PF_ERR_FORMAT
        bne pf_failed
pf_bad_checksum:
        lda #PF_ERR_CHECKSUM
pf_failed:
        sta pf_error
        lda N_FDOS
        sta pf_dos
        lda N_FSTATUS
        sta pf_transport
        jsr pf_cleanup
        lda pf_error
        sec
        rts

pf_begin:
        lda #0
        sta N_READY
        sta pf_error
        sta pf_dos
        sta pf_transport
        sta pd_stroke
        jsr pf_cleanup
        bcs pf_failed
        lda #$ff
        sta pf_crc
        sta pf_crc+1
        lda #0
        clc
        rts
pf_cleanup:
        jsr pf_close
        bcs pf_cleanup_done
        lda pd_handles+8
        beq pf_cleanup_ok
        ldx #8
        jsr pd_select
        jsr N_FREE
        bcs pf_cleanup_done
        lda #0
        sta pd_handles+8
pf_cleanup_ok:
        lda #0
        sta pf_close_error
        clc
        rts
pf_cleanup_done:
        sta pf_close_error
        rts
pf_open:
        sta N_FMODE
        lda N_CURRENT
        sta N_FOWNER
        lda pf_device
        sta N_FDEVICE
        lda pf_format
        sta N_FFORMAT
        lda pf_type
        sta N_FTYPE
        lda pf_length
        sta N_FNAMELEN
        lda #0
        sta N_FHANDLE
        ldx #0
-       lda pf_name,x
        sta N_UPATH,x
        cpx #16
        bcs +
        sta N_FNAME,x
+       inx
        cpx pf_length
        bne -
        jsr N_FOPEN
        php
        pha
        ldx #3
-       lda N_FHANDLE,x
        sta pf_handle,x
        dex
        bpl -
        pla
        plp
        rts
pf_close:
        lda pf_handle
        beq pf_cleanup_ok
        ldx #3
-       lda pf_handle,x
        sta N_FHANDLE,x
        dex
        bpl -
        lda N_CURRENT
        sta N_FOWNER
        jsr N_FCLOSE
        bcs pf_cleanup_done
        lda #0
        ldx #3
-       sta pf_handle,x
        dex
        bpl -
        clc
        rts

; Execute a chunk callback A:X over the two packed file regions. Memory has
; a 192-byte bitmap gap, which is never included in the CRC or file stream.
pf_regions:
        sta pf_process+1
        stx pf_process+2
        lda #0
        sta pf_region
        sta pf_offset
        sta pf_offset+1
        lda #$40
        sta pf_left
        lda #$1f
        sta pf_left+1
pf_chunk:
        lda #0
        sta pf_count
        lda #2
        sta pf_count+1
        lda pf_left+1
        cmp #2
        bcs pf_process
        sta pf_count+1
        lda pf_left
        sta pf_count
pf_process:
        jsr $ffff
        bcs pf_return
        jsr N_KEYIN
        cmp #27
        beq pf_cancelled
        clc
        lda pf_offset
        adc pf_count
        sta pf_offset
        lda pf_offset+1
        adc pf_count+1
        sta pf_offset+1
        sec
        lda pf_left
        sbc pf_count
        sta pf_left
        lda pf_left+1
        sbc pf_count+1
        sta pf_left+1
        ora pf_left
        bne pf_chunk
        lda pf_region
        bne pf_cleanup_ok
        inc pf_region
        lda #0
        sta pf_offset
        lda #$20
        sta pf_offset+1
        lda #$e8
        sta pf_left
        lda #3
        sta pf_left+1
        jmp pf_chunk
pf_cancelled:
        lda #PF_ERR_CANCEL
        sec
        rts
pf_memory_args:
        jsr pd_select
        lda pf_offset
        sta N_OFFSET
        lda pf_offset+1
        sta N_OFFSET+1
        lda pf_count
        sta N_COUNT
        lda pf_count+1
        sta N_COUNT+1
        rts
pf_file_args:
        lda pf_count
        sta N_FCOUNT
        lda pf_count+1
        sta N_FCOUNT+1
        rts
pf_read_exact:
        jsr pf_file_args
        jsr N_FREAD
        bcs pf_return
        lda N_FACTUAL
        cmp pf_count
        bne pf_short
        lda N_FACTUAL+1
        cmp pf_count+1
        bne pf_short
        lda #0
        clc
        rts
pf_short:
        lda #PF_ERR_FORMAT
        sec
        rts
pf_read_header:
        lda #16
        sta pf_count
        lda #0
        sta pf_count+1
        jmp pf_read_exact
pf_eof:
        lda #1
        sta N_FCOUNT
        lda #0
        sta N_FCOUNT+1
        jsr N_FREAD
        bcs pf_return
        lda N_FACTUAL
        ora N_FACTUAL+1
        bne pf_short
        lda N_FEOF
        cmp #1
        bne pf_short
        lda #0
        clc
        rts
pf_crc_document:
        ldx #0
        jsr pf_memory_args
        jsr N_READ
        bcs pf_return
        jmp pf_crc_buffer
pf_write_body:
        ldx #0
        jsr pf_memory_args
        jsr N_READ
        bcs pf_return
        jsr pf_file_args
        jmp N_FWRITE
pf_load_body:
        jsr pf_read_exact
        bcs pf_return
        jsr pf_crc_buffer
        ldx #8
        jsr pf_memory_args
        jmp N_WRITE
pf_verify_body:
        jsr pf_read_exact
        bcs pf_return
        ldx #0
-       lda N_BUFFER,x
        sta pf_compare,x
        lda N_BUFFER+256,x
        sta pf_compare+256,x
        inx
        bne -
        ldx #0
        jsr pf_memory_args
        jsr N_READ
        bcs pf_return
        lda pf_count
        sta pf_check_left
        lda pf_count+1
        sta pf_check_left+1
        lda #<N_BUFFER
        sta pf_check_read+1
        lda #>N_BUFFER
        sta pf_check_read+2
        lda #<pf_compare
        sta pf_check_against+1
        lda #>pf_compare
        sta pf_check_against+2
pf_check_read:
        lda $ffff
pf_check_against:
        cmp $ffff
        bne pf_compare_failed
        inc pf_check_read+1
        bne +
        inc pf_check_read+2
+       inc pf_check_against+1
        bne +
        inc pf_check_against+2
+       lda pf_check_left
        bne +
        dec pf_check_left+1
+       dec pf_check_left
        lda pf_check_left
        ora pf_check_left+1
        bne pf_check_read
        lda #0
        clc
        rts
pf_compare_failed:
        lda #PF_ERR_MISMATCH
        sec
        rts
pf_crc_buffer:
        lda #<N_BUFFER
        sta pf_crc_read+1
        lda #>N_BUFFER
        sta pf_crc_read+2
        lda pf_count
        sta pf_crc_left
        lda pf_count+1
        sta pf_crc_left+1
pf_crc_read:
        lda $ffff
        eor pf_crc+1
        sta pf_crc+1
        ldx #8
-       asl pf_crc
        rol pf_crc+1
        bcc +
        lda pf_crc
        eor #$21
        sta pf_crc
        lda pf_crc+1
        eor #$10
        sta pf_crc+1
+       dex
        bne -
        inc pf_crc_read+1
        bne +
        inc pf_crc_read+2
+       lda pf_crc_left
        bne +
        dec pf_crc_left+1
+       dec pf_crc_left
        lda pf_crc_left
        ora pf_crc_left+1
        bne pf_crc_read
        lda #0
        clc
        rts

pf_header: .byte $55,$50,$4e,$54,1,0,$40,1,200,0,$28,$23,0,0,0,0
pf_device: .byte 8
pf_format: .byte 0
pf_type: .byte 0
pf_length: .byte 0
pf_name: .fill 256,0
pf_handle: .fill 4,0
pf_error: .byte 0
pf_close_error: .byte 0
pf_dos: .byte 0
pf_transport: .byte 0
pf_page: .byte 0
pf_region: .byte 0
pf_left: .word 0
pf_offset: .word 0
pf_count: .word 0
pf_crc: .word 0
pf_wanted_crc: .word 0
pf_crc_left: .word 0
pf_check_left: .word 0
pf_compare=$5400
