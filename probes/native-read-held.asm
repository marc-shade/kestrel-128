; One-shot native C128 IRQ observer that holds the foreground (GPL v3).
; For apps whose idle loop keeps using N_BUFFER ($3a00), such as AES clients:
; the IRQ stays in this handler while the host saves $3a00, lets the copy run,
; reads the result and puts $3a00 back, so the foreground never sees the
; borrow. No heap or KERNAL calls except INDFET ($ff74) for RAM.
; $3ff0 old IRQ, +2 done (1 ok, 2 host timeout, 4 bad command, 5 busy),
; +3 mode (0 RAM, 1 VDC memory), +4 bank (0/1, RAM), +5 source word, +7 count
; word (1..512), output at $3a00. VDC mode runs only when the foreground is
; idle at its input wait (N_READY = 1), so no VDC register access of its own
; is interrupted; otherwise it returns 5 at once and the host tries again. It
; restores the VDC update address (registers 18/19) and leaves register 31
; selected, as the ROM editor does.
; +11/+12 MMU mode/common registers; +13 interrupted foreground MMU config.
; +14 handshake: probe 1 held; host 2 copy; probe (after the copy) waits for
; host 3 release. Each wait gives up after about 20 seconds.
* = $3e00
        php
        pha
        txa
        pha
        tya
        pha
        tsx
        lda $0105,x            ; native IRQ additionally stacked the MMU
        sta $3ffd
        lda $d505
        sta $3ffb
        lda $d506
        sta $3ffc
        cld
        lda $fb
        pha
        lda $fc
        pha
        lda $fd
        pha
        lda $fe
        pha
        lda $3ff3
        beq +
        lda $3d12               ; VDC: only from the idle input wait
        bne +
        lda #5
        sta $3ff2
        jmp finish
+       lda #1                  ; held: the host may save $3a00 now
        sta $3ffe
        lda #2
        jsr handshake
        bcc +
        jmp timed_out
+       lda $3ff5
        sta $fb
        lda $3ff6
        sta $fc
        lda #0
        sta $fd
        lda #$3a
        sta $fe
        lda $3ff7
        sta left
        lda $3ff8
        sta left+1
        cmp #>512
        bcc count_low
        bne bad
        lda left
        cmp #<513
        bcs bad
count_low:
        lda left
        ora left+1
        beq bad
        lda $3ff4
        cmp #2
        bcs bad
        lda $3ff3
        beq copy
        cmp #1
        bne bad
        jmp vdc
bad:
        jmp invalid
copy:
        lda #$fb
        ldx $3ff4
        ldy #0
        jsr $ff74
        sta ($fd),y
        inc $fb
        bne +
        inc $fc
+       inc $fd
        bne +
        inc $fe
+       lda left
        bne +
        dec left+1
+       dec left
        lda left
        ora left+1
        bne copy
        lda #1
        bne copied
invalid:
        lda #4
copied:
        sta $3ff2               ; the host reads $3a00, restores it, releases
        lda #3
        jsr handshake
        jmp finish
timed_out:
        lda #2
        sta $3ff2
finish:
        lda $3ff0
        sta $0314
        lda $3ff1
        sta $0315
        pla
        sta $fe
        pla
        sta $fd
        pla
        sta $fc
        pla
        sta $fb
        pla
        tay
        pla
        tax
        pla
        plp
        jmp ($3ff0)
; VDC memory from $3ff5/6 to $3a00 through register 31 (auto-increment).
vdc:
        lda #18
        jsr vget
        sta oldaddr+1
        lda #19
        jsr vget
        sta oldaddr
        jsr vdc_seek            ; the 8563 prefetches on reads: address, one
        lda #31                 ; read to settle the latch, then address again
        jsr vget                ; (as vd_read_seek in graphics/vdc-lifetime.inc)
        jsr vdc_seek
        lda #31
        sta $d600
        ldy #0
vdc_byte:
        jsr vready
        bcs vdc_timeout
        lda $d601
        sta ($fd),y
        inc $fd
        bne +
        inc $fe
+       lda left
        bne +
        dec left+1
+       dec left
        lda left
        ora left+1
        bne vdc_byte
        lda #1
        .byte $2c               ; skip the next two bytes
vdc_timeout:
        lda #2
        pha
        lda #18
        ldx oldaddr+1
        jsr vput
        lda #19
        ldx oldaddr
        jsr vput
        lda #31
        sta $d600
        pla
        jmp copied
vdc_seek:                       ; update address = the requested source
        lda #18
        ldx $3ff6
        jsr vput
        lda #19
        ldx $3ff5
        jmp vput
vget:
        sta $d600
        jsr vready
        lda $d601
        rts
vput:
        sta $d600
        jsr vready
        stx $d601
        rts
vready:                         ; keeps X and Y
        lda #0
        sta vwait
-       bit $d600
        bmi +
        dec vwait
        bne -
        sec
        rts
+       clc
        rts
; Wait until $3ffe = A; carry set after about 20 seconds without it.
handshake:
        sta want
        lda #0
        sta wait
        sta wait+1
        lda #22
        sta wait+2
-       lda $3ffe
        cmp want
        beq +
        dec wait
        bne -
        dec wait+1
        bne -
        dec wait+2
        bne -
        sec
        rts
+       clc
        rts
left: .word 0
oldaddr: .word 0
vwait: .byte 0
want: .byte 0
wait: .fill 3,0
        .cerror * > $3ff0, "held capture exceeds private scratch region"
