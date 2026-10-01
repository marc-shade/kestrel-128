; AES menu bar (GEM menu_bar / menu_icheck / menu_ienable), bank 1.
; See docs/NATIVE-AES.md#menus. The bar occupies cell row 0 of the app's
; surface. Drop-downs reuse the alert save-under (one overlay at a time).
; Input arrives through the event wait: while a drop-down is open the menu
; owns input; a choice closes it and queues MN_SELECTED (10).
MN_MAX_TITLES = 8
MN_MAX_ITEMS = 48
MN_MAX_PER_TITLE = 12
MN_TEXT_MAX = 16
MN_POOL_SIZE = 400
MN_KEY = $85                  ; F1 opens the first menu from the keyboard
MN_GREY = $c1                 ; disabled items: grey ink on white
MN_CHECKED = 1
MN_DISABLED = 2
MN_SEPARATOR = $80

; INSTALL. N_BUFFER: surface handle (4), NUL-terminated ASCII spec
; "Title:item|item^K|-|item;Title:...". An empty spec removes the menu.
; Reply: 4 dirty-row bytes.
mn_install:
        lda mn_open
        beq +
        jmp mn_badarg           ; not while a drop-down is open
+       ldx #3
-       lda N_BUFFER,x
        sta mn_surface,x
        dex
        bpl -
        lda N_BUFFER+4
        bne +
        sta mn_titles           ; empty: no menu
        jmp mn_install_reply
+       jsr mn_parse
        bcc +
        lda #0
        sta mn_titles
        jmp mn_badarg
+       jsr mn_layout
        bcc +
        lda #0
        sta mn_titles
        jmp mn_badarg
+       jsr al_clear_dirty
        jsr mn_draw_bar
        bcc mn_install_reply
        rts
mn_install_reply:
        lda #0
        ldx #3
-       sta al_dirty,x
        dex
        bpl -
        lda al_dirty
        ora #1                  ; row 0
        sta al_dirty
        ldx #3
-       lda al_dirty,x
        sta N_BUFFER,x
        dex
        bpl -
        lda #0
        clc
        rts
mn_badarg:
        lda #N_BADARG
        sec
        rts

; SET. N_BUFFER: title, item (within the title), flags (bit 0 checked,
; bit 1 disabled). Separators keep their flag. Reply as INSTALL.
mn_set:
        lda N_BUFFER
        cmp mn_titles
        bcs mn_badarg
        tax
        lda N_BUFFER+1
        cmp mn_title_count,x
        bcs mn_badarg
        clc
        adc mn_title_first,x
        tax
        lda mn_item_flags,x
        and #MN_SEPARATOR
        sta mn_math
        lda N_BUFFER+2
        and #MN_CHECKED|MN_DISABLED
        ora mn_math
        sta mn_item_flags,x
        jsr al_clear_dirty
        lda mn_open             ; repaint an open drop-down of that title
        beq +
        sec
        sbc #1
        cmp N_BUFFER
        bne +
        jsr mn_draw_items
        bcs mn_set_done
+       ldx #3
-       lda al_dirty,x
        sta N_BUFFER,x
        dex
        bpl -
        lda #0
        clc
mn_set_done:
        rts

; ---- parsing ---------------------------------------------------------------
mn_parse:
        lda #<(N_BUFFER+4)
        sta mn_read+1
        lda #>(N_BUFFER+4)
        sta mn_read+2
        lda #0
        sta mn_titles
        sta mn_items
        sta mn_pool_len
        sta mn_pool_len+1
mn_parse_title:
        jsr mn_token
        bcs mn_parse_bad
        cmp #$3a                ; ':'
        bne mn_parse_bad
        lda mn_tok_len
        beq mn_parse_bad
        ldx mn_titles
        cpx #MN_MAX_TITLES
        bcs mn_parse_bad
        sta mn_title_len,x
        lda mn_items
        sta mn_title_first,x
        lda #0
        sta mn_title_count,x
        jsr mn_pool_add
        bcs mn_parse_bad
        ldx mn_titles
        lda mn_add_off
        sta mn_title_off_lo,x
        lda mn_add_off+1
        sta mn_title_off_hi,x
        inc mn_titles
