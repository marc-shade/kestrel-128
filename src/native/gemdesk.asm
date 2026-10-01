; GEM desktop (docs/GEM-DESKTOP.md): drive icons and folder windows on the
; AES. Written as "browse" on the GEM boot disk, so launched apps return here.
.include "api.inc"
.include "aes-api.inc"
AE_POINTER = 1
AE_MIRROR = 1
FO_PRESENT = 1                  ; forms.inc calls ae_present from its dialog loop
GM_WINDOWS = 4
GM_RECORD = 21                 ; name 16, type, flags, blocks (word), directory ordinal
GM_CHUNK = 24                  ; records per N_BUFFER transfer (504 bytes)
GM_MAX_ENTRIES = 195            ; 16 pages of records: the $5000 workspace, a window's snapshot
GM_WORKSPACE = $5000             ; bank-0 workspace reserved at start (like Files)
GM_PAGES = (GM_MAX_ENTRIES*GM_RECORD+255)/256
GM_PAPER = $61                 ; window work: blue ink on white
GM_SELECTED = $16              ; selected row: white on blue
GM_DESK = $16                  ; desktop: white icons on blue
GM_ICON_SELECTED = $61
GM_ICONS = 5                   ; Boot, Drive 9, Trash; USB and Printer when they answer
GM_USB = 3
GM_PRINTER = 4
GM_PRT_LFN = 121               ; the printer probe's KERNAL file (the file service uses 122..126)
GM_APP_PAGES = 96              ; the core, then the GDDLG.PRG module window
GM_MOP_INFO = 1                ; module operations
GM_MOP_PREFS = 2
GM_MOP_FORMAT = 3
GM_MOP_CONTROL = 4
GM_MOP_USBINFO = 5              ; GDUSB: Show Info (and rename) on a USB entry
GM_MOP_COPY = 6                 ; GDCPY: a row dropped on a window or drive icon
GM_MOP_RESTORE = 7              ; GDSES: the desktop at start
GM_MOP_SAVEDESK = 8             ; GDSES: Options:Save Desktop
GM_MOP_NEWFOLDER = 9            ; GDNEW: File:New Folder (USB)
GM_NOCOPYASK = 2                ; gm_confirm: Preferences turned Confirm copies off
GM_KEYCLICK = 4                 ; gm_confirm: Control Panel turned Key click on
GM_NOOVERASK = 8                ; gm_confirm: Preferences turned Confirm overwrites off
GM_BELL = 16                    ; gm_confirm: Control Panel turned the bell on
GM_MOP_PRTSCR = 10              ; GDPRT: Options:Print Screen, or HELP
GM_MOP_DISKCOPY = 11            ; GDDSK: a drive icon dropped on the other drive's icon
GM_MOP_PRINT = 12               ; GDPRT: rows dropped on the Printer icon
GM_MOP_LOCK = 13                ; GDDSK: Show Info changed Read-only (gm_lock_want)
GM_REC_COUNT = 9               ; desktop record: window count, then windows
GM_REC_WINDOWS = 10
GM_BITS = (GM_MAX_ENTRIES+7)/8
* = N_APPBASE
gm_image:
        .text "napp"
        .byte 1,1,14,<(gm_module-gm_image)
        .word gm_module-gm_image
        .byte GM_APP_PAGES,>(gm_module-gm_image)
        .word gm_start-gm_image
        .word 0
        .text "gem desktop",0
        .fill N_APPBASE+32-*,0

gm_start:
        cld
        lda N_BROWSERERROR      ; a program the dispatcher could not start
        sta gm_start_error
        lda #0
        sta N_BROWSERERROR
        lda #$ff
        sta gm_icon_sel
        jsr gm_surface_setup
        bcs gm_fatal_text
        jsr gm_aes_setup
        bcs gm_fatal
        jsr vd_open             ; the 80-column mirror; without it, 40 columns only
        bcc +
        jsr vd_close
+       lda gm_start_error
        beq gm_loop
        jsr gm_hex_error        ; "[3][Could not start that|program: error $xx][OK]"
        lda #<gm_start_alert
        ldx #>gm_start_alert
        ldy #1
        jsr gm_alert
gm_loop:
        lda #MU_MESAG|MU_BUTTON|MU_KEYBD
        sta ae_ev_params
        lda #2                  ; up to a double click
        sta ae_ev_params+1
        lda #1
        sta ae_ev_params+2
        sta ae_ev_params+3
        jsr ae_event
        bcs gm_fatal
        lda ae_ev_result
        and #MU_MESAG
        beq +
        jsr gm_message
+       lda ae_ev_result
        and #MU_BUTTON
        beq +
        jsr gm_click
+       lda ae_ev_result
        and #MU_KEYBD
        beq +
        jsr gm_key
+       jsr ae_present
        jmp gm_loop
; The AES is unusable: back to the card launcher, which reports the code.
gm_fatal:
        sta N_BROWSERERROR
        jsr gm_leave
        jsr N_VCLOSE
gm_fatal_text:
        jmp gm_launcher

; ---- surface, pointer ----------------------------------------------------------
gm_surface_setup:
        lda N_CURRENT           ; the sort workspace: bank 0 $5000..$5fff
        sta N_OWNER
        lda #0
        sta N_BANK
        lda #>GM_WORKSPACE
        sta N_PAGE
        lda #16
        sta N_PAGES
        jsr N_RESERVE
        bcs gm_setup_done
        lda N_CURRENT           ; the windows' USB paths: a page each
        sta N_OWNER
        lda #GM_WINDOWS
        sta N_PAGES
        lda #$ff
        sta N_BANK
        jsr N_ALLOC
        bcs gm_setup_done
        ldx #3
-       lda N_HANDLE,x
        sta gm_paths,x
        dex
        bpl -
        lda N_CURRENT
        sta N_OWNER
        lda #0
        sta N_BANK
        lda #$c0
        sta N_PAGE
        lda #36
        sta N_PAGES
        jsr N_RESERVE
        bcs gm_setup_done
        ldx #3
-       lda N_HANDLE,x
        sta gm_surface,x
        sta ae_surface,x
        dex
        bpl -
        lda #0
        sta N_OFFSET
        sta N_OFFSET+1
        sta N_COUNT
        lda #2
        sta N_COUNT+1
-       lda #0
        ldx N_OFFSET+1
        cpx #$20
        bcc +
        lda gm_desk_color
+       sta N_VALUE
        jsr N_FILL
        bcs gm_setup_done
        inc N_OFFSET+1
        inc N_OFFSET+1
        lda N_OFFSET+1
        cmp #$24
        bne -
        jsr gm_bind
        bcs gm_setup_done
        jsr gfx_clip_defaults
        jsr gm_ult_probe
        jsr gm_draw_icons
        bcs gm_setup_done
        jsr gm_select_surface
        jsr N_VSHOW
        bcs gm_setup_done
        jmp pm_install
gm_setup_done:
        rts
gm_select_surface:
        lda N_CURRENT
        sta N_OWNER
        ldx #3
-       lda gm_surface,x
        sta N_HANDLE,x
        dex
        bpl -
        rts
gm_bind:
        jsr gm_select_surface
        jmp gfx_bind
pm_control_count = 0
pm_select_surface = gm_select_surface
pm_find_hit:
        ldx #$ff                ; controls are AES objects, not pointer hits
        rts

; ---- AES -------------------------------------------------------------------------
gm_aes_setup:
        jsr ae_attach
        bcc gm_aes_ready
        cmp #N_BADHANDLE
        beq +
        sec
        rts
+       jsr gm_open_aesvc       ; none resident: load it from this folder
        bcs gm_aes_failed
        jsr ae_load
        php
        pha
        lda ae_stream_taken
        bne +
        jsr gm_close_file       ; the loader refused before taking it
+       pla
        plp
        bcs gm_aes_failed
gm_aes_ready:
        lda #WS_SURFACE
        sta N_BUFFER
        ldx #3
-       lda gm_surface,x
        sta N_BUFFER+1,x
        dex
        bpl -
        jsr gm_wcall
        bcs gm_aes_failed
        lda #<gm_menu
        ldx #>gm_menu
        jsr ae_menu_install
        bcs gm_aes_failed
        lda #GM_MOP_RESTORE     ; the desktop as it was left, or as saved (GDSES.PRG)
        jsr gm_module_run
        jmp gm_view_checks
gm_aes_failed:
        rts
; Open AESVC.PRG beside this program (IEC name or Ultimate sibling path).
gm_open_aesvc:
        lda N_DEVICE
        sta N_FDEVICE
        lda N_APPFORMAT
        sta N_FFORMAT
        cmp #3
        bne gm_open_iec
        ldx #0
        stx gm_math
-       lda N_SOURCEPATH,x
        sta N_UPATH,x
        cmp #$2f
        bne +
        txa
        clc
        adc #1
        sta gm_math             ; length through the last slash
+       inx
        cpx N_NAMELEN
        bne -
        lda gm_math
        clc
        adc #9
        bcs gm_open_bad
        sta N_FNAMELEN
        ldx gm_math
        ldy #0
-       lda gm_aesvc_name,y
        sta N_UPATH,x
        inx
        iny
        cpy #9
        bne -
        beq gm_open_now
gm_open_iec:
        lda #9
        sta N_FNAMELEN
        ldx #8
-       lda gm_aesvc_name,x
        sta N_FNAME,x
        dex
        bpl -
gm_open_now:
        lda #N_APPOWNER
        sta N_FOWNER
        lda #1
        sta N_FTYPE
        lda #0
        sta N_FMODE
        ldx #3
-       sta N_FHANDLE,x
        dex
        bpl -
        jsr N_FOPEN
        bcs +
        ldx #3
-       lda N_FHANDLE,x
        sta gm_file,x
        dex
        bpl -
        clc
+       rts
gm_open_bad:
        lda #N_BADARG
        sec
        rts
gm_close_file:
        lda #N_APPOWNER
        sta N_FOWNER
        ldx #3
-       lda gm_file,x
        sta N_FHANDLE,x
        dex
        bpl -
        jmp N_FCLOSE
gm_wcall:
        lda #AE_OP_WINDOW
        jsr ae_call
        bcs +
        ldx #4                  ; the rows it drew (reply bytes 4..7), for the mirror
        jsr gm_dirty_from
        lda #0
        clc
+       rts
; Append gm_q (LE32, destroyed) in decimal: divide by 10 until zero.
gm_anum32:
        lda #0
        sta gm_ndig
gm_n32_digit:
        lda #0                  ; gm_q /= 10, A = the remainder
        ldx #32
gm_n32_bit:
        asl gm_q
        rol gm_q+1
        rol gm_q+2
        rol gm_q+3
        rol a
        cmp #10
        bcc +
        sbc #10
        inc gm_q
+       dex
        bne gm_n32_bit
        ldx gm_ndig
        ora #$30
        sta gm_digits,x
        inc gm_ndig
        lda gm_q
        ora gm_q+1
        ora gm_q+2
        ora gm_q+3
        bne gm_n32_digit
-       dec gm_ndig             ; most significant first
        ldx gm_ndig
        lda gm_digits,x
        jsr gm_aput
        lda gm_ndig
        bne -
        rts
; OR the four dirty-row bytes at N_BUFFER+X..X+3 into ae_dirty. Keeps N_BUFFER.
gm_dirty_from:
        ldy #0
-       lda N_BUFFER,x
        ora ae_dirty,y
        sta ae_dirty,y
        inx
        iny
        cpy #4
        bne -
        rts
; Present what changed on the VDC: the AES's rows (bit row&7 of byte row>>3),
; then the rows the gfx library marked itself.
ae_present:
        ldx #24
gm_am_row:
        txa
        lsr
        lsr
        lsr
        tay
        lda ae_dirty,y
        sta gm_mbit
        txa
        and #7
        tay
        lda gm_mbit
-       dey
        bmi +
        lsr
        jmp -
+       and #1
        beq +
        sta vm_rows,x
        sta vm_pending
+       dex
        bpl gm_am_row
        lda #0
        ldx #3
-       sta ae_dirty,x
        dex
        bpl -
        jmp vm_present
; Leave for another app: restore the 80-column screen, then the pointer.
gm_leave:
        jsr vd_close
        jmp pm_close
; A/X = alert string, Y = default button. Keyboard and pointer until chosen;
; carry clear with the button (1..3) in A and N_BUFFER.
gm_alert:
        sta gm_alert_icon+1     ; the bell (Control Panel) for a stop alert, "[3]"
        stx gm_alert_icon+2
        pha
        lda gm_confirm
        and #GM_BELL
        beq +
        sty gm_alert_default
        ldy #1
gm_alert_icon:
        lda $ffff,y
        ldy gm_alert_default
        cmp #$33
        bne +
        jsr sd_bell             ; (keeps X and Y)
+       pla
        jsr ae_alert_open
        bcs gm_alert_done
        jsr gm_alert_rows
-       jsr ae_event_wait       ; idle until a key, the pointer or a tick
        pha
        jsr ae_read_pointer
        pla
        jsr ae_alert_step
        bcs gm_alert_done
        lda N_BUFFER
        pha
        jsr gm_alert_rows
        pla
        beq -
        sta N_BUFFER            ; the button again: the VDC mirror's present used N_BUFFER
        clc
gm_alert_done:
        rts
gm_alert_rows:                  ; an alert reply: dirty rows in bytes 2..5
        ldx #2
        jsr gm_dirty_from
        jmp ae_present

; ---- messages --------------------------------------------------------------------
gm_message:
        lda ae_ev_result+7
        cmp #MN_SELECTED
        bne +
        jmp gm_menu_choice
+       cmp #WM_REDRAW
        bne +
        ldx ae_ev_result+10
        bne gm_redraw_window
        jmp gm_redraw_desktop
+       ldx ae_ev_result+10     ; window messages: find our slot
        jsr gm_slot_of
        bcc +
        rts
+       stx gm_slot
        lda ae_ev_result+7
        cmp #WM_TOPPED
        bne +
        lda #WF_TOP
        jmp gm_wset_simple
+       cmp #WM_CLOSED
        bne +
        jmp gm_close_or_up
+       cmp #WM_FULLED
        bne +
        jmp gm_fulled
+       cmp #WM_ARROWED
        bne +
        jmp gm_arrowed
+       cmp #WM_VSLID
        bne +
        jmp gm_vslid
+       cmp #WM_MOVED           ; moved and sized: take the rectangle
        beq +
        cmp #WM_SIZED
        bne gm_message_done
+       ldx #3
-       lda ae_ev_result+11,x
        sta gm_rect,x
        dex
        bpl -
        jsr gm_set_rect
        jmp gm_update_slider
gm_message_done:
        rts
gm_redraw_window:
        jsr gm_slot_of
        bcs gm_message_done
        stx gm_slot
        ldx #3
-       lda ae_ev_result+11,x
        sta gm_clip,x
        dex
        bpl -
        jmp gm_paint_window

; ---- desktop icons ----------------------------------------------------------------
; Icons at columns 34..37: glyph rows y, y+1, label row y+2.
gm_redraw_desktop:
        ldx #3
-       lda ae_ev_result+11,x
        sta gm_clip,x
        dex
        bpl -
        jsr gm_bind
        bcs gm_icons_done
        lda #WS_GET             ; visible desktop rectangles
        sta N_BUFFER
        lda #0
        sta N_BUFFER+1
        lda #WF_FIRSTXYWH
        sta N_BUFFER+2
-       jsr gm_wcall
        bcs gm_icons_clip_reset
        lda N_BUFFER+2
        beq gm_icons_clip_reset
        jsr gm_clip_to_rect     ; rectangle within the redraw area
        bcs +
        jsr gm_draw_icons
        bcs gm_icons_clip_reset
+       lda #WS_GET
        sta N_BUFFER
        lda #WF_NEXTXYWH
        sta N_BUFFER+2
        jmp -
gm_icons_clip_reset:
        php
        pha
        jsr gfx_clip_defaults
        pla
        plp
gm_icons_done:
        rts
; Draw every icon with the current clip.
gm_draw_icons:
        lda #0
        sta gm_i
