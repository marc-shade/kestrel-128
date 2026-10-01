; Retained REU arena running entirely in owned bank-1 RAM.
.include "api.inc"
BK_BASE = $6000
RU_BANKED = 1
* = BK_BASE
provider_image:
        .text "nbk1"
        .byte 1,1,12,0
        .word provider_end-provider_image
        .byte (provider_end-provider_image+255)/256,1
        .word provider_entry-provider_image,0
        ldx #$0e
        jmp $02ab             ; checked common STX $ff00 / RTS
        .byte 0
        .word 0               ; loader patches the checked bank-0 callback
        .fill 8,0
provider_entry:
        cmp #9
        bcc provider_reu
        beq provider_config
        cmp #10
        beq provider_status
        cmp #11
        beq provider_native
        lda #N_BADARG
        sec
        rts
provider_reu:
        asl
        tax
        lda provider_entries,x
        sta provider_call+1
        lda provider_entries+1,x
        sta provider_call+2
provider_call:
        jmp $ffff
provider_config:
        ldx #17
-       lda N_BUFFER,x
        sta ru_owner,x        ; contiguous owner/pages/page/token/offset/count
        dex
        bpl -
        lda #0
        clc
        rts
provider_status:
        ldx #20
-       lda ru_owner,x        ; config + actual (2) + last error
        sta N_BUFFER,x
        dex
        bpl -
        ldx #6
-       lda ru_total,x        ; total/available/slots/active/busy
        sta N_BUFFER+21,x
        dex
        bpl -
        lda ru_probe_live
        sta N_BUFFER+28
        lda #0
        clc
        rts
provider_native:
        lda N_BUFFER
        jmp bk_native
provider_entries: .word ru_open,ru_close,ru_alloc,ru_reserve,ru_free,ru_read,ru_write,ru_stats,ru_release
.include "banked-client.inc"
.include "reu.inc"
provider_end:
.cerror provider_end > $c000, "bank-1 code exceeds the executable region"
