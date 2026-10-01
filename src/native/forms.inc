; Native forms (docs/NATIVE-FORMS.md), GPL v3: GEM-style dialogs drawn on the
; app's VIC surface with the graphics core. Needs graphics-core.inc,
; text-core.inc and input/pointer.inc; the app binds the graphics core and
; sets fo_surface before fo_open. The app defines FO_PRESENT: 1 when it mirrors
; its surface to the VDC with graphics/vdc-mirror.inc and supplies ae_present
; (called once per dialog-loop pass), else 0.
FOT_TEXT = 1
FOT_BUTTON = 2
FOT_CHECK = 3
FOT_RADIO = 4
FOT_FIELD = 5
FOF_DEFAULT = 1                  ; flags
FOF_EXIT = 2
FOF_CANCEL = 4
FOS_SELECTED = 1                 ; state
FOS_DISABLED = 2
FOC_PAPER = $61
FOC_FOCUS = $07
FOC_GREY = $c1
FOT_MAX_OBJECTS = 32

; ---- open, close -------------------------------------------------------------------
; A/X = form. Carry set: A = error (N_BADARG for a bad header).
fo_open:
        sta fo_ptr
        stx fo_ptr+1
        sta fo_hdr+1
        stx fo_hdr+2
        ldy #4
fo_hdr:
        lda $ffff,y
        sta fo_x,y
        dey
        bpl fo_hdr
        lda fo_n
        beq fo_bad
        cmp #FOT_MAX_OBJECTS+1
        bcs fo_bad
        lda fo_w
        cmp #3
        bcc fo_bad
        cmp #39
        bcs fo_bad
        lda fo_h
        cmp #3
        bcc fo_bad
        cmp #24
        bcs fo_bad
        lda fo_x
        cmp #$ff
        bne fo_placed
        lda #40                 ; centred below the menu bar
        sec
        sbc fo_w
        lsr
        sta fo_x
        lda #25
        sec
        sbc fo_h
        lsr
        bne +
        lda #1
+       sta fo_y
fo_placed:
        lda fo_y
        beq fo_bad
        clc
        adc fo_h
        cmp #26
        bcs fo_bad
        lda fo_x
        clc
        adc fo_w
        cmp #41
        bcs fo_bad
        jsr fo_transfer_alloc   ; save the cells under the form
        bcs fo_open_done
        ldx #0                  ; fields: caret at the end
fo_init_fields:
        stx fo_i
        jsr fo_fetch
        lda fo_type
        cmp #FOT_FIELD
        bne +
        jsr fo_uiptr
        lda #0
        sta N_UIKEY
        jsr N_FEDIT
        bcs fo_open_free
+       ldx fo_i
        inx
        cpx fo_n
        bne fo_init_fields
        lda #$ff
        sta fo_focus
        lda #1                  ; a press held from before is not a click
        sta fo_prev_button
        jsr fo_next
        jsr fo_draw_all
fo_open_done:
        rts
fo_open_free:                   ; nothing is drawn yet: drop the saved copy
        pha
        jsr fo_select_save
        jsr N_FREE
        pla
        sec
        rts
fo_bad:
        lda #N_BADARG
        sec
        rts

; Restore the cells under the form and free the saved copy.
fo_close:
        lda #1                  ; saved copy -> surface
        jsr fo_transfer
        php
        pha
.if FO_PRESENT
        jsr fo_mark_rows        ; a raw copy, unseen by the graphics core's tracking
.fi
        jsr fo_select_save
        jsr N_FREE
        pla
        plp
        rts
.if FO_PRESENT
; Mark the form's cell rows for the app's VDC mirror (vm_rows/vm_pending of
; graphics/vdc-mirror.inc, as its vm_dirty marks gfx drawing); the app's next
; ae_present sends them.
fo_mark_rows:
        ldx fo_y
        ldy fo_h
        beq +
        lda #1
        sta vm_pending
-       sta vm_rows,x
        inx
        dey
        bne -
+       rts
.fi

; X = object: draw it again (after the app changed its state or text).
fo_redraw:
        jsr fo_draw_obj
        php
        pha
        jsr gfx_clip_defaults
        pla
        plp
        rts

; ---- the dialog loop ----------------------------------------------------------------------
; Until an exit object is pressed: A = its index, carry clear. Carry set: A =
; error from drawing, the heap or N_FEDIT.
fo_do:
.if FO_PRESENT
        jsr ae_present          ; the app's VDC mirror: rows the dialog redrew
.fi
        lda #1
        sta N_READY
        jsr N_KEYIN
        ldx #0
        stx N_READY
        sta fo_key
        jsr pm_poll
        ldx #0                  ; a press is a change from up to down
        lda pm_buttons
        beq +
        lda fo_prev_button
        bne +
        inx
+       stx fo_press
        lda pm_buttons
        beq +
        lda #1
+       sta fo_prev_button
        lda fo_key
        beq +
        jsr fo_key_act
        bcs fo_do_result
+       lda fo_press
        beq fo_do
        jsr fo_click
        bcc fo_do
fo_do_result:                   ; carry set: fo_exit holds the exit, or $ff
-       lda pm_buttons          ; left with the pointer: the press ends here, at
        beq +                   ; its release, so the caller never sees it
        lda #1
        sta N_READY
        jsr N_KEYIN             ; (idle; a key typed meanwhile is dropped)
        ldx #0
        stx N_READY
        jsr pm_poll
        jmp -
+       lda fo_exit
        cmp #$ff
        beq +
        clc
        rts
+       lda fo_error
        sec
        rts
; Acting routines return carry set to leave fo_do: fo_exit = the object, or
; $ff with fo_error set.
fo_fail:
        sta fo_error
        lda #$ff
        sta fo_exit
        sec
        rts
fo_continue:
        clc
        rts

fo_key_act:
        cmp #27                 ; Esc: the cancel object
        bne +
        lda #FOF_CANCEL
        jmp fo_press_flagged
+       cmp #13
        bne +
        ldx fo_focus            ; Return: the focused button, else the default
        cpx #$ff
        beq fo_return_default
        jsr fo_fetch
        lda fo_type
        cmp #FOT_BUTTON
        bne fo_return_default
        ldx fo_focus
        jmp fo_act
fo_return_default:
        lda #FOF_DEFAULT
        jmp fo_press_flagged
+       cmp #9                  ; Tab, cursor down: next
        beq fo_key_next
        cmp #$11
        beq fo_key_next
        cmp #$91
        bne fo_key_other
        jsr fo_prev
        jmp fo_focus_moved
fo_key_next:
        jsr fo_next
fo_focus_moved:
        bcs fo_fail
        clc
        rts
fo_key_other:
        ldx fo_focus
        cpx #$ff
        beq fo_continue
        jsr fo_fetch
        lda fo_type
        cmp #FOT_FIELD
        beq fo_edit
        lda fo_key              ; Space acts on the focused object
        cmp #32
        bne fo_continue
        ldx fo_focus
        jmp fo_act
fo_edit:
        jsr fo_uiptr
        lda fo_key
        sta N_UIKEY
        jsr N_FEDIT
        bcs fo_fail
        ldx fo_focus
        jsr fo_draw_obj
        bcs fo_fail
        jsr gfx_clip_defaults
        clc
        rts
; A = flag: act on the first enabled object with it.
fo_press_flagged:
        sta fo_flag
        ldx #0
-       stx fo_i
        jsr fo_fetch
        lda fo_flags
        and fo_flag
        beq +
        lda fo_state
        and #FOS_DISABLED
        bne +
        ldx fo_i
        jmp fo_act
+       ldx fo_i
        inx
        cpx fo_n
        bne -
        clc
        rts

; A press: the object under the pointer takes focus and acts (fields: focus).
fo_click:
        lda pm_x+1              ; pointer cell
        lsr
        lda pm_x
        ror
        lsr
        lsr
        sta fo_cx
        lda pm_y
        lsr
        lsr
        lsr
        sta fo_cy
        ldx #0
fo_hit:
        stx fo_i
        jsr fo_fetch
        jsr fo_focusable
        bcc fo_hit_next
        lda fo_cx
        sec
        sbc fo_ax
        bcc fo_hit_next
        cmp fo_ow
        bcs fo_hit_next
        lda fo_cy
        sec
        sbc fo_ay
        bcc fo_hit_next
        cmp fo_rows
        bcs fo_hit_next
        ldx fo_i
        jsr fo_set_focus
        bcs fo_click_fail
        lda fo_type
        cmp #FOT_FIELD
        beq fo_continue
        ldx fo_i
        jmp fo_act
