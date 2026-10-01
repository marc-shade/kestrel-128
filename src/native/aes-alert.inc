; AES alerts (GEM form_alert), bank 1. See docs/NATIVE-AES.md#alerts.
; Open parses "[icon][line|...][button|...]" (ASCII), saves the covered cells
; into an owner-30 allocation, draws through the shared graphics library and
; returns a dirty-row mask. Step takes one key/pointer sample; choosing a
; button restores the saved cells exactly and frees the buffer.
AL_MAX_LINES = 5
AL_LINE_MAX = 30
AL_MAX_BUTTONS = 3
AL_BUTTON_MAX = 10
AL_MAX_CELLS = 250
AL_PAPER = $61               ; blue ink on white paper
AL_FOCUS_INK = $07               ; black ink on yellow, the suite's focus colour

; Open. N_BUFFER: surface handle (4), default button 0..3, then the string,
; NUL-terminated. The app's surface must be bound-able by the foreground app.
; Reply: chosen 0, focus, dirty rows (4 bytes; bit r&7 of byte r>>3).
al_open:
        lda al_active
        bne al_badarg           ; one alert at a time
        ldx #3
-       lda N_BUFFER,x
        sta al_surface,x
        dex
        bpl -
        lda N_BUFFER+4
        sta al_default
        jsr al_parse            ; before any callback reuses N_BUFFER
        bcs al_badarg
        lda al_default
        cmp #AL_MAX_BUTTONS+1
        bcs al_badarg
        cmp al_buttons
        beq +
        bcs al_badarg
+       jsr al_layout
        bcs al_badarg
        lda al_bytes            ; save = 9 bytes per cell; pages = ceil(/256)
        cmp #1
        lda al_bytes+1
        adc #0
        sta N_PAGES
        lda #N_AESOWNER
        sta N_OWNER
        lda #$ff
        sta N_BANK
        lda #0                  ; N_ALLOC
        jsr bk_native
        bcs al_fail
        ldx #3
-       lda N_HANDLE,x
        sta al_save,x
        dex
        bpl -
        lda #0
        jsr al_transfer         ; save the covered cells
        bcs al_fail_free
        lda #1
        sta al_active
        lda al_default
        bne +
        lda #1                  ; no default: focus the first button
+       sta al_focus
        lda #0
        sta al_armed
        sta al_pressed
        jsr al_clear_dirty
        jsr al_draw
        bcs al_fail_restore
        jmp al_reply
al_fail_restore:
        pha
        lda #1
        jsr al_transfer
        pla
al_fail_free:
        pha
        jsr al_free
        pla
al_fail:
        ldx #0
        stx al_active
        sec
        rts
al_badarg:
        lda #N_BADARG
        sec
        rts

; Step. N_BUFFER: key (0 none), pointer x (word), pointer y, buttons (bit 0).
al_step:
        lda al_active
        bne +
        lda #N_BADHANDLE
        sec
        rts
+       jsr al_clear_dirty
        lda N_BUFFER+1
        sta al_px
        lda N_BUFFER+2
        sta al_px+1
        lda N_BUFFER+3
        sta al_py
        lda N_BUFFER+4
        and #1
        sta al_down
        lda N_BUFFER
        beq al_pointer
        cmp #13
        bne +
        lda al_focus
        jmp al_choose
+       cmp #27                 ; Escape chooses the last button (Cancel)
        bne +
        lda al_buttons
        jmp al_choose
+       cmp #9
        beq al_next
        cmp #$1d                ; cursor right
        beq al_next
        cmp #$9d                ; cursor left
        beq al_previous
        sec
        sbc #$31                ; digits 1..n choose directly
        cmp al_buttons
        bcs al_pointer          ; other keys: no change
        adc #1
        jmp al_choose
al_next:
        lda al_focus
        cmp al_buttons
        bcc +
        lda #0                  ; wrap after the last button
+       clc
        adc #1
        jmp al_set_focus
al_previous:
        ldx al_focus
        dex
        bne +
        ldx al_buttons          ; wrap before the first button
