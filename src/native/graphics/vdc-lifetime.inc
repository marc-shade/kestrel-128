; Owned 16/64 KiB VDC bitmap lifetime. App supplies initial bitmap/attribute callbacks.
.weak
vd_storage_alloc=N_ALLOC
vd_storage_read=N_READ
vd_storage_write=N_WRITE
vd_storage_free=N_FREE
vd_storage_close=vd_success
.endweak
vd_open:
        jsr vd_gate
        lda #0
        sta vd_fault
        sta vd_phase
        sta vd_live
        sta vd_probe_live
        sta vd_pointer_visible
        sta vd_handle
        ldx #1
        jsr vd_getreg
        cmp #80
        bne vd_platform
        ldx #6
        jsr vd_getreg
        cmp #25
        bne vd_platform
        ldx #9
        jsr vd_getreg
        and #31
        cmp #7
        bne vd_platform
        ldx #8
        jsr vd_getreg
        and #3
        bne vd_platform
        ldx #22
        jsr vd_getreg
        cmp #$78
        bne vd_platform
        ldx #23
        jsr vd_getreg
        cmp #7               ; last displayed raster, inclusive; all eight must show
        bcc vd_platform
        ldx #25
        jsr vd_getreg
        bmi vd_platform
        lda #0
        sta vd_index
vd_save_registers:
        ldy vd_index
        ldx vd_registers,y
        jsr vd_getreg
        sta vd_saved,y
        inc vd_index
        lda vd_index
        cmp #vd_register_count
        bne vd_save_registers
        inc vd_phase           ; saved registers precede the first mutation
        jsr vd_blank
        lda vd_saved+11        ; R28: select linear 64K addressing for the probe
        ora #$10
        ldx #28
        jsr vd_setreg
        lda #0
        sta vd_addr
        sta vd_addr+1
        jsr vd_peek
        sta vd_probe_low
        inc vd_addr+1
        jsr vd_peek
        sta vd_probe_high
        inc vd_probe_live
        lda #$aa
        jsr vd_poke
        dec vd_addr+1
        lda #$55
        jsr vd_poke
        inc vd_addr+1
        jsr vd_peek
        cmp #$aa
        beq +
        cmp #$55
        bne vd_platform
        lda #0
        beq ++
+       lda #1
+       sta vd_color          ; 16K chips alias bit 8 in 64K addressing
        jsr vd_restore_probe
        lda #$40
        sta vd_pages
        lda #0
        sta vd_base
        lda vd_saved+11
        and #$ef
        ldx vd_color
        beq +
        ora #$10
        ldx #$48
        stx vd_pages
        ldx #$40
        stx vd_base
+       ldx #28
        jsr vd_setreg
        lda N_CURRENT
        sta N_OWNER
        lda #$ff
        sta N_BANK
        lda vd_pages
        sta N_PAGES
        jsr vd_storage_alloc
        bcs vd_fail
        ldx #3
-       lda N_HANDLE,x
        sta vd_handle,x
        dex
        bpl -
        jsr vd_transfer_start
vd_snapshot:
        lda #0                ; zero byte count means one complete 256-byte page
        sta vd_count
        jsr vd_read_block
        jsr vd_storage_write
        bcs vd_fail
        jsr vd_transfer_next
        bne vd_snapshot
        inc vd_phase          ; all bytes saved before the first bitmap write
        jsr vd_initial_bitmap
        lda #$20
        ldx #10
        jsr vd_setreg
        lda vd_base
        ldx #12
        jsr vd_setreg
        lda #0
        ldx #13
        jsr vd_setreg
        ldx #21
        jsr vd_setreg
        ldx #24
        jsr vd_setreg
        ldx #27
        jsr vd_setreg
        lda #$80
        ldx #20
        jsr vd_setreg
        jsr vd_initial_attributes
        lda #$f2
        ldx #26
        jsr vd_setreg
        lda #$87
        ldx vd_color
        beq +
        ora #$40
+       ldx #25
        jsr vd_setreg
        lda #1
        sta vd_live
        jmp vd_success
vd_platform:
        lda #N_PLATFORM
vd_fail:
        sta vd_fault
        ldx vd_stack
        txs
        sec
        rts
vd_success:
        lda #0
        clc
        rts
vd_gate:
        tsx
        inx
        inx                   ; remove this helper's own return address
        stx vd_stack
        lda #0
        sta N_READY
        rts

