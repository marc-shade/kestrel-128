; Checked NBK1 PRG loader. Caller opens a native read stream as owner 32,
; then transfers its N_FHANDLE to bk_load. Success closes the source before
; enabling execution. Any failure after acquisition retains state 1 until
; bk_close releases both stream and image; there is no implicit retry.
bk_load:
        php
        pha
        jsr bk_enter
        bcs bk_enter_failed
        pla
        lda bk_state
        bne bk_load_badarg
        lda N_FOWNER
        cmp #N_APPOWNER
        bne bk_load_badarg
        lda N_FHANDLE
        beq bk_load_badarg
        cmp #3
        bcs bk_load_badarg
        sec
        sbc #1
        asl
        asl
        asl
        asl
        tax
        lda NFILES,x
        cmp #N_APPOWNER
        bne bk_load_badarg
        lda NFILES+2,x
        bne bk_load_badarg
        ldy #1
-       lda NFILES+4,x
        cmp N_FHANDLE,y
        bne bk_load_badarg
        inx
        iny
        cpy #4
        bne -
        jsr bk_check_tails
        bcs bk_finish
        ldx #3
-       lda N_FHANDLE,x
        sta bk_file,x
        dex
        bpl -
        lda #1
        sta bk_state
        lda #34
        sta bk_count
        lda #0
        sta bk_count+1
        jsr bk_read_chunk
        bcs bk_finish
        ldx #7
-       lda N_BUFFER,x
        cmp bk_prefix,x
        bne bk_bad_image
        dex
        bpl -
        lda N_BUFFER+8       ; required native ABI minor
        cmp #N_ABI_MINOR+1
        bcs bk_bad_image
        lda N_BUFFER+9       ; flags
        bne bk_bad_image
        lda N_BUFFER+13
        cmp #1               ; bank 1
        bne bk_bad_image
        ldx #9               ; exit stub, reserved byte and zero callback import
-       lda N_BUFFER+18,x
        cmp bk_stub,x
        bne bk_bad_image
        dex
        bpl -
        ldx #5
-       lda N_BUFFER+28,x
        bne bk_bad_image
        dex
        bpl -
        lda N_BUFFER+10
        sta bk_length
        lda N_BUFFER+11
        sta bk_length+1
        bne +
        lda bk_length
        cmp #33
        bcc bk_bad_image
+       lda bk_length
        cmp #1               ; ceil(length / 256), with checked upper bound
        lda bk_length+1
        adc #0
        beq bk_bad_image
        cmp #(BK_LIMIT-BK_BASE)/256+1
        bcs bk_bad_image
        cmp N_BUFFER+12
        bne bk_bad_image
        sta bk_pages
        lda N_BUFFER+15
        bne +
        lda N_BUFFER+14
        cmp #32
        bcc bk_bad_image
+       lda N_BUFFER+14
        cmp bk_length
        lda N_BUFFER+15
        sbc bk_length+1
        bcs bk_bad_image
        lda N_BUFFER+14
        sta bk_entry
        lda N_BUFFER+15
        clc
        adc #>BK_BASE
        sta bk_entry+1
        lda N_BUFFER+16
        sta bk_expected
        lda N_BUFFER+17
        sta bk_expected+1
        lda #BK_OWNER
        sta N_OWNER
        lda #1
        sta N_BANK
        lda #>BK_BASE
        sta N_PAGE
        lda bk_pages
        sta N_PAGES
        jsr N_RESERVE
        bcs bk_finish
        ldx #3
-       lda N_HANDLE,x
        sta bk_handle,x
        dex
        bpl -
        ldx #0
-       lda N_BUFFER+2,x
        sta N_BUFFER,x
        inx
        cpx #32
        bne -
        lda #0
        sta bk_offset
        sta bk_offset+1
        sta N_BUFFER+14
        sta N_BUFFER+15
        lda #$ff
        sta bk_crc
        sta bk_crc+1
        lda #32
        sta bk_count
        jsr bk_crc_buffer
        lda bk_expected
        sta N_BUFFER+14
        lda bk_expected+1
        sta N_BUFFER+15
        jsr bk_write_chunk
        bcs bk_finish
bk_load_more:
        sec
        lda bk_length
        sbc bk_offset
        sta bk_count
        lda bk_length+1
        sbc bk_offset+1
        sta bk_count+1
        ora bk_count
        beq bk_load_eof
        lda bk_count+1
        cmp #2
        bcc +
        lda #2
        sta bk_count+1
        lda #0
        sta bk_count
+       jsr bk_read_chunk
        bcs bk_finish
        jsr bk_crc_buffer
        jsr bk_write_chunk
        bcs bk_finish
        jmp bk_load_more