-       ldx gm_i
        cpx #GM_ICONS
        bcs +
        lda gm_icon_on,x        ; USB and Printer only when present
        beq gm_icon_next
        jsr gm_draw_icon
        bcs ++
gm_icon_next:
        inc gm_i
        bne -
+       clc
+       rts
gm_draw_icon:
        ldx gm_i
        lda gm_icon_art,x
        sta gm_art
        lda gm_icon_y,x
        sta gm_row
        lda #0
        sta gm_j
-       lda gm_j                ; 8 glyphs: 4 columns x 2 rows
        and #3
        clc
        adc #34
        jsr gm_times8
        sta gfx_x0
        stx gfx_x0+1
        lda gm_j
        lsr
        lsr
        clc
        adc gm_row
        jsr gm_times8
        sta gfx_y0
        stx gfx_y0+1
        lda gm_art              ; art: 16 rows x 4 bytes
        asl
        asl
        asl
        asl
        asl
        asl                     ; *64
        sta gm_math
        lda gm_j
        and #4                  ; lower glyph row: +32
        asl
        asl
        asl
        clc
        adc gm_math
        sta gm_math
        lda gm_j
        and #3
        clc
        adc gm_math
        tax
        ldy #0
-       lda gm_icon_bits,x
        sta gfx_bits,y
        inx
        inx
        inx
        inx
        iny
        cpy #8
        bne -
        lda #3
        sta gfx_pen
        jsr gfx_glyph
        bcs gm_icon_done
        inc gm_j
        lda gm_j
        cmp #8
        bne --
        ldx gm_i                ; colours: selected icons inverted
        lda gm_desk_color
        cpx gm_icon_sel
        bne +
        lda #GM_ICON_SELECTED
+       sta gfx_color
        lda #34
        sta gfx_x0
        lda #38
        sta gfx_x1
        lda gm_row
        sta gfx_y0
        clc
        adc #2
        sta gfx_y1
        jsr gm_cells_hi0
        jsr gfx_colors
        bcs gm_icon_done
        ldx gm_i                ; label, centred under the 32-pixel icon
        lda gm_icon_label_lo,x
        sta gm_copy+1
        lda gm_icon_label_hi,x
        sta gm_copy+2
        ldy #0
gm_copy:
        lda $ffff,y
        beq +
        sta gfx_text_buffer,y
        iny
        bne gm_copy
+       sty gfx_text_length
        tya                     ; x = 34*8 + (32 - len*8)/2 = 288 - len*4
        asl
        asl
        sta gm_math
        sec
        lda #<288
        sbc gm_math
        sta gfx_x0
        lda #>288
        sbc #0
        sta gfx_x0+1
        lda gm_row
        clc
        adc #2
        jsr gm_times8
        sta gfx_y0
        stx gfx_y0+1
        lda #0                  ; clear the label row first
        sta gfx_pen
        jsr gm_label_clear
        bcs gm_icon_done
        lda #1
        sta gfx_pen
        jsr gfx_text
gm_icon_done:
        rts
gm_label_clear:
        lda gfx_x0              ; keep the text origin
        pha
        lda gfx_x0+1
        pha
        lda gfx_y0
        pha
        lda #<(31*8)
        sta gfx_x0
        lda #>(31*8)
        sta gfx_x0+1
        lda #<320
        sta gfx_x1
        lda #>320
        sta gfx_x1+1
        pla
        sta gfx_y0
        pha
        clc
        adc #8
        sta gfx_y1
        lda #0
        sta gfx_y1+1
        jsr gfx_rect
        pla
        sta gfx_y0
        pla
        sta gfx_x0+1
        pla
        sta gfx_x0
        rts
; Icon under cell (gm_cx, gm_cy): X = icon or $ff.
gm_icon_hit:
        ldx #$ff
        lda gm_cx
        cmp #31
        bcc ++
        ldx #GM_ICONS-1
-       lda gm_icon_on,x
        beq gm_hit_next
        lda gm_cy
        sec
        sbc gm_icon_y,x
        cmp #3
        bcc +
gm_hit_next:
        dex
        bpl -
+       rts
+       ldx #$ff
        rts

; ---- clicks and keys ---------------------------------------------------------------
gm_click:
        lda #0
        sta gm_drag
        jsr gm_click_at
        jmp gm_release
gm_pointer_cell:
        lda ae_ev_result+3      ; pointer cell
        lsr
        lda ae_ev_result+2
        ror
        lsr
        lsr
        sta gm_cx
        lda ae_ev_result+4
        lsr
        lsr
        lsr
        sta gm_cy
        rts
gm_click_at:
        jsr gm_pointer_cell
        lda #WS_FIND
        sta N_BUFFER
        lda gm_cx
        sta N_BUFFER+1
        lda gm_cy
        sta N_BUFFER+2
        jsr gm_wcall
        bcs gm_click_done
        ldx N_BUFFER
        beq gm_click_desktop
        jsr gm_slot_of          ; a click in the top window's work area
        bcs gm_click_done
        stx gm_slot
        jsr gm_row_under
        bcs gm_band
        jsr gm_select_entry
        lda ae_ev_result+6
        cmp #2
        bcs +
        inc gm_drag             ; a single press on a row may drag it
        rts
+       jmp gm_open_entry
gm_click_desktop:
        jsr gm_icon_hit
        cpx #$ff
        beq gm_deselect_icon
        cpx gm_icon_sel
        beq +
        stx gm_new_icon
        jsr gm_repaint_icon_sel
+       lda ae_ev_result+6
        cmp #2
        bcs +
        lda gm_icon_sel         ; a single press on a drive icon may drag it
        cmp #2
        bcs gm_click_done
        lda #2
        sta gm_drag
        rts
+       jmp gm_open_icon
gm_deselect_icon:
        lda #$ff
        sta gm_new_icon
        jmp gm_repaint_icon_sel
gm_click_done:
        rts
; Repaint the old and new selected icons (the desktop stays uncovered there
; unless a window covers it: redraw through the desktop's visible rectangles).
gm_repaint_icon_sel:
        lda gm_icon_sel
        pha
        lda gm_new_icon
        sta gm_icon_sel
        pla
        jsr gm_redraw_icon_cells
        lda gm_icon_sel
gm_redraw_icon_cells:
        cmp #$ff
        beq +
        tax
        lda #31
        sta ae_ev_result+11
        lda gm_icon_y,x
        sta ae_ev_result+12
        lda #9
        sta ae_ev_result+13
        lda #3
        sta ae_ev_result+14
        jmp gm_redraw_desktop
+       rts

gm_key:
        lda gm_confirm          ; Control Panel: a click for every key
        and #GM_KEYCLICK
        beq +
        jsr sd_click
+       lda ae_ev_result+1
        cmp #13
        bne +
        jmp gm_open_selection
+       cmp #1                  ; Ctrl-A: select all
        bne +
        jmp gm_select_all
+       cmp #$38                ; 8 or 9: select that drive's icon and open it
        beq gm_key_drive
        cmp #$39
        beq gm_key_drive
        cmp #$11                ; cursor down / up in the top window
        beq gm_key_move
        cmp #$91
        beq gm_key_move
        cmp #$84                ; HELP: Print Screen (TOS's Alt-Help)
        beq gm_print_screen
        rts
gm_key_move:
        sta gm_math
        jsr gm_top_slot
        bcs gm_key_done
        stx gm_slot
        ldy gm_win_sel,x
        lda gm_math
        cmp #$11
        bne +
        iny
        tya
        cmp gm_win_count,x
        bcs gm_key_done
        bcc gm_key_set
+       cpy #$ff
        beq gm_key_done
        dey
        bmi gm_key_done
gm_key_set:
        tya
        jsr gm_select_index
        jmp gm_scroll_to_selection
gm_key_done:
        rts
gm_key_drive:
        and #15
        ldx #0                  ; the boot drive's icon
        cmp N_BOOTDEVICE
        beq +
        ldx #1                  ; drive 9's icon
        cmp #9
        bne gm_key_done
+       cpx gm_icon_sel
        beq +
        stx gm_new_icon
        jsr gm_repaint_icon_sel
+       jmp gm_open_icon

; ---- menu ------------------------------------------------------------------------------
gm_menu_choice:
        lda ae_ev_result+10     ; title
        bne +
        lda ae_ev_result+11     ; Desk: About, or the Control Panel
        bne gm_menu_control
        lda #<gm_about
        ldx #>gm_about
        ldy #1
        jmp gm_alert
gm_menu_control:
        lda #GM_MOP_CONTROL
        jmp gm_module_run
+       cmp #1
        bne gm_menu_options
        lda ae_ev_result+11
        beq gm_open_selection   ; File: Open
        cmp #1
        bne +
        jmp gm_show_info
+       cmp #3
        bne +
        jmp gm_delete
+       cmp #4
        bne +
        lda #GM_MOP_FORMAT
        jmp gm_module_run
+       cmp #5
        bne +
        lda #GM_MOP_NEWFOLDER
        jmp gm_module_run
+       cmp #7
        bne +
        jsr gm_top_slot         ; File: Close
        bcs +
        stx gm_slot
        jmp gm_close_slot
+       rts
gm_menu_options:
        cmp #2
        bne +
        jmp gm_menu_view
+       lda ae_ev_result+11
        bne +
        lda #GM_MOP_PREFS
        jmp gm_module_run
+       cmp #1
        bne +
        lda #GM_MOP_SAVEDESK
        jmp gm_module_run
+       cmp #2
        bne +
gm_print_screen:
        lda #GM_MOP_PRTSCR
        jmp gm_module_run
+       cmp #3
        bne +
        jmp gm_launcher_leave
+       rts
; Open the selected entry of the top window, else the selected icon.
gm_open_selection:
        jsr gm_top_slot
        bcs +
        stx gm_slot
        lda gm_win_sel,x
        cmp #$ff
        beq +
        jmp gm_open_entry
+       lda gm_icon_sel
        cmp #$ff
        beq +
        jmp gm_open_icon
+       rts

; ---- windows: open a drive ----------------------------------------------------------
gm_open_icon:
        ldx gm_icon_sel
        cpx #GM_PRINTER         ; Printer: files are dropped on it
        beq gm_open_none
        cpx #2                  ; Trash opens nothing (no deleted files kept)
        bne +
gm_open_none:
        rts
+       jsr gm_icon_drive
gm_open_drive:
        ldx #0                  ; a free slot
-       lda gm_win_handle,x
        beq +
        inx
        cpx #GM_WINDOWS
        bne -
        lda gm_restoring        ; restoring: quietly open nothing
        bne gm_open_quiet
        lda #<gm_full_alert
        ldx #>gm_full_alert
        ldy #1
        jmp gm_alert
+       stx gm_slot
        lda gm_fmt              ; a new USB window starts at the root
        cmp #3
        bne +
        jsr gm_path_root
+       jsr gm_scan
        bcc +
        ldx gm_restoring
        bne gm_open_quiet
        jsr gm_hex_error
        lda #<gm_drive_alert
        ldx #>gm_drive_alert
        ldy #1
        jmp gm_alert
+       lda #WS_CREATE
        sta N_BUFFER
        lda #<(WK_NAME|WK_CLOSER|WK_FULLER|WK_MOVER|WK_SIZER|WK_UPARROW|WK_DNARROW)
        sta N_BUFFER+2
        lda #>WK_VSLIDE
        sta N_BUFFER+3
        lda #0                  ; full: columns 0..30, rows 1..24
        sta N_BUFFER+4
        lda #1
        sta N_BUFFER+5
        lda #31
        sta N_BUFFER+6
        lda #24
        sta N_BUFFER+7
        jsr gm_wcall
        bcs gm_open_fail
        ldx gm_slot
        lda N_BUFFER
        sta gm_win_handle,x
        lda gm_dev
        sta gm_win_dev,x
        lda gm_fmt
        sta gm_win_fmt,x
        lda #0
        sta gm_win_top,x
        lda #$ff
        jsr gm_select_set
        jsr gm_set_title
        lda #WS_OPEN            ; staggered by slot
        sta N_BUFFER
        ldx gm_slot
        lda gm_win_handle,x
        sta N_BUFFER+1
        txa
        clc
        adc #1
        sta N_BUFFER+2
        adc #1
        sta N_BUFFER+3
        lda #28
        sta N_BUFFER+4
        lda #16
        sta N_BUFFER+5
        lda gm_restoring        ; restoring: the saved rectangle
        beq +
        ldx #3
-       lda gm_orect,x
        sta N_BUFFER+2,x
        dex
        bpl -
+       jsr gm_wcall
        bcs gm_open_fail
        jmp gm_update_slider    ; from the opened work area, not the full one
gm_open_fail:
        ldx gm_slot
        jmp gm_free_slot
gm_open_quiet:
        rts

; X = drive icon -> gm_dev, gm_fmt (3: Ultimate DOS)
gm_icon_drive:
        lda gm_icon_dev_lo,x
        bne +
        lda N_BOOTDEVICE        ; icon 0: the boot drive in its format
        sta gm_dev
        lda N_BOOTFORMAT
        sta gm_fmt
        rts
+       sta gm_dev
        lda #3                  ; USB: Ultimate DOS context 1
        cpx #GM_USB
        beq +
        jsr gm_drive_format     ; icon 1: device 9 in the geometry its DOS names
+       sta gm_fmt
        rts
; A = gm_dev's geometry (0 D64, 1 D71, 2 D81), from the drive's identity:
; "UI" resets its DOS, which answers 73 with its ROM's name ("CBM DOS V2.6
; 1541", "CBM DOS V3.0 1571", "COPYRIGHT CBM DOS V10 1581"). Known once per
; run; a drive that answers with another name is read as a D64. A drive that
; does not answer is read as a D64 and asked again next time; the listing
; then reports its error.
gm_drive_format:
        lda gm_dev_format
        bpl gm_df_done
        lda gm_dev
        sta dc_device
        lda #$55                ; "UI"
        sta dc_text
        lda #$49
        sta dc_text+1
        lda #2
        sta dc_length
        jsr dc_command
        bcs gm_df_none
        cmp #73
        bne gm_df_none
        ldy #0                  ; answered: D64 unless the name says otherwise
        ldx dc_status_length
        cpx #4
        bcc gm_df_found
        dex                     ; X = the last start of "15?1"
        dex
        dex
        dex
gm_df_scan:
        lda dc_status,x
        cmp #$31
        bne gm_df_next
        lda dc_status+1,x
        cmp #$35
        bne gm_df_next
        lda dc_status+3,x
        cmp #$31
        bne gm_df_next
        lda dc_status+2,x
        ldy #2
        cmp #$38                ; 1581
        beq gm_df_found
        dey
        cmp #$37                ; 1571
        beq gm_df_found
        dey                     ; 1541 or another model: D64
        beq gm_df_found
gm_df_next:
        dex
        bpl gm_df_scan
gm_df_found:
        sty gm_dev_format
        tya
gm_df_done:
        rts
gm_df_none:
        lda #0
        rts
; Snapshot the directory of gm_dev/gm_fmt into a new owner-32 allocation.
gm_scan:
        lda N_CURRENT
        sta N_OWNER
        lda #GM_PAGES
        sta N_PAGES
        lda #$ff
        sta N_BANK
        jsr N_ALLOC
        bcs gm_scan_done
        ldx gm_slot
        lda N_HANDLE
        sta gm_mem0,x
        lda N_HANDLE+1
        sta gm_mem1,x
        lda N_HANDLE+2
        sta gm_mem2,x
        lda N_HANDLE+3
        sta gm_mem3,x
        lda #0
        sta gm_count
        sta gm_page
        lda gm_fmt
        cmp #3
        bne gm_scan_page
        jmp gm_scan_ult
gm_scan_page:
        lda N_CURRENT
        sta N_FOWNER
        lda gm_dev
        sta N_FDEVICE
        lda gm_fmt
        sta N_FFORMAT
        lda gm_page
        sta N_DPAGE
        jsr N_DIRPAGE
        bcs gm_scan_fail
        lda N_DNEXT
        sta gm_page
        lda N_DCOUNT
        beq gm_scan_end
        ldx #0                  ; keep the page before N_BUFFER is reused
-       lda N_BUFFER,x
        sta gm_dirpage,x
        inx
        bne -
        ldx #0
gm_scan_record:
        lda gm_dirpage,x
        beq gm_scan_skip
        ldy gm_count
        cpy #GM_MAX_ENTRIES
        bcs gm_scan_skip
        jsr gm_rec_addr        ; gm_sortbuf record gm_count
        sta gm_rec_dst+2
        lda gm_ra
        sta gm_rec_dst+1
        stx gm_math
        ldy #0
-       lda gm_dirpage+2,x      ; name
        jsr gm_rec_put
        inx
        cpy #16
        bne -
        ldx gm_math
        lda gm_dirpage,x        ; type, flags, blocks, directory ordinal
        jsr gm_rec_put
        lda gm_dirpage+1,x
        jsr gm_rec_put
        lda gm_dirpage+18,x
        jsr gm_rec_put
        lda gm_dirpage+19,x
        jsr gm_rec_put
        lda gm_count
        jsr gm_rec_put
        inc gm_count
gm_scan_skip:
        txa
        clc
        adc #32
        tax
        bne gm_scan_record
        lda gm_page
        cmp #$ff
        bne gm_scan_page
gm_scan_end:
        ldx gm_slot
        lda gm_count
        sta gm_win_count,x
        jsr gm_sort_write
        bcs gm_scan_fail
gm_scan_done:
        rts
gm_scan_fail:
        pha
        ldx gm_slot
        jsr gm_free_mem
        pla
        sec
        rts

; ---- View: sorting a snapshot --------------------------------------------------------
; Order gm_count records of gm_sortbuf by gm_view and write them to the slot's
; allocation. Carry set on a heap error.
gm_sort_write:
        ldx #0
-       cpx gm_count
        beq +
        txa
        sta gm_order,x
        inx
        bne -
+       jsr gm_sort
        lda #0
        sta gm_k
gm_write_chunk:
        lda gm_count
        sec
        sbc gm_k                ; records left
        bne +
        clc
        rts
+       jsr gm_chunk_size
        lda #<N_BUFFER
        sta gm_rec_dst+1
        lda #>N_BUFFER
        sta gm_rec_dst+2
        lda #0
        sta gm_j
-       lda gm_k
        clc
        adc gm_j
        tax
        ldy gm_order,x
        jsr gm_rec_addr
        sta gm_rec_src2+2
        lda gm_ra
        sta gm_rec_src2+1
        jsr gm_copy_rec
        inc gm_j
        lda gm_j
        cmp gm_m
        bne -
        jsr gm_chunk_heap
        jsr N_WRITE
        bcs gm_chunk_fail
        jsr gm_chunk_next
        jmp gm_write_chunk
gm_chunk_fail:
        rts
; Reload the slot's snapshot into gm_sortbuf, then sort and write it back.
gm_resort_slot:
        ldx gm_slot
        lda gm_win_count,x
        sta gm_count
        lda #$ff
        jsr gm_select_set
        lda #0
        sta gm_k
gm_load_chunk:
        lda gm_count
        sec
        sbc gm_k
        beq gm_sort_write
        jsr gm_chunk_size
        jsr gm_chunk_heap
        jsr N_READ
        bcs gm_chunk_fail
        lda #<N_BUFFER
        sta gm_rec_src2+1
        lda #>N_BUFFER
        sta gm_rec_src2+2
        lda #0
        sta gm_j
-       lda gm_k
        clc
        adc gm_j
        tay
        jsr gm_rec_addr
        sta gm_rec_dst+2
        lda gm_ra
        sta gm_rec_dst+1
        jsr gm_copy_rec
        inc gm_j
        lda gm_j
        cmp gm_m
        bne -
        jsr gm_chunk_next
        jmp gm_load_chunk
gm_chunk_size:                  ; A records left -> gm_m, at most GM_CHUNK
        cmp #GM_CHUNK
        bcc +
        lda #GM_CHUNK
+       sta gm_m
        rts
gm_chunk_heap:                  ; the slot's records gm_k..gm_k+gm_m-1
        jsr gm_select_mem
        lda gm_k
        jsr gm_mulrec
        sta N_OFFSET
        stx N_OFFSET+1
        lda gm_m
        jsr gm_mulrec
        sta N_COUNT
        stx N_COUNT+1
        rts
gm_chunk_next:
        lda gm_k
        clc
        adc gm_m
        sta gm_k
        rts
; Copy one record from gm_rec_src2 to gm_rec_dst; advance both addresses.
gm_copy_rec:
        ldy #0
gm_rec_src2:
        lda $ffff,y
        jsr gm_rec_put
        cpy #GM_RECORD
        bne gm_rec_src2
        lda gm_rec_src2+1
        clc
        adc #GM_RECORD
        sta gm_rec_src2+1
        bcc +
        inc gm_rec_src2+2
+       lda gm_rec_dst+1
        clc
        adc #GM_RECORD
        sta gm_rec_dst+1
        bcc +
        inc gm_rec_dst+2
+       rts
gm_rec_put:
gm_rec_dst:
        sta $ffff,y
        iny
        rts
; Shell sort of gm_order[0..gm_count) with gm_compare.
gm_sort:
        ldx #GM_GAP_COUNT-1
gm_gap_loop:
        stx gm_gapi
        lda gm_gaps,x
        sta gm_gap
        cmp gm_count
        bcs gm_next_gap
        sta gm_i2
gm_ins_outer:
        ldx gm_i2
        lda gm_order,x
        sta gm_ins_val
        stx gm_pos
gm_ins_inner:
        lda gm_pos
        sec
        sbc gm_gap
        bcc gm_ins_place
        tax
        lda gm_order,x
        sta gm_other
        jsr gm_compare
        bcc gm_ins_place
        ldx gm_pos
        lda gm_other
        sta gm_order,x
        lda gm_pos
        sec
        sbc gm_gap
        sta gm_pos
        jmp gm_ins_inner
gm_ins_place:
        ldx gm_pos
        lda gm_ins_val
        sta gm_order,x
        inc gm_i2
        lda gm_i2
        cmp gm_count
        bcc gm_ins_outer
gm_next_gap:
        ldx gm_gapi
        dex
        bpl gm_gap_loop
        rts
; Carry set when record gm_other sorts after record gm_ins_val. Name order maps
; the $a0 padding below every character; size puts larger files first; the
; directory ordinal breaks ties, and alone is "Unsorted".
gm_compare:
        ldy gm_other
        jsr gm_rec_addr
        sta gm_fa+2
        lda gm_ra
        sta gm_fa+1
        ldy gm_ins_val
        jsr gm_rec_addr
        sta gm_fb+2
        lda gm_ra
        sta gm_fb+1
        ldx gm_view
        cpx #3
        beq gm_cmp_ordinal
        cpx #1
        bne +
        ldy #16                 ; type
        jsr gm_cmp_raw
        bne gm_cmp_out
+       cpx #2
        bne gm_cmp_name
        ldy #19                 ; blocks, larger first
        jsr gm_cmp_rev
        bne gm_cmp_out
        ldy #18
        jsr gm_cmp_rev
        bne gm_cmp_out
gm_cmp_name:
        ldy #0
-       jsr gm_fb
        jsr gm_name_key
        sta gm_cmpb
        jsr gm_fa
        jsr gm_name_key
        cmp gm_cmpb
        bne gm_cmp_out
        iny
        cpy #16
        bne -
gm_cmp_ordinal:
        ldy #20
        jsr gm_cmp_raw
gm_cmp_out:
        bne +
        clc
+       rts
gm_cmp_raw:
        jsr gm_fb
        sta gm_cmpb
        jsr gm_fa
        cmp gm_cmpb
        rts
gm_cmp_rev:
        jsr gm_fa
        sta gm_cmpb
        jsr gm_fb
        cmp gm_cmpb
        rts
gm_fa:
        lda $ffff,y
        rts
gm_fb:
        lda $ffff,y
        rts
gm_name_key:
        cmp #$a0
        bne +
        lda #0
        rts
+       and #$7f
        rts
; View menu: sort every open window again.
gm_menu_view:
        lda ae_ev_result+11
gm_set_view:                    ; A = 0 name, 1 type, 2 size, 3 unsorted
        cmp gm_view
        beq gm_view_done
        sta gm_view
        jsr gm_view_checks
        lda #GM_WINDOWS-1
        sta gm_vslot
-       ldx gm_vslot
        lda gm_win_handle,x
        beq +
        stx gm_slot
        jsr gm_resort_slot
        bcs gm_view_fail
        jsr gm_repaint_all
+       dec gm_vslot
        bpl -
gm_view_done:
        rts
gm_view_fail:
        jsr gm_hex_error
        lda #<gm_drive_alert
        ldx #>gm_drive_alert
        ldy #1
        jmp gm_alert
; Check the current View item, clear the others.
gm_view_checks:
        lda #3
        sta gm_vslot
-       ldy #0
        lda gm_vslot
        cmp gm_view
        bne +
        iny
+       tax
        lda #2
        jsr ae_menu_set
        bcs +
        dec gm_vslot
        bpl -
        clc
+       rts

; ---- Show Info ------------------------------------------------------------------------
; The selected entry of the top window, else the selected drive icon.
gm_show_info:
        lda #0
        sta gm_alen
        lda #<gm_s_head
        ldx #>gm_s_head
        jsr gm_astr
        jsr gm_top_slot
        bcs gm_info_icon
        stx gm_slot
        lda gm_win_sel,x
        cmp #$ff
        beq gm_info_icon
        lda gm_win_fmt,x        ; USB: FILE_STAT in an alert; rename is IEC only
        cmp #3
        bne +
        lda #GM_MOP_USBINFO
        jmp gm_module_run
+       jsr gm_read_record
        bcs gm_info_fail
        lda #0
        sta gm_lock_want
        lda #GM_MOP_INFO
        jsr gm_module_run
        lda gm_lock_want        ; Read-only changed: GDDSK sets the lock
        bpl +
        lda #GM_MOP_LOCK
        jmp gm_module_run
+       rts
; Append gm_rec's name, up to its padding, as printable alert text.
gm_aname:
        ldy #0
gm_info_name:
        lda gm_rec,y
        cmp #$a0
        beq gm_aname_done       ; the padding ends the name
        jsr gm_printable
        jsr gm_aput
        iny
        cpy #16
        bne gm_info_name
gm_aname_done:
        rts
; Append "Type: TYP  Blocks: N" for gm_rec.
gm_atype:
        lda #<(gm_s_type+1)
        ldx #>(gm_s_type+1)
        jsr gm_astr
        lda gm_rec+16
        and #7
        cmp #7
        bcc +
        lda #0
+       sta gm_math
        asl
        adc gm_math
        tay
        ldx #3
-       lda gm_types,y
        stx gm_math
        jsr gm_aput
        ldx gm_math
        iny
        dex
        bne -
        lda #<gm_s_blocks
        ldx #>gm_s_blocks
        jsr gm_astr
        lda gm_rec+18
        sta gm_num
        lda gm_rec+19
        sta gm_num+1
        jmp gm_anum
gm_info_end:
        lda #<gm_s_ok
        ldx #>gm_s_ok
        jsr gm_astr
        lda #0
        jsr gm_aput
        lda #<gm_abuf
        ldx #>gm_abuf
        ldy #1
        jmp gm_alert
gm_info_fail:
        jmp gm_view_fail
; A drive icon: its file count and blocks used, from the directory pages.
gm_info_icon:
        ldx gm_icon_sel
        cpx #GM_USB
        bne +
        jmp gm_not_usb
+       cpx #2                  ; (and the Printer: nothing to show)
        bcc +
        rts                     ; nothing selected, or Trash
+       jsr gm_icon_drive
        lda #<gm_drive_title
        ldx #>gm_drive_title
        jsr gm_astr
        lda gm_dev
        sta gm_num
        lda #0
        sta gm_num+1
        jsr gm_anum
        lda #0
        sta gm_count
        sta gm_page
        sta gm_total
        sta gm_total+1
gm_info_page:
        lda N_CURRENT
        sta N_FOWNER
        lda gm_dev
        sta N_FDEVICE
        lda gm_fmt
        sta N_FFORMAT
        lda gm_page
        sta N_DPAGE
        jsr N_DIRPAGE
        bcs gm_info_fail
        lda N_DNEXT
        sta gm_page
        lda N_DCOUNT
        beq gm_info_sum
        ldx #0
-       lda N_BUFFER,x
        beq +
        inc gm_count
        lda gm_total
        clc
        adc N_BUFFER+18,x
        sta gm_total
        lda gm_total+1
        adc N_BUFFER+19,x
        sta gm_total+1
+       txa
        clc
        adc #32
        tax
        bne -
        lda gm_page
        cmp #$ff
        bne gm_info_page
gm_info_sum:
        lda #<gm_s_files
        ldx #>gm_s_files
        jsr gm_astr
        lda gm_count
        sta gm_num
        lda #0
        sta gm_num+1
        jsr gm_anum
        lda #<gm_s_used
        ldx #>gm_s_used
        jsr gm_astr
        lda gm_total
        sta gm_num
        lda gm_total+1
        sta gm_num+1
        jsr gm_anum
        lda gm_dev              ; free space, as the drive's listing says it
        sta dc_device
        jsr dc_blocks_free
        bcs +
        lda #<gm_s_free
        ldx #>gm_s_free
        jsr gm_astr
        lda dc_free
        sta gm_num
        lda dc_free+1
        sta gm_num+1
        jsr gm_anum
+       jmp gm_info_end
; Alert text builder: gm_abuf/gm_alen.
gm_astr:                        ; append the zero-terminated string at A/X
        sta gm_astr_src+1
        stx gm_astr_src+2
        ldy #0
gm_astr_src:
        lda $ffff,y
        beq +
        jsr gm_aput
        iny
        bne gm_astr_src
+       rts
gm_aput:                        ; keeps Y
        ldx gm_alen
        sta gm_abuf,x
        inc gm_alen
        rts
gm_anum:                        ; append gm_num (0..9999) in decimal
        ldy #3
        jsr gm_decimal4
        ldy #0
-       lda gfx_text_buffer,y
        cmp #32
        beq +
        jsr gm_aput
+       iny
        cpy #4
        bne -
        rts

; ---- Delete and Trash --------------------------------------------------------------
; The selected entry of gm_slot -> gm_rec. Carry set on a heap error.
gm_read_record:
        ldx gm_slot
        lda gm_win_sel,x
        jsr gm_mulrec
        sta N_OFFSET
        stx N_OFFSET+1
        lda #GM_RECORD
        sta N_COUNT
        lda #0
        sta N_COUNT+1
        jsr gm_select_mem
        jsr N_READ
        bcs +
        ldx #GM_RECORD-1
-       lda N_BUFFER,x
        sta gm_rec,x
        dex
        bpl -
        clc
+       rts
; File:Delete (Ctrl-D), or an entry dropped on Trash: confirm, scratch it on
; the drive, check the drive's count, and list the drive's windows again.
gm_delete:
        jsr gm_top_slot
        bcs gm_del_none
        stx gm_slot
gm_delete_slot:                 ; X = gm_slot
        lda gm_nsel,x
        cmp #2
        bcs gm_del_many
gm_delete_one:                  ; gm_slot's gm_win_sel (GDCPY's Move, gm_each)
        ldx gm_slot
        lda gm_win_sel,x
        cmp #$ff
        beq gm_del_none
        jsr gm_read_record
        bcc +
        jmp gm_view_fail
+       ldx gm_slot             ; USB: any name; the drive gets the full path
        lda gm_win_fmt,x
        cmp #3
        beq gm_del_ask
        ldx #0                  ; "S0:" and the exact name; no DOS pattern characters
gm_del_copy:
        lda gm_rec,x
        cmp #$a0
        beq gm_del_named
        ldy #gm_bad_chars_end-gm_bad_chars-1
-       cmp gm_bad_chars,y
        beq gm_del_badname
        dey
        bpl -
        sta dc_text+3,x
        inx
        cpx #16
        bne gm_del_copy
