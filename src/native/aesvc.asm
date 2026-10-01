; AESVC.PRG: persistent AES component, bank 1 AE_BASE, owner 30.
; Step 1 of docs/GEM-LAYER-DESIGN.md: identity, attach and status. The image
; stays resident across app exits, so its own bytes carry the session state.
.include "api.inc"
.include "aes-api.inc"
BK_BASE = AE_BASE
gfx_heap_read = aes_heap_read  ; the graphics library calls back to bank 0
gfx_heap_write = aes_heap_write
gfx_heap_fill = aes_heap_fill
* = BK_BASE
aes_image:
        .text "nbk1"
        .byte 1,1,14,0
        .word aes_end-aes_image
        .byte (aes_end-aes_image+255)/256,1
        .word aes_entry-aes_image,0
        ldx #$0e
        jmp $02ab             ; checked common STX $ff00 / RTS
        .byte 0
        .word 0               ; each attaching app patches its callback here
        .fill 8,0
aes_identity:                 ; image offset 32, checked by bk_attach
        .text "naes"
        .byte AE_MAJOR,AE_MINOR
        .byte AE_CAP_ALERT|AE_CAP_EVENT|AE_CAP_MENU|AE_CAP_WINDOW|AE_CAP_SESSION|AE_CAP_DCLICK|AE_CAP_ACC ; capability bits
        .byte 0
        .cerror aes_identity-aes_image != 32, "AES identity must be at offset 32"
aes_exports:                  ; image offset 40: what a desk accessory calls
        .word aes_entry         ; operations, as through the gate
        .word ac_menu_add       ; A/X = an item's text while the menu is parsed
        .word ev_msg_in         ; the message being queued
        .cerror aes_exports-aes_image != 40, "AES exports must be at offset 40"

; A = operation. Packets in N_BUFFER; results in A/carry.
aes_entry:
        cmp #AE_OP_COUNT
        bcs aes_badarg
        cmp #AE_OP_SHUTDOWN
        bne +
        jmp aes_shutdown
+       cmp #AE_OP_STATUS
        beq +
        pha
        jsr aes_ensure_data     ; every other op uses the data segment
        pla
        bcc +
        rts
+
        cmp #AE_OP_ALERT
        bne +
        jmp al_open
+       cmp #AE_OP_STEP
        bne +
        jmp al_step
+       cmp #AE_OP_EVENT
        bne +
        jmp ev_event
+       cmp #AE_OP_POST
        bne +
        jmp ev_post
+       cmp #AE_OP_MENU
        bne +
        jmp mn_install
+       cmp #AE_OP_MENU_SET
        bne +
        jmp mn_set
+       cmp #AE_OP_WINDOW
        bne +
        jmp wn_entry
+       cmp #AE_OP_SESSION
        bne +
        jmp aes_session
+       cmp #AE_OP_DCLICK
        bne +
        jmp aes_dclick
+       cmp #AE_OP_ACC
        bne +
        jmp aes_acc
+       cmp #AE_OP_ATTACH
        bne aes_reply
        ldx #3
-       lda N_BUFFER,x        ; a different cookie means a different app
        cmp aes_app,x
        bne aes_new_app
        dex
        bpl -
        lda #0
        beq aes_count
aes_new_app:
        ldx #3
-       lda N_BUFFER,x
        sta aes_app,x
        dex
        bpl -
        inc aes_apps
        bne +
        inc aes_apps+1
