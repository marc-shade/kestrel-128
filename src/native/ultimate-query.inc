; Fixed, nonmutating queries using the same lock/FIFO/abort path as streams.
; This occupies padding at $4b00..$4bfb already excluded from the heap.
ultimate_query:
        php
        jsr fs_enter
        bcc +
        jmp fs_enter_failed
+       lda #0
        sta N_USTATUS
        jsr nd_guard
        bcs uq_finish
        lda N_UOP
        cmp #N_U_QUERY_COUNT
        bcs uq_argument
        tax
        lda uq_targets,x
        bne uq_target
        lda N_UARG
        beq uq_argument
        cmp #16
        bcs uq_argument
uq_target:
        sta nu_short
        lda uq_commands,x
        sta nu_short+1
        lda uq_arguments,x
        bpl +
        lda N_UARG
+       sta nu_short+2
        lda uq_lengths,x
        sta nu_cmdlen
        lda #0
        sta nu_cmdlen+1
        lda #<nu_short
        ldx #>nu_short
uq_send:
        ldy #0
        sty nu_packet_mode
        jsr nu_send
        bcs uq_result
        beq uq_result
        lda #N_IOERROR
uq_result:
        pha
        lda nu_length
        sta N_FACTUAL
        lda nu_length+1
        sta N_FACTUAL+1
        pla
uq_finish:
        jmp fs_finish
uq_argument:
        lda #N_BADARG
        bne uq_finish

uq_targets:   .byte 0,4,4,4,4,3,3,3,1
uq_commands:  .byte 1,$28,$29,$34,$35,2,4,5,$26
uq_arguments: .byte 0,0,1,0,0,0,$80,$80,0
uq_lengths:   .byte 2,3,3,2,2,2,3,3,2