gm_del_named:
        txa
        beq gm_del_badname      ; an empty name
        clc
        adc #3
        sta dc_length
        lda #$53                ; S0:
        sta dc_text
        lda #$30
        sta dc_text+1
        lda #$3a
        sta dc_text+2
gm_del_ask:
        lda gm_confirm          ; Preferences may turn the question off (bit 0)
        lsr
        bcc gm_del_go
        lda #0                  ; "[2][Delete NAME?|This cannot be undone.][Delete|Cancel]"
        sta gm_alen
        lda #<gm_s_delete
        ldx #>gm_s_delete
        jsr gm_astr
        jsr gm_aname
        lda #<gm_s_undone
        ldx #>gm_s_undone
        jsr gm_astr
        lda #0
        jsr gm_aput
        lda #<gm_abuf
        ldx #>gm_abuf
        ldy #2                  ; Cancel is the default
        jsr gm_alert
        bcs gm_del_none
        lda N_BUFFER
        cmp #1
        bne gm_del_none
gm_del_go:
        ldx gm_slot
        lda gm_win_fmt,x
        cmp #3
        bne +
        jmp gm_ult_delete
+       lda gm_win_dev,x
        sta dc_device
        sta gm_dev
        lda gm_win_fmt,x
        sta gm_fmt
        jsr dc_command
        bcs gm_del_error
        cmp #1                  ; 01, FILES SCRATCHED, exactly one file
        bne gm_del_status
        lda dc_track
        cmp #1
        bne gm_del_status
        lda gm_batch            ; several: listed again once, at the end
        bne gm_del_none
        jmp gm_refresh_drive
gm_del_none:
        rts
; "[2][Delete N items?|This cannot be undone.][Delete|Cancel]", then each;
; a failure is reported and the next is tried.
gm_del_many:
        lda gm_confirm
        lsr
        bcc gm_del_all
        lda #0
        sta gm_alen
        lda #<gm_s_delete
        ldx #>gm_s_delete
        jsr gm_astr
        ldx gm_slot
        lda gm_nsel,x
        sta gm_num
        lda #0
        sta gm_num+1
        jsr gm_anum
        lda #<gm_s_items
        ldx #>gm_s_items
        jsr gm_astr
        lda #<gm_s_undone
        ldx #>gm_s_undone
        jsr gm_astr
        lda #0
        jsr gm_aput
        lda #<gm_abuf
        ldx #>gm_abuf
        ldy #2
        jsr gm_alert
        bcs gm_del_none
        lda N_BUFFER
        cmp #1
        bne gm_del_none
gm_del_all:
        lda gm_confirm
        pha
        lda #0
        sta gm_confirm
        inc gm_batch
        lda #<gm_delete_one
        ldx #>gm_delete_one
        jsr gm_each
        dec gm_batch
        pla
        sta gm_confirm
gm_relist_slot:                 ; gm_slot's drive, every window of it
        ldx gm_slot
        lda gm_win_fmt,x
        sta gm_fmt
        lda gm_win_dev,x
        sta gm_dev
        jmp gm_refresh_drive
gm_del_badname:
        lda #<gm_badname_alert
        ldx #>gm_badname_alert
        ldy #1
        jmp gm_alert
gm_del_error:                   ; "[3][Could not delete|NAME|error $xx][OK]"
        pha
        jsr gm_del_head
gm_error_hex:                   ; stacked A: "error $xx][OK]"
        lda #<gm_s_error
        ldx #>gm_s_error
        jsr gm_astr
        pla
        pha
        lsr
        lsr
        lsr
        lsr
        tax
        lda gm_hex_digits,x
        jsr gm_aput
        pla
        and #15
        tax
        lda gm_hex_digits,x
        jsr gm_aput
        jmp gm_info_end
gm_del_status:                  ; "[3][Could not delete|NAME|<drive status>][OK]"
        jsr gm_del_head
gm_status_text:
        ldy #0
gm_del_text:
        cpy dc_status_length
        beq gm_del_text_end
        cpy #30
        beq gm_del_text_end
        lda dc_status,y
        jsr gm_printable
        jsr gm_aput
        iny
        bne gm_del_text
gm_del_text_end:
        jmp gm_info_end
; A (PETSCII or ASCII) -> printable alert text: controls become spaces, and
; the alert syntax characters [ ] | and DEL become '?'.
gm_printable:
        and #$7f
        cmp #32
        bcs +
        lda #32
+       cmp #$5b
        beq +
        cmp #$5d
        beq +
        cmp #$7c
        beq +
        cmp #$7f
        bne ++
+       lda #$3f
+       rts
gm_del_head:
        lda #<gm_s_nodelete
        ldx #>gm_s_nodelete
gm_fail_head:                   ; A/X = "[3][Could not ...|", then the name and '|'
        pha
        lda #0
        sta gm_alen
        pla
        jsr gm_astr
        jsr gm_aname
        lda #<gm_s_bar
        ldx #>gm_s_bar
        jmp gm_astr
; List every window of gm_dev/gm_fmt again after the drive changed.
gm_refresh_drive:
        lda #GM_WINDOWS-1
        sta gm_vslot
gm_refresh_loop:
        ldx gm_vslot
        lda gm_win_handle,x
        beq gm_refresh_next
        lda gm_win_dev,x
        cmp gm_dev
        bne gm_refresh_next
        lda gm_win_fmt,x
        cmp gm_fmt
        bne gm_refresh_next
        stx gm_slot
        jsr gm_free_mem
        jsr gm_scan
        bcc +
        jsr gm_close_slot       ; the drive cannot be listed now
        jmp gm_refresh_next
+       lda #$ff
        jsr gm_select_set
        jsr gm_work
        jsr gm_max_top
        ldx gm_slot
        cmp gm_win_top,x
        bcs +
        sta gm_win_top,x
+       jsr gm_update_slider
        jsr gm_repaint_all
gm_refresh_next:
        dec gm_vslot
        bpl gm_refresh_loop
        rts
; After a press still held: wait for the release. A listing row dragged from
; the top window and dropped on Trash is deleted; dropped on another window or
; a drive icon, it is copied or moved there (GDCPY.PRG).
gm_release:
        lda ae_ev_result+5
        and #1
        beq gm_release_done
        lda #MU_BUTTON
        sta ae_ev_params
        lda #1
        sta ae_ev_params+1
        sta ae_ev_params+2
        lda #0
        sta ae_ev_params+3
        lda gm_drag
        bne gm_drag_track
        jsr ae_event
        jmp gm_release_done
; A dragged row: an outline follows the pointer (drawn, and erased by XOR,
; around each wait) until the release. An AES without the outline call
; refuses it; the drag still works.
gm_drag_track:
        jsr gm_pointer_cell
gm_drag_loop:
        jsr gm_drag_box
        jsr ae_present
        lda #MU_BUTTON|MU_M1    ; the release, or the pointer leaving its cell
        sta ae_ev_params
        lda #1
        sta ae_ev_params+4      ; rectangle 1 fires outside
        sta ae_ev_params+7
        sta ae_ev_params+8
        lda gm_cx
        sta ae_ev_params+5
        lda gm_cy
        sta ae_ev_params+6
        jsr ae_event
        php
        jsr gm_drag_box
        plp
        bcs gm_release_done
        jsr gm_pointer_cell
        lda ae_ev_result
        and #MU_BUTTON
        beq gm_drag_loop
        lda #WS_FIND
        sta N_BUFFER
        lda gm_cx
        sta N_BUFFER+1
        lda gm_cy
        sta N_BUFFER+2
        jsr gm_wcall
        bcs gm_release_done
        lda gm_drag
        lsr
        bcs gm_row_drop
        lda N_BUFFER            ; a drive icon: only onto the other drive's icon
        bne gm_release_done
        jsr gm_icon_hit
        cpx #2
        bcs gm_release_done
        cpx gm_icon_sel
        beq gm_release_done
        stx gm_target
        lda #GM_MOP_DISKCOPY
        jmp gm_module_run
gm_row_drop:
        lda N_BUFFER
        beq +
        ldx gm_slot
        cmp gm_win_handle,x
        bne gm_drop             ; another window: GDCPY copies or moves them there
        lda gm_win_sel,x        ; the same window: the pressed row alone
        jmp gm_select_index
+
        jsr gm_icon_hit
        cpx #2
        bne +
        jmp gm_delete
+       cpx #GM_PRINTER
        beq gm_drop_print
        inx
        beq gm_release_done
gm_drop:                        ; a drive icon, or a window
        lda #GM_MOP_COPY
        .byte $2c               ; (bit abs: skips the next lda)
gm_drop_print:                  ; the Printer icon: GDPRT prints them
        lda #GM_MOP_PRINT
        jmp gm_module_run
gm_release_done:
        rts
gm_drag_box:                    ; a 10x1-cell outline at the pointer
        lda #WS_OUTLINE
        sta N_BUFFER
        lda gm_cx
        cmp #30
        bcc +
        lda #30
+       sta N_BUFFER+1
        lda gm_cy
        sta N_BUFFER+2
        lda #10
        sta N_BUFFER+3
        lda #1
        sta N_BUFFER+4
        jmp gm_wcall

; ---- desktop persistence ------------------------------------------------------------
; The desktop record (64 bytes): "GDS",1; confirm; view; colour; 0; window
; count; then per window, bottom to top: device, format, x, y, w, h, top row,
; selection; at 60 and 61 the printer's device and secondary address. It goes to the AES session before a launch (restored when the
; desktop returns) and to DESKTOP.INF with Options:Save Desktop.
GM_RECORD_SIZE = 64
GM_REC_PRINTER = 60             ; the printer's device and secondary address (0: none saved)
gm_session_build:
        ldx #GM_RECORD_SIZE-1
        lda #0
-       sta gm_session,x
        dex
        bpl -
        ldx #3
-       lda gm_magic,x
        sta gm_session,x
        dex
        bpl -
        lda gm_confirm
        sta gm_session+4
        lda gm_view
        sta gm_session+5
        lda gm_desk_color
        sta gm_session+6
        lda $0a22               ; KERNAL RPTFLG: key repeat
        sta gm_session+7
        lda gm_dclick
        sta gm_session+8
        lda gm_prt_dev
        sta gm_session+GM_REC_PRINTER
        lda gm_prt_sa
        sta gm_session+GM_REC_PRINTER+1
        lda #GM_REC_WINDOWS
        sta gm_spos
        jsr gm_top_slot         ; the top window goes last, so it reopens on top
        bcc +
        ldx #$ff
+       stx gm_stop
        ldx #0
-       stx gm_sslot
        cpx gm_stop
        beq +
        jsr gm_session_window
+       ldx gm_sslot
        inx
        cpx #GM_WINDOWS
        bne -
        ldx gm_stop
        bmi gm_session_built
        stx gm_sslot
; Append slot gm_sslot (if open) to the record.
gm_session_window:
        ldx gm_sslot
        lda gm_win_handle,x
        beq gm_session_built
        lda gm_win_fmt,x        ; USB windows (paths) are not kept
        cmp #3
        beq gm_session_built
        lda #WS_GET
        sta N_BUFFER
        lda gm_win_handle,x
        sta N_BUFFER+1
        lda #WF_CURRXYWH
        sta N_BUFFER+2
        jsr gm_wcall
        bcs gm_session_built
        ldy gm_spos
        ldx gm_sslot
        lda gm_win_dev,x
        sta gm_session,y
        lda gm_win_fmt,x
        sta gm_session+1,y
        lda N_BUFFER
        sta gm_session+2,y
        lda N_BUFFER+1
        sta gm_session+3,y
        lda N_BUFFER+2
        sta gm_session+4,y
        lda N_BUFFER+3
        sta gm_session+5,y
        lda gm_win_top,x
        sta gm_session+6,y
        lda gm_win_sel,x
        sta gm_session+7,y
        tya
        clc
        adc #8
        sta gm_spos
        inc gm_session+GM_REC_COUNT
gm_session_built:
        rts
; Before leaving: keep the desktop in the AES for the return.
gm_session_save:
        jsr gm_session_build
        ldx #0
-       lda #0
        cpx #GM_RECORD_SIZE
        bcs +
        lda gm_session,x
+       sta N_BUFFER,x
        inx
        bne -
        jmp ae_session_write
; At start: the AES session, else DESKTOP.INF, else the defaults.
gm_restore_color:
        lda #WS_SET             ; the AES paints the desktop in this colour
        sta N_BUFFER
        lda #0
        sta N_BUFFER+1
        lda #WF_DESKCOLOR
        sta N_BUFFER+2
        lda gm_desk_color
        sta N_BUFFER+3
        jmp gm_wcall
gm_file_select:
        lda N_CURRENT
        sta N_FOWNER
        ldx #3
-       lda gm_file,x
        sta N_FHANDLE,x
        dex
        bpl -
        rts
; ---- the dialog modules (GDDLG.PRG, GDSET.PRG) ------------------------------------
; A = GM_MOP_*: run that dialog in the module window, loading its module from
; this program's folder when another one (or none) is there.
gm_module_run:
        sta gm_mop
        tax
        lda gm_mop_module-1,x   ; the module that runs it
        tax
        cpx gm_mloaded
        beq gm_module_call
        stx gm_mwanted
        lda #0
        sta gm_mloaded
        lda N_MSTATE
        beq +
        jsr N_MCLOSE
        bcs gm_module_fail
+       lda gm_mwanted          ; the file name
        asl
        asl
        asl
        clc
        adc gm_mwanted          ; *9
        tay
        ldx #0
-       lda gm_mod_names-9,y
        sta N_FNAME,x
        iny
        inx
        cpx #9
        bne -
        stx N_FNAMELEN
        jsr N_MLOAD
        bcs gm_module_fail
        ldx #2
-       lda N_MTOKEN,x
        sta gm_mtoken,x
        dex
        bpl -
        lda gm_mwanted
        sta gm_mloaded
gm_module_call:
        ldx #2
-       lda gm_mtoken,x
        sta N_MTOKEN,x
        dex
        bpl -
        jsr N_MCALL
        bcc +
        ldx N_MERROR            ; a gate error: load again next time
        beq +
        ldx #0
        stx gm_mloaded
        lda N_MERROR
        jmp gm_module_fail
+       rts
gm_module_fail:                 ; "[3][Could not load GDDLG.PRG.|error $xx][OK]"
        pha
        lda #0
        sta gm_alen
        lda #<gm_s_nomodule
        ldx #>gm_s_nomodule
        jsr gm_astr
        lda gm_mwanted          ; the module's name
        asl
        asl
        asl
        clc
        adc gm_mwanted
        tay
        lda #9                  ; (gm_aput uses X)
        sta gm_math4
-       lda gm_mod_names-9,y
        jsr gm_aput
        iny
        dec gm_math4
        bne -
        lda #<gm_s_nomodule2
        ldx #>gm_s_nomodule2
        jsr gm_astr
        jmp gm_error_hex

; ---- USB storage: the Ultimate's DOS through directory cursors -------------------
; (docs/NATIVE-ULTIMATE.md). A USB window keeps its absolute path in
; a heap page per slot (gm_path_page); records hold the first 16 name bytes and the
; entry's position, so a full name is read again from the cursor when needed.
gm_ult_probe:                   ; the USB icon only when DOS target 1 answers
        lda #1
        sta N_UARG
        lda #N_U_IDENTIFY
        sta N_UOP
        lda N_CURRENT
        sta N_FOWNER
        jsr N_UQUERY
        lda #0
        bcs +
        lda #1
+       sta gm_icon_on+GM_USB
; The Printer icon only when the printer's IEC device (4, or 5 from the
; Control Panel) answers a LISTEN (KERNAL OPEN with no name sends nothing;
; CHKOUT addresses the device). GDSES and GDSET call it again when the
; device changes.
gm_prt_probe:
        lda $9d
        pha
        lda #0
        sta $9d                 ; no KERNAL messages
        tax
        jsr $ff68               ; SETBNK
        lda #GM_PRT_LFN
        ldx gm_prt_dev
        ldy gm_prt_sa
        jsr $ffba               ; SETLFS
        lda #0
        jsr $ffbd               ; SETNAM: none
        jsr $ffc0               ; OPEN
        bcs gm_prt_quiet
        ldx #GM_PRT_LFN
        ldy #0
        jsr $ffc9               ; CHKOUT
        bcs +
        lda $90
        bmi +
        iny
