; Native drive operations. All UCI access uses public, serialized services.
; Keep full names, independently checked inventory and session system locks.
UD_ERR_INVALID=$80
UD_ERR_SYSTEM=$81
UD_ERR_OFF=$82
UD_ERR_CHANGED=$83
UD_ERR_IMAGE=$84
UD_ERR_BUSY=$85
UD_ERR_CONTEXT=$86
UD_ERR_PENDING=$87
ud_init:
        lda N_BOOTDEVICE
        sta ud_boot_device
        lda #0
        sta ud_source_device
        lda N_APPFORMAT
        cmp #3
        beq +
        lda N_DEVICE
        sta ud_source_device
+       lda #1
        sta ud_context
        rts

ud_probe:
        lda #0
        sta uc_valid
        sta uc_partial
        sta ud_verified
        sta ud_count
        sta ud_partial
        ldx #11
-       sta ud_records,x
        dex
        bpl -
        lda #N_U_DRIVES
        jsr uc_query
        bcs ud_probe_failed
        jsr uc_parse_drives
        lda uc_error
        bne ud_probe_failed
        lda uc_count
        sta ud_count
        lda uc_partial
        sta ud_partial
        ldx #0
        ldy #0
ud_copy_record:
        cpx ud_count
        beq ud_check_partial
        lda uc_data+1,y
        sta ud_records,y
        lda uc_data+2,y
        sta ud_records+1,y
        cmp ud_boot_device
        beq ud_lock_slot
        cmp ud_source_device
        beq ud_lock_slot
        cmp N_BOOTDEVICE
        bne +
ud_lock_slot:
        lda #1
        sta ud_locks,x
+       lda uc_data+3,y
        sta ud_records+2,y
        iny
        iny
        iny
        inx
        bne ud_copy_record
ud_check_partial:
        lda ud_partial
        beq ud_probe_ready
        lda ud_records
        cmp #3
        bcs ud_probe_bad
        lda ud_records+3
        cmp #3
        bcs ud_probe_bad
        lda ud_records+1
        cmp #8
        bcc ud_probe_bad
        cmp ud_records+4
        beq ud_probe_bad
        lda ud_records+4
        cmp #8
        bcc ud_probe_bad
        lda #0
        sta ud_power_index
ud_power_query:
        lda ud_power_index
        clc
        adc #N_U_POWER_A
        jsr uc_query
        bcs ud_probe_failed
        lda uc_length+1
        bne ud_probe_bad
        lda uc_length
        cmp #2
        bcc ud_probe_bad
        cmp #4
        bcs ud_probe_bad
        lda uc_data
        cmp #$6f
        bne ud_probe_bad
        lda uc_data+1
        cmp #$6e
        beq ud_power_on
        cmp #$66
        bne ud_probe_bad
        lda uc_length
        cmp #3
        bne ud_probe_bad
        lda uc_data+2
        cmp #$66
        bne ud_probe_bad
        lda #0
        beq ud_power_compare
ud_power_on:
        lda uc_length
        cmp #2
        beq +
        lda uc_data+2
        cmp #$20
        bne ud_probe_bad
+       lda #1
ud_power_compare:
        ldx ud_power_index
        ldy ud_offsets,x
        cmp ud_records+2,y
        bne ud_probe_bad
        inc ud_power_index
        lda ud_power_index
        cmp #2
        bne ud_power_query
ud_probe_ready:
        lda #1
        sta ud_verified
        sta uc_valid
        lda ud_count
        sta uc_count
        lda ud_partial
        sta uc_partial
        ldx #11
-       lda ud_records,x
        sta uc_data+1,x
        dex
        bpl -
        lda ud_selected
        cmp ud_count
        bcc +
        lda #0
        sta ud_selected
+       lda #0
        sta uc_error
        clc
        rts
ud_probe_bad:
        lda #N_CORRUPT
        sta uc_error
ud_probe_failed:
        lda #0
        sta uc_valid
        sta ud_verified
        lda uc_error
        sec
        rts

; No unknown type, duplicate address (even if off), system slot or live file.
ud_guard:
        lda ud_verified
        beq ud_invalid
        ldx ud_selected
        cpx ud_count
        bcs ud_invalid
        ldy ud_offsets,x
        lda ud_records,y
        cmp #3
        bcs ud_invalid
        lda ud_records+1,y
        cmp #8
        bcc ud_invalid
        cmp #31
        bcs ud_invalid
        sta ud_id
        cmp ud_boot_device
        beq ud_system
        cmp ud_source_device
        beq ud_system
        cmp N_BOOTDEVICE
        beq ud_system
        lda ud_locks,x
        bne ud_system
        lda ud_records+2,y
        beq ud_off
        ldx #0
-       cpx ud_count
        beq ud_guard_files
        cpx ud_selected
        beq +
        ldy ud_offsets,x
        lda ud_records+1,y
        cmp ud_id
        beq ud_invalid
+       inx
        bne -
ud_guard_files:
        lda $98                 ; existing KERNAL files belong to their caller
        bne ud_busy
        ldx #0
-       lda NFILES,x
        beq +
        cmp #$ff
        bne ud_busy
+       txa
        eor #16
        tax
        bne -
        lda #0
        clc
        rts
ud_invalid:
        lda #UD_ERR_INVALID
        bne ud_error_return
ud_system:
        lda #UD_ERR_SYSTEM
        bne ud_error_return
ud_off:
        lda #UD_ERR_OFF
        bne ud_error_return
ud_busy:
        lda #UD_ERR_BUSY
ud_error_return:
        sec
        rts

; A=$23 Mount/$24 Eject. Capture exactly the displayed selection at the prompt.
ud_prepare:
        sta ud_choice
        lda #0
        sta ud_pending
        lda ud_choice
        cmp #$23
        beq +
        cmp #$24
        bne ud_invalid
+       jsr ud_guard
        bcs ud_prepare_done
        lda ud_choice
        cmp #$23
        bne ud_prepare_copy
        jsr ud_image
        bcs ud_prepare_done
ud_prepare_copy:
        ldx #11
-       lda ud_records,x
        sta ud_saved_records,x
        dex
        bpl -
        lda ud_count
        sta ud_saved_count
        lda ud_partial
        sta ud_saved_partial
        lda ud_selected
        sta ud_saved_selected
        lda ud_choice
        sta ud_pending
        lda #0
        clc
ud_prepare_done:
        rts
ud_cancel:
        lda #0
        sta ud_pending
        clc
        rts

ud_image:
        lda ud_context
        beq ud_context_bad
        cmp #3
        bcs ud_context_bad
        lda ud_name_length
        cmp #6                  ; slash, one character and a four-byte suffix
        bcc ud_image_bad
        lda ud_name
        cmp #$2f
        bne ud_image_bad
        ldx #0
-       lda ud_name,x
        beq ud_image_bad
        inx
        cpx ud_name_length
        bne -
        txa
        sec
        sbc #4
        tax
        lda ud_name,x
        cmp #$2e
        bne ud_image_bad
        lda ud_name+1,x
        and #$df
        cmp #$44
        beq +
        cmp #$47
        bne ud_image_bad
+       sta ud_image_kind
        lda ud_name+2,x
        cmp #$36
        beq ud_image_64
        cmp #$37
        beq ud_image_71
        cmp #$38
        bne ud_image_bad
        lda ud_image_kind
        cmp #$44
        bne ud_image_bad
ud_image_71:
        lda #$31
        bne ud_image_last
ud_image_64:
        lda #$34
ud_image_last:
        cmp ud_name+3,x
        bne ud_image_bad
        lda #0
        clc
        rts
ud_image_bad:
        lda #UD_ERR_IMAGE
        bne ud_error_return
ud_context_bad:
        lda #UD_ERR_CONTEXT
        bne ud_error_return

; Confirmation consumes the pending action before any I/O. Never replay it.
ud_confirm:
        lda ud_pending
        beq ud_not_pending
        sta ud_choice
        lda #0
        sta ud_pending
        jsr ud_probe
        bcs ud_confirm_done
        lda ud_selected
        cmp ud_saved_selected
        bne ud_changed
        lda ud_count
        cmp ud_saved_count
        bne ud_changed
        lda ud_partial
        cmp ud_saved_partial
        bne ud_changed
        ldx #11
-       lda ud_records,x
        cmp ud_saved_records,x
        bne ud_changed
        dex
        bpl -
        jsr ud_guard
        bcs ud_confirm_done
        lda ud_choice
        cmp #$23
        bne +
        jsr ud_image
        bcs ud_confirm_done
+       lda #1
        sta ud_check_context
ud_context_idle:
        lda ud_check_context
        sta N_BUFFER
        lda #7                  ; FILE_INFO: only an explicit no-open-file reply
        sta N_BUFFER+1
        lda #0
        sta N_FCOUNT
        sta N_FCOUNT+1
        jsr ud_packet
        bcc ud_busy
        cmp #N_IOERROR
        bne ud_confirm_done
        lda uc_dos
        cmp #85
        bne ud_packet_failed
        lda uc_transport
        ora uc_length
        ora uc_length+1
        bne ud_packet_failed
        inc ud_check_context
        lda ud_check_context
        cmp #3
        bne ud_context_idle
        lda ud_context
        beq ud_context_bad
        cmp #3
        bcs ud_context_bad
        sta N_BUFFER
        lda ud_choice
        sta N_BUFFER+1
        lda ud_id
        sta N_BUFFER+2
        lda #0
        sta N_FCOUNT+1
        lda #1
        sta N_FCOUNT
        lda ud_choice
        cmp #$24
        beq ud_packet
        ldx #0
-       lda ud_name,x
        sta N_BUFFER+3,x
        inx
        cpx ud_name_length
        bne -
        txa
        clc
        adc #1
        sta N_FCOUNT
        lda #0
        adc #0
        sta N_FCOUNT+1
        jmp ud_packet
ud_changed:
        lda #UD_ERR_CHANGED
        bne ud_error_return
ud_not_pending:
        lda #UD_ERR_PENDING
        bne ud_error_return
ud_packet_failed:
        lda #N_IOERROR
        bne ud_error_return
ud_confirm_done:
        cmp #1
        rts

ud_packet:
        lda N_CURRENT
        sta N_FOWNER
        jsr N_UCOMMAND
        jmp uc_query_result

ud_offsets: .byte 0,3,6,9
ud_selected: .byte 0
ud_count: .byte 0
ud_partial: .byte 0
ud_verified: .byte 0
ud_locks: .fill 4,0
ud_records: .fill 12,0
ud_saved_records: .fill 12,0
ud_saved_count: .byte 0
ud_saved_partial: .byte 0
ud_saved_selected: .byte 0
ud_boot_device: .byte 0
ud_source_device: .byte 0
ud_power_index: .byte 0
ud_id: .byte 0
ud_choice: .byte 0
ud_pending: .byte 0
ud_check_context: .byte 0
ud_context: .byte 1
ud_image_kind: .byte 0
ud_name_length: .byte 0
ud_name: .fill 256,0
