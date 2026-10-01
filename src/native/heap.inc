; Native C128 page ownership and bounded banked transfers, GPL v3.
; INDFET/INDSTA execute the C128 KERNAL's common-RAM bank gateways. Each
; short transfer restores the borrowed pointer and self-modified operand.
; Interrupts remain serviceable between bytes, including a 512-byte call.

heap_init:
        lda #0
        sta N_BUSY
        sta N_ERROR
        ldx #0
heap_clear_handles:
        sta NHANDLES,x
        inx
        bne heap_clear_handles
        lda #$ff
heap_reserve_pages:
        sta NPAGES0,x
        sta NPAGES1,x
        inx
        bne heap_reserve_pages
        lda #0
        ldx #N_FIRST0
heap_free_zero:
        sta NPAGES0,x
        inx
        cpx #$ff
        bne heap_free_zero
        ldx #N_FIRST1
heap_free_one:
        sta NPAGES1,x
        inx
        cpx #$ff
        bne heap_free_one
        rts

; Callers PHP before entering. The saved status is consumed by heap_finish.
heap_enter:
        lda N_BUSY
        beq heap_lock
        lda #N_REENTRANT
        sec
        rts
heap_lock:
        inc N_BUSY
        cld
        lda $ff00
        cmp #$0e
        bne heap_bad_platform
        lda $d505
        and #$40
        bne heap_bad_platform
        lda $d506
        and #$0f
        cmp #4
        bne heap_bad_platform
        lda $d508
        ora $d50a
        and #$0f              ; unused high bits read as ones on the 8722
        ora $d507
        bne heap_bad_platform
        lda $d509
        cmp #1
        bne heap_bad_platform
        clc
        rts
heap_bad_platform:
        lda #N_PLATFORM
        sec
        rts
heap_finish:
        sta N_ERROR
        ldx #0
        stx N_BUSY
        plp
        cmp #1
        rts
heap_nested:
        plp
        sec
        rts                     ; do not alter the active result/lock
heap_enter_failed:
        cmp #N_REENTRANT
        beq heap_nested
        jmp heap_finish
heap_success:
        lda #N_OK
        jmp heap_finish
heap_argument:
        lda #N_BADARG
        jmp heap_finish
heap_owner_argument:
        lda N_OWNER
        beq heap_owner_bad
        cmp #$ff
        beq heap_owner_bad
        clc
        rts
heap_owner_bad:
        lda #N_BADARG
        sec
        rts

heap_alloc:
        php
        jsr heap_enter
        bcc *+5
        jmp heap_enter_failed
        jsr heap_owner_argument
        bcs heap_argument
        lda N_PAGES
        beq heap_argument
        lda N_BANK
        cmp #$ff
        beq heap_auto
        cmp #2
        bcs heap_argument
        sta hbank
        jsr heap_find_run
        bcc heap_have_run
        jmp heap_no_memory
heap_auto:
        lda #1
        sta hbank
        jsr heap_find_run
        bcc heap_have_run
        dec hbank
        jsr heap_find_run
        bcs heap_no_memory
heap_have_run:
        jsr heap_find_slot
        bcs heap_no_slot
        jmp heap_commit
heap_no_memory:
        lda #N_NOMEM
        jmp heap_finish
heap_no_slot:
        lda #N_NOSLOT
        jmp heap_finish

heap_reserve:
        php
        jsr heap_enter
        bcc *+5
        jmp heap_enter_failed
        jsr heap_owner_argument
        bcc *+5
        jmp heap_argument
        lda N_PAGES
        bne *+5
        jmp heap_argument
        lda N_BANK
        cmp #2
        bcc *+5
        jmp heap_argument
        sta hbank
        tax
        lda N_PAGE
        cmp first_page,x
        bcc heap_reserve_range
        sta hstart
        clc
        adc N_PAGES
        bcs heap_reserve_range
        sta hend
        ldx hstart
heap_reserve_check:
        jsr heap_page_get
        bne heap_no_memory
        inx
        cpx hend
        bne heap_reserve_check
        jmp heap_have_run
heap_reserve_range:
        lda #N_RANGE
        jmp heap_finish

heap_find_run:
        lda #0
        sta hrun
        ldx hbank
        lda first_page,x
        tax
heap_scan:
        jsr heap_page_get
        bne heap_scan_used
        lda hrun
        bne heap_scan_next
        stx hstart
heap_scan_next:
        inc hrun
        lda hrun
        cmp N_PAGES
        beq heap_run_found
        bne heap_scan_advance
heap_scan_used:
        lda #0
        sta hrun
heap_scan_advance:
        inx
        cpx #$ff
        bne heap_scan
        sec
        rts
heap_run_found:
        clc
        rts
