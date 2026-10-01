; Native foreground application lifecycle, GPL v3.
; Checked bank-0 application loading through the shared owned file service.
; IEC and Ultimate use the same manifest, extent, CRC and cleanup rules.

app_launch:
        php
        lda N_APPSTATE
        ora N_CURRENT
        ora N_BUSY
        ora N_FBUSY
        beq app_available
app_nested:
        lda #N_REENTRANT
        plp
        sec
        rts
app_available:
        tsx
        lda $0101,x
        and #4
        beq app_interrupts
        lda #N_PLATFORM
        jmp app_before
app_interrupts:
        cld
        jsr heap_stats
        bcc *+5
        jmp app_before
        lda NFILES
        cmp #N_APPOWNER
        beq app_nested
        lda NFILES+16
        cmp #N_APPOWNER
        beq app_nested
        ldx #0
app_owner_scan:
        lda NHANDLES,x
        cmp #N_APPOWNER
        beq app_nested
        txa
        clc
        adc #8
        tax
        bne app_owner_scan
        lda N_APPFORMAT
        cmp #4
        bcs app_argument
        cmp #3
        beq app_ultimate_source
        lda N_DEVICE
        cmp #8
        bcc app_argument
        cmp #31
        bcs app_argument
        lda N_NAMELEN
        beq app_argument
        cmp #17
        bcs app_argument
        jmp app_channels
app_ultimate_source:
        lda N_DEVICE
        beq app_argument
        cmp #3
        bcs app_argument
        lda N_NAMELEN
        beq app_argument
        lda N_UPATH
        cmp #$2f
        bne app_argument
        jmp app_channels
app_argument:
        lda #N_BADARG
app_before:
        sta N_APPERROR
        plp
        cmp #1
        rts
app_channels:
        lda $99
        bne app_channel_busy
        lda $9a
        cmp #3
        beq app_begin
app_channel_busy:
        lda #N_CHANNELS
        jmp app_before
app_begin:
        ; A staged request crosses exactly one launch attempt. An unclaimed
        ; ready request expires before another executable can receive it.
        lda N_DOCREQUEST
        asl
        lda #0
        rol
        sta N_DOCREQUEST
        lda #1
        sta N_APPSTATE
        lda #N_APPOWNER
        sta N_CURRENT
        sta N_FOWNER
        lda #0
        sta N_READY
        ldx #4
-       sta N_EXITCODE,x        ; exit, DOS, transport, app error and action
        dex
        bpl -
        ldx #6
-       sta l_available,x       ; count, EOF, open, result, index and final EOF
        dex
        bpl -
        sta N_FMODE
        ldx #3
app_clear_file_handle:
        sta N_FHANDLE,x
        dex
        bpl app_clear_file_handle
        jsr module_source
        lda #1                 ; raw PRG bytes include their load address
        sta N_FTYPE
        lda N_DEVICE
        sta N_FDEVICE
        lda N_APPFORMAT
        sta N_FFORMAT
        lda N_NAMELEN
        sta N_FNAMELEN
        ldx #15
app_copy_name:
        lda N_APPNAME,x
        sta N_FNAME,x
        dex
        bpl app_copy_name
        jsr fs_open
        jsr app_record_io
        php
        pha
        ldx #3
app_keep_file_handle:
        lda N_FHANDLE,x
        sta l_handle,x
        dex
        bpl app_keep_file_handle
        lda N_FHANDLE
        sta l_open
        pla
        plp
        bcc *+5
        jmp app_failure
        jsr app_byte
        bcc *+5
        jmp app_failure
        cmp #<N_APPBASE
        beq *+5
        jmp app_bad_image
        jsr app_byte
        bcc *+5
        jmp app_failure
        cmp #>N_APPBASE
        beq *+5
        jmp app_bad_image
        lda #0
        sta l_index
app_read_header:
        jsr app_byte
        bcc *+5
        jmp app_failure
        ldx l_index
        sta N_APPHEADER,x
        inc l_index
        lda l_index
        cmp #32
        bne app_read_header
        jsr app_validate
        bcc *+5
        jmp app_failure
        lda #N_APPOWNER
        sta N_OWNER
        lda N_APPHEADER+10
        sta N_PAGES
        lda #0
        sta N_BANK
        lda #>N_APPBASE
        sta N_PAGE
        jsr heap_reserve
        bcc *+5
        jmp app_failure
        ; Keep the app allocation identity independently of the source file.
        ; File and heap handle generations diverge across repeated launches.
        ldx #3
