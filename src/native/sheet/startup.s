; Native Kestrel startup for the Sheet application; no BASIC/cc65 ROM startup.
.export __STARTUP__ : absolute = 1
.export native_entry
.import _main, zerobss
.import __BSS_RUN__, __BSS_SIZE__, __CSTACK_RUN__, __CSTACK_SIZE__
.importzp sp

.segment "LOADADDR"
        .word $6000
.segment "HEADER"
        .byte $4e,$41,$50,$50,1,1,13,0
        .word __BSS_RUN__-$6000
        ; The startup packer needs a separate 48-byte tail after the live stack.
        .byte 96,$4e             ; module window offset $4e00, full app window
        .word native_entry-$6000
        .word 0
        .byte $53,$48,$45,$45,$54,0,0,0,0,0,0,0,0,0,0,0
.segment "STARTUP"
native_entry:
        cld
        ldx #25
@save:  lda $02,x
        sta saved_zp,x
        dex
        bpl @save
        jsr zerobss
        lda #<(__CSTACK_RUN__+__CSTACK_SIZE__)
        sta sp
        lda #>(__CSTACK_RUN__+__CSTACK_SIZE__)
        sta sp+1
        jsr _main
        sta native_exit_code
        ldx #25
@restore:
        lda saved_zp,x
        sta $02,x
        dex
        bpl @restore
        lda native_exit_code
        jmp $1c3e               ; N_EXIT restores the dispatcher's CPU stack.
.segment "DATA"
saved_zp: .res 26,0              ; cannot be cleared by zerobss after the save
native_exit_code: .byte 0
.segment "CSTACK"
        .res 384                ; 129 bytes measured in the engine test
