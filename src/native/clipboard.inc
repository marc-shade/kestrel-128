.include "clipboard-api.inc"

cp_begin:
        php
        jsr cp_enter
        bcs cp_enter_failed
        lda cp_length+2
        bne cp_range
        lda cp_length
        ora cp_length+1
        beq cp_range
        lda cp_length+1
        cmp #>CB_MAX_BYTES
        bcc +
        bne cp_range
        lda cp_length
        bne cp_range
+       jsr cp_sequence_check
        bcs cp_finish
        jsr cp_discard
        bcs cp_finish
        lda cp_length
        cmp #1
        lda cp_length+1
        adc #0
        sta cp_pages
        lda #4
        sta cp_page
cp_allocate:
        lda #N_CLIPOWNER
        sta N_OWNER
        lda #1
        sta N_BANK
        lda cp_page
        sta N_PAGE
        clc
        adc cp_pages
        bcs cp_nomem
        ldx cp_page
        cpx #$c0
        bcs cp_high_range
        cmp #$61
        bcc cp_reserve
        lda #$c0
        sta cp_page
        bne cp_allocate
cp_high_range:
        cmp #$ff
        bcc cp_reserve
        bne cp_nomem
cp_reserve:
        lda cp_pages
        sta N_PAGES
        jsr N_RESERVE
        bcc cp_allocated
        cmp #N_NOMEM
        bne cp_finish
        inc cp_page
        bne cp_allocate
cp_nomem:
        lda #N_NOMEM
        bne cp_finish
cp_allocated:
        ldx #3
-       lda N_HANDLE,x
        sta CB_PENDING,x
        lda cp_cookie,x
        sta CB_COOKIE,x
        dex
        bpl -
        ldx #2
-       lda cp_length,x
        sta CB_EXPECTED,x
        lda #0
        sta CB_WRITTEN,x
        dex
        bpl -
        jmp cp_success

cp_write:
        php
        jsr cp_enter
        bcs cp_enter_failed
        jsr cp_draft
        bcs cp_finish
        lda CB_EXPECTED+2
        bne cp_corrupt
        ldx #2
-       lda CB_WRITTEN,x
        sta cp_offset,x
        dex
        bpl -
        jsr cp_bounds
        bcs cp_finish
        lda cp_end
        cmp CB_EXPECTED
        lda cp_end+1
        sbc CB_EXPECTED+1
        bcc cp_write_ready
        bne cp_range
        lda cp_end
        cmp CB_EXPECTED
        bne cp_range
cp_write_ready:
        ldy #CB_PENDING-N_CLIPBOARD
        jsr cp_select
        jsr N_WRITE
        bcc +
        ldx #$ff
        stx CB_EXPECTED+2
        jmp cp_finish
+       lda cp_end
        sta CB_WRITTEN
        lda cp_end+1
        sta CB_WRITTEN+1
        jmp cp_success

cp_commit:
        php
        jsr cp_enter
        bcs cp_enter_failed
        jsr cp_draft
        bcs cp_finish
        jsr cp_sequence_check
        bcs cp_finish
        ldx #2
-       lda CB_WRITTEN,x
        cmp CB_EXPECTED,x
        bne cp_range
        dex
        bpl -
        jsr cp_release_published
        bcs cp_finish
        ldx #3
-       lda CB_PENDING,x
        sta CB_HANDLE,x
        lda #0
        sta CB_PENDING,x
        dex
        bpl -
        ldx #2
-       lda CB_EXPECTED,x
        sta CB_LENGTH,x
        dex
        bpl -
        lda #CB_TEXT
        sta CB_FORMAT
        jmp cp_published

cp_abort:
        php
        jsr cp_enter
        bcs cp_enter_failed
        jsr cp_discard
        jmp cp_finish
cp_clear:
        php
        jsr cp_enter
        bcs cp_enter_failed
        jsr cp_sequence_check
        bcs cp_finish
        jsr cp_discard
        bcs cp_finish
        jsr cp_release_published
        bcs cp_finish
        lda #0
        sta CB_FORMAT
        sta CB_LENGTH
        sta CB_LENGTH+1
        sta CB_LENGTH+2
cp_published:
        inc CB_SEQUENCE
        bne cp_success
        inc CB_SEQUENCE+1
        bne cp_success
        inc CB_SEQUENCE+2
        jmp cp_success

cp_info:
        php
        jsr cp_enter
        bcs cp_enter_failed
        ldx #2
-       lda CB_LENGTH,x
        sta cp_length,x
        dex
        bpl -
        lda CB_FORMAT
        sta cp_format
        jmp cp_success
cp_read:
        php
        jsr cp_enter
        bcs cp_enter_failed
        lda CB_FORMAT
        cmp #CB_TEXT
        bne cp_badhandle
        lda CB_LENGTH+2
        bne cp_corrupt
        jsr cp_bounds
        bcs cp_finish
        lda cp_end
        cmp CB_LENGTH
        lda cp_end+1
        sbc CB_LENGTH+1
        bcc cp_read_ready
        bne cp_range
        lda cp_end
        cmp CB_LENGTH
        bne cp_range