+       txa
al_set_focus:
        sta al_focus
        jsr al_paint_buttons
        bcs al_step_fail
        jsr al_mark_buttons
        jmp al_reply_open
; Press over a button arms it; release over the same button chooses it.
al_pointer:
        lda al_down
        beq al_release
        lda al_pressed
        bne al_quiet            ; still held
        lda #1
        sta al_pressed
        jsr al_hit
        sta al_armed
        beq al_quiet
        cmp al_focus
        beq al_quiet
        jmp al_set_focus
al_release:
        lda al_pressed
        beq al_quiet
        lda #0
        sta al_pressed
        lda al_armed
        beq al_quiet
        jsr al_hit
        cmp al_armed
        bne +
        jmp al_choose
+       lda #0
        sta al_armed
al_quiet:
        jmp al_reply_open
al_step_fail:
        sec
        rts

; A = button 1..n: restore the covered cells, free the buffer, report it.
; A failed restore or free keeps the alert open and owned for a retry.
al_choose:
        sta al_chosen
        lda #1
        jsr al_transfer
        bcs al_step_fail
        jsr al_free
        bcs al_step_fail
        lda #0
        sta al_active
        jsr al_mark_alert
        lda al_chosen
        jmp al_reply_tail
al_reply:
        jsr al_mark_alert
al_reply_open:
        lda #0
al_reply_tail:
        sta N_BUFFER
        lda al_focus
        sta N_BUFFER+1
        ldx #3
-       lda al_dirty,x
        sta N_BUFFER+2,x
        dex
        bpl -
        lda #0
        clc
        rts

al_clear_dirty:
        lda #0
        ldx #3
-       sta al_dirty,x
        dex
        bpl -
        rts
al_mark_alert:
        lda al_y
        ldx al_h
        bne al_mark
al_mark_buttons:
        lda al_button_y
        ldx #2
; Mark X cell rows starting at row A.
al_mark:
        sta al_row
        stx al_count
-       lda al_row
        and #7
        tax
        lda al_bits,x
        sta al_math
        lda al_row
        lsr
        lsr
        lsr
        tax
        lda al_math
        ora al_dirty,x
        sta al_dirty,x
        inc al_row
        dec al_count
        bne -
        rts

al_free:
        jsr al_select_save
        lda #1                  ; N_FREE
        jsr bk_native
        bcs +
        lda #0
        sta al_save
+       rts
; Discard an alert whose app is gone: its surface no longer exists.
al_discard:
        lda al_active
        beq +
        jsr al_free
        lda #0
        sta al_active
+       rts

; ---- parsing -------------------------------------------------------------
al_parse:
        ldy #0
        lda #$5b
        jsr al_expect
        bcs al_parse_bad
        lda N_BUFFER+5,y
        sec
        sbc #$30
        cmp #4
        bcs al_parse_bad
        sta al_icon
        iny
        lda #$5d
        jsr al_expect
        bcs al_parse_bad
        lda #$5b
        jsr al_expect
        bcs al_parse_bad
        lda #0
        sta al_lines
al_line_start:
        ldx al_lines
        lda #0
        sta al_line_len,x
al_line_char:
        lda N_BUFFER+5,y
        iny
        cmp #$7c
        beq al_line_next
        cmp #$5d
        beq al_lines_done
        jsr al_printable
        bcs al_parse_bad
        ldx al_lines
        pha
        lda al_line_len,x
        cmp #AL_LINE_MAX
        bcs al_parse_bad_pla
        adc al_line_base,x      ; carry clear
        tax
        pla
        sta al_text,x
        ldx al_lines
        inc al_line_len,x
        jmp al_line_char
al_line_next:
        inc al_lines
        lda al_lines
        cmp #AL_MAX_LINES
        bcc al_line_start
al_parse_bad:
        sec
        rts
al_parse_bad_pla:
        pla
        sec
        rts
al_lines_done:
        inc al_lines
        lda #$5b
        jsr al_expect
        bcs al_parse_bad
        lda #0
        sta al_buttons
