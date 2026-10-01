; Kestrel 128 hardware harness: one Ultimate DOS command, outside the OS
; under test. Runs in C64 mode (REST run_prg). Assemble with
;   64tass -D TARGET=1|2 -D COMMAND=$07|$03 -o dos-context.prg dos-context.asm
; It sends [TARGET, COMMAND] with the register protocol of ultimate.inc and
; leaves the reply at $c100 (GPL v3 or later, see LICENSE):
;   $c100 result: $01 complete, $ff no interface, $fe interface not idle,
;         $fd timeout
;   $c101 data length, $c102 status length (each capped at 64)
;   $c103/$c104 $df1c/$df1d before the command
;   $c110.. data, $c180.. status text
;   $c000 = $aa once the result is stored
; Only one command per run: a later command in the same run has read a wrong
; identity byte from $df1d on the reference cartridge (2026-09-30).
ptr = $fb
cnt = $fd                       ; 3-byte timeout counter at $fd..$ff
REPLY = $c100

        * = $0801
        .word +, 10
        .byte $9e
        .text "2064"
        .byte 0
+       .word 0

        * = $0810
start:
        sei
        lda #0
        sta $c000
        tay
-       sta REPLY,y
        iny
        bne -
        lda #<REPLY
        sta ptr
        lda #>REPLY
        sta ptr+1
        lda $df1c
        sta REPLY+3
        lda $df1d
        sta REPLY+4
        cmp #$c9
        bne +
        lda $df1d
        cmp #$c9
        beq ++
+       jmp absent
+       lda $df1c
        and #$3f
        beq +
        jmp foreign             ; never abort another client's transaction
+
        lda #TARGET
        sta $df1d
        lda #COMMAND
        sta $df1d
        lda #1
        sta $df1c
        lda $df1c
        and #8
        bne timeout
wait:   jsr timer
wait_loop:
        lda $df1c
        and #$30
        cmp #$10
        bne packet
        jsr tick
        bcc wait_loop
        bcs timeout
packet: cmp #0
        beq complete
        jsr timer
data:   lda $df1c
        and #$80
        beq status
        lda $df1e
        ldy #1
        jsr store
        jsr tick
        bcc data
        bcs timeout
status: lda $df1c
        and #$40
        beq ack
        lda $df1f
        ldy #2
        jsr store
        jsr tick
        bcc status
        bcs timeout
ack:    lda #2
        sta $df1c
        jsr timer
ack_wait:
        lda $df1c
        and #2
        beq wait
        jsr tick
        bcc ack_wait
        bcs timeout
complete:
        lda #$01
        bne result
absent: lda #$ff
        bne result
foreign:
        lda #$fe
        bne result
timeout:
        lda #4                  ; abort only the command this probe sent
        sta $df1c
        lda #$fd
result: sta REPLY
        lda #$aa
        sta $c000
        cli
idle:   jmp idle

store:                          ; A = byte, Y = 1 (data) or 2 (status)
        pha
        lda (ptr),y
        cmp #64
        bcs full
        pha
        clc
        adc #1
        sta (ptr),y
        pla
        cpy #1
        bne +
        clc
        adc #$10
        bne ++
+       clc
        adc #$80
+       tay
        pla
        sta (ptr),y
        rts
full:   pla
        rts

timer:  lda #0
        sta cnt
        sta cnt+1
        sta cnt+2
        rts

tick:   inc cnt                 ; carry set after about 2^20 ticks
        bne +
        inc cnt+1
        bne +
        inc cnt+2
        lda cnt+2
        cmp #$10
        bcs ++
+       clc
        rts
+       sec
        rts