fo_hit_next:
        ldx fo_i
        inx
        cpx fo_n
        bne fo_hit
        clc
        rts
fo_click_fail:
        jmp fo_fail

; X = object: act. Buttons with the exit (or cancel) flag leave fo_do;
; checkboxes toggle; a radio button clears the rest of its group.
fo_act:
        stx fo_i
        jsr fo_fetch
        lda fo_state
        and #FOS_DISABLED
        bne fo_continue
        lda fo_type
        cmp #FOT_BUTTON
        bne +
        lda fo_flags
        and #FOF_EXIT|FOF_CANCEL
        beq fo_continue
        lda fo_i
        sta fo_exit
        sec
        rts
+       cmp #FOT_CHECK
        bne +
        lda fo_state
        eor #FOS_SELECTED
        jsr fo_put_state
        ldx fo_i
        jsr fo_draw_obj
        bcs fo_act_fail
        jmp fo_act_done
+       cmp #FOT_RADIO
        bne fo_continue
        lda fo_flags
        and #$f0
        sta fo_flag             ; the group
        lda fo_i
        sta fo_target
        ldx #0
fo_radio_loop:
        stx fo_i
        jsr fo_fetch
        lda fo_type
        cmp #FOT_RADIO
        bne fo_radio_next
        lda fo_flags
        and #$f0
        cmp fo_flag
        bne fo_radio_next
        lda fo_state
        and #255-FOS_SELECTED
        ldx fo_i
        cpx fo_target
        bne +
        ora #FOS_SELECTED
+       cmp fo_state
        beq fo_radio_next
        jsr fo_put_state
        ldx fo_i
        jsr fo_draw_obj
        bcs fo_act_fail
fo_radio_next:
        ldx fo_i
        inx
        cpx fo_n
        bne fo_radio_loop
fo_act_done:
        jsr gfx_clip_defaults
        clc
        rts
fo_act_fail:
        jmp fo_fail

; ---- focus -----------------------------------------------------------------------------------
; Carry set on a drawing error (A).
fo_next:
        ldx fo_focus
        lda fo_n
        sta fo_count
-       inx
        cpx fo_n
        bcc +
        ldx #0
+       stx fo_i
        jsr fo_fetch
        jsr fo_focusable
        bcs +
        ldx fo_i
        dec fo_count
        bne -
        clc
        rts
+       ldx fo_i
        jmp fo_set_focus
fo_prev:
        ldx fo_focus
        lda fo_n
        sta fo_count
-       dex
        bpl +
        ldx fo_n
        dex
+       stx fo_i
        jsr fo_fetch
        jsr fo_focusable
        bcs +
        ldx fo_i
        dec fo_count
        bne -
        clc
        rts
+       ldx fo_i
; X = object: move the focus there, drawing the old and new objects.
fo_set_focus:
        lda fo_focus
        stx fo_focus
        cmp fo_focus
        beq fo_focus_same
        cmp #$ff
        beq +
        tax
        jsr fo_draw_obj
        bcs fo_focus_done
+       ldx fo_focus
        jsr fo_draw_obj
        bcs fo_focus_done
fo_focus_same:
        jsr gfx_clip_defaults
        clc
fo_focus_done:
        php
        pha
        ldx fo_i                ; callers expect fo_o to be this object
        jsr fo_fetch
        pla
        plp
        rts
; After fo_fetch: carry set if the object can take focus.
fo_focusable:
        lda fo_type
        cmp #FOT_BUTTON
        bcc +
        cmp #FOT_FIELD+1
        bcs +
        lda fo_state
        and #FOS_DISABLED
        bne +
        sec
        rts
+       clc
        rts

; ---- objects ------------------------------------------------------------------------------------
; X = object -> fo_type.. (8 bytes), fo_ax/fo_ay (screen cells), fo_ow
; (width), fo_rows (height in rows).
fo_fetch:
        txa
        asl
        asl
        asl
        clc
        adc #5
        clc
        adc fo_ptr
        sta fo_obj_rd+1
        sta fo_obj_wr+1
        lda fo_ptr+1
        adc #0
        sta fo_obj_rd+2
        sta fo_obj_wr+2
        ldy #7