cp_read_ready:
        ldy #CB_HANDLE-N_CLIPBOARD
        jsr cp_select
        jsr N_READ
        jmp cp_finish

; Range checking never modifies the transfer buffer or a published item.
cp_bounds:
        lda cp_offset+2
        bne cp_bounds_bad
        lda cp_count+1
        cmp #2
        bcc +
        bne cp_bounds_bad
        lda cp_count
        bne cp_bounds_bad
+       lda cp_count
        ora cp_count+1
        beq cp_bounds_bad
        clc
        lda cp_offset
        adc cp_count
        sta cp_end
        lda cp_offset+1
        adc cp_count+1
        sta cp_end+1
        bcs cp_bounds_bad
        lda #0
        rts
cp_bounds_bad:
        lda #N_RANGE
        sec
        rts
cp_select:
        ldx #0
-       lda N_CLIPBOARD,y
        sta N_HANDLE,x
        iny
        inx
        cpx #4
        bne -
        lda #N_CLIPOWNER
        sta N_OWNER
        ldx #1
-       lda cp_offset,x
        sta N_OFFSET,x
        lda cp_count,x
        sta N_COUNT,x
        dex
        bpl -
        rts
cp_discard:
        lda CB_PENDING
        beq cp_private_ok
        ldy #CB_PENDING-N_CLIPBOARD
        jsr cp_select
        jsr N_FREE
        bcs cp_private_return
        lda #0
        sta CB_PENDING
cp_private_ok:
        lda #0
        clc
cp_private_return:
        rts
cp_release_published:
        lda CB_HANDLE
        beq cp_private_ok
        ldy #CB_HANDLE-N_CLIPBOARD
        jsr cp_select
        jsr N_FREE
        bcs cp_private_return
        lda #0
        sta CB_HANDLE
        clc
        rts
cp_draft:
        lda CB_PENDING
        beq cp_private_badhandle
        ldx #3
-       lda CB_COOKIE,x
        cmp cp_cookie,x
        bne cp_private_badhandle
        dex
        bpl -
        clc
        rts
cp_private_badhandle:
        lda #N_BADHANDLE
        sec
        rts
cp_sequence_check:
        lda CB_SEQUENCE
        and CB_SEQUENCE+1
        and CB_SEQUENCE+2
        cmp #$ff
        bne cp_private_ok
        lda #N_MEXHAUSTED
        sec
        rts

; A global per-call lock excludes reentrancy across copies of the library.
; Only the foreground app may stage a draft. Its generation guards commit.
cp_enter:
        lda CB_BUSY
        ora N_BUSY
        ora N_FBUSY
        ora N_UIBUSY
        bne cp_nested
        inc CB_BUSY
        cld
        lda #0
        sta N_READY
        tsx
        lda $0103,x
        and #4
        bne cp_platform
        jsr N_STATS
        bcs cp_private_return
        lda N_CURRENT
        cmp #N_APPOWNER
        bne cp_platform
        lda N_APPSTATE
        cmp #2
        bne cp_platform
        lda CB_VERSION
        beq +
        cmp #1
        bne cp_platform
+       lda #1
        sta CB_VERSION
        lda NPAGES0+$60
        beq cp_private_badhandle
        cmp #NSLOTS+1
        bcs cp_private_badhandle
        sta cp_cookie
        sec
        sbc #1
        asl
        asl
        asl
        tax
        lda NHANDLES,x
        cmp #N_APPOWNER
        bne cp_private_badhandle
        lda NHANDLES+1,x
        bne cp_private_badhandle
        lda NHANDLES+2,x
        cmp #$60
        bne cp_private_badhandle
        ldy #1
-       lda NHANDLES+4,x
        sta cp_cookie,y
        inx
        iny
        cpy #4
        bne -
        clc
        rts
cp_platform:
        lda #N_PLATFORM
        sec
        rts
cp_nested:
        lda #N_REENTRANT
        sec
        rts
cp_enter_failed:
        cmp #N_REENTRANT
        bne cp_finish
        plp
        sec
        rts
cp_range:
        lda #N_RANGE
        bne cp_finish
cp_badhandle:
        lda #N_BADHANDLE
        bne cp_finish
cp_corrupt:
        lda #N_CORRUPT
        bne cp_finish
cp_success:
        lda #0
cp_finish:
        ldx #0
        stx CB_BUSY
        plp
        cmp #1
        rts
cp_length: .fill 3,0
cp_offset: .fill 3,0
cp_count: .word 0
cp_format: .byte 0
cp_end: .word 0
cp_cookie: .fill 4,0
cp_page: .byte 0
cp_pages: .byte 0
