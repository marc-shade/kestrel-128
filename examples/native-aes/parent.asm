; Standalone AES example: attach to the persistent AES, or load AESVC.PRG
; from this app's folder when none is resident. Esc leaves it resident.
.include "api.inc"
.include "aes-api.inc"
* = N_APPBASE
app_image:
        .text "napp"
        .byte 1,1,14,0
        .word app_end-app_image
        .byte (app_end-app_image+255)/256,0
        .word app_entry-app_image,0
        .text "aes demo",0
        .fill N_APPBASE+32-*,0
app_entry:
        cld
        jsr ae_attach
        bcc demo_attached
        cmp #N_BADHANDLE
        beq +
        jmp demo_failed
+
        lda N_DEVICE
        sta N_FDEVICE
        lda N_APPFORMAT
        sta N_FFORMAT
        cmp #3
        bne demo_iec_name
        ldx #0
        stx demo_path_length
-       lda N_SOURCEPATH,x
        sta N_UPATH,x
        cmp #$2f
        bne +
        txa
        clc
        adc #1
        sta demo_path_length
+       inx
        cpx N_NAMELEN
        bne -
        lda demo_path_length
        clc
        adc #9
        bcs demo_argument
        sta N_FNAMELEN
        ldx demo_path_length
        ldy #0
-       lda demo_name,y
        sta N_UPATH,x
        inx
        iny
        cpy #9
        bne -
        beq demo_open
demo_iec_name:
        lda #9
        sta N_FNAMELEN
        ldx #8
-       lda demo_name,x
        sta N_FNAME,x
        dex
        bpl -
demo_open:
        lda #N_APPOWNER
        sta N_FOWNER
        lda #1
        sta N_FTYPE
        lda #0
        sta N_FMODE
        ldx #3
-       sta N_FHANDLE,x       ; early OPEN refusal may not produce a new token
        dex
        bpl -
        jsr N_FOPEN
        php
        pha
        ldx #3
-       lda N_FHANDLE,x
        sta demo_file,x
        dex
        bpl -
        pla
        plp
        bcs demo_failed
        jsr ae_load
        php
        pha
        lda ae_stream_taken
        beq +                 ; preflight refusal leaves the stream with caller
        lda #0
        sta demo_file
+       pla
        plp
        bcs demo_failed
        inc demo_loaded
demo_attached:
        jsr demo_reply
        ldx #15
-       lda demo_ev_defaults,x
        sta ae_ev_params,x
        dex
        bpl -
        lda #1
        sta demo_active
        lda #0
        beq demo_failed
demo_argument:
        lda #N_BADARG
demo_failed:
        sta demo_error
        jsr demo_draw
input_loop:
        lda #1
        sta N_READY
        jsr N_KEYIN
        beq input_loop
        ldx #0
        stx N_READY
        cmp #27
        beq demo_exit
        cmp #$55              ; U: unload the AES, then exit
        beq demo_unload
        cmp #$45              ; E: wait for the events in ae_ev_params
        bne +
        lda demo_active
        beq input_loop
        lda #1
        sta demo_waiting
        jsr ae_event
        ldx #0
        stx demo_waiting
        sta demo_error
        jsr demo_draw
        jmp input_loop
+       cmp #$50              ; P: post one message to the AES queue
        bne +
        lda demo_active
        beq input_loop
        ldx #7
-       lda demo_message,x
        sta N_BUFFER,x
        dex
        bpl -
        jsr ae_post
        sta demo_error
        jsr demo_draw
        jmp input_loop
+       cmp #$57              ; W: three AES windows over the VIC surface
        bne +
        jsr demo_windows
        sta demo_error
        jsr demo_draw
        jmp input_loop
+       cmp #$4d              ; M: a menu bar over this app's VIC surface
        bne +
        jsr demo_menu_run
        sta demo_error
        jsr demo_draw
        jmp input_loop
+       cmp #$41              ; A: an AES alert over this app's VIC surface
        bne +
        jsr demo_alert_run
        sta demo_error
        jsr demo_draw
        jmp input_loop
+
        cmp #13
        bne input_loop
        lda demo_active
        beq input_loop
        lda #AE_OP_STATUS
        jsr ae_call
        sta demo_error
        bcs +
        jsr demo_reply