fo_obj_rd:
        lda $ffff,y
        sta fo_type,y
        dey
        bpl fo_obj_rd
        lda fo_x
        clc
        adc fo_ox
        sta fo_ax
        lda fo_y
        clc
        adc fo_oy
        sta fo_ay
        ldy #1
        lda fo_type
        cmp #FOT_BUTTON
        bne +
        iny
+       sty fo_rows
        rts
; A = the fetched object's new state byte.
fo_put_state:
        sta fo_state
        ldy #2
fo_obj_wr:
        sta $ffff,y
        rts
; The fetched field's record -> N_UIPTR.
fo_uiptr:
        lda fo_spec
        sta N_UIPTR
        lda fo_spec+1
        sta N_UIPTR+1
        rts

; ---- drawing ----------------------------------------------------------------------------------
; The frame like an AES alert: two one-pixel rings, then every object.
fo_draw_all:
        lda fo_x
        sta fo_c0x
        clc
        adc fo_w
        sta fo_c1x
        lda fo_y
        sta fo_c0y
        clc
        adc fo_h
        sta fo_c1y
        ldx #0
-       stx fo_inset
        txa
        and #1                  ; insets 0 2 4 clear, 1 3 ink
        jsr fo_box
        bcs fo_draw_done
        ldx fo_inset
        inx
        cpx #5
        bne -
        lda #FOC_PAPER
        jsr fo_cells
        bcs fo_draw_done
        ldx #0
-       stx fo_j
        jsr fo_draw_obj
        bcs fo_draw_done
        ldx fo_j
        inx
        cpx fo_n
        bne -
        jsr gfx_clip_defaults
        clc
fo_draw_done:
        rts

; X = object. Carry set on a graphics error.
fo_draw_obj:
        stx fo_i
        jsr fo_fetch
        lda #FOC_PAPER           ; its colour
        sta fo_color
        lda fo_state
        and #FOS_DISABLED
        beq +
        lda #FOC_GREY
        sta fo_color
        bne ++
+       lda fo_i
        cmp fo_focus
        bne +
        lda fo_type
        cmp #FOT_FIELD           ; a field shows focus at its caret only
        beq +
        lda #FOC_FOCUS
        sta fo_color
+       lda fo_ax               ; its cells, cleared
        sta fo_c0x
        clc
        adc fo_ow
        sta fo_c1x
        lda fo_ay
        sta fo_c0y
        clc
        adc fo_rows
        sta fo_c1y
        lda #0
        sta fo_inset
        jsr fo_box              ; A = 0: clear
        bcs fo_draw_done
        lda fo_type
        cmp #FOT_BUTTON
        beq fo_draw_button
        cmp #FOT_CHECK
        beq fo_draw_toggle
        cmp #FOT_RADIO
        beq fo_draw_toggle
        cmp #FOT_FIELD
        bne +
        jmp fo_draw_field
+       jsr fo_label            ; text
        lda fo_ax
        jsr fo_text_at_row
        bcs fo_draw_done
        jmp fo_draw_colors
fo_draw_button:
        lda #1                  ; a one-pixel frame; the default has two
        jsr fo_box
        bcs fo_draw_done
        inc fo_inset
        lda #0
        jsr fo_box
        bcs fo_draw_done
        lda fo_flags
        and #FOF_DEFAULT
        beq +
        lda #1
        jsr fo_box
        bcs fo_draw_done
        inc fo_inset
        lda #0
        jsr fo_box
        bcs fo_draw_done
+       jsr fo_label            ; centred label, 4 pixels down
        lda fo_ow
        sec
        sbc gfx_text_length
        lsr
        clc
        adc fo_ax
        jsr fo_times8
        sta gfx_x0
        stx gfx_x0+1
        lda fo_ay
        jsr fo_times8
        clc
        adc #4
        sta gfx_y0
        txa
        adc #0
        sta gfx_y0+1
        jsr fo_text
        bcs fo_draw_fail
        jmp fo_draw_colors
