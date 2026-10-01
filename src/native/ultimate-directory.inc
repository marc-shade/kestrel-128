; Owned Ultimate directory cursor, GPL v3. FMODE=2 shares a file descriptor.
; One cursor reserves its DOS context until checked CLOSE restores the CWD.
; READ_DIR holds the shared UCI transport between individual entry packets.
; An idle external directory snapshot cannot be queried by this firmware;
; opening a native cursor claims that context's directory snapshot for Kestrel.

nd_guard:
        lda nd_active
        beq nd_idle
        lda #N_CHANNELS
        sec
        rts
nd_idle:
        clc
        rts

nd_record:
        txa
        lsr
        lsr
        lsr
        lsr
        clc
        adc #1
        cmp nd_slot
        bne nd_corrupt
        lda nd_length
        beq nd_corrupt
        lda nd_active
        cmp #2
        bcs nd_corrupt
        lda NFILES+3,x
        and #8
        bne nd_corrupt
        jsr nu_remaining
        bne nd_corrupt
        lda NFILES+3,x
        and #1
        beq nd_idle
        lda nd_active
        beq nd_idle
nd_corrupt:
        jmp fs_corrupt

; Read and validate the original path before claiming a descriptor or changing
; the device. GET_PATH has no terminator; 256-byte paths cannot fit this ABI.
nd_prepare:
        lda #$12
        jsr nu_two
        bcs nd_prepare_failed
        cmp #0
        bne nd_prepare_io
        lda nu_length+1
        bne nd_prepare_protocol
        lda nu_length
        beq nd_prepare_protocol
        sta nd_length
        lda N_BUFFER
        cmp #$2f
        bne nd_prepare_protocol
        ldx #0
nd_save_path:
        lda N_BUFFER,x
        beq nd_prepare_protocol
        sta nd_path,x
        inx
        cpx nd_length
        bne nd_save_path
        jmp nu_allocate
nd_prepare_protocol:
        lda #$fc
        sta N_FSTATUS
nd_prepare_io:
        lda #N_IOERROR
nd_prepare_failed:
        jmp fs_finish

nd_begin:
        lda N_FHANDLE
        sta nd_slot
        lda #0
        sta nd_active
        lda N_FNAMELEN
        ldx #<N_UPATH
        ldy #>N_UPATH
        jsr nd_change
        bcs nd_open_failed
        cmp #0
        bne nd_open_failed
        lda #$12
        jsr nu_two
        bcs nd_open_failed
        cmp #0
        bne nd_open_failed
        lda nu_length+1
        bne nd_open_protocol
        lda nu_length
        beq nd_open_protocol
        sta N_FNAMELEN
        lda N_BUFFER
        cmp #$2f
        bne nd_open_protocol
        ldx #0
nd_canonical_path:
        lda N_BUFFER,x
        beq nd_open_protocol
        sta N_UPATH,x
        inx
        cpx N_FNAMELEN
        bne nd_canonical_path
        lda #$13
        jsr nu_two
        bcs nd_open_failed
        cmp #2                  ; 00 snapshot ready, 01 empty directory
        bcs nd_open_failed
        ldx f_slot
        sta NFILES+3,x
        jsr fs_snapshot
        lda #0
        jmp fs_finish
nd_open_protocol:
        lda #$fc
        sta N_FSTATUS
nd_open_failed:
        jmp nu_open_failed      ; retain the owner until CWD restoration succeeds

; Construct CHANGE_DIR with exact raw bytes, not a zero-terminated field.
nd_change:
        sta nd_transfer_length
        stx nd_path_byte+1
        sty nd_path_byte+2
        lda f_device
        sta NU_COMMAND
        lda #$11
        sta NU_COMMAND+1
        ldx #0
nd_path_byte:
        lda $ffff,x
        sta NU_COMMAND+2,x
        inx
        cpx nd_transfer_length
        bne nd_path_byte
        clc
        txa
        adc #2
        sta nu_cmdlen
        lda #0
        adc #0
        sta nu_cmdlen+1
        jmp nu_full

; FCOUNT must be 512. Return one [attribute, complete raw name] packet,
; 2..256 bytes; POSITION counts entries. EOF never releases the cursor.
nd_read:
        lda f_operation
        bne nd_argument
        lda N_FCOUNT
        bne nd_range
        lda N_FCOUNT+1
        cmp #2
        bne nd_range
        lda NFILES+3,x
        and #6
        beq nd_read_clean
        lda NFILES+7,x
        bne nd_read_return
        lda #N_IOERROR
        bne nd_read_return
nd_argument:
        jmp fs_argument
nd_range:
        jmp fs_transfer_range
nd_read_return:
        jmp fs_finish
nd_read_clean:
        lda NFILES+3,x
        and #1
        bne nd_publish_empty
        lda NFILES+8,x
        and NFILES+9,x
        and NFILES+10,x
        and NFILES+11,x
        cmp #$ff
        beq nd_range
        lda NFILES+1,x
        sta f_device
        lda #1
        sta nu_packet_mode
        lda nd_active
        bne nd_continue
        lda f_device
        sta nu_short
        lda #$14
        sta nu_short+1
        lda #2
        sta nu_cmdlen
        lda #0
        sta nu_cmdlen+1
        lda #<nu_short
        ldx #>nu_short
        jsr nu_send
        jmp nd_received
