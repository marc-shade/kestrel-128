; Native Ultimate DOS backend. No borrowed zero page, MMU changes or KERNAL
; channel changes. The shared fs lock and generation/owner records cover both
; IEC and Ultimate handles. Never replay a mutating command after uncertainty.
NU_COMMAND = $4bfc
NU_PAYLOAD = $4c00

nu_record:
        lda NFILES+1,x
        beq nu_bad_record
        lda NFILES+2,x
        cmp #3
        bcs nu_bad_record
        lda NFILES+3,x
        and #$f0
        bne nu_bad_record
        lda NFILES+4,x
        ora NFILES+5,x
        ora NFILES+6,x
        beq nu_bad_record
        lda NFILES+12,x         ; no IEC command-channel lease
        bne nu_bad_record
        lda NFILES+2,x
        cmp #2
        bne +
        jmp nd_record
+
        lda NFILES+3,x
        and #4
        bne nu_record_ok
        lda NFILES+2,x
        bne nu_record_write
        lda NFILES+3,x
        and #8
        beq nu_bad_record
        jsr nu_remaining
        beq nu_record_empty
        lda NFILES+3,x
        and #1
        bne nu_bad_record
        beq nu_record_ok
nu_record_empty:
        lda NFILES+3,x
        and #3
        beq nu_bad_record
        bne nu_record_ok
nu_record_write:
        lda NFILES+3,x
        and #9
        bne nu_bad_record
        jsr nu_remaining
        bne nu_bad_record
nu_record_ok:
        clc
        rts
nu_bad_record:
        jmp fs_corrupt
nu_remaining:
        lda NFILES+13,x
        ora NFILES+14,x
        ora NFILES+15,x
        ora nu_high,x
        rts

nu_open:
        jsr nd_guard
        bcc *+5
        jmp fs_finish
        lda N_FDEVICE
        beq nu_argument
        cmp #3
        bcs nu_argument
        sta f_device
        lda N_FMODE
        cmp #3
        bcs nu_argument
        cmp #2
        bne +
        lda nd_slot
        bne nu_context_busy
+
        lda N_FTYPE
        cmp #3
        bcs nu_argument
        lda N_FNAMELEN
        beq nu_argument
        lda N_UPATH
        cmp #$2f               ; always absolute; neither DOS CWD is changed
        bne nu_argument
        ldx #0
        stx nu_component
nu_path:
        lda N_UPATH,x
        beq nu_argument
        cmp #$2f
        beq nu_separator
        cmp #$5c
        beq nu_separator
        inc nu_component
        lda N_FMODE
        cmp #1
        bne nu_path_next
        lda nu_component
        bmi nu_argument        ; firmware create component buffer is 128 bytes
        bpl nu_path_next
nu_separator:
        lda #0
        sta nu_component
nu_path_next:
        inx
        cpx N_FNAMELEN
        bne nu_path
        ldx #0
nu_context_check:
        jsr fs_record
        bcc +
        jmp fs_finish
+       lda NFILES,x
        beq nu_context_next
        lda NFILES+1,x
        cmp f_device
        beq nu_context_busy
nu_context_next:
        txa
        eor #16
        tax
        bne nu_context_check
        jmp fs_open_find_slot
nu_argument:
        jmp fs_argument
nu_context_busy:
        lda #N_CHANNELS
        jmp fs_finish

nu_claim:
        lda #7                 ; FILE_INFO must explicitly say no open file
        jsr nu_two
        bcs nu_open_return
        cmp #85
        beq nu_claim_ready
        cmp #0
        beq nu_context_busy
        jmp nu_open_ioerror
nu_claim_ready:
        lda N_FMODE
        cmp #2
        bne nu_allocate
        jmp nd_prepare
nu_allocate:
        ldx f_slot
        inc NFILES+4,x
        bne +
        inc NFILES+5,x
        bne +
        inc NFILES+6,x
+       lda N_FOWNER
        sta NFILES,x
        lda f_device
        sta NFILES+1,x
        lda N_FMODE
        sta NFILES+2,x
        lda #0
        sta NFILES+7,x
        sta NFILES+8,x
        sta NFILES+9,x
        sta NFILES+10,x
        sta NFILES+11,x
        sta NFILES+12,x
        sta NFILES+13,x
        sta NFILES+14,x
        sta NFILES+15,x
        sta nu_high,x
        lda #4                 ; retain ownership before sending OPEN
        sta NFILES+3,x
        txa
        lsr
        lsr
        lsr
        lsr
        clc
        adc #1
        sta N_FHANDLE
        lda NFILES+4,x
        sta N_FHANDLE+1
        lda NFILES+5,x
        sta N_FHANDLE+2
        lda NFILES+6,x
        sta N_FHANDLE+3
        lda N_FMODE
        cmp #2
        bne +
        jmp nd_begin
+
        lda f_device
        sta NU_COMMAND
        lda #2
        sta NU_COMMAND+1
        lda N_FMODE
        beq +
        lda #6
+       ora #1                 ; read=1, exclusive create/read/write=7
        sta NU_COMMAND+2
        ldx #0
nu_name_copy:
        lda N_UPATH,x
        sta NU_COMMAND+3,x
        inx
        cpx N_FNAMELEN
        bne nu_name_copy
        clc
        txa
        adc #3
        sta nu_cmdlen
        lda #0
        adc #0
        sta nu_cmdlen+1
        jsr nu_full
        bcs nu_open_failed
        cmp #0
        bne nu_open_failed
        lda #7
        jsr nu_two
        bcs nu_open_failed
        cmp #0
        bne nu_open_failed
        lda nu_length+1
        bne nu_info
        lda nu_length
        cmp #12
        bcc nu_open_protocol
nu_info:
        lda N_BUFFER+11
        and #$18
        bne nu_open_protocol
        ldx f_slot
        lda #0
        sta NFILES+3,x
        lda NFILES+2,x
        bne nu_open_ok
        lda N_BUFFER
        sta NFILES+13,x
        lda N_BUFFER+1
        sta NFILES+14,x
        lda N_BUFFER+2
        sta NFILES+15,x
        lda N_BUFFER+3
        sta nu_high,x
        lda #8
        sta NFILES+3,x
        jsr nu_eof
nu_open_ok:
        jsr fs_snapshot
        lda #0
        jmp fs_finish
nu_open_protocol:
        lda #$fc
        sta N_FSTATUS
nu_open_failed:
        ; Even a plain-text OPEN rejection may leave ownership ambiguous.
        ; Only a checked CLOSE (or 84) releases this context.
        lda #N_IOERROR
        ldx f_slot
        sta NFILES+7,x
        jmp fs_finish
nu_open_ioerror:
        lda #N_IOERROR
nu_open_return:
        jmp fs_finish

nu_transfer:
        jsr nd_guard
        bcc *+5
        jmp fs_finish
        lda N_FCOUNT
        sta nu_expected
        lda N_FCOUNT+1
        sta nu_expected+1
        lda f_operation
        bne nu_write
        lda nu_high,x
        ora NFILES+15,x
        bne nu_read
        lda NFILES+14,x
        cmp nu_expected+1
        bcc nu_clip
        bne nu_read
        lda NFILES+13,x
        cmp nu_expected
        bcs nu_read
nu_clip:
        lda NFILES+13,x
        sta nu_expected
        lda NFILES+14,x
        sta nu_expected+1
nu_read:
        jsr nu_read_block
        bcs nu_transfer_failed
        ldx f_slot
        sec
        lda NFILES+13,x
        sbc nu_expected
        sta NFILES+13,x
        lda NFILES+14,x
        sbc nu_expected+1
        sta NFILES+14,x
        lda NFILES+15,x
        sbc #0
        sta NFILES+15,x
        lda nu_high,x
        sbc #0
        sta nu_high,x
        jsr nu_eof
        jmp nu_advance
nu_eof:
        jsr nu_remaining
        bne +
        lda NFILES+3,x
        ora #1
        sta NFILES+3,x
+       rts
nu_write:
        ; Keep the original bytes outside N_BUFFER for a full READ comparison.
        ldx #0
nu_write_copy:
        lda N_BUFFER,x
        sta NU_PAYLOAD,x
        lda N_BUFFER+256,x
        sta NU_PAYLOAD+256,x
        inx
        bne nu_write_copy
        lda f_device
        sta NU_COMMAND
        lda #5
        sta NU_COMMAND+1
        lda #0
        sta NU_COMMAND+2
        sta NU_COMMAND+3
        clc
        lda nu_expected
        adc #4
        sta nu_cmdlen
        lda nu_expected+1
        adc #0
        sta nu_cmdlen+1
        lda nu_expected+1
        cmp #2
        bne +
        dec nu_cmdlen          ; 512 => 511 + 1: verified physical USB workaround
+       jsr nu_full
        bcs nu_transfer_failed
        cmp #0
        bne nu_transfer_failed
        lda nu_expected+1
        cmp #2
        bne nu_verify
        lda #5
        sta nu_short+1
        lda #0
        sta nu_short+2
        sta nu_short+3
        lda NU_PAYLOAD+511
        sta nu_short+4
        lda #5
        jsr nu_short_send
        bcs nu_transfer_failed
        cmp #0
        bne nu_transfer_failed
nu_verify:
        ldx f_slot
        ldy #0
nu_seek_copy:
        lda NFILES+8,x
        sta nu_short+2,y
        inx
        iny
        cpy #4
        bne nu_seek_copy
        lda #6
        sta nu_short+1
        jsr nu_short_send
        bcs nu_transfer_failed
        cmp #0
        bne nu_transfer_failed
        jsr nu_read_block
        bcs nu_transfer_failed
        ldx #0
nu_compare:
        lda nu_expected+1
        cmp #2
        beq nu_compare_both
        cmp #1
        beq nu_compare_page
        cpx nu_expected
        bcs nu_advance
nu_compare_page:
        lda N_BUFFER,x
        cmp NU_PAYLOAD,x
        bne nu_verify_failed
        lda nu_expected+1
        beq nu_compare_next
        cpx nu_expected
        bcs nu_compare_next
        bcc nu_compare_high
nu_compare_both:
        lda N_BUFFER,x
        cmp NU_PAYLOAD,x
        bne nu_verify_failed
nu_compare_high:
        lda N_BUFFER+256,x
        cmp NU_PAYLOAD+256,x
        bne nu_verify_failed
nu_compare_next:
        inx
        bne nu_compare
nu_advance:
        ldx f_slot
        clc
        lda NFILES+8,x
        adc nu_expected
        sta NFILES+8,x
        lda NFILES+9,x
        adc nu_expected+1
        sta NFILES+9,x
        lda NFILES+10,x
        adc #0
        sta NFILES+10,x
        lda NFILES+11,x
        adc #0
        sta NFILES+11,x
        lda nu_expected
        sta N_FACTUAL
        lda nu_expected+1
        sta N_FACTUAL+1
        jsr fs_snapshot
        lda #0
        jmp fs_finish
nu_verify_failed:
        lda #$e6
        sta N_FSTATUS
nu_transfer_failed:
        ldx f_slot
        lda NFILES+3,x
        ora #6
        sta NFILES+3,x
        lda #N_IOERROR
        sta NFILES+7,x
        jsr fs_snapshot
        lda #N_IOERROR
        jmp fs_finish
nu_read_block:
        lda #4
        sta nu_short+1
        lda nu_expected
        sta nu_short+2
        lda nu_expected+1
        sta nu_short+3
        lda #4
        jsr nu_short_send
        bcs nu_read_done
        cmp #0
        beq nu_read_count
        cmp #$ff
        bne nu_read_bad
        lda N_USTATUS          ; empty status is valid only for exact READ
        bne nu_read_bad
nu_read_count:
        lda nu_length
        cmp nu_expected
        bne nu_short_read
        lda nu_length+1
        cmp nu_expected+1
        bne nu_short_read
        lda #0
        clc
nu_read_done:
        rts
nu_short_read:
        lda #$e5
        sta N_FSTATUS
nu_read_bad:
        sec
        rts

nu_close:
        lda NFILES+2,x
        cmp #2
        bne +
        jmp nd_close
+       jsr nd_guard
        bcc *+3
        rts
        lda NFILES+1,x
        sta f_device
        lda #3
        jsr nu_two
        bcs nu_close_failed
        cmp #0
        beq nu_close_ok
        cmp #84
        bne nu_close_failed
nu_close_ok:
        jsr fs_snapshot
        ldx f_slot
        lda #0
        sta NFILES,x
        clc
        rts
nu_close_failed:
        ldx f_slot
        lda NFILES+3,x
        ora #4
        sta NFILES+3,x
        lda #N_IOERROR
        sta NFILES+7,x
        sec
        rts

nu_two:
        sta nu_short+1
        lda #2
nu_short_send:
        sta nu_cmdlen
        lda #0
        sta nu_cmdlen+1
        sta nu_packet_mode
        lda f_device
        sta nu_short
        lda #<nu_short
        ldx #>nu_short
        jmp nu_send
nu_full:
        lda #0
        sta nu_packet_mode
        lda #<NU_COMMAND
        ldx #>NU_COMMAND
nu_send:
        sta nu_command_byte+1
        stx nu_command_byte+2
        jsr nu_reply_init
        lda $df1d
        cmp #$c9
        bne nu_absent
        lda $df1d
        cmp #$c9
        bne nu_absent
        lda $df1c
        and #$3f
        bne nu_foreign         ; never abort another client's transaction
        lda nu_cmdlen+1
        cmp #3
        bcs nu_bad_command
        ora nu_cmdlen
        beq nu_bad_command
nu_command_byte:
        lda $ffff
        sta $df1d
        inc nu_command_byte+1
        bne +
        inc nu_command_byte+2
+       lda nu_cmdlen
        bne +
        dec nu_cmdlen+1
+       dec nu_cmdlen
        lda nu_cmdlen
        ora nu_cmdlen+1
        bne nu_command_byte
        lda nu_packet_mode
        beq +
        sta nd_active          ; claim the transaction before triggering it
+
        lda #1
        sta $df1c
        lda $df1c
        and #8
        bne nu_timeout
nu_wait:
        jsr nu_timer_init
nu_wait_loop:
        lda $df1c
        and #$30
        cmp #$10
        bne nu_packet
        jsr nu_tick
        bcc nu_wait_loop
        bcs nu_timeout
nu_packet:
        cmp #0
        beq nu_complete
        sta nu_part_state
        lda #0
        sta nu_statlen
        jsr nu_timer_init
nu_data:
        lda $df1c
        and #$80
        beq nu_status
        lda nu_length+1
        cmp #2
        bcs nu_protocol
        lda nu_length
        sta nu_data_store+1
        lda nu_length+1
        clc
        adc #>N_BUFFER
        sta nu_data_store+2
        lda $df1e
nu_data_store:
        sta N_BUFFER
        inc nu_length
        bne +
        inc nu_length+1
+       jsr nu_tick
        bcc nu_data
        bcs nu_timeout
nu_status:
        lda $df1c
        and #$40
        beq nu_status_end
        lda $df1f
        ldx nu_locked
        bne nu_status_tick
        ldx nu_statlen
        cpx #31
        bcs nu_protocol
        sta N_USTATUS,x
        inx
        stx nu_statlen
        lda #0
        sta N_USTATUS,x
nu_status_tick:
        jsr nu_tick
        bcc nu_status
        bcs nu_timeout
nu_status_end:
        lda nu_statlen
        beq nu_ack
        lda nu_locked
        bne nu_ack
        jsr nu_parse
        sta nu_code
        cmp #0
        beq nu_ack
        inc nu_locked
