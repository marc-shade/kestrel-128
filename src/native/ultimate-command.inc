; ABI 1.11 serialized UCI packet. The request is N_BUFFER[0:2+N_FCOUNT],
; including the two-byte target/command header and 0..510 body bytes.
; Uses the same lock, pending-directory guard, reply limits and owned abort
; as fixed queries. Callers own command semantics and affected resources.
ultimate_command:
        php
        jsr fs_enter
        bcc +
        jmp fs_enter_failed
+       lda #0
        sta N_USTATUS
        jsr nd_guard
        bcs uq_finish
        clc
        lda N_FCOUNT
        adc #2
        sta nu_cmdlen
        lda N_FCOUNT+1
        adc #0
        sta nu_cmdlen+1
        bcs uq_argument
        cmp #2
        bcc uq_command_ready
        bne uq_argument
        lda nu_cmdlen
        bne uq_argument
uq_command_ready:
        lda #<N_BUFFER
        ldx #>N_BUFFER
        jmp uq_send
native_command_end:
