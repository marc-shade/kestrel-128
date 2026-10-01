; GDPRT.PRG (assembled on its own against the core's labels, gemdesk.sym,
; which build-native-desktop.py writes first; docs/NATIVE-MODULES.md).
.include "gemdesk.sym"
* = gm_module
; GDPRT.PRG (docs/GEM-DESKTOP.md): Options:Print Screen, or HELP (gm_mop =
; GM_MOP_PRTSCR), and rows dropped on the Printer icon (GM_MOP_PRINT).
gm_mod_prt:
        .text "nmod"
        .byte 1,1,14,0
        .word gm_mod_prt_end-gm_mod_prt
        .word 0
        .word dsk.entry-gm_mod_prt
        .word 0
dsk .block
entry:
        lda gm_mop
        cmp #GM_MOP_PRTSCR
        bne +
        jmp print_screen
+       jmp prt.print_target

; ---- printing: the screen, pictures and files -------------------------------------
; Bit-image bands in the Commodore mode: CHR$(8), then 29 bands of 7 dot rows,
; each 320 columns of one byte (bit 7 set, bit 0 the top dot) ended by CR;
; CHR$(15) returns to text. A set bitmap bit prints a dot. The rows come from
; the desktop's surface (Options:Print Screen, or HELP) or, for a Paint
; picture dropped on the Printer icon, from its file. Esc stops between bands;
; a printer that stops answering is reported.
print_screen:
        jsr printer_open
        bcs print_absent
        lda #0
        sta ps_file
        jsr ps_bands
        php
        pha
        jsr ps_stop
        pla
        plp
        bcc ps_done
        cmp #2
        beq print_absent
        lda #<s_prtscr_stopped
        ldx #>s_prtscr_stopped
ps_alert:
        ldy #1
        jmp gm_alert
ps_done:
        rts
ps_stop:
        jsr $ffcc
        lda #PRT_LFN
        jmp $ffc3

; The bands, rows from ps_fetch. Carry clear when done; carry set with A = 1
; after Esc or a failed read, 2 when the printer stopped answering. The
; printer is back in text mode either way, and its channel is cleared.
ps_bands:
        lda #0
        sta ps_y
ps_band:
        jsr $ffcc               ; (reads leave the channels to the file service)
        lda ps_y                ; the two character rows the band crosses
        lsr
        lsr
        lsr
        sta ps_math
        jsr ps_fetch            ; ps_a and ps_b at those rows
        bcs ps_cancelled
        lda #200                ; rows in this band: 7, or what is left
        sec
        sbc ps_y
        cmp #7
        bcc +
        lda #7
+       sta ps_rows
        ldx #PRT_LFN
        jsr $ffc9
        bcs ps_gone
        lda #8                  ; bit-image mode
        jsr $ffd2
        lda #40
        sta ps_cells
ps_cell:
        ldy #7                  ; the cell's 8 rows from each character row
-
ps_a:   lda $ffff,y
        sta ps_cell16,y
ps_b:   lda $ffff,y
        sta ps_cell16+8,y
        dey
        bpl -
        lda ps_a+1
        clc
        adc #8
        sta ps_a+1
        bcc +
        inc ps_a+2
+       lda ps_b+1
        clc
        adc #8
        sta ps_b+1
        bcc +
        inc ps_b+2
+       lda #$80
        sta ps_mask
ps_column:
        lda ps_y                ; from the band's bottom row up to its top
        and #7
        clc
        adc ps_rows
        tay
        ldx ps_rows
        lda #0
        sta ps_dots
-       dey
        lda ps_cell16,y
        and ps_mask
        cmp #1                  ; carry = a dot
        rol ps_dots
        dex
        bne -
        lda ps_dots
        ora #$80
        jsr $ffd2
        lsr ps_mask
        bne ps_column
        dec ps_cells
        bne ps_cell
        lda #13
        jsr $ffd2
        lda $90
        bmi ps_gone
        jsr $ffcc
        jsr N_KEYIN             ; Esc stops between bands
        cmp #27
        beq ps_cancelled
        lda ps_y
        clc
        adc #7
        sta ps_y
        cmp #200
        bcc ps_band
        jsr ps_text
        bcs ps_gone
        rts                     ; (carry clear)
