; Document edits record byte spans through the retained banked service.
; Preparation never changes document bytes. An unavailable journal permits
; the edit, then drops stale history and reports that it cannot be undone.
.include "../history-api.inc"
eh_insert:
        lda #0
        beq eh_edit
eh_delete:
        lda #1
        bne eh_edit
eh_replace:
        lda #2
        bne eh_edit
eh_clip:
        lda #3
eh_edit:
        sta eh_kind
        ldx #5
-       lda d_pos,x
        sta eh_saved,x
        sta eh_header,x
        dex
        bpl -
        ldx #2
-       lda #0
        sta eh_header+6,x
        lda eh_kind
        bne +
        lda eh_saved+3,x
        sta eh_header+6,x
        lda #0
        sta eh_header+3,x
+       dex
        bpl -
        lda eh_kind
        cmp #2
        bne +
        #es_copy3 d_replace_count,eh_header+6
+       lda eh_kind
        cmp #3
        bne +
        ldx #8
-       lda ec_start,x
        sta eh_header,x
        dex
        bpl -
+       lda #0
        sta eh_pending
        lda eh_available
        beq eh_execute
        ldx #8
-       lda eh_header,x
        sta N_BUFFER,x
        dex
        bpl -
        lda #H_BEGIN
        jsr bk_call
        bcs eh_execute
        #es_copy3 eh_header+3,eh_left
        jsr eh_capture
        bcs eh_execute
        inc eh_pending
eh_execute:
        jsr eh_restore
        ldx eh_kind
        lda eh_calls_lo,x
        sta eh_call+1
        lda eh_calls_hi,x
        sta eh_call+2
        jsr eh_call
        bcc eh_result
        cmp #N_NOMEM
        beq +
        cmp #N_NOSLOT
        bne eh_result
+       ldx eh_pending
        beq eh_result
        lda #H_ABORT
        jsr bk_call
        bcs eh_result
        lda #0
        sta eh_pending
        jsr eh_restore
        jsr eh_call          ; retry a refused edit after returning its record
eh_result:
        php
        pha
        bcs eh_failed_edit
        lda eh_pending
        beq eh_lost
        #es_copy3 eh_header+6,eh_left
        jsr eh_capture
        bcs eh_lost
        lda #H_SEAL
        jsr bk_call
        bcs eh_lost
        jmp eh_done
eh_lost:
        lda #1
        sta eh_warning
        sta N_BUFFER
        lda eh_available
        beq eh_done
        lda #H_CLEAR
        jsr bk_call
        jmp eh_done
eh_failed_edit:
        lda eh_available
        beq eh_done
        lda #H_ABORT
        jsr bk_call
eh_done:
        jsr eh_restore
        pla
        plp
        rts
eh_restore:
        ldx #5
-       lda eh_saved,x
        sta d_pos,x
        dex
        bpl -
        rts
eh_capture:
        #es_copy3 eh_header,eh_position
eh_capture_loop:
        lda eh_left
        ora eh_left+1
        ora eh_left+2
        beq eh_ok
        lda #0
        sta d_count
        sta d_count+2
        lda #2
        sta d_count+1
        lda eh_left+2
        bne +
        lda eh_left+1
        cmp #2
        bcs +
        sta d_count+1
        lda eh_left
        sta d_count
+       #es_copy3 eh_position,d_pos
        jsr doc_read
        bcs eh_return
        ldx #0
-       lda d_output,x
        sta N_BUFFER,x
        lda d_output+256,x
        sta N_BUFFER+256,x
        inx
        bne -
        lda d_count
        sta H_COUNT
        lda d_count+1
        sta H_COUNT+1
        lda #H_APPEND
        jsr bk_call
        bcs eh_return
        #es_sub3 d_count,eh_left
        #es_add3 d_count,eh_position
        jmp eh_capture_loop
eh_ok:
        clc
eh_return:
        rts
eh_reset:
        lda eh_available
        bne +
        sta dm_mode          ; a new document may have room for the provider
        rts
+
        lda #0
        sta N_BUFFER
        lda #H_CLEAR
        jmp bk_call
eh_save:
        lda eh_available
        beq eh_return
        lda #H_SAVE
        jmp bk_call
eh_close:
        lda eh_available
        beq eh_ok
        lda #H_CLOSE
        jsr bk_call
        bcs eh_return
        lda #0
        sta eh_available
        rts
eh_relieve:
        ; RAM-only VIC documents may reclaim optional history/provider RAM
        ; when their next 4 KiB chunk would otherwise be refused.
        lda eh_available
        beq eh_no_room
        lda bp_started
        bne eh_no_room
        jsr eh_close
        bcs eh_return
        jmp vd_close
eh_no_room:
        lda #N_NOMEM
        sec
        rts
eh_call:
        jmp $ffff
eh_notice:
        lda eh_warning
        beq eh_return
        lda ed_status
        beq +
        cmp #17
        bcc eh_return
        cmp #22
        bcs eh_return
+       lda #30
        sta ed_status
        rts
eh_calls_lo: .byte <doc_insert,<doc_delete,<doc_replace,<ec_replace
eh_calls_hi: .byte >doc_insert,>doc_delete,>doc_replace,>ec_replace

; Previously unused bytes in the already owned $5000..$5fff workspace.
eh_header=$5f9c
eh_saved=eh_header+9
eh_left=eh_saved+6
eh_position=eh_left+3
eh_available=eh_position+3
eh_pending=eh_available+1
eh_kind=eh_pending+1
eh_warning=eh_kind+1
.cerror eh_warning >= $5fc0, "history scratch overlaps text scratch"