heap_page_get:
        lda hbank
        bne heap_get_one
        lda NPAGES0,x
        rts
heap_get_one:
        lda NPAGES1,x
        rts
heap_page_set:
        ldy hbank
        bne heap_set_one
        sta NPAGES0,x
        rts
heap_set_one:
        sta NPAGES1,x
        rts

heap_find_slot:
        ldx #0
heap_slot_loop:
        lda NHANDLES,x
        bne heap_slot_next
        lda NHANDLES+4,x
        and NHANDLES+5,x
        and NHANDLES+6,x
        cmp #$ff
        bne heap_slot_found
        ; A generation never wraps back to a previously valid handle.
        sta NHANDLES,x         ; retire after 16,777,215 allocations
heap_slot_next:
        txa
        clc
        adc #8
        tax
        bne heap_slot_loop
        sec
        rts
heap_slot_found:
        stx hslot
        txa
        lsr
        lsr
        lsr
        clc
        adc #1
        sta htag
        clc
        rts

heap_commit:
        ldx hslot
        inc NHANDLES+4,x
        bne heap_generation_ready
        inc NHANDLES+5,x
        bne heap_generation_ready
        inc NHANDLES+6,x
heap_generation_ready:
        lda N_OWNER
        sta NHANDLES,x
        lda hbank
        sta NHANDLES+1,x
        sta N_BANK
        lda hstart
        sta NHANDLES+2,x
        sta N_PAGE
        lda N_PAGES
        sta NHANDLES+3,x
        sta hleft
        lda htag
        sta N_HANDLE
        lda NHANDLES+4,x
        sta N_HANDLE+1
        lda NHANDLES+5,x
        sta N_HANDLE+2
        lda NHANDLES+6,x
        sta N_HANDLE+3
        ldx hstart
heap_mark:
        lda htag
        jsr heap_page_set
        inx
        dec hleft
        bne heap_mark
        jmp heap_success

heap_handle:
        jsr heap_owner_argument
        bcs heap_handle_end
        lda N_HANDLE
        beq heap_handle_bad
        cmp #NSLOTS+1
        bcs heap_handle_bad
        sta htag
        sec
        sbc #1
        asl
        asl
        asl
        tax
        stx hslot
        lda NHANDLES,x
        beq heap_handle_bad
        cmp #$ff
        beq heap_handle_bad
        lda NHANDLES+4,x
        cmp N_HANDLE+1
        bne heap_handle_bad
        lda NHANDLES+5,x
        cmp N_HANDLE+2
        bne heap_handle_bad
        lda NHANDLES+6,x
        cmp N_HANDLE+3
        bne heap_handle_bad
        lda NHANDLES,x
        cmp N_OWNER
        bne heap_handle_owner
        clc
heap_handle_end:
        rts
heap_handle_bad:
        lda #N_BADHANDLE
        sec
        rts
heap_handle_owner:
        lda #N_WRONGOWNER
        sec
        rts

heap_check_record:
        ldx hslot
        lda NHANDLES+1,x
        cmp #2
        bcs heap_record_bad
        sta hbank
        tay
        lda NHANDLES+2,x
        cmp first_page,y
        bcc heap_record_bad
        sta hstart
        lda NHANDLES+3,x
        beq heap_record_bad
        sta hleft
        clc
        adc hstart
        bcs heap_record_bad
        sta hend
        ldx hstart
heap_record_page:
        jsr heap_page_get
        cmp htag
        bne heap_record_bad
        inx
        cpx hend
        bne heap_record_page
        clc
        rts
heap_record_bad:
        lda #N_CORRUPT
        sec
        rts

heap_free:
        php
        jsr heap_enter
        bcc *+5
        jmp heap_enter_failed
        jsr heap_handle
        bcs heap_free_error
        jsr heap_check_record
        bcs heap_free_error
        jsr heap_clear_record
        jmp heap_success
heap_free_error:
        jmp heap_finish
heap_clear_record:
        lda htag
        cmp v_tag
        bne +
        jsr display_restore   ; restore before any displayed page becomes free
+
        ldx hstart
heap_unmark:
        lda #0
        jsr heap_page_set
        inx
        cpx hend
        bne heap_unmark
        ldx hslot
        lda #0
        sta NHANDLES,x         ; retain generation, invalidate ownership
        rts

heap_release:
        php
        jsr heap_enter
        bcc *+5
        jmp heap_enter_failed
        jsr heap_owner_argument
        bcs heap_free_error
        lda #0
        sta hpass
heap_release_pass:
        lda #0
        sta hslot
        lda #1
        sta htag
heap_release_loop:
        ldx hslot
        lda NHANDLES,x
        cmp N_OWNER
        bne heap_release_next
        jsr heap_check_record
        bcs heap_free_error
        lda hpass
        beq heap_release_next
        jsr heap_clear_record
