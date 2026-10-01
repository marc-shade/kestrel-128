; Retained bank-0 executor for one owned, fixed-address bank-1 image.
; Include banked-load.inc after this file for the checked stream loader.
; See docs/NATIVE-BANKED.md. No resident bytes or unassigned common scratch.
; A second instance may be included inside a .block with its own base, limit
; and code owner (docs/GEM-LAYER-DESIGN.md); the defaults keep the per-app
; executor byte-identical.
        .weak
BK_BASE = $6000
BK_LIMIT = $c000
BK_OWNER = N_APPOWNER         ; owner of the bank-1 code allocation
        .endweak

; A = provider operation; arguments/results use N_BUFFER. bk_load must have
; completed, including source close. Callee returns A/carry; D/I are preserved.
bk_call:
        php
        pha
        jsr bk_enter
        bcs bk_enter_failed
        pla
        sta bk_operation
        lda bk_state
        cmp #2
        bne bk_bad_handle
        jsr bk_check_code
        bcs bk_finish
        jsr bk_check_tails
        bcs bk_finish
        ldx #2
-       lda $06,x
        sta bk_saved_regs,x
        dex
        bpl -
        lda $d506
        sta bk_saved_rcr
        ora #3                ; bottom 16 KiB common while bank-1 code runs
        sta $d506
        lda #0
        sta N_READY
        sta $07
        sta $08
        lda bk_operation
        sta $06
        lda #>(bk_return-1)
        pha
        lda #<(bk_return-1)
        pha
        lda #>(BK_BASE+16-1)   ; validated bank-1 exit stub: LDX #$0e / JMP $02ab
        pha
        lda #<(BK_BASE+16-1)
        pha
        lda bk_entry+1
        pha
        lda bk_entry
        pha
        lda #$20
        pha
        lda #$4e
        jmp $02f2
bk_return:
        sta bk_result
        php
        pla
        and #1
        sta bk_carry
        lda bk_saved_rcr
        sta $d506
        ldx #2
-       lda bk_saved_regs,x
        sta $06,x
        dex
        bpl -
        lda #0
        sta bk_busy
        sta bk_error
        plp
        lda bk_result
        lsr bk_carry
        rts

; A callback reaches bank 0 through the preflighted common RTI tail.
; Restore standard mapping BEFORE any native gate, including heap reads of
; bank-1 pages $04..$3f. Protect the active code and parent allocation.
bk_callback:
        sta bk_service
        lda bk_saved_rcr
        sta $d506
        lda bk_service
        cmp #28
        bcs bk_service_bad
        tax
        lda bk_services,x
        beq bk_service_bad
        cpx #8
        bcs bk_service_call
        cpx #5                ; STATS needs no owner
        beq bk_service_call
        lda N_OWNER
        cmp #N_APPOWNER
.if BK_OWNER != N_APPOWNER
        beq +
        cmp #BK_OWNER         ; a persistent component also owns its data
+
.fi
        bne bk_service_bad
        cpx #1                ; FREE, WRITE and FILL cannot alter active code
        beq bk_protect_code
        cpx #3
        beq bk_protect_code
        cpx #4
        bne bk_service_call
bk_protect_code:
        ldx #3
-       lda N_HANDLE,x
        cmp bk_handle,x
        bne bk_protect_parent
        dex
        bpl -
        bmi bk_service_bad
bk_protect_parent:
        ldx #3
-       lda N_HANDLE,x
        cmp bk_cookie,x
        bne bk_service_call
        dex
        bpl -
bk_service_bad:
        lda #N_BADARG
        sec
        bcs bk_service_return
bk_service_call:
        lda bk_service
        asl
        clc
        adc bk_service
        adc #<N_ALLOC
        sta bk_dispatch+1
bk_dispatch:
        jsr N_ALLOC
bk_service_return:
        php
        pha
        lda bk_saved_rcr
        ora #3
        sta $d506
        pla
        tax
        plp
        txa
        ldx #$4e
        rts                   ; common STX $ff00 / RTS returns to bank 1