+       jsr demo_draw
        jmp input_loop
demo_unload:
        lda demo_active
        beq demo_exit
        jsr ae_unload
        bcs demo_failed
        lda #0
        sta demo_active
        beq demo_leave
demo_exit:
        lda demo_active
        beq demo_leave
        jsr ae_detach
        bcs demo_failed
        lda #0
        sta demo_active
demo_leave:
        jsr demo_close_file
        bcs demo_failed
        lda #0
        jmp N_EXIT
; Reserve and initialize the 36-page VIC surface once (as the desktop does),
; present it, run one alert to completion, then return to the text screens.
; Key $ff stands for "pointer moved/clicked": this example has no pointer
; driver, so the host sets ae_pointer_* and sends $ff (example-only input).
demo_alert_run:
        jsr demo_surface_open
        bcs demo_alert_done
        lda #<demo_alert
        ldx #>demo_alert
        ldy #2                ; Cancel is the default
        jsr ae_alert_open
        bcs demo_alert_hide
        jmp demo_alert_loop
; Reserve/initialize the surface once, then present it. Carry set on error.
demo_surface_open:
        lda demo_active
        bne +
        lda #N_BADHANDLE
        sec
        rts
+       lda ae_surface
        bne demo_alert_show
        lda N_CURRENT
        sta N_OWNER
        lda #0
        sta N_BANK
        lda #$c0
        sta N_PAGE
        lda #36
        sta N_PAGES
        jsr N_RESERVE
        bcs demo_alert_done
        ldx #3
-       lda N_HANDLE,x
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
        lda #$16
+       sta N_VALUE
        jsr N_FILL
        bcs demo_alert_done
        inc N_OFFSET+1
        inc N_OFFSET+1
        lda N_OFFSET+1
        cmp #$24
        bne -
demo_alert_show:
        lda N_CURRENT
        sta N_OWNER
        ldx #3
-       lda ae_surface,x
        sta N_HANDLE,x
        dex
        bpl -
        jmp N_VSHOW
demo_alert_loop:
        lda #1
        sta N_READY
        jsr N_KEYIN
        beq demo_alert_loop
        ldx #0
        stx N_READY
        cmp #$ff
        bne +
        lda #0
+       jsr ae_alert_step
        bcs demo_alert_hide
        lda N_BUFFER
        beq demo_alert_loop
        sta demo_choice
        jsr N_VCLOSE
        lda #0
        clc
demo_alert_done:
        rts
demo_alert_hide:
        pha
        jsr N_VCLOSE
        pla
        sec
        rts
; Install the menu, wait for messages and keys until Escape, then remove it.
; Options:Grid toggles its check mark. The last choice is shown afterwards.
demo_menu_run:
        jsr demo_surface_open
        bcs demo_menu_done
        lda #<demo_menu
        ldx #>demo_menu
        jsr ae_menu_install
        bcs demo_menu_hide
        lda #1                ; File:Open... starts disabled
        ldx #1
        ldy #2
        jsr ae_menu_set
        bcs demo_menu_hide
        lda #16|1             ; messages and keys
        sta ae_ev_params
        lda #1
        sta demo_waiting
demo_menu_loop:
        jsr ae_event
        bcs demo_menu_end
        lda ae_ev_result
        and #16
        beq demo_menu_key
        lda ae_ev_result+7
        cmp #10               ; MN_SELECTED
        bne demo_menu_key
        lda ae_ev_result+10
        sta demo_menu_title
        lda ae_ev_result+11
        sta demo_menu_item
        inc demo_menu_count
        cmp #0                ; Options (title 2) : Grid (item 0) toggles
        bne demo_menu_key
        lda demo_menu_title
        cmp #2
        bne demo_menu_key
        lda demo_grid
        eor #1
        sta demo_grid
        tay
        lda #2
        ldx #0
        jsr ae_menu_set
        bcs demo_menu_end
demo_menu_key:
        lda ae_ev_result
        and #1
        beq demo_menu_loop
        lda ae_ev_result+1
        cmp #27
        bne demo_menu_loop
        lda #0
demo_menu_end:
        pha
        lda #0
        sta demo_waiting
        lda #<demo_empty      ; remove the menu (its pixels stay the app's)
        ldx #>demo_empty
        jsr ae_menu_install
        pla
