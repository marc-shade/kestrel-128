; Ctrl-P, in the clipboard module (docs/NATIVE-EDITOR-GUI.md): the
; whole document to the printer on IEC device 4 through the KERNAL (logical
; file 121, beside the file service's 122..126; secondary address 7, the
; Commodore printers' upper/lowercase set). ASCII letters become PETSCII,
; CR, LF and CR LF each end a line with CR, a tab prints as a space, and other
; control bytes are left out. Esc stops between 512-byte chunks.
EP_LFN = 121
EP_DEVICE = 4
ep_print:
        lda ed_active
        sta d_slot
        jsr doc_context
        bcc +
        jmp ec_error
+       ldx #8                  ; the KERNAL's file parameters, as the file service keeps them
-       lda $b7,x
        sta ep_saved,x
        dex
        bpl -
        lda $c6
        sta ep_saved+9
        lda $c7
        sta ep_saved+10
        lda $9d
        sta ep_saved+11
        lda #0
        sta $9d                 ; no KERNAL messages
        sta ep_previous
        sta ep_position
        sta ep_position+1
        sta ep_position+2
        tax
        jsr $ff68               ; SETBNK: the name in bank 0
        lda #EP_LFN
        ldx #EP_DEVICE
        ldy #7
        jsr $ffba               ; SETLFS
        lda #0
        jsr $ffbd               ; SETNAM: none
        jsr $ffc0               ; OPEN (no bus traffic without a name)
        bcs ep_absent_open
        ldx #EP_LFN
        jsr $ffc9               ; CHKOUT: the printer answers or is absent
        bcs ep_absent
        lda $90
        bmi ep_absent
ep_chunk:
        #doc_cmp3 ep_position,ed_length
        bcs ep_printed
        #es_copy3 ep_position,d_pos
        lda #0
        sta d_count
        sta d_count+2
        lda #2
        sta d_count+1
        jsr doc_read
        bcs ep_read_failed
        lda d_actual
        ora d_actual+1
        beq ep_printed
        lda #<d_output
        sta ep_read+1
        lda #>d_output
        sta ep_read+2
        lda d_actual
        sta ep_left
        lda d_actual+1
        sta ep_left+1
ep_byte:
ep_read:
        lda $ffff
        jsr ep_petscii
        bcs ep_next
        jsr $ffd2
        lda $90
        bmi ep_absent
ep_next:
        inc ep_read+1
        bne +
        inc ep_read+2
+       lda ep_left
        bne +
        dec ep_left+1
+       dec ep_left
        lda ep_left
        ora ep_left+1
        bne ep_byte
        clc
        lda ep_position
        adc d_actual
        sta ep_position
        lda ep_position+1
        adc d_actual+1
        sta ep_position+1
        bcc +
        inc ep_position+2
+       jsr ed_cancel_check
        bcc ep_chunk
        lda #8                  ; "cancelled; document kept"
        bne ep_done
ep_printed:
        lda #32
        bne ep_done
ep_read_failed:
        lda #25                 ; "clipboard error; text retained" names no data loss
        bne ep_done
ep_absent:
        lda #33
ep_done:
        pha
        jsr $ffcc               ; CLRCHN
        lda #EP_LFN
        jsr $ffc3               ; CLOSE
        pla
ep_restore:
        pha
        ldx #8
-       lda ep_saved,x
        sta $b7,x
        dex
        bpl -
        lda ep_saved+9
        sta $c6
        lda ep_saved+10
        sta $c7
        lda ep_saved+11
        sta $9d
        pla
        jmp ec_status
ep_absent_open:
        lda #33
        bne ep_restore
; A = a document byte -> A to print, carry clear; carry set to leave it out.
ep_petscii:
        ldx ep_previous
        sta ep_previous
        cmp #10
        bne +
        cpx #13                 ; CR LF: the CR ended the line
        beq ep_skip
        lda #13
        clc
        rts
+       cmp #13
        beq ep_keep
        cmp #9
        bne +
        lda #32
        clc
        rts
+       cmp #32
        bcc ep_skip
        cmp #127
        bcs ep_skip
        cmp #$41
        bcc ep_keep
        cmp #$5b
        bcs +
        ora #$80                ; A-Z: shifted letters
        clc
        rts
+       cmp #$61
        bcc ep_keep
        cmp #$7b
        bcs ep_keep
        and #$df                ; a-z: unshifted letters
ep_keep:
        clc
        rts
ep_skip:
        sec
        rts
ep_saved: .fill 12,0
ep_previous: .byte 0
ep_position: .fill 3,0
ep_left: .word 0
