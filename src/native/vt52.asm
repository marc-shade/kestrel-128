; VT52 terminal (docs/NATIVE-VT52.md): an Atari-style VT52 screen on the
; 80-column VDC, talking to a SwiftLink-compatible ACIA at $de00. Receive is
; NMI-driven into a 256-byte ring; the keyboard is sent as ASCII with VT52
; cursor sequences. F8 returns to the desktop, restoring the VDC, its font,
; the screen mode, the NMI vector and the programmable keys.
.include "api.inc"
VDC_ADDR = $d600
VDC_DATA = $d601
ACIA_DATA = $de00
ACIA_STATUS = $de01
ACIA_CMD = $de02
ACIA_CTRL = $de03
ACIA_CTRL_VAL = $1e             ; 19200 baud on the SwiftLink's doubled clock, 8N1
ACIA_CMD_VAL = $09              ; DTR, receive interrupt, RTS on, transmit interrupt off
NMI_VECTOR = $0318
NMI_EXIT = $ff33
ATTR_BASE = $0800
VT_ROWS = 25
VT_COLS = 80
VT_QUIT_KEY = $8c               ; F8
* = N_APPBASE
vt_image:
        .text "napp"
        .byte 1,1,14,0
        .word vt_end-vt_image
        .byte (vt_end-vt_image+48+255)/256,0
        .word vt_start-vt_image
        .word 0
        .text "vt52 terminal",0
        .fill N_APPBASE+32-*,0

; ---- start and stop -----------------------------------------------------------------
vt_start:
        cld
        jsr vt_video_begin
        bcs vt_no_serial        ; restores whatever was already changed
        jsr vt_acia_open
        bcs vt_no_serial
        jsr vt_reset
vt_loop:
-       ldy vt_rx_tail          ; everything received so far
        cpy vt_rx_head
        beq +
        lda vt_rx_buf,y
        iny
        sty vt_rx_tail
        jsr vt_put
        jmp -
+       jsr vt_place_cursor
        lda vt_quit_request     ; a non-serial NMI, a stuck transmitter or VDC
        bne vt_quit
        lda #1
        sta N_READY
        jsr N_KEYIN
        ldx #0
        stx N_READY
        cmp #0
        beq vt_loop
        cmp #VT_QUIT_KEY
        beq vt_quit
        jsr vt_key
        jmp vt_loop
vt_quit:
        jsr vt_acia_close
vt_no_serial:
        jsr vt_video_end
vt_leave:
        lda #0
        jmp N_EXIT

; ---- keyboard -> host ---------------------------------------------------------------
; PETSCII key -> ASCII; cursor keys send VT52 ESC A..D.
vt_key:
        ldx #3
-       cmp vt_cursor_keys,x
        beq vt_key_cursor
        dex
        bpl -
        cmp #$14                ; DEL: backspace
        bne +
        lda #8
        jmp vt_send
+       cmp #$0d
        beq vt_send
        cmp #$1b
        beq vt_send
        cmp #$20
        bcc vt_send             ; Ctrl-letter and Tab are ASCII controls already
        cmp #$41
        bcc vt_send             ; space, digits, punctuation
        cmp #$5b
        bcs +
        ora #$20                ; unshifted letters are lowercase
        jmp vt_send
+       cmp #$60
        bcc vt_send             ; [ \ ] ^ _
        cmp #$c1
        bcc vt_key_done
        cmp #$db
        bcs vt_key_done
        and #$7f                ; shifted letters are uppercase
        jmp vt_send
vt_key_cursor:
        lda vt_cursor_codes,x   ; (vt_send uses X)
        pha
        lda #27
        jsr vt_send
        pla
vt_send:                        ; transmit A, bounded wait for the transmitter
        pha
        ldx #0
        ldy #0
-       lda ACIA_STATUS
        and #$10
        bne +
        dex
        bne -
        dey
        bne -
        pla
        lda #2
        sta vt_quit_request
        rts
+       pla
        sta ACIA_DATA
vt_key_done:
        rts
vt_cursor_keys: .byte $91,$11,$1d,$9d
vt_cursor_codes: .byte $41,$42,$43,$44 ; A B C D

