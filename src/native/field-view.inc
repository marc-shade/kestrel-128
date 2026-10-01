; A focused field owns WIDTH cells at the current VIC/VDC console position.
; Two edge cells indicate clipping; the inner cells include the caret.
field_draw:
        php
        jsr field_start
        bcc +
        jmp field_early
+       lda N_UIWIDTH
        cmp #3
        bcc field_draw_invalid
        cmp #80
        bcs field_draw_invalid
        lda #40
        bit $d7
        bpl +
        lda #80
+       sta field_columns
        sec
        jsr $fff0
        cpx #25
        bcs field_draw_invalid
        tya
        clc
        adc N_UIWIDTH
        bcs field_draw_invalid
        cmp field_columns
        bcs field_draw_invalid
        lda N_UIWIDTH
        sec
        sbc #2
        sta field_capacity
        lda field_state+UI_LENGTH
        cmp field_state+UI_CARET
        bcc field_draw_invalid
        lda $d7
        and #$80
        beq +
        ldx #UI_VIEW80
        bne field_draw_view
+       ldx #UI_VIEW40
field_draw_view:
        stx field_view_index
        lda field_state+UI_LENGTH
        sec
        sbc field_capacity
        bcs +
        lda #$ff
+       clc
        adc #1
        cmp field_state,x
        bcs +
        sta field_state,x
+
        lda field_state,x
        cmp field_state+UI_CARET
        bcc +
        lda field_state+UI_CARET
        sta field_state,x
+       lda field_state+UI_CARET
        sec
        sbc field_state,x
        cmp field_capacity
        bcc field_draw_begin
        lda field_state+UI_CARET
        sec
        sbc field_capacity
        clc
        adc #1
        sta field_state,x
field_draw_begin:
        lda field_state,x
        sta field_at
        lda #$92
        jsr field_chrout
        lda #32
        ldx field_at
        beq +
        lda #$3c
+       jsr field_chrout
        lda field_capacity
        sta field_left_count
field_draw_character:
        ldx field_at
        cpx field_state+UI_CARET
        bne +
        lda #$12
        jsr field_chrout
+       ldx field_at
        cpx field_state+UI_LENGTH
        bcs field_draw_blank
        jsr field_read
        cmp #32
        bcc field_draw_dot
        cmp #127
        bcc field_draw_put
field_draw_dot:
        lda #$2e
        bne field_draw_put
field_draw_blank:
        lda #32
field_draw_put:
        jsr field_chrout
        ldx field_at
        cpx field_state+UI_CARET
        bne +
        lda #$92
        jsr field_chrout
+       inc field_at
        dec field_left_count
        bne field_draw_character
        ldx field_view_index
        lda field_state+UI_LENGTH
        sec
        sbc field_state,x
        cmp field_capacity
        beq field_draw_last_blank
        bcc field_draw_last_blank
        lda #$3e
        bne field_draw_last
field_draw_last_blank:
        lda #32
field_draw_last:
        jsr field_chrout
        jmp field_finish
field_draw_invalid:
        jmp field_invalid
field_chrout:
        pha
        lda #0
        sta $f4
        pla
        jmp $ffd2
