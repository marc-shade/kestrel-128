; GDUSB.PRG (assembled on its own against the core's labels, gemdesk.sym,
; which build-native-desktop.py writes first; docs/NATIVE-MODULES.md).
.include "gemdesk.sym"
* = gm_module
; GDUSB.PRG: Show Info on a USB entry, with rename (its own forms library).
gm_mod_usb:
        .text "nmod"
        .byte 1,1,14,0
        .word gm_mod_usb_end-gm_mod_usb
        .word 0
        .word usb.entry-gm_mod_usb
        .word 0
usb .block
entry:
        ldx #3                  ; forms draw on the desktop's surface
-       lda gm_surface,x
        sta fo_surface,x
        dex
        bpl -
        jmp gm_uinfo

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
gm_info_line: .fill 32,0
gm_t_info: .byte 73,116,101,109,32,73,110,102,111,114,109,97,116,105,111,110,0   ; Item Information
gm_t_readonly: .byte 82,101,97,100,45,111,110,108,121,0   ; Read-only
gm_t_ok: .byte 79,75,0   ; OK
gm_t_cancel: .byte 67,97,110,99,101,108,0   ; Cancel
gm_s_norename: .byte 91,51,93,91,67,111,117,108,100,32,110,111,116,32,114,101,110,97,109,101,124,0   ; [3][Could not rename|
; Show Info on a USB entry: the name (editable, 63 bytes, 26 shown), "Folder"
; or "File, N bytes" and read-only from FILE_STAT (size LE32, date, time,
; extension, attribute, name). OK with a changed name sends RENAME_FILE with
; both full paths ("old NUL new"; the firmware refuses an existing name),
; FILE_STAT must then find the new name, and the window is listed again.
gm_uinfo:
        jsr gm_read_record
        bcc +
        jmp gm_view_fail
+       lda gm_rec+20
        jsr gm_ult_fullname     ; N_UPATH/N_FNAMELEN; the leaf in gm_name/gm_nlen
        bcs gm_ui_error
        lda #$08                ; FILE_STAT
        jsr gm_ucmd
        bcs gm_ui_error
        lda N_FACTUAL+1
        bne +
        lda N_FACTUAL
        cmp #13                 ; the fields and at least one name byte
        bcc gm_ui_short
+       ldx #3                  ; size, before the form reuses N_BUFFER
-       lda N_BUFFER,x
        sta gm_q,x
        dex
        bpl -
        lda N_BUFFER+11         ; attribute: 1 read-only, $10 folder
        sta gm_uattr
        lda gm_nlen             ; the leaf into the field (63 at most)
        cmp #64
        bcc +
        lda #63
+       sta gm_uname_field
        tax
-       lda gm_name-1,x
        sta gm_uname_buf-1,x
        dex
        bne -
        lda #0                  ; the line: "Folder" or "File, N bytes"
        sta gm_alen
        lda gm_uattr
        and #$10
        beq +
        lda #<gm_s_ufolder
        ldx #>gm_s_ufolder
        jsr gm_astr
        jmp gm_ui_line
+       lda #<gm_s_ufile
        ldx #>gm_s_ufile
        jsr gm_astr
        lda gm_q+1              ; exactly one: "1 byte"
        ora gm_q+2
        ora gm_q+3
        bne +
        lda gm_q
        cmp #1
+       php
        jsr gm_anum32
        lda #<gm_s_ubytes
        ldx #>gm_s_ubytes
        jsr gm_astr
        plp
        bne gm_ui_line
        dec gm_alen             ; drop the "s"
gm_ui_line:
        ldx gm_alen
        lda #0
        sta gm_abuf,x
-       lda gm_abuf,x
        sta gm_info_line,x
        dex
        bpl -
        lda gm_uattr            ; read-only: shown, not changeable
        lsr
        lda #0
        bcc +
        lda #FOS_SELECTED
+       ora #FOS_DISABLED
        sta gm_uinfo_form+5+3*8+2
        lda #<gm_uinfo_form
        ldx #>gm_uinfo_form
        jsr gm_form
        bcc +
        jmp gm_view_fail
+       cmp #4                  ; OK
        bne gm_ui_done
        ldx gm_uname_field      ; unchanged: nothing to do
        cpx gm_nlen
        bne gm_urename
-       lda gm_uname_buf-1,x
        cmp gm_name-1,x
        bne gm_urename
        dex
        bne -
gm_ui_done:
        rts
gm_ui_short:
        lda #N_IOERROR
gm_ui_error:
        jmp gm_usb_error
gm_ur_bad:
        lda #<gm_s_ur_bad
        ldx #>gm_s_ur_bad
        ldy #1
        jmp gm_alert
; The new name: 1..63 printable bytes, none of " / \ : < > * ? |, not ending
; in a space or a period (as Files checks).
gm_urename:
        ldx gm_uname_field
        beq gm_ur_bad
        lda gm_uname_buf-1,x
        cmp #$20
        beq gm_ur_bad
        cmp #$2e
        beq gm_ur_bad
gm_ur_char:
        lda gm_uname_buf-1,x
        cmp #$20
        bcc gm_ur_bad
        cmp #$7f
        bcs gm_ur_bad
        ldy #8
gm_ur_forbid:
        cmp gm_ur_forbidden,y
        beq gm_ur_bad
        dey
        bpl gm_ur_forbid
        dex
        bne gm_ur_char
        lda gm_rec+20           ; the old full path again (the form used N_BUFFER)
        jsr gm_ult_fullname
        bcs gm_ui_error
        lda N_FNAMELEN          ; "old NUL new": new = the old path's folder + name
        sta gm_ur_old
        sec
        sbc gm_nlen
        sta gm_ur_dir
        ldx gm_ur_old
        lda #0
        sta N_UPATH,x
        inx
        beq gm_ur_long
        ldy #0
-       cpy gm_ur_dir
        beq +
        lda N_UPATH,y
        sta N_UPATH,x
        inx
        beq gm_ur_long
        iny
        bne -
+       ldy #0
-       lda gm_uname_buf,y
        sta N_UPATH,x
        inx
        beq gm_ur_long
        iny
        cpy gm_uname_field
        bne -
        stx N_FNAMELEN
        stx gm_ur_end
        lda #$0a                ; RENAME_FILE
        jsr gm_ucmd
        bcs gm_ur_failed
        lda N_FACTUAL
        ora N_FACTUAL+1
        bne gm_ur_unproven
        ldx gm_ur_old           ; the new path alone, for FILE_STAT
        inx
        ldy #0
-       lda N_UPATH,x
        sta N_UPATH,y
        iny
        inx
        cpx gm_ur_end
        bne -
        sty N_FNAMELEN
        lda #$08
        jsr gm_ucmd
        bcs gm_ur_unproven
        jmp gm_ult_rescan
gm_ur_long:
        lda #$23                ; the paths would exceed 255 bytes
gm_ur_failed:                   ; "[3][Could not rename|NAME|error $xx][OK]"
        pha
        lda #<gm_s_norename
        ldx #>gm_s_norename
        jsr gm_fail_head
        jmp gm_error_hex
gm_ur_unproven:
        lda #<gm_s_ur_unproven
        ldx #>gm_s_ur_unproven
        ldy #1
        jsr gm_alert
        jmp gm_ult_rescan
gm_ur_forbidden: .byte $22,$2f,$5c,$3a,$3c,$3e,$2a,$3f,$7c
gm_ur_old: .byte 0
gm_ur_dir: .byte 0
gm_ur_end: .byte 0
gm_uattr: .byte 0
gm_uname_field: .byte 0,0,63    ; N_FEDIT record: length, caret, maximum,
        .word gm_uname_buf      ; buffer, 40/80-column views, no filter
        .byte 0,0,0
gm_uname_buf: .fill 64,0
gm_uinfo_form: .byte $ff,0,30,10,6
        .byte FOT_TEXT,0,0,2,1,20
        .word gm_t_info
        .byte FOT_FIELD,0,0,2,3,26
        .word gm_uname_field
        .byte FOT_TEXT,0,0,2,4,26
        .word gm_info_line
        .byte FOT_CHECK,0,FOS_DISABLED,2,5,12
        .word gm_t_readonly
        .byte FOT_BUTTON,FOF_DEFAULT|FOF_EXIT,0,8,7,8
        .word gm_t_ok
        .byte FOT_BUTTON,FOF_CANCEL|FOF_EXIT,0,18,7,8
        .word gm_t_cancel
gm_s_ufolder: .byte 70,111,108,100,101,114,0   ; Folder
gm_s_ufile: .byte 70,105,108,101,44,32,0   ; File, 
gm_s_ubytes: .byte 32,98,121,116,101,115,0   ;  bytes
gm_s_ur_bad: .byte 91,49,93,91,84,104,97,116,32,110,97,109,101,32,99,97,110,110,111,116,32,98,101,124
        .byte 117,115,101,100,32,111,110,32,85,83,66,32,115,116,111,114,97,103,101,46,93,91,79,75
        .byte 93,0   ; [1][That name cannot be|used on USB storage.][OK]
gm_s_ur_unproven: .byte 91,51,93,91,84,104,101,32,100,114,105,118,101,32,100,105,100,32,110,111,116,124,99,111
        .byte 110,102,105,114,109,32,116,104,101,32,110,101,119,32,110,97,109,101,59,124,115,101,101,32
        .byte 116,104,101,32,108,105,115,116,46,93,91,79,75,93,0   ; [3][The drive did not|confirm the new name;|see the list.][OK]

.include "forms.inc"
.bend
gm_mod_usb_end:
.cerror gm_mod_usb_end > N_APPBASE+GM_APP_PAGES*256, "GDUSB.PRG exceeds the module window: ", gm_mod_usb_end