fo_draw_toggle:
        lda fo_state            ; glyph: box or circle, empty or marked
        and #FOS_SELECTED
        sta fo_t8
        lda fo_type
        sec
        sbc #FOT_CHECK
        asl
        ora fo_t8
        asl
        asl
        asl
        tay
        ldx #0
-       lda fo_glyphs,y
        sta gfx_bits,x
        iny
        inx
        cpx #8
        bne -
        lda fo_ax
        jsr fo_times8
        sta gfx_x0
        stx gfx_x0+1
        lda fo_ay
        jsr fo_times8
        sta gfx_y0
        stx gfx_y0+1
        lda #3
        sta gfx_pen
        jsr gfx_glyph
        bcs fo_draw_fail
        jsr fo_label
        lda fo_ax
        clc
        adc #2
        jsr fo_text_at_row
        bcs fo_draw_fail
fo_draw_colors:
        lda fo_color
        jmp fo_cells
fo_draw_fail:
        rts
; A field: the visible part of its text, an underline, and its caret.
fo_draw_field:
        lda fo_spec             ; record: length, caret, max, buffer, view
        sta fo_rec_rd+1
        sta fo_rec_wr+1
        lda fo_spec+1
        sta fo_rec_rd+2
        sta fo_rec_wr+2
        ldy #5
fo_rec_rd:
        lda $ffff,y
        sta fo_rec,y
        dey
        bpl fo_rec_rd
        lda fo_rec+1            ; keep the caret inside the view
        cmp fo_rec+5
        bcs +
        sta fo_rec+5
+       lda fo_rec+1
        sec
        sbc fo_rec+5
        cmp fo_ow
        bcc +
        lda fo_rec+1
        sec
        sbc fo_ow
        clc
        adc #1
        sta fo_rec+5
+       lda fo_rec+5
        ldy #5
fo_rec_wr:
        sta $ffff,y
        lda fo_rec+3            ; the visible bytes
        clc
        adc fo_rec+5
        sta fo_buf_rd+1
        lda fo_rec+4
        adc #0
        sta fo_buf_rd+2
        lda fo_rec
        sec
        sbc fo_rec+5
        bcs +
        lda #0
+       cmp fo_ow
        bcc +
        lda fo_ow
+       sta gfx_text_length
        ldy #0
        beq fo_buf_test
fo_buf_rd:
        lda $ffff,y
        sta gfx_text_buffer,y
        iny
fo_buf_test:
        cpy gfx_text_length
        bne fo_buf_rd
        lda fo_ax
        jsr fo_text_at_row
        bcs fo_field_done
        lda #1                  ; underline: the cells' last pixel row
        sta gfx_pen
        lda fo_ax
        jsr fo_times8
        sta gfx_x0
        stx gfx_x0+1
        lda fo_c1x
        jsr fo_times8
        sta gfx_x1
        stx gfx_x1+1
        lda fo_ay
        jsr fo_times8
        clc
        adc #7
        sta gfx_y0
        txa
        adc #0
        sta gfx_y0+1
        lda gfx_y0
        clc
        adc #1
        sta gfx_y1
        lda gfx_y0+1
        adc #0
        sta gfx_y1+1
        jsr gfx_rect
        bcs fo_field_done
        lda fo_color
        jsr fo_cells
        bcs fo_field_done
        lda fo_i                ; focused: the caret cell
        cmp fo_focus
        bne fo_field_ok
        lda fo_rec+1
        sec
        sbc fo_rec+5
        clc
        adc fo_ax
        sta fo_c0x
        sta fo_c1x
        inc fo_c1x
        lda #FOC_FOCUS
        jmp fo_cells
fo_field_ok:
        clc
fo_field_done:
        rts

; Text of the fetched object (at most its width, 38) -> gfx_text_buffer.
fo_label:
        lda fo_spec
        sta fo_label_rd+1
        lda fo_spec+1
        sta fo_label_rd+2
        ldy #0
fo_label_rd:
        lda $ffff,y
        beq +
        sta gfx_text_buffer,y
        iny
        cpy fo_ow
        bcs +
        cpy #38
        bne fo_label_rd
+       sty gfx_text_length
        rts
; A = cell column: gfx_text_buffer at that column on the object's row.
fo_text_at_row:
        jsr fo_times8
        sta gfx_x0
        stx gfx_x0+1
        lda fo_ay
        jsr fo_times8
        sta gfx_y0
        stx gfx_y0+1