al_button_start:
        ldx al_buttons
        lda #0
        sta al_button_len,x
al_button_char:
        lda N_BUFFER+5,y
        iny
        cmp #$7c
        beq al_button_next
        cmp #$5d
        beq al_buttons_done
        jsr al_printable
        bcs al_parse_bad
        ldx al_buttons
        pha
        lda al_button_len,x
        cmp #AL_BUTTON_MAX
        bcs al_parse_bad_pla
        adc al_button_base,x    ; carry clear
        tax
        pla
        sta al_button_text,x
        ldx al_buttons
        inc al_button_len,x
        jmp al_button_char
al_button_next:
        ldx al_buttons
        lda al_button_len,x
        beq al_parse_bad        ; buttons need a label
        inc al_buttons
        lda al_buttons
        cmp #AL_MAX_BUTTONS
        bcc al_button_start
        bcs al_parse_bad
al_buttons_done:
        ldx al_buttons
        lda al_button_len,x
        beq al_parse_bad
        inc al_buttons
        lda N_BUFFER+5,y        ; the string ends here
        bne al_parse_bad
        clc
        rts
; A = expected byte at Y; advances Y. Carry set on a mismatch.
al_expect:
        cmp N_BUFFER+5,y
        bne +
        iny
        clc
        rts
+       sec
        rts
al_printable:
        cmp #32
        bcc +
        cmp #127
        rts                     ; carry set above printable ASCII
+       sec
        rts

; ---- layout: cells on the 40x25 grid ---------------------------------------
al_layout:
        lda #0
        sta al_tw
        ldx al_lines
-       dex
        bmi +
        lda al_line_len,x
        cmp al_tw
        bcc -
        sta al_tw
        bcs -
+       lda al_tw
        ldx al_icon
        beq +
        clc
        adc #3                  ; 16-pixel icon plus one blank column
+       sta al_inner
        lda #0                  ; buttons: label + 2 each, 1 apart
        ldx al_buttons
-       dex
        bmi +
        clc
        adc al_button_len,x
        adc #3
        bne -
+       sec
        sbc #1
        sta al_bw
        cmp al_inner
        bcc +
        sta al_inner
+       lda al_inner
        clc
        adc #2
        sta al_w
        cmp #39
        bcs al_layout_bad
        lda al_lines
        clc
        adc #5                  ; margin, lines, gap, 2-row buttons, margin
        sta al_h
        ; cells = w*h (<= 38*10), bytes = 9*cells
        lda #0
        sta al_cells
        sta al_cells+1
        ldx al_h
-       clc
        lda al_cells
        adc al_w
        sta al_cells
        bcc +
        inc al_cells+1
+       dex
        bne -
        lda al_cells+1
        bne al_layout_bad
        lda al_cells
        cmp #AL_MAX_CELLS+1
        bcs al_layout_bad
        sta al_bytes
        lda #0
        sta al_bytes+1
        ldx #3
-       asl al_bytes
        rol al_bytes+1
        dex
        bne -
        clc
        lda al_bytes
        adc al_cells
        sta al_bytes
        bcc +
        inc al_bytes+1
+       sec
        lda #40
        sbc al_w
        lsr
        sta al_x
        sec
        lda #25
        sbc al_h
        lsr
        sta al_y
        lda al_x                ; x*8 and w*8 as words
        jsr al_times8
        sta al_x8
        stx al_x8+1
        lda al_w
        jsr al_times8
        sta al_w8
        stx al_w8+1
        lda al_y
        clc
        adc al_lines
        adc #2
        sta al_button_y
        sec                     ; centre the button row in the inner width
        lda al_inner
        sbc al_bw
        lsr
        clc
        adc al_x
        adc #1
        ldx #0
-       cpx al_buttons
        beq +
        sta al_button_x,x
        sec
        adc al_button_len,x     ; + label (carry adds one) ...
        adc #2                  ; ... + 2 more: width len+2 plus a gap cell
        inx
        bne -
