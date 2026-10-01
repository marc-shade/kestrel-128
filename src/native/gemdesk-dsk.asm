; GDDSK.PRG (assembled on its own against the core's labels, gemdesk.sym,
; which build-native-desktop.py writes first; docs/NATIVE-MODULES.md).
.include "gemdesk.sym"
* = gm_module
; GDDSK.PRG (docs/GEM-DESKTOP.md): a drive icon dropped on the other drive's
; icon copies the whole disk, every sector of every track, through a buffer
; channel ("#") on each drive: U1 reads a source sector into the source
; drive's buffer and its 256 bytes are read; B-P, the bytes and U2 write them
; on the target; U1 on the target reads the sector back to be compared. Each
; drive's status is read after every command. Both drives must hold the same
; geometry (D64, D71 or D81). Esc stops between tracks. With gm_mop =
; GM_MOP_LOCK it sets or clears a file's lock instead (lock, below).
; Entry: gm_icon_sel = the dragged (source) icon, gm_target = the target icon.
gm_mod_dsk:
        .text "nmod"
        .byte 1,1,14,0
        .word gm_mod_dsk_end-gm_mod_dsk
        .word 0
        .word dsk.entry-gm_mod_dsk
        .word 0
dsk .block
SCMD = 118                      ; KERNAL files: the kernel uses 122..126, the printer 121
SDATA = 117
DCMD = 116
DDATA = 115
entry:
        lda gm_mop
        cmp #GM_MOP_LOCK
        bne +
        jmp lock
+
        ldx gm_target
        jsr gm_icon_drive
        lda gm_dev
        sta ddev
        lda gm_fmt
        sta fmt
        ldx gm_icon_sel
        jsr gm_icon_drive
        lda gm_dev
        sta sdev
        cmp ddev
        beq done                ; one drive under two icons
        lda gm_fmt
        cmp fmt
        bne kinds
        cmp #3
        bcc +
kinds:                          ; "[1][Both drives must hold|the same kind of disk.][OK]"
        lda #<s_kinds
        ldx #>s_kinds
        ldy #1
        jmp gm_alert
+       tax
        lda last_track,x
        sta tracks
        lda #0                  ; "[3][Copy the disk in drive 8|onto drive 9? Everything|on drive 9 is replaced.][Copy|Cancel]"
        sta gm_alen
        lda #<s_ask
        ldx #>s_ask
        jsr gm_astr
        lda sdev
        jsr put_device
        lda #<s_onto
        ldx #>s_onto
        jsr gm_astr
        lda ddev
        jsr put_device
        lda #<s_every
        ldx #>s_every
        jsr gm_astr
        lda ddev
        jsr put_device
        lda #<s_replaced
        ldx #>s_replaced
        jsr gm_astr
        lda #0
        jsr gm_aput
        lda #<gm_abuf
        ldx #>gm_abuf
        ldy #2                  ; Cancel is the default
        jsr gm_alert
        bcs done
        lda N_BUFFER
        cmp #1
        beq copy
done:
        rts
put_device:                     ; A = a device number, in decimal
        sta gm_num
        lda #0
        sta gm_num+1
        jmp gm_anum

copy:
        lda N_FBUSY             ; no kernel stream may hold either drive
        ora N_BUSY
        bne busy
        ldx #1
-       lda NFCMDS,x
        cmp sdev
        beq busy
        cmp ddev
        beq busy
        dex
        bpl -
        jsr save_files
        lda sdev                ; each drive: the command channel, then a buffer
        ldx #SCMD
        jsr open_pair
        bcs failed
        lda ddev
        ldx #DCMD
        jsr open_pair
        bcs failed
        jsr progress_open
        lda #1
        sta track
track_loop:
        jsr progress_title
        lda track               ; sectors on this track
        ldx fmt
        cpx #2
        bne zones
        lda #40                 ; D81: 40 on every track
        bne have_sectors
zones:
        cmp #36                 ; D64/D71: zones, the second side as the first
        bcc +
        sbc #35
+       ldx #3
-       cmp zone_start,x
        bcs +
        dex
        bne -
+       lda zone_sectors,x
have_sectors:
        sta sectors
        lda #0
        sta sector
sector_loop:
        lda #$31                ; source: U1
        ldx #SCMD
        jsr u_command
        bcs failed
        ldx #SDATA
        jsr $ffc6               ; CHKIN
        bcs no_answer
        lda #0
        sta index
