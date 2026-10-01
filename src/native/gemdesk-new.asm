; GDNEW.PRG (assembled on its own against the core's labels, gemdesk.sym,
; which build-native-desktop.py writes first; docs/NATIVE-MODULES.md).
.include "gemdesk.sym"
* = gm_module
; GDNEW.PRG: File:New Folder in a USB window (its own forms library).
gm_mod_new:
        .text "nmod"
        .byte 1,1,14,0
        .word gm_mod_new_end-gm_mod_new
        .word 0
        .word new.entry-gm_mod_new
        .word 0
new .block
entry:
        ldx #3                  ; forms draw on the desktop's surface
-       lda gm_surface,x
        sta fo_surface,x
        dex
        bpl -
        jmp gm_newfolder
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
; File:New Folder: a folder in the top USB window's folder. The name (1..31
; printable characters, none of " / \ : < > * ? |, not ending in a space or
; a period) goes to Ultimate DOS CREATE_DIR with the full path; FILE_STAT
; must then answer with a directory, and the window is listed again.
gm_newfolder:
        jsr gm_top_slot
        bcs gm_nf_notusb
        stx gm_slot
        lda gm_win_fmt,x
        cmp #3
        beq +
gm_nf_notusb:
        lda #<gm_s_nf_usb
        ldx #>gm_s_nf_usb
        ldy #1
        jmp gm_alert
+       lda #0
        sta gm_nf_field
        lda #<gm_nf_form
        ldx #>gm_nf_form
        jsr gm_form
        bcc +
        jmp gm_view_fail
+       cmp #2                  ; Create (object 2)
        bne gm_nf_done
        ldx gm_nf_field         ; the name
        beq gm_nf_bad
        lda gm_nf_buf-1,x
        cmp #$20
        beq gm_nf_bad
        cmp #$2e
        beq gm_nf_bad
        dex
gm_nf_char:
        lda gm_nf_buf,x
        cmp #$20
        bcc gm_nf_bad
        cmp #$7f
        bcs gm_nf_bad
        ldy #gm_nf_forbidden_end-gm_nf_forbidden-1
gm_nf_forbid:
        cmp gm_nf_forbidden,y
        beq gm_nf_bad
        dey
        bpl gm_nf_forbid
        dex
        bpl gm_nf_char
        jsr gm_path_to_upath    ; the window's folder, '/', the name
        ldx N_FNAMELEN
        lda N_UPATH-1,x
        cmp #$2f
        beq +
        lda #$2f
        sta N_UPATH,x
        inx
+       ldy #0
-       lda gm_nf_buf,y
        sta N_UPATH,x
        inx
        beq gm_nf_bad           ; past 255 bytes
        iny
        cpy gm_nf_field
        bne -
        stx N_FNAMELEN
        lda #$16                ; CREATE_DIR
        jsr gm_ucmd
        bcs gm_nf_failed
        lda N_FACTUAL
        ora N_FACTUAL+1
        bne gm_nf_unproven
        lda #$08                ; FILE_STAT: a directory now
        jsr gm_ucmd
        bcs gm_nf_unproven
        lda N_BUFFER+11
        and #$18
        cmp #$10
        bne gm_nf_unproven
        jmp gm_ult_rescan
gm_nf_bad:
        lda #<gm_s_nf_bad
        ldx #>gm_s_nf_bad
        ldy #1
        jmp gm_alert
gm_nf_failed:                   ; "[3][Could not make the|folder: error $xx][OK]"
        pha
        lda #0
        sta gm_alen
        lda #<gm_s_nf_failed
        ldx #>gm_s_nf_failed
        jsr gm_astr
        jmp gm_error_hex
gm_nf_unproven:
        lda #<gm_s_nf_unproven
        ldx #>gm_s_nf_unproven
        ldy #1
        jsr gm_alert
        jmp gm_ult_rescan
gm_nf_done:
        rts
gm_nf_field: .byte 0,0,31       ; N_FEDIT record: length, caret, maximum,
        .word gm_nf_buf         ; buffer, 40/80-column views, no filter
        .byte 0,0,0
gm_nf_buf: .fill 32,0
gm_nf_forbidden: .byte $22,$2f,$5c,$3a,$3c,$3e,$2a,$3f,$7c
gm_nf_forbidden_end:
gm_nf_form: .byte $ff,0,30,9,4
        .byte FOT_TEXT,0,0,2,1,20
        .word gm_t_newfolder
        .byte FOT_FIELD,0,0,2,3,26
        .word gm_nf_field
        .byte FOT_BUTTON,FOF_DEFAULT|FOF_EXIT,0,6,6,10
        .word gm_t_create
        .byte FOT_BUTTON,FOF_CANCEL|FOF_EXIT,0,18,6,8
        .word gm_t_nf_cancel
gm_t_newfolder: .byte 78,101,119,32,70,111,108,100,101,114,0   ; New Folder
gm_t_create: .byte 67,114,101,97,116,101,0   ; Create
gm_t_nf_cancel: .byte 67,97,110,99,101,108,0   ; Cancel
gm_s_nf_usb: .byte 91,49,93,91,78,101,119,32,102,111,108,100,101,114,115,32,97,114,101,32,109,97,100,101
        .byte 124,105,110,32,85,83,66,32,119,105,110,100,111,119,115,46,93,91,79,75,93,0   ; [1][New folders are made|in USB windows.][OK]
gm_s_nf_bad: .byte 91,49,93,91,84,104,97,116,32,110,97,109,101,32,99,97,110,110,111,116,32,98,101,124
        .byte 117,115,101,100,32,102,111,114,32,97,32,102,111,108,100,101,114,46,93,91,79,75,93,0   ; [1][That name cannot be|used for a folder.][OK]
gm_s_nf_failed: .byte 91,51,93,91,67,111,117,108,100,32,110,111,116,32,109,97,107,101,32,116,104,101,124,102
        .byte 111,108,100,101,114,58,32,0   ; [3][Could not make the|folder: 
gm_s_nf_unproven: .byte 91,51,93,91,84,104,101,32,100,114,105,118,101,32,100,105,100,32,110,111,116,124,99,111
        .byte 110,102,105,114,109,32,116,104,101,32,102,111,108,100,101,114,59,124,115,101,101,32,116,104
        .byte 101,32,108,105,115,116,46,93,91,79,75,93,0   ; [3][The drive did not|confirm the folder;|see the list.][OK]

.include "forms.inc"
.bend
gm_mod_new_end:
.cerror gm_mod_new_end > N_APPBASE+GM_APP_PAGES*256, "GDNEW.PRG exceeds the module window: ", gm_mod_new_end