bk_load_eof:
        jsr bk_select_file
        lda #1
        sta N_FCOUNT
        lda #0
        sta N_FCOUNT+1
        jsr N_FREAD
        bcs bk_finish
        lda N_FACTUAL
        ora N_FACTUAL+1
        bne bk_long_image
        lda N_FEOF
        beq bk_short_image
        lda bk_crc
        cmp bk_expected
        bne bk_checksum
        lda bk_crc+1
        cmp bk_expected+1
        bne bk_checksum
        jsr bk_close_source
        bcs bk_finish
        lda #<bk_callback
        sta N_BUFFER
        lda #>bk_callback
        sta N_BUFFER+1
        lda #22
        sta bk_offset
        lda #0
        sta bk_offset+1
        lda #2
        sta bk_count
        lda #0
        sta bk_count+1
        jsr bk_write_chunk
        bcc bk_load_success
        ldx #1
        stx bk_state
        jmp bk_finish
bk_load_success:
        lda #2
        sta bk_state
        lda #0
        jmp bk_finish
bk_bad_image:
        lda #N_BADIMAGE
        jmp bk_finish
bk_long_image:
        lda #N_LONGIMAGE
        jmp bk_finish
bk_short_image:
        lda #N_SHORTIMAGE
        jmp bk_finish
bk_checksum:
        lda #N_CHECKSUM
        jmp bk_finish
bk_load_badarg:
        lda #N_BADARG
        jmp bk_finish

bk_close:
        php
        pha
        jsr bk_enter
        bcs bk_enter_failed
        pla
        lda bk_state
        beq +
        lda #1
        sta bk_state
+
        jsr bk_close_source
        bcs bk_finish
        lda bk_handle
        beq bk_close_done
        jsr bk_select_code
        jsr N_FREE
        bcs bk_finish
        lda #0
        sta bk_handle
bk_close_done:
        lda #0
        sta bk_state
        jmp bk_finish
bk_close_source:
        lda bk_file
        beq +
        jsr bk_select_file
        jsr N_FCLOSE
        bcs bk_io_return
        lda #0
        sta bk_file
+       clc
        rts
bk_select_file:
        lda #N_APPOWNER
        sta N_FOWNER
        ldx #3
-       lda bk_file,x
        sta N_FHANDLE,x
        dex
        bpl -
        rts
bk_read_chunk:
        jsr bk_select_file
        lda bk_count
        sta N_FCOUNT
        lda bk_count+1
        sta N_FCOUNT+1
        jsr N_FREAD
        bcs bk_io_return
        lda N_FACTUAL
        cmp bk_count
        bne +
        lda N_FACTUAL+1
        cmp bk_count+1
        bne +
        lda #0
        clc
bk_io_return:
        rts
+       lda #N_SHORTIMAGE
        sec
        rts
bk_select_code:
        lda #BK_OWNER
        sta N_OWNER
        ldx #3
-       lda bk_handle,x
        sta N_HANDLE,x
        dex
        bpl -
        rts
bk_write_chunk:
        jsr bk_select_code
        lda bk_offset
        sta N_OFFSET
        lda bk_offset+1
        sta N_OFFSET+1
        lda bk_count
        sta N_COUNT
        lda bk_count+1
        sta N_COUNT+1
        jsr N_WRITE
        bcs bk_io_return
        clc
        lda bk_offset
        adc bk_count
        sta bk_offset
        lda bk_offset+1
        adc bk_count+1
        sta bk_offset+1
        clc
        rts

.if BK_OWNER != N_APPOWNER
; Persistent instance: adopt the image an earlier app loaded and left owned by
; BK_OWNER instead of loading it again. The header must satisfy the same rules
; bk_load enforces, plus the includer's bk_identity at image offset 32. The
; image cannot be CRC-checked here: its callback import is live code state.
; Carry clear: attached (state 2). Carry set: A=N_BADHANDLE when no image is
; resident (load one), N_BADIMAGE on a mismatch; state stays 0.
bk_attach:
        php
        pha
        jsr bk_enter
        bcs bk_attach_gate
        pla
        lda bk_state
        bne bk_load_badarg
        ldx #0
bk_attach_scan:
        lda NHANDLES,x
        cmp #BK_OWNER
        bne bk_attach_next
        lda NHANDLES+1,x
        cmp #1
        bne bk_attach_next
        lda NHANDLES+2,x
        cmp #>BK_BASE
        beq bk_attach_found
bk_attach_next:
        txa
        clc
        adc #8
        tax
        bne bk_attach_scan
        lda #N_BADHANDLE
        jmp bk_finish
