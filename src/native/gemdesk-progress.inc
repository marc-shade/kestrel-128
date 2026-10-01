; A progress window for a GEMDESK module (docs/GEM-DESKTOP.md): a title-only
; window whose title the module writes with progress_text (into gm_abuf,
; 0-terminated, at most 16 characters). Included inside a module's block.
; progress_open creates and opens it (with no window free, the work goes on
; without one); progress_title sets the title again; progress_close closes and
; deletes it, then lets the desktop answer the redraws that queued, so the next
; alert saves an up-to-date picture. Painting reuses the desktop's row buffers
; (gm_rows, gm_rec, gm_slot), so a module closes it only when its own work no
; longer needs them.
PW_X = 7
PW_Y = 10
PW_W = 26
PW_H = 3
progress_open:
        lda #WS_CREATE
        sta N_BUFFER
        lda #<WK_NAME
        sta N_BUFFER+2
        lda #>WK_NAME
        sta N_BUFFER+3
        jsr pw_rect             ; (the full size: the rectangle it opens at)
        jsr gm_wcall
        bcs pw_none             ; no window free: the copy goes on without one
        lda N_BUFFER
        sta pw
        jsr progress_title
        lda #WS_OPEN
        jsr pw_call
        jsr pw_rect_at_2
        jsr gm_wcall
        lda #WS_FILL            ; its work row: paper
        jsr pw_call
        lda #0
        sta N_BUFFER+2
        lda #GM_PAPER
        sta N_BUFFER+3
        jsr pw_rect
        jsr gm_wcall
        jmp ae_present
pw_none:
        rts
pw_call:                        ; A = sub-op on the progress window
        sta N_BUFFER
        lda pw
        sta N_BUFFER+1
        rts
pw_rect_at_2:                   ; the rectangle at N_BUFFER+2..5
        ldx #0
        .byte $2c               ; (bit abs: skips the next ldx)
pw_rect:                        ; the rectangle at N_BUFFER+4..7
        ldx #2
        lda #PW_X
        sta N_BUFFER+2,x
        lda #PW_Y
        sta N_BUFFER+3,x
        lda #PW_W
        sta N_BUFFER+4,x
        lda #PW_H
        sta N_BUFFER+5,x
        rts
progress_title:
        lda pw
        beq pw_none
        jsr progress_text
        lda #WS_SET
        jsr pw_call
        lda #WF_NAME
        sta N_BUFFER+2
        ldx #0
-       lda gm_abuf,x
        sta N_BUFFER+3,x
        inx
        cpx gm_alen
        bne -
        jsr gm_wcall
        jmp ae_present
; Close it, and let the desktop answer the redraws its closing queued, so the
; next alert saves an up-to-date picture.
progress_close:
        lda pw
        beq pw_none
        lda #WS_CLOSE
        jsr pw_call
        jsr gm_wcall
        lda #WS_DELETE
        jsr pw_call
        jsr gm_wcall
        lda #0
        sta pw
pw_drain:
        lda #MU_MESAG|MU_TIMER
        sta ae_ev_params
        lda #0
        sta ae_ev_params+14
        sta ae_ev_params+15
        jsr ae_event
        bcs +
        lda ae_ev_result
        and #MU_MESAG
        beq +
        jsr gm_message
        jmp pw_drain
+       lda #0                  ; no timer left for the next wait: an alert's
        sta ae_ev_params        ; wait would otherwise wake on every jiffy
        jmp ae_present
pw: .byte 0                     ; the progress window's handle, 0 when none
