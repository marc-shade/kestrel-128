; Native 640x200 VDC launcher. All mutable VRAM is backed by an owned handle.
; Foreground only, D=0 and IRQs enabled. Close before every app/workspace exit.
; A failed close retains the snapshot and blocks handoff until a retry succeeds.
; Register 28 selects addressing; an alias probe establishes physical capacity.
.weak
VD_DESKTOP_COMMON=1
VD_USE_STATUS_SURFACE=0
.endweak
.if VD_DESKTOP_COMMON
.weak
vd_initial_bitmap=vd_unpack
vd_initial_attributes=vd_render_all
.endweak
.include "../graphics/vdc-lifetime.inc"
.endif

; Packed scene uses non-overlapping earlier blocks, exploiting the VDC's
; block-copy unit. The build verifies every decoded byte and distance.
; The scene stays in the parent's image; vd_scene_read supplies each 256-byte
; page in N_BUFFER, preserving Y and reselecting the VDC data register.
vd_unpack:
        lda #0
        sta vd_scene_at
        sta vd_addr
        lda vd_base
        sta vd_addr+1
vd_token:
        jsr vd_next
        cmp #0
        beq vd_unpack_done
        bmi vd_copy_token
        cmp #64
        bcs vd_fill_token
        sta vd_length
        jsr vd_seek
        ldy vd_length
-       jsr vd_next
        jsr vd_putbyte
        dey
        bne -
        beq vd_token_advance
vd_fill_token:
        sec
        sbc #63
        sta vd_length
        jsr vd_seek
        jsr vd_next
        jsr vd_putbyte
        lda #0
        ldx #24
        jsr vd_setreg
        lda vd_length
        sec
        sbc #1
        beq vd_token_advance
        ldx #30
        jsr vd_setreg
        jmp vd_token_advance
vd_copy_token:
        sec
        sbc #125
        sta vd_length
        jsr vd_next
        sta vd_distance
        jsr vd_next
        sta vd_distance+1
        lda vd_addr
        sec
        sbc vd_distance
        pha
        lda vd_addr+1
        sbc vd_distance+1
        ldx #32
        jsr vd_setreg
        pla
        ldx #33
        jsr vd_setreg
        lda #$80
        ldx #24
        jsr vd_setreg
        jsr vd_seek
        lda vd_length
        ldx #30
        jsr vd_setreg
vd_token_advance:
        jsr vd_wait
        clc
        lda vd_addr
        adc vd_length
        sta vd_addr
        bcc +
        inc vd_addr+1
+       jmp vd_token
vd_unpack_done:
        rts
vd_next:
        ldx vd_scene_at
        bne +
        jsr vd_scene_read
+       lda N_BUFFER,x
        inx
        stx vd_scene_at
        rts

vd_select:
        lda vd_live
        beq vd_success
        lda vd_fault
        bne vd_return_fault
        jsr vd_gate
        jsr vd_hide_pointer
        jsr vd_render_selection
        jmp vd_success
vd_return_fault:
        sec
        rts
vd_render_all:                ; a new or restored scene: draw every card
        lda #$ff
        sta vd_shown
vd_render_selection:
        ; Only the cards whose highlight changes are rewritten: the one shown
        ; selected (vd_shown) and the new selection. vd_shown=$ff: all.
        lda vd_color
        beq vd_markers
        lda #0
        sta vd_row
        sta vd_addr
        lda #$80
        sta vd_addr+1
        lda #80
        sta vd_count
vd_color_row:
        ldx #6
-       lda vd_row
        sec
        sbc gd_card_rows,x
        cmp #2
        bcc +
        dex
        bpl -
+       jsr vd_card_changes   ; X: this row's card, or $ff
        bcc vd_color_skip
        lda #$2f
        ldy #79
-       sta N_BUFFER,y
        dey
        bpl -
        txa
        bmi vd_color_write
        lda #$1f
        cpx gd_selected
        bne +
        lda #$d0
+       ldy #75
-       sta N_BUFFER,y
        dey
        cpy #3
        bne -
vd_color_write:
        jsr vd_write_block
vd_color_skip:
        jsr vd_next_row
        inc vd_row
        lda vd_row
        cmp #25
        bne vd_color_row
vd_markers:
        lda #0
        sta vd_index
vd_marker:
        ldx vd_index
        jsr vd_card_changes
        bcc vd_marker_next
        lda pm_tops,x
        clc
        adc #4
        ldx #13
        jsr vd_xy
        ldy #0
-       jsr vd_seek
        lda #0
        ldx vd_index
        cpx gd_selected
        bne +
        lda vd_arrow,y
+       jsr vd_putbyte
        jsr vd_next_row
        iny
        cpy #8
        bne -
vd_marker_next:
        inc vd_index
        lda vd_index
        cmp #7
        bne vd_marker
        lda gd_selected
        sta vd_shown
        lda gd_launch_error
        beq vd_unpack_done
        ; The VIC error renderer has prepared the same ASCII label and digits.
        lda #176
        ldx #0
        jsr vd_xy
        lda #80
        sta vd_count
        lda #0
        sta vd_row
vd_status_row:
.if VD_USE_STATUS_SURFACE
        jsr vd_status_surface
.else
        lda #0
        ldx #79
-       sta N_BUFFER,x
        dex
        bpl -
        ldx #0
vd_status_glyph:
        lda gfx_text_buffer,x
        sec
        sbc #32
        sta vd_font_low
        lda #0
        sta vd_font_high
        asl vd_font_low
        rol vd_font_high
        asl vd_font_low
        rol vd_font_high
        asl vd_font_low
        rol vd_font_high
        lda vd_font_low
        clc
        adc #<gfx_font
        sta vd_glyph_load+1
        lda vd_font_high
        adc #>gfx_font
        sta vd_glyph_load+2
        ldy vd_row
vd_glyph_load:
        lda $ffff,y
        sta N_BUFFER+4,x
        inx
        cpx gfx_text_length
        bne vd_status_glyph
.endif
        jsr vd_write_block
        jsr vd_next_row
        inc vd_row
        lda vd_row
        cmp #8
        bne vd_status_row
        rts

.if VD_DESKTOP_COMMON
.include "../graphics/vdc-pointer.inc"
.include "../graphics/vdc-state.inc"
.endif
vd_card_changes:              ; carry set: card X's highlight must be drawn
        lda vd_shown
        bmi +                 ; nothing drawn yet: every row and card
        cpx gd_selected
        beq +
        cpx vd_shown
        beq +
        clc
        rts
+       sec
        rts
vd_shown: .byte $ff           ; the card drawn selected, $ff for none
vd_scene_at: .byte 0          ; next byte in the N_BUFFER scene page, 0: read
.include "vdc-arrow.inc"
.if VD_DESKTOP_COMMON
.include "../graphics/vdc-pointer-shape.inc"
.endif