heap_release_next:
        inc htag
        lda hslot
        clc
        adc #8
        sta hslot
        bne heap_release_loop
        inc hpass
        lda hpass
        cmp #2
        bne heap_release_pass  ; preflight every record before freeing any
        jmp heap_success

heap_stats:
        php
        jsr heap_enter
        bcc *+5
        jmp heap_enter_failed
        lda #0
        sta N_FREE0
        sta N_FREE1
        sta N_SLOTS
        ldx #0
heap_count_pages:
        lda NPAGES0,x
        bne heap_count_one
        inc N_FREE0
heap_count_one:
        lda NPAGES1,x
        bne heap_count_next
        inc N_FREE1
heap_count_next:
        inx
        bne heap_count_pages
heap_count_slots:
        lda NHANDLES,x
        bne heap_count_slot_next
        lda NHANDLES+4,x
        and NHANDLES+5,x
        and NHANDLES+6,x
        cmp #$ff
        beq heap_count_slot_next
        inc N_SLOTS
heap_count_slot_next:
        txa
        clc
        adc #8
        tax
        bne heap_count_slots
        jmp heap_success

heap_read:
        php
        lda #0
        beq heap_transfer
heap_write:
        php
        lda #1
        bne heap_transfer
heap_fill:
        php
        lda #2
heap_transfer:
        pha
        jsr heap_enter
        bcc heap_transfer_entered
        tax
        pla
        txa
        jmp heap_enter_failed
heap_transfer_entered:
        pla
        sta hoperation
        jsr heap_handle
        bcc *+5
        jmp heap_finish
        jsr heap_check_record
        bcc *+5
        jmp heap_finish
        lda N_COUNT+1
        cmp #2
        bcc heap_count_small
        bne heap_transfer_range
        lda N_COUNT
        bne heap_transfer_range
heap_count_small:
        lda N_COUNT
        ora N_COUNT+1
        beq heap_transfer_range
        clc
        lda N_OFFSET
        adc N_COUNT
        sta hbound
        lda N_OFFSET+1
        adc N_COUNT+1
        bcs heap_transfer_range
        ldx hslot
        cmp NHANDLES+3,x
        bcc heap_transfer_valid
        bne heap_transfer_range
        lda hbound
        beq heap_transfer_valid
heap_transfer_range:
        lda #N_RANGE
        jmp heap_finish
heap_transfer_valid:
        lda N_OFFSET
        sta haddress
        clc
        lda N_OFFSET+1
        adc hstart
        sta haddress+1
        lda N_COUNT
        sta hremaining
        lda N_COUNT+1
        sta hremaining+1
        lda #<N_BUFFER
        sta heap_buffer_read+1
        sta heap_buffer_write+1
        lda #>N_BUFFER
        sta heap_buffer_read+2
        sta heap_buffer_write+2
heap_transfer_loop:
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
        inc haddress
        bne heap_address_ok
        inc haddress+1
heap_address_ok:
        inc heap_buffer_read+1
        inc heap_buffer_write+1
        bne heap_buffer_ok
        inc heap_buffer_read+2
        inc heap_buffer_write+2
heap_buffer_ok:
        lda hremaining
        bne heap_remaining_low
        dec hremaining+1
heap_remaining_low:
        dec hremaining
        lda hremaining
        ora hremaining+1
        bne heap_transfer_loop
        jmp heap_success
heap_far_fetch:
        php
        sei
        lda $fb
        pha
        lda $fc
        pha
        lda $02aa
        pha
        lda haddress
        sta $fb
        lda haddress+1
        sta $fc
        lda #$fb
        ldx hbank
        ldy #0
        jsr $ff74
        sta hbyte
        pla
        sta $02aa
        pla
        sta $fc
        pla
        sta $fb
        plp
        lda hbyte
        rts
heap_far_store:
        sta hbyte
        php
        sei
        lda $fb
        pha
        lda $fc
        pha
        lda $02b9
        pha
        lda haddress
        sta $fb
        lda haddress+1
        sta $fc
        lda #$fb
        sta $02b9
        lda hbyte
        ldx hbank
        ldy #0
        jsr $ff77
        pla
        sta $02b9
        pla
        sta $fc
        pla
        sta $fb
        plp
        rts

first_page: .byte N_FIRST0, N_FIRST1
hbank: .byte 0
hstart: .byte 0
hend: .byte 0
hrun: .byte 0
hleft: .byte 0
hslot: .byte 0
htag: .byte 0
hpass: .byte 0
hoperation: .byte 0
haddress: .word 0
hremaining: .word 0
hbound: .byte 0
hbyte: .byte 0