ps_gone:
        jsr $ffcc
        lda #2
        sec
        rts
ps_cancelled:                   ; Esc, or a read failed
        jsr ps_text
        lda #1
        sec
        rts
ps_text:                        ; CHR$(15), then CLRCHN; carry set if refused
        ldx #PRT_LFN
        jsr $ffc9
        bcs +
        lda #15
        jsr $ffd2
        clc
+       php
        jsr $ffcc
        plp
        rts

; ps_a/ps_b at character rows ps_math and ps_math+1; carry set on failure.
ps_fetch:
        lda ps_file
        bne pf_file
        lda ps_math             ; the surface: both rows read again
        jsr ps_row
        bcs pf_done
        ldx #0                  ; the first to ps_first, the second stays in N_BUFFER
-       lda N_BUFFER,x
        sta ps_first,x
        lda N_BUFFER+160,x
        sta ps_first+160,x
        inx
        cpx #160
        bne -
        ldx ps_math
        inx
        txa
        cmp #25
        bcs +                   ; none below the last: its rows are not printed
        jsr ps_row
        bcs pf_done
+       lda #<ps_first
        ldx #>ps_first
        ldy #>N_BUFFER          ; (N_BUFFER is page-aligned)
        bne pf_point
pf_file:                        ; a picture: rows arrive in order, two held
        lda ps_math
        cmp ps_top
        beq pf_held
        inc ps_top              ; the band moved down one row: the lower held
        lda pf_lower            ; row is now the upper, the next is read
        ldx pf_upper
        stx pf_lower
        sta pf_upper
        lda ps_top
        cmp #24
        bcs pf_held             ; no row below the last
        jsr pf_read_lower
        bcs pf_done
pf_held:
        lda #0
        ldx pf_upper
        ldy pf_lower
pf_point:
        sta ps_a+1
        stx ps_a+2
        lda #0
        sta ps_b+1
        sty ps_b+2
        clc
pf_done:
        rts
; The picture's next character row (320 bytes) into the page pair pf_lower;
; carry set when the file ends short or a read fails.
pf_read_lower:
        ldx #0
        jsr prt.select
        lda #<320
        sta N_FCOUNT
        lda #>320
        sta N_FCOUNT+1
        jsr N_FREAD
        bcs +
        lda N_FACTUAL
        cmp #<320
        bne pf_short
        lda N_FACTUAL+1
        cmp #>320
        bne pf_short
        lda pf_lower
        sta pf_store+2
        sta pf_store2+2
        ldx #0
-       lda N_BUFFER,x
pf_store:
        sta $ff00,x
        lda N_BUFFER+160,x
pf_store2:
        sta $ffa0,x
        inx
        cpx #160
        bne -
        clc
+       rts
pf_short:
        sec
        rts

; A = a character row: its 320 bitmap bytes into N_BUFFER; carry set on failure.
ps_row:
        sta ps_math             ; offset = row*320 = row*256 + row*64
        lsr
        lsr
        clc
        adc ps_math
        sta N_OFFSET+1
        lda ps_math
        lsr
        ror
        ror
        and #$c0
        sta N_OFFSET
        lda #<320
        sta N_COUNT
        lda #>320
        sta N_COUNT+1
        ldx #3
-       lda gm_surface,x
        sta N_HANDLE,x
        dex
        bpl -
        lda N_CURRENT
        sta N_OWNER
        jmp N_READ

PRT_LFN = 121
print_absent:                   ; "[1][No printer answers|on device 4.][OK]"
        lda gm_prt_dev
        ora #$30
        sta s_noprinter_dev
        lda #<s_noprinter
        ldx #>s_noprinter
        jmp ps_alert
printer_open:                   ; logical file 121 to the Control Panel's printer
        lda #0                  ; (device 4 or 5, secondary 7 or 0); carry set if refused
        tax
        jsr $ff68
        lda #PRT_LFN
        ldx gm_prt_dev
        ldy gm_prt_sa
        jsr $ffba
        lda #0
        jsr $ffbd
        jmp $ffc0