demo_menu_hide:
        pha
        jsr N_VCLOSE
        pla
        cmp #1
        rts
demo_menu_done:
        rts
; Window mode. Every WM_REDRAW is answered by filling the window's visible
; work area (pen and colour per window) through the AES fill operation.
; Keys: 1-3 top, m move, s grow, c close the top window, r record the top
; window's visible rectangles, t text in the first window (text sub-op, clipped
; to its visible work area), u the same text in pen 0 (clearing it), Escape
; closes and deletes all windows.
demo_win_text:                ; Y = pen
        sty N_BUFFER+4
        lda #10               ; text: handle, work cell x, y, pen, string
        sta N_BUFFER
        lda demo_handles
        sta N_BUFFER+1
        lda #1
        sta N_BUFFER+2
        lda #5                ; a row Beta covers when it is above
        sta N_BUFFER+3
        ldx #0
-       lda demo_text,x
        sta N_BUFFER+5,x
        inx
        cmp #0
        bne -
        jmp demo_wcall
demo_text: .byte 84,101,120,116,32,105,110,32,65,108,112,104,97,0   ; ASCII "Text in Alpha" (.text becomes PETSCII)
demo_windows:
        jsr demo_surface_open
        bcc +
        rts
+       lda #8                ; windows draw on this surface
        sta N_BUFFER
        ldx #3
-       lda ae_surface,x
        sta N_BUFFER+1,x
        dex
        bpl -
        jsr demo_wcall
        bcs demo_win_hide
        lda #0
        sta demo_i
demo_win_create:
        lda demo_i
        asl
        asl
        asl                   ; 8 bytes per table entry
        tay
        lda #0                ; create: kind, full rectangle
        sta N_BUFFER
        ldx #0
-       lda demo_win_table,y
        sta N_BUFFER+2,x
        iny
        inx
        cpx #6
        bne -
        jsr demo_wcall
        bcs demo_win_hide
        ldx demo_i
        lda N_BUFFER
        sta demo_handles,x
        jsr demo_win_setup    ; name and sliders while still closed
        bcs demo_win_hide
        inc demo_i
        lda demo_i
        cmp #3
        bne demo_win_create
        lda #0
        sta demo_i
-       ldx demo_i            ; open each at its full rectangle
        jsr demo_win_open
        bcs demo_win_hide
        inc demo_i
        lda demo_i
        cmp #3
        bne -
        lda #16|1
        sta ae_ev_params
        lda #1
        sta demo_waiting
demo_win_loop:
        jsr ae_event
        bcs demo_win_end
        lda ae_ev_result
        and #16
        beq demo_win_keys
        lda ae_ev_result+7
        cmp #21               ; WM_TOPPED..WM_MOVED: frame gadgets
        bcc +
        cmp #29
        bcs +
        jsr demo_win_message
        jmp demo_win_keys
+       cmp #20               ; WM_REDRAW
        bne demo_win_keys
        ldx ae_ev_result+10
        beq demo_win_keys     ; the AES already cleared the desktop
        inc demo_redraws
        lda #7                ; fill: handle, pen, colour, clip
        sta N_BUFFER
        stx N_BUFFER+1
        lda demo_pens-1,x
        sta N_BUFFER+2
        lda demo_colors-1,x
        sta N_BUFFER+3
        ldy #3
-       lda ae_ev_result+11,y
        sta N_BUFFER+4,y
        dey
        bpl -
        jsr demo_wcall
        bcs demo_win_end
        jsr demo_markers      ; content that moves with the window
        bcs demo_win_end
demo_win_keys:
        lda ae_ev_result
        and #1
        beq demo_win_loop
        lda ae_ev_result+1
        cmp #27
        beq demo_win_close_all
        cmp #$31
        bcc +
        cmp #$34
        bcs +
        sbc #$30              ; carry clear: 1..3 -> index 0..2
        tax
        lda demo_handles,x
        sta N_BUFFER+1
        lda #4
        sta N_BUFFER
        lda #10               ; WF_TOP
        sta N_BUFFER+2
        jsr demo_wcall
        jmp demo_win_loop