+       clc
        rts
al_layout_bad:
        sec
        rts
; A*8 -> A low, X high.
al_times8:
        ldx #0
        stx al_math
        asl
        rol al_math
        asl
        rol al_math
        asl
        rol al_math
        ldx al_math
        rts

; ---- save / restore ---------------------------------------------------------
; A = 0 saves surface cells into the buffer; 1 restores them. Bitmap spans
; (w*8 bytes per cell row) come first, then attribute spans (w bytes).
al_transfer:
        sta al_direction
        lda #0
        sta al_index
        sta al_save_off
        sta al_save_off+1
        lda al_cells            ; attributes follow cells*8 bitmap bytes
        jsr al_times8
        sta al_attr_off
        stx al_attr_off+1
        lda al_y                ; attribute surface offset 8192+y*40+x
        jsr al_times8
        sta al_attr_surf
        stx al_attr_surf+1
        asl al_attr_surf
        rol al_attr_surf+1
        asl al_attr_surf
        rol al_attr_surf+1      ; y*32
        lda al_y
        jsr al_times8
        clc
        adc al_attr_surf
        sta al_attr_surf
        txa
        adc al_attr_surf+1
        sta al_attr_surf+1      ; y*40
        clc
        lda al_attr_surf
        adc al_x
        sta al_attr_surf
        lda al_attr_surf+1
        adc #>8192
        sta al_attr_surf+1
al_transfer_row:
        lda al_y
        clc
        adc al_index
        asl
        tax
        clc
        lda gfx_rows,x
        adc al_x8
        sta al_surf_off
        lda gfx_rows+1,x
        adc al_x8+1
        sta al_surf_off+1
        lda al_save_off
        sta al_buf_off
        lda al_save_off+1
        sta al_buf_off+1
        lda al_w8
        sta al_len
        lda al_w8+1
        sta al_len+1
        jsr al_span
        bcs al_transfer_done
        clc
        lda al_save_off
        adc al_w8
        sta al_save_off
        lda al_save_off+1
        adc al_w8+1
        sta al_save_off+1
        lda al_attr_surf
        sta al_surf_off
        lda al_attr_surf+1
        sta al_surf_off+1
        lda al_attr_off
        sta al_buf_off
        lda al_attr_off+1
        sta al_buf_off+1
        lda al_w
        sta al_len
        lda #0
        sta al_len+1
        jsr al_span
        bcs al_transfer_done
        clc
        lda al_attr_off
        adc al_w
        sta al_attr_off
        bcc +
        inc al_attr_off+1
+       clc
        lda al_attr_surf
        adc #40
        sta al_attr_surf
        bcc +
        inc al_attr_surf+1
+       inc al_index
        lda al_index
        cmp al_h
        bne al_transfer_row
        clc
al_transfer_done:
        rts
; Copy al_len bytes between surface al_surf_off and buffer al_buf_off.
al_span:
        lda al_direction
        bne +
        jsr al_select_surface
        jsr al_at_surface
        jsr al_read
        bcs al_span_done
        jsr al_select_save
        jsr al_at_buffer
        jmp al_write
+       jsr al_select_save
        jsr al_at_buffer
        jsr al_read
        bcs al_span_done
        jsr al_select_surface
        jsr al_at_surface
        jmp al_write
al_span_done:
        rts
al_at_surface:
        lda al_surf_off
        sta N_OFFSET
        lda al_surf_off+1
        sta N_OFFSET+1
        jmp al_count_set
al_at_buffer:
        lda al_buf_off
        sta N_OFFSET
        lda al_buf_off+1
        sta N_OFFSET+1
al_count_set:
        lda al_len
        sta N_COUNT
        lda al_len+1
        sta N_COUNT+1
        rts
al_read:
        lda #2                  ; N_READ
        jmp bk_native
al_write:
        lda #3                  ; N_WRITE
        jmp bk_native
al_select_surface:
        lda N_CURRENT
        sta N_OWNER
        ldx #3