fo_text:
        lda gfx_text_length
        beq +
        lda #1
        sta gfx_pen
        jmp gfx_text
+       clc
        rts
; Rectangle of cells fo_c0x..fo_c1x, fo_c0y..fo_c1y, inset fo_inset pixels,
; pen A (0 clear, 1 ink).
fo_box:
        sta gfx_pen
        lda fo_c0x
        jsr fo_times8
        clc
        adc fo_inset
        sta gfx_x0
        txa
        adc #0
        sta gfx_x0+1
        lda fo_c0y
        jsr fo_times8
        clc
        adc fo_inset
        sta gfx_y0
        txa
        adc #0
        sta gfx_y0+1
        lda fo_c1x
        jsr fo_times8
        sec
        sbc fo_inset
        sta gfx_x1
        txa
        sbc #0
        sta gfx_x1+1
        lda fo_c1y
        jsr fo_times8
        sec
        sbc fo_inset
        sta gfx_y1
        txa
        sbc #0
        sta gfx_y1+1
        jmp gfx_rect
; Colour A over cells fo_c0x..fo_c1x, fo_c0y..fo_c1y.
fo_cells:
        sta gfx_color
        lda #0
        sta gfx_x0+1
        sta gfx_x1+1
        sta gfx_y0+1
        sta gfx_y1+1
        lda fo_c0x
        sta gfx_x0
        lda fo_c1x
        sta gfx_x1
        lda fo_c0y
        sta gfx_y0
        lda fo_c1y
        sta gfx_y1
        jmp gfx_colors
fo_times8:                      ; A*8 -> A lo, X hi
        ldx #0
        stx fo_t8
        asl
        rol fo_t8
        asl
        rol fo_t8
        asl
        rol fo_t8
        ldx fo_t8
        rts

; ---- save-under ------------------------------------------------------------------------------
; Allocate the copy (w*h*9 bytes), then A = 0: save.
fo_transfer_alloc:
        lda fo_w
        ldx fo_h
        jsr fo_mul              ; cells
        lda fo_prod             ; *9 = *8 + *1
        sta fo_bytes
        lda fo_prod+1
        sta fo_bytes+1
        ldx #3
-       asl fo_prod
        rol fo_prod+1
        dex
        bne -
        lda fo_prod
        clc
        adc fo_bytes
        lda fo_prod+1
        adc fo_bytes+1
        clc
        adc #1                  ; pages, rounded up
        sta N_PAGES
        lda N_CURRENT
        sta N_OWNER
        lda #$ff
        sta N_BANK
        jsr N_ALLOC
        bcs fo_transfer_done
        ldx #3
-       lda N_HANDLE,x
        sta fo_save,x
        dex
        bpl -
        lda #0
        jsr fo_transfer
        bcc +
        jmp fo_open_free
+       rts
; A = 0: surface -> copy; 1: copy -> surface. Row by row: bitmap, colours.
fo_transfer:
        sta fo_dir
        lda #0
        sta fo_row
        sta fo_soff
        sta fo_soff+1
fo_transfer_row:
        lda fo_y                ; bitmap: (y+row)*320 + x*8
        clc
        adc fo_row
        sta fo_cy
        lda #0
        sta fo_boff+1
        lda fo_cy               ; *64
        ldx #6
-       asl
        rol fo_boff+1
        dex
        bne -
        sta fo_boff
        lda fo_boff+1           ; + *256
        clc
        adc fo_cy
        sta fo_boff+1
        lda fo_x
        jsr fo_times8
        clc
        adc fo_boff
        sta fo_boff
        txa
        adc fo_boff+1
        sta fo_boff+1
        lda fo_w                ; w*8 bytes
        jsr fo_times8
        sta fo_len
        stx fo_len+1
        jsr fo_copy_run
        bcs fo_transfer_done
        lda fo_cy               ; colours: 8192 + (y+row)*40 + x
        ldx #40
        jsr fo_mul
        lda fo_prod
        clc
        adc fo_x
        sta fo_boff
        lda fo_prod+1
        adc #$20
        sta fo_boff+1
        lda fo_w
        sta fo_len
        lda #0
        sta fo_len+1
        jsr fo_copy_run
        bcs fo_transfer_done
        inc fo_row
        lda fo_row
        cmp fo_h
        bne fo_transfer_row
        clc