+       pha
        jsr demo_top          ; X = top window (0: none)
        pla
        cpx #0
        beq demo_win_loop
        cmp #$43              ; c: close
        bne +
        stx N_BUFFER+1
        lda #2
        sta N_BUFFER
        jsr demo_wcall
        jmp demo_win_loop
+       cmp #$52              ; r: record visible rectangles
        bne +
        jsr demo_win_rects
        jmp demo_win_loop
+       ldy #1                ; t: text in the first window's work area (pen 1)
        cmp #$54
        beq demo_text_key
        dey                   ; u: the same text in pen 0 clears it again
        cmp #$55
        bne +
demo_text_key:
        jsr demo_win_text
        jmp demo_win_loop
+       cmp #$4d              ; m: move by one cell right and down
        beq +
        cmp #$4c              ; l: move by one cell left and up
        beq +
        cmp #$53              ; s: grow by two columns and one row
        bne demo_win_loop
+       sta demo_math
        stx demo_math2
        lda #5
        sta N_BUFFER
        stx N_BUFFER+1
        lda #5                ; WF_CURRXYWH
        sta N_BUFFER+2
        jsr demo_wcall
        bcs demo_win_loop
        ldx #3                ; set takes x,y,w,h at [3..6]
-       lda N_BUFFER,x
        sta N_BUFFER+3,x
        dex
        bpl -
        lda demo_math
        cmp #$4c
        bne +
        dec N_BUFFER+3
        dec N_BUFFER+4
        jmp +++
+       cmp #$4d
        bne +
        inc N_BUFFER+3
        inc N_BUFFER+4
        jmp ++
+       inc N_BUFFER+5
        inc N_BUFFER+5
        inc N_BUFFER+6
+       lda #4
        sta N_BUFFER
        lda demo_math2
        sta N_BUFFER+1
        lda #5
        sta N_BUFFER+2
        jsr demo_wcall
        jmp demo_win_loop
demo_win_close_all:
        lda #0
        sta demo_i
-       ldx demo_i
        lda demo_handles,x
        sta N_BUFFER+1
        lda #2                ; close (refused when already closed)
        sta N_BUFFER
        jsr demo_wcall
        ldx demo_i
        lda demo_handles,x
        sta N_BUFFER+1
        lda #3                ; delete
        sta N_BUFFER
        jsr demo_wcall
        inc demo_i
        lda demo_i
        cmp #3
        bne -
        lda #0
demo_win_end:
        pha
        lda #0
        sta demo_waiting
        pla
demo_win_hide:
        pha
        jsr N_VCLOSE
        pla
        cmp #1
        rts
; X = table index: name and slider values of the new window.
demo_win_setup:
        lda #4                ; set name
        sta N_BUFFER
        lda demo_handles,x
        sta N_BUFFER+1
        lda #2                ; WF_NAME
        sta N_BUFFER+2
        txa
        asl
        asl
        asl
        tay
        ldx #0
-       lda demo_win_names,y
        sta N_BUFFER+3,x
        beq +
        iny
        inx
        bne -
+       jsr demo_wcall
        bcs demo_setup_done
        ldx demo_i
        lda demo_win_table+6,y ; slider position / size per window
        lda demo_i
        asl
        asl
        asl
        tay
        lda demo_win_table+6,y
        beq demo_setup_ok     ; 0: no slider settings
        sta demo_math         ; field for the position (8 h / 9 v)
        lda demo_slides,x
        jsr demo_set_field
        bcs demo_setup_done
        lda demo_math
        clc
        adc #7                ; 15 h size / 16 v size
        sta demo_math
        ldx demo_i
        lda demo_sizes,x
        jsr demo_set_field
        bcs demo_setup_done
demo_setup_ok:
        clc
demo_setup_done:
        rts
demo_set_field:
        sta N_BUFFER+3
        lda #4
        sta N_BUFFER
        ldx demo_i
        lda demo_handles,x
        sta N_BUFFER+1
        lda demo_math
        sta N_BUFFER+2
        jmp demo_wcall
; X = table index: open at the full rectangle.
demo_win_open:
        txa
        asl
        asl
        asl
        tay
        lda demo_handles,x
        sta N_BUFFER+1
        lda #1
        sta N_BUFFER
        ldx #0
-       lda demo_win_table+2,y
        sta N_BUFFER+2,x
        iny
        inx
        cpx #4
        bne -
        jmp demo_wcall
; Answer the frame gadgets as a GEM app does: the AES only reports them.
demo_win_message:
        inc demo_gadgets
        ldx ae_ev_result+10
        stx demo_math2
        stx N_BUFFER+1
        cmp #21               ; WM_TOPPED
        bne +
        lda #4
        sta N_BUFFER
        lda #10
        sta N_BUFFER+2
        jmp demo_wcall
+       cmp #22               ; WM_CLOSED
        bne +
        lda #2
        sta N_BUFFER
        jmp demo_wcall
+       cmp #23               ; WM_FULLED: full size, or back to the last
        bne demo_not_full
        lda #5
        sta N_BUFFER
        lda #7                ; WF_FULLXYWH
        sta N_BUFFER+2
        jsr demo_wcall
        ldx #3
-       lda N_BUFFER,x
        sta demo_work,x
        dex
        bpl -
        lda #5
        sta N_BUFFER
        lda demo_math2
        sta N_BUFFER+1
        lda #5                ; WF_CURRXYWH
        sta N_BUFFER+2
        jsr demo_wcall
        ldx #3
-       lda N_BUFFER,x
        cmp demo_work,x
        bne demo_to_full
        dex
        bpl -
        lda #5                ; already full: previous rectangle
        sta N_BUFFER
        lda demo_math2
        sta N_BUFFER+1
        lda #6                ; WF_PREVXYWH
        sta N_BUFFER+2
        jsr demo_wcall
        ldx #3
-       lda N_BUFFER,x
        sta demo_work,x
        dex
        bpl -
demo_to_full:
        ldx #3
-       lda demo_work,x
        sta N_BUFFER+3,x
        dex
        bpl -
        jmp demo_set_rect
demo_not_full:
        cmp #24               ; WM_ARROWED: move the slider
        bne demo_not_arrowed
        ldx ae_ev_result+11
        lda demo_steps,x
        sta demo_math
        lda #9                ; WF_VSLIDE for actions 0..3
        cpx #4
        bcc +
        lda #8                ; WF_HSLIDE for 4..7
+       sta demo_field
        ldx demo_math2
        lda demo_field
        cmp #9
        bne +
        lda demo_vpos-1,x
        jmp ++
+       lda demo_hpos-1,x
+       clc
        adc demo_math         ; signed step, clamped to 0..255
        bit demo_math
        bmi +
        bcc ++
        lda #255
        bne ++
+       bcs +
        lda #0
+       jmp demo_set_slider
demo_not_arrowed:
        cmp #25               ; WM_HSLID
        bne +
        lda #8
        sta demo_field
        lda ae_ev_result+11
        jmp demo_set_slider
+       cmp #26               ; WM_VSLID
        bne +
        lda #9
        sta demo_field
        lda ae_ev_result+11
        jmp demo_set_slider
+       ldx #3                ; WM_SIZED / WM_MOVED: take the new rectangle
-       lda ae_ev_result+11,x
        sta N_BUFFER+3,x
        dex
        bpl -
demo_set_rect:
        lda #4
        sta N_BUFFER
        lda demo_math2
        sta N_BUFFER+1
        lda #5
        sta N_BUFFER+2
        jmp demo_wcall
demo_set_slider:
        ldx demo_math2
        ldy demo_field
        cpy #9
        bne +
        sta demo_vpos-1,x
        jmp ++
+       sta demo_hpos-1,x
+       sta N_BUFFER+3
        lda #4
        sta N_BUFFER
        stx N_BUFFER+1
        lda demo_field
        sta N_BUFFER+2
        jmp demo_wcall
; Marker cells at the work area's top-left ($f2) and bottom-right ($2f):
; content positioned relative to the window, so a missing move or resize
; redraw would leave a stale marker behind.
demo_markers:
        ldx ae_ev_result+10
        stx demo_math2
        lda #5                ; get WF_WORKXYWH
        sta N_BUFFER
        stx N_BUFFER+1
        lda #4
        sta N_BUFFER+2
        jsr demo_wcall
        bcs demo_markers_done
        ldx #3