mn_parse_item:
        jsr mn_token
        bcs mn_parse_bad
        sta mn_delim
        ldx mn_items
        cpx #MN_MAX_ITEMS
        bcs mn_parse_bad
        ldx mn_titles
        lda mn_title_count-1,x
        cmp #MN_MAX_PER_TITLE
        bcs mn_parse_bad
        jsr mn_item_add
        bcs mn_parse_bad
        ldx mn_titles
        inc mn_title_count-1,x
        inc mn_items
        lda mn_delim
        cmp #$7c                ; '|'
        beq mn_parse_item
        ldx mn_titles           ; the first title's end: a desk accessory
        dex                     ; adds its items there
        bne +
        jsr ac_menu
        lda mn_delim
+       cmp #$3b                ; ';'
        beq mn_parse_title
        clc                     ; NUL ends the spec
        rts
mn_parse_bad:
        sec
        rts

; Read one token into mn_tok up to ':' ';' '|' or NUL (returned in A).
mn_token:
        lda #0
        sta mn_tok_len
mn_token_next:
        jsr mn_getc
        cmp #0
        beq mn_token_end
        cmp #$3a
        beq mn_token_end
        cmp #$3b
        beq mn_token_end
        cmp #$7c
        beq mn_token_end
        cmp #32
        bcc mn_token_bad
        cmp #127
        bcs mn_token_bad
        ldx mn_tok_len
        cpx #MN_TEXT_MAX+2      ; room for a "^K" suffix
        bcs mn_token_bad
        sta mn_tok,x
        inc mn_tok_len
        bne mn_token_next
mn_token_end:
        clc
        rts
mn_token_bad:
        sec
        rts
; Next spec byte; the spec may run past 256 bytes, so the address advances.
mn_getc:
        lda mn_read+2           ; never read past the 512-byte N_BUFFER
        cmp #>(N_BUFFER+512)
        bcs mn_getc_end
mn_read:
        lda N_BUFFER+4
        inc mn_read+1
        bne +
        inc mn_read+2
+       rts
mn_getc_end:
        lda #0
        rts

; A desk accessory's item, while its menu entry runs: A/X = NUL-terminated
; text in bank 1. Carry clear with A = the item's index in the first title.
ac_menu_add:
        sta ac_menu_read+1
        stx ac_menu_read+2
        ldx #0
ac_menu_read:
        lda $ffff,x
        sta mn_tok,x
        beq +
        inx
        cpx #MN_TEXT_MAX+2
        bne ac_menu_read
        sec
        rts
+       stx mn_tok_len
        lda mn_items
        cmp #MN_MAX_ITEMS
        bcs ac_menu_full
        lda mn_title_count
        cmp #MN_MAX_PER_TITLE
        bcs ac_menu_full
        jsr mn_item_add
        bcs ac_menu_full
        lda mn_title_count
        inc mn_title_count
        inc mn_items
        clc
        rts
ac_menu_full:
        sec
        rts

; Classify mn_tok as an item: "-" separator, optional "^K" shortcut suffix.
mn_item_add:
        ldx mn_items
        lda #0
        sta mn_item_flags,x
        sta mn_item_key,x
        lda mn_tok_len
        beq mn_item_bad
        cmp #1
        bne +
        lda mn_tok
        cmp #$2d                ; '-'
        bne +
        lda #MN_SEPARATOR|MN_DISABLED
        sta mn_item_flags,x
        lda #0
        sta mn_tok_len
        beq mn_item_store
+       ldy mn_tok_len
        cpy #3
        bcc mn_item_store
        lda mn_tok-2,y
        cmp #$5e                ; '^'
        bne mn_item_store
        lda mn_tok-1,y
        and #$df                ; letters fold to upper case
        cmp #$41
        bcc mn_item_bad
        cmp #$5b
        bcs mn_item_bad
        and #$1f                ; Ctrl-letter key code
        sta mn_item_key,x
        dey
        dey
        sty mn_tok_len
mn_item_store:
        lda mn_tok_len
        cmp #MN_TEXT_MAX+1
        bcs mn_item_bad
        sta mn_item_len,x
        jsr mn_pool_add
        bcs mn_item_bad
        ldx mn_items
        lda mn_add_off
        sta mn_item_off_lo,x
        lda mn_add_off+1
        sta mn_item_off_hi,x
        clc
        rts
mn_item_bad:
        sec
        rts