-       jsr $ffcf               ; CHRIN
        ldy index
        sta buffer,y
        inc index
        bne -
        jsr end_transfer
        bcs no_answer
        ldx #DCMD               ; target: B-P, the bytes, U2
        lda #<s_bp
        ldy #>s_bp
        jsr fixed_command
        bcs failed
        ldx #DDATA
        jsr $ffc9               ; CHKOUT
        bcs no_answer
        lda #0
        sta index
-       ldy index
        lda buffer,y
        jsr $ffd2               ; CHROUT
        inc index
        bne -
        jsr end_transfer
        bcs no_answer
        lda #$32
        ldx #DCMD
        jsr u_command
        bcs failed
        lda #$31                ; and read back
        ldx #DCMD
        jsr u_command
        bcs failed
        ldx #DDATA
        jsr $ffc6
        bcs no_answer
        lda #0
        sta index
        sta differ
-       jsr $ffcf
        ldy index
        cmp buffer,y
        beq +
        inc differ
+       inc index
        bne -
        jsr end_transfer
        bcs no_answer
        lda differ
        bne mismatch
        inc sector
        lda sector
        cmp sectors
        bcc sector_loop
        jsr N_KEYIN             ; Esc stops between tracks
        cmp #27
        beq stopped
        inc track
        lda tracks
        cmp track
        bcs track_loop
        jsr close_all           ; "[1][Disk copied and compared.][OK]"
        lda #<s_done
        ldx #>s_done
        bne report
busy:                           ; "[1][A drive is in use;|try again.][OK]"
        lda #<s_busy
        ldx #>s_busy
        ldy #1
        jmp gm_alert
stopped:                        ; "[1][Disk copy stopped.|Drive 9 holds part|of the copy.][OK]"
        jsr close_all
        lda #0
        sta gm_alen
        lda #<s_stopped
        ldx #>s_stopped
        jsr gm_astr
        lda ddev
        jsr put_device
        lda #<s_part
        ldx #>s_part
        bne report_built
mismatch:                       ; "[3][Disk copy stopped at|track T, sector S:|the copy differs.][OK]"
        lda #<s_differs
        ldx #>s_differs
        bne failure
no_answer:
        jsr $ffcc
        lda #<s_no_answer       ; "a drive did not answer."
        ldx #>s_no_answer
        bne failure
failed:                         ; the drive's status line
        lda #<line
        ldx #>line
failure:
        pha
        txa
        pha
        jsr close_all
        lda #0
        sta gm_alen
        lda #<s_failed
        ldx #>s_failed
        jsr gm_astr
        lda track
        jsr put_device
        lda #<s_sector
        ldx #>s_sector
        jsr gm_astr
        lda sector
        jsr put_device
        lda #$3a
        jsr gm_aput
        lda #$7c
        jsr gm_aput
        pla
        tax
        pla
report_built:
        jsr gm_astr
        lda #<s_ok
        ldx #>s_ok
        jsr gm_astr
        lda #0
        jsr gm_aput
        lda #<gm_abuf
        ldx #>gm_abuf
report:
        ldy #1
        jsr gm_alert
        lda ddev                ; the target's windows are listed again
        sta gm_dev
        lda fmt
        sta gm_fmt
        jmp gm_refresh_drive

.include "gemdesk-sector.inc"
; The KERNAL's file parameters, as the file service keeps them, for
; close_all to restore; no KERNAL messages.
save_files:
        ldx #8
-       lda $b7,x
        sta saved,x
        dex
        bpl -
        lda $c6
        sta saved+9
        lda $c7
        sta saved+10
        lda $9d
        sta saved+11
        lda #0
        sta $9d
        sta track
        sta sector
        lda #1
        sta opened
        rts

; ---- the read-only lock (Show Info, GM_MOP_LOCK) ---------------------------------
; CBM DOS has no lock command, so the entry's type byte (bit 6: locked) is
; changed where the drive keeps it: the directory chain from 18/1 (D64, D71)
; or 40/3 (D81) is read (U1) until a closed file has gm_lock_name; that
; sector is written back (B-P 0, its 256 bytes, U2) with the bit as
; gm_lock_want says, and read again (U1) to prove it. Then gm_slot's drive is
; listed again. A failure is reported with the drive's status line.
lock:
        lda gm_lock_want
        and #$40
        sta lk_want
        lda #0
        sta gm_lock_want
        sta lk_count
        ldx gm_slot
        lda gm_win_fmt,x
        sta fmt
        lda gm_win_dev,x
        sta sdev
        ldx N_FBUSY             ; no kernel stream may hold the drive
        bne lk_busy
        ldx N_BUSY
        bne lk_busy
        ldx #1