-       lda N_BUFFER,x
        sta demo_work,x
        dex
        bpl -
        lda demo_work
        ldy demo_work+1
        ldx #$f2
        jsr demo_marker
        bcs demo_markers_done
        lda demo_work
        clc
        adc demo_work+2
        sec
        sbc #1
        pha
        lda demo_work+1
        clc
        adc demo_work+3
        sec
        sbc #1
        tay
        pla
        ldx #$2f
demo_marker:                  ; A = x, Y = y, X = colour: one inked cell
        sta N_BUFFER+4
        sty N_BUFFER+5
        stx N_BUFFER+3
        lda #1
        sta N_BUFFER+6
        sta N_BUFFER+7
        sta N_BUFFER+2        ; pen 1
        lda demo_math2
        sta N_BUFFER+1
        lda #7
        sta N_BUFFER
        jmp demo_wcall
demo_markers_done:
        rts
demo_top:
        lda #5
        sta N_BUFFER
        lda #10               ; WF_TOP
        sta N_BUFFER+2
        jsr demo_wcall
        ldx N_BUFFER
        rts
demo_win_rects:
        stx N_BUFFER+1
        lda #0
        sta demo_rect_count
        lda #5
        sta N_BUFFER
        lda #11               ; WF_FIRSTXYWH
        sta N_BUFFER+2
-       jsr demo_wcall
        bcs +
        lda N_BUFFER+2
        beq +
        lda demo_rect_count
        asl
        asl
        tay
        ldx #0
-       lda N_BUFFER,x
        sta demo_rects,y
        iny
        inx
        cpx #4
        bne -
        inc demo_rect_count
        lda demo_rect_count
        cmp #16
        bcs +
        lda #5
        sta N_BUFFER
        lda #12               ; WF_NEXTXYWH
        sta N_BUFFER+2
        jmp --
+       rts
demo_wcall:
        lda #AE_OP_WINDOW
        jmp ae_call
demo_reply:
        ldx #12
-       lda N_BUFFER,x
        sta demo_status,x
        dex
        bpl -
        rts
demo_close_file:
        lda demo_file
        beq +
        ldx #3
-       lda demo_file,x
        sta N_FHANDLE,x
        dex
        bpl -
        lda #N_APPOWNER
        sta N_FOWNER
        jsr N_FCLOSE
        bcs ++
        lda #0
        sta demo_file
+       clc
+       rts

demo_draw:
        lda #0
        sta demo_screen
demo_draw_screen:
        lda $d7
        rol
        lda #0
        rol
        cmp demo_screen
        beq +
        jsr $ff5f
+       lda #$93
        jsr $ffd2
        lda #<demo_title
        ldx #>demo_title
        jsr demo_puts
        lda demo_status
        jsr demo_hex
        lda demo_status+1
        jsr demo_hex
        lda #<demo_attach_text
        ldx #>demo_attach_text
        jsr demo_puts
        lda demo_status+5
        jsr demo_hex
        lda demo_status+4
        jsr demo_hex
        lda #<demo_apps_text
        ldx #>demo_apps_text
        jsr demo_puts
        lda demo_status+7
        jsr demo_hex
        lda demo_status+6
        jsr demo_hex
        lda #<demo_loaded_text
        ldx #>demo_loaded_text
        jsr demo_puts
        lda demo_loaded
        jsr demo_hex
        lda #<demo_choice_text
        ldx #>demo_choice_text
        jsr demo_puts
        lda demo_choice
        jsr demo_hex
        lda #<demo_event_text
        ldx #>demo_event_text
        jsr demo_puts
        ldy #0
-       lda ae_ev_result,y
        jsr demo_hex_y
        iny
        cpy #7
        bne -
        lda #<demo_message_text
        ldx #>demo_message_text
        jsr demo_puts
        ldy #7
-       lda ae_ev_result,y
        jsr demo_hex_y
        iny
        cpy #15
        bne -
        lda #<demo_error_text
        ldx #>demo_error_text
        jsr demo_puts
        lda demo_error
        jsr demo_hex
        lda #<demo_help
        ldx #>demo_help
        jsr demo_puts
        inc demo_screen
        lda demo_screen
        cmp #2
        bne demo_draw_screen
        rts
demo_puts:
        sta demo_put+1
        stx demo_put+2