nu_ack:
        inc nu_packets
        bne +
        inc nu_packets+1
        beq nu_timeout
+       lda #2
        sta $df1c
        jsr nu_timer_init
nu_ack_wait:
        lda $df1c
        and #2
        bne nu_ack_tick
        lda nu_packet_mode
        beq nu_wait
        lda nu_part_state
        cmp #$30
        bne nu_wait             ; the final packet must reach idle first
        beq nu_complete         ; return one directory entry, with more pending
nu_ack_tick:
        jsr nu_tick
        bcc nu_ack_wait
        bcs nu_timeout
nu_complete:
        lda nu_code
        sta N_FDOS
        clc
        rts
nu_reply_init:
        lda #0
        sta nu_length
        sta nu_length+1
        sta nu_locked
        sta N_USTATUS
        sta nu_packets
        sta nu_packets+1
        sta nu_part_state
        lda #$ff
        sta nu_code
        rts
nu_parse:
        lda N_USTATUS
        sec
        sbc #$30
        cmp #10
        bcs nu_parse_bad
        asl
        sta nu_digit
        asl
        asl
        clc
        adc nu_digit
        sta nu_digit
        lda N_USTATUS+1
        sec
        sbc #$30
        cmp #10
        bcs nu_parse_bad
        clc
        adc nu_digit
        rts
nu_parse_bad:
        lda #$ff
        rts
nu_absent:
        lda #$fe
        bne nu_transport_error
nu_foreign:
        lda #$e2
        sta N_FSTATUS
        lda #N_CHANNELS
        sec
        rts
nu_bad_command:
        lda #$fc
        bne nu_transport_error
nu_protocol:
        lda #$fc
        bne nu_abort
nu_timeout:
        lda #$ff
nu_abort:
        pha
        lda #4
        sta $df1c
        ; This abort belongs to the command submitted above. Give firmware
        ; a bounded interval to finish it before callers attempt cleanup.
        ; Preserve the initiating error and never replay the command/abort.
        jsr nu_timer_init
nu_abort_wait:
        lda $df1c
        and #$3f
        beq nu_abort_return
        jsr nu_tick
        bcc nu_abort_wait
nu_abort_return:
        pla
nu_transport_error:
        sta N_FSTATUS
        lda #N_IOERROR
        sec
        rts
nu_timer_init:
        lda #0
        sta nu_tmo
        sta nu_tmo+1
        lda #5
        sta nu_tmo+2
        rts
nu_tick:
        dec nu_tmo
        bne +
        dec nu_tmo+1
        bne +
        dec nu_tmo+2
        beq nu_tick_expired
+       clc
        rts
nu_tick_expired:
        sec
        rts

nu_high:       .fill 17,0       ; fourth remaining byte, indexed by descriptor 0/16
nu_component:  .byte 0
nu_short:      .fill 6,0
nu_cmdlen:     .word 0
nu_expected:   .word 0
nu_length:     .word 0
nu_packets:    .word 0
nu_statlen:    .byte 0
nu_locked:     .byte 0
nu_code:       .byte 0
nu_digit:      .byte 0
nu_tmo:        .fill 3,0
nu_packet_mode:.byte 0          ; 1 returns a single directory reply packet
nu_part_state: .byte 0
nu_code_end:
.include "modules.inc"
.include "module-validate.inc"
native_module_code_end:
.include "display-show.inc"
.include "keyboard-input.inc"
        .cerror * > N_BROWSERPATH, "native Ultimate code overlaps browser path"
* = N_BROWSERPATH
        .byte $2f
        .fill 255,0
.include "ultimate-query.inc"
native_query_end:
        .include "ultimate-command.inc"
        .include "keyboard.inc"
        .cerror * > NU_COMMAND, "native Ultimate queries overlap command buffer"
* = NU_COMMAND
        .fill $204,0
* = N_UPATH
        .fill 256,0
* = N_USTATUS
        .fill 32,0
