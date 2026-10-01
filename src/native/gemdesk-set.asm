; GDSET.PRG (assembled on its own against the core's labels, gemdesk.sym,
; which build-native-desktop.py writes first; docs/NATIVE-MODULES.md).
.include "gemdesk.sym"
* = gm_module
gm_set:
        .text "nmod"
        .byte 1,1,14,0
        .word gm_set_end-gm_set
        .word 0
        .word set.entry-gm_set
        .word 0
set .block
gm_dialog_done:
        rts
gm_dialog_fail:
        jmp gm_view_fail
entry:
        ldx #3                  ; forms draw on the desktop's surface
-       lda gm_surface,x
        sta fo_surface,x
        dex
        bpl -
        lda gm_mop
        cmp #GM_MOP_PREFS
        bne +
        jmp gm_prefs
+       jmp gm_control

; Options:Preferences: confirm deletes, copies and overwrites, the sort
; order, the colour.
gm_prefs:
        lda gm_confirm
        and #FOS_SELECTED       ; (bit 0: deletes)
        sta gm_pref_form+5+1*8+2
        lda gm_confirm          ; copies: ticked while the bit is clear
        and #GM_NOCOPYASK
        eor #GM_NOCOPYASK
        lsr
        sta gm_pref_form+5+2*8+2
        lda gm_confirm          ; overwrites: ticked while the bit is clear
        and #GM_NOOVERASK
        eor #GM_NOOVERASK
        lsr
        lsr
        lsr
        sta gm_pref_form+5+3*8+2
        ldx #0
        ldy #0
-       lda #0
        cpy gm_view
        bne +
        lda #FOS_SELECTED
+       sta gm_pref_form+5+5*8+2,x ; objects 5..8, 8 bytes apart
        txa
        clc
        adc #8
        tax
        iny
        cpy #4
        bne -
        ldx #0                  ; desktop colour radios: objects 10..12
        ldy #0
-       lda #0
        pha
        lda gm_desk_colors,y
        cmp gm_desk_color
        bne +
        pla
        lda #FOS_SELECTED
        pha
+       pla
        sta gm_pref_form+5+10*8+2,x
        txa
        clc
        adc #8
        tax
        iny
        cpy #3
        bne -
        lda #<gm_pref_form
        ldx #>gm_pref_form
        jsr gm_form
        bcs gm_dialog_fail
        cmp #13                 ; OK
        bne gm_dialog_done
        ldx #0                  ; the chosen colour
        ldy #0
-       lda gm_pref_form+5+10*8+2,x
        and #FOS_SELECTED
        bne +
        txa
        clc
        adc #8
        tax
        iny
        cpy #3
        bne -
        beq gm_prefs_view
+       lda gm_desk_colors,y
        cmp gm_desk_color
        beq gm_prefs_view
        sta gm_desk_color
        jsr gm_restore_color    ; the AES repaints; WM_REDRAW brings the icons
gm_prefs_view:
        lda gm_confirm          ; keep the bits this dialog does not show
        and #GM_KEYCLICK|GM_BELL
        sta gm_confirm
        lda gm_pref_form+5+3*8+2 ; overwrites unticked: bit 3
        asl
        asl
        ora gm_pref_form+5+2*8+2 ; copies unticked: bit 1
        and #FOS_SELECTED*5
        eor #FOS_SELECTED*5
        asl
        ora gm_confirm
        sta gm_confirm
        lda gm_pref_form+5+1*8+2
        and #FOS_SELECTED
        ora gm_confirm
        sta gm_confirm
        ldx #0
        ldy #0
-       lda gm_pref_form+5+5*8+2,x
        and #FOS_SELECTED
        bne +
        txa
        clc
        adc #8
        tax
        iny
        cpy #4
        bne -
        rts
+       tya
        jmp gm_set_view
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
gm_pref_form: .byte $ff,0,30,14,15
        .byte FOT_TEXT,0,0,2,1,20
        .word gm_t_prefs
        .byte FOT_CHECK,0,0,2,2,18
        .word gm_t_confirm
        .byte FOT_CHECK,0,0,2,3,18
        .word gm_t_copies
        .byte FOT_CHECK,0,0,2,4,20
        .word gm_t_overwrites
        .byte FOT_TEXT,0,0,2,5,18
        .word gm_t_sortby
        .byte FOT_RADIO,$10,0,4,6,8
        .word gm_t_sname
        .byte FOT_RADIO,$10,0,14,6,8
        .word gm_t_stype
        .byte FOT_RADIO,$10,0,4,7,8
        .word gm_t_ssize
        .byte FOT_RADIO,$10,0,14,7,12
        .word gm_t_sunsorted
        .byte FOT_TEXT,0,0,2,8,9
        .word gm_t_desktop
        .byte FOT_RADIO,$20,0,4,9,7
        .word gm_t_blue
        .byte FOT_RADIO,$20,0,12,9,7
        .word gm_t_grey
        .byte FOT_RADIO,$20,0,20,9,8
        .word gm_t_black
        .byte FOT_BUTTON,FOF_DEFAULT|FOF_EXIT,0,8,11,8
        .word gm_t_ok
        .byte FOT_BUTTON,FOF_CANCEL|FOF_EXIT,0,18,11,8
        .word gm_t_cancel
