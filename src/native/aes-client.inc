; Bank-0 client for the persistent AES component (docs/GEM-LAYER-DESIGN.md).
; Include once in the retained app core after api.inc and aes-api.inc. It is a
; second, block-scoped executor instance: owner 30, bank-1 AE_BASE..AE_LIMIT.
;
; ae_attach  adopt a resident AES and register this app (op AE_OP_ATTACH).
;            Carry set with A=N_BADHANDLE means none is resident: open the
;            AESVC.PRG stream as owner 32 and call ae_load instead.
; ae_load    load AESVC.PRG from the stream in N_FHANDLE, then register.
; ae_call    A = operation; packet in N_BUFFER; returns the AES's A/carry.
; ae_detach  forget the attachment; the AES stays resident for the next app.
; ae_unload  free the AES image (owner 30) so its pages return to the heap.
; On success of attach/load, N_BUFFER holds the AE_OP_ATTACH reply.
; After ae_load, ae_stream_taken tells whether the caller still owns its stream.
aes .block
BK_BASE = AE_BASE
BK_LIMIT = AE_LIMIT
BK_OWNER = N_AESOWNER
.include "banked.inc"
.include "banked-load.inc"
bk_identity: .text "naes"
        .byte AE_MAJOR
.bend
ae_call = aes.bk_call
ae_detach = aes.bk_detach
ae_unload:                      ; free the data segment, then the image
        lda #AE_OP_SHUTDOWN
        jsr aes.bk_call
        bcc +
        rts
+       jmp aes.bk_close
ae_callback = aes.bk_callback  ; patched into AE_BASE+22 on attach/load
ae_state = aes.bk_state
ae_attach:
        jsr aes.bk_attach
        bcc ae_register
        rts
ae_load:
        jsr aes.bk_load
        php
        pha
        lda aes.bk_file         ; nonzero: the loader took the caller's stream,
        ora aes.bk_state        ; which it closes; zero: preflight refused and
        sta ae_stream_taken     ; the caller still owns and must close it
        pla
        plp
        bcc ae_register
        pha                     ; an owner-30 image outlives this app: never
        lda aes.bk_state        ; leave a partial one behind after a failure
        beq +
        jsr aes.bk_close        ; carry set here keeps state 1 for a retry
+       pla
        sec
        rts
; The executor's parent cookie (app slot + allocation generation) identifies
; the foreground app to the AES, which discards per-app state on a change.
ae_register:
        ldx #3
-       lda aes.bk_cookie,x
        sta N_BUFFER,x
        dex
        bpl -
        lda #AE_OP_ATTACH
        jmp aes.bk_call
ae_stream_taken: .byte 0

; Alerts (AES minor 1). Set ae_surface to the app's VIC surface handle.
; ae_alert_open: A/X = NUL-terminated ASCII "[icon][l1|l2][b1|b2]", Y = default
; button (0..3). ae_alert_step: A = key (0 none); pointer in ae_pointer_x/y and
; ae_pointer_buttons. Both reply in N_BUFFER: chosen (0 while open), focus,
; four dirty-row bytes to merge into a VDC mirror.
ae_alert_open:
        sta ae_alert_read+1
        stx ae_alert_read+2
        sty N_BUFFER+4
        ldx #3
-       lda ae_surface,x
        sta N_BUFFER,x
        dex
        bpl -
        ldy #0
ae_alert_read:
        lda $ffff,y
        sta N_BUFFER+5,y
        beq +
        iny
        bne ae_alert_read
        lda #N_BADARG           ; no terminator within 255 bytes
        sec
        rts
+       lda #AE_OP_ALERT
        jmp ae_call
ae_alert_step:
        sta N_BUFFER
        lda ae_pointer_x
        sta N_BUFFER+1
        lda ae_pointer_x+1
        sta N_BUFFER+2
        lda ae_pointer_y
        sta N_BUFFER+3
        lda ae_pointer_buttons
        sta N_BUFFER+4
        lda #AE_OP_STEP
        jmp ae_call