; ---- the VT52 interpreter -------------------------------------------------------------
vt_reset:
        lda #0
        sta vt_state
        sta vt_row
        sta vt_col
        sta vt_reverse
        sta vt_saved_row
        sta vt_saved_col
        lda #1
        sta vt_wrap
        sta vt_cursor_on
        lda #15
        sta vt_fg
        lda #0                  ; background: VDC register 26, low nibble
        sta vt_bg
        jsr vt_set_background
        jmp vt_clear_all

; A = received byte.
vt_put:
        ldx vt_state
        beq vt_put_normal
        dex
        beq vt_escape
        dex
        beq vt_y_row
        dex
        beq vt_y_col
        dex
        beq vt_fg_color
        and #15                 ; state 5: ESC c, background
        sta vt_bg
        lda #0
        sta vt_state
        jmp vt_set_background
vt_fg_color:
        and #15
        sta vt_fg
        lda #0
        sta vt_state
        rts
vt_y_row:
        sec
        sbc #32
        cmp #VT_ROWS
        bcc +
        lda #VT_ROWS-1
+       sta vt_row
        lda #3
        sta vt_state
        rts
vt_y_col:
        sec
        sbc #32
        cmp #VT_COLS
        bcc +
        lda #VT_COLS-1
+       sta vt_col
        lda #0
        sta vt_state
        rts
vt_put_normal:
        cmp #32
        bcc vt_control
        cmp #127
        bcs vt_ignore
        jsr vt_draw_char
        inc vt_col
        lda vt_col
        cmp #VT_COLS
        bcc vt_ignore
        lda vt_wrap
        bne +
        dec vt_col              ; no wrap: stay on the last column
        rts
+       lda #0
        sta vt_col
        jmp vt_line_feed
vt_ignore:
        rts
vt_control:
        cmp #27
        bne vt_c_cr
        lda #1
        sta vt_state
        rts
vt_c_cr:
        cmp #13
        bne vt_c_bs
        lda #0
        sta vt_col
        rts
vt_c_bs:
        cmp #8
        bne vt_c_tab
        lda vt_col
        beq vt_ignore
        dec vt_col
        rts
vt_c_tab:
        cmp #9
        bne vt_c_lf
        lda vt_col              ; next multiple of 8, at most the last column
        ora #7
        clc
        adc #1
        cmp #VT_COLS
        bcc +
        lda #VT_COLS-1
+       sta vt_col
        rts
vt_c_lf:
        cmp #7                  ; BEL: the SID bell
        bne +
        jmp sd_bell
+       cmp #10                 ; LF, VT and FF move down
        bcc vt_ignore
        cmp #13
        bcs vt_ignore
vt_line_feed:
        lda vt_row
        cmp #VT_ROWS-1
        bcs +
        inc vt_row
        rts
+       jmp vt_scroll_up

; After ESC: A = command letter.
vt_escape:
        ldx #0
        stx vt_state
        ldx #vt_esc_count-1
-       cmp vt_esc_keys,x
        beq +
        dex
        bpl -
        rts                     ; unknown: ignored
+       lda vt_esc_hi,x
        pha
        lda vt_esc_lo,x
        pha
        rts
vt_esc_keys: .byte $41,$42,$43,$44,$45,$48,$49,$4a,$4b,$4c,$4d,$59
        .byte $62,$63,$64,$65,$66,$6a,$6b,$6c,$6f,$70,$71,$76,$77
vt_esc_count = *-vt_esc_keys
vt_esc_lo:
        .byte <(vt_up-1),<(vt_down-1),<(vt_right-1),<(vt_left-1),<(vt_clear_home-1),<(vt_home-1)
        .byte <(vt_reverse_lf-1),<(vt_erase_eos-1),<(vt_erase_eol-1),<(vt_insert_line-1),<(vt_delete_line-1),<(vt_y_start-1)
        .byte <(vt_fg_start-1),<(vt_bg_start-1),<(vt_erase_sos-1),<(vt_cursor_show-1),<(vt_cursor_hide-1),<(vt_save-1)
        .byte <(vt_restore-1),<(vt_erase_line-1),<(vt_erase_sol-1),<(vt_reverse_on-1),<(vt_reverse_off-1),<(vt_wrap_on-1)
        .byte <(vt_wrap_off-1)
vt_esc_hi:
        .byte >(vt_up-1),>(vt_down-1),>(vt_right-1),>(vt_left-1),>(vt_clear_home-1),>(vt_home-1)
        .byte >(vt_reverse_lf-1),>(vt_erase_eos-1),>(vt_erase_eol-1),>(vt_insert_line-1),>(vt_delete_line-1),>(vt_y_start-1)
        .byte >(vt_fg_start-1),>(vt_bg_start-1),>(vt_erase_sos-1),>(vt_cursor_show-1),>(vt_cursor_hide-1),>(vt_save-1)
        .byte >(vt_restore-1),>(vt_erase_line-1),>(vt_erase_sol-1),>(vt_reverse_on-1),>(vt_reverse_off-1),>(vt_wrap_on-1)
        .byte >(vt_wrap_off-1)
vt_up:
        lda vt_row
        beq +
        dec vt_row
+       rts
vt_down:
        lda vt_row
        cmp #VT_ROWS-1
        bcs +
        inc vt_row
+       rts
vt_right:
        lda vt_col
        cmp #VT_COLS-1
        bcs +
        inc vt_col
+       rts
vt_left:
        lda vt_col
        beq +
        dec vt_col
+       rts
vt_clear_home:
        jsr vt_clear_all
vt_home:
        lda #0
        sta vt_row
        sta vt_col
        rts
vt_reverse_lf:
        lda vt_row
        beq +
        dec vt_row
        rts
+       lda #0                  ; at the top: the screen moves down
        jmp vt_open_line
vt_erase_eos:                   ; cursor .. end of screen
        jsr vt_cursor_offset
        jsr vt_range_to_end
        jmp vt_erase_range
vt_erase_eol:                   ; cursor .. end of line
        jsr vt_cursor_offset
        lda #VT_COLS
        sec
        sbc vt_col
        sta vt_count
        lda #0
        sta vt_count+1
        jmp vt_erase_range
vt_erase_sos:                   ; start of screen .. cursor
        jsr vt_cursor_offset
        jsr vt_range_from_start
        jmp vt_erase_range
vt_erase_line:
        lda vt_row
        jsr vt_row_offset
        lda #VT_COLS
        sta vt_count
        lda #0
        sta vt_count+1
        jmp vt_erase_range
vt_erase_sol:                   ; start of line .. cursor
        lda vt_row
        jsr vt_row_offset
        ldx vt_col
        inx
        stx vt_count
        lda #0
        sta vt_count+1
        jmp vt_erase_range
vt_insert_line:
        lda #0
        sta vt_col
        lda vt_row
        jmp vt_open_line
vt_delete_line:
        lda #0
        sta vt_col
        lda vt_row
        jmp vt_close_line
vt_y_start:
        lda #2
        sta vt_state
        rts
vt_fg_start:
        lda #4
        sta vt_state
        rts
vt_bg_start:
        lda #5
        sta vt_state
        rts
vt_cursor_show:
        lda #1
        bne +
vt_cursor_hide:
        lda #0
+       sta vt_cursor_on
        rts
vt_save:
        lda vt_row
        sta vt_saved_row
        lda vt_col
        sta vt_saved_col
        rts
vt_restore:
        lda vt_saved_row
        sta vt_row
        lda vt_saved_col
        sta vt_col
        rts
vt_reverse_on:
        lda #$40
        bne +
vt_reverse_off:
        lda #0
+       sta vt_reverse
        rts
vt_wrap_on:
        lda #1
        bne +
vt_wrap_off:
        lda #0
+       sta vt_wrap
        rts

; ---- screen operations on the VDC -------------------------------------------------------
; A (printable ASCII) at the cursor, with the current colour and reverse.
vt_draw_char:
        pha
        jsr vt_cursor_offset
        jsr vt_set_address
        pla
        jsr vd_put
        lda vt_offset+1
        clc
        adc #>ATTR_BASE
        tay
        lda vt_offset
        jsr vd_address
        lda vt_fg
        ora vt_reverse
        ora #$80                ; the alternate set holds the ASCII font
        jmp vd_put
; Blank vt_count cells from vt_offset (spaces, plain colour).
vt_erase_range:
        lda vt_count
        ora vt_count+1
        beq +
        lda vt_count            ; the fills consume the count
        sta vt_count2
        lda vt_count+1
        sta vt_count2+1
        jsr vt_set_address
        lda #32
        jsr vd_fill
        jsr vt_count_again
        lda vt_offset+1
        clc
        adc #>ATTR_BASE
        tay
        lda vt_offset
        jsr vd_address
        jsr vt_plain_attr
        jmp vd_fill
+       rts
vt_count_again:
        lda vt_count2
        sta vt_count
        lda vt_count2+1
        sta vt_count+1
        rts
vt_plain_attr:
        lda vt_fg
        ora #$80
        rts
vt_clear_all:
        lda #0
        sta vt_offset
        sta vt_offset+1
        lda #<(VT_ROWS*VT_COLS)
        sta vt_count
        lda #>(VT_ROWS*VT_COLS)
        sta vt_count+1
        jmp vt_erase_range
; Scroll everything up one row; the last row is blanked.
vt_scroll_up:
        lda #0
        jmp vt_close_line
; A = row: rows A+1.. move up one; the last row is blanked.
vt_close_line:
        sta vt_line
        cmp #VT_ROWS-1
        bcs vt_close_last
        jsr vt_row_offset       ; destination: row A
        lda vt_offset
        sta vt_dest
        lda vt_offset+1
        sta vt_dest+1
        lda vt_line             ; source: row A+1
        clc
        adc #1
        jsr vt_row_offset
        lda #VT_ROWS-1          ; count: (24-A) rows
        sec
        sbc vt_line
        jsr vt_rows_count
        jsr vt_copy_both
vt_close_last:
        lda #VT_ROWS-1
        jmp vt_blank_row
; A = row: rows A..23 move down one (from the bottom up); row A is blanked.
vt_open_line:
        sta vt_line
        lda #VT_ROWS-2
        sta vt_i
-       lda vt_i
        bmi +
        cmp vt_line
        bcc +
        clc                     ; row i -> row i+1
        adc #1
        jsr vt_row_offset
        lda vt_offset
        sta vt_dest
        lda vt_offset+1
        sta vt_dest+1
        lda vt_i
        jsr vt_row_offset
        lda #1
        jsr vt_rows_count
        jsr vt_copy_both
        dec vt_i
        jmp -
+       lda vt_line
vt_blank_row:
        jsr vt_row_offset
        lda #VT_COLS
        sta vt_count
        lda #0
        sta vt_count+1
        jmp vt_erase_range
; Copy vt_count cells from vt_offset to vt_dest, characters and attributes.
vt_copy_both:
        lda vt_count            ; the copy consumes the count
        sta vt_count2
        lda vt_count+1
        sta vt_count2+1
        jsr vt_copy
        jsr vt_count_again
        lda vt_offset+1
        clc
        adc #>ATTR_BASE
        sta vt_offset+1
        lda vt_dest+1
        clc
        adc #>ATTR_BASE
        sta vt_dest+1
vt_copy:
        lda vt_dest+1
        ldx #18
        jsr vd_reg_write
        lda vt_dest
        ldx #19
        jsr vd_reg_write
        lda vt_offset+1
        ldx #32
        jsr vd_reg_write
        lda vt_offset
        ldx #33
        jsr vd_reg_write
        lda vt_reg24
        ora #$80                ; block copy
        ldx #24
        jsr vd_reg_write
        jmp vd_blocks
; A rows -> vt_count cells.
vt_rows_count:
        tax
        lda #0
        sta vt_count
        sta vt_count+1
        cpx #0
        beq vt_rows_done
-       lda vt_count
        clc
        adc #VT_COLS
        sta vt_count
        bcc +
        inc vt_count+1
+       dex
        bne -
vt_rows_done:
        rts
; vt_offset = row A * 80 (row*16 + row*64). Row < 25.
vt_row_offset:
        ldx #0
        stx vt_offset+1
        asl
        asl
        asl
        asl                     ; row*16 < 512: only this shift can carry
        rol vt_offset+1
        sta vt_offset
        sta vt_math
        lda vt_offset+1
        sta vt_math+1
        asl vt_offset           ; *64
        rol vt_offset+1
        asl vt_offset
        rol vt_offset+1
        lda vt_offset
        clc
        adc vt_math
        sta vt_offset
        lda vt_offset+1
        adc vt_math+1
        sta vt_offset+1
        rts
vt_cursor_offset:
        lda vt_row
        jsr vt_row_offset
        lda vt_offset
        clc
        adc vt_col
        sta vt_offset
        bcc +
        inc vt_offset+1
+       rts
vt_range_to_end:                ; vt_count = 2000 - vt_offset
        lda #<(VT_ROWS*VT_COLS)
        sec
        sbc vt_offset
        sta vt_count
        lda #>(VT_ROWS*VT_COLS)
        sbc vt_offset+1
        sta vt_count+1
        rts
