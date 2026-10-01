; Fixed native C128 mode snapshot through the existing bounded IRQ borrower.
; Read only the listed registers; no FIFO, collision or IRQ-acknowledge reads.
; Same metadata/old-IRQ record as native-read.asm, fixed 15-byte output at $3a00.
* = $3e00
        php
        pha
        txa
        pha
        tya
        pha
        tsx
        lda $0105,x            ; interrupted foreground MMU, stacked by C128 ROM
        sta $3ffd
        sta $3a00
        lda $d505
        sta $3ffb
        sta $3a01
        lda $d506
        sta $3ffc
        sta $3a02
        lda $00
        sta $3a03
        lda $01
        sta $3a04
        lda $d011
        sta $3a05
        lda $d015
        sta $3a06
        lda $d016
        sta $3a07
        lda $d018
        sta $3a08
        lda $d01a
        sta $3a09
        lda $dd00
        sta $3a0a
        lda $dd02
        sta $3a0b
        lda $d7
        sta $3a0c
        lda $d8
        sta $3a0d
        lda $d030
        sta $3a0e
        lda $3ff0
        sta $0314
        lda $3ff1
        sta $0315
        lda #1
        sta $3ff2
        pla
        tay
        pla
        tax
        pla
        plp
        jmp ($3ff0)
        .cerror * > $3ff0, "native mode snapshot overlaps command record"