+       jsr al_discard        ; the previous app's surface is gone
        jsr ev_reset          ; and so are its queued messages
        jsr mn_reset          ; and its menu bar
        jsr wn_reset          ; and its windows (an accessory's too)
        jsr ac_reset          ; the accessory forgets them
        lda #1
aes_count:
        sta aes_changed
        inc aes_attaches
        bne aes_reply
        inc aes_attaches+1
; Reply: major, minor, capabilities, 0, attaches (word), distinct apps
; (word), 1 when this attach changed the foreground app, current app cookie.
aes_reply:
        ldx #12
-       lda aes_state,x
        sta N_BUFFER,x
        dex
        bpl -
        lda #0
        clc
        rts
aes_badarg:
        lda #N_BADARG
        sec
        rts

aes_state:
        .byte AE_MAJOR,AE_MINOR,AE_CAP_ALERT|AE_CAP_EVENT|AE_CAP_MENU|AE_CAP_WINDOW|AE_CAP_SESSION|AE_CAP_DCLICK|AE_CAP_ACC,0
aes_attaches: .word 0
aes_apps: .word 0
aes_changed: .byte 0
aes_app: .fill 4,0
aes_heap_read:
        lda #2
        jmp bk_native
aes_heap_write:
        lda #3
        jmp bk_native
aes_heap_fill:
        lda #4
        jmp bk_native
; Reserve and clear the RAM-table segment once; it outlives apps like the
; image. Carry set with the heap's error when the pages are taken.
aes_ensure_data:
        lda aes_data_ok
        bne aes_data_ready
        lda #N_AESOWNER
        sta N_OWNER
        lda #1
        sta N_BANK
        lda #>AE_DATA
        sta N_PAGE
        lda #AE_DATA_PAGES
        sta N_PAGES
        lda #7                  ; N_RESERVE
        jsr bk_native
        bcs aes_data_done
        ldx #3
-       lda N_HANDLE,x
        sta aes_data_handle,x
        dex
        bpl -
        lda #<AE_DATA           ; bank-1 code addresses it directly
        sta aes_clear+1
        lda #>AE_DATA
        sta aes_clear+2
        ldy #AE_DATA_PAGES
        lda #0
        tax
aes_clear:
        sta AE_DATA,x
        inx
        bne aes_clear
        inc aes_clear+2
        dey
        bne aes_clear
        lda #1
        sta aes_data_ok
aes_data_ready:
        clc
aes_data_done:
        rts
; SHUTDOWN: release overlays and the data segment before the image is freed.
aes_shutdown:
        lda aes_data_ok
        beq +
        jsr mn_close            ; restores an open drop-down on the app surface
        bcs aes_data_done
        jsr al_discard
        lda #N_AESOWNER
        sta N_OWNER
        ldx #3
-       lda aes_data_handle,x
        sta N_HANDLE,x
        dex
        bpl -
        lda #1                  ; N_FREE
        jsr bk_native
        bcs aes_data_done
        lda #0
        sta aes_data_ok
        sta mn_titles
        sta wn_count
+       lda #0
        clc
        rts
; SESSION: a 256-byte record that outlives app changes (cleared only when the
; data segment is first reserved), so a desktop can restore itself on return.
aes_session:
        ldx #0
        lda N_BUFFER+256
        bne aes_session_write
-       lda aes_session_record,x
        sta N_BUFFER,x
        inx
        bne -
        lda #0
        clc
        rts
aes_session_write:
        cmp #1
        bne aes_session_bad
-       lda N_BUFFER,x
        sta aes_session_record,x
        inx
        bne -
        lda #0
        clc
        rts
aes_session_bad:
        jmp aes_badarg
; DCLICK (evnt_dclick): the double-click window, speed 0 (slow) .. 4 (fast).
; Kept in the image, so it outlives app changes like the desktop colour.
aes_dclick:
        lda N_BUFFER
        beq aes_dclick_get
        cmp #1
        bne aes_session_bad
        ldx N_BUFFER+1
        cpx #5
        bcs aes_session_bad
        stx aes_dclick_speed
        lda aes_dclick_jiffies,x
        sta ev_dclick
aes_dclick_get:
        lda aes_dclick_speed
        sta N_BUFFER
        lda #0
        clc
        rts
aes_dclick_jiffies: .byte 40,30,20,15,10
; ACC: 1 installs the desk accessory image at AC_BASE (identity "nacc" 1 at
; offset 32, entries menu/message/dispatch/reset at 40), 0 removes it. The
; image is the loading app's business (owner N_ACCOWNER); only the entries
; are kept here, and they stay across app changes.
aes_acc:
        lda N_BUFFER
        beq aes_acc_remove
        cmp #1
        bne aes_acc_bad
        ldx #4
-       lda AC_BASE+32,x
        cmp aes_acc_identity,x
        bne aes_acc_bad
        dex
        bpl -
        ldx #0
        ldy #0
-       lda AC_BASE+40,y
        sta ac_menu+1,x
        lda AC_BASE+41,y
        sta ac_menu+2,x
        inx
        inx
        inx
        iny
        iny
        cpy #8
        bne -
        lda #0
        clc
        rts
aes_acc_bad:
        jmp aes_badarg
aes_acc_remove:
        ldx #9
-       lda #<ac_none
        sta ac_menu+1,x
        lda #>ac_none
        sta ac_menu+2,x
        dex
        dex
        dex
        bpl -
        lda #0
        clc
        rts
aes_acc_identity: .text "nacc"
        .byte 1
; The accessory's entries (defaults: nothing to do, carry clear).
ac_menu: jmp ac_none            ; the first title's items are parsed
ac_message: jmp ac_none         ; ev_msg_in is about to be queued; carry set takes it
ac_dispatch: jmp ac_none        ; the reply of a sample is in N_BUFFER
ac_reset: jmp ac_none           ; a new app: every window is gone
ac_none:
        clc
        rts
aes_dclick_speed: .byte 2
ev_dclick: .byte 20             ; jiffies (speed 2), read by the event step
aes_data_ok: .byte 0
aes_data_handle: .fill 4,0
        .section aesdata
aes_session_record: .fill 256
        .send aesdata
.include "banked-client.inc"
.include "aes-alert.inc"
.include "aes-event.inc"
.include "aes-menu.inc"
.include "aes-window.inc"
.include "graphics/graphics-core.inc"
.include "graphics/text-core.inc"
aes_end:
.cerror aes_end > AE_LIMIT, "AES exceeds its bank-1 region"
        .virtual AE_DATA
aes_data:
        .dsection aesdata
aes_data_end:
        .endv
.cerror aes_data_end > AE_DATA+AE_DATA_PAGES*256, "AES RAM tables exceed the data segment"