vd_close:
        jsr vd_gate
        lda #0
        sta vd_fault          ; retry the complete restore after a prior stall
        lda vd_phase
        beq vd_success
        jsr vd_blank
        jsr vd_restore_probe
        lda vd_phase
        cmp #2
        bcc vd_restore_registers
        lda vd_saved+11
        and #$ef
        ldx vd_color
        beq +
        ora #$10
+       ldx #28
        jsr vd_setreg
        jsr vd_transfer_start
vd_restore_memory:
        jsr vd_storage_read
        bcs vd_fail
        lda #0
        sta vd_count
        jsr vd_write_block
        jsr vd_transfer_next
        bne vd_restore_memory
vd_restore_registers:
        ; Addressing is restored after VRAM, display control after all other
        ; registers. R18/R19 are last so the saved update address is exact.
        lda #vd_register_count-1
        sta vd_index
-       ldy vd_index
        cpy #3
        beq +
        cpy #4
        beq +
        cpy #8
        beq +
        lda vd_saved,y
        ldx vd_registers,y
        jsr vd_setreg
+       dec vd_index
        bpl -
        lda vd_saved+8
        ldx #25
        jsr vd_setreg
        lda vd_saved+3
        ldx #18
        jsr vd_setreg
        lda vd_saved+4
        ldx #19
        jsr vd_setreg
        lda #0
        sta vd_live
        sta vd_pointer_visible
        lda vd_handle
        beq +
        jsr vd_select_handle
        jsr vd_storage_free
        bcs vd_fail
        lda #0
        sta vd_handle
+
 .if vd_storage_close != vd_success
        jsr vd_storage_close
        bcs vd_fail
 .endif
        lda #0
        sta vd_phase
        jmp vd_success
vd_blank:
        lda #$22              ; same foreground/background; no attribute reads
        ldx #26
        jsr vd_setreg
        lda #7
        ldx #25
        jmp vd_setreg
vd_restore_probe:
        lda vd_probe_live
        beq +
        lda vd_saved+11
        ora #$10
        ldx #28
        jsr vd_setreg
        lda #0
        sta vd_addr
        lda #1
        sta vd_addr+1
        lda vd_probe_high
        jsr vd_poke
        dec vd_addr+1
        lda vd_probe_low
        jsr vd_poke
        lda #0
        sta vd_probe_live
+       rts

vd_select_handle:
        lda N_CURRENT
        sta N_OWNER
        ldx #3
-       lda vd_handle,x
        sta N_HANDLE,x
        dex
        bpl -
        rts
vd_transfer_start:
        jsr vd_select_handle
        lda #0
        sta N_OFFSET
        sta N_OFFSET+1
        sta N_COUNT
        sta vd_addr
        lda #1
        sta N_COUNT+1
        lda vd_base
        sta vd_addr+1
        lda vd_pages
        sta vd_left
        rts
vd_transfer_next:
        inc N_OFFSET+1
        inc vd_addr+1
        dec vd_left
        rts

; Every selected register and every data byte uses a bounded ready handshake.
; No foreground scratch in zero page, no long interrupt-disabled section.
vd_wait:
        pha
        lda #0
        sta vd_wait_low
        sta vd_wait_high
-       bit $d600
        bmi +
        inc vd_wait_low
        bne -
        inc vd_wait_high
        bne -
        pla
        lda #N_IOERROR
        jmp vd_fail
+       pla
        rts
vd_getreg:
        stx $d600
        jsr vd_wait
        lda $d601
        rts
vd_setreg:
        stx $d600
        jsr vd_wait
        sta $d601
        rts
vd_seek:
        lda vd_addr+1
        ldx #18
        jsr vd_setreg
        lda vd_addr
        ldx #19
        jsr vd_setreg
        ldx #31
        stx $d600
        jmp vd_wait
vd_read_seek:
        jsr vd_seek
        jsr vd_getbyte         ; prime the real VDC read latch, then re-address
        jmp vd_seek
vd_getbyte:
        jsr vd_wait
        lda $d601
        rts
vd_putbyte:
        jsr vd_wait
        sta $d601
        rts
vd_peek:
        jsr vd_read_seek
        jmp vd_getbyte
vd_poke:
        pha
        jsr vd_seek
        pla
        jmp vd_putbyte
vd_read_block:
        jsr vd_read_seek
        ldy #0
-       jsr vd_getbyte
        sta N_BUFFER,y
        iny
        cpy vd_count
        bne -
        rts
vd_write_block:
        jsr vd_seek
        ldy #0
-       lda N_BUFFER,y
        jsr vd_putbyte
        iny
        cpy vd_count
        bne -
        rts
