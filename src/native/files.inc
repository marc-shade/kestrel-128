; Native owned IEC/Ultimate streams, GPL v3. Foreground only; no CLALL/replacement.
FS_LFN = 122                    ; slots use 122/123 and secondary 8/9
FS_CMD = 124                    ; 124/125, one shared command channel per device
FS_META = 126                   ; temporary direct-access channel, secondary 10

fs_enter:
        lda N_FBUSY
        ora N_BUSY
        bne fs_enter_busy
        tsx
        lda $0103,x             ; caller's PHP, below this JSR return address
        and #4
        bne fs_enter_platform
        cld
        jsr heap_stats
        bcs fs_enter_done
        lda N_FOWNER
        beq fs_enter_argument
        cmp #$ff
        beq fs_enter_argument
        lda $99
        bne fs_enter_channels
        lda $9a
        cmp #3
        bne fs_enter_channels
        lda #1
        sta N_FBUSY
        lda #0
        sta N_READY
        sta N_FACTUAL
        sta N_FACTUAL+1
        sta N_FEOF
        sta N_FDOS
        sta N_FSTATUS
        sta f_result
        sta f_cmd
        sta f_io
        sta f_uncertain
        clc
fs_enter_done:
        rts
fs_enter_busy:
        lda #N_REENTRANT
        sec
        rts
fs_enter_platform:
        lda #N_PLATFORM
        sec
        rts
fs_enter_argument:
        lda #N_BADARG
        sec
        rts
fs_enter_channels:
        lda #N_CHANNELS
        sec
        rts
fs_enter_failed:
        cmp #N_REENTRANT
        beq fs_nested
        sta N_FERROR
fs_nested:
        plp
        sec
        rts
fs_finish:
        sta N_FERROR
        ldx #0
        stx N_FBUSY
        plp
        cmp #1
        rts
fs_argument:
        lda #N_BADARG
        jmp fs_finish
fs_channels:
        lda #N_CHANNELS
        sec
        rts
fs_corrupt:
        lda #N_CORRUPT
        sec
        rts

; Validate descriptor at X. Free/retired records have no live resources.
fs_record:
        lda NFILES,x
        bne fs_record_live
        clc
        rts
fs_record_live:
        cmp #$ff
        beq fs_corrupt
        lda NFILES+1,x
        cmp #3
        bcs +
        jmp nu_record
+
        cmp #8
        bcc fs_corrupt
        cmp #31
        bcs fs_corrupt
        lda NFILES+2,x
        cmp #3
        bcs fs_corrupt
        cmp #2
        bne fs_record_flags
        lda NFILES+3,x
        and #4                 ; directory operations only retain uncertain cleanup
        beq fs_corrupt
fs_record_flags:
        lda NFILES+3,x
        and #$f0
        bne fs_corrupt
        lda NFILES+4,x
        ora NFILES+5,x
        ora NFILES+6,x
        beq fs_corrupt
        lda NFILES+12,x
        beq fs_corrupt
        cmp #3
        bcs fs_corrupt
        lda NFILES+3,x
        and #4
        bne fs_record_ok
        lda NFILES+2,x
        bne fs_record_write
        lda NFILES+3,x
        and #8
        beq fs_corrupt
        lda NFILES+13,x
        ora NFILES+14,x
        ora NFILES+15,x
        beq fs_record_empty
        lda NFILES+3,x
        and #1
        bne fs_corrupt
        beq fs_record_command
fs_record_empty:
        lda NFILES+3,x
        and #3                 ; finished, or poisoned during final EOI check
        beq fs_corrupt
        bne fs_record_command
fs_record_write:
        lda NFILES+3,x
        and #9
        bne fs_corrupt
        lda NFILES+13,x
        ora NFILES+14,x
        ora NFILES+15,x
        bne fs_record_bad
fs_record_command:
        lda NFILES+12,x
        tay
        dey
        lda NFCMDS,y
        cmp NFILES+1,x
        bne fs_record_bad
        lda NFCMDS+2,y
        cmp #1
        bne fs_record_bad
fs_record_ok:
        clc
        rts