vt_range_from_start:            ; vt_count = vt_offset + 1, from offset 0
        lda vt_offset
        clc
        adc #1
        sta vt_count
        lda vt_offset+1
        adc #0
        sta vt_count+1
        lda #0
        sta vt_offset
        sta vt_offset+1
        rts
vt_set_address:
        ldy vt_offset+1
        lda vt_offset
; A = low, Y = high: the update address; the data port stays selected.
vd_address:
        pha
        tya
        ldx #18
        jsr vd_reg_write
        pla
        ldx #19
        jsr vd_reg_write
        ldx #31
        stx VDC_ADDR
        rts
; A -> the data port.
vd_put:
        jsr vd_wait
        sta VDC_DATA
        rts
; A written vt_count times from the current address (first byte, then fills).
vd_fill:
        jsr vd_put
        lda vt_count
        sec
        sbc #1
        sta vt_count
        bcs +
        dec vt_count+1
+       lda vt_reg24
        and #$7f                ; block fill
        ldx #24
        jsr vd_reg_write
; vt_count more bytes, in blocks of at most 255.
vd_blocks:
        lda vt_count+1
        bne +
        lda vt_count
        beq vd_blocks_done
        cmp #255
        bcc ++
+       lda #255
+       sta vt_math
        ldx #30
        jsr vd_reg_write
        lda vt_count
        sec
        sbc vt_math
        sta vt_count
        bcs vd_blocks
        dec vt_count+1
        jmp vd_blocks
vd_blocks_done:
        rts
; X = register, A = value.
vd_reg_write:
        stx VDC_ADDR
        jsr vd_wait
        sta VDC_DATA
        rts
; X = register -> A.
vd_reg_read:
        stx VDC_ADDR
        jsr vd_wait
        lda VDC_DATA
        rts
; Bounded wait for the VDC's ready bit. A lost VDC ends the session.
vd_wait:
        pha
        lda #0
        sta vt_wait
        sta vt_wait+1
-       bit VDC_ADDR
        bmi +
        dec vt_wait
        bne -
        dec vt_wait+1
        bne -
        lda #3
        sta vt_quit_request
+       pla
        rts
vt_place_cursor:
        lda vt_cursor_on
        beq +
        jsr vt_cursor_offset
        lda vt_offset+1
        ldx #14
        jsr vd_reg_write
        lda vt_offset
        ldx #15
        jsr vd_reg_write
        lda #$60                ; blinking
        bne ++
+       lda #$20                ; off
+       ldx #10
        jmp vd_reg_write
vt_set_background:
        lda vt_bg
        ldx #26
        jmp vd_reg_write

; ---- taking over and giving back the VDC -----------------------------------------------
VT_SAVED_REGS = 37
vt_video_begin:
        lda N_CURRENT           ; the kernel's font copy lives in an owned allocation
        sta N_OWNER
        lda #16
        sta N_PAGES
        lda #$ff
        sta N_BANK
        jsr N_ALLOC
        bcc +
        rts
+       ldx #3
-       lda N_HANDLE,x
        sta vt_font_token,x
        dex
        bpl -
        php                     ; one code per programmable key (F8 would type MONITOR)
        sei
        ldx #0
-       lda $1000,x
        sta vt_saved_keys,x
        inx
        bne -
        ldx #9
-       lda #1
        sta $1000,x
        lda vt_native_keys,x
        sta $100a,x
        dex
        bpl -
        lda #0
        sta $d1
        sta $d2
        plp
        lda $d7
        sta vt_saved_screen
        ldx #0
-       cpx #31                 ; never read the data port as a register
        beq +
        jsr vd_reg_read
        sta vt_saved_vdc,x
+       inx
        cpx #VT_SAVED_REGS
        bne -
        lda vt_saved_vdc+24
        sta vt_reg24
        lda #1
        sta vt_phase
        lda vt_saved_screen     ; the 80-column screen
        bmi +
        jsr $ff5f
+       lda #$93
        jsr $ffd2
        jsr vt_font_address     ; save the alternate character set (4 KiB)
        jsr vd_wait             ; prime the read latch, then point again
        lda VDC_DATA
        jsr vt_font_address
        lda #0
        sta vt_chunk
