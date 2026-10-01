; Foreground REU arena, retained in the app core. Include exactly once per app.
; See docs/NATIVE-REU.md. No resident bytes, zero-page scratch or heap pages.
; All entries preserve D/I and return A=0/C=0 or native error/C=1.
; Public arguments/results are ru_owner/pages/page/handle/offset/count/actual.
; The eight-byte token is slot+generation LE24 + native app handle.
; Modules call this retained copy; they must not instantiate another arena.
.weak
RU_BANKED = 0                 ; banked.inc owns the temporary common-RAM map
RU_INCLUDE_RESIZE = 0         ; opt-in growth for shared document extents
.endweak

ru_open:
        php
        jsr ru_enter
        bcs ru_enter_failed
        lda ru_cookie
        bne +
        ldx #3
-       lda ru_current,x
        sta ru_cookie,x
        dex
        bpl -
+       jsr ru_context
        bcs ru_finish
        lda ru_active
        bne ru_success
        jsr ru_probe_restore
        bcs ru_finish
        jsr ru_probe
        bcc +
        pha
        jsr ru_probe_restore
        pla
        bcs ru_ioerror
        jmp ru_finish
+       lda #1
        sta ru_active
        jmp ru_success

; A closed arena keeps retired generations until the app allocation ends.
ru_close:
        php
        jsr ru_enter
        bcs ru_enter_failed
        jsr ru_context
        bcs ru_finish
        jsr ru_probe_restore
        bcs ru_finish
        ldx #0
-       lda ru_records,x
        bne ru_argument
        txa
        clc
        adc #8
        tax
        bne -
        sta ru_active
        jmp ru_success

ru_enter:
        lda ru_busy
        ora N_BUSY
        ora N_FBUSY
        ora N_UIBUSY
        bne ru_nested
        inc ru_busy
        cld
        lda $ff00
.if RU_BANKED
        cmp #$4e
.else
        cmp #$0e
.endif
        bne ru_platform_error
        lda $d505
        and #$40
        bne ru_platform_error
        lda $d506
        and #15
.if RU_BANKED
        cmp #7
.else
        cmp #4
.endif
        bne ru_platform_error
        lda N_CURRENT
        cmp #N_APPOWNER
        bne ru_platform_error
        lda N_APPSTATE
        cmp #2
        bne ru_platform_error
        lda NPAGES0+$60
        beq ru_platform_error
        cmp #NSLOTS+1
        bcs ru_platform_error
        sta ru_current
        sec
        sbc #1
        asl
        asl
        asl
        tax
        lda NHANDLES,x
        cmp N_CURRENT
        bne ru_platform_error
        lda NHANDLES+1,x
        bne ru_platform_error
        lda NHANDLES+2,x
        cmp #$60
        bne ru_platform_error
        lda NHANDLES+4,x
        sta ru_current+1
        lda NHANDLES+5,x
        sta ru_current+2
        lda NHANDLES+6,x
        sta ru_current+3
        clc
        rts
ru_platform_error:
        lda #N_PLATFORM
        sec
        rts
ru_nested:
        lda #N_REENTRANT
        sec
        rts
ru_enter_failed:
        cmp #N_REENTRANT
        bne ru_finish
        plp
        sec
        rts
ru_context:
        ldx #3
-       lda ru_cookie,x
        cmp ru_current,x
        bne ru_bad_token
        dex
        bpl -
        clc
        rts
ru_ready:
        jsr ru_context
        bcs +
        lda ru_active
        beq ru_platform_error
        lda ru_owner
        beq ru_bad_argument
        cmp #255
        beq ru_bad_argument
        clc
+       rts
ru_bad_argument:
        lda #N_BADARG
        sec
        rts
ru_bad_token:
        lda #N_BADHANDLE
        sec
        rts
ru_success:
        lda #0
ru_finish:
        sta ru_error
        ldx #0
        stx ru_busy
        plp
        cmp #1
        rts
ru_argument:
        lda #N_BADARG
        jmp ru_finish
ru_ioerror:
        lda #N_IOERROR
        jmp ru_finish
ru_range:
        lda #N_RANGE
        jmp ru_finish
ru_nomem:
        lda #N_NOMEM
        jmp ru_finish

ru_alloc:
        ldy #0
        beq ru_allocate
ru_reserve:
        ldy #1
ru_allocate:
        php
        jsr ru_enter
        bcs ru_enter_failed
        sty ru_fixed
        jsr ru_ready
        bcs ru_finish
        lda ru_pages
        ora ru_pages+1
        beq ru_argument
        ldx #0
ru_slot_scan:
        lda ru_records,x
        bne +
        lda ru_records+5,x
        and ru_records+6,x
        and ru_records+7,x
        cmp #255
        bne ru_slot_found
+       txa
        clc
        adc #8
        tax
        bne ru_slot_scan
        lda #N_NOSLOT
        jmp ru_finish
ru_slot_found:
        stx ru_slot
        lda #0
        sta ru_first
        sta ru_first+1
        lda ru_fixed
        beq ru_scan_again
        lda ru_page
        sta ru_first
        lda ru_page+1
        sta ru_first+1
ru_scan_again:
        clc
        lda ru_first
        adc ru_pages
        sta ru_limit
        lda ru_first+1
        adc ru_pages+1
        sta ru_limit+1
        bcs ru_nomem
        lda ru_total
        cmp ru_limit
        lda ru_total+1
        sbc ru_limit+1
        bcc ru_nomem
        ldx #0
ru_interval:
        lda ru_records,x
        beq ru_next_interval
        lda ru_records+1,x
        cmp ru_limit
        lda ru_records+2,x
        sbc ru_limit+1
        bcs ru_next_interval
        clc
        lda ru_records+1,x
        adc ru_records+3,x
        sta ru_last
        lda ru_records+2,x
        adc ru_records+4,x
        sta ru_last+1
        lda ru_first
        cmp ru_last
        lda ru_first+1
        sbc ru_last+1
        bcs ru_next_interval
        lda ru_fixed
        bne ru_nomem
        lda ru_last
        sta ru_first
        lda ru_last+1
        sta ru_first+1
        jmp ru_scan_again
ru_next_interval:
        txa
        clc
        adc #8
        tax
        bne ru_interval
        ldx ru_slot
        inc ru_records+5,x
        bne +
        inc ru_records+6,x
        bne +
        inc ru_records+7,x
+       lda ru_owner
        sta ru_records,x
        lda ru_first
        sta ru_records+1,x
        sta ru_page
        lda ru_first+1
        sta ru_records+2,x
        sta ru_page+1
        lda ru_pages
        sta ru_records+3,x
        lda ru_pages+1
        sta ru_records+4,x
        txa
        lsr
        lsr
        lsr
        clc
        adc #1
        sta ru_handle
        lda ru_records+5,x
        sta ru_handle+1
        lda ru_records+6,x
        sta ru_handle+2
        lda ru_records+7,x
        sta ru_handle+3
        ldx #3
-       lda ru_cookie,x
        sta ru_handle+4,x
        dex
        bpl -
        jmp ru_success

ru_validate:
        jsr ru_ready
        bcs +
        ldx #3
-       lda ru_handle+4,x
        cmp ru_cookie,x
        bne ru_bad_token
        dex
        bpl -
        lda ru_handle
        beq ru_bad_token
        cmp #33
        bcs ru_bad_token
        sec
        sbc #1
        asl
        asl
        asl
        tax
        lda ru_records,x
        beq ru_bad_token
        lda ru_handle+1
        cmp ru_records+5,x
        bne ru_bad_token
        lda ru_handle+2
        cmp ru_records+6,x
        bne ru_bad_token
        lda ru_handle+3
        cmp ru_records+7,x
        bne ru_bad_token
        lda ru_records,x
        cmp ru_owner
        bne ru_other_owner
        clc
+       rts
ru_other_owner:
        lda #N_WRONGOWNER
        sec
        rts

.if RU_INCLUDE_RESIZE
; Grow an extent in place, preserving its token and every REU byte. ru_pages
; is the requested total size in 4K pages. Equal size succeeds; shrinking or
; zero is BADARG. N_NOMEM leaves the original extent intact, allowing callers
; to allocate/copy/free a replacement. No DMA or generation changes occur.
ru_resize:
        php
        jsr ru_enter
        bcs ru_enter_failed
        jsr ru_validate
        bcs ru_finish
        stx ru_slot
        lda ru_pages
        ora ru_pages+1
        beq ru_argument
        lda ru_pages
        cmp ru_records+3,x
        lda ru_pages+1
        sbc ru_records+4,x
        bcc ru_argument
        lda ru_records+1,x
        sta ru_first
        sta ru_page
        lda ru_records+2,x
        sta ru_first+1
        sta ru_page+1
        clc
        lda ru_first
        adc ru_pages
        sta ru_limit
        lda ru_first+1
        adc ru_pages+1
        sta ru_limit+1
        bcs ru_nomem
        lda ru_total
        cmp ru_limit
        lda ru_total+1
        sbc ru_limit+1
        bcc ru_nomem
        ldx #0
ru_resize_scan:
        cpx ru_slot
        beq ru_resize_next
        lda ru_records,x
        beq ru_resize_next
        lda ru_records+1,x
        cmp ru_limit
        lda ru_records+2,x
        sbc ru_limit+1
        bcs ru_resize_next
        clc
        lda ru_records+1,x
        adc ru_records+3,x
        sta ru_last
        lda ru_records+2,x
        adc ru_records+4,x
        sta ru_last+1
        lda ru_first
        cmp ru_last
        lda ru_first+1
        sbc ru_last+1
        bcc ru_nomem
ru_resize_next:
        txa
        clc
        adc #8
        tax
        bne ru_resize_scan
        ldx ru_slot
        lda ru_pages
        sta ru_records+3,x
        lda ru_pages+1
        sta ru_records+4,x
        jmp ru_success
.endif

ru_free:
        php
        jsr ru_enter
        bcs ru_enter_failed
        jsr ru_validate
        bcs ru_finish
        lda #0
        sta ru_records,x
        jmp ru_finish
ru_release:
        php
        jsr ru_enter
        bcs ru_enter_failed
        jsr ru_ready
        bcs ru_finish
        ldx #0
-       lda ru_records,x
        cmp ru_owner
        bne +
        lda #0
        sta ru_records,x
+       txa
        clc
        adc #8
        tax
        bne -
        jmp ru_success
ru_stats:
        php
        jsr ru_enter
        bcs ru_enter_failed
        jsr ru_ready
        bcs ru_finish
        lda ru_total
        sta ru_available
        lda ru_total+1
        sta ru_available+1
        ldx #0
        stx ru_slots
-       lda ru_records,x
        beq +
        sec
        lda ru_available
        sbc ru_records+3,x
        sta ru_available
        lda ru_available+1
        sbc ru_records+4,x
        sta ru_available+1
        jmp ++
+       lda ru_records+5,x
        and ru_records+6,x
        and ru_records+7,x
        cmp #255
        beq +
        inc ru_slots
+       txa
        clc
        adc #8
        tax
        bne -
        jmp ru_success

ru_write:
        ldy #$90
        bne ru_transfer
ru_read:
        ldy #$91
ru_transfer:
        php
        jsr ru_enter
        bcs ru_transfer_failed
        sty ru_command
        lda #0
        sta ru_actual
        sta ru_actual+1
        jsr ru_validate
        bcs ru_finish
        lda ru_count
        ora ru_count+1
        beq ru_range
        lda ru_count+1
        cmp #2
        bcc +
        bne ru_range
        lda ru_count
        bne ru_range
+       lda ru_records+3,x
        sta ru_bound+1
        lda ru_records+4,x
        sta ru_bound+2
        lda #0
        sta ru_bound
        ldy #4
-       asl ru_bound+1
        rol ru_bound+2
        dey
        bne -
        ; 4096 pages needs a 25th end bit: only the full-device allocation.
        lda #0
        rol
        sta ru_full
        clc
        lda ru_offset
        adc ru_count
        sta ru_end
        lda ru_offset+1
        adc ru_count+1
        sta ru_end+1
        lda ru_offset+2
        adc #0
        sta ru_end+2
        lda #0
        rol
        cmp ru_full
        bcc ru_offset_valid
        bne ru_range
        lda ru_bound
        cmp ru_end
        lda ru_bound+1
        sbc ru_end+1
        lda ru_bound+2
        sbc ru_end+2
        bcc ru_range
ru_offset_valid:
        lda #0
        sta ru_address
        lda ru_records+1,x
        sta ru_address+1
        lda ru_records+2,x
        sta ru_address+2
        ldy #4
-       asl ru_address+1
        rol ru_address+2
        dey
        bne -
        clc
        lda ru_offset
        sta ru_address
        lda ru_offset+1
        adc ru_address+1
        sta ru_address+1
        lda ru_offset+2
        adc ru_address+2
        sta ru_address+2
        lda ru_count
        sta ru_remaining
        lda ru_count+1
        sta ru_remaining+1