-       cmp NFCMDS,x
        beq lk_busy
        dex
        bpl -
        jsr save_files
        lda sdev
        ldx #SCMD
        jsr open_pair
        bcs lk_failed
        ldx #18                 ; the directory's first sector
        ldy #1
        lda fmt
        cmp #2
        bne +
        ldx #40
        ldy #3
+       stx track
        sty sector
lk_sector:
        inc lk_count            ; (a D81 directory has 37 sectors)
        lda lk_count
        cmp #40
        bcs lk_missing
        jsr lk_read
        bcs lk_failed
        ldx #2                  ; each entry's type byte, 32 apart
lk_entry:
        stx lk_at
        lda buffer,x
        bpl lk_next             ; not a closed file
        ldy #0
-       lda buffer+3,x          ; the name, after the first block's address
        cmp gm_lock_name,y
        bne lk_next
        inx
        iny
        cpy #16
        bne -
        beq lk_found
lk_next:
        lda lk_at
        clc
        adc #32
        tax
        bcc lk_entry
        lda buffer              ; the next directory sector
        beq lk_missing
        sta track
        lda buffer+1
        sta sector
        jmp lk_sector
lk_busy:                        ; "[1][A drive is in use;|try again.][OK]"
        lda #<s_busy
        ldx #>s_busy
        ldy #1
        jsr gm_alert
        jmp lk_relist
lk_missing:                     ; "[3][Could not set read-only:|it is not in the directory.][OK]"
        lda #<s_lk_missing
        ldx #>s_lk_missing
        bne lk_report
lk_found:
        ldx lk_at
        lda buffer,x
        and #$bf
        ora lk_want
        sta buffer,x
        sta lk_type
        ldx #SCMD
        lda #<s_bp
        ldy #>s_bp
        jsr fixed_command
        bcs lk_failed
        ldx #SDATA
        jsr $ffc9               ; CHKOUT
        bcs lk_absent
        lda #0
        sta index
-       ldy index
        lda buffer,y
        jsr $ffd2               ; CHROUT
        inc index
        bne -
        jsr end_transfer
        bcs lk_quiet
        lda #$32                ; U2
        ldx #SCMD
        jsr u_command
        bcs lk_failed
        jsr lk_read             ; and read back
        bcs lk_failed
        ldx lk_at
        lda buffer,x
        cmp lk_type
        bne lk_unproven
        jsr close_all
        jmp lk_relist
lk_unproven:                    ; "...|the drive did not keep it.][OK]"
        lda #<s_lk_unproven
        ldx #>s_lk_unproven
        bne lk_report
lk_absent:
        jsr $ffcc
lk_quiet:
        jsr st_bad              ; line = "a drive did not answer."
lk_failed:                      ; the drive's status line
        lda #<line
        ldx #>line
lk_report:
        pha
        txa
        pha
        jsr close_all
        lda #0
        sta gm_alen
        lda #<s_lk_head
        ldx #>s_lk_head
        jsr gm_astr
        pla
        tax
        pla
        jsr gm_astr
        lda #<s_ok
        ldx #>s_ok
        jsr gm_astr
        lda #0
        jsr gm_aput
        lda #<gm_abuf
        ldx #>gm_abuf
        ldy #1
        jsr gm_alert
lk_relist:
        lda sdev
        sta gm_dev
        lda fmt
        sta gm_fmt
        jmp gm_refresh_drive
; U1 on track/sector, the 256 bytes into buffer. Carry set: line says why.
lk_read:
        lda #$31
        ldx #SCMD
        jsr u_command
        bcs lk_read_done
        ldx #SDATA
        jsr $ffc6               ; CHKIN
        bcs +
        lda #0
        sta index
-       jsr $ffcf               ; CHRIN
        ldy index
        sta buffer,y
        inc index
        bne -
        jsr end_transfer
        bcc lk_read_done
+       jsr $ffcc
        jmp st_bad
lk_read_done:
        rts
; Close the progress window, then the four files (buffers before command
; channels), and restore the KERNAL's file parameters.
close_all:
        jsr progress_close
        lda opened
        beq closed
        lda #SDATA
        jsr $ffc3
        lda #DDATA
        jsr $ffc3
        lda #SCMD
        jsr $ffc3
        lda #DCMD
        jsr $ffc3
        ldx #8
-       lda saved,x
        sta $b7,x
        dex
        bpl -
        lda saved+9
        sta $c6
        lda saved+10
        sta $c7
        lda saved+11
        sta $9d
        lda #0
        sta opened
closed:
        rts