fs_record_bad:
        jmp fs_corrupt
fs_handle:
        lda N_FHANDLE
        beq fs_bad_handle
        cmp #3
        bcs fs_bad_handle
        sec
        sbc #1
        asl
        asl
        asl
        asl
        tax
        stx f_slot
        jsr fs_record
        bcs fs_handle_done
        lda NFILES,x
        beq fs_bad_handle
        lda NFILES+4,x
        cmp N_FHANDLE+1
        bne fs_bad_handle
        lda NFILES+5,x
        cmp N_FHANDLE+2
        bne fs_bad_handle
        lda NFILES+6,x
        cmp N_FHANDLE+3
        bne fs_bad_handle
        lda NFILES,x
        cmp N_FOWNER
        bne fs_wrong_owner
        clc
fs_handle_done:
        rts
fs_bad_handle:
        lda #N_BADHANDLE
        sec
        rts
fs_wrong_owner:
        lda #N_WRONGOWNER
        sec
        rts

fs_slot_channels:
        lda f_slot
        lsr
        lsr
        lsr
        lsr
        clc
        adc #FS_LFN
        sta f_lfn
        sec
        sbc #FS_LFN-8
        sta f_sa
        rts

; Check the complete KERNAL table before any serial operation. f_expect=0
; requires an unused data channel; 1 requires exactly our LFN/device/SA.
fs_guard:
        jsr fs_slot_channels
        lda #0
        sta f_found
        sta f_command_found
        ldx #0
fs_command_find:
        lda NFCMDS,x
        cmp f_device
        beq fs_command_found_slot
        inx
        cpx #2
        bne fs_command_find
        ldx #0
fs_command_empty:
        lda NFCMDS,x
        beq fs_command_found_slot
        inx
        cpx #2
        bne fs_command_empty
        jmp fs_channels
fs_command_found_slot:
        stx f_cslot
        txa
        clc
        adc #FS_CMD
        sta f_clfn
        lda NFCMDS+2,x
        cmp #2
        bcc fs_command_usable
        lda #N_IOERROR
        sec
        rts
fs_command_usable:
        lda #1
        sec
        sbc f_expect
        sta f_extra              ; new data LFN only for OPEN
        lda NFCMDS,x
        beq fs_command_extra
        lda #1
        bne fs_command_expected
fs_command_extra:
        inc f_extra
        lda #0
fs_command_expected:
        sta f_command_expect
        lda $98
        cmp #11
        bcc *+5
        jmp fs_guard_bad
        clc
        adc f_extra
        cmp #11
        bcc *+5
        jmp fs_guard_bad
        ldx $98
        dex
        bpl *+5
        jmp fs_guard_end
fs_guard_loop:
        ; Metadata uses a temporary LFN before opening a read stream.
        lda f_expect
        bne fs_guard_command
        lda N_FMODE
        cmp #1
        beq fs_guard_command
        lda $0362,x
        cmp #FS_META
        bne fs_guard_command
        jmp fs_guard_bad
fs_guard_command:
        lda $0362,x
        cmp f_clfn
        bne fs_guard_data
        lda $036c,x
        cmp f_device
        bne fs_guard_bad
        lda $0376,x
        and #15
        cmp #15
        bne fs_guard_bad
        inc f_command_found
        bne fs_guard_next
fs_guard_data:
        lda $0362,x
        cmp f_lfn
        bne fs_guard_device
        inc f_found
        lda $036c,x
        cmp f_device
        bne fs_guard_bad
        lda $0376,x
        and #15
        cmp f_sa
        bne fs_guard_bad
        beq fs_guard_next
fs_guard_device:
        lda $036c,x
        cmp f_device
        bne fs_guard_next
        ; Only the other owned stream may share this drive. Never close a
        ; command channel around foreign raw KERNAL files on the same device.
        lda f_slot
        eor #16
        tay
        lda NFILES,y
        beq fs_guard_bad
        lda NFILES+1,y
        cmp f_device
        bne fs_guard_bad
        tya
        lsr
        lsr
        lsr
        lsr
        clc
        adc #FS_LFN
        cmp $0362,x
        bne fs_guard_bad
        sec
        sbc #FS_LFN-8
        sta f_other_sa
        lda $0376,x
        and #15
        cmp f_other_sa
        bne fs_guard_bad