prt .block
.include "gemdesk-stream.inc"
; Rows dropped on the Printer icon (GDCPY hands them over) are sent to IEC
; device 4 through the KERNAL (logical file 121, secondary address 7): a Paint
; picture (the UPNT header) in bit-image bands, as Print Screen; an IEC file as
; it is stored (PETSCII); a USB file with its ASCII letters swapped for PETSCII
; and each CR, LF or CR LF sent as CR. Esc stops between 512-byte chunks.
print_target:
        ldx gm_slot
        lda gm_win_dev,x
        sta sdev
        lda gm_win_fmt,x
        sta sfmt
        lda #0
        sta stop
        sta dfmt                ; (so check refuses a folder)
        sta gm_alen
        lda #<s_print
        ldx #>s_print
        jsr gm_astr
        ldx gm_slot
        lda gm_nsel,x
        cmp #2
        bcs print_many
        jsr gm_read_record
        bcc +
        jmp gm_view_fail
+       jsr check
        bcs print_done
        jsr gm_aname
        jmp print_ask
print_many:
        sta gm_num
        lda #0
        sta gm_num+1
        jsr gm_anum
        lda #<gm_s_items
        ldx #>gm_s_items
        jsr gm_astr
print_ask:                      ; "[2][Print NAME?][Print|Cancel]"
        lda #<s_print_choice
        ldx #>s_print_choice
        jsr gm_astr
        lda #0
        jsr gm_aput
        lda #<gm_abuf
        ldx #>gm_abuf
        ldy #1
        jsr gm_alert
        bcs print_done
        lda N_BUFFER
        cmp #1
        bne print_done
        jsr printer_open        ; the printer, once for every row
        bcs print_absent
        lda #<print_item
        ldx #>print_item
        jsr gm_each
        lda #PRT_LFN
        jsr $ffc3
        lda stop                ; 2: the printer stopped answering
        cmp #2
        beq print_absent
print_done:
        rts
; One row: its bytes to the printer. Refusals and read failures are reported
; and the next row is tried; Esc, or a printer that stops answering, ends it.
print_item:
        lda stop
        bne print_done
        jsr gm_read_record
        bcs print_done
        jsr check
        bcs print_done
        jsr source_name
        bcs print_done
        lda #0
        sta ep_last
        sta handles
        sta handles+1
        sta handles+2
        sta handles+3
        ldx #0
        lda #0
        jsr open
        bcs print_failed
        lda #16                 ; the header a picture starts with
        jsr read_head
        bcs print_failed
        ldx #11
-       lda N_BUFFER,x
        cmp upnt,x
        bne print_have          ; not a picture: these bytes are text
        dex
        bpl -
        lda size
        cmp #16
        beq print_picture
        bne print_have
print_failed:
        jsr fail                ; (fail reports; the handle is closed below)
        jmp print_close
print_chunk:
        jsr read_source
        bcs print_failed
print_have:
        lda size
        ora size+1
        beq print_close
        ldx #PRT_LFN
        jsr $ffc9               ; CHKOUT (the file service reset the channels)
        bcs print_gone
        lda $90
        bmi print_gone
        lda #<N_BUFFER
        sta print_read+1
        lda #>N_BUFFER
        sta print_read+2
        lda size
        sta pleft
        lda size+1
        sta pleft+1
print_byte:
print_read:
        lda $ffff
        ldx sfmt
        cpx #3
        bne print_out           ; IEC: as stored
        jsr ascii_petscii
        bcs print_next
print_out:
        jsr $ffd2
        lda $90
        bmi print_gone
print_next:
        inc print_read+1
        bne +
        inc print_read+2
+       lda pleft
        bne +
        dec pleft+1
+       dec pleft
        lda pleft
        ora pleft+1
        bne print_byte
        jsr $ffcc               ; CLRCHN before the next read
        lda eof
        bne print_close
        jsr cancel
        bcc print_chunk
        lda #1
        sta stop
        lda #<s_print_stopped
        ldx #>s_print_stopped
        jsr refuse
        jmp print_close
print_gone:
        jsr $ffcc
        lda #2
        sta stop
print_close:
        ldx #0
        jsr close_one
        rts

