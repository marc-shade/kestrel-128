; GDFMT.PRG (assembled on its own against the core's labels, gemdesk.sym,
; which build-native-desktop.py writes first; docs/NATIVE-MODULES.md).
.include "gemdesk.sym"
* = gm_module
; GDFMT.PRG: File:Format (its own forms library and progress window).
gm_mod_fmt:
        .text "nmod"
        .byte 1,1,14,0
        .word gm_mod_fmt_end-gm_mod_fmt
        .word 0
        .word fmt.entry-gm_mod_fmt
        .word 0
fmt .block
entry:
        ldx #3                  ; forms draw on the desktop's surface
-       lda gm_surface,x
        sta fo_surface,x
        dex
        bpl -
        jmp gm_format
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
; File:Format: drive 8 or 9, disk name and ID, then a confirmation; the drive
; gets "N0:NAME,ID" under a "Formatting disk" window, every window of that
; drive is listed again, and the new disk's listing is read back for its free
; blocks ("[1][Drive 9 is formatted:|664 blocks free.][OK]").
gm_format:
        lda #0
        sta gm_fname_field      ; empty name and ID each time
        sta gm_fid_field
        sta gm_fname_buf
        sta gm_fid_buf
        lda #FOS_SELECTED
        sta gm_format_form+5+2*8+2
        lda #0
        sta gm_format_form+5+3*8+2
        lda #<gm_format_form
        ldx #>gm_format_form
        jsr gm_form
        bcc +
        jmp gm_view_fail
+       cmp #8                  ; Format
        bne gm_format_done
        ldx gm_fname_field
        beq gm_format_bad       ; a disk needs a name
        lda gm_fid_field
        beq gm_format_bad
        lda #8                  ; the chosen drive
        ldx gm_format_form+5+3*8+2
        beq +
        lda #9
+       sta dc_device
        sta gm_dev
        ldx N_BOOTFORMAT        ; the geometry its icon opens it in, so its
        cmp N_BOOTDEVICE        ; windows are the ones listed again
        beq +
        jsr gm_drive_format
        tax
+       stx gm_fmt
        lda gm_dev
        clc                     ; "[3][Format drive 8?|Every file on it|will be erased.][Format|Cancel]"
        adc #$30
        sta gm_format_ask_drive
        lda #<gm_format_ask
        ldx #>gm_format_ask
        ldy #2
        jsr gm_alert
        bcs gm_format_done
        lda N_BUFFER
        cmp #1
        bne gm_format_done
        ldy #3                  ; N0:NAME,ID
        ldx #0
-       lda gm_fname_buf,x
        sta dc_text,y
        iny
        inx
        cpx gm_fname_field
        bne -
        lda #$2c
        sta dc_text,y
        iny
        ldx #0
-       lda gm_fid_buf,x
        sta dc_text,y
        iny
        inx
        cpx gm_fid_field
        bne -
        sty dc_length
        lda #$4e
        sta dc_text
        lda #$30
        sta dc_text+1
        lda #$3a
        sta dc_text+2
        jsr progress_open       ; "Formatting disk" while the drive works
        jsr dc_command
        php
        pha
        jsr progress_close
        pla
        plp
        bcs gm_format_error
        cmp #0
        bne gm_format_status
        jsr dc_blocks_free      ; the new disk's listing, read back
        php
        lda dc_free
        sta gm_fmt_free
        lda dc_free+1
        sta gm_fmt_free+1
        jsr gm_refresh_drive
        plp
        bcs gm_format_unread
        lda #0                  ; "[1][Drive 9 is formatted:|664 blocks free.][OK]"
        sta gm_alen
        lda #<gm_s_formatted
        ldx #>gm_s_formatted
        jsr gm_astr
        lda gm_dev
        ora #$30
        jsr gm_aput
        lda #<gm_s_formatted2
        ldx #>gm_s_formatted2
        jsr gm_astr
        lda gm_fmt_free
        sta gm_num
        lda gm_fmt_free+1
        sta gm_num+1
        jsr gm_anum
        lda #<gm_s_formatted3
        ldx #>gm_s_formatted3
        jsr gm_astr
        lda #<gm_abuf
        ldx #>gm_abuf
        ldy #1
        jmp gm_alert
gm_format_unread:
        lda #<gm_s_unread
        ldx #>gm_s_unread
        ldy #1
        jmp gm_alert
gm_format_done:
        rts
gm_format_bad:
        lda #<gm_format_need
        ldx #>gm_format_need
        ldy #1
        jmp gm_alert
gm_format_error:
        pha
        jsr gm_format_head
        jmp gm_error_hex