+       sty gm_icon_on+GM_PRINTER
        jsr $ffcc               ; CLRCHN
        lda #GM_PRT_LFN
        jsr $ffc3               ; CLOSE
gm_prt_quiet:
        pla
        sta $9d
        rts
; gm_slot's path page -> the self-modified load and store below.
; The paths live in a 4-page heap block, a page per slot; gm_path holds the
; one in use. gm_path_page reads gm_slot's through N_BUFFER (which it
; replaces); gm_path_store writes gm_path back after gm_pw.
gm_path_page:
        jsr gm_path_io
        jsr N_READ
        ldy #0
-       lda N_BUFFER,y
        sta gm_path,y
        iny
        bne -
        rts
gm_path_store:
        ldy #0
-       lda gm_path,y
        sta N_BUFFER,y
        iny
        bne -
        jsr gm_path_io
        jmp N_WRITE
gm_path_io:
        lda N_CURRENT
        sta N_OWNER
        ldx #3
-       lda gm_paths,x
        sta N_HANDLE,x
        dex
        bpl -
        lda #0
        sta N_OFFSET
        sta N_COUNT
        lda gm_slot
        sta N_OFFSET+1
        lda #1
        sta N_COUNT+1
        rts
gm_pr:
        lda gm_path,y
        rts
gm_pw:
        sta gm_path,y
        rts
gm_path_root:                   ; gm_slot's path = "/"
        lda #$2f
        sta gm_path
        ldx gm_slot
        lda #1
        sta gm_win_plen,x
        jmp gm_path_store
gm_path_to_upath:               ; gm_slot's path -> N_UPATH, N_FNAMELEN
        jsr gm_path_page
        ldx gm_slot
        lda gm_win_plen,x
        sta N_FNAMELEN
        ldy #0
-       cpy N_FNAMELEN
        beq +
        jsr gm_pr
        sta N_UPATH,y
        iny
        bne -
+       rts
gm_upath_to_path:               ; N_UPATH, N_FNAMELEN -> gm_slot's path
        ldx gm_slot
        lda N_FNAMELEN
        sta gm_win_plen,x
        ldy #0
-       cpy N_FNAMELEN
        beq +
        lda N_UPATH,y
        jsr gm_pw
        iny
        bne -
+       jmp gm_path_store
; Open a directory cursor at gm_slot's path on DOS context gm_dev; the
; canonical path the service returns becomes the window's path.
gm_ult_open:
        jsr gm_path_to_upath
        lda N_CURRENT
        sta N_FOWNER
        lda gm_dev
        sta N_FDEVICE
        lda #3
        sta N_FFORMAT
        lda #2
        sta N_FMODE
        lda #0
        sta N_FTYPE
        ldx #3
-       sta N_FHANDLE,x
        dex
        bpl -
        jsr N_FOPEN
        bcs +
        ldx #3
-       lda N_FHANDLE,x
        sta gm_file,x
        dex
        bpl -
        jsr gm_upath_to_path
        clc
+       rts
gm_ult_read:                    ; one packet: attribute, then the name
        jsr gm_file_select
        lda #0
        sta N_FCOUNT
        lda #2
        sta N_FCOUNT+1
        jmp N_FREAD
; The listing (from gm_scan, after the allocation): records into gm_sortbuf.
gm_scan_ult:
        jsr gm_ult_open
        bcs gm_ult_scan_fail0
gm_ult_scan_next:
        jsr gm_ult_read
        bcs gm_ult_scan_fail
        lda N_FACTUAL
        ora N_FACTUAL+1
        beq gm_ult_scan_done
        ldy gm_count
        cpy #GM_MAX_ENTRIES
        bcs gm_ult_scan_done    ; the snapshot is full
        jsr gm_rec_addr
        sta gm_rec_dst+2
        lda gm_ra
        sta gm_rec_dst+1
        lda N_FACTUAL           ; name length 1..255
        sec
        sbc #1
        sta gm_nlen
        ldy #0
        ldx #0
-       lda #$a0                ; the first 16 bytes, padded like a CBM name
        cpx gm_nlen
        bcs +
        lda N_BUFFER+1,x
+       jsr gm_rec_put
        inx
        cpx #16
        bne -
        lda N_BUFFER            ; type 5 DIR or 6 file; the attribute as flags
        and #$10
        beq +
        lda #5
        bne ++
+       lda #6
+       jsr gm_rec_put
        lda N_BUFFER
        jsr gm_rec_put
        lda #0                  ; no size in a directory packet
        jsr gm_rec_put
        jsr gm_rec_put
        lda gm_count            ; the position in the cursor
        jsr gm_rec_put
        inc gm_count
        jmp gm_ult_scan_next
gm_ult_scan_done:
        jsr gm_close_file
        bcs gm_ult_scan_fail0
        jmp gm_scan_end
gm_ult_scan_fail:
        pha
        jsr gm_close_file
        pla
gm_ult_scan_fail0:
        jmp gm_scan_fail
; A = an entry's position in gm_slot's directory: N_UPATH/N_FNAMELEN = its
; full path, gm_ult_attr = its attribute. Carry set: A = error.
gm_ult_fullname:
        sta gm_target
        ldx gm_slot
        lda gm_win_dev,x
        sta gm_dev
        jsr gm_ult_open
        bcs gm_fn_done
        lda #0
        sta gm_k
gm_fn_next:
        jsr gm_ult_read
        bcs gm_fn_close
        lda N_FACTUAL
        ora N_FACTUAL+1
        beq gm_fn_missing
        lda gm_k
        cmp gm_target
        beq gm_fn_found
        inc gm_k
        jmp gm_fn_next
gm_fn_found:
        lda N_BUFFER
        sta gm_ult_attr
        lda N_FACTUAL
        sec
        sbc #1
        sta gm_nlen
        ldx #0
-       lda N_BUFFER+1,x
        sta gm_name,x
        inx
        cpx gm_nlen
        bne -
        jsr gm_close_file
        bcs gm_fn_done
        jsr gm_path_to_upath    ; the directory, then '/' if needed, then the name
        ldx N_FNAMELEN
        lda N_UPATH-1,x
        cmp #$2f
        beq +
        lda #$2f
        sta N_UPATH,x
        inx
        beq gm_fn_long
+       ldy #0
-       lda gm_name,y
        sta N_UPATH,x
        inx
        beq gm_fn_long
        iny
        cpy gm_nlen
        bne -
        stx N_FNAMELEN
        clc
        rts
gm_fn_long:
        lda #$23                ; the path would exceed 255 bytes
        sec
        rts
gm_fn_missing:                  ; the listing changed under the window
        lda #N_RANGE
gm_fn_close:
        pha
        jsr gm_close_file
        pla
        sec
gm_fn_done:
        rts
; Open the selected USB entry: a folder opens in the window, a file is
; handed to the dispatcher with its full path (it checks the program).
gm_ult_open_entry:
        jsr gm_read_record
        bcs gm_usb_error
        lda gm_rec+20
        jsr gm_ult_fullname
        bcs gm_usb_error
        lda gm_ult_attr
        and #$10
        bne gm_ult_enter
        jsr gm_ult_peek         ; the signature first, as Files: UPNT is Paint's,
        lda gm_doc_kind         ; USHT Sheet's
        cmp #2
        bcs gm_ult_document
        jsr gm_text_suffix      ; then .TXT or .SEQ: a text document
        bcs +
gm_ult_document:
        jmp gm_usb_document
+       lda N_FNAMELEN
        sta N_NAMELEN
        ldx gm_slot
        lda gm_win_dev,x
        sta N_DEVICE
        lda #3
        sta N_APPFORMAT
        jsr gm_session_save
        jsr gm_leave
        lda #0
        jmp N_REPLACE
gm_ult_enter:
        jsr gm_upath_to_path
; List gm_slot's (new) path again in the same window.
gm_ult_rescan:
        ldx gm_slot
        lda gm_win_dev,x
        sta gm_dev
        lda #3
        sta gm_fmt
        jsr gm_free_mem
        jsr gm_scan
        bcc +
        pha
        jsr gm_close_slot
        pla
        jmp gm_usb_error
+       ldx gm_slot
        lda #0
        sta gm_win_top,x
        lda #$ff
        jsr gm_select_set
        jsr gm_set_title
        jsr gm_update_slider
        jmp gm_repaint_all
; The close box: on a USB folder below the root, go up one level (as TOS).
gm_close_or_up:
        ldx gm_slot
        lda gm_win_fmt,x
        cmp #3
        bne gm_close_full
        lda gm_win_plen,x
        cmp #2
        bcc gm_close_full
        jsr gm_path_page
        ldx gm_slot
        ldy gm_win_plen,x
        dey                     ; the last byte; a trailing '/' is skipped
        jsr gm_pr
        cmp #$2f
        bne +
        dey
+
-       jsr gm_pr               ; back to the previous '/'
        cmp #$2f
        beq +
        dey
        bne -
+       iny                     ; keep that '/'
        tya
        ldx gm_slot
        sta gm_win_plen,x
        jmp gm_ult_rescan
gm_close_full:
        jmp gm_close_slot
; gm_slot's title: "Drive nn", or "USB " and the end of the path.
gm_set_title:
        ldx gm_slot             ; a USB path first: reading it uses N_BUFFER
        lda gm_win_fmt,x
        cmp #3
        bne +
        jsr gm_path_page
+       lda #WS_SET
        sta N_BUFFER
        ldx gm_slot
        lda gm_win_handle,x
        sta N_BUFFER+1
        lda #WF_NAME
        sta N_BUFFER+2
        lda gm_win_fmt,x
        cmp #3
        beq gm_title_usb
        ldy #0
-       lda gm_drive_title,y
        sta N_BUFFER+3,y
        iny
        cpy #6
        bne -
        ldx gm_slot
        lda gm_win_dev,x
        jsr gm_decimal2
        cpx #$30                ; one digit below 10
        bne +
        sta N_BUFFER+9
        lda #0
        sta N_BUFFER+10
        beq gm_title_set
+       sta N_BUFFER+10
        stx N_BUFFER+9
        lda #0
        sta N_BUFFER+11
gm_title_set:
        jmp gm_wcall
gm_title_usb:
        ldy #3
-       lda gm_usb_title,y
        sta N_BUFFER+3,y
        dey
        bpl -
        ldx gm_slot
        lda gm_win_plen,x
        sta gm_math
        sec                     ; the last 12 path bytes
        sbc #12
        bcs +
        lda #0
+       tay
        ldx #7
gm_title_char:
        cpy gm_math
        beq gm_title_end
        jsr gm_pr
        cmp #32
        bcc gm_title_q
        cmp #127
        bcc gm_title_ok
gm_title_q:
        lda #$3f                ; not printable
gm_title_ok:
        sta N_BUFFER,x
        inx
        iny
        bne gm_title_char
gm_title_end:
        lda #0
        sta N_BUFFER,x
        jmp gm_wcall
gm_not_usb:
        lda #<gm_s_notusb
        ldx #>gm_s_notusb
        ldy #1
        jmp gm_alert
gm_usb_error:                   ; "[3][Could not read USB|storage: error $xx][OK]"
        pha
        lsr
        lsr
        lsr
        lsr
        tax
        lda gm_hex_digits,x
        sta gm_s_usbhex
        pla
        and #15
        tax
        lda gm_hex_digits,x
        sta gm_s_usbhex+1
        lda #<gm_s_usbfail
        ldx #>gm_s_usbfail
        ldy #1
        jmp gm_alert
gm_ult_attr: .byte 0

; USB delete: DELETE_FILE with the entry's full path, then FILE_STAT; only
; DOS 82 FILE NOT FOUND with an empty reply proves the removal (as Files).
gm_ult_delete:
        lda gm_rec+20
        jsr gm_ult_fullname
        bcs gm_ult_del_error
        lda #$09                ; DELETE_FILE
        jsr gm_ucmd
        bcs gm_ult_del_error
        lda N_FACTUAL
        ora N_FACTUAL+1
        bne gm_ult_del_unknown
        lda #$08                ; FILE_STAT
        jsr gm_ucmd
        bcc gm_ult_del_unknown  ; still there
        lda N_FACTUAL
        ora N_FACTUAL+1
        ora N_FSTATUS
        bne gm_ult_del_unknown
        lda N_FDOS
        cmp #82
        bne gm_ult_del_unknown
        beq gm_ult_del_done
gm_ult_del_unknown:
        lda #<gm_s_unproven
        ldx #>gm_s_unproven
        ldy #1
        jsr gm_alert
gm_ult_del_done:
        lda gm_batch
        bne +
        jmp gm_ult_rescan
+       rts
gm_ult_del_error:
        jmp gm_del_error
; A = Ultimate DOS opcode: N_BUFFER = context, opcode, the path in N_UPATH
; (FILE_STAT adds a NUL: its firmware handler takes the body as a C string).
gm_ucmd:
        sta N_BUFFER+1
        ldx gm_slot
        lda gm_win_dev,x
        sta N_BUFFER
gm_ucmd_at:                     ; (N_BUFFER = another context, N_BUFFER+1 = the opcode)
        lda N_CURRENT
        sta N_FOWNER
        ldx #0
-       lda N_UPATH,x
        sta N_BUFFER+2,x
        inx
        cpx N_FNAMELEN
        bne -
        stx N_FCOUNT
        lda #0
        sta N_FCOUNT+1
        lda N_BUFFER+1
        cmp #$08
        bne +
        lda #0
        sta N_BUFFER+2,x
        inc N_FCOUNT
        bne +
        inc N_FCOUNT+1
+       jmp N_UCOMMAND

; ---- documents (docs/NATIVE-DOCUMENT-LAUNCH.md) ------------------------------------
; A text file opens in the Editor through the one-launch document contract;
; closing the Editor returns to "browse", this desktop, whose windows the AES
; session brings back.
gm_iec_document:                ; N_BUFFER = the record: IEC name and type
        ldx gm_slot
        lda gm_win_dev,x
        sta N_BROWSERDEV
        lda gm_win_fmt,x
        sta N_BROWSERFMT
        ldx #0
-       lda N_BUFFER,x
        cmp #$a0
        beq +
        sta N_BROWSERNAME,x
        inx
        cpx #16
        bne -
+       stx N_BROWSERNAME_LEN
        lda N_BUFFER+16         ; SEQ 1, PRG 2, USR 3 -> 0, 1, 2
        and #7
        sec
        sbc #1
        sta N_DOCTYPE
        sta N_FTYPE             ; a UPNT picture (Paint saves SEQ) goes to Paint
        lda N_BROWSERDEV
        sta N_FDEVICE
        lda N_BROWSERFMT
        sta N_FFORMAT
        ldx N_BROWSERNAME_LEN
        stx N_FNAMELEN
        dex
-       lda N_BROWSERNAME,x
        sta N_FNAME,x
        dex
        bpl -
        jsr gm_peek
        jmp gm_document_launch
gm_usb_document:                ; gm_name/gm_nlen = the leaf; the window's path
        ldx gm_slot
        lda gm_win_dev,x
        sta N_BROWSERDEV
        lda #3
        sta N_BROWSERFMT
        jsr gm_path_page
        ldx gm_slot
        lda gm_win_plen,x
        sta N_BROWSERLEN
        ldy #0
-       cpy N_BROWSERLEN
        beq +
        jsr gm_pr
        sta N_BROWSERPATH,y
        iny
        bne -
+       ldx #0
-       lda gm_name,x
        sta N_BROWSERNAME,x
        inx
        cpx gm_nlen
        bne -
        stx N_BROWSERNAME_LEN
        lda #0
        sta N_DOCTYPE