gm_t_desktop: .byte 68,101,115,107,116,111,112,58,0   ; Desktop:
gm_t_blue: .byte 66,108,117,101,0                    ; Blue
gm_t_grey: .byte 71,114,101,121,0                    ; Grey
gm_t_black: .byte 66,108,97,99,107,0                 ; Black
gm_desk_colors: .byte $16,$1c,$10                    ; white icons on blue, grey, black
gm_t_ok: .byte 79,75,0   ; OK
gm_t_cancel: .byte 67,97,110,99,101,108,0   ; Cancel
gm_t_prefs: .byte 80,114,101,102,101,114,101,110,99,101,115,0   ; Preferences
gm_t_confirm: .byte 67,111,110,102,105,114,109,32,100,101,108,101,116,101,115,0   ; Confirm deletes
gm_t_copies: .byte 67,111,110,102,105,114,109,32,99,111,112,105,101,115,0   ; Confirm copies
gm_t_overwrites: .byte 67,111,110,102,105,114,109,32,111,118,101,114,119,114,105,116,101,115,0   ; Confirm overwrites
gm_t_sortby: .byte 83,111,114,116,32,119,105,110,100,111,119,115,32,98,121,58,0   ; Sort windows by:
gm_t_sname: .byte 78,97,109,101,0   ; Name
gm_t_stype: .byte 84,121,112,101,0   ; Type
gm_t_ssize: .byte 83,105,122,101,0   ; Size
gm_t_sunsorted: .byte 85,110,115,111,114,116,101,100,0   ; Unsorted
; Desk:Control Panel: key repeat (KERNAL RPTFLG), double-click speed (AES
; evnt_dclick), Key click (gm_confirm bit 2: GEMDESK clicks on every key),
; Bell (bit 4: the SID bell for every stop alert, "[3]") and
; the printer (TOS's Install Printer): IEC device 4 or 5, and Lowercase
; (secondary address 7; off, 0: upper case and graphics). All are kept with
; the desktop; a new device is probed again for the Printer icon.
gm_control:
        ldx #2                  ; key repeat radios: objects 2..4
-       lda #0
        ldy gm_rpt_values,x
        cpy $0a22
        bne +
        lda #FOS_SELECTED
+       sta gm_ctrl_rpt_state,x
        dex
        bpl -
        lda $0a22               ; another value: shown as cursor keys only
        ldx #2
-       cmp gm_rpt_values,x
        beq +
        dex
        bpl -
        lda #FOS_SELECTED
        sta gm_ctrl_rpt_state+1
+       ldx #4                  ; speed radios: objects 6..10
-       lda #0
        cpx gm_dclick
        bne +
        lda #FOS_SELECTED
+       sta gm_ctrl_speed_state,x
        dex
        bpl -
        ldx #0                  ; copy the states into the form's objects
-       lda gm_ctrl_rpt_state,x
        ldy gm_ctrl_rpt_offset,x
        sta gm_ctrl_form,y
        inx
        cpx #3
        bne -
        ldx #0
-       lda gm_ctrl_speed_state,x
        ldy gm_ctrl_speed_offset,x
        sta gm_ctrl_form,y
        inx
        cpx #5
        bne -
        lda gm_confirm          ; Key click: object 11
        lsr
        lsr
        and #FOS_SELECTED
        sta gm_ctrl_form+5+11*8+2
        lda gm_confirm          ; Bell: object 12
        lsr
        lsr
        lsr
        lsr
        and #FOS_SELECTED
        sta gm_ctrl_form+5+12*8+2
        lda #FOS_SELECTED       ; the printer: objects 14, 15 and 16
        ldx #0
        ldy gm_prt_dev
        cpy #5
        bne +
        tax
        lda #0
+       sta gm_ctrl_form+5+14*8+2
        stx gm_ctrl_form+5+15*8+2
        lda gm_prt_sa
        and #FOS_SELECTED       ; (7 has bit 0; 0 has not)
        sta gm_ctrl_form+5+16*8+2
        lda #<gm_ctrl_form
        ldx #>gm_ctrl_form
        jsr gm_form
        bcc +
        jmp gm_view_fail
+       cmp #17                 ; OK
        bne gm_control_done
        lda gm_ctrl_form+5+16*8+2 ; Lowercase: secondary address 7, else 0
        and #FOS_SELECTED
        beq +
        lda #7
+       sta gm_prt_sa
        ldx #4
        lda gm_ctrl_form+5+14*8+2
        and #FOS_SELECTED
        bne +
        inx
+       cpx gm_prt_dev
        beq +
        stx gm_prt_dev          ; another printer: its icon again, then
        jsr gm_prt_probe        ; the desktop repainted with it
        jsr gm_restore_color
+
        lda gm_confirm
        and #$ff^(GM_KEYCLICK|GM_BELL)
        sta gm_confirm
        lda gm_ctrl_form+5+12*8+2 ; Bell: bit 4; Key click: bit 2
        asl
        asl
        ora gm_ctrl_form+5+11*8+2
        and #FOS_SELECTED*5
        asl
        asl
        ora gm_confirm
        sta gm_confirm
        ldx #2
-       ldy gm_ctrl_rpt_offset,x
        lda gm_ctrl_form,y
        and #FOS_SELECTED
        beq +
        lda gm_rpt_values,x
        sta $0a22
+       dex
        bpl -
        ldx #4
-       ldy gm_ctrl_speed_offset,x
        lda gm_ctrl_form,y
        and #FOS_SELECTED
        beq +
        stx gm_dclick
+       dex
        bpl -
        lda gm_dclick
        jmp ae_dclick
gm_control_done:
        rts
gm_rpt_values: .byte $80,$00,$40                     ; all keys, cursor keys only, none
gm_ctrl_rpt_offset: .byte 5+2*8+2,5+3*8+2,5+4*8+2   ; state bytes of objects 2..4
gm_ctrl_speed_offset: .byte 5+6*8+2,5+7*8+2,5+8*8+2,5+9*8+2,5+10*8+2
gm_ctrl_rpt_state: .fill 3,0
gm_ctrl_speed_state: .fill 5,0
gm_ctrl_form: .byte $ff,0,30,13,19
        .byte FOT_TEXT,0,0,2,1,20
        .word gm_t_control
        .byte FOT_TEXT,0,0,2,3,12
        .word gm_t_repeat
        .byte FOT_RADIO,$10,0,4,4,6
        .word gm_t_all
        .byte FOT_RADIO,$10,0,11,4,9
        .word gm_t_cursor
        .byte FOT_RADIO,$10,0,21,4,7
        .word gm_t_none
        .byte FOT_TEXT,0,0,2,5,26
        .word gm_t_dclick
        .byte FOT_RADIO,$20,0,4,6,4
        .word gm_t_1
        .byte FOT_RADIO,$20,0,9,6,4
        .word gm_t_2
        .byte FOT_RADIO,$20,0,14,6,4
        .word gm_t_3
        .byte FOT_RADIO,$20,0,19,6,4
        .word gm_t_4
        .byte FOT_RADIO,$20,0,24,6,4
        .word gm_t_5
        .byte FOT_CHECK,0,0,2,7,12
        .word gm_t_click
        .byte FOT_CHECK,0,0,16,7,10
        .word gm_t_bell
        .byte FOT_TEXT,0,0,2,8,8
        .word gm_t_printer
        .byte FOT_RADIO,$30,0,11,8,4
        .word gm_t_4
        .byte FOT_RADIO,$30,0,16,8,4
        .word gm_t_5
        .byte FOT_CHECK,0,0,2,9,16
        .word gm_t_lower
        .byte FOT_BUTTON,FOF_DEFAULT|FOF_EXIT,0,6,10,8
        .word gm_t_ok
        .byte FOT_BUTTON,FOF_CANCEL|FOF_EXIT,0,18,10,8
        .word gm_t_cancel
gm_t_bell: .byte 66,101,108,108,0   ; Bell
gm_t_printer: .byte 80,114,105,110,116,101,114,58,0   ; Printer:
gm_t_lower: .byte 76,111,119,101,114,99,97,115,101,0   ; Lowercase
gm_t_control: .byte 67,111,110,116,114,111,108,32,80,97,110,101,108,0   ; Control Panel
gm_t_repeat: .byte 75,101,121,32,114,101,112,101,97,116,58,0   ; Key repeat:
gm_t_all: .byte 65,108,108,0   ; All
gm_t_cursor: .byte 67,117,114,115,111,114,0   ; Cursor
gm_t_none: .byte 78,111,110,101,0   ; None
gm_t_dclick: .byte 68,111,117,98,108,101,45,99,108,105,99,107,32,40,115,108,111,119,45,102,97,115,116,41,58,0   ; Double-click (slow-fast):
gm_t_1: .byte 49,0   ; 1
gm_t_2: .byte 50,0   ; 2
gm_t_3: .byte 51,0   ; 3
gm_t_4: .byte 52,0   ; 4
gm_t_5: .byte 53,0   ; 5
gm_t_click: .byte 75,101,121,32,99,108,105,99,107,0   ; Key click

.include "forms.inc"
.bend
gm_set_end:
.cerror gm_set_end > N_APPBASE+GM_APP_PAGES*256, "GDSET.PRG exceeds the module window: ", gm_set_end