gm_format_status:
        jsr gm_format_head
        jmp gm_status_text
gm_format_head:
        lda #0
        sta gm_alen
        lda #<gm_s_noformat
        ldx #>gm_s_noformat
        jmp gm_astr

.include "gemdesk-progress.inc"
progress_text:                  ; "Formatting disk" into gm_abuf
        lda #0
        sta gm_alen
        lda #<gm_s_formatting
        ldx #>gm_s_formatting
        jsr gm_astr
        lda #0
        jmp gm_aput

gm_fmt_free: .word 0
gm_fname_field: .byte 0,0,16    ; N_FEDIT records: disk name and ID (IEC filename filter)
        .word gm_fname_buf
        .byte 0,0,3
gm_fname_buf: .fill 17,0
gm_fid_field: .byte 0,0,2
        .word gm_fid_buf
        .byte 0,0,3
gm_fid_buf: .fill 3,0
gm_format_form: .byte $ff,0,30,11,10
        .byte FOT_TEXT,0,0,2,1,20
        .word gm_t_format
        .byte FOT_TEXT,0,0,2,3,6
        .word gm_t_drive
        .byte FOT_RADIO,$10,0,9,3,5
        .word gm_t_8
        .byte FOT_RADIO,$10,0,15,3,5
        .word gm_t_9
        .byte FOT_TEXT,0,0,2,4,5
        .word gm_t_name
        .byte FOT_FIELD,0,0,9,4,17
        .word gm_fname_field
        .byte FOT_TEXT,0,0,2,5,3
        .word gm_t_id
        .byte FOT_FIELD,0,0,9,5,3
        .word gm_fid_field
        .byte FOT_BUTTON,FOF_DEFAULT|FOF_EXIT,0,6,8,10
        .word gm_t_formatb
        .byte FOT_BUTTON,FOF_CANCEL|FOF_EXIT,0,18,8,8
        .word gm_t_cancel
gm_t_name: .byte 78,97,109,101,58,0   ; Name:
gm_t_cancel: .byte 67,97,110,99,101,108,0   ; Cancel
gm_t_format: .byte 70,111,114,109,97,116,32,100,105,115,107,0   ; Format disk
gm_t_drive: .byte 68,114,105,118,101,58,0   ; Drive:
gm_t_8: .byte 56,0   ; 8
gm_t_9: .byte 57,0   ; 9
gm_t_id: .byte 73,68,58,0   ; ID:
gm_t_formatb: .byte 70,111,114,109,97,116,0   ; Format
gm_s_noformat: .byte 91,51,93,91,67,111,117,108,100,32,110,111,116,32,102,111,114,109,97,116,32,116,104,101,32,100,105,115,107,46,124,0   ; [3][Could not format the disk.|
gm_format_need: .byte 91,49,93,91,65,32,100,105,115,107,32,110,101,101,100,115,32,97,32,110,97,109,101,124,97,110,100,32,97,110,32,73,68,46,93,91,79,75,93,0   ; [1][A disk needs a name|and an ID.][OK]
gm_format_ask: .byte 91,51,93,91,70,111,114,109,97,116,32,100,114,105,118,101,32
gm_format_ask_drive: .byte 56
        .byte 63,124,69,118,101,114,121,32,102,105,108,101,32,111,110,32,105,116,124,119,105,108,108,32,98,101,32,101,114,97,115,101,100,46,93,91,70,111,114,109,97,116,124,67,97,110,99,101,108,93,0
gm_s_formatting: .byte 70,111,114,109,97,116,116,105,110,103,32,100,105,115,107,0   ; Formatting disk
gm_s_formatted: .byte 91,49,93,91,68,114,105,118,101,32,0   ; [1][Drive 
gm_s_formatted2: .byte 32,105,115,32,102,111,114,109,97,116,116,101,100,58,124,0   ;  is formatted:|
gm_s_formatted3: .byte 32,98,108,111,99,107,115,32,102,114,101,101,46,93,91,79,75,93,0   ;  blocks free.][OK]
gm_s_unread: .byte 91,51,93,91,84,104,101,32,110,101,119,32,100,105,115,107,32,99,111,117,108,100,124,110,111,116,32,98,101,32,114,101,97,100,32,98,97,99,107,46,93,91,79,75,93,0   ; [3][The new disk could|not be read back.][OK]

.include "forms.inc"
.bend
gm_mod_fmt_end:
.cerror gm_mod_fmt_end > N_APPBASE+GM_APP_PAGES*256, "GDFMT.PRG exceeds the module window: ", gm_mod_fmt_end
