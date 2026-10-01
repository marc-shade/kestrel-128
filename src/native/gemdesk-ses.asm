; GDSES.PRG (assembled on its own against the core's labels, gemdesk.sym,
; which build-native-desktop.py writes first; docs/NATIVE-MODULES.md).
.include "gemdesk.sym"
* = gm_module
; GDSES.PRG: the desktop's persistence away from the core: restoring the
; desktop at start (the AES session, else DESKTOP.INF) and Options:Save
; Desktop. Building and saving the session record before a launch stays in
; the core, so no module load comes between a launch's settings and the launch.
gm_ses:
        .text "nmod"
        .byte 1,1,14,0
        .word gm_ses_end-gm_ses
        .word 0
        .word ses.entry-gm_ses
        .word 0
ses .block
entry:
        lda gm_mop
        cmp #GM_MOP_RESTORE
        beq gm_restore
        jmp gm_save_desktop
gm_restore:
        jsr acc_start           ; the desk accessory first: the menu shows it
        lda #$ff                ; the AES's current double-click speed
        jsr ae_dclick
        bcs +
        sta gm_dclick
+       jsr ae_session_read
        bcs gm_restore_file
        ldx #GM_RECORD_SIZE-1
-       lda N_BUFFER,x
        sta gm_session,x
        dex
        bpl -
        jsr gm_session_valid
        bcc gm_restore_apply
gm_restore_file:
        jsr gm_load_desktop
        bcs gm_restore_color