fo_transfer_done:
        rts
; fo_len bytes between surface offset fo_boff and copy offset fo_soff, in the
; fo_dir direction; then fo_soff advances.
fo_copy_run:
        lda fo_dir
        bne +
        jsr fo_select_surface   ; surface -> buffer -> copy
        jsr fo_at_surface
        jsr N_READ
        bcs fo_run_done
        jsr fo_select_save
        jsr fo_at_save
        jsr N_WRITE
        jmp fo_run_next
+       jsr fo_select_save      ; copy -> buffer -> surface
        jsr fo_at_save
        jsr N_READ
        bcs fo_run_done
        jsr fo_select_surface
        jsr fo_at_surface
        jsr N_WRITE
fo_run_next:
        bcs fo_run_done
        lda fo_soff
        clc
        adc fo_len
        sta fo_soff
        lda fo_soff+1
        adc fo_len+1
        sta fo_soff+1
        clc
fo_run_done:
        rts
fo_at_surface:
        lda fo_boff
        sta N_OFFSET
        lda fo_boff+1
        sta N_OFFSET+1
        jmp fo_count_len
fo_at_save:
        lda fo_soff
        sta N_OFFSET
        lda fo_soff+1
        sta N_OFFSET+1
fo_count_len:
        lda fo_len
        sta N_COUNT
        lda fo_len+1
        sta N_COUNT+1
        rts
fo_select_surface:
        ldx #3
-       lda fo_surface,x
        sta N_HANDLE,x
        dex
        bpl -
        bmi fo_owner
fo_select_save:
        ldx #3
-       lda fo_save,x
        sta N_HANDLE,x
        dex
        bpl -
fo_owner:
        lda N_CURRENT
        sta N_OWNER
        rts
fo_mul:                         ; A*X -> fo_prod
        sta fo_mul_a
        stx fo_mul_b
        lda #0
        sta fo_prod
        sta fo_prod+1
        ldx #8
-       lsr fo_mul_b
        bcc +
        clc
        lda fo_prod+1
        adc fo_mul_a
        sta fo_prod+1
+       ror fo_prod+1
        ror fo_prod
        dex
        bne -
        rts

; Box and circle, empty and marked.
fo_glyphs:
        .byte $ff,$81,$81,$81,$81,$81,$81,$ff
        .byte $ff,$c3,$a5,$99,$99,$a5,$c3,$ff
        .byte $3c,$42,$81,$81,$81,$81,$42,$3c
        .byte $3c,$42,$99,$bd,$bd,$99,$42,$3c

fo_surface: .fill 4,0
fo_save: .fill 4,0
fo_ptr: .word 0
fo_x: .byte 0                   ; header copy: x, y, w, h, n
fo_y: .byte 0
fo_w: .byte 0
fo_h: .byte 0
fo_n: .byte 0
fo_type: .byte 0                ; fetched object: 8 bytes
fo_flags: .byte 0
fo_state: .byte 0
fo_ox: .byte 0
fo_oy: .byte 0
fo_ow: .byte 0
fo_spec: .word 0
fo_ax: .byte 0
fo_ay: .byte 0
fo_rows: .byte 0
fo_focus: .byte $ff
fo_i: .byte 0
fo_j: .byte 0
fo_target: .byte 0
fo_count: .byte 0
fo_flag: .byte 0
fo_key: .byte 0
fo_press: .byte 0
fo_prev_button: .byte 0
fo_exit: .byte 0
fo_error: .byte 0
fo_color: .byte 0
fo_cx: .byte 0
fo_cy: .byte 0
fo_c0x: .byte 0
fo_c0y: .byte 0
fo_c1x: .byte 0
fo_c1y: .byte 0
fo_inset: .byte 0
fo_t8: .byte 0
fo_dir: .byte 0
fo_row: .byte 0
fo_boff: .word 0
fo_soff: .word 0
fo_len: .word 0
fo_bytes: .word 0
fo_mul_a: .byte 0
fo_mul_b: .byte 0
fo_prod: .word 0
fo_rec: .fill 6,0