gm_document_launch:
        lda gm_doc_kind         ; 1 Editor text, 2 Paint picture, 3 Sheet workbook
        sta N_DOCKIND
        lda #0
        sta N_DOCRETURN         ; back to this desktop, not system Files
        lda #$80
        sta N_DOCREQUEST
        ldx #5                  ; "editor"
        ldy #5
        lda gm_doc_kind
        cmp #2
        bcc +
        ldx #4                  ; "paint"
        ldy #10
        cmp #3
        bcc +
        ldy #15                 ; "sheet"
+       inx
        stx N_NAMELEN
        dex
-       lda gm_editor_name,y
        sta N_APPNAME,x
        dey
        dex
        bpl -
        lda N_BOOTDEVICE        ; the app from the boot disk
        sta N_DEVICE
        lda N_BOOTFORMAT
        sta N_APPFORMAT
        jsr gm_session_save
        jsr gm_leave
        lda #0
        jmp N_REPLACE
; The USB file in N_UPATH/N_FNAMELEN (from gm_ult_fullname): gm_peek on it.
; The file service reads both and writes neither, so a program launch after
; it still has the full path.
gm_ult_peek:
        ldx gm_slot
        lda gm_win_dev,x
        sta N_FDEVICE
        lda #3
        sta N_FFORMAT
        lda #0
        sta N_FTYPE
        jmp gm_peek
; The file named for N_FOPEN (device, format, type, name): gm_doc_kind = 2
; when its first four bytes are "UPNT", 3 when they are "USHT", else 1. A file that cannot be opened
; or read counts as 1: the app or dispatcher that opens it next reports the
; error.
gm_peek:
        lda #1
        sta gm_doc_kind
        lda #N_APPOWNER
        sta N_FOWNER
        lda #0
        sta N_FMODE
        ldx #3
-       sta N_FHANDLE,x
        dex
        bpl -
        jsr N_FOPEN
        bcs gm_peek_done
        ldx #3
-       lda N_FHANDLE,x
        sta gm_file,x
        dex
        bpl -
        lda #4
        sta N_FCOUNT
        lda #0
        sta N_FCOUNT+1
        jsr gm_file_select
        jsr N_FREAD
        bcs gm_peek_close
        lda N_FACTUAL+1
        bne gm_peek_close
        lda N_FACTUAL
        cmp #4
        bne gm_peek_close
        ldx #3
-       lda N_BUFFER,x
        cmp gm_upnt,x
        bne gm_peek_sheet
        dex
        bpl -
        lda #2
        bne gm_peek_kind
gm_peek_sheet:
        ldx #3
-       lda N_BUFFER,x
        cmp gm_usht,x
        bne gm_peek_close
        dex
        bpl -
        lda #3
gm_peek_kind:
        sta gm_doc_kind
gm_peek_close:
        jsr gm_close_file
gm_peek_done:
        rts
; gm_name/gm_nlen: carry clear when it ends in .TXT or .SEQ (any case).
gm_text_suffix:
        lda gm_nlen
        cmp #5                  ; at least "X.TXT"
        bcc gm_suffix_no
        tax
        lda gm_name-4,x
        cmp #$2e
        bne gm_suffix_no
        lda gm_name-3,x         ; the three letters, upper-cased
        and #$df
        sta gm_suffix
        lda gm_name-2,x
        and #$df
        sta gm_suffix+1
        lda gm_name-1,x
        and #$df
        sta gm_suffix+2
        lda gm_suffix
        cmp #$54                ; TXT
        bne +
        lda gm_suffix+1
        cmp #$58
        bne gm_suffix_no
        lda gm_suffix+2
        cmp #$54
        bne gm_suffix_no
        clc
        rts
+       cmp #$53                ; SEQ
        bne gm_suffix_no
        lda gm_suffix+1
        cmp #$45
        bne gm_suffix_no
        lda gm_suffix+2
        cmp #$51
        bne gm_suffix_no
        clc
        rts
gm_suffix_no:
        sec
        rts

; ---- windows: painting ----------------------------------------------------------------
; Clear the work area inside gm_clip, then draw the visible rows clipped to
; each visible rectangle.
gm_paint_window:
        ldx gm_slot
        lda #WS_FILL
        sta N_BUFFER
        lda gm_win_handle,x
        sta N_BUFFER+1
        lda #0
        sta N_BUFFER+2
        lda #GM_PAPER
        sta N_BUFFER+3
        ldx #3
-       lda gm_clip,x
        sta N_BUFFER+4,x
        dex
        bpl -
        jsr gm_wcall
        bcs gm_paint_done
        jsr gm_work             ; gm_wx/wy/ww/wh
        bcs gm_paint_done
        jsr gm_read_rows        ; the visible records into gm_rows
        bcs gm_paint_done
        jsr gm_bind
        bcs gm_paint_done
        lda #WS_GET
        sta N_BUFFER
        ldx gm_slot
        lda gm_win_handle,x
        sta N_BUFFER+1
        lda #WF_FIRSTXYWH
        sta N_BUFFER+2
-       jsr gm_wcall
        bcs gm_paint_reset
        lda N_BUFFER+2
        beq gm_paint_reset
        jsr gm_clip_to_rect
        bcs +
        jsr gm_draw_rows
        bcs gm_paint_reset
+       lda #WS_GET
        sta N_BUFFER
        lda #WF_NEXTXYWH
        sta N_BUFFER+2
        jmp -
gm_paint_reset:
        php
        pha
        jsr gfx_clip_defaults
        pla
        plp
gm_paint_done:
        rts
; Rows of the work area (current clip): text, and the selected row's colour.
gm_draw_rows:
        lda #0
        sta gm_i
gm_row_loop:
        lda gm_i
        cmp gm_wh
        bcs gm_rows_done
        ldx gm_slot
        clc
        adc gm_win_top,x
        bcs gm_rows_done
        cmp gm_win_count,x
        bcs gm_rows_done
        sta gm_item
        jsr gm_format_row       ; gfx_text_buffer/length
        lda gm_wx
        jsr gm_times8
        sta gfx_x0
        stx gfx_x0+1
        lda gm_wy
        clc
        adc gm_i
        jsr gm_times8
        sta gfx_y0
        stx gfx_y0+1
        lda #1
        sta gfx_pen
        jsr gfx_text
        bcs gm_rows_fail
        lda gm_item
        jsr gm_bit
        and gm_win_bits,x
        beq +
        lda gm_wx               ; selected: inverted cells
        sta gfx_x0
        clc
        adc gm_ww
        sta gfx_x1
        lda gm_wy
        clc
        adc gm_i
        sta gfx_y0
        adc #1
        sta gfx_y1
        jsr gm_cells_hi0
        lda #GM_SELECTED
        sta gfx_color
        jsr gfx_colors
        bcs gm_rows_fail
+       inc gm_i
        jmp gm_row_loop
gm_rows_done:
        clc
gm_rows_fail:
        rts
; "NAME16 TYP BLKS" for entry gm_item from gm_rows.
gm_format_row:
        lda gm_item            ; copy the 20-byte record (offset up to 460)
        ldx gm_slot
        sec
        sbc gm_win_top,x
        jsr gm_mulrec
        clc
        adc #<gm_rows
        sta gm_rec_src+1
        txa
        adc #>gm_rows
        sta gm_rec_src+2
        ldx #GM_RECORD-1
gm_rec_src:
        lda $ffff,x
        sta gm_rec,x
        dex
        bpl gm_rec_src
        ldx #0
        ldy #0
-       lda gm_rec,x            ; name: PETSCII padded with $a0 -> ASCII
        cmp #$a0
        beq +
        and #$7f
        cmp #32
        bcs ++
+       lda #32
+       sta gfx_text_buffer,y
        inx
        iny
        cpy #16
        bne -
        lda #32
        sta gfx_text_buffer+16
        lda gm_rec+16           ; type
        and #7
        cmp #7
        bcc +
        lda #0
+       sta gm_math
        asl
        adc gm_math             ; *3
        tay
        lda gm_types,y
        sta gfx_text_buffer+17
        lda gm_types+1,y
        sta gfx_text_buffer+18
        lda gm_types+2,y
        sta gfx_text_buffer+19
        lda #32
        sta gfx_text_buffer+20
        lda gm_rec+16           ; USB entries have no size in the listing
        and #7
        cmp #5
        bcc +
        lda #32
        ldy #4
-       sta gfx_text_buffer+20,y
        dey
        bne -
        beq ++
+       lda gm_rec+18           ; blocks, 4 digits right aligned
        sta gm_num
        lda gm_rec+19
        sta gm_num+1
        ldy #24
        jsr gm_decimal4
+       lda #25
        sta gfx_text_length
        rts
; Read the records of rows 0..wh-1 into gm_rows.
gm_read_rows:
        ldx gm_slot
        lda gm_win_count,x
        sec
        sbc gm_win_top,x
        beq gm_read_none
        bcc gm_read_none
        cmp gm_wh
        bcc +
        lda gm_wh
+       jsr gm_mulrec
        sta N_COUNT
        stx N_COUNT+1
        jsr gm_select_mem
        ldx gm_slot
        lda gm_win_top,x
        jsr gm_mulrec
        sta N_OFFSET
        stx N_OFFSET+1
        jsr N_READ
        bcs gm_read_done
        ldx #0                  ; at most 24*20 = 480 bytes
-       lda N_BUFFER,x
        sta gm_rows,x
        lda N_BUFFER+256,x
        sta gm_rows+256,x
        inx
        bne -
gm_read_none:
        clc
gm_read_done:
        rts
; Work rectangle of the slot's window.
gm_work:
        lda #WS_GET
        sta N_BUFFER
        ldx gm_slot
        lda gm_win_handle,x
        sta N_BUFFER+1
        lda #WF_WORKXYWH
        sta N_BUFFER+2
        jsr gm_wcall
        bcs +
        lda N_BUFFER
        sta gm_wx
        lda N_BUFFER+1
        sta gm_wy
        lda N_BUFFER+2
        sta gm_ww
        lda N_BUFFER+3
        sta gm_wh
+       rts
; Rectangle N_BUFFER[0..3] (cells) intersected with gm_clip -> graphics clip.
; Carry set when the intersection is empty.
gm_clip_to_rect:
        lda N_BUFFER
        cmp gm_clip
        bcs +
        lda gm_clip
+       sta gm_ix0
        lda N_BUFFER+1
        cmp gm_clip+1
        bcs +
        lda gm_clip+1
+       sta gm_iy0
        lda N_BUFFER
        clc
        adc N_BUFFER+2
        sta gm_ix1
        lda gm_clip
        clc
        adc gm_clip+2
        cmp gm_ix1
        bcs +
        sta gm_ix1
+       lda N_BUFFER+1
        clc
        adc N_BUFFER+3
        sta gm_iy1
        lda gm_clip+1
        clc
        adc gm_clip+3
        cmp gm_iy1
        bcs +
        sta gm_iy1
+       lda gm_ix0
        cmp gm_ix1
        bcs gm_clip_empty
        lda gm_iy0
        cmp gm_iy1
        bcs gm_clip_empty
        lda gm_ix0
        jsr gm_times8
        sta gfx_x0
        stx gfx_x0+1
        lda gm_ix1
        jsr gm_times8
        sta gfx_x1
        stx gfx_x1+1
        lda gm_iy0
        jsr gm_times8
        sta gfx_y0
        stx gfx_y0+1
        lda gm_iy1
        jsr gm_times8
        sta gfx_y1
        stx gfx_y1+1
        jsr gfx_set_clip
        rts
gm_clip_empty:
        sec
        rts

; ---- scrolling ----------------------------------------------------------------------
gm_arrowed:
        jsr gm_work
        ldx gm_slot
        lda ae_ev_result+11
        cmp #2                  ; 2 line up, 3 line down, 0/1 page up/down
        bne +
        lda gm_win_top,x
        beq gm_scroll_done
        dec gm_win_top,x
        jmp gm_scrolled
+       cmp #3
        bne +
        lda #1
        jmp gm_scroll_down
+       cmp #0
        bne gm_page_down
        lda gm_win_top,x        ; page up
        sec
        sbc gm_wh
        bcs +
        lda #0
+       sta gm_win_top,x
        jmp gm_scrolled
gm_page_down:
        lda gm_wh
gm_scroll_down:
        clc
        adc gm_win_top,x
        sta gm_math
        jsr gm_max_top
        cmp gm_math
        bcc +
        lda gm_math
+       sta gm_win_top,x
gm_scrolled:
        jsr gm_update_slider
        jmp gm_repaint_all
gm_scroll_done:
        rts
; A = the largest top row: max(0, count - wh).
gm_max_top:
        ldx gm_slot
        lda gm_win_count,x
        sec
        sbc gm_wh
        bcs +
        lda #0
+       rts
gm_vslid:
        jsr gm_work
        jsr gm_max_top
        ldx ae_ev_result+11     ; top = pos * max / 255 (rounded)
        jsr gm_mul
        lda gm_prod
        clc
        adc #127
        lda gm_prod+1
        adc #0
        ldx gm_slot
        sta gm_win_top,x
        jmp gm_scrolled
; Keep the selection visible after keyboard moves.
gm_scroll_to_selection:
        jsr gm_work
        ldx gm_slot
        lda gm_win_sel,x
        cmp gm_win_top,x
        bcs +
        sta gm_win_top,x
        jmp gm_scrolled
+       sec
        sbc gm_win_top,x
        cmp gm_wh
        bcc gm_repaint_all
        lda gm_win_sel,x
        sec
        sbc gm_wh
        clc
        adc #1
        sta gm_win_top,x
        jmp gm_scrolled
; Repaint the whole work area of the slot.
gm_repaint_all:
        jsr gm_work
        lda gm_wx
        sta gm_clip
        lda gm_wy
        sta gm_clip+1
        lda gm_ww
        sta gm_clip+2
        lda gm_wh
        sta gm_clip+3
        jmp gm_paint_window
; Slider size = wh*255/count, position = top*255/max(1, count-wh).
gm_update_slider:
        jsr gm_work
        ldx gm_slot
        lda #255
        sta gm_math3
        lda gm_win_count,x
        beq +
        cmp gm_wh
        bcc +
        beq +
        lda gm_wh
        ldx #255
        jsr gm_mul
        ldx gm_slot
        lda gm_win_count,x
        jsr gm_div              ; gm_prod / A
        sta gm_math3
+       lda #WF_VSLSIZE
        ldy gm_math3
        jsr gm_wset_value
        jsr gm_max_top
        sta gm_math3
        lda #0
        ldy gm_math3
        beq +
        ldx gm_slot
        lda gm_win_top,x
        ldx #255
        jsr gm_mul
        lda gm_math3
        jsr gm_div
+       tay
        lda #WF_VSLIDE
        jmp gm_wset_value
; A = field, Y = value byte.
gm_wset_value:
        sty N_BUFFER+3
gm_wset_simple:
        sta N_BUFFER+2
        lda #WS_SET
        sta N_BUFFER
        ldx gm_slot
        lda gm_win_handle,x
        sta N_BUFFER+1
        jmp gm_wcall
gm_set_rect:
        ldx #3
-       lda gm_rect,x
        sta N_BUFFER+3,x
        dex
        bpl -
        lda #WF_CURRXYWH
        jmp gm_wset_simple
gm_fulled:
        lda #WS_GET             ; full size, or back to the previous one
        sta N_BUFFER
        ldx gm_slot
        lda gm_win_handle,x
        sta N_BUFFER+1
        lda #WF_FULLXYWH
        sta N_BUFFER+2
        jsr gm_wcall
        ldx #3
-       lda N_BUFFER,x
        sta gm_rect,x
        dex
        bpl -
        lda #WS_GET
        sta N_BUFFER
        ldx gm_slot
        lda gm_win_handle,x
        sta N_BUFFER+1
        lda #WF_CURRXYWH
        sta N_BUFFER+2
        jsr gm_wcall
        ldx #3
-       lda N_BUFFER,x
        cmp gm_rect,x
        bne +
        dex
        bpl -
        lda #WS_GET
        sta N_BUFFER
        ldx gm_slot
        lda gm_win_handle,x
        sta N_BUFFER+1
        lda #WF_PREVXYWH
        sta N_BUFFER+2
        jsr gm_wcall
        ldx #3
