; GDDLG.PRG (assembled on its own against the core's labels, gemdesk.sym,
; which build-native-desktop.py writes first; docs/NATIVE-MODULES.md).
.include "gemdesk.sym"
* = gm_module
gm_dlg:
        .text "nmod"
        .byte 1,1,14,0
        .word gm_dlg_end-gm_dlg
        .word 0
        .word dlg.entry-gm_dlg
        .word 0
dlg .block
entry:
        ldx #3                  ; forms draw on the desktop's surface
-       lda gm_surface,x
        sta fo_surface,x
        dex
        bpl -
        jmp gm_info_dialog
; File:Show Info on an entry: name (editable), type and blocks, read-only
; (changeable). OK with a changed name renames the file on the drive; with
; Read-only changed it leaves the lock to set, by the name the file then has,
; in gm_lock_want/gm_lock_name, which the core hands to GDDSK afterwards (a
; module cannot load another). A failed rename withdraws it.
gm_info_dialog:
        ldx #0                  ; the name into the field
-       lda gm_rec,x
        cmp #$a0
        beq +
        sta gm_name_buf,x
        inx
        cpx #16
        bne -
+       stx gm_name_field
        lda #0
        sta gm_name_buf,x
        sta gm_alen             ; "Type: SEQ  Blocks: 1"
        jsr gm_atype
        ldx gm_alen
        lda #0
        sta gm_abuf,x
        ldx #0
-       lda gm_abuf,x
        sta gm_info_line,x
        beq +
        inx
        bne -
+       lda gm_rec+17           ; read-only: the lock bit of its type
        and #$40
        beq +
        lda #FOS_SELECTED
+       sta gm_info_form+5+4*8+2
        lda #<gm_info_form
        ldx #>gm_info_form
        jsr gm_form
        bcs gm_dialog_fail
        cmp #5                  ; OK
        bne gm_dialog_done
        lda gm_rec+17
        and #$40
        sta gm_listed_lock
        lda gm_info_form+5+4*8+2
        lsr
        lda #0
        bcc +
        lda #$40
+       cmp gm_listed_lock
        beq gm_info_name
        ora #$80                ; Read-only changed: the lock to set, and the name
        sta gm_lock_want
        ldx #15
-       lda #$a0
        cpx gm_name_field
        bcs +
        lda gm_name_buf,x
+       sta gm_lock_name,x
        dex
        bpl -
gm_info_name:
        ldx #0                  ; the same name: nothing to do
-       cpx gm_name_field
        beq +
        lda gm_name_buf,x
        cmp gm_rec,x
        bne gm_rename
        inx
        bne -
+       cpx #16
        beq gm_dialog_done
        lda gm_rec,x
        cmp #$a0
        bne gm_rename
gm_dialog_done:
        rts
gm_dialog_fail:
        jmp gm_view_fail
; Rename: "R0:NEW=OLD" to the window's drive, then list it again.
gm_rename:
        lda gm_name_field
        beq gm_rename_bad
        ldy #3
        ldx #0
-       lda gm_name_buf,x       ; the new name
        jsr gm_dos_char
        bcs gm_rename_bad
        sta dc_text,y
        iny
        inx
        cpx gm_name_field
        bne -
        lda #$3d                ; =
        sta dc_text,y
        iny
        ldx #0
-       lda gm_rec,x            ; the old name
        cmp #$a0
        beq +
        jsr gm_dos_char
        bcs gm_rename_bad
        sta dc_text,y
        iny
        inx
        cpx #16
        bne -
+       sty dc_length
        lda #$52                ; R0:
        sta dc_text
        lda #$30
        sta dc_text+1
        lda #$3a
        sta dc_text+2
        ldx gm_slot
        lda gm_win_dev,x
        sta dc_device
        sta gm_dev
        lda gm_win_fmt,x
        sta gm_fmt
        jsr dc_command
        bcs gm_rename_error
        cmp #0
        bne gm_rename_status
        jmp gm_refresh_drive
gm_rename_bad:
        jsr gm_lock_withdraw
        jmp gm_del_badname
gm_rename_error:
        pha
        jsr gm_lock_withdraw
        lda #<gm_s_norename
        ldx #>gm_s_norename
        jsr gm_fail_head
        jmp gm_error_hex
gm_rename_status:
        jsr gm_lock_withdraw
        lda #<gm_s_norename
        ldx #>gm_s_norename
        jsr gm_fail_head
        jmp gm_status_text
gm_lock_withdraw:               ; the name did not change: no lock either
        lda #0
        sta gm_lock_want
        rts
gm_listed_lock: .byte 0
; A = name byte: carry set for DOS syntax characters. Keeps X and Y.
gm_dos_char:
        stx gm_math4
        ldx #gm_bad_chars_end-gm_bad_chars-1
-       cmp gm_bad_chars,x
        beq +
        dex
        bpl -
        ldx gm_math4
        clc
        rts
+       ldx gm_math4
        sec
        rts
; A/X = form: open it, run it, close it. A = the exit object.
gm_form:
        sta gm_form_ptr
        stx gm_form_ptr+1
        jsr gm_bind
        bcs gm_form_done
        jsr gfx_clip_defaults
        lda gm_form_ptr
        ldx gm_form_ptr+1
        jsr fo_open
        bcs gm_form_done
        jsr fo_do
        bcs gm_form_close_error
        sta gm_form_exit
        jsr fo_close
        bcs gm_form_done
        lda gm_form_exit
gm_form_done:
        rts
gm_form_close_error:            ; keep the first error, still restore
        pha
        jsr fo_close
        pla
        sec
        rts

gm_form_exit: .byte 0
gm_form_ptr: .word 0
gm_name_field: .byte 0,0,16     ; N_FEDIT record: length, caret, maximum,
        .word gm_name_buf       ; buffer, 40/80-column views, IEC filename filter
        .byte 0,0,3
gm_name_buf: .fill 17,0
gm_info_line: .fill 32,0
; Show Info: x (centred), y, w, h, objects
gm_info_form: .byte $ff,0,30,10,7
        .byte FOT_TEXT,0,0,2,1,20
        .word gm_t_info
        .byte FOT_TEXT,0,0,2,3,5
        .word gm_t_name
        .byte FOT_FIELD,0,0,8,3,17
        .word gm_name_field
        .byte FOT_TEXT,0,0,2,4,26
        .word gm_info_line
        .byte FOT_CHECK,0,FOS_DISABLED,2,5,12
        .word gm_t_readonly
        .byte FOT_BUTTON,FOF_DEFAULT|FOF_EXIT,0,8,7,8
        .word gm_t_ok
        .byte FOT_BUTTON,FOF_CANCEL|FOF_EXIT,0,18,7,8
        .word gm_t_cancel
gm_t_info: .byte 73,116,101,109,32,73,110,102,111,114,109,97,116,105,111,110,0   ; Item Information
gm_t_name: .byte 78,97,109,101,58,0   ; Name:
gm_t_readonly: .byte 82,101,97,100,45,111,110,108,121,0   ; Read-only
gm_t_ok: .byte 79,75,0   ; OK
gm_t_cancel: .byte 67,97,110,99,101,108,0   ; Cancel
gm_s_norename: .byte 91,51,93,91,67,111,117,108,100,32,110,111,116,32,114,101,110,97,109,101,124,0   ; [3][Could not rename|


.include "forms.inc"
.bend
gm_dlg_end:
.cerror gm_dlg_end > N_APPBASE+GM_APP_PAGES*256, "GDDLG.PRG exceeds the module window: ", gm_dlg_end
