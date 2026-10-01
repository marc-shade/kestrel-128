; C128 KERNAL boot sector, loaded at $0b00. GPL v3.
; Enter BASIC 7 through its normal RUN path, then the native SYS stub.
* = $0b00
        .byte $43,$42,$4d       ; CBM signature (unshifted PETSCII)
        .word $0b00
        .byte 0,0              ; no additional raw sectors
        .text "kestrel",0
        .byte 0                ; no optional filename loaded by BOOT_CALL
        ldx #command_end-command-1
boot_key:
        lda command,x
        sta $034a,x
        dex
        bpl boot_key
        lda #command_end-command
        sta $d0
        rts
command: .byte $52,$55,$4e,$22,$55,$22,13 ; RUN"U" + Return
command_end:
        .fill $0c00-*,0