nd_continue:
        lda $df1d
        cmp #$c9
        bne nd_read_absent
        lda $df1d
        cmp #$c9
        bne nd_read_absent
        jsr nu_reply_init
        jsr nu_wait
nd_received:
        bcc nd_validate
        cmp #N_CHANNELS
        beq nd_read_return      ; no command was issued; do not poison the cursor
        bne nd_read_failed
nd_read_absent:
        lda #$fe
        sta N_FSTATUS
        bne nd_read_io
nd_validate:
        lda nu_part_state
        cmp #$20
        beq nd_final_status
        cmp #$30
        bne nd_read_protocol
        lda N_USTATUS
        bne nd_read_io
        beq nd_packet_size
nd_final_status:
        lda nu_code
        bne nd_read_io
        lda #0
        sta nd_active          ; final packet ACK has reached transport idle
nd_packet_size:
        lda nu_length+1
        beq nd_packet_low
        cmp #1
        bne nd_read_protocol
        lda nu_length
        bne nd_read_protocol
        beq nd_packet_name
nd_packet_low:
        lda nu_length
        cmp #2
        bcc nd_read_protocol
nd_packet_name:
        ldx #1
nd_name_byte:
        lda N_BUFFER,x
        beq nd_read_protocol
        cmp #$2f
        beq nd_read_protocol
        cmp #$5c
        beq nd_read_protocol
        inx
        cpx nu_length
        bne nd_name_byte
        ldx f_slot
        inc NFILES+8,x
        bne nd_position_ready
        inc NFILES+9,x
        bne nd_position_ready
        inc NFILES+10,x
        bne nd_position_ready
        inc NFILES+11,x
nd_position_ready:
        lda nu_length
        sta N_FACTUAL
        lda nu_length+1
        sta N_FACTUAL+1
        lda nu_part_state
        cmp #$20
        bne nd_publish_empty
        lda #1
        sta NFILES+3,x
nd_publish_empty:
        jsr fs_snapshot
        lda #0
        jmp fs_finish
nd_read_protocol:
        lda #$fc
        sta N_FSTATUS
nd_read_io:
        lda #N_IOERROR
nd_read_failed:
        ldx f_slot
        sta NFILES+7,x
        pha
        lda NFILES+3,x
        ora #6
        sta NFILES+3,x
        pla
        jmp fs_finish

nd_close:
        lda NFILES+1,x
        sta f_device
        jsr nd_cancel
        bcs nd_close_failed
        lda nd_length
        ldx #<nd_path
        ldy #>nd_path
        jsr nd_change
        bcs nd_close_failed
        cmp #0
        bne nd_close_io
        lda #$12
        jsr nu_two
        bcs nd_close_failed
        cmp #0
        bne nd_close_io
        lda nu_length+1
        bne nd_close_protocol
        lda nu_length
        cmp nd_length
        bne nd_close_protocol
        ldx #0
nd_restored_byte:
        lda N_BUFFER,x
        cmp nd_path,x
        bne nd_close_protocol
        inx
        cpx nd_length
        bne nd_restored_byte
        jsr fs_snapshot
        ldx f_slot
        lda #0
        sta NFILES,x
        sta nd_slot
        clc
        rts
nd_close_protocol:
        lda #$fc
        sta N_FSTATUS
nd_close_io:
        lda #N_IOERROR
nd_close_failed:
        ldx f_slot
        sta NFILES+7,x
        pha
        lda NFILES+3,x
        ora #4
        sta NFILES+3,x
        pla
        sec
        rts

; Cancellation is only for this cursor's active transaction. Never clear the
; lease on an unobserved abort; another CLOSE may retry checked cleanup.
nd_cancel:
        lda nd_active
        beq nd_idle
        lda $df1d
        cmp #$c9
        bne nd_cancel_absent
        lda $df1d
        cmp #$c9
        bne nd_cancel_absent
        lda $df1c
        and #$3f
        beq nd_cancel_done
        lda #4
        sta $df1c
        jsr nu_timer_init
nd_cancel_wait:
        lda $df1c
        and #$3f
        beq nd_cancel_done
        jsr nu_tick
        bcc nd_cancel_wait
        lda #$ff
        bne nd_cancel_error
nd_cancel_absent:
        lda #$fe
nd_cancel_error:
        sta N_FSTATUS
        lda #N_IOERROR
        sec
        rts
nd_cancel_done:
        lda #0
        sta nd_active
        clc
        rts

nd_release:
        lda nd_slot
        beq nd_idle
        cmp #3
        bcs nd_corrupt
        sec
        sbc #1
        asl
        asl
        asl
        asl
        tax
        lda NFILES,x
        cmp N_FOWNER
        bne nd_release_other
        stx f_slot
        jmp nd_close
nd_release_other:
        lda #0
        clc
        rts

nd_slot: .byte 0
nd_active: .byte 0
nd_length: .byte 0
nd_transfer_length: .byte 0
nd_path: .fill 256,0