gm_restore_apply:
        lda gm_session+4
        and #1|GM_NOCOPYASK|GM_KEYCLICK|GM_NOOVERASK|GM_BELL
        sta gm_confirm
        lda gm_session+5
        sta gm_view
        lda gm_session+6
        sta gm_desk_color
        lda gm_session+7
        sta $0a22               ; key repeat
        lda gm_session+8
        sta gm_dclick
        jsr ae_dclick
        lda gm_session+GM_REC_PRINTER   ; the printer (records saved before hold 0:
        cmp #4                          ; device 4, as the start probed)
        beq +
        cmp #5
        bne ++
+       sta gm_prt_dev
        lda gm_session+GM_REC_PRINTER+1
        and #7                  ; 7 or 0
        sta gm_prt_sa
        jsr gm_prt_probe        ; its icon; the desktop is repainted at the end
+       lda #1
        sta gm_restoring
        lda #0
        sta gm_sslot            ; record index
        lda #GM_REC_WINDOWS
        sta gm_spos
gm_restore_loop:
        lda gm_sslot
        cmp gm_session+GM_REC_COUNT
        bcs gm_restore_done
        ldy gm_spos
        lda gm_session,y
        sta gm_dev
        lda gm_session+1,y
        sta gm_fmt
        ldx #0
-       lda gm_session+2,y
        sta gm_orect,x
        iny
        inx
        cpx #4
        bne -
        jsr gm_open_drive       ; nothing opens if the drive cannot be read now
        ldx gm_slot
        lda gm_win_handle,x
        beq gm_restore_next
        jsr gm_work
        jsr gm_max_top
        ldy gm_spos
        cmp gm_session+6,y      ; the saved top row, if the listing still has it
        bcc +
        lda gm_session+6,y
+       ldx gm_slot
        sta gm_win_top,x
        lda gm_session+7,y
        cmp gm_win_count,x
        bcc +
        lda #$ff
+       jsr gm_select_set
        jsr gm_update_slider
gm_restore_next:
        lda gm_spos
        clc
        adc #8
        sta gm_spos
        inc gm_sslot
        jmp gm_restore_loop
gm_restore_done:
        lda #0
        sta gm_restoring
        jmp gm_restore_color    ; (in the core: Preferences uses it too)
; gm_session: carry clear when it is a desktop record.
gm_session_valid:
        ldx #3
-       lda gm_session,x
        cmp gm_magic,x
        bne +
        dex
        bpl -
        lda gm_session+5
        cmp #4
        bcs +
        lda gm_session+8        ; double-click speed 0..4
        cmp #5
        bcs +
        lda gm_session+GM_REC_COUNT
        cmp #GM_WINDOWS+1
        rts                     ; carry clear when at most four windows
+       sec
        rts
; DESKTOP.INF on the boot drive -> gm_session. Carry set if absent or invalid.
gm_load_desktop:
        lda #0
        jsr gm_desktop_open
        bcs gm_load_done
        lda #GM_RECORD_SIZE
        sta N_FCOUNT
        lda #0
        sta N_FCOUNT+1
        jsr gm_file_select
        jsr N_FREAD
        bcs gm_load_close       ; (closing may reuse N_BUFFER and the counts)
        ldx #GM_RECORD_SIZE-1
-       lda N_BUFFER,x
        sta gm_session,x
        dex
        bpl -
        lda N_FACTUAL+1
        bne +
        lda N_FACTUAL
        cmp #GM_REC_WINDOWS
        bcc gm_load_short
+       jsr gm_close_file
        bcs gm_load_done
        jmp gm_session_valid
gm_load_short:
        sec
gm_load_close:
        php
        jsr gm_close_file
        plp
gm_load_done:
        rts
; A = mode (0 read, 1 create): open DESKTOP.INF on the boot drive.
gm_desktop_open:
        sta N_FMODE
        lda N_CURRENT
        sta N_FOWNER
        lda N_BOOTDEVICE
        sta N_FDEVICE
        lda N_BOOTFORMAT
        sta N_FFORMAT
        ldx #10
-       lda gm_inf_name,x
        sta N_FNAME,x
        dex
        bpl -
        lda #11
        sta N_FNAMELEN
        lda #0
        sta N_FTYPE             ; SEQ
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
; Options:Save Desktop: replace DESKTOP.INF on the boot drive.
gm_save_desktop:
        jsr gm_session_build
        lda N_BOOTDEVICE        ; scratch the old one (none is not an error)
        sta dc_device
        ldx #13
-       lda gm_inf_scratch,x
        sta dc_text,x
        dex
        bpl -
        lda #14
        sta dc_length
        jsr dc_command
        bcs gm_save_error
        cmp #1
        bne gm_save_status
        lda #1                  ; create
        jsr gm_desktop_open
        bcs gm_save_error
        ldx #GM_RECORD_SIZE-1
-       lda gm_session,x
        sta N_BUFFER,x
        dex
        bpl -
        lda #GM_RECORD_SIZE
        sta N_FCOUNT
        lda #0
        sta N_FCOUNT+1
        jsr gm_file_select
        jsr N_FWRITE
        bcs gm_save_write_error
        jsr gm_close_file       ; a failed close is an error too
        bcs gm_save_error
        rts
gm_save_write_error:
        pha
        jsr gm_close_file
        pla
gm_save_error:                  ; "[3][Could not save the|desktop: error $xx][OK]"
        pha
        lda #<gm_s_nosave
        ldx #>gm_s_nosave
        pha
        lda #0
        sta gm_alen
        pla
        jsr gm_astr
        jmp gm_error_hex
gm_save_status:
        lda #<gm_s_nosave
        ldx #>gm_s_nosave
        pha
        lda #0
        sta gm_alen
        pla
        jsr gm_astr
        jmp gm_status_text

.bend
; ---- the desk accessory (docs/GEM-LAYER-DESIGN.md#desk-accessories) --------------
; DESK1.ACC beside this program: adopted when already resident (owner 29 at
; bank-1 AC_BASE), else loaded; then installed in the AES and the menu is
; installed again so the Desk menu lists it. No DESK1.ACC: no accessory. A
; file that cannot be loaded is reported, and no partial image is kept.
acc_start:
        jsr dacc.bk_attach
        bcc acc_install
        cmp #N_BADHANDLE
        beq +
        jmp acc_failed
+       ldx #8                  ; gm_open_aesvc opens the name in gm_aesvc_name
-       lda gm_aesvc_name,x
        sta acc_saved,x
        lda acc_name,x
        sta gm_aesvc_name,x
        dex
        bpl -
        jsr gm_open_aesvc
        php
        ldx #8
-       lda acc_saved,x
        sta gm_aesvc_name,x
        dex
        bpl -
        plp
        bcs acc_none            ; none there (or unreadable): no accessory
        jsr dacc.bk_load
        php
        pha
        lda dacc.bk_file        ; zero: refused before taking the stream
        ora dacc.bk_state
        bne +
        jsr gm_close_file
+       pla
        plp
        bcc acc_install
        pha
        lda dacc.bk_state       ; never keep a partial image
        beq +
        jsr dacc.bk_close
+       pla
        jmp acc_failed
acc_install:
        lda #1
        sta N_BUFFER
        lda #AE_OP_ACC
        jsr ae_call
        bcs acc_failed
        lda #<gm_menu
        ldx #>gm_menu
        jmp ae_menu_install
acc_none:
        rts
acc_failed:                     ; "[3][Could not load|DESK1.ACC: error $xx][OK]"
        pha
        lda #0
        sta gm_alen
        lda #<acc_s_failed
        ldx #>acc_s_failed
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
        lda #<gm_s_ok
        ldx #>gm_s_ok
        jsr gm_astr
        lda #0
        jsr gm_aput
        lda #<gm_abuf
        ldx #>gm_abuf
        ldy #1
        jmp gm_alert
acc_name: .byte 68,69,83,75,49,46,65,67,67
acc_saved: .fill 9,0
acc_s_failed: .byte 91,51,93,91,67,111,117,108,100,32,110,111,116,32,108,111,97,100,124,68,69,83,75,49,46,65,67,67,58,32,101,114,114,111,114,32,36,0
dacc .block                     ; the accessory's loader: owner 29 at bank-1 AC_BASE
BK_BASE = AC_BASE
BK_LIMIT = AC_BASE+AC_PAGES*256
BK_OWNER = N_ACCOWNER
.include "banked.inc"
.include "banked-load.inc"
bk_identity: .text "nacc"
        .byte 1
.bend
gm_ses_end:
.cerror gm_ses_end > N_APPBASE+GM_APP_PAGES*256, "GDSES.PRG exceeds the module window: ", gm_ses_end