-       ldx #0                  ; 512 bytes into N_BUFFER
-       jsr vd_wait
        lda VDC_DATA
        sta N_BUFFER,x
        inx
        bne -
-       jsr vd_wait
        lda VDC_DATA
        sta N_BUFFER+256,x
        inx
        bne -
        jsr vt_font_chunk
        jsr N_WRITE
        bcc +
        rts                     ; phase 1: the caller restores what was changed
+       inc vt_chunk
        lda vt_chunk
        cmp #8
        bne ---
        lda #2
        sta vt_phase
        jsr vt_font_address     ; the ASCII font: codes 32..126, 8 of 16 rows
        lda #0
        tax
-       jsr vd_put              ; codes 0..31 blank
        inx
        bne -
-       jsr vd_put
        inx
        bne -
        lda #<vt_font
        sta vt_font_read+1
        lda #>vt_font
        sta vt_font_read+2
        ldx #95
-       ldy #0
vt_font_read:
        lda $ffff,y
        jsr vd_put
        iny
        cpy #8
        bne vt_font_read
        lda #0
-       jsr vd_put
        dey
        bne -
        lda vt_font_read+1
        clc
        adc #8
        sta vt_font_read+1
        bcc +
        inc vt_font_read+2
+       dex
        bne --
        lda #0                  ; screen at $0000, attributes at $0800
        ldx #12
        jsr vd_reg_write
        inx
        jsr vd_reg_write
        ldx #21
        jsr vd_reg_write
        ldx #27
        jsr vd_reg_write
        lda #>ATTR_BASE
        ldx #20
        jsr vd_reg_write
        lda vt_saved_vdc+25     ; text mode with attributes
        and #$7f
        ora #$40
        ldx #25
        jsr vd_reg_write
        clc
        rts
vt_font_address:
        lda vt_saved_vdc+28
        and #$e0
        clc
        adc #$10
        tay
        lda #0
        jmp vd_address
vt_font_chunk:                  ; heap offset chunk*512, 512 bytes
        lda N_CURRENT
        sta N_OWNER
        ldx #3
-       lda vt_font_token,x
        sta N_HANDLE,x
        dex
        bpl -
        lda #0
        sta N_OFFSET
        sta N_COUNT
        lda vt_chunk
        asl
        sta N_OFFSET+1
        lda #2
        sta N_COUNT+1
        rts

; Restore in reverse; each phase undoes what its step changed.
vt_video_end:
        lda vt_phase
        cmp #2
        bcc vt_font_kept
        jsr vt_font_address     ; the saved font back
        lda #0
        sta vt_chunk
-       jsr vt_font_chunk
        jsr N_READ
        bcs vt_font_kept        ; unreadable: leave our font rather than garbage
        ldx #0
-       lda N_BUFFER,x
        jsr vd_put
        inx
        bne -
-       lda N_BUFFER+256,x
        jsr vd_put
        inx
        bne -
        inc vt_chunk
        lda vt_chunk
        cmp #8
        bne ---
vt_font_kept:
        lda vt_phase
        beq vt_video_done
        ldy #0                  ; the VDC mode
-       ldx vt_restore_regs,y
        lda vt_saved_vdc,x
        jsr vd_reg_write
        iny
        cpy #vt_restore_count
        bne -
        lda N_CURRENT           ; the font copy
        sta N_OWNER
        ldx #3
-       lda vt_font_token,x
        sta N_HANDLE,x
        dex
        bpl -
        jsr N_FREE
        lda vt_saved_screen     ; the screen the kernel had
        cmp $d7
        beq +
        jsr $ff5f
+       php
        sei
        ldx #0
-       lda vt_saved_keys,x
        sta $1000,x
        inx
        bne -
        lda #0
        sta $d1
        sta $d2
        plp
        lda #0
        sta vt_phase
vt_video_done:
        rts
vt_restore_regs: .byte 10,11,12,13,14,15,20,21,24,25,26,27,28,29,32,33,18,19
vt_restore_count = *-vt_restore_regs
vt_native_keys: .byte $85,$89,$86,$8a,$87,$8b,$88,$8c,$83,$84

