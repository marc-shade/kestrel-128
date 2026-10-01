; A checked, already initialized surface; no implicit allocation or clearing.
display_prepare:
        ldx #>N_APPBASE
display_app_pages:
        lda NPAGES0,x
        cmp l_app_handle
        beq +
        lda #N_BADHANDLE
        jmp heap_finish
+       inx
        cpx field_app_end
        bne display_app_pages
        lda hbank
        bne display_range
        lda hstart
        cmp #$c0
        bne display_range
        lda hleft
        cmp #36
        beq +
display_range:
        lda #N_RANGE
        jmp heap_finish
+       lda $d506
        and #$40
        ora $d8
        bne display_bad_mode
        lda $00
        and #6
        cmp #6
        bne display_bad_mode
        lda $d01a
        and #15
        cmp #1
        bne display_bad_mode
        lda $d011
        and #$60
        bne display_bad_mode
        lda $d016
        and #$10
        bne display_bad_mode
        lda $d015
        bne display_bad_mode    ; sprite storage has no native ownership contract yet
        lda $dd02
        and #3
        cmp #3
        beq +
display_bad_mode:
        lda #N_PLATFORM
        jmp heap_finish
+       sei
        lda $d011
        and #$7f
        sta v_d011
        lda $d016
        sta v_d016
        lda $d018
        sta v_d018
        lda $dd00
        and #3
        sta v_bank
        lda $01
        and #6
        sta v_port
        lda #$ff
        sta $d8
        sta $d012
        lda $01
        and #$fd
        ora #4
        sta $01
        lda #$80
        sta $d018
        lda #8                 ; known 40-column bitmap geometry, restored on exit
        sta $d016
        lda #$3b               ; 25 rows, standard scroll, raster compare high bit 0
        sta $d011
        lda $dd00
        and #$fc
        sta $dd00
        lda htag
        sta v_tag
        jmp heap_success      ; restores the caller's original D/I
native_display_show_end:
