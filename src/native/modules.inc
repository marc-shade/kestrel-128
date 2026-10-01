; Checked foreground modules in the running app's declared bank-0 window.
; The app loader's buffered reader is idle after checked app entry. Only
; its stream/CRC scratch is borrowed here; l_app_handle, l_entry, l_app_sp
; and N_APPHEADER remain the original app's identity and return context.
module_load:
        php
        jsr module_start
        bcs module_early
        lda l_open
        bne module_busy
        lda m_generation
        and m_generation+1
        and m_generation+2
        cmp #$ff
        bne +
        lda #N_MEXHAUSTED
        bne module_early
+       lda N_FNAMELEN
        beq module_argument
        cmp #17
        bcs module_argument
        ldy #0
module_name:
        lda N_FNAME,y
        cmp #32
        bcc module_argument
        cmp #127
        bcs module_argument
        jsr field_filter_iec
        bcs module_argument
        iny
        cpy N_FNAMELEN
        bne module_name
        lda m_source_format
        sta N_FFORMAT
        lda m_source_device
        sta N_FDEVICE
        cmp #3
        bcs module_source_ready
        lda m_source_length
        clc
        adc N_FNAMELEN
        bcs module_argument
        sta m_name_length
        ldx #0
module_source_path:
        lda N_SOURCEPATH,x
        sta N_UPATH,x
        inx
        cpx m_source_length
        bne module_source_path
        ldy #0
module_source_name:
        lda N_FNAME,y
        sta N_UPATH,x
        inx
        iny
        cpy N_FNAMELEN
        bne module_source_name
        lda m_name_length
        sta N_FNAMELEN
module_source_ready:
        jsr module_invalidate
        inc m_generation
        bne +
        inc m_generation+1
        bne +
        inc m_generation+2
+       lda #1
        sta N_MSTATE
        sta N_FTYPE
        lda #0
        sta N_FMODE
        sta l_result
        sta l_available
        sta l_available+1
        sta l_file_eof
        sta l_eof
        sta N_DOSCODE
        sta N_IOSTATUS
        lda #N_APPOWNER
        sta N_FOWNER
        jsr fs_open
        jsr app_record_io
        php
        pha
        ldx #3
module_save_handle:
        lda N_FHANDLE,x
        sta l_handle,x
        dex
        bpl module_save_handle
        lda l_handle
        sta l_open
        pla
        plp
        bcs module_failure
        ldx #0
module_origin:
        stx l_index
        jsr app_byte
        bcs module_failure
        ldx l_index
        cmp m_base,x
        bne module_bad_image
        inx
        cpx #2
        bne module_origin
        ldx #0
module_header:
        stx l_index
        jsr app_byte
        bcs module_failure
        ldx l_index
        sta N_MHEADER,x
        inx
        cpx #16
        bne module_header
        jsr module_validate
        bcs module_failure
        lda m_base
        sta module_store+1
        lda m_base+1
        sta module_store+2
        lda #$ff
        sta l_crc
        sta l_crc+1
        ldx #0
module_copy_header:
        stx l_index
        lda N_MHEADER,x
        cpx #14
        bcc +
        lda #0
+       jsr app_crc_byte
        ldx l_index
        lda N_MHEADER,x
        jsr module_put
        ldx l_index
        inx
        cpx #16
        bne module_copy_header
        lda N_MHEADER+8
        sec
        sbc #16
        sta l_left
        lda N_MHEADER+9
        sbc #0
        sta l_left+1
module_copy:
        jsr app_byte
        bcs module_failure
        pha
        jsr app_crc_byte
        pla
        jsr module_put
        lda l_left
        bne +
        dec l_left+1
+       dec l_left
        lda l_left
        ora l_left+1
        bne module_copy
        lda l_eof
        bne module_eof
        lda #N_LONGIMAGE
        bne module_failure
module_eof:
        lda l_crc
        cmp N_MHEADER+14
        bne module_bad_crc
        lda l_crc+1
        cmp N_MHEADER+15
        bne module_bad_crc
        jsr app_close
        lda l_result
        bne module_finish
        lda #2
        sta N_MSTATE
        ldx #2
module_publish:
        lda m_generation,x
        sta N_MTOKEN,x
        dex
        bpl module_publish
        lda #0
        beq module_early
module_bad_crc:
        lda #N_CHECKSUM
        bne module_failure
module_bad_image:
        lda #N_BADIMAGE
module_failure:
        sta l_result
        jsr app_close
module_finish:
        lda #0
        sta N_MSTATE
        lda l_open
        beq +
        lda #4
        sta N_MSTATE
+       lda l_result
        ldx #0
        stx l_result           ; a module failure is not an app launch failure
module_early:
        sta N_MERROR
        plp
        cmp #1
        rts
module_busy:
        lda #N_REENTRANT
        bne module_early
module_argument:
        lda #N_BADARG
        bne module_early
module_put:
module_store:
        sta $ffff
        inc module_store+1
        bne +
        inc module_store+2
+       rts

module_close:
        php
        jsr module_start
        bcs module_early
        jsr module_invalidate
        lda #0
        sta l_result
        jsr app_close
        jmp module_finish

module_invalidate:
        lda #0
        sta N_MSTATE
        sta N_MTOKEN
        sta N_MTOKEN+1
        sta N_MTOKEN+2
        rts