-       lda al_surface,x
        sta N_HANDLE,x
        dex
        bpl -
        rts
al_select_save:
        lda #N_AESOWNER
        sta N_OWNER
        ldx #3
-       lda al_save,x
        sta N_HANDLE,x
        dex
        bpl -
        rts

; ---- drawing ----------------------------------------------------------------
al_draw:
        jsr al_select_surface
        jsr gfx_bind
        bcs al_draw_done
        lda #0                  ; paper, then a double frame
        jsr al_box
        bcs al_draw_done
        lda #1
        jsr al_box
        bcs al_draw_done
        lda #2
        jsr al_box
        bcs al_draw_done
        lda #3
        jsr al_box
        bcs al_draw_done
        lda al_x                ; colours over the whole alert
        sta gfx_x0
        clc
        adc al_w
        sta gfx_x1
        lda al_y
        sta gfx_y0
        clc
        adc al_h
        sta gfx_y1
        lda #0
        sta gfx_x0+1
        sta gfx_x1+1
        sta gfx_y0+1
        sta gfx_y1+1
        lda #AL_PAPER
        sta gfx_color
        jsr gfx_colors
        bcs al_draw_done
        jsr al_draw_icon
        bcs al_draw_done
        jsr al_draw_lines
        bcs al_draw_done
        jmp al_paint_buttons
al_draw_done:
        rts
; A = inset 0..3 in pixels; even insets clear-then-ink pattern: 0 paper,
; 1 outer line, 2 gap, 3 inner line are pens 0,1,0,1 over shrinking boxes.
al_box:
        sta al_inset
        and #1
        sta gfx_pen
        clc
        lda al_x8
        adc al_inset
        sta gfx_x0
        lda al_x8+1
        adc #0
        sta gfx_x0+1
        lda al_y
        jsr al_times8
        clc
        adc al_inset
        sta gfx_y0
        lda #0
        sta gfx_y0+1
        clc
        lda al_x8
        adc al_w8
        sta gfx_x1
        lda al_x8+1
        adc al_w8+1
        sta gfx_x1+1
        sec
        lda gfx_x1
        sbc al_inset
        sta gfx_x1
        bcs +
        dec gfx_x1+1
+       lda al_y
        clc
        adc al_h
        jsr al_times8
        sec
        sbc al_inset
        sta gfx_y1
        lda #0
        sta gfx_y1+1
        lda al_inset
        beq +
        cmp #2
        bne al_box_line
+       jmp gfx_rect            ; paper and the gap between the lines
al_box_line:
        jsr gfx_rect            ; a filled box...
        bcs al_box_line_done
        lda #0                  ; ...hollowed one pixel in
        sta gfx_pen
        jsr al_shrink
        jmp gfx_rect
al_box_line_done:
        rts
; Shrink gfx_x0..y1 by one pixel on every side (16-bit x, 8-bit y).
al_shrink:
        inc gfx_x0
        bne al_shrink_y
        inc gfx_x0+1
al_shrink_y:
        inc gfx_y0
        dec gfx_y1
        lda gfx_x1
        bne al_shrink_x1
        dec gfx_x1+1
al_shrink_x1:
        dec gfx_x1
        rts

al_draw_icon:
        lda al_icon
        bne +
        clc
        rts
+       sec
        sbc #1
        asl
        asl
        asl
        asl
        asl
        sta al_icon_base        ; 32 bytes per icon: 16 rows x 2 bytes
        lda #0
        sta al_index
al_icon_glyph:
        lda al_index            ; glyph g: row half g>>1, byte column g&1
        and #2
        asl
        asl
        asl                     ; 0 or 16 = (g>>1)*8 rows * 2 bytes
        clc
        adc al_icon_base
        sta al_math
        lda al_index
        and #1
        clc
        adc al_math
        tax
        ldy #0