fs_guard_next:
        dex
        bmi *+5
        jmp fs_guard_loop
fs_guard_end:
        lda f_found
        cmp f_expect
        bne fs_guard_bad
        lda f_command_found
        cmp f_command_expect
        bne fs_guard_bad
        clc
        rts
fs_guard_bad:
        jmp fs_channels

fs_dirpage:
        php
        jsr fs_enter
        bcc *+5
        jmp fs_enter_failed
        lda N_FFORMAT
        cmp #3
        bcs fs_argument        ; this older page API remains IEC-only
        lda #2
        sta N_FMODE
        jmp fs_open_arguments
fs_open:
        php
        jsr fs_enter
        bcc *+5
        jmp fs_enter_failed
fs_open_arguments:
        lda N_FFORMAT
        cmp #3
        bne +
        jmp nu_open
+
        lda N_FDEVICE
        cmp #8
        bcs *+5
        jmp fs_argument
        cmp #31
        bcc *+5
        jmp fs_argument
        sta f_device
        lda N_FFORMAT
        cmp #3
        bcc *+5
        jmp fs_argument
        lda N_FMODE
        cmp #3
        bcc *+5
        jmp fs_argument
        cmp #2
        bne fs_open_file
        ldx N_FFORMAT
        lda N_DPAGE
        cmp f_mdirs,x
        bcc *+5
        jmp fs_argument
        lda #0
        sta N_DCOUNT
        lda #$ff
        sta N_DNEXT
        jmp fs_open_find_slot
fs_open_file:
        lda N_FTYPE
        cmp #3
        bcc *+5
        jmp fs_argument
        lda N_FNAMELEN
        beq fs_open_argument
        cmp #17
        bcs fs_open_argument
        ldx #0
fs_name:
        lda N_FNAME,x
        cmp #$20
        bcc fs_open_argument
        cmp #$7f
        bcs fs_open_argument
        cmp #$2a
        beq fs_open_argument
        cmp #$3f
        beq fs_open_argument
        cmp #$2c
        beq fs_open_argument
        cmp #$3a
        beq fs_open_argument
        cmp #$2f
        beq fs_open_argument
        cmp #$5c
        beq fs_open_argument
        cmp #$40                 ; no replace prefix
        beq fs_open_argument
        cmp #$23                 ; no direct buffer or directory syntax
        beq fs_open_argument
        cmp #$24
        beq fs_open_argument
        sta f_filename,x
        inx
        cpx N_FNAMELEN
        bne fs_name
        lda #$2c
        sta f_filename,x
        inx
        ldy N_FTYPE
        lda f_types,y
        sta f_filename,x
        inx
        lda #$2c
        sta f_filename,x
        inx
        ldy N_FMODE
        lda f_modes,y
        sta f_filename,x
        inx
        stx f_namelen
fs_open_find_slot:
        ldx #0
        beq fs_open_slot
fs_open_argument:
        jmp fs_argument
fs_open_slot:
        jsr fs_record
        bcc *+5
        jmp fs_finish
        lda NFILES,x
        bne fs_open_next
        lda NFILES+4,x
        and NFILES+5,x
        and NFILES+6,x
        cmp #$ff
        bne fs_open_available
fs_open_next:
        txa
        clc
        adc #16
        tax
        cpx #32
        bne fs_open_slot
        lda #N_NOSLOT
        jmp fs_finish
fs_open_available:
        stx f_slot
        lda f_device
        cmp #3
        bcs +
        jmp nu_claim
+
        lda #0
        sta f_expect
        lda #2
        sta f_extra
        jsr fs_guard
        bcc *+5
        jmp fs_finish
        ldx f_slot
        inc NFILES+4,x
        bne fs_generation
        inc NFILES+5,x
        bne fs_generation
        inc NFILES+6,x