ru_chunk:
        lda ru_remaining
        sta ru_length
        lda ru_remaining+1
        sta ru_length+1
        clc
        lda ru_address
        adc ru_length
        lda ru_address+1
        adc ru_length+1
        bcc +
        ; Split at every 64K edge, also covering REC's 512K wrap.
        sec
        lda #0
        sbc ru_address
        sta ru_length
        lda #0
        sbc ru_address+1
        sta ru_length+1
+       lda ru_actual
        sta ru_host
        clc
        lda ru_actual+1
        adc #>N_BUFFER
        sta ru_host+1
        jsr ru_dma
        bcs ru_finish
        clc
        lda ru_actual
        adc ru_length
        sta ru_actual
        lda ru_actual+1
        adc ru_length+1
        sta ru_actual+1
        clc
        lda ru_address
        adc ru_length
        sta ru_address
        lda ru_address+1
        adc ru_length+1
        sta ru_address+1
        bcc +
        inc ru_address+2
+       sec
        lda ru_remaining
        sbc ru_length
        sta ru_remaining
        lda ru_remaining+1
        sbc ru_length+1
        sta ru_remaining+1
        ora ru_remaining
        bne ru_chunk
        jmp ru_success

ru_transfer_failed:
        cmp #N_REENTRANT
        beq ru_enter_failed
        pha
        lda #0
        sta ru_actual
        sta ru_actual+1
        pla
        jmp ru_finish

; Idle REC ownership. Never consume another driver's armed command or IRQ.
; Unreadable extended bank latches are deliberately set to zero after DMA.
ru_hw_check:
        lda $df01
        bmi ru_hw_busy
        lda $df09
        and #$e0
        bne ru_hw_busy
        lda $df09
        and #31
        cmp #31
        bne ru_platform_error
        lda $df0a
        and #63
        cmp #63
        bne ru_platform_error
        clc
        rts
ru_hw_busy:
        lda #N_CHANNELS
        sec
        rts
ru_dma:
        php
        sei
        jsr ru_hw_check
        bcs ru_dma_return
        lda $d506
        pha
        and #$bf              ; DMA sees physical bank 0; no MMU/ROM changes
.if RU_BANKED
        ldx ru_host+1         ; the private probe pair resides in bank 1
        cpx #$40              ; N_BUFFER remains physical bank 0
        bcc +
        ora #$40
+
.endif
        sta $d506
        lda $d030
        pha
        and #$fe
        sta $d030
        lda #0
        sta $df09
        sta $df0a
        lda ru_host
        sta $df02
        lda ru_host+1
        sta $df03
        ldx #2
-       lda ru_address,x
        sta $df04,x
        dex
        bpl -
        lda ru_length
        sta $df07
        lda ru_length+1
        sta $df08
        lda $df00             ; acknowledge this arena's old completion
        lda ru_command
        sta $df01             ; immediate, <=512 bytes; CPU resumes after DMA
        lda $df00
        and #$60
        cmp #$40
        php
        lda #0
        sta $df06
        lda #$10
        sta $df01             ; disarm FF00 decode before any native bank call
        ldx #0
        plp
        beq +
        ldx #N_IOERROR
+       pla
        sta $d030
        pla
        sta $d506
        txa
ru_dma_return:
        plp
        cmp #1
        rts

; Preserve two bytes at zero and each power-of-two bank. Two distinct bytes
; reject an unpopulated 1764 bank's floating data latch. No RAM is cleared.
ru_probe:
        jsr ru_hw_check
        bcs ru_probe_return
        lda #0
        sta ru_address
        sta ru_address+1
        sta ru_address+2
        lda #2
        sta ru_length
        lda #0
        sta ru_length+1
        lda #<ru_probe_data
        sta ru_host
        lda #>ru_probe_data
        sta ru_host+1
        jsr ru_probe_read
        bcs ru_probe_return
        lda ru_probe_data
        sta ru_probe_zero
        lda ru_probe_data+1
        sta ru_probe_zero+1
        lda #1
        sta ru_probe_live
        lda #$55
        sta ru_probe_data
        lda #$aa
        sta ru_probe_data+1
        jsr ru_probe_write
        bcs ru_probe_return
        jsr ru_probe_read
        bcs ru_probe_return
        lda ru_probe_data
        cmp #$55
        bne ru_probe_error
        lda ru_probe_data+1
        cmp #$aa
        bne ru_probe_error
        lda #1
        sta ru_probe_bank