; Events (AES minor 2). Fill ae_ev_params with packet bytes 0..15 (mask,
; clicks, button mask/state, two rectangles, timer), then ae_event waits
; until something fires, polling N_KEYIN, the pointer and the jiffy clock.
; The pointer comes from pm_poll when the app sets AE_POINTER=1 and includes
; the pointer module, otherwise from ae_pointer_*. Result: ae_ev_result.
; ae_post: N_BUFFER 0..7 = message; carry set with N_NOMEM when the queue
; (16 messages) is full.
        .weak
AE_POINTER = 0
AE_MIRROR = 0                   ; 1: the app supplies ae_present (a VDC mirror)
AE_CLICK_TICKS = 48             ; > the AES's longest double-click window (40)
        .endweak
ae_event:
        lda #1                  ; the first sample is taken at the call itself:
        sta ae_ev_first         ; the timer and button state start from now
        lda #0
        sta ae_ev_key
        beq ae_event_sample
ae_event_next:
        jsr ae_event_wait
.if AE_POINTER
        jsr ae_key_mouse
.fi
ae_event_sample:
.if AE_POINTER
        jsr ae_read_pointer
        ldx ae_km_click         ; a keyboard click: pressed for one sample
        beq +
        dec ae_km_click
        beq +
        lda #1
        sta ae_pointer_buttons
+       lda ae_km_hold          ; the keyboard's held button (drag lock)
        ora ae_pointer_buttons
        sta ae_pointer_buttons
.else
        ldx #3                  ; what the idle wait compares against
-       lda ae_pointer_x,x
        sta ae_ev_seen,x
        dex
        bpl -
.fi
        lda ae_pointer_buttons  ; a press: clicks may count for the longest
        beq +                   ; double-click window, which needs ticks
        lda #AE_CLICK_TICKS
        sta ae_ev_window
+       ldx #15
-       lda ae_ev_params,x
        sta N_BUFFER,x
        dex
        bpl -
        lda ae_ev_key
        sta N_BUFFER+16
        lda ae_pointer_x
        sta N_BUFFER+17
        lda ae_pointer_x+1
        sta N_BUFFER+18
        lda ae_pointer_y
        sta N_BUFFER+19
        lda ae_pointer_buttons
        sta N_BUFFER+20
        php
        sei                     ; one consistent reading of the jiffy clock
        lda $a0
        sta N_BUFFER+21
        lda $a1
        sta N_BUFFER+22
        lda $a2
        sta N_BUFFER+23
        plp
        lda ae_ev_first
        sta N_BUFFER+24
        lda #0
        sta ae_ev_first
        lda #AE_OP_EVENT
        jsr ae_call
        bcs ae_event_done
        ldx #3
-       lda N_BUFFER+15,x       ; rows the menu redrew, kept for a VDC mirror
        ora ae_dirty,x
        sta ae_dirty,x
        dex
        bpl -
        lda N_BUFFER
.if AE_MIRROR
        bne ae_event_fired
        lda N_BUFFER+15         ; nothing fired, but a menu redrew rows: the app
        ora N_BUFFER+16         ; presents them (N_BUFFER is free again here)
        ora N_BUFFER+17
        ora N_BUFFER+18
        beq +
        jsr ae_present
+       jmp ae_event_next
ae_event_fired:
.else
        beq ae_event_next
.fi
        ldx #18
-       lda N_BUFFER,x
        sta ae_ev_result,x
        dex
        bpl -
        lda #0                  ; A = 0 on success, like every client entry
        clc
ae_event_done:
        rts