; A picture: its 25 character rows, two held at a time, in bit-image bands.
print_picture:
        lda #1
        sta ps_file
        lda #0
        sta ps_top
        lda #>PIC_ROWS          ; row 0, then row 1 below it
        sta pf_lower
        jsr pf_read_lower
        bcs pic_short
        lda #>PIC_ROWS
        sta pf_upper
        lda #>(PIC_ROWS+512)
        sta pf_lower
        jsr pf_read_lower
        bcs pic_short
        jsr ps_bands
        bcc print_close
        cmp #2
        beq print_gone0
        lda #1                  ; Esc, or a row that could not be read
        sta stop
        lda #<s_print_stopped
        ldx #>s_print_stopped
        jsr refuse
        jmp print_close
print_gone0:
        sta stop
        jmp print_close
pic_short:
        lda #N_IOERROR
        bne print_failed
PIC_ROWS = gm_sortbuf+1024      ; two rows of 320 bytes, a 512-byte page pair each
stop: .byte 0                   ; 1 Esc, 2 the printer stopped answering
upnt: .byte 85,80,78,84,1,0,$40,$01,$c8,0,$28,$23   ; UPNT, version 1, 320x200, 9000 bytes

; A = an ASCII byte -> PETSCII, carry clear; carry set to leave it out.
ascii_petscii:
        ldx ep_last
        sta ep_last
        cmp #10
        bne +
        cpx #13                 ; CR LF: the CR ended the line
        beq ap_skip
        lda #13
        clc
        rts
+       cmp #13
        beq ap_keep
        cmp #9
        bne +
        lda #32
        clc
        rts
+       cmp #32
        bcc ap_skip
        cmp #127
        bcs ap_skip
        cmp #$41
        bcc ap_keep
        cmp #$5b
        bcs +
        ora #$80
        clc
        rts
+       cmp #$61
        bcc ap_keep
        cmp #$7b
        bcs ap_keep
        and #$df
ap_keep:
        clc
        rts
ap_skip:
        sec
        rts

s_print: .byte 91,50,93,91,80,114,105,110,116,32,0   ; [2][Print 
s_print_choice: .byte 63,93,91,80,114,105,110,116,124,67,97,110,99,101,108,93,0   ; ?][Print|Cancel]
s_print_stopped: .byte 91,49,93,91,80,114,105,110,116,105,110,103,32,115,116,111,112,112,101,100,46,124,84,104
        .byte 101,32,112,114,105,110,116,101,114,32,109,97,121,32,104,111,108,100,124,112,97,114,116,32
        .byte 111,102,32,97,32,102,105,108,101,46,93,91,79,75,93,0   ; [1][Printing stopped.|The printer may hold|part of a file.][OK]
ep_last: .byte 0
pleft: .word 0
.bend
ps_file: .byte 0                ; 0 the surface, 1 a picture file
ps_top: .byte 0                 ; a picture: the character row held as the upper
pf_upper: .byte 0               ; the pages of the two held rows
pf_lower: .byte 0
s_noprinter: .byte 91,49,93,91,78,111,32,112,114,105,110,116,101,114,32,97,110,115,119,101,114,115,124,111,110,32,100,101,118,105,99,101,32
s_noprinter_dev: .byte 52,46,93,91,79,75,93,0   ; [1][No printer answers|on device 4.][OK]
s_prtscr_stopped: .byte 91,49,93,91,80,114,105,110,116,32,83,99,114,101,101,110,124,115,116,111,112,112,101,100,46,93,91,79,75,93,0   ; [1][Print Screen|stopped.][OK]
ps_y: .byte 0
ps_rows: .byte 0
ps_cells: .byte 0
ps_mask: .byte 0
ps_dots: .byte 0
ps_math: .byte 0
ps_cell16: .fill 16,0
ps_first = gm_sortbuf           ; a band's first character row (320 bytes)
sdev: .byte 0                   ; (a temporary for print_target)
.bend
gm_mod_prt_end:
.cerror gm_mod_prt_end > N_APPBASE+GM_APP_PAGES*256, "GDPRT.PRG exceeds the module window: ", gm_mod_prt_end