fs_generation:
        lda N_FOWNER
        sta NFILES,x
        lda f_device
        sta NFILES+1,x
        lda N_FMODE
        sta NFILES+2,x
        lda #0
        sta NFILES+3,x
        sta NFILES+7,x
        sta NFILES+8,x
        sta NFILES+9,x
        sta NFILES+10,x
        sta NFILES+11,x
        sta NFILES+13,x
        sta NFILES+14,x
        sta NFILES+15,x
        lda f_cslot
        clc
        adc #1
        sta NFILES+12,x
        lda f_lfn
        sec
        sbc #FS_LFN-1
        sta N_FHANDLE
        lda NFILES+4,x
        sta N_FHANDLE+1
        lda NFILES+5,x
        sta N_FHANDLE+2
        lda NFILES+6,x
        sta N_FHANDLE+3
        lda #0
        sta f_data
        jsr fs_begin_io
        jsr fs_command
        bcs fs_open_error
        lda N_FMODE
        cmp #1
        beq fs_open_data
        jsr fs_metadata
        bcs fs_open_error
        lda N_FMODE
        cmp #2
        beq fs_open_end
fs_open_data:
        lda f_lfn
        ldx f_device
        ldy f_sa
        jsr $ffba
        lda f_namelen
        ldx #<f_filename
        ldy #>f_filename
        jsr $ffbd
        inc f_data
        jsr $ffc0
        bcs fs_open_serial
        jsr fs_serial
        bcs fs_open_error
        jsr fs_drive_status
        bcs fs_open_error
        jsr fs_end_io
        jsr fs_snapshot
        lda #0
        jmp fs_finish
fs_open_serial:
        jsr fs_io_error
fs_open_error:
        lda f_data
        beq fs_open_end
        jsr fs_close_data
        jsr fs_drive_status
        bcc fs_open_end
        inc f_uncertain
fs_open_end:
        jsr fs_drop_command
        jsr fs_end_io
        jmp fs_open_failed
fs_open_failed:
        ldx f_slot
        lda f_uncertain
        beq fs_open_discard
        lda #4
        sta NFILES+3,x
        lda f_result
        sta NFILES+7,x
        bne fs_open_return
fs_open_discard:
        lda #0
        sta NFILES,x
        sta N_FHANDLE
        sta N_FHANDLE+1
        sta N_FHANDLE+2
        sta N_FHANDLE+3
fs_open_return:
        jsr fs_snapshot
        lda f_result
        jmp fs_finish

fs_read:
        php
        jsr fs_enter
        bcc *+5
        jmp fs_enter_failed
        lda #0
        beq fs_transfer
fs_write:
        php
        jsr fs_enter
        bcc *+5
        jmp fs_enter_failed
        lda #1
fs_transfer:
        sta f_operation
        jsr fs_handle
        bcc *+5
        jmp fs_finish
        lda NFILES+2,x
        cmp #2
        bne +
        lda NFILES+1,x
        cmp #3
        bcs fs_argument
        jmp nd_read
+       lda NFILES+2,x
        cmp f_operation
        beq *+5
        jmp fs_argument
        lda N_FCOUNT+1
        cmp #2
        bcc fs_count_low
        bne fs_transfer_range
        lda N_FCOUNT
        bne fs_transfer_range
fs_count_low:
        lda N_FCOUNT
        ora N_FCOUNT+1
        beq fs_transfer_range
        lda NFILES+3,x
        and #6
        beq fs_transfer_clean
        lda NFILES+7,x
        bne fs_transfer_failed
        lda #N_IOERROR
fs_transfer_failed:
        jmp fs_finish
fs_transfer_range:
        lda #N_RANGE
        jmp fs_finish
fs_transfer_clean:
        ; Reject 32-bit position wrap before issuing any byte.
        clc
        lda NFILES+8,x
        adc N_FCOUNT
        lda NFILES+9,x
        adc N_FCOUNT+1
        lda NFILES+10,x
        adc #0
        lda NFILES+11,x
        adc #0
        bcs fs_transfer_range
        lda NFILES+3,x
        and #1
        beq fs_transfer_begin
        jsr fs_snapshot
        lda #0
        jmp fs_finish