demo_put:
        lda $ffff
        beq +
        jsr $ffd2
        inc demo_put+1
        bne demo_put
        inc demo_put+2
        bne demo_put
+       rts
demo_hex_y:                    ; demo_hex, preserving Y
        sta demo_hex_save
        tya
        pha
        lda demo_hex_save
        jsr demo_hex
        pla
        tay
        rts
demo_hex_save: .byte 0
demo_hex:
        pha
        lsr
        lsr
        lsr
        lsr
        jsr demo_digit
        pla
        and #15
demo_digit:
        tax
        lda demo_digits,x
        jmp $ffd2
demo_file: .fill 4,0
demo_path_length: .byte 0
demo_active: .byte 0
demo_loaded: .byte 0
demo_error: .byte 0
demo_screen: .byte 0
demo_status: .fill 13,0
demo_choice: .byte 0
demo_i: .byte 0
demo_math: .byte 0
demo_math2: .byte 0
demo_redraws: .byte 0
demo_handles: .fill 3,0
demo_rect_count: .byte 0
demo_gadgets: .byte 0
demo_field: .byte 0
demo_steps: .byte $c0,$40,$f0,$10,$c0,$40,$f0,$10   ; page -64/+64, line -16/+16
demo_vpos: .byte 0,64,0
demo_hpos: .byte 0,0,200
demo_work: .fill 4,0
demo_rects: .fill 64,0
; kind (word), x, y, w, h, slider field (0 none, 8 h, 9 v), 0
demo_win_table:
        .word $000f
        .byte 1,2,20,10,0,0
        .word $01f3
        .byte 10,6,18,12,9,0
        .word $0e21
        .byte 5,14,24,8,8,0
demo_slides: .byte 0,64,200
demo_sizes: .byte 0,128,64
demo_pens: .byte 0,1,0
demo_colors: .byte $15,$b0,$3e
demo_win_names:
        .byte 65,108,112,104,97,0,0,0      ; Alpha
        .byte 66,101,116,97,0,0,0,0        ; Beta
        .byte 71,97,109,109,97,0,0,0       ; Gamma
demo_menu_title: .byte 0
demo_menu_item: .byte 0
demo_menu_count: .byte 0
demo_grid: .byte 0
demo_empty: .byte 0
demo_menu: .byte 68,101,115,107,58,65,98,111,117,116,32,65,69,83,46,46,46,59,70,105,108,101,58,78,101,119,94,78,124,79,112,101,110,46,46,46,94,79,124,45,124,81,117,105,116,94,81,59,79,112,116,105,111,110,115,58,71,114,105,100,124,83,110,97,112,0
demo_waiting: .byte 0
demo_ev_defaults: .byte 1|32,1,1,1, 0,0,0,0,0, 0,0,0,0,0, 60,0 ; keyboard or 60 jiffies
demo_message: .byte 41,0,7,0,1,2,3,4    ; AC_OPEN-style: type, 0, sender 7, data
demo_event_text: .text 13,"event (hex): ",0
demo_message_text: .text 13,"message (hex): ",0
demo_choice_text: .text 13,"alert choice (hex): $",0
demo_alert: .byte 91,51,93,91,68,101,108,101,116,101,32,78,79,84,69,83,46,84,88,84,63,124,84,104,105,115,32,99,97,110,110,111,116,32,98,101,32,117,110,100,111,110,101,46,93,91,68,101,108,101,116,101,124,67,97,110,99,101,108,93,0
demo_name: .text "aesvc.prg"
demo_digits: .text "0123456789abcdef"
demo_title: .text "aes demo",13,"version (hex): $",0
demo_attach_text: .text 13,"attaches (hex): $",0
demo_apps_text: .text 13,"apps (hex): $",0
demo_loaded_text: .text 13,"loaded here (hex): $",0
demo_error_text: .text 13,"last error (hex): $",0
demo_help: .text 13,13,"return: aes status",13
           .text "esc: exit, aes stays resident",13
           .text "u: unload aes and exit",13
           .text "a: aes alert over the vic surface",13
           .text "e: wait for events  p: post a message",13
           .text "m: menu bar over the vic surface",13
           .text "w: three aes windows",13,0
.include "aes-client.inc"
app_end:
.cerror app_end > N_APPLIMIT, "example parent exceeds its slot"