; Append mn_tok[0..mn_tok_len) to the text pool; offset in mn_add_off.
mn_pool_add:
        lda mn_pool_len
        sta mn_add_off
        lda mn_pool_len+1
        sta mn_add_off+1
        clc
        lda mn_pool_len
        adc mn_tok_len
        sta mn_math16
        lda mn_pool_len+1
        adc #0
        sta mn_math16+1
        lda mn_math16           ; new length must stay <= MN_POOL_SIZE
        cmp #<(MN_POOL_SIZE+1)
        lda mn_math16+1
        sbc #>(MN_POOL_SIZE+1)
        bcs mn_pool_full
        clc
        lda #<mn_pool
        adc mn_pool_len
        sta mn_pool_store+1
        lda #>mn_pool
        adc mn_pool_len+1
        sta mn_pool_store+2
        ldy #0
-       cpy mn_tok_len
        beq +
        lda mn_tok,y
mn_pool_store:
        sta $ffff,y
        iny
        bne -
+       lda mn_math16
        sta mn_pool_len
        lda mn_math16+1
        sta mn_pool_len+1
        clc
        rts
mn_pool_full:
        sec
        rts

; ---- layout ------------------------------------------------------------------
mn_layout:
        lda #1
        sta mn_math
        ldx #0
-       cpx mn_titles
        beq +
        lda mn_math
        sta mn_title_x,x
        clc
        adc mn_title_len,x
        adc #1
        sta mn_math
        cmp #41
        bcs mn_layout_bad
        inx
        bne -
+       ldx #0                  ; every drop-down must fit and fit the save-under
-       cpx mn_titles
        beq +
        stx mn_math
        jsr mn_geometry
        bcs mn_layout_bad
        ldx mn_math
        inx
        bne -
+       clc
        rts
mn_layout_bad:
        sec
        rts
; X = title: drop-down x, w, h into mn_dx/mn_dw/mn_dh. Carry set if too big.
mn_geometry:
        lda #0
        sta mn_dw
        sta mn_keys
        lda mn_title_count,x
        sta mn_dh
        lda mn_title_first,x
        tay
        ldx mn_dh
-       lda mn_item_len,y
        cmp mn_dw
        bcc +
        sta mn_dw
+       lda mn_item_key,y
        ora mn_keys
        sta mn_keys
        iny
        dex
        bne -
        lda mn_dw               ; blank, check column, text, blank
        clc
        adc #3
        ldx mn_keys
        beq +
        adc #3                  ; blank, "^K"
+       sta mn_dw
        cmp #39
        bcs mn_geometry_bad
        ldx mn_math
        lda mn_title_x,x
        sec
        sbc #1
        sta mn_dx
        clc
        adc mn_dw
        cmp #41
        bcc +
        lda #40
        sec
        sbc mn_dw
        sta mn_dx
+       lda #0                  ; cells = w*(items+2 margin rows) must fit
        ldx mn_dh
        inx
        inx
-       clc
        adc mn_dw
        bcs mn_geometry_bad
        dex
        bne -
        cmp #AL_MAX_CELLS+1
        rts                     ; carry set when larger
mn_geometry_bad:
        sec
        rts

; ---- drawing -----------------------------------------------------------------
mn_bind:
        ldx #3
-       lda mn_surface,x
        sta al_surface,x
        dex
        bpl -
        jsr al_select_surface
        jmp gfx_bind
mn_draw_bar:
        jsr mn_bind
        bcs mn_draw_done
        lda #0
        sta gfx_x0
        sta gfx_x0+1
        sta gfx_y0
        sta gfx_y0+1
        sta gfx_y1+1
        sta gfx_pen
        lda #<320
        sta gfx_x1
        lda #>320
        sta gfx_x1+1
        lda #8
        sta gfx_y1
        jsr gfx_rect
        bcs mn_draw_done
        lda #0
        sta al_index
-       lda al_index
        cmp mn_titles
        bcs +
        tax
        jsr mn_title_text
        ldx al_index
        lda mn_title_x,x
        jsr al_times8
        sta gfx_x0
        stx gfx_x0+1
        lda #0
        sta gfx_y0
        sta gfx_y0+1
        lda #1
        sta gfx_pen
        jsr gfx_text
        bcs mn_draw_done
        inc al_index
        bne -
+       jsr mn_bar_colors
        bcs mn_draw_done
        lda al_dirty
        ora #1
        sta al_dirty
        clc
mn_draw_done:
        rts