; The input wait between samples, also for an app's own alert loop. N_READY
; stays published and no AES call is made until something can change the
; result: a key, a keyboard click still counting, a 1351 read that moved the
; pointer or changed the button (AE_POINTER=1) or changed ae_pointer_*
; (AE_POINTER=0), or a jiffy tick while MU_TIMER is requested or a click may
; still be counting. A = ae_ev_key = the key or 0. Each sample is a banked
; call: a loop sampling on every pass was at its input wait 2% of the time on
; the C128, and one sampling on every tick stays in phase with VICE's monitor.
ae_event_wait:
        lda #1                  ; published for the whole wait (N_KEYIN clears
        sta N_READY             ; it for a key; pm_poll while it reads the port)
        jsr N_KEYIN
        sta ae_ev_key
        tax
        bne ae_wait_done
.if AE_POINTER
        lda ae_km_click
        bne ae_wait_done
        lda pm_pending          ; the 1351 read starts in raster lines 80..159
        pha                     ; and completes 32 lines later: drive it here
        jsr pm_poll
        pla
        beq ae_wait_time
        lda pm_pending
        bne ae_wait_time
        ldx #2                  ; a read completed: did the pointer move?
ae_wait_moved:
        lda pm_x,x
        cmp ae_pointer_x,x
        bne ae_wait_done
        dex
        bpl ae_wait_moved
        lda pm_buttons
        ora ae_km_hold
        beq +
        lda #1
+       cmp ae_pointer_buttons
        bne ae_wait_done
.else
        ldx #3
-       lda ae_pointer_x,x
        cmp ae_ev_seen,x
        bne ae_wait_done
        dex
        bpl -
.fi
ae_wait_time:
        lda ae_ev_params
        and #MU_TIMER
        bne +
        lda ae_ev_window
        beq ae_event_wait
+       lda $a2                 ; the jiffy clock's low byte
        cmp ae_ev_tick
        beq ae_event_wait
        lda ae_ev_window
        beq ae_wait_done
        dec ae_ev_window
ae_wait_done:
        ldx #0                  ; leaving the wait: a sample follows
        stx N_READY
        lda $a2
        sta ae_ev_tick
        lda ae_ev_key
        rts