; ---- progress: a title-only window, "Copy track T/N" (titles hold 16 characters) --
.include "gemdesk-progress.inc"
progress_text:                  ; "Copy track T/N" into gm_abuf
        lda #0
        sta gm_alen
        lda #<s_copying
        ldx #>s_copying
        jsr gm_astr
        lda track
        jsr put_device
        lda #<s_of
        ldx #>s_of
        jsr gm_astr
        lda tracks
        jsr put_device
        lda #0
        jmp gm_aput


last_track: .byte 35,70,80
zone_start: .byte 1,18,25,31     ; D64 zones: tracks 1-17, 18-24, 25-30, 31-35
zone_sectors: .byte 21,19,18,17
s_kinds: .byte 91,49,93,91,66,111,116,104,32,100,114,105,118,101,115,32,109,117,115,116,32,104,111,108,100,124,116,104,101,32,115,97,109,101,32,107,105,110,100,32,111,102,32,100,105,115,107,46,93,91,79,75,93,0   ; [1][Both drives must hold|the same kind of disk.][OK]
s_ask: .byte 91,51,93,91,67,111,112,121,32,116,104,101,32,100,105,115,107,32,105,110,32,100,114,105,118,101,32,0   ; [3][Copy the disk in drive 
s_onto: .byte 124,111,110,116,111,32,100,114,105,118,101,32,0   ; |onto drive 
s_replaced: .byte 32,105,115,32,114,101,112,108,97,99,101,100,46,93,91,67,111,112,121,124,67,97,110,99,101,108,93,0   ;  is replaced.][Copy|Cancel]
s_every: .byte 63,32,69,118,101,114,121,116,104,105,110,103,124,111,110,32,100,114,105,118,101,32,0   ; ? Everything|on drive 
s_busy: .byte 91,49,93,91,65,32,100,114,105,118,101,32,105,115,32,105,110,32,117,115,101,59,124,116,114,121,32,97,103,97,105,110,46,93,91,79,75,93,0   ; [1][A drive is in use;|try again.][OK]
s_done: .byte 91,49,93,91,68,105,115,107,32,99,111,112,105,101,100,32,97,110,100,32,99,111,109,112,97,114,101,100,46,93,91,79,75,93,0   ; [1][Disk copied and compared.][OK]
s_stopped: .byte 91,49,93,91,68,105,115,107,32,99,111,112,121,32,115,116,111,112,112,101,100,46,124,68,114,105,118,101,32,0   ; [1][Disk copy stopped.|Drive 
s_part: .byte 32,104,111,108,100,115,32,112,97,114,116,124,111,102,32,116,104,101,32,99,111,112,121,46,0   ;  holds part|of the copy.
s_failed: .byte 91,51,93,91,68,105,115,107,32,99,111,112,121,32,115,116,111,112,112,101,100,32,97,116,124,116,114,97,99,107,32,0   ; [3][Disk copy stopped at|track 
s_sector: .byte 44,32,115,101,99,116,111,114,32,0   ; , sector 
s_differs: .byte 116,104,101,32,99,111,112,121,32,100,105,102,102,101,114,115,46,0   ; the copy differs.
s_copying: .byte 67,111,112,121,32,116,114,97,99,107,32,0   ; Copy track 
s_of: .byte 47,0   ; /
s_ok: .byte 93,91,79,75,93,0   ; ][OK]
s_lk_head: .byte 91,51,93,91,67,111,117,108,100,32,110,111,116,32,115,101,116,32,114,101,97,100,45,111,110,108,121,58,124,0   ; [3][Could not set read-only:|
s_lk_missing: .byte 105,116,32,105,115,32,110,111,116,32,105,110,32,116,104,101,32,100,105,114,101,99,116,111,114,121,46,0   ; it is not in the directory.
s_lk_unproven: .byte 116,104,101,32,100,114,105,118,101,32,100,105,100,32,110,111,116,32,107,101,101,112,32,105,116,46,0   ; the drive did not keep it.
lk_want: .byte 0
lk_type: .byte 0
lk_at: .byte 0
lk_count: .byte 0
sdev: .byte 0
ddev: .byte 0
fmt: .byte 0
tracks: .byte 0
track: .byte 0
sector: .byte 0
sectors: .byte 0
differ: .byte 0
opened: .byte 0
saved: .fill 12,0
buffer = gm_sortbuf+1024         ; a sector (painting fills only the rows below 512)
.bend
gm_mod_dsk_end:
.cerror gm_mod_dsk_end > N_APPBASE+GM_APP_PAGES*256, "GDDSK.PRG exceeds the module window: ", gm_mod_dsk_end