fs_transfer_begin:
        lda NFILES+1,x
        sta f_device
        cmp #3
        bcs +
        jmp nu_transfer
+
        lda #1
        sta f_expect
        sta f_extra
        jsr fs_guard
        bcc *+5
        jmp fs_finish
        lda N_FCOUNT
        sta f_left
        lda N_FCOUNT+1
        sta f_left+1
        lda #<N_BUFFER
        sta fs_buffer_read+1
        sta fs_buffer_write+1
        lda #>N_BUFFER
        sta fs_buffer_read+2
        sta fs_buffer_write+2
        jsr fs_begin_io
        jsr fs_command
        bcc *+5
        jmp fs_transfer_end
        ldx f_lfn
        lda f_operation
        bne fs_select_output
        jsr $ffc6
        bcc fs_read_loop
        bcs fs_transfer_serial
fs_select_output:
        jsr $ffc9
        bcc fs_write_loop
fs_transfer_serial:
        jsr fs_io_error
        jmp fs_transfer_end
fs_read_loop:
        jsr $ffcf
        sta f_byte
        jsr fs_serial
        bcc *+5
        jmp fs_transfer_end
        lda f_byte
fs_buffer_read:
        sta N_BUFFER
        jsr fs_advance
        ldx f_slot
        lda NFILES+13,x
        bne fs_remaining_low
        lda NFILES+14,x
        bne fs_remaining_middle
        dec NFILES+15,x
fs_remaining_middle:
        dec NFILES+14,x
fs_remaining_low:
        dec NFILES+13,x
        lda NFILES+13,x
        ora NFILES+14,x
        ora NFILES+15,x
        bne fs_read_remaining
        lda f_raw
        and #$40
        bne fs_read_eof
        ; The 1541's sequential path mishandles a one-byte file: the first
        ; byte is correct but EOI arrives later, after link bytes. Only this
        ; independently measured one-byte extent may finish without EOI.
        lda NFILES+8,x
        cmp #1
        bne fs_read_extent_error
        lda NFILES+9,x
        ora NFILES+10,x
        ora NFILES+11,x
        bne fs_read_extent_error
fs_read_eof:
        lda NFILES+3,x
        ora #1
        sta NFILES+3,x
        jmp fs_transfer_status
fs_read_remaining:
        lda f_raw
        and #$40
        beq fs_read_more
fs_read_extent_error:
        lda #N_IOERROR
        jsr fs_error
        jmp fs_transfer_end
fs_read_more:
        lda f_left
        ora f_left+1
        bne fs_read_loop
        beq fs_transfer_status
fs_write_loop:
fs_buffer_write:
        lda N_BUFFER
        jsr $ffd2
        jsr fs_serial
        bcs fs_transfer_end
        jsr fs_advance
        lda f_left
        ora f_left+1
        bne fs_write_loop
fs_transfer_status:
        jsr $ffcc               ; flush the final deferred IEC output byte
        jsr fs_serial
        ; DOS status is checked by OPEN/CLOSE. Repeated status reads between
        ; data chunks produced replies missing their first digit on the 1571
        ; emulator. Every byte/flush still checks IEC
        ; status, and callers must check CLOSE before treating a write as done.
fs_transfer_end:
        jsr fs_end_io
        ldx f_slot
        lda f_result
        beq fs_transfer_ok
        sta NFILES+7,x
        lda NFILES+3,x
        ora #2
        sta NFILES+3,x
        lda f_uncertain
        beq fs_transfer_ok
        lda NFILES+3,x
        ora #4
        sta NFILES+3,x
fs_transfer_ok:
        jsr fs_snapshot
        lda f_result
        jmp fs_finish
fs_advance:
        inc fs_buffer_read+1
        inc fs_buffer_write+1
        bne fs_buffer_next
        inc fs_buffer_read+2
        inc fs_buffer_write+2
fs_buffer_next:
        inc N_FACTUAL
        bne fs_actual_next
        inc N_FACTUAL+1
fs_actual_next:
        ldx f_slot
        inc NFILES+8,x
        bne fs_position_next
        inc NFILES+9,x
        bne fs_position_next
        inc NFILES+10,x
        bne fs_position_next
        inc NFILES+11,x
