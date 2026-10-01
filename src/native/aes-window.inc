; AES windows (GEM wind_create/open/close/delete/set/get/find), bank 1.
; See docs/NATIVE-AES.md#windows. Windows live on the 40x25 cell grid below
; the menu row. A cell map names the top window of every cell; each change
; compares it with the previous map, redraws the frames it uncovered or
; changed, clears uncovered desktop cells and queues WM_REDRAW for work areas.
WN_MAX = 7
WN_DESKTOP = $16             ; cleared desktop: blue paper, as the suite
WN_TITLE_MAX = 16

; One op, sub-operation in N_BUFFER[0], handle in N_BUFFER[1]:
; 0 create (2..3 kind, 4..7 full rect) -> [0] handle
; 1 open (2..5 rect)   2 close   3 delete
; 4 set (2 field, 3.. value)     5 get (2 field) -> [0..3]
; 6 find (1 x, 2 y cells) -> [0] handle
; 7 fill (1 handle, 2 pen, 3 colour, 4..7 clip rect): paint the visible
;   work area of a window inside the clip (the app's WM_REDRAW response)
; 8 surface (1..4 handle): the app surface windows are drawn on
; 9 outline (1..4 x, y, w, h cells): XOR a one-pixel outline on that
;   surface; the same call again erases it (feedback for a client's drag)
; 10 text (1 handle, 2..3 first cell x, y counted in the work area, 4 pen,
;   5.. NUL-terminated ASCII, at most 38): draw it into the visible work
;   area, clipped as fill is (GEM v_gtext); the cells keep their colours
; Every reply carries the cell rows drawn in bytes 4..7.
wn_entry:
        jsr al_clear_dirty
        lda N_BUFFER
        cmp #11
        bcs wn_badarg
        asl
        tax
        lda wn_ops+1,x
        pha
        lda wn_ops,x
        pha
        rts
wn_ops: .word wn_create-1,wn_open-1,wn_close-1,wn_delete-1
        .word wn_set-1,wn_get-1,wn_find-1,wn_fill-1,wn_bind_surface-1,wn_client_outline-1
        .word wn_text-1
wn_badarg:
        lda #N_BADARG
        sec
        rts
wn_done:
        ldx #3
-       lda al_dirty,x
        sta N_BUFFER+4,x
        dex
        bpl -
        lda #0
        clc
        rts

wn_client_outline:
        ldx #3
-       lda N_BUFFER+1,x
        sta wn_dx,x             ; (wn_dx, dy, dw, dh are consecutive)
        dex
        bpl -
        jsr wn_outline
        bcc wn_done
        rts
wn_bind_surface:
        ldx #3
-       lda N_BUFFER+1,x
        sta wn_surface,x
        dex
        bpl -
        jmp wn_done

; ---- create / delete ---------------------------------------------------------
wn_create:
        ldx #4
        jsr wn_rect_valid
        bcs wn_badarg
        ldx #1
-       lda wn_flags,x
        beq +
        inx
        cpx #WN_MAX+1
        bne -
        lda #N_NOSLOT
        sec
        rts
+       lda #1
        sta wn_flags,x
        lda N_BUFFER+2
        sta wn_kind_lo,x
        lda N_BUFFER+3
        and #$0f
        sta wn_kind_hi,x
        lda N_BUFFER+4
        sta wn_fx,x
        sta wn_x,x
        sta wn_px,x
        lda N_BUFFER+5
        sta wn_fy,x
        sta wn_y,x
        sta wn_py,x
        lda N_BUFFER+6
        sta wn_fw,x
        sta wn_w,x
        sta wn_pw,x
        lda N_BUFFER+7
        sta wn_fh,x
        sta wn_h,x
        sta wn_ph,x
        lda #0
        sta wn_title_len,x
        sta wn_vpos,x
        sta wn_hpos,x
        lda #255
        sta wn_vsize,x
        sta wn_hsize,x
        stx N_BUFFER
        jmp wn_done
wn_delete:
        jsr wn_handle
        bcs wn_badarg
        lda wn_flags,x
        cmp #1                  ; only created, closed windows
        bne wn_badarg
        lda #0
        sta wn_flags,x
        jmp wn_done
; N_BUFFER[1] must name a created window: X = handle.
wn_handle:
        ldx N_BUFFER+1
        beq +
        cpx #WN_MAX+1
        bcs +
        lda wn_flags,x
        beq +
        clc
        rts
+       sec
        rts
; X = packet offset of x,y,w,h: carry set unless 4x3 cells or larger lie
; within columns 0..39 and rows 1..24.
wn_rect_valid:
        lda N_BUFFER+2,x        ; w
        cmp #4
        bcc +
        clc
        adc N_BUFFER,x
        bcs +
        cmp #41
        bcs +
        lda N_BUFFER+1,x        ; y
        beq +
        lda N_BUFFER+3,x        ; h
        cmp #3
        bcc +
        clc
        adc N_BUFFER+1,x
        bcs +
        cmp #26
        rts                     ; carry set when past row 24
+       sec
        rts

; ---- open / close / top / move --------------------------------------------------
wn_open:
        jsr wn_handle
        bcs wn_badarg
        lda wn_flags,x
        cmp #1
        bne wn_badarg           ; already open
        stx wn_h_arg
        ldx #2
        jsr wn_rect_valid
        bcs wn_badarg
        jsr wn_snapshot
        ldx wn_h_arg
        jsr wn_store_rect
        lda #3
        sta wn_flags,x
        jsr wn_push_top
        jmp wn_change
wn_close:
        jsr wn_handle
        bcs wn_badarg
        lda wn_flags,x
        cmp #3
        bne wn_badarg
        stx wn_h_arg
        jsr wn_snapshot
        ldx wn_h_arg
        lda #1
        sta wn_flags,x
        jsr wn_remove
        jmp wn_change
; Keep the current rectangle as the previous one, take N_BUFFER[2..5].
wn_store_rect:
        lda wn_x,x
        sta wn_px,x
        lda wn_y,x
        sta wn_py,x
        lda wn_w,x
        sta wn_pw,x
        lda wn_h,x
        sta wn_ph,x
        lda N_BUFFER+2
        sta wn_x,x
        lda N_BUFFER+3
        sta wn_y,x
        lda N_BUFFER+4
        sta wn_w,x
        lda N_BUFFER+5
        sta wn_h,x
        lda #1
        sta wn_force,x          ; whole window redrawn after a move/size/open
        rts
; Put window X on top of the stack (removing it first when present).
wn_push_top:
        stx wn_math
        jsr wn_remove
        ldx wn_count
-       beq +
        lda wn_order-1,x
        sta wn_order,x
        dex
        bne -
+       lda wn_math
        sta wn_order
        inc wn_count
        rts
; Remove window X from the stack if present.
wn_remove:
        stx wn_math2
        ldy #0
        ldx #0
-       cpx wn_count
        beq ++
        lda wn_order,x
        cmp wn_math2
        beq +
        sta wn_order,y
        iny
+       inx
        bne -
+       sty wn_count
        ldx wn_math2
        rts

; ---- set / get / find ---------------------------------------------------------
wn_set:
        lda N_BUFFER+1          ; the desktop's colour: repaint every desktop
        bne +                   ; cell and ask for its redraw
        lda N_BUFFER+2
        cmp #WF_DESKCOLOR
        bne +
        lda N_BUFFER+3
        sta wn_desk_color
        lda #1
        sta wn_force
        jmp wn_change
+       jsr wn_handle
        bcc +
        jmp wn_badarg
+       stx wn_h_arg
        lda N_BUFFER+2
        cmp #WF_NAME
        beq wn_set_name
        cmp #WF_CURRXYWH
        beq wn_set_rect
        cmp #WF_TOP
        beq wn_set_top
        cmp #WF_VSLIDE
        beq wn_set_vpos
        cmp #WF_HSLIDE
        beq wn_set_hpos
        cmp #WF_VSLSIZE
        beq wn_set_vsize
        cmp #WF_HSLSIZE
        beq wn_set_hsize
        jmp wn_badarg
wn_set_vpos:
        lda N_BUFFER+3
        sta wn_vpos,x
        jmp wn_set_frame
wn_set_hpos:
        lda N_BUFFER+3
        sta wn_hpos,x
        jmp wn_set_frame
wn_set_vsize:
        lda N_BUFFER+3
        sta wn_vsize,x
        jmp wn_set_frame
wn_set_hsize:
        lda N_BUFFER+3
        sta wn_hsize,x
        jmp wn_set_frame
wn_set_name:
        ldy #0
-       lda N_BUFFER+3,y        ; NUL-terminated, 0..16 printable ASCII
        beq +
        cpy #WN_TITLE_MAX
        bcs wn_set_bad
        cmp #32
        bcc wn_set_bad
        cmp #127
        bcs wn_set_bad
        iny
        bne -
+       tya
        sta wn_title_len,x
        txa
        asl
        asl
        asl
        asl
        tax
        ldy #0
-       lda N_BUFFER+3,y
        sta wn_title,x
        inx
        iny
        cpy #WN_TITLE_MAX
        bne -
        ldx wn_h_arg
wn_set_frame:
        lda wn_flags,x          ; an open window redraws its frame now
        cmp #3
        bne +
        jsr wn_draw_frame
        bcs wn_set_fail
+       jmp wn_done
wn_set_bad:
        jmp wn_badarg
wn_set_fail:
        rts
wn_set_rect:
        ldx #3
        jsr wn_rect_valid       ; x,y,w,h at N_BUFFER[3..6]
        bcs wn_set_bad
        ldx #0                  ; wn_store_rect reads [2..5]: copy upward
-       lda N_BUFFER+3,x
        sta N_BUFFER+2,x
        inx
        cpx #4
        bne -
        jsr wn_snapshot
        ldx wn_h_arg
        jsr wn_store_rect
        lda wn_flags,x
        cmp #3
        beq wn_change
        jmp wn_done             ; a closed window just keeps the rectangle
wn_set_top:
        lda wn_flags,x
        cmp #3
        bne wn_set_bad
        jsr wn_snapshot
        ldx wn_h_arg
        jsr wn_push_top
        jmp wn_change

wn_get:
        lda N_BUFFER+2
        cmp #WF_TOP
        bne wn_get_other
        lda #0                  ; 0: no open window
        ldx wn_count
        beq +
        lda wn_order
+       sta N_BUFFER
        jmp wn_done
wn_get_other:
        cmp #WF_FIRSTXYWH
        beq wn_get_first
        cmp #WF_NEXTXYWH
        beq wn_get_next
        jsr wn_handle
        bcs wn_get_bad
        lda N_BUFFER+2
        cmp #WF_CURRXYWH
        beq wn_get_curr
        cmp #WF_PREVXYWH
        beq wn_get_prev
        cmp #WF_FULLXYWH
        beq wn_get_full
        cmp #WF_WORKXYWH
        bne wn_get_bad
        jsr wn_geometry
        lda wn_wx
        sta N_BUFFER
        lda wn_wy
        sta N_BUFFER+1
        lda wn_ww
        sta N_BUFFER+2
        lda wn_wh
        sta N_BUFFER+3
        jmp wn_done
wn_get_bad:
        jmp wn_badarg
wn_get_curr:
        lda wn_x,x
        ldy wn_y,x
        pha
        lda wn_w,x
        sta N_BUFFER+2
        lda wn_h,x
        jmp wn_get_rect
wn_get_prev:
        lda wn_px,x
        ldy wn_py,x
        pha
        lda wn_pw,x
        sta N_BUFFER+2
        lda wn_ph,x
        jmp wn_get_rect
wn_get_full:
        lda wn_fx,x
        ldy wn_fy,x
        pha
        lda wn_fw,x
        sta N_BUFFER+2
        lda wn_fh,x
wn_get_rect:
        sta N_BUFFER+3
        sty N_BUFFER+1
        pla
        sta N_BUFFER
        jmp wn_done
; FIRSTXYWH: visible rectangles of the window's work area (handle 0: the
; desktop cells of rows 1..24). NEXTXYWH continues; w = 0 ends the list.
wn_get_first:
        ldx N_BUFFER+1
        beq +
        jsr wn_handle
        bcs wn_get_bad
        lda wn_flags,x
        cmp #3
        bne wn_get_bad
+       stx it_h
        jsr wn_area_work
        jsr it_begin
wn_get_next:
        jsr it_next
        lda it_rx
        sta N_BUFFER
        lda it_ry
        sta N_BUFFER+1
        lda it_rw
        sta N_BUFFER+2
        lda it_rh
        sta N_BUFFER+3
        jmp wn_done

wn_find:
        lda N_BUFFER+1
        cmp #40
        bcs +
        ldy N_BUFFER+2
        cpy #25
        bcs +
        jsr wn_cell_address
        ldy #0
        lda (wn_ptr),y
        sta N_BUFFER
        jmp wn_done
+       lda #0
        sta N_BUFFER
        jmp wn_done

; FILL: pen and colour over the visible work area of window N_BUFFER[1]
; (0: desktop) inside the clip rectangle N_BUFFER[4..7].
wn_fill:
        ldx N_BUFFER+1
        beq +
        jsr wn_handle
        bcs wn_get_bad
        lda wn_flags,x
        cmp #3
        bne wn_get_bad
+       stx it_h
        lda N_BUFFER+2
        sta wn_fill_pen
        lda N_BUFFER+3
        sta wn_fill_color
        jsr wn_area_work
        jsr wn_clip_area        ; intersect with N_BUFFER[4..7]
        jsr wn_bind
        bcs wn_fill_done
        jsr it_begin
-       jsr it_next
        lda it_rw
        beq +
        jsr it_pixels
        lda wn_fill_pen
        sta gfx_pen
        jsr gfx_rect
        bcs wn_fill_done
        jsr it_cells
        lda wn_fill_color
        sta gfx_color
        jsr gfx_colors
        bcs wn_fill_done
        jsr wn_mark_rect
        jmp -
+       jmp wn_done
wn_fill_done:
        rts

; TEXT: N_BUFFER[5..] in pen N_BUFFER[4] at work cell N_BUFFER[2..3] of window
; N_BUFFER[1], inside its visible work area.
wn_text:
        ldx N_BUFFER+1
        jsr wn_handle
        bcs wn_text_bad
        lda wn_flags,x
        cmp #3
        bne wn_text_bad
        stx it_h
        ldy #0
-       lda N_BUFFER+5,y
        beq +
        sta gfx_text_buffer,y
        iny
        cpy #38
        bne -
+       sty gfx_text_length
        lda N_BUFFER+4
        sta wn_fill_pen
        jsr wn_area_work
        lda it_ax               ; the clip: the text's own cells
        clc
        adc N_BUFFER+2
        sta N_BUFFER+4
        sta wn_text_x
        lda it_ay
        clc
        adc N_BUFFER+3
        sta N_BUFFER+5
        sta wn_text_y
        sty N_BUFFER+6
        lda #1
        sta N_BUFFER+7
        jsr wn_clip_area
        jsr wn_bind
        bcs wn_text_done
        jsr it_begin
-       jsr it_next
        lda it_rw
        beq wn_text_end
        jsr it_pixels
        jsr gfx_set_clip
        bcs wn_text_done
        lda wn_text_x
        jsr al_times8
        sta gfx_x0
        stx gfx_x0+1
        lda wn_text_y
        jsr al_times8
        sta gfx_y0
        stx gfx_y0+1
        lda wn_fill_pen
        sta gfx_pen
        jsr gfx_text
        bcs wn_text_done
        jsr wn_mark_rect
        jmp -
wn_text_end:
        jsr wn_bind             ; binding again restores the full clip
        bcs wn_text_done
        jmp wn_done
wn_text_bad:
        jmp wn_get_bad
wn_text_done:
        rts
wn_text_x: .byte 0
wn_text_y: .byte 0

; ---- the cell map ------------------------------------------------------------
wn_snapshot:
        ldx #0
-       lda wn_map,x
        sta wn_old,x
        lda wn_map+256,x
        sta wn_old+256,x
        lda wn_map+512,x
        sta wn_old+512,x
        lda wn_map+768,x
        sta wn_old+768,x
        inx
        bne -
        lda #0                  ; the previous top window loses its highlight
        ldx wn_count
        beq +
        lda wn_order
+       sta wn_top_old
        rts
; Rebuild the map from the stack, bottom window first.
wn_rebuild:
        lda #0
        ldx #0
-       sta wn_map,x
        sta wn_map+256,x
        sta wn_map+512,x
        sta wn_map+768,x
        inx
        bne -
        ldx wn_count
wn_rebuild_window:
        dex
        bmi wn_rebuild_done
        stx wn_math
        lda wn_order,x
        tax
        stx wn_math2
        lda wn_y,x
        sta wn_row
        lda wn_h,x
        sta wn_rows
-       ldx wn_math2
        lda wn_x,x
        ldy wn_row
        jsr wn_cell_address
        ldx wn_math2
        ldy wn_w,x
        dey
        txa
-       sta (wn_ptr),y
        dey
        bpl -
        inc wn_row
        dec wn_rows
        bne --
        ldx wn_math
        jmp wn_rebuild_window
wn_rebuild_done:
        rts
; A = column, Y = row -> wn_ptr = wn_map + row*40 + column.
wn_cell_address:
        clc
        adc wn_row40_lo,y
        sta wn_ptr
        lda wn_row40_hi,y
        adc #0
        sta wn_ptr+1
        clc
        lda wn_ptr
        adc #<wn_map
        sta wn_ptr
        lda wn_ptr+1
        adc #>wn_map
        sta wn_ptr+1
        rts

; After a stack or rectangle change: rebuild, find every changed cell, redraw
; frames, clear uncovered desktop cells and queue work-area WM_REDRAWs.
wn_change:
        jsr wn_rebuild
        ldx #WN_MAX             ; empty boxes; frame flags from forced windows
-       lda #$ff
        sta wn_bx0,x
        sta wn_by0,x
        lda #0
        sta wn_bx1,x
        sta wn_by1,x
        lda wn_force,x
        sta wn_frame,x
        dex
        bpl -
        lda wn_count            ; top-window change: both title bars redraw
        beq +
        lda wn_order
+       sta wn_top_new
        cmp wn_top_old
        beq +
        tax
        lda #1
        sta wn_frame,x
        ldx wn_top_old
        sta wn_frame,x
+       lda #1                  ; walk the 960 cells of rows 1..24
        sta wn_row
wn_scan_row:
        lda #0
        sta wn_col
        ldy wn_row
        jsr wn_cell_address
        lda wn_ptr
        sta wn_scan_new+1
        lda wn_ptr+1
        sta wn_scan_new+2
        sec
        lda wn_ptr
        sbc #<wn_map
        sta wn_math16
        lda wn_ptr+1
        sbc #>wn_map
        sta wn_math16+1
        clc
        lda wn_math16
        adc #<wn_old
        sta wn_scan_old+1
        lda wn_math16+1
        adc #>wn_old
        sta wn_scan_old+2
wn_scan_cell:
        ldx wn_col
wn_scan_new:
        lda $ffff,x
        sta wn_new_owner
wn_scan_old:
        cmp $ffff,x
        bne wn_scan_mark
        tax
        lda wn_force,x
        beq wn_scan_next
wn_scan_mark:
        ldx wn_new_owner        ; this cell of this owner needs repainting
        jsr wn_cell_role        ; carry set: a frame cell of that window
        bcc +
        lda #1
        sta wn_frame,x
        bne wn_scan_next
+       lda wn_col              ; work (or desktop) cell: grow the box
        cmp wn_bx0,x
        bcs +
        sta wn_bx0,x
+       cmp wn_bx1,x
        bcc +
        adc #0                  ; carry set: col + 1
        sta wn_bx1,x
+       lda wn_row
        cmp wn_by0,x
        bcs +
        sta wn_by0,x
+       cmp wn_by1,x
        bcc wn_scan_next
        adc #0
        sta wn_by1,x
wn_scan_next:
        inc wn_col
        lda wn_col
        cmp #40
        bne wn_scan_cell
        inc wn_row
        lda wn_row
        cmp #25
        bne wn_scan_row
        ; desktop cells first: clear pixels and colours of what was uncovered
        lda wn_bx0
        cmp #$ff
        beq wn_frames
        lda #0
        sta it_h
        jsr wn_box_area
        jsr wn_bind
        bcs wn_change_fail
        jsr it_begin
-       jsr it_next
        lda it_rw
        beq +
        jsr it_pixels
        lda #0
        sta gfx_pen
        jsr gfx_rect
        bcs wn_change_fail
        jsr it_cells
        lda wn_desk_color
        sta gfx_color
        jsr gfx_colors
        bcs wn_change_fail
        jsr wn_mark_rect
        jmp -
+       lda #0
        jsr wn_queue_redraw
wn_frames:
        ldx #1                  ; frames of every marked open window
-       lda wn_flags,x
        cmp #3
        bne +
        lda wn_frame,x
        beq +
        stx wn_math3
        jsr wn_draw_frame
        bcs wn_change_fail
        ldx wn_math3
+       lda wn_bx0,x            ; and a work-area redraw where cells changed
        cmp #$ff
        beq +
        lda wn_flags,x
        cmp #3
        bne +
        stx wn_math3
        txa
        jsr wn_queue_redraw
        ldx wn_math3
+       lda #0
        sta wn_force,x
        inx
        cpx #WN_MAX+1
        bne -
        lda #0
        sta wn_force
        jmp wn_done
wn_change_fail:
        rts
wn_desk_color: .byte WN_DESKTOP ; image RAM: the choice outlives app changes

; X = owner of the cell at wn_col/wn_row. Carry set when it is a frame cell
; of window X (never for the desktop).
wn_cell_role:
        cpx #0
        bne +
        clc
        rts
+       stx wn_math4
        jsr wn_geometry
        ldx wn_math4
        lda wn_col
        sec
        sbc wn_wx
        cmp wn_ww
        bcs wn_role_frame
        lda wn_row
        sec
        sbc wn_wy
        cmp wn_wh
        bcs wn_role_frame
        clc
        rts
wn_role_frame:
        sec
        rts

; Queue WM_REDRAW for owner A with its box, merging an already queued one.
wn_queue_redraw:
        tax
        stx wn_msg_h
        lda wn_bx0,x
        sta ev_msg_in+4
        lda wn_by0,x
        sta ev_msg_in+5
        lda wn_bx1,x
        sec
        sbc wn_bx0,x
        sta ev_msg_in+6
        lda wn_by1,x
        sec
        sbc wn_by0,x
        sta ev_msg_in+7
        lda #WM_REDRAW
        sta ev_msg_in
        lda #0
        sta ev_msg_in+1
        sta ev_msg_in+2
        lda wn_msg_h
        sta ev_msg_in+3
        jsr ev_merge_redraw     ; union with a queued redraw of the same owner
        bcc +
        jsr ev_push             ; a full queue drops it: FIRSTXYWH still works
+       rts

; ---- geometry ----------------------------------------------------------------
; X = window: work area, bars and gadget positions.
wn_geometry:
        lda wn_x,x
        sta wn_wx
        lda wn_w,x
        sta wn_ww
        lda wn_y,x
        sta wn_wy
        lda wn_h,x
        sta wn_wh
        lda #0
        sta wn_has_title
        sta wn_has_info
        sta wn_has_vbar
        sta wn_has_hbar
        lda wn_kind_lo,x
        and #<(WK_NAME|WK_CLOSER|WK_FULLER|WK_MOVER)
        beq +
        inc wn_has_title
        inc wn_wy
        dec wn_wh
+       lda wn_kind_lo,x
        and #<WK_INFO
        beq +
        inc wn_has_info
        inc wn_wy
        dec wn_wh
+       lda wn_kind_lo,x
        and #<(WK_UPARROW|WK_DNARROW)
        bne +
        lda wn_kind_hi,x
        and #>WK_VSLIDE
        beq ++
+       inc wn_has_vbar
        dec wn_ww
+       lda wn_kind_hi,x
        and #>(WK_LFARROW|WK_RTARROW|WK_HSLIDE)
        bne +
        lda wn_has_vbar         ; a sizer alone takes a bottom row
        bne ++
        lda wn_kind_lo,x
        and #<WK_SIZER
        beq ++
+       inc wn_has_hbar
        dec wn_wh
+       rts
; The work area of it_h as the iterator area (desktop: rows 1..24).
wn_area_work:
        ldx it_h
        bne +
        lda #0
        sta it_ax
        lda #1
        sta it_ay
        lda #40
        sta it_aw
        lda #24
        sta it_ah
        rts
+       jsr wn_geometry
        lda wn_wx
        sta it_ax
        lda wn_wy
        sta it_ay
        lda wn_ww
        sta it_aw
        lda wn_wh
        sta it_ah
        rts
; The changed box of owner it_h as the area.
wn_box_area:
        ldx it_h
        lda wn_bx0,x
        sta it_ax
        lda wn_by0,x
        sta it_ay
        lda wn_bx1,x
        sec
        sbc wn_bx0,x
        sta it_aw
        lda wn_by1,x
        sec
        sbc wn_by0,x
        sta it_ah
        rts
; Intersect the area with the clip rectangle N_BUFFER[4..7].
wn_clip_area:
        lda it_ax               ; right/bottom edges first
        clc
        adc it_aw
        sta wn_math
        lda N_BUFFER+4
        clc
        adc N_BUFFER+6
        cmp wn_math
        bcs +
        sta wn_math
+       lda it_ay
        clc
        adc it_ah
        sta wn_math2
        lda N_BUFFER+5
        clc
        adc N_BUFFER+7
        cmp wn_math2
        bcs +
        sta wn_math2
+       lda N_BUFFER+4
        cmp it_ax
        bcc +
        sta it_ax
+       lda N_BUFFER+5
        cmp it_ay
        bcc +
        sta it_ay
+       lda wn_math             ; empty when the edges crossed
        sec
        sbc it_ax
        bcs +
        lda #0
+       sta it_aw
        lda wn_math2
        sec
        sbc it_ay
        bcs +
        lda #0
+       sta it_ah
        rts

; ---- visible-rectangle iterator ------------------------------------------------
; Cells of owner it_h inside it_ax/ay/aw/ah as rectangles: horizontal runs,
; extended downward while the next row has exactly the same run; a run that
; continues one above was already covered and is skipped.
it_begin:
        lda it_ay
        sta it_row
        lda it_ax
        sta it_col
        rts
it_next:
        lda it_aw
        beq it_end
        lda it_ah
        beq it_end
it_row_loop:
        lda it_ay
        clc
        adc it_ah
        sta wn_math
        lda it_row
        cmp wn_math
        bcs it_end
        lda it_ax
        clc
        adc it_aw
        sta it_x1
it_col_loop:
        lda it_col
        cmp it_x1
        bcs it_next_row
        ldy it_row
        jsr it_owner_at         ; A = owner of (it_col, it_row)
        cmp it_h
        beq it_run_found
        inc it_col
        bne it_col_loop
it_next_row:
        inc it_row
        lda it_ax
        sta it_col
        jmp it_row_loop
it_end:
        lda #0
        sta it_rw
        sta it_rh
        sta it_rx
        sta it_ry
        rts
it_run_found:
        lda it_col              ; run: it_col .. it_run_end-1
        sta it_rx
-       inc it_col
        lda it_col
        cmp it_x1
        bcs +
        ldy it_row
        jsr it_owner_at
        cmp it_h
        beq -
+       lda it_col
        sta it_run_end
        lda it_row              ; already covered from the row above?
        cmp it_ay
        beq +
        sec
        sbc #1
        jsr it_same_run
        bcs it_col_loop         ; yes: skip this run
+       lda it_row
        sta it_ry
        sta it_down
-       inc it_down             ; extend downward
        lda it_ay
        clc
        adc it_ah
        cmp it_down
        beq +
        bcc +
        lda it_down
        jsr it_same_run
        bcs -
+       lda it_run_end
        sec
        sbc it_rx
        sta it_rw
        lda it_down
        sec
        sbc it_ry
        sta it_rh
        rts
; A = row: carry set when that row holds exactly the run it_rx..it_run_end.
it_same_run:
        sta it_test_row
        lda it_rx
        sta it_test_col
-       ldy it_test_row
        lda it_test_col
        jsr it_owner_at_col
        cmp it_h
        bne it_same_no
        inc it_test_col
        lda it_test_col
        cmp it_run_end
        bne -
        lda it_rx               ; the cells either side must not belong
        cmp it_ax
        beq +
        sec
        sbc #1
        ldy it_test_row
        jsr it_owner_at_col
        cmp it_h
        beq it_same_no
+       lda it_run_end
        cmp it_x1
        beq +
        ldy it_test_row
        jsr it_owner_at_col
        cmp it_h
        beq it_same_no
+       sec
        rts
it_same_no:
        clc
        rts
it_owner_at:
        lda it_col
; A = column, Y = row -> A = map owner.
it_owner_at_col:
        jsr wn_cell_address
        ldy #0
        lda (wn_ptr),y
        rts
; Current rectangle as pixel bounds / cell bounds for the graphics library.
it_pixels:
        lda it_rx
        jsr al_times8
        sta gfx_x0
        stx gfx_x0+1
        lda it_rx
        clc
        adc it_rw
        jsr al_times8
        sta gfx_x1
        stx gfx_x1+1
        lda it_ry
        jsr al_times8
        sta gfx_y0
        stx gfx_y0+1
        lda it_ry
        clc
        adc it_rh
        jsr al_times8
        sta gfx_y1
        stx gfx_y1+1
        rts
it_cells:
        lda it_rx
        sta gfx_x0
        clc
        adc it_rw
        sta gfx_x1
        lda it_ry
        sta gfx_y0
        clc
        adc it_rh
        sta gfx_y1
        lda #0
        sta gfx_x0+1
        sta gfx_x1+1
        sta gfx_y0+1
        sta gfx_y1+1
        rts
wn_mark_rect:
        lda it_ry
        ldx it_rh
        jmp al_mark

wn_bind:
        ldx #3
-       lda wn_surface,x
        sta al_surface,x
        dex
        bpl -
        jsr al_select_surface
        jmp gfx_bind

; ---- frames ----------------------------------------------------------------------
; Draw window X's frame into each of its visible rectangles.
wn_draw_frame:
        stx it_h
        stx wn_frame_h
        jsr wn_geometry
        jsr wn_bind
        bcs wn_frame_done
        ldx wn_frame_h          ; the whole window as the area
        lda wn_x,x
        sta it_ax
        lda wn_y,x
        sta it_ay
        lda wn_w,x
        sta it_aw
        lda wn_h,x
        sta it_ah
        jsr it_begin
wn_frame_rect:
        jsr it_next
        lda it_rw
        bne +
        jsr gfx_clip_defaults   ; back to the full surface
        clc
        rts
+       jsr it_pixels
        jsr gfx_set_clip
        bcs wn_frame_done
        jsr wn_mark_rect
        jsr wn_paint_frame
        bcs wn_frame_done
        jmp wn_frame_rect
wn_frame_done:
        rts

; Paint window wn_frame_h's frame (clipped to the current rectangle).
wn_paint_frame:
        ldx wn_frame_h
        lda wn_has_title
        beq wn_paint_info
        lda wn_y,x              ; title bar
        sta wn_band_y
        lda #1
        sta wn_band_line
        jsr wn_band
        bcs wn_paint_done
        ldx wn_frame_h
        lda wn_x,x
        sta wn_cx
        lda wn_kind_lo,x
        and #<WK_CLOSER
        beq +
        lda #0                  ; close box
        jsr wn_gadget
        bcs wn_paint_done
        ldx wn_frame_h
+       lda wn_kind_lo,x
        and #<WK_FULLER
        beq +
        lda wn_x,x
        clc
        adc wn_w,x
        sec
        sbc #1
        sta wn_cx
        lda #1                  ; full box
        jsr wn_gadget
        bcs wn_paint_done
+       jsr wn_title_text
        bcs wn_paint_done
wn_paint_info:
        ldx wn_frame_h
        lda wn_has_info
        beq wn_paint_vbar
        lda wn_y,x
        clc
        adc wn_has_title
        sta wn_band_y
        lda #1
        sta wn_band_line
        jsr wn_band
        bcs wn_paint_done
wn_paint_vbar:
        lda wn_has_vbar
        beq wn_paint_hbar
        jsr wn_vbar
        bcs wn_paint_done
wn_paint_hbar:
        lda wn_has_hbar
        beq wn_paint_sizer
        jsr wn_hbar
        bcs wn_paint_done
wn_paint_sizer:
        ldx wn_frame_h
        lda wn_kind_lo,x
        and #<WK_SIZER
        beq +
        lda wn_x,x
        clc
        adc wn_w,x
        sec
        sbc #1
        sta wn_cx
        lda wn_y,x
        clc
        adc wn_h,x
        sec
        sbc #1
        sta wn_band_y
        lda #6                  ; size box
        jmp wn_gadget
+       clc
wn_paint_done:
        rts

; A full-width row at wn_band_y: clear it, colour it (the top window's title
; bar in the focus colour), then a line along its bottom when wn_band_line.
wn_band:
        ldx wn_frame_h
        lda wn_x,x
        jsr al_times8
        sta gfx_x0
        stx gfx_x0+1
        ldx wn_frame_h
        lda wn_x,x
        clc
        adc wn_w,x
        jsr al_times8
        sta gfx_x1
        stx gfx_x1+1
        lda wn_band_y
        jsr al_times8
        sta gfx_y0
        stx gfx_y0+1
        clc
        adc #8
        sta gfx_y1
        lda #0
        sta gfx_y1+1
        sta gfx_pen
        jsr gfx_rect
        bcs wn_band_done
        lda wn_band_line
        beq +
        lda gfx_y1              ; one-pixel line at the bottom
        sec
        sbc #1
        sta gfx_y0
        lda #1
        sta gfx_pen
        jsr gfx_rect
        bcs wn_band_done
+       ldx wn_frame_h
        lda wn_x,x
        sta gfx_x0
        clc
        adc wn_w,x
        sta gfx_x1
        lda wn_band_y
        sta gfx_y0
        clc
        adc #1
        sta gfx_y1
        lda #0
        sta gfx_x0+1
        sta gfx_x1+1
        sta gfx_y0+1
        sta gfx_y1+1
        lda #AL_PAPER
        ldx wn_frame_h
        cpx wn_order            ; the top window's title bar is highlighted
        bne +
        ldy wn_count
        beq +
        lda wn_y,x
        cmp wn_band_y
        bne +
        lda wn_has_title
        beq +
        lda #AL_FOCUS_INK
        .byte $2c
+       lda #AL_PAPER
        sta gfx_color
        jmp gfx_colors
wn_band_done:
        rts

; Title text centred between the close and full boxes (cut to fit).
wn_title_text:
        ldx wn_frame_h
        lda wn_title_len,x
        bne +
        clc
        rts
+       lda wn_w,x              ; room = w - 2 (gadget columns)
        sec
        sbc #2
        cmp wn_title_len,x
        bcc +
        lda wn_title_len,x
+       sta gfx_text_length
        txa
        asl
        asl
        asl
        asl
        tay
        ldx #0
-       lda wn_title,y
        sta gfx_text_buffer,x
        iny
        inx
        cpx gfx_text_length
        bne -
        ldx wn_frame_h
        lda wn_w,x              ; x = window x + (w - len) / 2
        sec
        sbc gfx_text_length
        lsr
        clc
        adc wn_x,x
        jsr al_times8
        sta gfx_x0
        stx gfx_x0+1
        ldx wn_frame_h
        lda wn_y,x
        jsr al_times8
        sta gfx_y0
        stx gfx_y0+1
        lda #1
        sta gfx_pen
        jmp gfx_text

; A = gadget glyph (0 close, 1 full, 2 up, 3 down, 4 left, 5 right, 6 size,
; 7 track, 8 thumb) at cell wn_cx, row wn_band_y (or wn_gy when set).
wn_gadget:
        asl
        asl
        asl
        tay
        ldx #0
-       lda wn_glyphs,y
        sta gfx_bits,x
        iny
        inx
        cpx #8
        bne -
        lda wn_cx
        jsr al_times8
        sta gfx_x0
        stx gfx_x0+1
        lda wn_band_y
        jsr al_times8
        sta gfx_y0
        stx gfx_y0+1
        lda #3                  ; replace the whole cell
        sta gfx_pen
        jmp gfx_glyph

; Vertical bar in the right column of the work rows.
wn_vbar:
        ldx wn_frame_h
        lda wn_x,x
        clc
        adc wn_w,x
        sec
        sbc #1
        sta wn_cx
        lda wn_wy
        sta wn_band_y
        lda wn_wh               ; track rows between optional arrows
        sta wn_track
        lda wn_has_hbar         ; a size box without a bottom row sits in
        bne +                   ; this column's last cell
        lda wn_kind_lo,x
        and #<WK_SIZER
        beq +
        dec wn_track
+       lda wn_wy
        sta wn_track_y
        lda wn_kind_lo,x
        and #<WK_UPARROW
        beq +
        lda #2
        jsr wn_gadget
        bcs wn_bar_done
        inc wn_track_y
        dec wn_track
        ldx wn_frame_h
+       lda wn_kind_lo,x
        and #<WK_DNARROW
        beq +
        lda wn_track_y          ; the down arrow closes the track
        clc
        adc wn_track
        sec
        sbc #1
        sta wn_band_y
        lda #3
        jsr wn_gadget
        bcs wn_bar_done
        dec wn_track
        ldx wn_frame_h
+       lda wn_vsize,x
        sta wn_slide_size
        lda wn_vpos,x
        sta wn_slide_pos
        jsr wn_thumb
        lda #0                  ; the track: thumb cells solid, others patterned
        sta wn_i
-       lda wn_i
        cmp wn_track
        bcs +
        clc
        adc wn_track_y
        sta wn_band_y
        jsr wn_track_glyph
        jsr wn_gadget
        bcs wn_bar_done
        inc wn_i
        bne -
+       ldx wn_frame_h          ; colour the column
        lda wn_cx
        sta gfx_x0
        clc
        adc #1
        sta gfx_x1
        lda wn_wy
        sta gfx_y0
        clc
        adc wn_wh
        sta gfx_y1
        jmp wn_bar_colors
wn_bar_done:
        rts
; Horizontal bar in the bottom row, left of the corner.
wn_hbar:
        ldx wn_frame_h
        lda wn_y,x
        clc
        adc wn_h,x
        sec
        sbc #1
        sta wn_band_y
        lda wn_wx
        sta wn_cx
        lda wn_ww
        sta wn_track
        lda wn_has_vbar         ; a size box without a right column sits in
        bne +                   ; this row's last cell
        lda wn_kind_lo,x
        and #<WK_SIZER
        beq +
        dec wn_track
+       lda wn_wx
        sta wn_track_y          ; the track's first column here
        lda wn_kind_hi,x
        and #>WK_LFARROW
        beq +
        lda #4
        jsr wn_gadget
        bcs wn_bar_done
        inc wn_track_y
        dec wn_track
        ldx wn_frame_h
+       lda wn_kind_hi,x
        and #>WK_RTARROW
        beq +
        lda wn_track_y          ; the right arrow closes the track
        clc
        adc wn_track
        sec
        sbc #1
        sta wn_cx
        lda #5
        jsr wn_gadget
        bcs wn_bar_done
        dec wn_track
        ldx wn_frame_h
+       lda wn_hsize,x
        sta wn_slide_size
        lda wn_hpos,x
        sta wn_slide_pos
        jsr wn_thumb
        lda #0
        sta wn_i
-       lda wn_i
        cmp wn_track
        bcs +
        clc
        adc wn_track_y
        sta wn_cx
        jsr wn_track_glyph
        jsr wn_gadget
        bcs wn_bar_done
        inc wn_i
        bne -
+       ldx wn_frame_h          ; colour the whole row

        lda wn_x,x
        sta gfx_x0
        clc
        adc wn_w,x
        sta gfx_x1
        lda wn_band_y
        sta gfx_y0
        clc
        adc #1
        sta gfx_y1
wn_bar_colors:
        lda #0
        sta gfx_x0+1
        sta gfx_x1+1
        sta gfx_y0+1
        sta gfx_y1+1
        lda #AL_PAPER
        sta gfx_color
        jmp gfx_colors
; A = 8 (thumb) for track cell wn_i inside the thumb, else 7.
wn_track_glyph:
        lda wn_i
        cmp wn_thumb_at
        bcc +
        sec
        sbc wn_thumb_at
        cmp wn_thumb_len
        bcs +
        lda #8
        rts
+       lda #7
        rts
; Thumb length = max(1, ceil(track*size/256)), start = (pos*(track-len)+128)>>8.
wn_thumb:
        lda #0
        sta wn_thumb_at
        sta wn_thumb_len
        lda wn_track
        beq wn_thumb_done
        ldx wn_slide_size
        jsr wn_mul              ; track*size
        lda wn_prod
        cmp #1                  ; ceil: any low bits add one
        lda wn_prod+1
        adc #0
        bne +
        lda #1
+       cmp wn_track
        bcc +
        lda wn_track
+       sta wn_thumb_len
        lda wn_track
        sec
        sbc wn_thumb_len
        ldx wn_slide_pos
        jsr wn_mul
        lda wn_prod
        clc
        adc #128
        lda wn_prod+1
        adc #0
        sta wn_thumb_at
wn_thumb_done:
        rts
; A * X -> wn_prod (16-bit).
wn_mul:
        sta wn_mul_a
        stx wn_mul_b
        lda #0
        sta wn_prod
        sta wn_prod+1
        ldx #8
-       lsr wn_mul_b
        bcc +
        clc
        lda wn_prod+1
        adc wn_mul_a
        sta wn_prod+1
+       ror wn_prod+1
        ror wn_prod
        dex
        bne -
        rts

; ---- frame gadgets through the event wait ------------------------------------
WD_MOVE = 1
WD_SIZE = 2
WD_VSLIDE = 3
WD_HSLIDE = 4

; Called by the event wait with the sample in N_BUFFER (after the menu).
; Carry set when the window manager consumed the sample.
wn_input:
        lda wn_drag
        beq +
        jmp wn_drag_step
+       lda wn_count
        beq wn_not_ours
        lda N_BUFFER+20         ; a new press only
        and #1
        tax
        eor #1
        and wn_prev_down
        sta wn_math             ; (release; unused without a drag)
        lda wn_prev_down
        stx wn_prev_down
        bne wn_not_ours
        cpx #0
        beq wn_not_ours
        jsr wn_pointer_cell
        cmp #40
        bcs wn_not_ours
        cpy #25
        bcs wn_not_ours
        jsr wn_cell_address
        ldy #0
        lda (wn_ptr),y
        beq wn_not_ours         ; the desktop belongs to the app
        sta wn_hit
        cmp wn_order
        beq wn_top_press
        lda #WM_TOPPED          ; any press on a lower window tops it
        jsr wn_send
        sec
        rts
wn_not_ours:
        clc
        rts
; A press on the top window: which part of its frame?
wn_top_press:
        ldx wn_hit
        stx wn_frame_h
        jsr wn_geometry
        ldx wn_hit
        lda wn_px_cell          ; inside the work area: the app's click
        sec
        sbc wn_wx
        cmp wn_ww
        bcs +
        lda wn_py_cell
        sec
        sbc wn_wy
        cmp wn_wh
        bcs +
        clc
        rts
+       lda wn_has_title        ; title row
        beq wn_press_below_title
        lda wn_py_cell
        cmp wn_y,x
        bne wn_press_below_title
        lda wn_kind_lo,x
        and #<WK_CLOSER
        beq +
        lda wn_px_cell
        cmp wn_x,x
        bne +
        lda #WM_CLOSED
        jmp wn_send_consumed
+       lda wn_kind_lo,x
        and #<WK_FULLER
        beq +
        lda wn_x,x
        clc
        adc wn_w,x
        sec
        sbc #1
        cmp wn_px_cell
        bne +
        lda #WM_FULLED
        jmp wn_send_consumed
+       lda wn_kind_lo,x
        and #<WK_MOVER
        beq wn_consumed
        lda #WD_MOVE
        jmp wn_drag_begin
wn_press_below_title:
        lda wn_kind_lo,x        ; the size box
        and #<WK_SIZER
        beq +
        lda wn_x,x
        clc
        adc wn_w,x
        sec
        sbc #1
        cmp wn_px_cell
        bne +
        lda wn_y,x
        clc
        adc wn_h,x
        sec
        sbc #1
        cmp wn_py_cell
        bne +
        lda #WD_SIZE
        jmp wn_drag_begin
+       lda wn_has_vbar         ; the right column
        beq +
        lda wn_x,x
        clc
        adc wn_w,x
        sec
        sbc #1
        cmp wn_px_cell
        bne +
        jmp wn_press_vbar
+       lda wn_has_hbar         ; the bottom row
        beq wn_consumed
        lda wn_y,x
        clc
        adc wn_h,x
        sec
        sbc #1
        cmp wn_py_cell
        bne wn_consumed
        jmp wn_press_hbar
wn_consumed:
        sec
        rts
wn_send_consumed:
        jsr wn_send
        sec
        rts

; Right column: arrows are line steps, the track beside the thumb pages,
; the thumb starts a slider drag. WM_ARROWED byte 4: 0 page up, 1 page
; down, 2 line up, 3 line down, 4 page left, 5 page right, 6 line left,
; 7 line right (GEM WA_*).
wn_press_vbar:
        jsr wn_vbar_track       ; wn_track_y/wn_track and the thumb for X
        lda wn_kind_lo,x
        and #<WK_UPARROW
        beq +
        lda wn_py_cell
        cmp wn_wy
        bne +
        lda #2
        jmp wn_arrowed
+       lda wn_kind_lo,x
        and #<WK_DNARROW
        beq +
        lda wn_track_y
        clc
        adc wn_track
        cmp wn_py_cell
        bne +
        lda #3
        jmp wn_arrowed
+       lda wn_py_cell          ; on the track
        sec
        sbc wn_track_y
        cmp wn_track
        bcs wn_consumed
        cmp wn_thumb_at
        bcs +
        lda #0
        jmp wn_arrowed
+       sec
        sbc wn_thumb_at
        cmp wn_thumb_len
        bcc +
        lda #1
        jmp wn_arrowed
+       lda #WD_VSLIDE
        jmp wn_drag_begin
wn_press_hbar:
        jsr wn_hbar_track
        lda wn_kind_hi,x
        and #>WK_LFARROW
        beq +
        lda wn_px_cell
        cmp wn_wx
        bne +
        lda #6
        jmp wn_arrowed
+       lda wn_kind_hi,x
        and #>WK_RTARROW
        beq +
        lda wn_track_y
        clc
        adc wn_track
        cmp wn_px_cell
        bne +
        lda #7
        jmp wn_arrowed
+       lda wn_px_cell
        sec
        sbc wn_track_y
        cmp wn_track
        bcs wn_consumed
        cmp wn_thumb_at
        bcs +
        lda #4
        jmp wn_arrowed
+       sec
        sbc wn_thumb_at
        cmp wn_thumb_len
        bcc +
        lda #5
        jmp wn_arrowed
+       lda #WD_HSLIDE
        jmp wn_drag_begin
wn_arrowed:
        sta wn_msg_data
        lda #WM_ARROWED
        jmp wn_send_consumed

; Track geometry of window X's right column / bottom row, as the frame
; drawing computes it (arrows excluded), with the thumb.
wn_vbar_track:
        lda wn_wh
        sta wn_track
        lda wn_has_hbar
        bne +
        lda wn_kind_lo,x
        and #<WK_SIZER
        beq +
        dec wn_track
+       lda wn_wy
        sta wn_track_y
        lda wn_kind_lo,x
        and #<WK_UPARROW
        beq +
        inc wn_track_y
        dec wn_track
+       lda wn_kind_lo,x
        and #<WK_DNARROW
        beq +
        dec wn_track
+       lda wn_vsize,x
        sta wn_slide_size
        lda wn_vpos,x
        sta wn_slide_pos
        stx wn_math4
        jsr wn_thumb
        ldx wn_math4
        rts
wn_hbar_track:
        lda wn_ww
        sta wn_track
        lda wn_has_vbar
        bne +
        lda wn_kind_lo,x
        and #<WK_SIZER
        beq +
        dec wn_track
+       lda wn_wx
        sta wn_track_y
        lda wn_kind_hi,x
        and #>WK_LFARROW
        beq +
        inc wn_track_y
        dec wn_track
+       lda wn_kind_hi,x
        and #>WK_RTARROW
        beq +
        dec wn_track
+       lda wn_hsize,x
        sta wn_slide_size
        lda wn_hpos,x
        sta wn_slide_pos
        stx wn_math4
        jsr wn_thumb
        ldx wn_math4
        rts

; Queue message A about window wn_hit: [A, 0, 0, handle, data/rect...].
wn_send:
        sta ev_msg_in
        lda #0
        sta ev_msg_in+1
        sta ev_msg_in+2
        lda wn_hit
        sta ev_msg_in+3
        ldx #3
-       lda wn_msg_data,x
        sta ev_msg_in+4,x
        dex
        bpl -
        jsr ev_push
        lda #0
        ldx #3
-       sta wn_msg_data,x
        dex
        bpl -
        rts

; ---- drags: XOR outline for move/size, pointer tracking for sliders ----------
; A = drag kind; X = window. The pointer cell at the press is the anchor.
wn_drag_begin:
        sta wn_drag
        sta wn_drag_kind_end
        lda wn_px_cell
        sta wn_anchor_x
        lda wn_py_cell
        sta wn_anchor_y
        lda wn_x,x
        sta wn_dx
        lda wn_y,x
        sta wn_dy
        lda wn_w,x
        sta wn_dw
        lda wn_h,x
        sta wn_dh
        lda wn_drag
        cmp #WD_VSLIDE
        bcs +
        jsr wn_outline          ; the starting outline
+       sec
        rts
; Each sample during a drag: follow the pointer; the release ends it.
wn_drag_step:
        jsr wn_pointer_cell
        lda N_BUFFER+20
        and #1
        sta wn_prev_down
        bne +
        jmp wn_drag_end
+       lda wn_drag
        cmp #WD_VSLIDE
        bcc +
        sec                     ; sliders report on release only
        rts
+       jsr wn_drag_rect        ; candidate from the pointer
        lda wn_cand_x           ; unchanged: nothing to redraw
        cmp wn_dx
        bne +
        lda wn_cand_y
        cmp wn_dy
        bne +
        lda wn_cand_w
        cmp wn_dw
        bne +
        lda wn_cand_h
        cmp wn_dh
        beq wn_drag_held
+       jsr wn_outline          ; erase the old outline (XOR)...
        lda wn_cand_x
        sta wn_dx
        lda wn_cand_y
        sta wn_dy
        lda wn_cand_w
        sta wn_dw
        lda wn_cand_h
        sta wn_dh
        jsr wn_outline          ; ...and draw the new one
wn_drag_held:
        sec
        rts
wn_drag_end:
        lda wn_drag
        ldx #0
        stx wn_drag
        cmp #WD_VSLIDE
        bcs wn_drag_slider
        pha
        jsr wn_outline          ; erase
        pla
        ldx wn_hit
        cmp #WD_MOVE
        bne +
        lda wn_dx               ; unmoved: no message
        cmp wn_x,x
        bne ++
        lda wn_dy
        cmp wn_y,x
        beq wn_drag_done
        bne ++
+       lda wn_dw
        cmp wn_w,x
        bne +
        lda wn_dh
        cmp wn_h,x
        beq wn_drag_done
+       lda wn_dx
        sta wn_msg_data
        lda wn_dy
        sta wn_msg_data+1
        lda wn_dw
        sta wn_msg_data+2
        lda wn_dh
        sta wn_msg_data+3
        lda #WM_MOVED
        ldy wn_drag_kind_end
        cpy #WD_MOVE
        beq +
        lda #WM_SIZED
+       jsr wn_send
wn_drag_done:
        sec
        rts
; Slider release: position 0..255 from the pointer's place on the track.
wn_drag_slider:
        sta wn_math3
        ldx wn_hit
        jsr wn_geometry
        ldx wn_hit
        lda wn_math3
        cmp #WD_VSLIDE
        bne +
        jsr wn_vbar_track
        lda wn_py_cell
        jmp ++
+       jsr wn_hbar_track
        lda wn_px_cell
+       sec                     ; offset of the thumb's start on the track
        sbc wn_track_y
        bcs +
        lda #0
+       sta wn_math
        lda wn_track
        sec
        sbc wn_thumb_len
        beq wn_slide_zero       ; nothing to scroll
        sta wn_math2
        lda wn_math
        cmp wn_math2
        bcc +
        lda #255
        bne wn_slide_send
+       ldx #255                ; pos = offset*255 / free cells
        jsr wn_mul
        lda wn_prod
        ldx wn_prod+1
        jsr wn_div_free
        jmp wn_slide_send
wn_slide_zero:
        lda #0
wn_slide_send:
        sta wn_msg_data
        lda #WM_VSLID
        ldx wn_math3
        cpx #WD_VSLIDE
        beq +
        lda #WM_HSLID
+       jsr wn_send
        sec
        rts
; A/X (lo/hi) / wn_math2 -> A (quotient, < 256).
wn_div_free:
        sta wn_prod
        stx wn_prod+1
        lda #0
        ldx #16
-       asl wn_prod
        rol wn_prod+1
        rol
        cmp wn_math2
        bcc +
        sbc wn_math2
        inc wn_prod
+       dex
        bne -
        lda wn_prod
        rts

; Candidate rectangle from the pointer's offset to the anchor.
wn_drag_rect:
        ldx wn_hit
        lda wn_x,x
        sta wn_cand_x
        lda wn_y,x
        sta wn_cand_y
        lda wn_w,x
        sta wn_cand_w
        lda wn_h,x
        sta wn_cand_h
        lda wn_px_cell
        sec
        sbc wn_anchor_x
        sta wn_delta_x          ; signed
        lda wn_py_cell
        sec
        sbc wn_anchor_y
        sta wn_delta_y
        lda wn_drag
        sta wn_drag_kind_end
        cmp #WD_MOVE
        bne wn_drag_rect_size
        lda wn_cand_x           ; move: clamp inside columns 0..39, rows 1..24
        clc
        adc wn_delta_x
        bpl +
        lda #0
+       sta wn_cand_x
        clc
        adc wn_cand_w
        cmp #41
        bcc +
        lda #40
        sec
        sbc wn_cand_w
        sta wn_cand_x
+       lda wn_cand_y
        clc
        adc wn_delta_y
        bmi +
        bne ++
+       lda #1
+       sta wn_cand_y
        clc
        adc wn_cand_h
        cmp #26
        bcc +
        lda #25
        sec
        sbc wn_cand_h
        sta wn_cand_y
+       rts
wn_drag_rect_size:
        lda wn_cand_w           ; size: at least 4x3, inside the screen
        clc
        adc wn_delta_x
        bmi +
        cmp #4
        bcs ++
+       lda #4
+       sta wn_cand_w
        clc
        adc wn_cand_x
        cmp #41
        bcc +
        lda #40
        sec
        sbc wn_cand_x
        sta wn_cand_w
+       lda wn_cand_h
        clc
        adc wn_delta_y
        bmi +
        cmp #3
        bcs ++
+       lda #3
+       sta wn_cand_h
        clc
        adc wn_cand_y
        cmp #26
        bcc +
        lda #25
        sec
        sbc wn_cand_y
        sta wn_cand_h
+       rts

; XOR a one-pixel outline of wn_dx/dy/dw/dh (cells) onto the surface.
wn_outline:
        jsr wn_bind
        bcs wn_outline_done
        lda #2
        sta gfx_pen
        lda wn_dx               ; top edge
        jsr al_times8
        sta gfx_x0
        stx gfx_x0+1
        lda wn_dx
        clc
        adc wn_dw
        jsr al_times8
        sta gfx_x1
        stx gfx_x1+1
        lda wn_dy
        jsr al_times8
        sta gfx_y0
        stx gfx_y0+1
        clc
        adc #1
        sta gfx_y1
        lda #0
        sta gfx_y1+1
        jsr gfx_rect
        bcs wn_outline_done
        lda wn_dy               ; bottom edge
        clc
        adc wn_dh
        jsr al_times8
        sec
        sbc #1
        sta gfx_y0
        clc
        adc #1
        sta gfx_y1
        jsr gfx_rect
        bcs wn_outline_done
        lda wn_dy               ; left edge, between the two lines
        jsr al_times8
        clc
        adc #1
        sta gfx_y0
        lda wn_dy
        clc
        adc wn_dh
        jsr al_times8
        sec
        sbc #1
        sta gfx_y1
        lda gfx_x0
        clc
        adc #1
        sta gfx_x1
        lda gfx_x0+1
        adc #0
        sta gfx_x1+1
        jsr gfx_rect
        bcs wn_outline_done
        lda wn_dx               ; right edge
        clc
        adc wn_dw
        jsr al_times8
        sta gfx_x1
        stx gfx_x1+1
        sec
        sbc #1
        sta gfx_x0
        txa
        sbc #0
        sta gfx_x0+1
        jsr gfx_rect
        bcs wn_outline_done
        lda wn_dy
        ldx wn_dh
        jsr al_mark
        clc
wn_outline_done:
        rts

; Pointer cell of the sample: A = column (wn_px_cell), Y = row (wn_py_cell).
wn_pointer_cell:
        lda N_BUFFER+18
        lsr
        lda N_BUFFER+17
        ror
        lsr
        lsr
        sta wn_px_cell
        lda N_BUFFER+19
        lsr
        lsr
        lsr
        sta wn_py_cell
        tay
        lda wn_px_cell
        rts

wn_drag: .byte 0
wn_drag_kind_end: .byte 0
wn_prev_down: .byte 0
wn_hit: .byte 0
wn_px_cell: .byte 0
wn_py_cell: .byte 0
wn_anchor_x: .byte 0
wn_anchor_y: .byte 0
wn_delta_x: .byte 0
wn_delta_y: .byte 0
wn_dx: .byte 0
wn_dy: .byte 0
wn_dw: .byte 0
wn_dh: .byte 0
wn_cand_x: .byte 0
wn_cand_y: .byte 0
wn_cand_w: .byte 0
wn_cand_h: .byte 0
wn_msg_data: .fill 4,0

; A new foreground app: its windows went with its surface.
wn_reset:
        lda #0
        sta wn_count
        sta wn_top_old
        sta wn_drag
        sta wn_prev_down
        ldx #WN_MAX
-       sta wn_flags,x
        sta wn_force,x
        dex
        bpl -
        ldx #0
-       sta wn_map,x
        sta wn_map+256,x
        sta wn_map+512,x
        sta wn_map+768,x
        inx
        bne -
        rts

wn_ptr = $06                    ; the executor's scratch word (bk_native saves $06..$08)
wn_surface: .fill 4,0
wn_count: .byte 0
wn_order: .fill 8,0
wn_top_old: .byte 0
wn_top_new: .byte 0
wn_h_arg: .byte 0
wn_frame_h: .byte 0
wn_msg_h: .byte 0
wn_new_owner: .byte 0
wn_row: .byte 0
wn_rows: .byte 0
wn_col: .byte 0
wn_cx: .byte 0
wn_i: .byte 0
wn_band_y: .byte 0
wn_band_line: .byte 0
wn_track: .byte 0
wn_track_y: .byte 0
wn_thumb_at: .byte 0
wn_thumb_len: .byte 0
wn_slide_pos: .byte 0
wn_slide_size: .byte 0
wn_fill_pen: .byte 0
wn_fill_color: .byte 0
wn_math: .byte 0
wn_math2: .byte 0
wn_math3: .byte 0
wn_math4: .byte 0
wn_math16: .word 0
wn_mul_a: .byte 0
wn_mul_b: .byte 0
wn_prod: .word 0
wn_wx: .byte 0
wn_wy: .byte 0
wn_ww: .byte 0
wn_wh: .byte 0
wn_has_title: .byte 0
wn_has_info: .byte 0
wn_has_vbar: .byte 0
wn_has_hbar: .byte 0
it_h: .byte 0
it_ax: .byte 0
it_ay: .byte 0
it_aw: .byte 0
it_ah: .byte 0
it_row: .byte 0
it_col: .byte 0
it_x1: .byte 0
it_run_end: .byte 0
it_down: .byte 0
it_test_row: .byte 0
it_test_col: .byte 0
it_rx: .byte 0
it_ry: .byte 0
it_rw: .byte 0
it_rh: .byte 0
; per window 0..7 (0 = desktop where it applies)
wn_row40_lo:
 .for row=0, row<25, row+=1
        .byte <(row*40)
 .endfor
wn_row40_hi:
 .for row=0, row<25, row+=1
        .byte >(row*40)
 .endfor
; 8x8 gadgets: close, full, up, down, left, right, size, track, thumb
wn_glyphs:
        .byte $ff,$81,$a5,$99,$99,$a5,$81,$ff
        .byte $ff,$81,$bd,$a5,$a5,$bd,$81,$ff
        .byte $ff,$81,$99,$bd,$ff,$99,$81,$ff
        .byte $ff,$81,$99,$ff,$bd,$99,$81,$ff
        .byte $ff,$89,$99,$bf,$bf,$99,$89,$ff
        .byte $ff,$91,$99,$fd,$fd,$99,$91,$ff
        .byte $ff,$81,$bd,$a1,$a1,$a1,$81,$ff
        .byte $aa,$55,$aa,$55,$aa,$55,$aa,$55
        .byte $ff,$ff,$ff,$ff,$ff,$ff,$ff,$ff
; RAM tables in the owner-30 data segment (aesvc.asm AE_DATA)
        .section aesdata
wn_flags: .fill 8,0             ; 0 free, 1 created, 3 open
wn_force: .fill 8,0
wn_frame: .fill 8,0
wn_bx0: .fill 8,0
wn_by0: .fill 8,0
wn_bx1: .fill 8,0
wn_by1: .fill 8,0
wn_kind_lo: .fill 8,0
wn_kind_hi: .fill 8,0
wn_x: .fill 8,0
wn_y: .fill 8,0
wn_w: .fill 8,0
wn_h: .fill 8,0
wn_px: .fill 8,0
wn_py: .fill 8,0
wn_pw: .fill 8,0
wn_ph: .fill 8,0
wn_fx: .fill 8,0
wn_fy: .fill 8,0
wn_fw: .fill 8,0
wn_fh: .fill 8,0
wn_vpos: .fill 8,0
wn_hpos: .fill 8,0
wn_vsize: .fill 8,0
wn_hsize: .fill 8,0
wn_title_len: .fill 8,0
wn_title: .fill 8*16,0
wn_map: .fill 1000,0
wn_old: .fill 1000,0
        .send aesdata