-       lda al_icons,x
        sta gfx_bits,y
        inx
        inx
        iny
        cpy #8
        bne -
        lda al_x
        clc
        adc #1
        sta al_math
        lda al_index
        and #1
        clc
        adc al_math
        jsr al_times8
        sta gfx_x0
        stx gfx_x0+1
        lda al_y
        clc
        adc #1
        sta al_math
        lda al_index
        lsr
        clc
        adc al_math
        jsr al_times8
        sta gfx_y0
        stx gfx_y0+1
        lda #3
        sta gfx_pen
        jsr gfx_glyph
        bcs +
        inc al_index
        lda al_index
        cmp #4
        bne al_icon_glyph
        clc
+       rts

al_draw_lines:
        lda #0
        sta al_index
-       lda al_index
        cmp al_lines
        bcs +
        tax
        lda al_line_len,x
        beq al_line_skip
        sta gfx_text_length
        lda al_line_base,x
        tax
        ldy #0
-       lda al_text,x
        sta gfx_text_buffer,y
        inx
        iny
        cpy gfx_text_length
        bne -
        lda al_x
        clc
        adc #1
        ldx al_icon
        beq *+4
        adc #3
        jsr al_times8
        sta gfx_x0
        stx gfx_x0+1
        lda al_y
        clc
        adc #1
        adc al_index
        jsr al_times8
        sta gfx_y0
        stx gfx_y0+1
        lda #1
        sta gfx_pen
        jsr gfx_text
        bcs ++
al_line_skip:
        inc al_index
        jmp --
+       clc
+       rts

; Frame each button (twice for the default), label it, colour its cells
; with the focus colour when focused.
al_paint_buttons:
        lda #0
        sta al_index
al_button_paint:
        lda al_index
        cmp al_buttons
        bcc +
        clc
        rts
+       tax
        lda al_button_x,x
        jsr al_times8
        sta al_bx0
        stx al_bx0+1
        ldx al_index
        lda al_button_x,x
        clc
        adc al_button_len,x
        adc #2
        sta al_math
        jsr al_times8
        sta al_bx1
        stx al_bx1+1
        lda #0                  ; clear, then outer frame
        jsr al_button_box
        bcs al_button_done
        lda #1
        jsr al_button_box
        bcs al_button_done
        lda al_index
        clc
        adc #1
        cmp al_default
        bne +
        lda #2                  ; default: second frame line inside
        jsr al_button_box
        bcs al_button_done
+       ldx al_index            ; label, centred: one cell in, four px down
        lda al_button_len,x
        sta gfx_text_length
        lda al_button_base,x
        tax
        ldy #0
-       lda al_button_text,x
        sta gfx_text_buffer,y
        inx
        iny
        cpy gfx_text_length
        bne -
        clc
        lda al_bx0
        adc #8
        sta gfx_x0
        lda al_bx0+1
        adc #0
        sta gfx_x0+1
        lda al_button_y
        jsr al_times8
        clc
        adc #4
        sta gfx_y0
        stx gfx_y0+1
        lda #1
        sta gfx_pen
        jsr gfx_text
        bcs al_button_done
        ldx al_index            ; focus colour on its cells
        lda al_button_x,x
        sta gfx_x0
        clc
        adc al_button_len,x
        adc #2
        sta gfx_x1
        lda al_button_y
        sta gfx_y0
        clc
        adc #2
        sta gfx_y1
        lda #0
        sta gfx_x0+1
        sta gfx_x1+1
        sta gfx_y0+1
        sta gfx_y1+1
        inx
        lda #AL_PAPER
        cpx al_focus
        bne +
        lda #AL_FOCUS_INK
+       sta gfx_color
        jsr gfx_colors
        bcs al_button_done
        inc al_index
        jmp al_button_paint
al_button_done:
        rts
; A = 0 clear the button, 1 outer line, 2 inner (default) line.
al_button_box:
        sta al_inset
        lda al_bx0
        sta gfx_x0
        lda al_bx0+1
        sta gfx_x0+1
        lda al_bx1
        sta gfx_x1
        lda al_bx1+1
        sta gfx_x1+1
        lda al_button_y
        jsr al_times8
        sta gfx_y0
        stx gfx_y0+1
        clc
        adc #16
        sta gfx_y1
        lda #0
        sta gfx_y1+1
        lda al_inset
        bne +
        sta gfx_pen
        jmp gfx_rect