; ---- the serial port ----------------------------------------------------------------------
; Carry set when there is no ACIA, or another owner has it running.
vt_acia_open:
        lda ACIA_CTRL
        sta vt_saved_control
        lda ACIA_CMD
        sta vt_saved_command
        and vt_saved_control
        cmp #$ff                ; floating: absent
        beq vt_acia_absent
        lda vt_saved_command
        and #1                  ; DTR already on: in use
        bne vt_acia_absent
        lda #ACIA_CTRL_VAL
        sta ACIA_CTRL
        cmp ACIA_CTRL
        bne vt_acia_restore
        php
        sei
        lda #0
        sta vt_rx_head
        sta vt_rx_tail
        sta vt_quit_request
        sta ACIA_CMD            ; the interrupt source is off while installing
        lda ACIA_STATUS
        lda ACIA_DATA
        lda NMI_VECTOR
        sta vt_old_nmi
        lda NMI_VECTOR+1
        sta vt_old_nmi+1
        lda N_NMIPTR
        sta vt_old_gate
        lda N_NMIPTR+1
        sta vt_old_gate+1
        lda #<vt_nmi
        sta N_NMIPTR
        lda #>vt_nmi
        sta N_NMIPTR+1
        lda #<N_NMIGATE
        sta NMI_VECTOR
        lda #>N_NMIGATE
        sta NMI_VECTOR+1
        lda #1
        sta vt_serial_owned
        lda #ACIA_CMD_VAL
        sta ACIA_CMD
        plp
        clc
        rts
vt_acia_restore:
        lda vt_saved_control
        sta ACIA_CTRL
vt_acia_absent:
        sec
        rts
vt_acia_close:
        lda vt_serial_owned
        bne +
        rts
+       ldx #0                  ; let the last byte leave the transmitter
-       lda ACIA_STATUS
        and #$10
        bne +
        dex
        bne -                   ; (bounded; close regardless)
+       ldx #24                 ; one character time at 19200 baud and more
-       dex
        bne -
        php
        sei
        lda #0
        sta ACIA_CMD
        lda ACIA_STATUS
        lda ACIA_DATA
        lda vt_old_nmi
        sta NMI_VECTOR
        lda vt_old_nmi+1
        sta NMI_VECTOR+1
        lda vt_old_gate
        sta N_NMIPTR
        lda vt_old_gate+1
        sta N_NMIPTR+1
        lda vt_saved_control
        sta ACIA_CTRL
        lda vt_saved_command
        sta ACIA_CMD
        lda #0
        sta vt_serial_owned
        plp
        rts
; Entered from the ROM NMI stub (A/X/Y and the MMU saved): leave via $ff33.
vt_nmi:
        lda ACIA_STATUS         ; reading clears the interrupt
        and #$08                ; a received byte?
        beq vt_nmi_other
        lda ACIA_DATA
        ldx vt_rx_head
        inx
        cpx vt_rx_tail
        beq +                   ; full: dropped and counted
        dex
        sta vt_rx_buf,x
        inx
        stx vt_rx_head
        jmp NMI_EXIT
+       inc vt_rx_dropped
        jmp NMI_EXIT
vt_nmi_other:
        lda $dd0d               ; RESTORE or CIA2: leave the terminal
        lda #1
        sta vt_quit_request
        jmp NMI_EXIT

.include "sound.inc"
vt_font: .binary "graphics/font8.bin"

vt_state: .byte 0
vt_row: .byte 0
vt_col: .byte 0
vt_saved_row: .byte 0
vt_saved_col: .byte 0
vt_fg: .byte 15
vt_bg: .byte 0
vt_reverse: .byte 0
vt_wrap: .byte 1
vt_cursor_on: .byte 1
vt_line: .byte 0
vt_i: .byte 0
vt_math: .word 0
vt_offset: .word 0
vt_dest: .word 0
vt_count: .word 0
vt_count2: .word 0
vt_wait: .word 0
vt_reg24: .byte 0
vt_phase: .byte 0
vt_chunk: .byte 0
vt_quit_request: .byte 0
vt_serial_owned: .byte 0
vt_rx_dropped: .byte 0
vt_rx_head: .byte 0
vt_rx_tail: .byte 0
vt_saved_screen: .byte 0
vt_saved_control: .byte 0
vt_saved_command: .byte 0
vt_old_nmi: .word 0
vt_old_gate: .word 0
vt_font_token: .fill 4,0
vt_saved_vdc: .fill VT_SAVED_REGS,0
vt_saved_keys: .fill 256,0
        .align 256
vt_rx_buf: .fill 256,0
vt_end:
.cerror vt_end > N_APPLIMIT, "the VT52 terminal exceeds its slot"