; Row 0 paper, the open title in the focus colour.
mn_bar_colors:
        lda #0
        sta gfx_x0
        sta gfx_y0
        sta gfx_x0+1
        sta gfx_x1+1
        sta gfx_y0+1
        sta gfx_y1+1
        lda #40
        sta gfx_x1
        lda #1
        sta gfx_y1
        lda #AL_PAPER
        sta gfx_color
        jsr gfx_colors
        bcs +
        ldx mn_open
        beq +
        dex
        lda mn_title_x,x
        sta gfx_x0
        clc
        adc mn_title_len,x
        sta gfx_x1
        lda #AL_FOCUS_INK
        sta gfx_color
        jsr gfx_colors
+       rts
mn_title_text:
        lda mn_title_len,x
        sta gfx_text_length
        lda mn_title_off_lo,x
        sta mn_math16
        lda mn_title_off_hi,x
        sta mn_math16+1
        jmp mn_copy_text
mn_item_text:
        lda mn_item_len,x
        sta gfx_text_length
        lda mn_item_off_lo,x
        sta mn_math16
        lda mn_item_off_hi,x
        sta mn_math16+1
mn_copy_text:
        clc
        lda #<mn_pool
        adc mn_math16
        sta mn_copy+1
        lda #>mn_pool
        adc mn_math16+1
        sta mn_copy+2
        ldy #0
-       cpy gfx_text_length
        beq +
mn_copy:
        lda $ffff,y
        sta gfx_text_buffer,y
        iny
        bne -
+       rts

; Open title X (0-based): save the covered cells, draw the drop-down.
mn_drop:
        stx mn_math
        jsr mn_geometry
        ldx mn_math
        inx
        stx mn_open
        lda #$ff
        sta mn_hover
        lda mn_dx               ; the alert save-under state describes it
        sta al_x
        lda #1
        sta al_y
        lda mn_dw
        sta al_w
        lda mn_dh               ; items plus a margin row above and below,
        clc                     ; so the frame never crosses an item row
        adc #2
        sta al_h
        lda #0
        sta al_cells+1
        ldx al_h
        lda #0
-       clc
        adc mn_dw
        dex
        bne -
        sta al_cells
        sta al_bytes            ; 9 bytes per cell
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
+       lda al_x
        jsr al_times8
        sta al_x8
        stx al_x8+1
        lda al_w
        jsr al_times8
        sta al_w8
        stx al_w8+1
        jsr mn_bind
        bcs mn_drop_fail
        lda al_bytes
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
        bcs mn_drop_fail
        ldx #3
-       lda N_HANDLE,x
        sta al_save,x
        dex
        bpl -
        lda #0
        jsr al_transfer
        bcs mn_drop_free
        jsr mn_bind             ; transfers rebound heap arguments
        bcs mn_drop_restore
        lda #0                  ; paper and a one-pixel frame
        jsr al_box
        bcs mn_drop_restore
        lda #1
        jsr al_box
        bcs mn_drop_restore
        lda al_x                ; paper colour on every cell, margins included
        sta gfx_x0
        clc
        adc al_w
        sta gfx_x1
        lda #1
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
        bcs mn_drop_restore
        jsr mn_draw_items
        bcs mn_drop_restore
        jsr mn_bar_colors
        bcs mn_drop_restore
        jsr al_mark_alert
        lda al_dirty
        ora #1
        sta al_dirty
        clc
        rts
mn_drop_restore:
        pha
        lda #1
        jsr al_transfer
        pla
mn_drop_free:
        pha
        jsr al_free
        pla
mn_drop_fail:
        ldx #0
        stx mn_open
        sec
        rts

; Close the open drop-down: restore its cells, free the buffer.
mn_close:
        lda mn_open
        beq +
        lda #1
        jsr al_transfer
        bcs mn_close_done
        jsr al_free
        bcs mn_close_done
        jsr al_mark_alert
        lda #0
        sta mn_open
        jsr mn_bind
        bcs mn_close_done
        jsr mn_bar_colors
        bcs mn_close_done
        lda al_dirty
        ora #1
        sta al_dirty
+       clc
mn_close_done:
        rts

; Items of the open title: text, check marks, shortcuts, separators, colours.
mn_draw_items:
        ldx mn_open
        dex
        stx mn_title
        lda #0
        sta mn_row
mn_item_row:
        ldx mn_title
        lda mn_row
        cmp mn_title_count,x
        bcc +
        clc
        rts
+       clc
        adc mn_title_first,x
        sta mn_item
        tax
        lda mn_item_flags,x
        bpl mn_item_normal
        lda mn_dx               ; separator: a line through the middle
        clc
        adc #1
        jsr al_times8
        sta gfx_x0
        stx gfx_x0+1
        lda mn_dx
        clc
        adc mn_dw
        sec
        sbc #1
        jsr al_times8
        sta gfx_x1
        stx gfx_x1+1
        jsr mn_row_y
        clc
        adc #3
        sta gfx_y0
        adc #1
        sta gfx_y1
        lda #0
        sta gfx_y0+1
        sta gfx_y1+1
        lda #1
        sta gfx_pen
        jsr gfx_rect
        bcs mn_items_done
        jmp mn_item_colors
mn_item_normal:
        ldx mn_item             ; clear the text cells (repaints come here too)
        jsr mn_row_cells
        lda #0
        sta gfx_pen
        jsr gfx_rect
        bcs mn_items_done
        ldx mn_item
        lda mn_item_flags,x
        and #MN_CHECKED
        beq +
        ldx #7
-       lda mn_check,x
        sta gfx_bits,x
        dex
        bpl -
        lda mn_dx
        clc
        adc #1
        jsr al_times8
        sta gfx_x0
        stx gfx_x0+1
        jsr mn_row_y
        sta gfx_y0
        lda #0
        sta gfx_y0+1
        lda #1
        sta gfx_pen
        jsr gfx_glyph
        bcs mn_items_done
+       ldx mn_item
        jsr mn_item_text
        lda mn_dx
        clc
        adc #2
        jsr al_times8
        sta gfx_x0
        stx gfx_x0+1
        jsr mn_row_y
        sta gfx_y0
        lda #0
        sta gfx_y0+1
        lda #1
        sta gfx_pen
        jsr gfx_text
        bcs mn_items_done
        ldx mn_item
        lda mn_item_key,x
        beq mn_item_colors
        ora #$40                ; "^K" at the right edge
        sta gfx_text_buffer+1
        lda #$5e
        sta gfx_text_buffer
        lda #2
        sta gfx_text_length
        lda mn_dx
        clc
        adc mn_dw
        sec
        sbc #3
        jsr al_times8
        sta gfx_x0
        stx gfx_x0+1
        jsr mn_row_y
        sta gfx_y0
        lda #0
        sta gfx_y0+1
        jsr gfx_text
        bcs mn_items_done
mn_item_colors:
        lda mn_dx
        sta gfx_x0
        clc
        adc mn_dw
        sta gfx_x1
        lda mn_row
        clc
        adc #2
        sta gfx_y0
        adc #1
        sta gfx_y1
        lda #0
        sta gfx_x0+1
        sta gfx_x1+1
        sta gfx_y0+1
        sta gfx_y1+1
        ldx mn_item
        lda #MN_GREY
        ldy mn_item_flags,x
        cpy #MN_DISABLED        ; disabled or separator: grey
        bcs +
        lda #AL_PAPER
        ldy mn_row
        cpy mn_hover
        bne +
        lda #AL_FOCUS_INK
+       sta gfx_color
        jsr gfx_colors
        bcs mn_items_done
        inc mn_row
        jmp mn_item_row
mn_items_done:
        rts
; Pixel y of the current drop-down row (cell row 2 is the first item).
mn_row_y:
        lda mn_row
        clc
        adc #2
        jsr al_times8
        rts
; Text cells of the current row, inside the frame column.
mn_row_cells:
        lda mn_dx
        clc
        adc #1
        jsr al_times8
        sta gfx_x0
        stx gfx_x0+1
        lda mn_dx
        clc
        adc mn_dw
        sec
        sbc #1
        jsr al_times8
        sta gfx_x1
        stx gfx_x1+1
        jsr mn_row_y
        sta gfx_y0
        clc
        adc #8
        sta gfx_y1
        lda #0
        sta gfx_y0+1
        sta gfx_y1+1
        rts

; ---- input -------------------------------------------------------------------
; Called by the event wait with the sample in N_BUFFER. Carry set when the
; menu consumed the sample: the wait then reports only a queued selection.
mn_input:
        lda mn_titles
        bne +
        clc
        rts
+       lda N_BUFFER+20
        and #1
        sta mn_down
        eor #1
        and mn_prev_down        ; mn_release: held last sample, up now
        sta mn_release
        lda mn_prev_down
        eor #1
        and mn_down
        sta mn_press
        lda mn_down
        sta mn_prev_down
        jsr mn_pointer_cell
        lda mn_open
        bne mn_input_open
        lda N_BUFFER+16         ; closed: F1, shortcuts, a press on a title
        beq mn_closed_pointer
        cmp #MN_KEY
        bne +
        ldx #0
        jsr mn_drop
        bcs mn_consumed_far
        jsr mn_first_enabled
mn_consumed_far:
        jmp mn_consumed
+       jsr mn_shortcut
        bcc mn_not_ours
        jmp mn_consumed
mn_closed_pointer:
        lda mn_press
        beq mn_not_ours
        lda mn_cy
        bne mn_not_ours
        jsr mn_title_hit
        bcc mn_not_ours
        jsr mn_drop
        jmp mn_consumed
mn_not_ours:
        clc
        rts
mn_input_open:
        lda N_BUFFER+16
        beq mn_open_pointer
        cmp #27
        bne +
        jsr mn_close
        jmp mn_consumed
+       cmp #13
        bne +
        lda mn_hover
        cmp #$ff
        beq mn_consumed
        jmp mn_choose
+       cmp #$11                ; cursor down
        bne +
        jsr mn_next_enabled
        jmp mn_consumed
+       cmp #$91                ; cursor up
        bne +
        jsr mn_previous_enabled
        jmp mn_consumed
+       cmp #$1d                ; cursor right: next title
        bne +
        ldx mn_open
        cpx mn_titles
        bcc mn_switch
        ldx #0
        beq mn_switch
+       cmp #$9d                ; cursor left: previous title
        bne mn_consumed
        ldx mn_open
        dex
        dex
        bpl mn_switch
        ldx mn_titles
        dex
mn_switch:
        stx mn_switch_to
        jsr mn_close
        bcs mn_consumed
        ldx mn_switch_to
        jsr mn_drop
        bcs mn_consumed
        jsr mn_first_enabled
        jmp mn_consumed
mn_open_pointer:
        lda mn_cy               ; on the bar: another title opens on press
        bne mn_in_items
        lda mn_press
        beq mn_consumed
        jsr mn_title_hit
        bcc mn_outside
        inx
        cpx mn_open
        beq mn_consumed
        dex
        jmp mn_switch
mn_in_items:
        lda mn_cx               ; inside the drop-down: hover, release chooses
        sec
        sbc mn_dx
        cmp mn_dw
        bcs mn_outside
        ldx mn_cy               ; item rows start at cell row 2
        dex
        dex
        cpx mn_dh
        bcs mn_outside
        txa
        jsr mn_enabled_row
        bcs +
        lda #$ff
+       cmp mn_hover
        beq +
        sta mn_hover
        jsr mn_draw_items
+       lda mn_release
        beq mn_consumed
        lda mn_hover
        cmp #$ff
        beq mn_consumed
        jmp mn_choose
mn_outside:
        lda mn_press            ; a press elsewhere closes the menu
        beq mn_consumed
        jsr mn_close
mn_consumed:
        lda #0
        sta N_BUFFER+16         ; the key belonged to the menu
        sec
        rts

; Queue MN_SELECTED for the hovered item of the open title, then close.
mn_choose:
        ldx mn_open
        dex
        stx mn_msg_title
        lda mn_hover
        sta mn_msg_item
        jsr mn_close
        bcs mn_consumed
        jsr mn_queue
        jmp mn_consumed
mn_queue:
        lda #MN_SELECTED
        sta ev_msg_in
        lda #0
        sta ev_msg_in+1
        sta ev_msg_in+2
        sta ev_msg_in+5
        sta ev_msg_in+6
        sta ev_msg_in+7
        lda mn_msg_title
        sta ev_msg_in+3
        lda mn_msg_item
        sta ev_msg_in+4
        jmp ev_push
; A shortcut of an enabled item queues its selection. Carry set when found.
mn_shortcut:
        sta mn_math
        ldx #0
mn_short_title:
        cpx mn_titles
        bcs mn_short_none
        lda #0
        sta mn_row
mn_short_item:
        lda mn_row
        cmp mn_title_count,x
        bcs mn_short_next
        clc
        adc mn_title_first,x
        tay
        lda mn_item_key,y
        beq +
        cmp mn_math
        bne +
        lda mn_item_flags,y
        and #MN_DISABLED
        bne +
        stx mn_msg_title
        lda mn_row
        sta mn_msg_item
        jsr mn_queue
        sec
        rts
+       inc mn_row
        bne mn_short_item
mn_short_next:
        inx
        bne mn_short_title
mn_short_none:
        clc
        rts

; Pointer cell of the sample.
mn_pointer_cell:
        lda N_BUFFER+18
        lsr
        lda N_BUFFER+17
        ror
        lsr
        lsr
        sta mn_cx
        lda N_BUFFER+19
        lsr
        lsr
        lsr
        sta mn_cy
        rts
; Title under mn_cx on the bar: X = title, carry set when found.
mn_title_hit:
        ldx #0
-       cpx mn_titles
        bcs +
        lda mn_cx
        sec
        sbc mn_title_x,x
        cmp mn_title_len,x
        bcc mn_title_found
        inx
        bne -
+       clc
        rts
mn_title_found:
        sec
        rts
; A = row of the open title: carry set when that item can be chosen.
; A is preserved. Separators carry the disabled flag too.
mn_enabled_row:
        sta mn_math
        ldx mn_open
        dex
        clc
        adc mn_title_first,x
        tax
        lda mn_item_flags,x
        and #MN_DISABLED
        beq +
        lda mn_math
        clc
        rts
+       lda mn_math
        sec
        rts
mn_first_enabled:
        lda #$ff
        sta mn_hover
mn_next_enabled:
        ldy mn_dh
-       inc mn_hover
        lda mn_hover
        cmp mn_dh
        bcc +
        lda #0
        sta mn_hover
+       lda mn_hover
        jsr mn_enabled_row
        bcs mn_hover_set
        dey
        bne -
        lda #$ff
        sta mn_hover
mn_hover_set:
        jmp mn_draw_items
mn_previous_enabled:
        ldy mn_dh
-       ldx mn_hover
        dex
        cpx mn_dh
        bcc +
        ldx mn_dh
        dex
+       stx mn_hover
        txa
        jsr mn_enabled_row
        bcs mn_hover_set
        dey
        bne -
        lda #$ff
        sta mn_hover
        jmp mn_draw_items

; A new foreground app: its menu is gone with its surface.
mn_reset:
        lda #0
        sta mn_titles
        sta mn_open
        sta mn_prev_down
        rts

mn_surface: .fill 4,0
mn_titles: .byte 0
mn_items: .byte 0
mn_open: .byte 0
mn_hover: .byte $ff
mn_title: .byte 0
mn_row: .byte 0
mn_item: .byte 0
mn_dx: .byte 0
mn_dw: .byte 0
mn_dh: .byte 0
mn_keys: .byte 0
mn_cx: .byte 0
mn_cy: .byte 0
mn_down: .byte 0
mn_prev_down: .byte 0
mn_press: .byte 0
mn_release: .byte 0
mn_delim: .byte 0
mn_math: .byte 0
mn_math16: .word 0
mn_add_off: .word 0
mn_msg_title: .byte 0
mn_msg_item: .byte 0
mn_switch_to: .byte 0
mn_tok_len: .byte 0
mn_pool_len: .word 0
mn_check: .byte $00,$01,$03,$06,$8c,$d8,$70,$20
; RAM tables in the owner-30 data segment (aesvc.asm AE_DATA)
        .section aesdata
mn_tok: .fill MN_TEXT_MAX+2,0
mn_title_len: .fill MN_MAX_TITLES,0
mn_title_x: .fill MN_MAX_TITLES,0
mn_title_first: .fill MN_MAX_TITLES,0
mn_title_count: .fill MN_MAX_TITLES,0
mn_title_off_lo: .fill MN_MAX_TITLES,0
mn_title_off_hi: .fill MN_MAX_TITLES,0
mn_item_len: .fill MN_MAX_ITEMS,0
mn_item_key: .fill MN_MAX_ITEMS,0
mn_item_flags: .fill MN_MAX_ITEMS,0
mn_item_off_lo: .fill MN_MAX_ITEMS,0
mn_item_off_hi: .fill MN_MAX_ITEMS,0
mn_pool: .fill MN_POOL_SIZE,0
        .send aesdata
