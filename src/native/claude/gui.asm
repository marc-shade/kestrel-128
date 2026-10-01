; Fixed ABI inside the cc65 native image. No extra resident kernel code.
; The retained terminal supplies glyphs without borrowing the VDC address port.
; The serial NMI handler never touches VDC registers, zero page or native APIs.
* = $6080
.include "../api.inc"
gui_begin: jmp cg_begin
gui_poll:  jmp cg_poll
gui_key:   jmp cg_key
gui_end:   jmp cg_end
gui_dirty_all: jmp cg_dirty_all

cg_surface:
        lda N_CURRENT
        sta N_OWNER
        ldx #3
-       lda cg_handle,x
        sta N_HANDLE,x
        dex
        bpl -
        rts
cg_begin:
        lda #0
        sta cg_bitmap
        sta cg_handle
        sta N_BANK
        lda N_CURRENT
        sta N_OWNER
        lda #$c0
        sta N_PAGE
        lda #36
        sta N_PAGES
        jsr N_RESERVE
        bcs cg_failed
        ldx #3
-       lda N_HANDLE,x
        sta cg_handle,x
        dex
        bpl -
        lda #<cg_scene
        ldx #>cg_scene
        jsr cg_source
        lda #0
        sta N_OFFSET
        sta N_OFFSET+1
        sta N_COUNT
        lda #2
        sta N_COUNT+1
-       jsr cg_unpack
        bcs cg_failed
        inc N_OFFSET+1
        inc N_OFFSET+1
        lda N_OFFSET+1
        cmp #36
        bne -
        jsr N_VSHOW
        bcs cg_failed
        inc cg_bitmap
        lda $d020
        sta cg_border
        lda #6
        sta $d020
        jsr cg_keys_begin
        jsr pm_install
        bcs cg_failed
        jsr cg_dirty_all
        inc cg_controls_dirty
        ldx #16
-       txa
        pha
        jsr cg_panel
        pla
        tax
        dex
        bne -
        jsr cg_controls
        jmp cg_vdc_sync
cg_failed:
        sta cg_error
cg_end:
        jsr cg_vdc_close
        bcs cg_end_return
        jsr pm_close
        jsr cg_keys_end
        lda cg_bitmap
        beq +
        jsr N_VCLOSE
        lda cg_border
        sta $d020
        lda #0
        sta cg_bitmap
+       lda cg_handle
        beq +
        jsr cg_surface
        jsr N_FREE
        bcs +
        lda #0
        sta cg_handle
+       lda #0
        tax
        clc
cg_end_return:
        rts

; Runs 1..127: count/value. Literals: $80|(count-1), followed by 1..128 bytes.
; Both forms can cross the bounded native transfer's buffer chunks.
cg_source:
        sta cg_source_read+1
        stx cg_source_read+2
        lda #0
        sta cg_run
        rts
cg_byte:
cg_source_read:
        lda $ffff
        inc cg_source_read+1
        bne +
        inc cg_source_read+2
+       rts
cg_unpack:
        lda #<N_BUFFER
        sta cg_store+1
        lda #>N_BUFFER
        sta cg_store+2
        lda N_COUNT
        sta cg_left
        lda N_COUNT+1
        sta cg_left+1
-       lda cg_run
        bne +
        jsr cg_byte
        cmp #128
        bcs cg_literal_run
        sta cg_run
        jsr cg_byte
        sta cg_run_value
        lda #0
        sta cg_literal
        beq +
cg_literal_run:
        and #127
        clc
        adc #1
        sta cg_run
        lda #1
        sta cg_literal
+       lda cg_literal
        beq cg_repeated_byte
        jsr cg_byte
        jmp cg_output_byte
cg_repeated_byte:
        lda cg_run_value
cg_output_byte:
cg_store:
        sta $ffff
        inc cg_store+1
        bne +
        inc cg_store+2
+       dec cg_run
        lda cg_left
        bne +
        dec cg_left+1
+       dec cg_left
        lda cg_left
        ora cg_left+1
        bne -
        jmp N_WRITE

cg_dirty_all:
        lda #1
        ldx #24
-       sta cg_dirty,x
        dex
        bpl -
        rts

; Cell row -> its 40-byte screen offset. Uses no cc65 zero page.
cg_offset:
        lda cg_row
        asl
        asl
        asl
        sta N_OFFSET
        tay
        lda #0
        sta N_OFFSET+1
        asl N_OFFSET
        rol N_OFFSET+1
        asl N_OFFSET
        rol N_OFFSET+1
        tya
        clc
        adc N_OFFSET
        sta N_OFFSET
        bcc +
        inc N_OFFSET+1
+       rts
cg_bitmap_offset:
        jsr cg_offset
        ldx #3
-       asl N_OFFSET
        rol N_OFFSET+1
        dex
        bne -
        rts

; Draw at most one visible panel row per poll, after the receive ring drains.
; Keep all 25 rows and their colors in the existing, hidden text screen.
cg_panel:
        tsx
        stx cg_panel_stack
        lda cg_bitmap
        beq cg_panel_return
        lda cg_recovery
        beq +
        lda cg_font_ram
        beq cg_panel_return
+
        lda cg_top
        clc
        adc #16
        sta cg_limit
        ldx cg_top
-       lda cg_dirty,x
        bne cg_panel_found
        inx
        cpx cg_limit
        bne -
cg_panel_return:
        rts
cg_panel_found:
        stx cg_panel_row
        stx cg_row
        jsr cg_surface
        jsr cg_offset
        lda N_OFFSET
        sta cg_code_read+1
        sta cg_color_read+1
        lda N_OFFSET+1
        clc
        adc #4
        sta cg_code_read+2
        clc
        adc #$d4
        sta cg_color_read+2
        lda cg_view
        beq cg_panel_sources_ready
        lda cg_panel_row
        ldx #0
        jsr cg_terminal_read
        bcs cg_failed
        jsr cg_terminal_column
        ldx #0
-       lda N_BUFFER,y
        sta cg_cells,x
        iny
        inx
        cpx #40
        bne -
        lda cg_panel_row
        ldx #1
        jsr cg_terminal_read
        bcs cg_failed
        jsr cg_terminal_column
        ldx #0
-       lda N_BUFFER,y
        sta cg_attrs,x
        iny
        inx
        cpx #40
        bne -
        lda #<cg_cells
        sta cg_code_read+1
        lda #>cg_cells
        sta cg_code_read+2
        lda #<cg_attrs
        sta cg_color_read+1
        lda #>cg_attrs
        sta cg_color_read+2
cg_panel_sources_ready:
        lda #<N_BUFFER
        sta cg_glyph_store+1
        lda #>N_BUFFER
        sta cg_glyph_store+2
        lda #0
        sta cg_column
cg_panel_cell:
        ldx cg_column
cg_code_read:
        lda $ffff,x
        ldx #0
        stx cg_glyph_hi
        asl
        rol cg_glyph_hi
        asl
        rol cg_glyph_hi
        asl
        rol cg_glyph_hi
        asl
        rol cg_glyph_hi
        sta cg_glyph_lo
        lda cg_glyph_hi
        clc
        adc cg_font_hi
        sta cg_glyph_hi
        lda cg_font_ram
        beq cg_vdc_glyph
        lda cg_glyph_lo
        sta cg_ram_glyph+1
        lda cg_glyph_hi
        sta cg_ram_glyph+2
        ldy #0
cg_ram_glyph:
        lda $ffff,y
        jsr cg_terminal_ink
        jsr cg_glyph_write
        iny
        cpy #8
        bne cg_ram_glyph
        jmp cg_glyph_next
cg_vdc_glyph:
        jsr cg_vdc_address
        jsr cg_vdc_wait
        lda $d601              ; prime the VDC read latch, then rewind
        jsr cg_vdc_address
        ldy #0
-       jsr cg_vdc_wait
        lda $d601
        jsr cg_glyph_write
        iny
        cpy #8
        bne -
cg_glyph_next:
        clc
        lda cg_glyph_store+1
        adc #8
        sta cg_glyph_store+1
        bcc +
        inc cg_glyph_store+2
+       inc cg_column
        lda cg_column
        cmp #40
        bne cg_panel_cell
        jmp cg_panel_store
cg_glyph_write:
cg_glyph_store:
        sta $ffff,y
        rts
cg_panel_store:
        jsr cg_surface
        lda cg_panel_row
        sec
        sbc cg_top
        clc
        adc #5
        sta cg_row
        jsr cg_bitmap_offset
        lda #$40
        sta N_COUNT
        lda #1
        sta N_COUNT+1
        jsr N_WRITE
        bcs cg_failed
        ldx #39
cg_color_read:
        lda $ffff,x
        ldy cg_view
        beq cg_panel_color
        and #15
        tay
        lda cg_vdc_colors,y
cg_panel_color:
        asl
        asl
        asl
        asl
        ldy cg_view
        bne +
        ora #6
+
        sta N_BUFFER,x
        dex
        bpl cg_color_read
        jsr cg_offset
        lda N_OFFSET+1
        clc
        adc #32
        sta N_OFFSET+1
        lda #40
        sta N_COUNT
        lda #0
        sta N_COUNT+1
        jsr N_WRITE
        bcs cg_failed
        jsr cg_vdc_mark_row
        ldx cg_panel_row
        lda #0
        sta cg_dirty,x
        rts
cg_terminal_column:
        ldy #0
        lda cg_view
        cmp #2
        bne +
        ldy #40
+       rts
cg_terminal_read:
        jsr $ffff               ; populated only after the model is owned
        rts
cg_terminal_ink:
        ldx cg_view
        beq cg_ink_return
        sta cg_ink
        ldx cg_column
        lda cg_attrs,x
        and #$20
        beq +
        cpy #7
        bne +
        lda #255
        sta cg_ink
+       lda cg_attrs,x
        and #$40
        beq +
        lda cg_ink
        eor #255
        sta cg_ink
+       lda cg_cursor_row
        cmp cg_panel_row
        bne cg_terminal_no_cursor
        lda cg_view
        cmp #2
        lda cg_column
        bcc +
        clc
        adc #40
+       cmp cg_cursor_col
        bne cg_terminal_no_cursor
        lda cg_ink
        eor #255
        sta cg_ink
cg_terminal_no_cursor:
        lda cg_ink
cg_ink_return:
        rts
cg_vdc_address:
        ldx #18
        lda cg_glyph_hi
        jsr cg_vdc_reg
        inx
        lda cg_glyph_lo
        jsr cg_vdc_reg
        lda #31
        sta $d600
        rts
cg_vdc_reg:
        stx $d600
        jsr cg_vdc_wait
        sta $d601
        rts
cg_vdc_wait:
        pha
        lda #0
        sta cg_wait
        sta cg_wait+1
-       bit $d600
        bmi +
        dec cg_wait
        bne -
        dec cg_wait+1
        bne -
        lda #1
        sta cg_recovery
        sta cg_controls_dirty
        lda #N_PLATFORM
        sta cg_error
        ldx cg_panel_stack
        txs
        sec
        rts
+       pla
        rts

cg_enabled:
        lda cg_recovery
        beq +
        cpx #2
        beq cg_yes
        bne cg_no
+
        cpx #6
        bne +
        lda cg_live
        cmp #1
        bne cg_no
        lda cg_menu
        beq cg_no
        bne cg_yes
+
        cpx #5
        bne +
        lda cg_font_ram
        bne cg_yes
        beq cg_no
+
        cpx #2
        beq cg_yes
        cpx #0
        bne +
        lda cg_live
        beq cg_yes
        lda cg_menu
        beq cg_no
        lda cg_font_ram
        bne cg_yes
        beq cg_no
+       cpx #1
        bne +
        lda cg_live
        cmp #1
        beq cg_yes
        bne cg_no
+       cpx #3
        bne +
        lda cg_top
        bne cg_yes
        beq cg_no
+       cpx #4
        bne cg_no
        lda cg_top
        beq cg_yes
cg_no:  sec
        rts
cg_yes: clc
        rts
cg_hit:
        lda pm_x+1
        lsr
        lda pm_x
        ror
        lsr
        lsr
        sta cg_hit_x
        lda pm_y
        lsr
        lsr
        lsr
        sta cg_hit_y
        ldx #0
-       jsr cg_enabled
        bcs +
        lda cg_hit_x
        cmp cg_x0,x
        bcc +
        cmp cg_x1,x
        bcs +
        lda cg_hit_y
        cmp cg_y0,x
        bcc +
        cmp cg_y1,x
        bcc cg_hit_return
+       inx
        cpx #7
        bne -
        ldx #255
cg_hit_return:
        rts
cg_focus_set:
        cpx cg_focus
        beq +
        stx cg_focus
        inc cg_controls_dirty
+       rts
cg_activate:
        jsr cg_enabled
        bcs cg_zero
        cpx #2
        bcs +
        lda cg_menu
        beq +
        cpx #0
        beq cg_clip_copy
        lda #254
        ldx #0
        rts
+       cpx #6
        beq cg_terminal_activate
        cpx #5
        beq cg_view_next
        cpx #3
        bcs cg_page
        lda #0
        sta cg_menu
        inc cg_controls_dirty
        lda cg_actions,x
        ldx #0
        rts
cg_page:
        lda cg_top
        eor #9
        sta cg_top
        txa
        eor #7               ; Prev <-> Next; focus stays on an enabled button
        sta cg_focus
        inc cg_controls_dirty
        jsr cg_dirty_all
        jmp cg_zero
cg_view_next:
        inc cg_view
        lda cg_view
        cmp #3
        bne +
        lda #0
        sta cg_view
+       inc cg_controls_dirty
        jsr cg_dirty_all
        jmp cg_zero
cg_terminal_activate:
        lda #0
        sta cg_menu
        inc cg_controls_dirty
cg_zero:
        lda #0
        tax
        rts

cg_key:
        sta cg_keycode
        lda cg_recovery
        beq +
        lda cg_keycode
        cmp #27
        bne cg_recovery_other_key
        lda cg_retiring
        bne cg_key_return
        jsr cg_vdc_close
        bcs cg_zero
        lda #0
        sta cg_menu
        inc cg_controls_dirty
        jmp cg_zero
cg_recovery_other_key:
        lda cg_keycode
        cmp #$8c
        beq cg_key_return
        jmp cg_zero
+
        lda cg_bitmap
        beq cg_key_return
        lda cg_keycode
        beq cg_key_return
        lda #0
        sta N_READY
        lda #255
        sta pm_arm
        lda cg_keycode
        cmp #$8c
        beq cg_key_return
        cmp #255              ; Ctrl+Help, decoded at KEYCHK with its modifiers
        beq cg_menu_toggle
        lda cg_live
        beq cg_local_key
        cmp #1
        bne cg_key_return
        lda cg_menu
        beq cg_key_return
cg_local_key:
        lda cg_menu
        beq +
        lda cg_keycode
        cmp #3
        beq cg_clip_copy
        cmp #22
        bne +
        lda #254
        ldx #0
        rts
+       lda cg_keycode
        cmp #9
        beq cg_next
        cmp #$11
        beq cg_next
        cmp #$1d
        beq cg_next
        cmp #$18
        beq cg_previous
        cmp #$91
        beq cg_previous
        cmp #$9d
        beq cg_previous
        cmp #13
        beq cg_key_activate
        cmp #32
        beq cg_key_activate
        cmp #27
        bne cg_local_help
        lda cg_paste_active
        beq cg_local_escape
        lda #253
        ldx #0
        rts
cg_local_escape:
        lda cg_live
        beq cg_key_return
        lda #0
        sta cg_menu
        inc cg_controls_dirty
        jmp cg_zero
cg_local_help:
        lda cg_keycode
        cmp #$84
        beq cg_key_return
        jmp cg_zero
cg_key_return:
        lda cg_keycode
        ldx #0
        rts
cg_menu_toggle:
        lda #0
        sta cg_clip_status
        lda cg_live
        cmp #1
        bne cg_zero
        lda cg_menu
        eor #1
        sta cg_menu
        inc cg_controls_dirty
        jmp cg_zero
cg_key_activate:
        ldx cg_focus
        jmp cg_activate
cg_next:
        ldx cg_focus
-       inx
        cpx #7
        bcc +
        ldx #0
+       jsr cg_enabled
        bcs -
        jsr cg_focus_set
        jmp cg_zero
cg_previous:
        ldx cg_focus
-       dex
        bpl +
        ldx #6
+       jsr cg_enabled
        bcs -
        jsr cg_focus_set
        jmp cg_zero

cg_poll:
        lda cg_bitmap
        beq cg_zero
        lda #0
        sta N_READY
        sta cg_action
        lda cg_live
        cmp cg_seen_live
        beq +
        sta cg_seen_live
        sta cg_focus           ; Connect / Repaint / Desktop
        lda #0
        sta cg_menu
        lda #255
        sta pm_arm
        inc cg_controls_dirty
+       lda pm_seen
        sta cg_mouse_was_seen
        jsr pm_poll
        lda pm_seen
        beq cg_secondary_clear
        lda cg_mouse_was_seen
        beq cg_secondary_track
        lda pm_secondary_down
        cmp cg_secondary_seen
        beq cg_secondary_done
        sta cg_secondary_seen
        cmp #0
        beq cg_secondary_done
        lda cg_recovery
        bne cg_secondary_done
        lda cg_live
        cmp #1
        bne cg_secondary_done
        lda cg_menu
        eor #1
        sta cg_menu
        inc cg_controls_dirty
        lda #255
        sta pm_arm
        jmp cg_secondary_done
cg_secondary_clear:
        lda #0
        beq cg_secondary_save
cg_secondary_track:
        lda pm_secondary_down
cg_secondary_save:
        sta cg_secondary_seen
cg_secondary_done:
        lda pm_event
        beq +
        ldx pm_hit
        jsr cg_enabled
        bcs +
        jsr cg_focus_set
        lda pm_event
        cmp #2
        bne +
        ldx cg_focus
        jsr cg_activate
        sta cg_action
+       lda cg_controls_dirty
        beq +
        jsr cg_controls
+       jsr cg_panel
        jsr cg_vdc_sync
        lda cg_action
        ldx #0
        rts

cg_controls:
        jsr cg_surface
        lda cg_header_lo
        ldx cg_header_hi
        ldy cg_menu
        beq +
        lda cg_header_lo+1
        ldx cg_header_hi+1
+       jsr cg_source
        lda #1
        sta cg_row
cg_header_draw:
        jsr cg_row_unpack
        bcs cg_failed
        inc cg_row
        lda cg_row
        cmp #4
        bne cg_header_draw
        lda #0
        sta cg_control
cg_control_next:
        ldx cg_control
        lda #$b6
        sta N_VALUE
        jsr cg_enabled
        bcs +
        lda #$1b
        cpx cg_focus
        bne cg_control_color
        lda #7
cg_control_color:
        sta N_VALUE
+       lda cg_y0,x
        sta cg_row
-       jsr cg_offset
        ldx cg_control
        lda N_OFFSET
        clc
        adc cg_x0,x
        sta N_OFFSET
        lda N_OFFSET+1
        adc #32
        sta N_OFFSET+1
        lda cg_x1,x
        sec
        sbc cg_x0,x
        sta N_COUNT
        lda #0
        sta N_COUNT+1
        jsr N_FILL
        bcs cg_failed
        inc cg_row
        ldx cg_control
        lda cg_row
        cmp cg_y1,x
        bne -
        inc cg_control
        lda cg_control
        cmp #7
        bne cg_control_next
        ldy #4
        lda cg_recovery
        bne cg_status_ready
        ldy cg_live
        cpy #1
        bne +
        lda cg_menu
        beq +
        ldy #3
+
cg_status_ready:
        lda cg_recovery
        bne +
        lda cg_menu
        beq +
        lda cg_clip_status
        beq +
        tay
+       lda cg_status_lo,y
        ldx cg_status_hi,y
        jsr cg_source
        lda #4
        sta cg_row
        jsr cg_row_unpack
        bcs cg_failed
        lda cg_view
        asl
        tay
        lda cg_top
        beq +
        iny
+       lda cg_page_lo,y
        ldx cg_page_hi,y
        jsr cg_source
        lda #22
        sta cg_row
        jsr cg_bitmap_offset
        lda N_OFFSET
        clc
        adc #96
        sta N_OFFSET
        lda N_OFFSET+1
        adc #0
        sta N_OFFSET+1
        lda #128
        sta N_COUNT
        lda #0
        sta N_COUNT+1
        jsr cg_unpack
        bcs cg_failed
        lda #0
        sta cg_controls_dirty
        jmp cg_vdc_controls
cg_row_unpack:
        jsr cg_bitmap_offset
        lda #$40
        sta N_COUNT
        lda #1
        sta N_COUNT+1
        jmp cg_unpack

; Own only the KEYCHK callback here; c128hw.s owns and restores the full table.
cg_keys_begin:
        php
        sei
        ldx #0
-       lda nk_filter_image,x
        sta pk_entry,x
        inx
        cpx #pk_end-pk_entry
        bne -
        lda $033c
        sta cg_saved_callback
        sta pk_next
        lda $033d
        sta cg_saved_callback+1
        sta pk_next+1
        lda #<pk_entry
        sta $033c
        lda #>pk_entry
        sta $033d
        lda #1
        sta cg_keys_owned
        plp
        rts
cg_keys_end:
        lda cg_keys_owned
        beq +
        php
        sei
        lda cg_saved_callback
        sta $033c
        lda cg_saved_callback+1
        sta $033d
        lda #0
        sta cg_keys_owned
        plp
+       rts

cg_x0: .byte 1,14,27,1,29,12,27
cg_x1: .byte 12,25,39,11,39,28,39
cg_y0: .byte 1,1,1,21,21,21,0
cg_y1: .byte 4,4,4,24,24,24,1
cg_actions: .byte 13,$84,$8c
cg_header_lo: .byte <cg_header_0,<cg_header_1
cg_header_hi: .byte >cg_header_0,>cg_header_1
cg_status_lo: .byte <cg_status_0,<cg_status_1,<cg_status_2,<cg_status_3,<cg_status_4,<cg_status_5,<cg_status_6,<cg_status_7,<cg_status_8,<cg_status_9,<cg_status_10,<cg_status_11,<cg_status_12
cg_status_hi: .byte >cg_status_0,>cg_status_1,>cg_status_2,>cg_status_3,>cg_status_4,>cg_status_5,>cg_status_6,>cg_status_7,>cg_status_8,>cg_status_9,>cg_status_10,>cg_status_11,>cg_status_12
cg_page_lo: .byte <cg_page_0_0,<cg_page_0_9,<cg_page_1_0,<cg_page_1_9,<cg_page_2_0,<cg_page_2_9
cg_page_hi: .byte >cg_page_0_0,>cg_page_0_9,>cg_page_1_0,>cg_page_1_9,>cg_page_2_0,>cg_page_2_9
cg_vdc_colors: .byte 0,11,6,14,5,13,3,3,2,10,4,4,9,7,15,1
cg_font_ram: .byte 0
cg_view: .byte 0
cg_cursor_row: .byte 255
cg_cursor_col: .byte 255
cg_ink: .byte 0
cg_panel_stack: .byte 0
cg_wait: .word 0
cg_secondary_seen: .byte 0
cg_mouse_was_seen: .byte 0
cg_cells: .fill 40,0
cg_attrs: .fill 40,0
cg_bitmap: .byte 0
cg_border: .byte 0
cg_handle: .fill 4,0
cg_error: .byte 0
cg_live: .byte 0
cg_menu: .byte 0
cg_seen_live: .byte 0
cg_focus: .byte 0
cg_top: .byte 0
cg_font_hi: .byte 0
cg_dirty: .fill 25,0
cg_controls_dirty: .byte 0
cg_control: .byte 0
cg_row: .byte 0
cg_panel_row: .byte 0
cg_column: .byte 0
cg_limit: .byte 0
cg_hit_x: .byte 0
cg_hit_y: .byte 0
cg_keycode: .byte 0
cg_action: .byte 0
cg_glyph_lo: .byte 0
cg_glyph_hi: .byte 0
cg_run: .byte 0
cg_run_value: .byte 0
cg_literal: .byte 0
cg_left: .word 0
cg_keys_owned: .byte 0
cg_saved_callback: .word 0
.include "scene.inc"
PM_KEYS_OWNED=1
PM_KEYS_EXTERNAL=1
PM_SECONDARY=1
NK_LOCAL_HELP=1
NK_LOCAL_SECONDARY=1
pm_control_count=7
pm_select_surface=cg_surface
pm_find_hit=cg_hit
.include "../input/pointer.inc"
.include "../input/key-filter.inc"
.include "vdc.inc"
.include "clipboard.inc"
gui_limit = *