-       lda N_BUFFER,x
        sta gm_rect,x
        dex
        bpl -
+       jsr gm_set_rect
        jmp gm_update_slider

; ---- selection and opening entries -------------------------------------------------------
; Row under gm_cy in the slot's work area: A = entry, carry set if none.
gm_row_under:
        jsr gm_work
        lda gm_cy
        sec
        sbc gm_wy
        bcc +
        ldx gm_slot
        clc
        adc gm_win_top,x
        cmp gm_win_count,x
        bcs +
        clc
        rts
+       sec
        rts
gm_select_entry:                ; a click: Shift adds or removes the row
        tay
        lda $d3                 ; KERNAL SHFLAG: bit 0 Shift
        lsr
        tya
        bcs gm_toggle
        pha                     ; held on a selected row: the others stay, to drag
        jsr gm_bit
        and gm_win_bits,x
        beq +
        lda ae_ev_result+5
        and #1
        beq +
        pla
        ldx gm_slot
        sta gm_win_sel,x
        rts
+       pla
gm_select_index:                ; A becomes the only selected entry
        ldx gm_slot
        cmp gm_win_sel,x
        bne +
        ldy gm_nsel,x
        dey
        beq ++
+       jsr gm_select_set
        jmp gm_repaint_all
+       rts
gm_toggle:
        sta gm_bi
        jsr gm_bit
        eor gm_win_bits,x
        sta gm_win_bits,x
        ldx gm_slot
        and gm_bm
        beq +
        inc gm_nsel,x
        lda gm_bi
        sta gm_win_sel,x
        jmp gm_repaint_all
+       dec gm_nsel,x
        lda gm_bi
        cmp gm_win_sel,x
        bne +
        jsr gm_first_sel        ; the anchor moves to another selected row
        ldx gm_slot
        sta gm_win_sel,x
+       jmp gm_repaint_all
; A = gm_slot's only selected entry ($ff: none): the set is cleared, then A
; added. Keeps Y.
gm_select_set:
        ldx gm_slot
        sta gm_win_sel,x
        pha
        lda #0
        sta gm_nsel,x
        lda gm_slot25,x
        tax
        clc
        adc #GM_BITS
        sta gm_bend
        lda #0
-       sta gm_win_bits,x
        inx
        cpx gm_bend
        bne -
        pla
        cmp #$ff
        beq +
        jsr gm_bit_set
+       ldx gm_slot
        rts
gm_bit_set:                     ; A = entry of gm_slot: select it (counted)
        jsr gm_bit
        and gm_win_bits,x
        bne +
        lda gm_bm
        ora gm_win_bits,x
        sta gm_win_bits,x
        ldx gm_slot
        inc gm_nsel,x
+       rts
; A = entry of gm_slot -> X = its byte in gm_win_bits, A = gm_bm = its bit.
; Keeps Y.
gm_bit:
        pha
        and #7
        tax
        lda gm_bitmask,x
        sta gm_bm
        pla
        lsr
        lsr
        lsr
        ldx gm_slot
        clc
        adc gm_slot25,x
        tax
        lda gm_bm
        rts
gm_first_sel:                   ; -> A = gm_slot's first selected entry, $ff if none
        lda #0
        sta gm_ei
-       lda gm_ei
        ldx gm_slot
        cmp gm_win_count,x
        bcs +
        jsr gm_bit
        and gm_win_bits,x
        bne ++
        inc gm_ei
        bne -
+       lda #$ff
        rts
+       lda gm_ei
        rts
; Call A/X with gm_win_sel = each selected entry of gm_slot, lowest first.
; The listing is not read again in between, so entries keep their numbers.
gm_each:
        sta gm_each_call+1
        stx gm_each_call+2
        lda #0
        sta gm_ei
-       lda gm_ei
        ldx gm_slot
        cmp gm_win_count,x
        bcs ++
        jsr gm_bit
        and gm_win_bits,x
        beq +
        ldx gm_slot
        lda gm_ei
        sta gm_win_sel,x
gm_each_call:
        jsr $ffff
+       inc gm_ei
        bne -
+       rts
; Ctrl-A: every entry of the top window.
gm_select_all:
        jsr gm_top_slot
        bcs ++
        stx gm_slot
        lda #0
        jsr gm_select_set
        lda #1
        sta gm_bi
-       lda gm_bi
        ldx gm_slot
        cmp gm_win_count,x
        bcs +
        jsr gm_bit_set
        inc gm_bi
        bne -
+       jmp gm_repaint_all
+       rts
; A press below a window's entries: without Shift it clears the selection.
; Held, it drags a band: the rows between the press and the pointer (kept
; inside the window and the listing) are selected, live, until the release.
gm_band:
        lda gm_cy
        cmp gm_wy
        bcc gm_band_done        ; the frame
        ldx gm_slot
        lda gm_nsel,x
        beq +
        lda $d3
        lsr
        bcs +
        lda #$ff
        jsr gm_select_set
        jsr gm_repaint_all
+       lda ae_ev_result+5
        and #1
        beq gm_band_done        ; released: a click
        ldx gm_slot
        lda gm_win_count,x
        beq gm_band_done
        jsr gm_band_row
        sta gm_banchor
gm_band_loop:
        jsr gm_band_row
        sta gm_bnow
        lda #$ff
        jsr gm_select_set
        lda gm_banchor          ; from the lower to the higher row
        ldy gm_bnow
        cmp gm_bnow
        bcc +
        sty gm_bi
        tay
        jmp ++
+       sta gm_bi
+       sty gm_bend
-       lda gm_bi
        jsr gm_bit_set
        lda gm_bi
        inc gm_bi
        cmp gm_bend
        bne -
        ldx gm_slot
        lda gm_bnow
        sta gm_win_sel,x
        jsr gm_repaint_all
        jsr ae_present
        lda #MU_BUTTON|MU_M1    ; the release, or the pointer leaving its row
        sta ae_ev_params
        lda #1
        sta ae_ev_params+1
        sta ae_ev_params+2
        sta ae_ev_params+4      ; rectangle 1 fires outside
        lda #0
        sta ae_ev_params+3
        sta ae_ev_params+5
        lda gm_cy
        sta ae_ev_params+6
        lda #40
        sta ae_ev_params+7
        lda #1
        sta ae_ev_params+8
        jsr ae_event
        bcs gm_band_done
        lda ae_ev_result
        and #MU_BUTTON
        bne gm_band_done
        jsr gm_pointer_cell
        jmp gm_band_loop
gm_band_done:
        rts
gm_band_row:                    ; gm_cy in the work area and the listing -> A = entry
        lda gm_cy
        cmp gm_wy
        bcs +
        lda gm_wy
+       sec
        sbc gm_wy
        cmp gm_wh
        bcc +
        lda gm_wh
        sbc #1
+       ldx gm_slot
        clc
        adc gm_win_top,x
        cmp gm_win_count,x
        bcc +
        lda gm_win_count,x
        sbc #1
+       rts
; Launch the selected entry through the dispatcher (it checks the program).
gm_open_entry:
        ldx gm_slot
        lda gm_win_fmt,x
        cmp #3
        bne +
        jmp gm_ult_open_entry
+       lda gm_win_sel,x
        sta gm_item
        jsr gm_work
        ldx gm_slot             ; read the one record
        lda gm_item
        jsr gm_mulrec
        sta N_OFFSET
        stx N_OFFSET+1
        lda #GM_RECORD
        sta N_COUNT
        lda #0
        sta N_COUNT+1
        jsr gm_select_mem
        jsr N_READ
        bcs gm_launch_fail
        lda N_BUFFER+16         ; a SEQ file is a text document for the Editor
        and #7
        cmp #1
        bne +
        jmp gm_iec_document
+       ldx #0
-       lda N_BUFFER,x
        cmp #$a0
        beq +
        sta N_APPNAME,x
        inx
        cpx #16
        bne -
+       cpx #0
        beq gm_launch_fail
        stx N_NAMELEN
        ldx gm_slot
        lda gm_win_dev,x
        sta N_DEVICE
        lda gm_win_fmt,x
        sta N_APPFORMAT
        jsr gm_session_save     ; the windows come back when the desktop does
        jsr gm_leave
        lda #0
        jmp N_REPLACE
gm_launch_fail:
        rts
gm_launcher_leave:
        jsr gm_session_save
        jsr gm_leave
gm_launcher:
        lda N_BOOTFORMAT        ; the card launcher is "cards" on the boot disk
        sta N_APPFORMAT
        lda N_BOOTDEVICE
        sta N_DEVICE
        ldx #4
-       lda gm_cards_name,x
        sta N_APPNAME,x
        dex
        bpl -
        lda #5
        sta N_NAMELEN
        lda #0                  ; A is the exit result
        jmp N_REPLACE

; ---- windows: slots -------------------------------------------------------------------------
gm_slot_of:                     ; X = AES handle -> X = slot, carry set if none
        txa
        ldx #GM_WINDOWS-1
-       cmp gm_win_handle,x
        beq +
        dex
        bpl -
        sec
        rts
+       clc
        rts
gm_top_slot:
        lda #WS_GET
        sta N_BUFFER
        lda #WF_TOP
        sta N_BUFFER+2
        jsr gm_wcall
        bcs +
        ldx N_BUFFER
        beq +
        jmp gm_slot_of
+       sec
        rts
gm_close_slot:
        ldx gm_slot
        lda gm_win_handle,x
        sta N_BUFFER+1
        lda #WS_CLOSE
        sta N_BUFFER
        jsr gm_wcall
        ldx gm_slot
        lda gm_win_handle,x
        sta N_BUFFER+1
        lda #WS_DELETE
        sta N_BUFFER
        jsr gm_wcall
        ldx gm_slot
gm_free_slot:
        lda #0
        sta gm_win_handle,x
gm_free_mem:
        stx gm_math4
        jsr gm_select_mem_x
        jsr N_FREE
        ldx gm_math4
        lda #0
        sta gm_mem0,x
        rts
gm_select_mem:
        ldx gm_slot
gm_select_mem_x:
        lda N_CURRENT
        sta N_OWNER
        lda gm_mem0,x
        sta N_HANDLE
        lda gm_mem1,x
        sta N_HANDLE+1
        lda gm_mem2,x
        sta N_HANDLE+2
        lda gm_mem3,x
        sta N_HANDLE+3
        rts

; ---- arithmetic and text --------------------------------------------------------------------
gm_times8:                      ; A*8 -> A lo, X hi
        ldx #0
        stx gm_t8
        asl
        rol gm_t8
        asl
        rol gm_t8
        asl
        rol gm_t8
        ldx gm_t8
        rts
gm_mulrec:                      ; A*GM_RECORD -> A lo, X hi
        ldx #GM_RECORD
gm_mul:                         ; A*X -> gm_prod; also A lo, X hi
        sta gm_mul_a
        stx gm_mul_b
        lda #0
        sta gm_prod
        sta gm_prod+1
        ldx #8
-       lsr gm_mul_b
        bcc +
        clc
        lda gm_prod+1
        adc gm_mul_a
        sta gm_prod+1
+       ror gm_prod+1
        ror gm_prod
        dex
        bne -
        lda gm_prod
        ldx gm_prod+1
        rts
gm_div:                         ; gm_prod / A -> A (quotient < 256)
        sta gm_divisor
        lda #0
        ldx #16
-       asl gm_prod
        rol gm_prod+1
        rol
        cmp gm_divisor
        bcc +
        sbc gm_divisor
        inc gm_prod
+       dex
        bne -
        lda gm_prod
        rts
gm_cells_hi0:
        lda #0
        sta gfx_x0+1
        sta gfx_x1+1
        sta gfx_y0+1
        sta gfx_y1+1
        rts
; A (0..99) -> X tens digit, A units digit (ASCII; a leading 0 stays).
gm_decimal2:
        ldx #$30
-       cmp #10
        bcc +
        sbc #10
        inx
        bne -
+       ora #$30
        rts
; gm_num (0..9999) as 4 right-aligned digits ending at gfx_text_buffer+Y.
gm_decimal4:
        ldx #4
-       lda #0                  ; divide by 10
        stx gm_math2
        ldx #16
-       asl gm_num
        rol gm_num+1
        rol
        cmp #10
        bcc +
        sbc #10
        inc gm_num
+       dex
        bne -
        ora #$30
        sta gfx_text_buffer,y
        dey
        ldx gm_math2
        dex
        bne --
        ldx #3                  ; leading zeros to spaces
        iny
-       lda gfx_text_buffer,y
        cmp #$30
        bne +
        lda #32
        sta gfx_text_buffer,y
        iny
        dex
        bne -
+       rts
gm_hex_error:                   ; N_BROWSERERROR / A as two hex digits in the alerts
        pha
        lsr
        lsr
        lsr
        lsr
        tax
        lda gm_hex_digits,x
        sta gm_start_alert_hex
        sta gm_drive_alert_hex
        pla
        and #15
        tax
        lda gm_hex_digits,x
        sta gm_start_alert_hex+1
        sta gm_drive_alert_hex+1
        rts

; ---- data ----------------------------------------------------------------------------------------
gm_hex_digits: .byte 48,49,50,51,52,53,54,55,56,57,65,66,67,68,69,70
gm_aesvc_name: .text "aesvc.prg"
gm_cards_name: .text "cards"
gm_drive_title: .byte 68,114,105,118,101,32,0    ; "Drive "
gm_types: .byte 68,69,76,83,69,81,80,82,71,85,83,82,82,69,76   ; DEL SEQ PRG USR REL
        .byte 68,73,82,32,32,32            ; DIR, and a USB file (no CBM type)
gm_icon_y: .byte 2,6,20,10,14
gm_icon_art: .byte 0,0,1,0,2
gm_icon_on: .byte 1,1,1,0,0     ; USB and Printer: set by the probes at start
gm_icon_dev_lo: .byte 0,9,0,1   ; 0: the boot drive; USB: DOS context 1
gm_icon_label_lo: .byte <gm_label_boot,<gm_label_9,<gm_label_trash,<gm_label_usb,<gm_label_printer
gm_icon_label_hi: .byte >gm_label_boot,>gm_label_9,>gm_label_trash,>gm_label_usb,>gm_label_printer
gm_label_boot: .byte 66,111,111,116,0                    ; Boot
gm_label_9: .byte 68,114,105,118,101,32,57,0            ; Drive 9
gm_label_trash: .byte 84,114,97,115,104,0               ; Trash
gm_label_usb: .byte 85,83,66,0                        ; USB
gm_label_printer: .byte 80,114,105,110,116,101,114,0     ; Printer
; 32x16 icons, 4 bytes per row: drive, trash, printer
gm_icon_bits:
        .byte $7f,$ff,$ff,$fe, $40,$00,$00,$02, $40,$00,$00,$02, $47,$ff,$ff,$e2
        .byte $40,$00,$00,$02, $40,$00,$00,$02, $40,$00,$00,$02, $40,$00,$00,$02
        .byte $40,$00,$00,$02, $40,$00,$00,$02, $40,$00,$00,$02, $40,$00,$00,$1a
        .byte $40,$00,$00,$1a, $40,$00,$00,$02, $7f,$ff,$ff,$fe, $00,$00,$00,$00
        .byte $00,$0f,$f0,$00, $3f,$ff,$ff,$fc, $3f,$ff,$ff,$fc, $10,$00,$00,$08
        .byte $12,$49,$24,$88, $12,$49,$24,$88, $12,$49,$24,$88, $12,$49,$24,$88
        .byte $12,$49,$24,$88, $12,$49,$24,$88, $12,$49,$24,$88, $12,$49,$24,$88
        .byte $12,$49,$24,$88, $10,$00,$00,$08, $1f,$ff,$ff,$f8, $00,$00,$00,$00
        .byte $00,$ff,$ff,$00, $00,$80,$01,$00, $00,$80,$01,$00, $0f,$ff,$ff,$f0
        .byte $10,$00,$00,$08, $10,$00,$00,$08, $10,$00,$00,$3a, $10,$00,$00,$08
        .byte $1f,$ff,$ff,$f8, $10,$00,$00,$08, $13,$ff,$ff,$c8, $10,$00,$00,$08
        .byte $1f,$ff,$ff,$f8, $00,$80,$01,$00, $00,$ff,$ff,$00, $00,$00,$00,$00