.if AE_POINTER
; ae_pointer_* from the 1351 module (also for an app's own alert loop).
ae_read_pointer:
        jsr pm_poll
        lda pm_x
        sta ae_pointer_x
        lda pm_x+1
        sta ae_pointer_x+1
        lda pm_y
        sta ae_pointer_y
        lda pm_buttons          ; the 1351 module reports the left button
        beq +                   ; as $10; the AES expects bit 0
        lda #1
+       sta ae_pointer_buttons
        rts
.fi
.if AE_POINTER
; Keyboard mouse (TOS: Alt+cursor): with ALT or C= held, the cursor keys move
; the pointer 8 pixels and Return clicks; with Shift too, Return holds the
; button down until it is pressed again (a drag from the keyboard, as TOS's
; held Alt+Insert). The key itself is not delivered.
ae_key_mouse:
        lda ae_ev_key
        beq ae_km_done
        lda $d3                 ; KERNAL SHFLAG: 2 C=, 8 ALT
        and #$0a
        beq ae_km_done
        lda ae_ev_key
        ldx #3
-       cmp ae_km_keys,x
        beq ae_km_move
        dex
        bpl -
        cmp #13
        bne ae_km_done
        lda $d3
        lsr                     ; Shift: hold, or release, the button
        bcc +
        lda ae_km_hold
        eor #1
        sta ae_km_hold
        bpl ae_km_eaten
+       lda #2                  ; pressed on the next sample, released after it
        sta ae_km_click
        bne ae_km_eaten
ae_km_move:
        lda ae_km_dx,x
        beq ae_km_y
        bmi ae_km_left
        lda pm_x                ; right, at most 319
        clc
        adc #8
        sta pm_x
        bcc +
        inc pm_x+1
+       lda pm_x+1
        beq ae_km_y
        lda pm_x
        cmp #<320
        bcc ae_km_y
        lda #<319
        sta pm_x
        bne ae_km_y
ae_km_left:
        lda pm_x                ; left, at least 0
        sec
        sbc #8
        sta pm_x
        bcs ae_km_y
        dec pm_x+1
        bpl ae_km_y
        lda #0
        sta pm_x
        sta pm_x+1
ae_km_y:
        lda ae_km_dy,x
        beq ae_km_eaten
        bmi ae_km_up
        lda pm_y                ; down, at most 199
        clc
        adc #8
        cmp #200
        bcc ae_km_set_y
        lda #199
        bne ae_km_set_y
ae_km_up:
        lda pm_y                ; up, at least 0
        sec
        sbc #8
        bcs ae_km_set_y
        lda #0
ae_km_set_y:
        sta pm_y
ae_km_eaten:
        lda #0
        sta ae_ev_key
ae_km_done:
        rts
ae_km_keys: .byte $91,$11,$9d,$1d ; up, down, left, right
ae_km_dx: .byte 0,0,$f8,8
ae_km_dy: .byte $f8,8,0,0
ae_km_click: .byte 0
ae_km_hold: .byte 0
.fi
ae_post:
        lda #AE_OP_POST
        jmp ae_call

; Menu bar (AES minor 3). ae_menu_install: A/X = NUL-terminated ASCII spec
; "Title:item|item^K|-|item;Title:..." (at most 507 bytes), drawn on cell row
; 0 of ae_surface; an empty spec removes the menu. Choices arrive as
; MN_SELECTED (10) messages: byte 3 title, byte 4 item. ae_menu_set: A =
; title, X = item, Y = flags (1 checked, 2 disabled).
ae_menu_install:
        sta ae_menu_read+1
        stx ae_menu_read+2
        ldx #3
-       lda ae_surface,x
        sta N_BUFFER,x
        dex
        bpl -
        lda #<(N_BUFFER+4)
        sta ae_menu_write+1
        lda #>(N_BUFFER+4)
        sta ae_menu_write+2
ae_menu_read:
        lda $ffff
ae_menu_write:
        sta N_BUFFER+4
        beq ae_menu_copied
        inc ae_menu_read+1
        bne +
        inc ae_menu_read+2
+       inc ae_menu_write+1
        bne +
        inc ae_menu_write+2
+       lda ae_menu_write+2
        cmp #>(N_BUFFER+512)
        bcc ae_menu_read
        lda #N_BADARG           ; no terminator inside the packet
        sec
        rts
ae_menu_copied:
        lda #AE_OP_MENU
        jmp ae_call
ae_menu_set:
        sta N_BUFFER
        stx N_BUFFER+1
        sty N_BUFFER+2
        lda #AE_OP_MENU_SET
        jmp ae_call
; Session record (AES minor 5): 256 bytes in N_BUFFER. Carry set on error.
ae_session_read:
        lda #0
        beq +
ae_session_write:
        lda #1
+       sta N_BUFFER+256
        lda #AE_OP_SESSION
        jmp ae_call
; evnt_dclick (AES minor 6): A = speed 0..4 to set, or $ff to read. A = speed.
ae_dclick:
        ldx #0
        cmp #$ff
        beq +
        sta N_BUFFER+1
        inx
+       stx N_BUFFER
        lda #AE_OP_DCLICK
        jsr ae_call
        bcs +
        lda N_BUFFER
+       rts
ae_dirty: .fill 4,0             ; OR of redrawn cell rows; the app clears it
ae_ev_params: .fill 16,0
ae_ev_result: .fill 19,0
ae_ev_key: .byte 0
ae_ev_first: .byte 0
ae_ev_tick: .byte 0             ; the jiffy low byte when the wait last returned
ae_ev_window: .byte 0           ; ticks a click may still be counting
.if !AE_POINTER
ae_ev_seen: .fill 4,0           ; ae_pointer_x/y/buttons of the last sample
.fi
ae_surface: .fill 4,0
ae_pointer_x: .word 0
ae_pointer_y: .byte 0
ae_pointer_buttons: .byte 0