+       cmp #1
        beq +
        jsr al_shrink           ; inner line one pixel inside
+       lda #1
        sta gfx_pen
        jmp al_box_line

; Button under the pointer, 1..n, or 0.
al_hit:
        lda al_px+1
        cmp #>320
        bcc +
        bne al_hit_none
        lda al_px
        cmp #<320
        bcs al_hit_none
+       lda al_py
        cmp #200
        bcs al_hit_none
        lsr
        lsr
        lsr
        sec
        sbc al_button_y
        cmp #2
        bcs al_hit_none
        lda al_px+1             ; column = x / 8
        lsr
        lda al_px
        ror
        lsr
        lsr
        sta al_math
        ldx #0
-       cpx al_buttons
        beq al_hit_none
        lda al_math
        cmp al_button_x,x
        bcc +
        lda al_button_x,x
        clc
        adc al_button_len,x
        adc #2
        cmp al_math
        beq +
        bcc +
        inx
        txa
        rts
+       inx
        bne -
al_hit_none:
        lda #0
        rts

al_active: .byte 0
al_surface: .fill 4,0
al_save: .fill 4,0
al_default: .byte 0
al_focus: .byte 0
al_chosen: .byte 0
al_armed: .byte 0
al_pressed: .byte 0
al_down: .byte 0
al_px: .word 0
al_py: .byte 0
al_icon: .byte 0
al_lines: .byte 0
al_buttons: .byte 0
al_tw: .byte 0
al_bw: .byte 0
al_inner: .byte 0
al_x: .byte 0
al_y: .byte 0
al_w: .byte 0
al_h: .byte 0
al_x8: .word 0
al_w8: .word 0
al_cells: .word 0
al_bytes: .word 0
al_button_y: .byte 0
al_button_x: .fill AL_MAX_BUTTONS,0
al_line_len: .fill AL_MAX_LINES,0
al_button_len: .fill AL_MAX_BUTTONS,0
al_line_base: .byte 0,30,60,90,120
al_button_base: .byte 0,10,20
al_dirty: .fill 4,0
al_row: .byte 0
al_count: .byte 0
al_math: .byte 0
al_index: .byte 0
al_inset: .byte 0
al_direction: .byte 0
al_save_off: .word 0
al_attr_off: .word 0
al_attr_surf: .word 0
al_surf_off: .word 0
al_buf_off: .word 0
al_len: .word 0
al_bx0: .word 0
al_bx1: .word 0
al_icon_base: .byte 0
al_bits: .byte 1,2,4,8,16,32,64,128
; 16x16 icons, two bytes per row: note (!), question (?), stop.
al_icons:
        .byte $00,$00,$03,$c0,$03,$c0,$03,$c0,$03,$c0,$03,$c0,$03,$c0,$03,$c0
        .byte $01,$80,$01,$80,$00,$00,$00,$00,$03,$c0,$03,$c0,$00,$00,$00,$00
        .byte $07,$e0,$0f,$f0,$1c,$38,$18,$18,$00,$38,$00,$70,$00,$e0,$01,$c0
        .byte $01,$80,$01,$80,$00,$00,$00,$00,$01,$80,$01,$80,$00,$00,$00,$00
        .byte $07,$e0,$0f,$f0,$1f,$f8,$3f,$fc,$7f,$fe,$ff,$ff,$ff,$ff,$c0,$03
        .byte $c0,$03,$ff,$ff,$ff,$ff,$7f,$fe,$3f,$fc,$1f,$f8,$0f,$f0,$07,$e0
; RAM tables in the owner-30 data segment (aesvc.asm AE_DATA)
        .section aesdata
al_text: .fill AL_MAX_LINES*AL_LINE_MAX,0
al_button_text: .fill AL_MAX_BUTTONS*AL_BUTTON_MAX,0
        .send aesdata
