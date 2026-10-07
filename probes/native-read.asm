; One-shot native C128 IRQ observer. No heap calls or C64 interrupt offsets.
; Borrow $3a00..$3bff and $3e00..$3fff while idle, with no allocations
; or user input during the probe. The host restores both reserved buffers.
; Low memory contains resident kernel code and is never used as output.
; $3ff0 old IRQ, +2 done (1 ok, 2 timeout, 3 drift, 4 bad command),
; +3 mode (0 RAM / 1 VDC), +4 bank (0/1), +5 source word, +7 count word.
; Output at $3a00, at most 512 bytes. +9 resynchronization count word.
; +11/+12 MMU mode/common registers; +13 interrupted foreground MMU config.
; +14 host release (nonzero), +15 1 when the hold gave up before a release.
; $3fee: IRQs that found the foreground busy and left the hook armed.
;
; An idle app still runs its own work between input polls (an 80-column
; app's pointer update calls the bank-1 VDC service through N_BUFFER), so
; the copy runs only from an IRQ that finds the foreground at its input wait
; (N_READY = 1) in the native map; any other IRQ passes straight through
; and the next one tries again. After the copy the probe stays in the IRQ
; until the host has read $3a00 and put it back, so the foreground never
; sees the borrow.
.weak
HOLD_PAGES = 0                  ; 256 x 65536 polls: about 3 minutes at 1 MHz
.endweak
skips = $3fee
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
        lda $02aa
        pha
        lda $3ffc               ; common RAM: the native 1 KiB bottom area
        and #15
        cmp #4
        bne busy
        bit $3ffb
        bvs busy
        lda $3ffd               ; interrupted map: $00 (nested IRQ) or $0e
        and #$f1
        bne busy
        lda $3d12               ; N_READY: the foreground waits for input
        cmp #1
        beq idle
busy:
        inc skips
        jmp restore_registers   ; the hook stays armed for the next IRQ
idle:
        lda $3ff5
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
        bne invalid
        lda left
        cmp #<513
        bcs invalid
count_low:
        lda left
        ora left+1
        beq invalid
        lda $3ff4
        cmp #2
        bcs invalid
        lda $3ff3
        cmp #2
        bcs invalid
        cmp #1
        beq vdc_start
ram_loop:
        lda #$fb
        ldx $3ff4
        ldy #0
        jsr $ff74
        sta ($fd),y
        jsr advance
        bne ram_loop
        lda #1
        jmp finish
invalid:
        lda #4
        jmp finish
vdc_start:
        lda #18
        sta $d600
        jsr ready
        bcs initial_timeout
        lda $d601
        sta oldaddr+1
        lda #19
        sta $d600
        jsr ready
        bcs initial_timeout
        lda $d601
        sta oldaddr
        jmp vdc_cell
initial_timeout:
        lda #2
        jmp finish
vdc_cell:
        lda #3
        sta attempts
vdc_retry:
        lda #18
        sta $d600
        jsr ready
        bcs timeout
        lda $fc
        sta $d601
        lda #19
        sta $d600
        jsr ready
        bcs timeout
        lda $fb
        sta $d601
        lda #31
        sta $d600
        jsr ready
        bcs timeout
        lda $d601
        ldy #0
        sta ($fd),y
        inc $fb
        bne verify
        inc $fc
verify:
        lda #18
        sta $d600
        jsr ready
        bcs timeout
        lda $d601
        cmp $fc
        bne drift
        lda #19
        sta $d600
        jsr ready
        bcs timeout
        lda $d601
        cmp $fb
        bne drift
        jsr advance_output
        bne vdc_cell
        lda #1
        bne vdc_finish
drift:
        lda $fb
        bne drift_low
        dec $fc
drift_low:
        dec $fb
        inc $3ff9
        bne again
        inc $3ffa
again:
        dec attempts
        bne vdc_retry
        lda #3
        bne vdc_finish
timeout:
        lda #2
vdc_finish:
        pha
        lda #18
        sta $d600
        jsr ready
        bcs restore_failed
        lda oldaddr+1
        sta $d601
        lda #19
        sta $d600
        jsr ready
        bcs restore_failed
        lda oldaddr
        sta $d601
        pla
        jmp finish
restore_failed:
        pla
        lda #2
finish:
        sta $3ff2
        lda #HOLD_PAGES         ; X and Y count the inner polls
        sta $fb
hold:
        lda $3ffe
        bne released
        dex
        bne hold
        dey
        bne hold
        dec $fb
        bne hold
        inc $3fff               ; no release came; the host must not trust $3a00
released:
        lda $3ff0
        sta $0314
        lda $3ff1
        sta $0315
restore_registers:
        pla
        sta $02aa
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
advance:
        inc $fb
        bne advance_output
        inc $fc
advance_output:
        inc $fd
        bne output_ok
        inc $fe
output_ok:
        lda left
        bne left_low
        dec left+1
left_low:
        dec left
        lda left
        ora left+1
        rts
ready:
        ldx #0
ready_loop:
        bit $d600
        bmi ready_ok
        dex
        bne ready_loop
        sec
        rts
ready_ok:
        clc
        rts
left: .word 0
attempts: .byte 0
oldaddr: .word 0
        .cerror * > skips, "native capture exceeds private scratch region"