; Desk:About Kestrel...|-|Control Panel...;File:Open^O|Show Info^I
; |-|Delete^D|Format...|New Folder...|-|Close^W;View:Name|Type|Size|Unsorted
; ;Options:Preferences...|Save Desktop|Print Screen|Launcher^L
gm_menu:
        .byte 68,101,115,107,58,65,98,111,117,116,32,75,101,115,116,114,101,108,46,46,46,124,45,124,67,111,110,116
        .byte 114,111,108,32,80,97,110,101,108,46,46,46,59,70,105,108,101,58,79,112,101,110,94,79
        .byte 124,83,104,111,119,32,73,110,102,111,94,73,124,45,124,68,101,108,101,116,101,94,68,124
        .byte 70,111,114,109,97,116,46,46,46,124,78,101,119,32,70,111,108,100,101,114,46,46,46,124
        .byte 45,124,67,108,111,115,101,94,87,59,86,105,101,119,58,78,97,109,101,124,84,121,112,101
        .byte 124,83,105,122,101,124,85,110,115,111,114,116,101,100,59,79,112,116,105,111,110,115,58,80
        .byte 114,101,102,101,114,101,110,99,101,115,46,46,46,124,83,97,118,101,32,68,101,115,107,116
        .byte 111,112,124,80,114,105,110,116,32,83,99,114,101,101,110,124,76,97,117,110,99,104,101,114
        .byte 94,76,0
; Show Info alert pieces
gm_s_head: .byte 91,49,93,91,0                          ; [1][
gm_s_type: .byte 124,84,121,112,101,58,32,0             ; |Type:
gm_s_blocks: .byte 32,32,66,108,111,99,107,115,58,32,0  ;   Blocks:
gm_s_files: .byte 124,70,105,108,101,115,58,32,0        ; |Files:
gm_s_used: .byte 124,66,108,111,99,107,115,32,117,115,101,100,58,32,0   ; |Blocks used:
gm_s_ok: .byte 93,91,79,75,93,0                         ; ][OK]
gm_gaps: .byte 1,4,10,23,57,132
; [2][Delete NAME?|This cannot be undone.][Delete|Cancel]
gm_s_delete: .byte 91,50,93,91,68,101,108,101,116,101,32,0
gm_s_undone: .byte 63,124,84,104,105,115,32,99,97,110,110,111,116,32,98,101,32,117,110,100,111,110,101,46
        .byte 93,91,68,101,108,101,116,101,124,67,97,110,99,101,108,93,0
gm_s_nodelete: .byte 91,51,93,91,67,111,117,108,100,32,110,111,116,32,100,101,108,101,116,101,124,0  ; [3][Could not delete|
gm_s_bar: .byte 124,0
gm_s_error: .byte 101,114,114,111,114,32,36,0           ; error $
; [1][This name cannot be|deleted from here.][OK]
gm_badname_alert: .byte 91,49,93,91,84,104,105,115,32,110,97,109,101,32,99,97,110,110,111,116,32,98,101,124
        .byte 100,101,108,101,116,101,100,32,102,114,111,109,32,104,101,114,101,46,93,91,79,75,93,0
gm_bad_chars: .byte $2a,$3f,$2c,$3d,$3a,$22,$40   ; * ? , = : " @: DOS syntax in a name
gm_bad_chars_end:
GM_GAP_COUNT = 6
; [1][Kestrel GEM desktop|AES 1.6 on the C128][OK]
gm_about: .byte 91,49,93,91,75,101,115,116,114,101,108,32,71,69,77,32,100,101,115,107,116,111,112,124,65,69,83,32
        .byte 49,46,55,32,111,110,32,116,104,101,32,67,49,50,56,93,91,79,75,93,0
; [3][Could not start that|program: error $xx][OK]
gm_start_alert: .byte 91,51,93,91,67,111,117,108,100,32,110,111,116,32,115,116,97,114,116,32
        .byte 116,104,97,116,124,112,114,111,103,114,97,109,58,32,101,114,114,111,114,32,36
gm_start_alert_hex: .byte 48,48,93,91,79,75,93,0
; [3][Could not read this|drive: error $xx][OK]
gm_drive_alert: .byte 91,51,93,91,67,111,117,108,100,32,110,111,116,32,114,101,97,100,32,116
        .byte 104,105,115,124,100,114,105,118,101,58,32,101,114,114,111,114,32,36
gm_drive_alert_hex: .byte 48,48,93,91,79,75,93,0
; [1][Four folder windows|are already open.][OK]
gm_full_alert: .byte 91,49,93,91,70,111,117,114,32,102,111,108,100,101,114,32,119,105,110,100
        .byte 111,119,115,124,97,114,101,32,97,108,114,101,97,100,121,32,111,112,101,110,46,93,91,79,75,93,0

gm_confirm: .byte 1             ; bit 0: ask before deleting; bit 1 (GM_NOCOPYASK): copy without asking;
                                ; bit 2 (GM_KEYCLICK): click on keys; bit 3 (GM_NOOVERASK):
                                ; replace a name on the target without asking; bit 4
                                ; (GM_BELL): ring for stop alerts
gm_editor_name: .text "editor", "paint", "sheet"
gm_upnt: .byte $55,$50,$4e,$54 ; "UPNT", Paint's picture signature
gm_usht: .byte $55,$53,$48,$54 ; "USHT", Sheet's workbook signature
gm_doc_kind: .byte 0
gm_suffix: .fill 3,0
gm_s_unproven: .byte 91,51,93,91,84,104,101,32,100,114,105,118,101,32,100,105,100,32,110,111,116,32,112,114,111,118,101,124,116,104,101,32,100,101,108,101,116,105,111,110,59,32,115,101,101,32,116,104,101,32,108,105,115,116,46,93,91,79,75,93,0   ; [3][The drive did not prove|the deletion; see the list.][OK]
gm_target: .byte 0
gm_nlen: .byte 0
gm_s_notusb: .byte 91,49,93,91,78,111,116,32,97,118,97,105,108,97,98,108,101,32,111,110,32,85,83,66,124,115,116,111,114,97,103,101,32,105,110,32,116,104,101,32,100,101,115,107,116,111,112,32,121,101,116,46,93,91,79,75,93,0   ; [1][Not available on USB|storage in the desktop yet.][OK]
gm_s_usbfail: .byte 91,51,93,91,67,111,117,108,100,32,110,111,116,32,114,101,97,100,32,85,83,66,124,115,116,111,114,97,103,101,58,32,101,114,114,111,114,32,36
gm_s_usbhex: .byte 48,48
        .byte 93,91,79,75,93,0
gm_usb_title: .byte 85,83,66,32
gm_s_free: .byte 124,66,108,111,99,107,115,32,102,114,101,101,58,32,0   ; |Blocks free: 
gm_desk_color: .byte $16
gm_restoring: .byte 0
gm_orect: .fill 4,0
gm_spos: .byte 0
gm_sslot: .byte 0
gm_stop: .byte 0
gm_session: .fill 64,0
gm_magic: .byte 71,68,83,2                           ; "GDS", version 2
gm_dclick: .byte 2                                   ; double-click speed 0..4
gm_inf_name: .byte 68,69,83,75,84,79,80,46,73,78,70  ; DESKTOP.INF
gm_inf_scratch: .byte 83,48,58,68,69,83,75,84,79,80,46,73,78,70   ; S0:DESKTOP.INF
gm_s_nosave: .byte 91,51,93,91,67,111,117,108,100,32,110,111,116,32,115,97,118,101,32,116,104,101,32,100,101,115,107,116,111,112,46,124,0   ; [3][Could not save the desktop.|
gm_mop: .byte 0
gm_mtoken: .fill 3,0
gm_mod_names: .byte 71,68,68,76,71,46,80,82,71   ; module 1
        .byte 71,68,83,69,84,46,80,82,71   ; module 2
        .byte 71,68,67,80,89,46,80,82,71   ; module 3: GDCPY.PRG
        .byte 71,68,83,69,83,46,80,82,71   ; module 4: GDSES.PRG
        .byte 71,68,85,83,66,46,80,82,71   ; module 5: GDUSB.PRG
        .byte 71,68,68,83,75,46,80,82,71   ; module 6: GDDSK.PRG
        .byte 71,68,78,69,87,46,80,82,71   ; module 7: GDNEW.PRG
        .byte 71,68,70,77,84,46,80,82,71   ; module 8: GDFMT.PRG
        .byte 71,68,80,82,84,46,80,82,71   ; module 9: GDPRT.PRG
; GM_MOP_* 1..13 -> module: GDDLG 1 (Show Info), GDSET 2 (Preferences,
; Control Panel), GDCPY 3 (copy, move), GDSES 4 (the saved desktop, the
; accessory), GDUSB 5 (USB Show Info with rename), GDDSK 6 (disk copy, the
; read-only lock), GDNEW 7 (New Folder), GDFMT 8 (Format), GDPRT 9
; (printing, Print Screen).
gm_mop_module: .byte 1,2,8,2,5,3,4,4,7,9,6,9,6
gm_alert_default: .byte 0
gm_prt_dev: .byte 4             ; the printer: IEC device 4 or 5
gm_prt_sa: .byte 7              ; secondary address 7 (upper and lower case) or 0
gm_lock_want: .byte 0           ; Show Info to GDDSK: bit 7 a lock to set, bit 6 locked
gm_lock_name: .fill 16,0        ; the file's name, padded with $a0
gm_mloaded: .byte 0
gm_mwanted: .byte 0
gm_s_nomodule: .byte 91,51,93,91,67,111,117,108,100,32,110,111,116,32,108,111,97,100,32,0   ; [3][Could not load 
gm_s_nomodule2: .byte 46,124,0   ; .|
gm_surface: .fill 4,0
gm_file: .fill 4,0
gm_start_error: .byte 0
gm_icon_sel: .byte $ff
gm_new_icon: .byte 0
gm_slot: .byte 0
gm_dev: .byte 0
gm_fmt: .byte 0
gm_mbit: .byte 0
gm_q: .fill 4,0                 ; gm_anum32's number, then the division
gm_ndig: .byte 0
gm_digits: .fill 10,0
gm_dev_format: .byte $ff       ; device 9's detected geometry, $ff unknown
gm_count: .byte 0
gm_page: .byte 0
gm_drag: .byte 0
gm_view: .byte 0                ; View: 0 name, 1 type, 2 size, 3 unsorted
gm_vslot: .byte 0
gm_k: .byte 0
gm_m: .byte 0
gm_gap: .byte 0
gm_gapi: .byte 0
gm_i2: .byte 0
gm_ins_val: .byte 0
gm_pos: .byte 0
gm_other: .byte 0
gm_cmpb: .byte 0
gm_total: .word 0
gm_alen: .byte 0
gm_abuf: .fill 96,0
gm_item: .byte 0
gm_cx: .byte 0
gm_cy: .byte 0
gm_i: .byte 0
gm_j: .byte 0
gm_art: .byte 0
gm_row: .byte 0
gm_math: .byte 0
gm_math2: .byte 0
gm_math3: .byte 0
gm_math4: .byte 0
gm_t8: .byte 0
gm_ra: .byte 0
gm_rb: .byte 0
gm_num: .word 0
gm_mul_a: .byte 0
gm_mul_b: .byte 0
gm_prod: .word 0
gm_divisor: .byte 0
gm_wx: .byte 0
gm_wy: .byte 0
gm_ww: .byte 0
gm_wh: .byte 0
gm_ix0: .byte 0
gm_iy0: .byte 0
gm_ix1: .byte 0
gm_iy1: .byte 0
gm_clip: .fill 4,0
gm_rect: .fill 4,0
gm_win_handle: .fill GM_WINDOWS,0
gm_win_dev: .fill GM_WINDOWS,0
gm_win_fmt: .fill GM_WINDOWS,0
gm_win_count: .fill GM_WINDOWS,0
gm_win_top: .fill GM_WINDOWS,0
gm_win_sel: .fill GM_WINDOWS,$ff    ; the anchor: Show Info, Open, the cursor keys
gm_nsel: .fill GM_WINDOWS,0         ; entries selected
gm_win_bits: .fill GM_WINDOWS*GM_BITS,0   ; the selection, a bit per entry
gm_slot25: .byte 0,GM_BITS,2*GM_BITS,3*GM_BITS
gm_bitmask: .byte 1,2,4,8,16,32,64,128
gm_bm: .byte 0
gm_bi: .byte 0
gm_ei: .byte 0
gm_bend: .byte 0
gm_banchor: .byte 0
gm_bnow: .byte 0
gm_batch: .byte 0
gm_s_items: .byte 32,105,116,101,109,115,0   ; " items"
gm_mem0: .fill GM_WINDOWS,0
gm_mem1: .fill GM_WINDOWS,0
gm_mem2: .fill GM_WINDOWS,0
gm_mem3: .fill GM_WINDOWS,0
gm_rec: .fill GM_RECORD,0
gm_dirpage: .fill 256,0
gm_win_plen: .fill GM_WINDOWS,0
gm_name: .fill 256,0             ; a full USB name
; The AES client sits here, in the slack before the page-aligned path table.
.include "aes-client.inc"
gm_path: .fill 256,0             ; gm_slot's USB path (gm_path_page)
gm_paths: .fill 4,0              ; the heap block of every slot's path
; Y = record index -> A = high byte, gm_ra = low byte of gm_sortbuf+Y*21.
; Keeps X and Y (the scan and sort loops hold them).
gm_rec_addr:
        lda #0
        sta gm_t8
        tya                     ; Y*4
        asl
        rol gm_t8
        asl
        rol gm_t8
        sta gm_ra
        lda gm_t8
        sta gm_rb
        lda gm_ra
        asl                     ; Y*16
        rol gm_t8
        asl
        rol gm_t8
        clc
        adc gm_ra               ; Y*20
        sta gm_ra
        lda gm_t8
        adc gm_rb
        sta gm_t8
        tya                     ; Y*21
        clc
        adc gm_ra
        sta gm_ra
        lda gm_t8
        adc #>gm_sortbuf
        rts
gm_sortbuf = GM_WORKSPACE
.cerror (gm_sortbuf & 255) != 0, "gm_rec_addr adds only the high byte of the sort workspace"
.cerror GM_MAX_ENTRIES*GM_RECORD > 16*256, "the sort workspace holds 16 pages"
; Buffers that are never live together share storage: the visible rows are
; read only while painting, the sort buffer only while scanning or sorting,
; and the sort order only after a scan has finished with its directory page.
gm_rows = gm_sortbuf
gm_order = gm_dirpage
.cerror GM_MAX_ENTRIES > 256 || 24*GM_RECORD > GM_MAX_ENTRIES*GM_RECORD, "shared buffers too small"
.include "dos-command.inc"
.include "sound.inc"
.include "graphics/graphics-core.inc"
.include "graphics/text-core.inc"
.include "input/pointer.inc"
BP_MODE=0                       ; the VDC shows this VIC surface (docs/NATIVE-VDC-SERVICE.md)
bp_select_surface=gm_select_surface
.include "graphics/vdc-client.inc"
; ---- module window (docs/NATIVE-MODULES.md) ------------------------------------------
; Nine modules share the window, each assembled on its own
; (src/native/gemdesk-*.asm); the dialog modules each have their own copy of
; the forms library (docs/NATIVE-FORMS.md). GDDLG.PRG: Show Info with rename.
; GDSET.PRG: Preferences, Control Panel. GDCPY.PRG: copy and move by
; drag and drop. GDSES.PRG: the saved desktop and the desk accessory.
; GDUSB.PRG: Show Info on USB. GDDSK.PRG: disk copy and the read-only lock.
; GDNEW.PRG: New Folder. GDFMT.PRG: Format. GDPRT.PRG: printing, Print
; Screen. Entry: gm_mop selects the operation.
gm_module:
gm_end = gm_module
.cerror gm_module > N_APPLIMIT, "the GEM desktop core exceeds its slot"