fs_position_next:
        lda f_left
        bne fs_left_low
        dec f_left+1
fs_left_low:
        dec f_left
        rts
fs_snapshot:
        ldx f_slot
        lda NFILES+3,x
        and #1
        sta N_FEOF
        lda NFILES+8,x
        sta N_FPOSITION
        lda NFILES+9,x
        sta N_FPOSITION+1
        lda NFILES+10,x
        sta N_FPOSITION+2
        lda NFILES+11,x
        sta N_FPOSITION+3
        rts

fs_close:
        php
        jsr fs_enter
        bcc *+5
        jmp fs_enter_failed
        jsr fs_handle
        bcc *+5
        jmp fs_finish
        jsr fs_close_one
        jmp fs_finish
fs_release:
        php
        jsr fs_enter
        bcc *+5
        jmp fs_enter_failed
        ; Preflight every owned record before closing even the first file.
        ldx #0
fs_release_check:
        lda NFILES,x
        cmp N_FOWNER
        bne fs_release_next
        jsr fs_record
        bcc *+5
        jmp fs_finish
fs_release_next:
        txa
        clc
        adc #16
        tax
        cpx #32
        bne fs_release_check
        ; A directory owns the shared UCI reply stream. Release it before
        ; another owned file, regardless of descriptor order.
        jsr nd_release
        bcc *+5
        jmp fs_finish
        lda #0
        sta f_slot
fs_release_loop:
        ldx f_slot
        lda NFILES,x
        cmp N_FOWNER
        bne fs_release_advance
        jsr fs_close_one
        bcc *+5
        jmp fs_finish
fs_release_advance:
        lda f_slot
        clc
        adc #16
        sta f_slot
        cmp #32
        bne fs_release_loop
        lda #0
        jmp fs_finish
fs_close_one:
        ldx f_slot
        lda NFILES+1,x
        cmp #3
        bcs +
        jmp nu_close
+
        lda NFILES+3,x
        and #4
        beq fs_close_ready
        lda NFILES+7,x
        bne fs_close_retained
        lda #N_IOERROR
fs_close_retained:
        sec
        rts
fs_close_ready:
        lda NFILES+1,x
        sta f_device
        lda #1
        sta f_expect
        sta f_extra
        jsr fs_guard
        bcc *+3
        rts
        jsr fs_begin_io
        jsr fs_command
        bcs fs_close_end
        jsr fs_close_data
        jsr fs_drive_status
fs_close_end:
        jsr fs_drop_command
        jsr fs_end_io
        jsr fs_snapshot
        ldx f_slot
        lda f_result
        bne fs_close_failed
        sta NFILES,x
        clc
        rts
fs_close_failed:
        sta NFILES+7,x
        lda NFILES+3,x
        ora #4
        sta NFILES+3,x
        lda f_result
        sec
        rts

; All I/O helpers retain the first error and preserve caller KERNAL arguments.
fs_begin_io:
        lda #1
        sta f_io
        ldx #5
fs_save_parameters:
        lda $b7,x
        sta f_parameters,x
        dex
        bpl fs_save_parameters
        lda $c6
        sta f_parameters+6
        lda $c7
        sta f_parameters+7
        lda $9d
        sta f_parameters+8
        lda #0
        sta $9d
        tax
        jsr $ff68
        rts
fs_command:
        ldx f_cslot
        lda NFCMDS,x
        bne fs_command_already
        lda f_device
        sta NFCMDS,x
        lda #1
        sta NFCMDS+2,x
        lda f_clfn
        ldx f_device
        ldy #15
        jsr $ffba
        lda #0
        tax
        tay
        jsr $ffbd
        inc f_cmd
        jsr $ffc0
        bcs fs_io_error
        jmp fs_serial
fs_command_already:
        clc
        rts
fs_io_error:
        jsr fs_serial
        lda #N_IOERROR
        jmp fs_error
fs_serial:
        jsr $ffb7
        sta f_raw
        lda N_FSTATUS
        and #$bf
        bne fs_serial_saved
        lda f_raw
        sta N_FSTATUS
fs_serial_saved:
        lda f_raw
        and #$bf
        bne fs_serial_bad
        clc
        rts
fs_serial_bad:
        lda #N_IOERROR
fs_error:
        ldx f_result
        bne fs_error_retained
        sta f_result
fs_error_retained:
        sec
        rts
fs_close_data:
        jsr $ffcc
        lda f_lfn
        jsr $ffc3
        jsr fs_serial
        bcc fs_close_data_done
        inc f_uncertain
fs_close_data_done:
        rts
fs_end_io:
        lda f_io
        beq fs_end_done
        jsr $ffcc
fs_restore_parameters:
        jsr $ffcc
        ldx #5
fs_restore_loop:
        lda f_parameters,x
        sta $b7,x
        dex
        bpl fs_restore_loop
        lda f_parameters+6
        sta $c6
        lda f_parameters+7
        sta $c7
        lda f_parameters+8
        sta $9d
        lda #0
        sta f_io
fs_end_done:
        rts

fs_drop_command:
        ; CLOSE 15 is device-wide. Keep it while another stream owns this
        ; device, including an uncertain stream retained after a failed close.
        lda f_slot
        eor #16
        tax
        lda NFILES,x
        beq fs_drop_last
        lda NFILES+1,x
        cmp f_device
        beq fs_drop_done
fs_drop_last:
        ldx f_cslot
        lda NFCMDS,x
        beq fs_drop_done
        jsr $ffcc
        lda f_clfn
        jsr $ffc3
        jsr fs_serial
        bcs fs_drop_failed
        ldx f_cslot
        lda #0
        sta NFCMDS,x
        sta NFCMDS+2,x
fs_drop_done:
        rts
fs_drop_failed:
        inc f_uncertain
        ldx f_cslot
        lda #2
        sta NFCMDS+2,x
        rts

fs_drive_status:
        jsr $ffcc
        ldx f_clfn
        jsr $ffc6
        bcs fs_status_error
        lda #0
        sta f_index
fs_status_read:
        jsr $ffcf
        sta f_byte
        jsr fs_serial
        bcs fs_status_error
        ldx f_index
        lda f_byte
        sta f_status,x
        inc f_index
        cmp #13
        beq fs_status_complete
        lda f_raw
        and #$40
        bne fs_status_error
        lda f_index
        cmp #40
        bne fs_status_read
fs_status_error:
        jsr $ffcc
        lda #N_IOERROR
        jmp fs_error
fs_status_complete:
        jsr $ffcc
        lda f_index
        cmp #4
        bcc fs_status_error
        lda f_status+2
        cmp #$2c
        bne fs_status_error
        ldx #1
fs_status_digits:
        lda f_status,x
        cmp #$30
        bcc fs_status_error
        cmp #$3a
        bcs fs_status_error
        and #15
        sta f_status,x
        dex
        bpl fs_status_digits
        lda f_status
        asl
        sta f_byte
        asl
        asl
        clc
        adc f_byte
        adc f_status+1
        beq fs_status_ok
        ldx N_FDOS
        bne fs_status_error
        sta N_FDOS
        jmp fs_status_error
fs_status_ok:
        clc
        rts

.include "file-extent.inc"

f_types: .text "spu"
f_modes: .text "rw"
f_filename: .fill 20,0
f_namelen: .byte 0
f_parameters: .fill 9,0
f_status: .fill 40,0
f_slot: .byte 0
f_device: .byte 0
f_lfn: .byte 0
f_sa: .byte 0
f_expect: .byte 0
f_extra: .byte 0
f_found: .byte 0
f_cslot: .byte 0
f_clfn: .byte 0
f_command_found: .byte 0
f_command_expect: .byte 0
f_other_sa: .byte 0
f_result: .byte 0
f_cmd: .byte 0
f_data: .byte 0
f_io: .byte 0
f_uncertain: .byte 0
f_operation: .byte 0
f_byte: .byte 0
f_raw: .byte 0
f_index: .byte 0
f_left: .word 0