bk_attach_gate:
        jmp bk_enter_failed
bk_attach_found:
        lda NHANDLES+3,x
        sta bk_pages
        lda NHANDLES+4,x
        sta bk_handle+1
        lda NHANDLES+5,x
        sta bk_handle+2
        lda NHANDLES+6,x
        sta bk_handle+3
        txa
        lsr
        lsr
        lsr
        clc
        adc #1
        sta bk_handle
        jsr bk_select_code
        lda #0
        sta N_OFFSET
        sta N_OFFSET+1
        sta N_COUNT+1
        lda #40
        sta N_COUNT
        jsr N_READ
        bcs bk_attach_fail
        ldx #5
-       lda N_BUFFER,x          ; NBK1, format and ABI major
        cmp bk_prefix+2,x
        bne bk_attach_bad
        lda N_BUFFER+16,x       ; exit stub and reserved byte
        cmp bk_stub,x
        bne bk_attach_bad
        dex
        bpl -
        lda N_BUFFER+22         ; bk_load patches the callback import only
        ora N_BUFFER+23         ; after CRC and source close: zero = partial
        beq bk_attach_bad
        ldx #7
-       lda N_BUFFER+24,x       ; reserved header tail
        bne bk_attach_bad
        dex
        bpl -
        ldx #4
-       lda N_BUFFER+32,x       ; component identity and major version
        cmp bk_identity,x
        bne bk_attach_bad
        dex
        bpl -
        lda N_BUFFER+6          ; required native ABI minor
        cmp #N_ABI_MINOR+1
        bcs bk_attach_bad
        lda N_BUFFER+7          ; flags
        bne bk_attach_bad
        lda N_BUFFER+11
        cmp #1
        bne bk_attach_bad
        lda N_BUFFER+10
        cmp bk_pages
        bne bk_attach_bad
        lda N_BUFFER+8
        sta bk_length
        lda N_BUFFER+9
        sta bk_length+1
        lda N_BUFFER+12
        sta bk_entry
        lda N_BUFFER+13
        clc
        adc #>BK_BASE
        sta bk_entry+1
        jsr bk_check_code       ; extent, entry range, owner and page tags
        bcs bk_attach_fail
        lda #<bk_callback
        sta N_BUFFER
        lda #>bk_callback
        sta N_BUFFER+1
        lda #22
        sta bk_offset
        lda #0
        sta bk_offset+1
        sta bk_count+1
        lda #2
        sta bk_count
        jsr bk_write_chunk
        bcs bk_attach_fail
        lda #2
        sta bk_state
        lda #0
        jmp bk_finish
bk_attach_bad:
        lda #N_BADIMAGE
bk_attach_fail:
        ldx #0
        stx bk_handle
        stx bk_pages
        jmp bk_finish

; Forget the attachment without freeing the image, before N_EXIT/N_REPLACE.
; bk_close instead unloads the component and frees its allocation.
bk_detach:
        php
        pha
        jsr bk_enter
        bcs bk_attach_gate
        pla
        lda bk_state
        cmp #2
        bne bk_load_badarg
        lda #0
        sta bk_state
        sta bk_handle
        jmp bk_finish
.fi

; CRC16-CCITT, no borrowed zero-page pointer. The buffer cursor and count
; are private and consumed here; native argument mailboxes remain intact.
bk_crc_buffer:
        lda #<N_BUFFER
        sta bk_crc_get+1
        lda #>N_BUFFER
        sta bk_crc_get+2
        lda bk_count
        sta bk_crc_left
        lda bk_count+1
        sta bk_crc_left+1
bk_crc_get:
        lda N_BUFFER
        eor bk_crc+1
        sta bk_crc+1
        ldx #8
-       asl bk_crc
        rol bk_crc+1
        bcc +
        lda bk_crc
        eor #$21
        sta bk_crc
        lda bk_crc+1
        eor #$10
        sta bk_crc+1
+       dex
        bne -
        inc bk_crc_get+1
        bne +
        inc bk_crc_get+2
+       lda bk_crc_left
        bne +
        dec bk_crc_left+1
+       dec bk_crc_left
        lda bk_crc_left
        ora bk_crc_left+1
        bne bk_crc_get
        rts
bk_prefix: .byte <BK_BASE,>BK_BASE,$4e,$42,$4b,$31,1,1 ; PRG address, NBK1, format, ABI major
bk_stub: .byte $a2,$0e,$4c,$ab,$02,0,0,0,0,0
bk_count: .word 0
bk_offset: .word 0
bk_expected: .word 0
bk_crc: .word 0
bk_crc_left: .word 0
