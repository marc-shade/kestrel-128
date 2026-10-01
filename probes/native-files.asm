; Test-only native foreground client. Host supplies the public file mailbox.
.include "../src/native/api.inc"
* = N_APPBASE
start:
        .text "napp"
        .byte 1,1,1,0
        .word end-start
        .byte 16,0
        .word entry-start
        .word 0
        .text "file check",0
        .fill N_APPBASE+32-*,0
entry:
        lda N_CURRENT
        sta N_FOWNER
loop:
        lda #1
        sta N_READY
        jsr N_KEYIN
        beq loop
        cmp #27
        beq leave
        cmp #$4f
        beq open
        cmp #$52
        beq read
        cmp #$57
        beq write
        cmp #$43
        beq close
        cmp #$58
        beq release
        jmp loop
open:
        jsr N_FOPEN
        jmp result
read:
        jsr N_FREAD
        jmp result
write:
        jsr N_FWRITE
        jmp result
close:
        jsr N_FCLOSE
        jmp result
release:
        jsr N_FRELEASE
result:
        sta $3d9f              ; test-only byte, visible under native IRQ ROM map
        jmp loop
leave:
        lda #0
        jmp N_EXIT
end:
        .cerror * > $6100, "test client exceeds its first page"
