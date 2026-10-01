; Include in a bank-1 image after its NBK1 header. No zero-page allocation.
; A = native jump-table index. Shared arguments below $4000 are directly
; visible. $4000..$4fff mailboxes must be prepared by the bank-0 parent.
; Only the returning service subset documented in NATIVE-BANKED.md is legal.
; The parent patches BK_BASE+22 only after validating and loading the image.
bk_native:
        php
        pha
        tsx
        lda $0102,x
        and #4
        bne bk_client_platform
        pla
        sta $06
        lda #>(bk_client_return-1)
        pha
        lda #<(bk_client_return-1)
        pha
        lda #>$02aa           ; RTS through STX $ff00 / RTS at $02ab
        pha
        lda #<$02aa
        pha
        lda BK_BASE+23
        pha
        lda BK_BASE+22
        pha
        lda #$20              ; foreground callback: binary mode, IRQ enabled
        pha
        lda #$0e
        jmp $02f2             ; common STA $ff00 / LDA $06 ... / RTI
bk_client_return:
        sta bk_client_result
        php
        pla
        and #1
        sta bk_client_carry
        plp
        lda bk_client_result
        lsr bk_client_carry
        rts
bk_client_platform:
        pla
        plp
        lda #N_PLATFORM
        sec
        rts
bk_client_result: .byte 0
bk_client_carry: .byte 0