app_keep_allocation:
        lda N_HANDLE,x
        sta l_app_handle,x
        dex
        bpl app_keep_allocation
        ; Initialize the full declared allocation, including uninitialized
        ; data beyond the file. The validated range is below system ROM.
        lda N_APPHEADER+10
        sta l_zero_pages
        lda #>N_APPBASE
        sta app_zero+2
        lda #0
        ldx #0
app_zero:
        sta N_APPBASE,x
        inx
        bne app_zero
        inc app_zero+2
        dec l_zero_pages
        bne app_zero
        lda #$ff
        sta l_crc
        sta l_crc+1
        lda #0
        sta l_index
app_header_copy:
        ldx l_index
        lda N_APPHEADER,x
        sta N_APPBASE,x
        cpx #14
        beq app_crc_zero
        cpx #15
        bne app_header_crc
app_crc_zero:
        lda #0
app_header_crc:
        jsr app_crc_byte
        inc l_index
        lda l_index
        cmp #32
        bne app_header_copy
        lda #<(N_APPBASE+32)
        sta app_image_store+1
        lda #>(N_APPBASE+32)
        sta app_image_store+2
        sec
        lda N_APPHEADER+8
        sbc #32
        sta l_left
        lda N_APPHEADER+9
        sbc #0
        sta l_left+1
app_image_loop:
        jsr app_byte
        bcc *+5
        jmp app_failure
app_image_store:
        sta N_APPBASE+32
        jsr app_crc_byte
        inc app_image_store+1
        bne app_image_next
        inc app_image_store+2
app_image_next:
        lda l_left
        bne app_image_low
        dec l_left+1
app_image_low:
        dec l_left
        lda l_left
        ora l_left+1
        bne app_image_loop
        lda l_eof
        bne app_image_eof
        lda #N_LONGIMAGE
        bne app_failure
app_image_eof:
        lda l_crc
        cmp N_APPHEADER+14
        bne app_bad_crc
        lda l_crc+1
        cmp N_APPHEADER+15
        bne app_bad_crc
        jsr app_close
        lda l_result
        bne app_cleanup
        lda #2
        sta N_APPSTATE
        lda #N_APPOWNER
        sta N_OWNER
        tsx
        stx l_app_sp
        lda #0
        jsr app_jump
app_return:
        sta N_EXITCODE
        jsr module_invalidate
        cld
        lda #$0e
        sta $ff00
        cli
        lda #0
        sta N_READY
        jmp app_cleanup
app_jump:
        jmp (l_entry)
app_exit:
        ldx N_APPSTATE
        cpx #2
        beq app_exit_active
app_exit_invalid:
        lda #N_BADARG
        sec
        rts
app_replace:
        lda #1
        bne app_request
app_workspace:
        lda #2
app_request:
        ldx N_APPSTATE
        cpx #2
        bne app_exit_invalid
        sta N_ACTION
        lda #0
app_exit_active:
        ldx l_app_sp
        txs
        jmp app_return
app_bad_crc:
        lda #N_CHECKSUM
        bne app_failure
app_bad_image:
        lda #N_BADIMAGE
        bne app_failure
app_failure:
        sta l_result
        jsr app_close
app_cleanup:
        jsr display_restore   ; includes retained file/heap cleanup errors
        lda #3
        sta N_APPSTATE
        lda NFILES
        cmp #N_APPOWNER
        beq app_close_files
        lda NFILES+16
        cmp #N_APPOWNER
        bne app_release_memory
app_close_files:
        lda #N_APPOWNER
        sta N_FOWNER
        jsr fs_release
        bcs app_retain_resources
app_release_memory:
        lda #N_APPOWNER
        sta N_OWNER
        jsr heap_release
        bcc app_released
app_retain_resources:
        ldx l_result
        bne +
        sta l_result
+
        lda #4                 ; corrupt ownership stays reserved, not reused
        sta N_APPSTATE
        bne app_finish
app_released:
        lda #0
        sta N_CURRENT
        sta N_APPSTATE
app_finish:
        lda l_result
        sta N_APPERROR
        plp
        cmp #1
        rts

app_validate:
        ldx #3
app_magic_loop:
        lda N_APPHEADER,x
        cmp l_magic,x
        beq *+5
        jmp app_invalid
        dex
        bpl app_magic_loop
        lda N_APPHEADER+4
        cmp #1
        bne app_invalid
        lda N_APPHEADER+5
        cmp #1
        bne app_invalid
        lda N_APPHEADER+6
        cmp #N_ABI_MINOR+1
        bcs app_invalid
        jsr module_window
        bcs app_invalid
        lda N_APPHEADER+10
        beq app_invalid
        cmp #((N_APPLIMIT-N_APPBASE)/256)+1
        bcs app_invalid
        lda N_APPHEADER+9
        cmp N_APPHEADER+10
        bcc app_size_fits
        bne app_invalid
        lda N_APPHEADER+8
        bne app_invalid
app_size_fits:
        lda N_APPHEADER+9
        bne app_image_large
        lda N_APPHEADER+8
        cmp #33
        bcc app_invalid
app_image_large:
        lda N_APPHEADER+13
        bne app_entry_large
        lda N_APPHEADER+12
        cmp #32
        bcc app_invalid
app_entry_large:
        lda N_APPHEADER+13
        cmp N_APPHEADER+9
        bcc app_entry_fits
        bne app_invalid
        lda N_APPHEADER+12
        cmp N_APPHEADER+8
        bcs app_invalid
app_entry_fits:
        lda N_APPHEADER+12
        sta l_entry
        clc
        lda N_APPHEADER+13
        adc #>N_APPBASE
        sta l_entry+1
        ldx #16
app_title_loop:
        lda N_APPHEADER,x
        beq app_title_next
        cmp #$20
        bcc app_invalid
        cmp #$7f
        bcs app_invalid
app_title_next:
        inx
        cpx #32
        bne app_title_loop
        clc
        rts
app_invalid:
        lda #N_BADIMAGE
        sec
        rts

; Buffer complete owned reads, then deliver exactly one byte to the checked
; loader. EOF belongs to the final delivered byte, not the beginning of its
; buffer. The file service checks IEC extents and Ultimate FILE_INFO sizes.
app_byte:
        lda l_eof
        bne app_short_image
        lda l_available
        ora l_available+1
        bne app_buffer_read
        jsr app_select_file
        lda #0
        sta N_FCOUNT
        lda #2
        sta N_FCOUNT+1
        jsr fs_read
        jsr app_record_io
        bcs app_byte_done
        lda N_FACTUAL
        sta l_available
        lda N_FACTUAL+1
        sta l_available+1
        ora l_available
        beq app_short_image
        lda N_FEOF
        sta l_file_eof
        lda #<N_BUFFER
        sta app_buffer_read+1
        lda #>N_BUFFER
        sta app_buffer_read+2
app_buffer_read:
        lda N_BUFFER
        pha
        inc app_buffer_read+1
        bne +
        inc app_buffer_read+2
+       lda l_available
        bne +
        dec l_available+1
+       dec l_available
        lda l_available
        ora l_available+1
        bne +
        lda l_file_eof
        sta l_eof
+       pla
        clc
app_byte_done:
        rts
app_short_image:
        lda #N_SHORTIMAGE
        sec
        rts

app_select_file:
        lda #N_APPOWNER
        sta N_FOWNER
        ldx #3
app_select_handle:
        lda l_handle,x
        sta N_FHANDLE,x
        dex
        bpl app_select_handle
        rts
; Preserve the first failing file call's diagnostics across owned cleanup.
; Empty successful Ultimate READ status is not a launch error.
app_record_io:
        php
        pha
        bcc app_record_done
        lda N_DOSCODE
        bne +
        lda N_FDOS
        sta N_DOSCODE
+       lda N_IOSTATUS
        bne app_record_done
        lda N_FSTATUS
        sta N_IOSTATUS
app_record_done:
        pla
        plp
        rts

; CRC16-CCITT, initial $ffff, polynomial $1021; header bytes 14/15 are zero.
app_crc_byte:
        eor l_crc+1
        sta l_crc+1
        ldx #8
app_crc_bit:
        asl l_crc
        rol l_crc+1
        bcc app_crc_next
        lda l_crc
        eor #$21
        sta l_crc
        lda l_crc+1
        eor #$10
        sta l_crc+1
app_crc_next:
        dex
        bne app_crc_bit
        rts

app_close:
        lda l_open
        beq app_close_done
        jsr app_select_file
        jsr fs_close
        jsr app_record_io
        bcs app_close_failed
        lda #0
        sta l_open
app_close_done:
        rts
app_close_failed:
        ldx l_result
        bne app_close_done
        sta l_result
        rts

l_magic: .text "napp"
l_handle: .fill 4,0
l_app_handle: .fill 4,0
l_available: .word 0
l_file_eof: .byte 0
l_open: .byte 0
l_result: .byte 0
l_index: .byte 0
l_eof: .byte 0
l_zero_pages: .byte 0
l_app_sp: .byte 0
l_crc: .word 0
l_left: .word 0
        .align 2
l_entry: .word 0