; All three public entries save P/A before calling this foreground gate.
bk_enter:
        lda bk_busy
        ora N_BUSY
        ora N_FBUSY
        ora N_UIBUSY
        bne bk_nested
        inc bk_busy
        cld
        tsx
        lda $0104,x
        and #4
        bne bk_platform
        lda $ff00
        cmp #$0e
        bne bk_platform
        lda $d505
        and #$40
        bne bk_platform
        lda $d506
        and #15
        cmp #4
        bne bk_platform
        lda $d508
        ora $d50a
        and #15
        ora $d507
        bne bk_platform
        lda $d509
        cmp #1
        bne bk_platform
        lda N_CURRENT
        cmp #N_APPOWNER
        bne bk_platform
        lda N_APPSTATE
        cmp #2
        bne bk_platform
        lda NPAGES0+$60
        beq bk_invalid
        cmp #NSLOTS+1
        bcs bk_invalid
        sta bk_current
        sec
        sbc #1
        asl
        asl
        asl
        tax
        lda NHANDLES,x
        cmp #N_APPOWNER
        bne bk_invalid
        lda NHANDLES+1,x
        bne bk_invalid
        lda NHANDLES+2,x
        cmp #$60
        bne bk_invalid
        ldy #1
-       lda NHANDLES+4,x
        sta bk_current,y
        inx
        iny
        cpy #4
        bne -
        lda bk_cookie
        bne bk_compare_cookie
        ldx #3
-       lda bk_current,x
        sta bk_cookie,x
        dex
        bpl -
bk_compare_cookie:
        ldx #3
-       lda bk_current,x
        cmp bk_cookie,x
        bne bk_invalid
        dex
        bpl -
        clc
        rts
bk_nested:
        lda #N_REENTRANT
        sec
        rts
bk_platform:
        lda #N_PLATFORM
        sec
        rts
bk_invalid:
        lda #N_BADHANDLE
        sec
        rts
bk_enter_failed:
        tax
        pla
        txa
        cmp #N_REENTRANT
        bne bk_finish
        plp
        sec
        rts
bk_bad_handle:
        lda #N_BADHANDLE
bk_finish:
        sta bk_error
        ldx #0
        stx bk_busy
        plp
        cmp #1
        rts

bk_check_tails:
        ldx #3
-       lda $02ab,x
        cmp bk_fetch_tail,x
        bne bk_platform
        dex
        bpl -
        ldx #9
-       lda $02f2,x
        cmp bk_jump_tail,x
        bne bk_platform
        dex
        bpl -
        clc
        rts
bk_check_code:
        lda bk_pages
        beq bk_invalid
        cmp #(BK_LIMIT-BK_BASE)/256+1
        bcs bk_invalid
        lda bk_length+1
        bne +
        lda bk_length
        cmp #33
        bcc bk_invalid
+       lda bk_length
        cmp #1
        lda bk_length+1
        adc #0
        cmp bk_pages
        bne bk_invalid
        lda bk_entry+1
        cmp #>BK_BASE
        bcc bk_invalid
        bne +
        lda bk_entry
        cmp #32
        bcc bk_invalid
+       sec
        lda bk_entry+1
        sbc #>BK_BASE
        sta bk_relative
        lda bk_entry
        cmp bk_length
        lda bk_relative
        sbc bk_length+1
        bcs bk_invalid
        lda bk_handle
        beq bk_invalid
        cmp #NSLOTS+1
        bcs bk_invalid
        sec
        sbc #1
        asl
        asl
        asl
        tax
        lda NHANDLES,x
        cmp #BK_OWNER
        bne bk_invalid
        lda NHANDLES+1,x
        cmp #1
        bne bk_invalid
        lda NHANDLES+2,x
        cmp #>BK_BASE
        bne bk_invalid
        lda NHANDLES+3,x
        cmp bk_pages
        bne bk_invalid
        ldy #1
-       lda NHANDLES+4,x
        cmp bk_handle,y
        bne bk_invalid
        inx
        iny
        cpy #4
        bne -
        ldx #>BK_BASE
        ldy bk_pages
-       lda NPAGES1,x
        cmp bk_handle
        bne bk_invalid
        inx
        dey
        bne -
        clc
        rts

bk_fetch_tail: .byte $8e,0,$ff,$60
bk_jump_tail: .byte $8d,0,$ff,$a5,6,$a6,7,$a4,8,$40
bk_services: .byte 1,1,1,1,1,1,0,1, 0,0,0,1,1,1,1,1, 1,0,0,1,1,0,0,0, 1,1,1,1
bk_state: .byte 0              ; 0 empty, 1 load/cleanup retained, 2 ready
bk_handle: .fill 4,0
bk_file: .fill 4,0
bk_cookie: .fill 4,0
bk_current: .fill 4,0
bk_pages: .byte 0
bk_length: .word 0
bk_entry: .word 0
bk_busy: .byte 0
bk_error: .byte 0
bk_operation: .byte 0
bk_service: .byte 0
bk_result: .byte 0
bk_carry: .byte 0
bk_saved_rcr: .byte 0
bk_saved_regs: .fill 3,0
bk_relative: .byte 0
