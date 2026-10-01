; IEC DOS commands for native apps (docs/NATIVE-DOS-COMMANDS.md), GPL v3.
; Sends one command, such as "S0:NAME", as the name of an OPEN on secondary
; address 15 and reads the drive's status line. The drive runs the command
; when the channel opens; closing it again is safe only while no other
; channel is open to that drive, so the call is refused while the kernel
; holds a command channel for the device (an open native stream).
;
; In: dc_device (8..30), dc_text[dc_length] (1..DC_MAX bytes).
; Out: carry clear: A = dc_code, the status's DOS code; dc_status holds the
; line (dc_status_length bytes, without the CR) and dc_track its third field.
; dc_blocks_free reads the drive's "$" listing the same way: dc_free = the
; number of its last line, the drive's blocks free.
; Carry set: A = N_BADARG, N_REENTRANT, N_CHANNELS (the kernel has a channel
; to the device, or output is redirected) or N_IOERROR (dc_iostatus = the
; KERNAL status; the command may or may not have run).
DC_LFN = 127                    ; the kernel uses 122..126
DC_MAX = 40
dc_command:
        lda dc_length
        beq dc_bad
        cmp #DC_MAX+1
        bcs dc_bad
        lda #15
        jsr dc_begin
        bcc +
        rts
+       lda dc_length
        ldx #<dc_text
        ldy #>dc_text
        jsr $ffbd               ; SETNAM
        jsr $ffc0               ; OPEN: the drive receives the command
        bcs dc_open_failed
        jsr $ffb7
        sta dc_iostatus
        and #$80                ; device not present
        bne dc_close_failed
        ldx #DC_LFN
        jsr $ffc6               ; CHKIN
        bcs dc_close_failed
        jmp dc_status_read
; A = secondary address. The argument and channel checks, the saved KERNAL
; parameters, SETBNK and SETLFS shared by every call. Carry set: A = error.
dc_begin:
        sta dc_sa
        lda dc_device
        cmp #8
        bcc dc_bad
        cmp #31
        bcs dc_bad
        lda N_FBUSY
        ora N_BUSY
        beq +
        lda #N_REENTRANT
        sec
        rts
+       lda $99                 ; default input and output channels
        bne dc_channels
        lda $9a
        cmp #3
        bne dc_channels
        ldx #1                  ; the kernel's command channel table
-       lda NFCMDS,x
        cmp dc_device
        beq dc_channels
        dex
        bpl -
        ldx #5                  ; save the KERNAL file parameters like the kernel
-       lda $b7,x
        sta dc_saved,x
        dex
        bpl -
        lda $c6
        sta dc_saved+6
        lda $c7
        sta dc_saved+7
        lda $9d
        sta dc_saved+8
        lda #0
        sta $9d                 ; no KERNAL messages
        sta dc_iostatus
        sta dc_status_length
        sta dc_eoi
        tax
        jsr $ff68               ; SETBNK: file name in bank 0
        lda #DC_LFN
        ldx dc_device
        ldy dc_sa
        jsr $ffba               ; SETLFS
        clc
        rts
dc_status_read:
-       jsr $ffcf               ; CHRIN: the status line
        sta dc_byte
        jsr $ffb7
        sta dc_iostatus
        and #$83                ; timeout or device not present
        bne dc_close_failed
        lda dc_byte
        cmp #13
        beq dc_read
        ldx dc_status_length
        cpx #DC_MAX
        bcs dc_close_failed     ; no CR within the bound
        sta dc_status,x
        inc dc_status_length
        lda dc_iostatus
        and #$40                ; EOI before the CR
        beq -
dc_read:
        jsr dc_close
        bcs dc_io
        lda dc_status_length    ; "NN,MESSAGE,TT,SS"
        cmp #4
        bcc dc_io
        lda dc_status+2
        cmp #$2c
        bne dc_io
        lda dc_status
        jsr dc_digit
        bcs dc_io
        asl
        sta dc_code
        asl
        asl
        adc dc_code
        sta dc_code
        lda dc_status+1
        jsr dc_digit
        bcs dc_io
        adc dc_code
        sta dc_code
        jsr dc_field_track
        lda dc_code
        clc
        rts
dc_close_failed:
        jsr dc_close
dc_open_failed:
        jsr dc_restore
dc_io:
        lda #N_IOERROR
        sec
        rts
dc_bad:
        lda #N_BADARG
        sec
        rts
dc_channels:
        lda #N_CHANNELS
        sec
        rts
; Free blocks: the drive's "$" listing, read to its end; the number of its
; last line ("BLOCKS FREE.") -> dc_free (word). Same checks and errors as
; dc_command, which the drive may be asked for afterwards to explain a failure.
dc_blocks_free:
        lda #0
        jsr dc_begin
        bcc +
        rts
+       lda #1
        ldx #<dc_dollar
        ldy #>dc_dollar
        jsr $ffbd               ; SETNAM "$"
        jsr $ffc0
        bcs dc_open_failed
        jsr $ffb7
        sta dc_iostatus
        and #$80
        bne dc_close_failed
        ldx #DC_LFN
        jsr $ffc6
        bcs dc_close_failed
        lda #0
        sta dc_free
        sta dc_free+1
        jsr dc_get              ; the load address
        bcs dc_close_failed
        jsr dc_get
        bcs dc_close_failed
dc_line:
        jsr dc_get              ; link: zero at the end of the listing
        bcs dc_close_failed
        sta dc_byte
        jsr dc_get
        bcs dc_close_failed
        ora dc_byte
        beq dc_listed
        jsr dc_get              ; line number: blocks
        bcs dc_close_failed
        sta dc_free
        jsr dc_get
        bcs dc_close_failed
        sta dc_free+1
-       jsr dc_get              ; the text, up to its zero
        bcs dc_close_failed
        cmp #0
        bne -
        jmp dc_line
dc_listed:
        jsr dc_close
        bcs +
        lda #0
        rts
+       jmp dc_io
; CHRIN with the status check; carry set on a transport error or on EOI
; before the byte the caller expects (the last byte itself is fine).
dc_get:
        lda dc_eoi
        bne dc_get_end
        jsr $ffcf
        pha
        jsr $ffb7
        sta dc_iostatus
        and #$83
        bne dc_get_bad
        lda dc_iostatus
        and #$40
        sta dc_eoi
        pla
        clc
        rts
dc_get_bad:
        pla
dc_get_end:
        sec
        rts
; Close the channel, then restore the parameters. Carry set if CLOSE failed.
dc_close:
        jsr $ffcc               ; CLRCHN
        lda #DC_LFN
        jsr $ffc3               ; CLOSE
        php
        jsr dc_restore
        plp
        rts
dc_restore:
        jsr $ffcc
        ldx #5
-       lda dc_saved,x
        sta $b7,x
        dex
        bpl -
        lda dc_saved+6
        sta $c6
        lda dc_saved+7
        sta $c7
        lda dc_saved+8
        sta $9d
        rts
; A = ASCII digit -> value, carry set if not a digit.
dc_digit:
        sec
        sbc #$30
        cmp #10
        rts
; dc_track = the decimal third field (the file count after a scratch).
dc_field_track:
        lda #0
        sta dc_track
        ldx #0
        ldy #2                  ; skip two commas
-       cpx dc_status_length
        bcs dc_field_done
        lda dc_status,x
        inx
        cmp #$2c
        bne -
        dey
        bne -
-       cpx dc_status_length
        bcs dc_field_done
        lda dc_status,x
        inx
        jsr dc_digit
        bcs dc_field_done
        sta dc_byte
        lda dc_track            ; track*10 + digit
        asl
        sta dc_code2
        asl
        asl
        adc dc_code2
        adc dc_byte
        sta dc_track
        jmp -
dc_field_done:
        rts

dc_device: .byte 0
dc_length: .byte 0
dc_text: .fill DC_MAX,0
dc_code: .byte 0
dc_code2: .byte 0
dc_track: .byte 0
dc_iostatus: .byte 0
dc_byte: .byte 0
dc_status_length: .byte 0
dc_status: .fill DC_MAX,0
dc_saved: .fill 9,0
dc_sa: .byte 0
dc_eoi: .byte 0
dc_free: .word 0
dc_dollar: .byte $24