ru_probe_bank_next:
        lda ru_probe_bank
        sta ru_address+2
        jsr ru_probe_read
        bcs ru_probe_return
        lda ru_probe_data
        sta ru_probe_other
        lda ru_probe_data+1
        sta ru_probe_other+1
        lda #3
        sta ru_probe_live
        lda #$a5
        sta ru_probe_data
        lda #$5a
        sta ru_probe_data+1
        jsr ru_probe_write
        bcs ru_probe_return
        jsr ru_probe_read
        bcs ru_probe_return
        lda ru_probe_data
        cmp #$a5
        bne ru_probe_limit
        lda ru_probe_data+1
        cmp #$5a
        bne ru_probe_limit
        lda #0
        sta ru_address+2
        jsr ru_probe_read
        bcs ru_probe_return
        lda ru_probe_data
        cmp #$55
        bne ru_probe_limit
        lda ru_probe_data+1
        cmp #$aa
        bne ru_probe_limit
        jsr ru_probe_restore_other
        bcs ru_probe_return
        asl ru_probe_bank
        bne ru_probe_bank_next
        lda #0
        sta ru_total
        lda #16
        sta ru_total+1        ; all 256 banks: 16 MiB = 4096 pages
        bne ru_probe_done
ru_probe_limit:
        lda ru_probe_bank
        sta ru_total
        lda #0
        sta ru_total+1
        ldx #4
-       asl ru_total
        rol ru_total+1
        dex
        bne -
ru_probe_done:
        jsr ru_probe_restore
        bcs ru_probe_return
        lda ru_total+1
        bne +
        lda ru_total
        cmp #32
        bcc ru_platform_error
+       lda #0
        clc
ru_probe_return:
        rts
ru_probe_error:
        lda #N_IOERROR
        sec
        rts
ru_probe_read:
        lda #$91
        bne +
ru_probe_write:
        lda #$90
+       sta ru_command
        jmp ru_dma
ru_probe_restore_other:
        lda ru_probe_live
        and #2
        beq +
        lda ru_probe_bank
        sta ru_address+2
        lda ru_probe_other
        sta ru_probe_data
        lda ru_probe_other+1
        sta ru_probe_data+1
        jsr ru_probe_write
        bcs ru_probe_return
        lda #1
        sta ru_probe_live
+       clc
        rts
ru_probe_restore:
        lda ru_probe_live
        beq +
        lda #0
        sta ru_address
        sta ru_address+1
        sta ru_length+1
        lda #2
        sta ru_length
        lda #<ru_probe_data
        sta ru_host
        lda #>ru_probe_data
        sta ru_host+1
        jsr ru_probe_restore_other
        bcs ru_probe_return
        lda #0
        sta ru_address+2
        lda ru_probe_zero
        sta ru_probe_data
        lda ru_probe_zero+1
        sta ru_probe_data+1
        jsr ru_probe_write
        bcs ru_probe_return
        lda #0
        sta ru_probe_live
+       clc
        rts

ru_owner: .byte 0
ru_pages: .word 0             ; request, 4 KiB pages
ru_page: .word 0              ; reserve input / allocation start output
ru_handle: .fill 8,0
ru_offset: .fill 3,0          ; allocation-relative byte offset, LE24
ru_count: .word 0             ; 1..512 bytes through N_BUFFER
ru_actual: .word 0            ; completed prefix; zero before validation
ru_error: .byte 0
ru_total: .word 0             ; detected 4 KiB pages
ru_available: .word 0
ru_slots: .byte 0
ru_active: .byte 0
ru_busy: .byte 0
ru_cookie: .fill 4,0
ru_current: .fill 4,0
ru_fixed: .byte 0
ru_slot: .byte 0
ru_first: .word 0
ru_limit: .word 0
ru_last: .word 0
ru_bound: .fill 3,0
ru_end: .fill 3,0
ru_full: .byte 0
ru_address: .fill 3,0
ru_host: .word 0
ru_length: .word 0
ru_remaining: .word 0
ru_command: .byte 0
ru_probe_live: .byte 0
ru_probe_bank: .byte 0
ru_probe_zero: .word 0
ru_probe_other: .word 0
ru_probe_data: .word 0
ru_records: .fill 256,0       ; owner, start LE16, count LE16, generation LE24
ru_end_library:
