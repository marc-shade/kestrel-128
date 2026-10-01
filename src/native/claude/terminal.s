; Retained 80x25 terminal, independent of the active display view.
; Cells/attributes occupy one checked bank-1 allocation. The live 4096-byte
; font is owned at $5000, so GUI rendering never reads an active VDC bitmap.
.macpack longbranch
.export _tm_begin, _tm_end, _tm_run, _tm_fill, _tm_clear, _tm_scroll
.export _tm_cursor, _tm_glyph, _tm_read, _tm_live, _tm_error, tm_cells, tm_font
.import _scrRow, _scrCol, _scrLen, _scrChar, _scrAttr, _scrBuf
.import sf_read, _native_quit
.import _gui_font_hi, _gui_font_ram, _gui_view, _gui_dirty, _gui_dirty_all
.import _gui_terminal_read, _gui_cursor_row, _gui_cursor_col
.import _gui_terminal_restore, _scr_sync
.importzp ptr1

.include "../api.inc"

.bss
_tm_live: .res 1
_tm_error: .res 1
tm_font: .res 4
tm_cells: .res 4
tm_row: .res 1
tm_col: .res 1
tm_len: .res 1
tm_plane: .res 1
tm_top: .res 1
tm_bottom: .res 1
tm_source: .res 1
tm_dest: .res 1
tm_rows: .res 1
tm_direction: .res 1
tm_left: .res 2
tm_value: .res 1

.code
tm_owner:
        lda #0
        sta N_READY
        lda N_CURRENT
        sta N_OWNER
        rts
tm_select:
        jsr tm_owner
        ldx #3
@handle:lda tm_cells,x
        sta N_HANDLE,x
        dex
        bpl @handle
        rts
tm_failed:
        sta _tm_error
        lda #1
        sta _native_quit
        sec
        rts

_tm_begin:
        jsr tm_owner
        lda #0
        sta N_BANK
        lda #$50
        sta N_PAGE
        lda #16
        sta N_PAGES
        jsr N_RESERVE
        jcs @refused
        ldx #3
@font: lda N_HANDLE,x
        sta tm_font,x
        dex
        bpl @font
        lda #1
        sta N_BANK
        lda #16
        sta N_PAGES
        jsr N_ALLOC
        jcs @refused
        ldx #3
@cells:lda N_HANDLE,x
        sta tm_cells,x
        dex
        bpl @cells
        lda #0
        sta tm_source
@chunk:lda tm_source
        jsr sf_read
        jcs @refused
        lda tm_source
        clc
        adc #$50
        sta @write+2
        lda #>N_BUFFER
        sta @read+2
        ldx #2
@page: ldy #0
@read: lda N_BUFFER,y
@write:sta $5000,y
        iny
        bne @read
        inc @read+2
        inc @write+2
        dex
        bne @page
        inc tm_source
        inc tm_source
        lda tm_source
        cmp #16
        bne @chunk
        lda #<_tm_read
        sta _gui_terminal_read+1
        lda #>_tm_read
        sta _gui_terminal_read+2
        lda #<_scr_sync
        sta _gui_terminal_restore+1
        lda #>_scr_sync
        sta _gui_terminal_restore+2
        lda #$50
        sta _gui_font_hi
        lda #255
        sta _gui_cursor_row
        sta _gui_cursor_col
        lda #1
        sta _tm_live
        sta _gui_font_ram
        clc
        rts
@refused:
        sta _tm_error
        jsr _tm_end
        clc                     ; clean refusal retains the hardware terminal
        rts

_tm_end:
        lda tm_cells
        beq @font
        jsr tm_select
        jsr N_FREE
        bcs @return
        lda #0
        sta tm_cells
@font: lda tm_font
        beq @closed
        jsr tm_owner
        ldx #3
@select:lda tm_font,x
        sta N_HANDLE,x
        dex
        bpl @select
        jsr N_FREE
        bcs @return
        lda #0
        sta tm_font
@closed:
        lda #0
        sta _tm_live
        sta _gui_font_ram
        clc
@return:rts

; Set an offset from tm_row*80+tm_col, with plane high offset 0 or 8.
tm_offset:
        lda #0
        sta N_OFFSET+1
        lda tm_row
        asl
        asl
        rol N_OFFSET+1
        asl
        rol N_OFFSET+1
        asl
        rol N_OFFSET+1
        sta N_OFFSET
        sta tm_left
        lda N_OFFSET+1
        sta tm_left+1
        asl N_OFFSET
        rol N_OFFSET+1
        asl N_OFFSET
        rol N_OFFSET+1
        lda N_OFFSET
        clc
        adc tm_left
        sta N_OFFSET
        lda N_OFFSET+1
        adc tm_left+1
        sta N_OFFSET+1
        lda N_OFFSET
        clc
        adc tm_col
        sta N_OFFSET
        lda N_OFFSET+1
        adc #0
        ora tm_plane
        sta N_OFFSET+1
        lda tm_len
        sta N_COUNT
        lda #0
        sta N_COUNT+1
        rts

tm_clip:
        lda _tm_live
        beq @bad
        lda _scrRow
        cmp #25
        bcs @bad
        sta tm_row
        lda _scrCol
        cmp #80
        bcs @bad
        sta tm_col
        lda #80
        sec
        sbc tm_col
        cmp _scrLen
        bcc @count
        lda _scrLen
@count:sta tm_len
        beq @bad
        clc
        rts
@bad:  sec
        rts
tm_mark:
        lda _gui_view
        jeq @done
        ldx tm_row
        lda #1
        sta _gui_dirty,x
@done: rts
tm_attr:
        lda _scrAttr
        and #$6f
        ora #$80
        rts
tm_attr_fill:
        lda #8
        sta tm_plane
        jsr tm_offset
        jsr tm_attr
        sta N_VALUE
        jsr N_FILL
        bcs @failed
        jmp tm_mark
@failed:jmp tm_failed

_tm_run:
        jsr tm_clip
        jcs @done
        jsr tm_select
        lda #0
        sta tm_plane
        jsr tm_offset
        ldy #0
@copy: lda _scrBuf,y
        sta N_BUFFER,y
        iny
        cpy tm_len
        bne @copy
        jsr N_WRITE
        bcs @failed
        jmp tm_attr_fill
@failed:jmp tm_failed
@done: rts

_tm_fill:
        jsr tm_clip
        jcs @done
        jsr tm_select
        lda #0
        sta tm_plane
        jsr tm_offset
        lda _scrChar
        sta N_VALUE
        jsr N_FILL
        bcs @failed
        jmp tm_attr_fill
@failed:jmp tm_failed
@done: rts

_tm_clear:
        lda _tm_live
        jeq @done
        jsr tm_select
        lda #0
        sta tm_plane
        lda #$20
        jsr tm_fill_plane
        bcs @failed
        lda #8
        sta tm_plane
        jsr tm_attr
        jsr tm_fill_plane
        bcs @failed
        jmp _gui_dirty_all
@failed:jmp tm_failed
@done: rts
tm_fill_plane:
        sta tm_value
        lda #0
        sta N_OFFSET
        lda tm_plane
        sta N_OFFSET+1
        ldx #4
@chunk:txa
        pha
        lda #0
        sta N_COUNT
        lda #2
        sta N_COUNT+1
        cpx #1
        bne @write
        lda #<464
        sta N_COUNT
        lda #>464
        sta N_COUNT+1
@write:lda tm_value
        sta N_VALUE
        jsr N_FILL
        pla
        tax
        jcs @done
        inc N_OFFSET+1
        inc N_OFFSET+1
        dex
        bne @chunk
        clc
@done: rts

; A row, X plane (0 cells, 1 attributes) -> eighty complete bytes in N_BUFFER.
_tm_read:
        cmp #25
        bcs @bad
        sta tm_row
        txa
        and #1
        asl
        asl
        asl
        sta tm_plane
        lda #0
        sta tm_col
        lda #80
        sta tm_len
        jsr tm_select
        jsr tm_offset
        jsr N_READ
        bcs @failed
        rts
@bad:  lda #1
@failed:jmp tm_failed

_tm_scroll:
        lda _tm_live
        jeq @done
        lda _scrRow
        sta tm_top
        lda _scrCol
        cmp #25
        jcs @done
        sta tm_bottom
        lda _scrLen
        and #$7f
        jeq @done
        sta tm_len
        lda tm_bottom
        sec
        sbc tm_top
        jcc @done
        cmp tm_len
        jcc @done
        sec
        sbc tm_len
        clc
        adc #1
        sta tm_rows
        lda _scrLen
        and #$80
        sta tm_direction
        bne @down
        lda tm_top
        sta tm_dest
        clc
        adc tm_len
        sta tm_source
        jmp @row
@down: lda tm_bottom
        sta tm_dest
        sec
        sbc tm_len
        sta tm_source
@row:  ldx #0
@plane:txa
        pha
        lda tm_source
        jsr _tm_read
        pla
        tax
        jcs @done
        txa
        pha
        lda tm_dest
        sta tm_row
        jsr tm_offset
        jsr N_WRITE
        pla
        tax
        bcs @failed
        inx
        cpx #2
        bne @plane
        jsr tm_mark
        lda tm_direction
        bne @previous
        inc tm_dest
        inc tm_source
        jmp @next
@previous:
        dec tm_dest
        dec tm_source
@next: dec tm_rows
        bne @row
@done: rts
@failed:jmp tm_failed

_tm_cursor:
        lda _tm_live
        jeq @done
        ldx _gui_cursor_row
        cpx #25
        bcs @new
        lda #1
        sta _gui_dirty,x
@new:  lda _scrRow
        sta _gui_cursor_row
        tax
        lda _scrCol
        sta _gui_cursor_col
        cpx #25
        jcs @done
        lda #1
        sta _gui_dirty,x
@done: rts

_tm_glyph:
        lda _tm_live
        jeq @done
        lda #0
        sta ptr1+1
        lda _scrChar
        asl
        rol ptr1+1
        asl
        rol ptr1+1
        asl
        rol ptr1+1
        asl
        rol ptr1+1
        sta ptr1
        lda ptr1+1
        ora #$50
        sta ptr1+1
        ldy #0
@copy: lda _scrBuf,y
        sta (ptr1),y
        iny
        cpy #8
        bne @copy
        lda #0
@zero: sta (ptr1),y
        iny
        cpy #16
        bne @zero
@done: rts
