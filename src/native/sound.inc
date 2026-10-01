; Sound (docs/NATIVE-SERVICES.md), GPL v3: the SID bell. Voice 1 plays a
; short triangle tone that decays by itself (sustain 0), like the ST's bell.
; No kernel calls; the SID is at $d400 in the native app mapping.
SD_BELL_FREQ = 14985            ; 880 Hz on a PAL C128 (985,248 Hz clock)
sd_bell:
        lda #0
        sta $d404               ; gate off: the next gate on restarts the envelope
        lda #<SD_BELL_FREQ
        sta $d400
        lda #>SD_BELL_FREQ
        sta $d401
        lda #$09                ; attack 2 ms, decay 750 ms
        sta $d405
        lda #$00                ; sustain 0, release 6 ms
        sta $d406
        lda #$0f                ; volume 15, no filter ($d418 is write-only)
        sta $d418
        lda #$11                ; triangle, gate on
        sta $d404
        rts
; A key click: a short burst of noise on voice 1 (attack 2 ms, decay 6 ms).
sd_click:
        lda #0
        sta $d404
        sta $d400
        sta $d405               ; attack 2 ms, decay 6 ms
        sta $d406               ; sustain 0, release 6 ms
        lda #$40                ; a high noise rate
        sta $d401
        lda #$0f
        sta $d418
        lda #$81                ; noise, gate on
        sta $d404
        rts
