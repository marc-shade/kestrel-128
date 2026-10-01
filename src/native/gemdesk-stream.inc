; Stream helpers shared by GDCPY and GDDSK's printing (included in each
; module's block): the row's checks and full name, opening, reading and
; closing through the file service, the Esc check, and the failure alert.
; gm_rec: carry set, with an alert, for what cannot be copied: a folder, an
; unclosed ("splat") file, REL.
check:
        lda #0
        sta isdir
        lda sfmt
        cmp #3
        beq usb_check
        lda gm_rec+17           ; an unclosed file has no checked extent
        bpl unsupported
        lda gm_rec+16           ; SEQ 1, PRG 2, USR 3 -> 0, 1, 2
        and #7
        beq unsupported
        cmp #4
        bcs unsupported         ; REL and DIR are not streams
        sec
        sbc #1
        sta stype
        clc
        rts
usb_check:
        lda gm_rec+20
        jsr gm_ult_fullname
        bcs fail
        lda gm_ult_attr
        and #$10
        sta isdir
        beq +                   ; a file
        lda dfmt                ; a folder: only onto USB
        cmp #3
        bne unsupported
+       clc
        rts
unsupported:
        lda #<s_unsupported
        ldx #>s_unsupported
refuse:                         ; A/X = the alert
        ldy #1
        jsr gm_alert
        sec
        rts

; The source's full name in spath/slen (and its leaf in gm_name/gm_nlen).
source_name:
        lda sfmt
        cmp #3
        bne iec_name
        lda gm_rec+20
        jsr gm_ult_fullname     ; N_UPATH/N_FNAMELEN; the leaf in gm_name/gm_nlen
        bcs fail
        ldx #0
-       lda N_UPATH,x
        sta spath,x
        inx
        cpx N_FNAMELEN
        bne -
        stx slen
        lda #0
        sta stype
        clc
        rts
iec_name:
        ldx #0
-       lda gm_rec,x
        cmp #$a0
        beq +
        sta spath,x
        sta gm_name,x
        inx
        cpx #16
        bne -
+       stx slen
        stx gm_nlen
        clc
        rts
fail:                           ; "[3][Could not copy|NAME|error $xx][OK]"
        jsr fail_alert
        sec
        rts
fail_alert:
        pha                     ; gm_error_hex takes the code from the stack
        lda #<s_nocopy
        ldx #>s_nocopy
        jsr gm_fail_head
        jmp gm_error_hex

; X = slot (0 source, 4 destination), A = mode (0 read, 1 exclusive create).
; The handle is kept even when OPEN fails, for the close that follows.
open:
        stx slot
        sta N_FMODE
        lda N_CURRENT
        sta N_FOWNER
        lda #0
        ldx #3
-       sta N_FHANDLE,x
        dex
        bpl -
        lda slot
        bne open_destination
        lda sdev
        sta N_FDEVICE
        lda sfmt
        sta N_FFORMAT
        lda stype
        sta N_FTYPE
        lda slen
        sta N_FNAMELEN
        ldx #0
-       lda spath,x
        sta N_UPATH,x
        cpx #16
        bcs +
        sta N_FNAME,x
+       inx
        bne -
        beq open_call
open_destination:
        lda dopen
        sta N_FDEVICE
        lda dfmt
        sta N_FFORMAT
        lda dtype
        sta N_FTYPE
        lda dlen
        sta N_FNAMELEN
        ldx #0
-       lda dpath,x
        sta N_UPATH,x
        cpx #16
        bcs +
        sta N_FNAME,x
+       inx
        bne -
open_call:
        jsr N_FOPEN
        php
        pha
        ldx slot
        ldy #0
-       lda N_FHANDLE,y
        sta handles,x
        inx
        iny
        cpy #4
        bne -
        pla
        plp
        rts
select:                         ; X = slot
        stx slot
        lda N_CURRENT
        sta N_FOWNER
        ldy #0
-       lda handles,x
        sta N_FHANDLE,y
        inx
        iny
        cpy #4
        bne -
        rts
read_source:                    ; up to 512 bytes -> size, eof
        lda #0
        ldy #2
        bne read_count
read_head:                      ; A = up to 255 bytes (a file's first) -> size, eof
        ldy #0
read_count:                     ; A/Y = the count
        sta N_FCOUNT
        sty N_FCOUNT+1
        ldx #0
        jsr select
        jsr N_FREAD
        bcs +
        lda N_FACTUAL
        sta size
        lda N_FACTUAL+1
        sta size+1
        lda N_FEOF
        sta eof
        clc
+       rts
cancel:                         ; Esc stops between chunks
        jsr N_KEYIN
        cmp #27
        beq +
        clc
        rts
+       sec
        rts
close_streams:                  ; the destination first, then the source
        ldx #4
        jsr close_one
        bcs +
        ldx #0
close_one:
        lda handles,x
        ora handles+1,x
        ora handles+2,x
        ora handles+3,x
        beq closed
        stx close_at
        jsr select
        jsr N_FCLOSE
        bcs +
        ldx close_at
        lda #0
        sta handles,x
        sta handles+1,x
        sta handles+2,x
        sta handles+3,x
closed:
        clc
+       rts

s_nocopy: .byte 91,51,93,91,67,111,117,108,100,32,110,111,116,32,99,111,112,121,124,0   ; [3][Could not copy|
s_unsupported: .byte 91,49,93,91,70,111,108,100,101,114,115,32,111,110,116,111,32,97,32,100,114,105,118,101,44,124,82,69,76,32,97,110,100,32,117,110,99,108,111,115,101,100,32,102,105,108,101,115,124,99,97,110,110,111,116,32,98,101,32,99,111,112,105,101,100,46,93,91,79,75,93,0   ; [1][Folders onto a drive,|REL and unclosed files|cannot be copied.][OK]
isdir: .byte 0                  ; the row is a folder
dfmt: .byte 0
dopen: .byte 0
dtype: .byte 0
dlen: .byte 0
sdev: .byte 0
sfmt: .byte 0
stype: .byte 0
slen: .byte 0
slot: .byte 0
close_at: .byte 0
size: .word 0
eof: .byte 0
handles: .fill 8,0
spath = gm_sortbuf+512          ; the names, after a 512-byte chunk (painting,
dpath = gm_sortbuf+768          ; only when a progress window closes, fills just
                                ; the rows buffer below 512)
.cerror 24*GM_RECORD > 512, "painting would overwrite the copy's names"
.cerror GM_MAX_ENTRIES*GM_RECORD < 1024, "the sort workspace holds the chunk and both names"
