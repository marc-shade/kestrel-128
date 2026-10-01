; GDCPY.PRG (docs/GEM-DESKTOP.md): the selected rows of a window, dropped on
; another window or on a drive icon, are copied there as Files copies
; (src/native/files-copy.inc): each target is created exclusively, closed,
; then reopened and compared with the reopened source, including a final read
; that proves it has no extra tail. Move deletes each source only after that
; comparison. No partial target is deleted. While rows are copied, a
; "Copying N/M" ("Moving N/M") window shows which one; alerts about a row
; appear over it, and it closes when the rows are done. A USB folder dropped
; on USB is copied as a tree: the folder is made (CREATE_DIR, proven by
; FILE_STAT), then each entry is read again from the source folder by its
; position and copied, a folder by descending into it; a folder of the same
; name on the target is merged into. Move then deletes the source's contents,
; deepest first, and the emptied folder last, unless a name conflict in the
; row was skipped.
; Entry: gm_slot and its selection = the dragged rows; gm_cx/gm_cy = the cell
; where they were released.
copyop .block
entry:
        lda #WS_FIND
        sta N_BUFFER
        lda gm_cx
        sta N_BUFFER+1
        lda gm_cy
        sta N_BUFFER+2
        jsr gm_wcall
        bcs done
        ldx N_BUFFER
        beq icon
        jsr gm_slot_of
        bcs done
        cpx gm_slot
        beq done                ; within its own window: nothing
        stx dslot
        lda gm_win_dev,x
        sta ddev
        lda gm_win_fmt,x
        sta dfmt
        jmp target_known
icon:
        jsr gm_icon_hit         ; Boot, Drive 9, USB (the core deletes on Trash and
        cpx #2                  ; hands the Printer to GDDSK)
        beq done
        inx
        beq done
        dex
        lda #$ff
        sta dslot
        jsr gm_icon_drive
        lda gm_dev
        sta ddev
        lda gm_fmt
        sta dfmt
target_known:
        ldx gm_slot
        lda gm_win_dev,x
        sta sdev
        lda gm_win_fmt,x
        sta sfmt
        lda #0
        sta stop
        sta gm_alen
        lda #<s_copy
        ldx #>s_copy
        jsr gm_astr
        ldx gm_slot
        lda gm_nsel,x
        cmp #2
        bcs ask_many
        jsr gm_read_record      ; one row: refused before the question
        bcc +
        jmp gm_view_fail
+       jsr check
        bcs done
        jsr gm_aname
        jmp ask
ask_many:
        sta gm_num
        lda #0
        sta gm_num+1
        jsr gm_anum
        lda #<gm_s_items
        ldx #>gm_s_items
        jsr gm_astr
; "[2][Copy NAME|to DEST?][Copy|Move|Cancel]" ("Copy N items"): Copy is the
; default. With Confirm copies off in Preferences, the rows are copied
; without the question (Move needs it).
ask:
        lda gm_confirm
        and #GM_NOCOPYASK
        beq +
        lda #1                  ; Copy
        bne chosen
+       lda #<s_to
        ldx #>s_to
        jsr gm_astr
        jsr adest
        lda #<s_choice
        ldx #>s_choice
        jsr gm_astr
        lda #0
        jsr gm_aput
        lda #<gm_abuf
        ldx #>gm_abuf
        ldy #1
        jsr gm_alert
        bcs done
        lda N_BUFFER
        cmp #3
        bcs done                ; Cancel
chosen:
        sta choice
        lda gm_confirm          ; Move deletes without a second question
        pha
        and #$fe
        sta gm_confirm
        lda #0
        sta created
        sta item_no
        ldx gm_slot             ; the rows to count: at least the one dragged
        lda gm_nsel,x
        bne +
        lda #1
+       sta total
        inc gm_batch            ; and without listing between rows
        lda #<item
        ldx #>item
        jsr gm_each
        jsr progress_close      ; before the listings are painted again
        dec gm_batch
        pla
        sta gm_confirm
        lda choice              ; list again: the source's drive after Move,
        cmp #2
        bne +
        jsr gm_relist_slot
+       lda created             ; then the target's, if anything was created
        beq done
        lda ddev
        sta gm_dev
        lda dfmt
        sta gm_fmt
        jmp gm_refresh_drive
done:
        rts

; One row (gm_slot's gm_win_sel): refusals and failures are reported, and
; the next row is tried; Esc stops them all.
item:
        inc item_no
        lda #0
        sta skipped
        lda stop
        bne item_done
        jsr gm_read_record
        bcs item_done
        jsr check
        bcs item_done
        jsr names
        bcs item_done
        lda pw                  ; the progress window: opened for the first
        bne +                   ; row that is copied, retitled for each next
        jsr progress_open
        jmp ++
+       jsr progress_title
+       lda isdir
        bne item_tree
        jsr copy_new
item_copied:
        bcs item_done
        lda skipped             ; something was skipped: Move keeps the source
        bne item_done
        lda choice
        cmp #2
        bne item_done
        lda isdir               ; a folder: its contents first
        beq +
        jsr empty
        bcs item_done
+       jmp gm_delete_one
item_done:
        rts
item_tree:
        jsr tree
        jmp item_copied

; The source's full name, then the target's. Carry set, with an alert, when
; the target cannot take it.
names:
        jsr source_name
        bcc destination
        rts
destination:
        lda dfmt
        cmp #3
        beq usb_destination
        ldx gm_nlen             ; a drive: 1..16 characters without DOS syntax
        beq badname
        cpx #17
        bcs badname
        stx dlen
        dex
name_char:
        lda gm_name,x
        sta dpath,x
        ldy #gm_bad_chars_end-gm_bad_chars-1
-       cmp gm_bad_chars,y
        beq badname
        dey
        bpl -
        dex
        bpl name_char
        lda stype
        ldx sfmt
        cpx #3
        bne +
        jsr prg_suffix          ; from USB: ".PRG" becomes PRG, the rest SEQ
+       sta dtype
        lda ddev
        sta dopen
        clc
        rts
badname:
        lda #<s_badname
        ldx #>s_badname
        jmp refuse
usb_destination:
        lda #$2f                ; an icon: the root
        sta dpath
        ldx #1
        ldy dslot
        bmi usb_leaf
        lda gm_slot             ; a window: its path
        pha
        sty gm_slot
        jsr gm_path_page
        pla
        sta gm_slot
        ldx dslot
        lda gm_win_plen,x
        sta dlen
        ldy #0
-       cpy dlen
        beq +
        jsr gm_pr
        sta dpath,y
        iny
        bne -
+       ldx dlen
        lda dpath-1,x
        cmp #$2f
        beq usb_leaf
        lda #$2f
        sta dpath,x
        inx
usb_leaf:
        ldy #0
-       lda gm_name,y
        sta dpath,x
        inx
        beq toolong
        iny
        cpy gm_nlen
        bne -
        stx dlen
        lda #0
        sta dtype
        lda ddev
        ldx sfmt
        cpx #3
        bne +
        lda sdev                ; USB to USB: the other DOS context
        eor #3
+       sta dopen
        clc
        rts
toolong:
        lda #$23                ; the path would exceed 255 bytes
        jmp fail
; A = 1 when gm_name ends in ".PRG" (either case), else 0.
prg_suffix:
        ldx gm_nlen
        cpx #5
        bcc +
        ldy #3
-       dex
        lda gm_name,x
        cmp #$60
        bcc suffix_char
        and #$df
suffix_char:
        cmp suffix,y
        bne +
        dey
        bpl -
        lda #1
        rts
+       lda #0
        rts

; Append the target: "Drive N" or "USB".
adest:
        lda dfmt
        cmp #3
        bne +
        lda #<gm_label_usb
        ldx #>gm_label_usb
        jmp gm_astr
+       lda #<gm_drive_title
        ldx #>gm_drive_title
        jsr gm_astr
        lda ddev
        sta gm_num
        lda #0
        sta gm_num+1
        jmp gm_anum

.include "gemdesk-stream.inc"

; ---- the transfer ------------------------------------------------------------------
; Copy spath to dpath. Carry clear when verified; set after an alert.
copy_new:                       ; a new file: no "Keep both" name yet
        lda #0
        sta keep
copy:
        lda #0
        sta phase
        ldx #7
-       sta handles,x
        sta counts,x
        dex
        bpl -
        inc phase               ; 1: copying
        ldx #0
        lda #0
        jsr open
        bcs io_error
        jsr read_source
        bcs io_error
        lda size
        ora size+1
        bne create
        lda eof
        beq short
        lda dfmt
        cmp #3
        beq create
        ; A drive's DOS writes a CR when a write channel closes empty.
        jsr close_streams
        bcs close_error
        lda #<s_empty
        ldx #>s_empty
        jmp refuse
create:
        jsr stash               ; OPEN may reuse the service buffer
        lda dfmt                ; USB: FILE_STAT first (a drive answers 63)
        cmp #3
        bne +
        lda #$08
        jsr ucmd_d
        bcs +                   ; nothing there
        jsr close_streams
        bcs close_error
        jmp conflict
+       ldx #4
        lda #1                  ; exclusive create
        jsr open
        bcs io_error
        inc created
        jmp write
next_chunk:
        jsr cancel
        bcs cancelled
        jsr read_source
        bcs io_error
        lda size
        ora size+1
        beq written
        jsr stash
write:
        lda size
        ora size+1
        beq written
        ldx #4
        jsr select
        ldx #0
-       lda data,x
        sta N_BUFFER,x
        lda data+256,x
        sta N_BUFFER+256,x
        inx
        bne -
        lda size
        sta N_FCOUNT
        lda size+1
        sta N_FCOUNT+1
        jsr N_FWRITE
        bcs io_error
        jsr acknowledged
        bne short
        ldx #0
        jsr advance
written:
        lda eof
        bne reopen
        lda size
        ora size+1
        bne next_chunk
short:
        lda #N_IOERROR
        jmp io_error
reopen:
        jsr close_streams
        bcs close_error
        inc phase               ; 2: comparing
        ldx #0
        lda #0
        jsr open
        bcs io_error
        ldx #4
        lda #0
        jsr open
        bcs io_error
next_compare:
        jsr cancel
        bcs cancelled
        jsr read_source
        bcs io_error
        lda size
        ora size+1
        beq compared
        jsr stash
        ldx #4
        jsr select
        lda size
        sta N_FCOUNT
        lda size+1
        sta N_FCOUNT+1
        jsr N_FREAD
        bcs io_error
        jsr acknowledged
        bne mismatch
        ldx #0
-       lda size+1              ; the first page: all of it, or size bytes
        bne +
        cpx size
        bcs same
+       lda N_BUFFER,x
        cmp data,x
        bne mismatch
        inx
        bne -
        lda size+1
        beq same
-       cmp #2                  ; the second page
        beq +
        cpx size
        bcs same
+       lda N_BUFFER+256,x
        cmp data+256,x
        bne mismatch
        inx
        lda size+1
        cpx #0
        bne -
same:
        ldx #4
        jsr advance
compared:
        lda eof
        bne tail
        lda size
        ora size+1
        bne next_compare
        beq short
tail:                           ; one more byte must be the end
        ldx #4
        jsr select
        lda #1
        sta N_FCOUNT
        lda #0
        sta N_FCOUNT+1
        jsr N_FREAD
        bcs io_error
        lda N_FACTUAL
        ora N_FACTUAL+1
        bne mismatch
        lda N_FEOF
        beq mismatch
        ldx #3
-       lda counts,x
        cmp counts+4,x
        bne mismatch
        dex
        bpl -
        jsr close_streams
        bcs close_error
        jmp finished

mismatch:
        jsr close_streams
        bcs close_error
        lda #<s_mismatch
        ldx #>s_mismatch
        jmp refuse
cancelled:                      ; "[1][Copy stopped.|DEST may hold|part of NAME.][OK]"
        inc stop
        jsr close_streams
        bcs close_error
        lda #0
        sta gm_alen
        lda #<s_stopped
        ldx #>s_stopped
        jsr gm_astr
        jsr adest
        lda #<s_part
        ldx #>s_part
        jsr gm_astr
        jsr gm_aname
        lda #$2e
        jsr gm_aput
failed_alert:
        jsr gm_info_end
        sec
        rts
io_error:
        sta error
        lda N_FDOS
        sta dos
        lda slot                ; (the close selects other slots)
        sta failed_slot
        jsr close_streams
        bcs close_error
        lda phase               ; creating: 63 is an existing name
        cmp #1
        bne +
        lda failed_slot
        cmp #4
        bne +
        lda dos
        cmp #63
        bne +
        jmp conflict
+       lda error
        jmp fail
exists:                         ; a folder: "[1][NAME already|exists on DEST.][OK]"
        lda #0
        sta gm_alen
        lda #<gm_s_head
        ldx #>gm_s_head
        jsr gm_astr
        jsr gm_aname
        lda #<s_exists
        ldx #>s_exists
        jsr gm_astr
        jsr adest
        lda #$2e
        jsr gm_aput
        jmp failed_alert
close_error:                    ; release everything the desktop owns, then report
        pha
        lda N_CURRENT
        sta N_FOWNER
        jsr N_FRELEASE
        pla
        jmp fail

finished:
        clc
        rts

; A file whose name is on the target: "[2][NAME already|exists on DEST.]
; [Replace|Keep both|Skip]" (NAME: the target's last name, so a file inside a
; folder being merged is named), Skip the default and Esc Stop; or Replace at
; once when Confirm overwrites is off. Replace scratches (a drive) or deletes
; (USB) the target and copies again; Keep both copies under the source's name
; with "-2" before its extension (keep_name), then -3 and on while those are
; taken too, and asks again after -9; Skip goes on with the next file and
; keeps this row's source (skipped); Stop ends the rows. The streams are
; closed. Carry set after Stop, or when the copy after Replace fails.
conflict:
        lda keep
        beq ask_conflict
        cmp #9
        bcs +
        inc keep                ; NAME-N is taken too: the next number
        bne keep_name
+       lda #0
        sta keep
ask_conflict:
        lda gm_confirm
        and #GM_NOOVERASK
        bne replace
        lda #0
        sta gm_alen
        lda #<s_ask_head
        ldx #>s_ask_head
        jsr gm_astr
        jsr aleaf
        lda #<s_exists
        ldx #>s_exists
        jsr gm_astr
        jsr adest
        lda #<s_conflict
        ldx #>s_conflict
        jsr gm_astr
        lda #0
        jsr gm_aput
        lda #<gm_abuf
        ldx #>gm_abuf
        ldy #3
        jsr gm_alert
        bcs conflict_stop       ; Esc
        lda N_BUFFER
        cmp #1
        beq replace
        cmp #2
        beq keep_both
conflict_skip:
        inc skipped
        clc
        rts
conflict_stop:
        inc stop
        sec
        rts
keep_both:
        lda #2
        sta keep
; dpath's last name becomes the source's name (gm_name) with "-N" (N = keep)
; before its extension: the last "." after the first character, or the end.
; A drive keeps 16 characters by shortening the part before the suffix (the
; whole name when the extension leaves too little); USB paths stay within
; 255 bytes. Then the copy starts again.
keep_name:
        ldx dlen
-       dex
        cpx #$ff                ; (paths reach 255 bytes: not bmi)
        beq +
        lda dpath,x
        cmp #$2f
        bne -
+       inx
        stx leaf_at
        ldy gm_nlen
        sty ext_at
-       dey
        beq +
        lda gm_name,y
        cmp #$2e
        bne -
        sty ext_at
+       lda ext_at
        sta base_end
        lda dfmt
        cmp #3
        beq k_usb
        lda gm_nlen             ; a drive: cut what the suffix adds beyond 16
        sec
        sbc #14
        bcc k_build
        beq k_build
        sta k
        lda ext_at
        sec
        sbc k
        bcc +
        bne k_cut
+       lda gm_nlen             ; the extension leaves too little: suffix last
        sta ext_at
        lda #14
k_cut:
        sta base_end
        jmp k_build
k_usb:
        lda dlen
        cmp #254
        bcc k_build
        jmp toolong
k_build:
        ldx leaf_at
        ldy #0
-       cpy base_end
        beq +
        lda gm_name,y
        sta dpath,x
        inx
        iny
        bne -
+       lda #$2d                ; -
        sta dpath,x
        inx
        lda keep
        ora #$30
        sta dpath,x
        inx
        ldy ext_at
-       cpy gm_nlen
        beq +
        lda gm_name,y
        sta dpath,x
        inx
        iny
        bne -
+       stx dlen
        jmp copy
aleaf:                          ; dpath's last name (after its last /), 16 characters at most
        ldx dlen
-       dex
        cpx #$ff                ; (paths reach 255 bytes: not bmi)
        beq +
        lda dpath,x
        cmp #$2f
        bne -
+       inx
        stx leaf_at
        lda #16
        sta leaf_left
-       ldx leaf_at
        cpx dlen
        beq +
        lda dpath,x
        jsr gm_printable
        jsr gm_aput
        inc leaf_at
        dec leaf_left
        bne -
+       rts
replace:
        lda dfmt
        cmp #3
        beq replace_usb
        lda #$53                ; S0: and the exact name
        sta dc_text
        lda #$30
        sta dc_text+1
        lda #$3a
        sta dc_text+2
        ldx #0
-       lda dpath,x
        sta dc_text+3,x
        inx
        cpx dlen
        bne -
        txa
        clc
        adc #3
        sta dc_length
        lda ddev
        sta dc_device
        sta gm_dev
        lda dfmt
        sta gm_fmt
        jsr dc_command
        bcs replace_fail
        cmp #1                  ; 01, FILES SCRATCHED, exactly one
        bne replace_unproven
        lda dc_track
        cmp #1
        bne replace_unproven
        jmp copy
replace_usb:
        lda #$09                ; DELETE_FILE: an empty reply
        jsr ucmd_d
        bcs replace_fail
        lda N_FACTUAL
        ora N_FACTUAL+1
        bne replace_unproven
        jmp copy
replace_unproven:
        lda #N_IOERROR
replace_fail:
        jmp fail

; ---- folders (USB onto USB) ------------------------------------------------------
; Copy the folder spath/slen to dpath/dlen: make it, then copy each entry, read
; again by its position (the cursor is closed while a file is copied, since a
; DOS context holds one open file). tstack keeps the positions of the folders
; above. Carry set after an alert; what was made stays.
tree:
        ldx slen                ; not into itself: dpath is neither spath nor below it
        cpx dlen
        beq t_same
        bcs t_ok
        lda dpath,x
        cmp #$2f
        bne t_ok
t_same:
        dex
-       lda spath,x
        cmp dpath,x
        bne t_ok
        dex
        bpl -
        lda #<s_itself
        ldx #>s_itself
        jmp refuse
t_ok:
        lda #0
        sta depth
t_make:
        jsr mkdir
        bcs t_out
        lda #0
        sta index
t_next:
        jsr cancel
        bcs t_cancel
        jsr dirent
        bcs t_out
        beq t_up                ; no more here
        jsr push_s
        bcs t_out
        jsr push_d
        bcs t_out
        lda eattr
        and #$10
        bne t_down
        jsr copy_new
        bcs t_out
        jsr pop_d
        jsr pop_s
        inc index
        jmp t_next
t_down:
        ldx depth
        cpx #TDEPTH
        bcs t_deep
        lda index
        sta tstack,x
        inc depth
        jmp t_make
t_up:
        lda depth
        beq t_done
        dec depth
        jsr pop_d
        jsr pop_s
        ldx depth
        lda tstack,x
        sta index
        inc index
        jmp t_next
t_done:
        clc
t_out:
        rts
t_cancel:
        jmp cancelled
t_deep:
        jmp toolong
TDEPTH = 16

; Delete everything in the folder spath (Move, after its copy): the first
; entry each time, a folder's contents before the folder. The folder itself
; stays for gm_delete_one. Carry set after an alert.
empty:
        lda #0
        sta depth
em_next:
        lda #0
        sta index
        jsr dirent
        bcs t_out
        beq em_up
        jsr push_s
        bcs t_out
        lda eattr
        and #$10
        beq em_file
        inc depth
        bne em_next
em_up:
        lda depth
        beq t_done              ; (the top folder stays)
        dec depth
em_file:
        lda #$09                ; DELETE_FILE: a file, or a folder now empty
        ldy sdev
        jsr ucmd_s
        bcs em_fail
        lda N_FACTUAL           ; a message instead of the empty reply: refused
        ora N_FACTUAL+1
        bne unproven
        jsr pop_s
        jmp em_next
em_fail:
        jmp fail

; The first entry at position index or after it in the folder spath, not "."
; or "..": Z clear with its name in gm_name/gm_nlen, its attribute in eattr
; and index at its position; Z set when there is none. Carry set after an alert.
dirent:
        lda #0
        sta phase
        sta k
        ldx #0
        lda #2                  ; a directory cursor
        jsr open
        bcs e_error
e_read:
        jsr read_source         ; one packet: the attribute, then the name
        bcs e_error
        lda size
        ora size+1
        beq e_none
        lda k
        cmp index
        bcc e_skip
        lda N_BUFFER+1          ; "." and ".."
        cmp #$2e
        bne e_found
        ldx size
        cpx #2
        beq e_dot
        cpx #3
        bne e_found
        lda N_BUFFER+2
        cmp #$2e
        bne e_found
e_dot:
        inc index
e_skip:
        inc k
        jmp e_read
e_found:
        lda k
        sta index
        lda N_BUFFER
        sta eattr
        ldx size
        dex
        stx gm_nlen
        ldx #0
-       lda N_BUFFER+1,x
        sta gm_name,x
        inx
        cpx gm_nlen
        bne -
        jsr close_streams
        bcs e_close
        lda #1
        rts
e_none:
        jsr close_streams
        bcs e_close
        lda #0
        rts
e_error:
        jmp io_error
e_close:
        jmp close_error

; Make the folder dpath on the target's context: FILE_STAT must find nothing
; there, CREATE_DIR must answer without a message, and FILE_STAT must then
; find a folder. A folder already there is merged into: its entries stay and
; the copied ones join them (a name on both asks, as for any file); a file
; there is refused.
mkdir:
        lda #$08
        jsr ucmd_d
        bcs +
        lda N_BUFFER+11
        and #$18
        cmp #$10
        beq m_merge
        jmp exists
m_merge:
        clc
        rts
+       lda #$16                ; CREATE_DIR
        jsr ucmd_d
        bcs em_fail
        lda N_FACTUAL
        ora N_FACTUAL+1
        bne unproven
        lda #$08
        jsr ucmd_d
        bcs unproven
        lda N_BUFFER+11
        and #$18
        cmp #$10
        bne unproven
        inc created
        clc
        rts
unproven:
        lda #N_IOERROR
        jmp fail

; A = an Ultimate DOS opcode on dpath (the target's context) or, with Y = the
; context, on spath. Carry set with A = error; the reply is in N_BUFFER.
ucmd_d:
        pha
        ldy #0
-       lda dpath,y
        sta N_UPATH,y
        iny
        cpy dlen
        bne -
        lda dopen
        sta N_BUFFER
        pla
        jmp ucmd
ucmd_s:
        sty N_BUFFER
        ldy #0
-       pha
        lda spath,y
        sta N_UPATH,y
        pla
        iny
        cpy slen
        bne -
ucmd:                           ; A = opcode, N_BUFFER = context, Y = path length
        sty N_FNAMELEN
        sta N_BUFFER+1
        jmp gm_ucmd_at

; "/" and gm_name onto spath or dpath; carry set after an alert when the
; path would pass 255 bytes. pop_s/pop_d take the last name off again.
push_s:
        ldx slen
        lda #$2f
        sta spath,x
        ldy #0
-       inx
        beq p_long
        lda gm_name,y
        sta spath,x
        iny
        cpy gm_nlen
        bne -
        inx
        beq p_long
        stx slen
        clc
        rts
push_d:
        ldx dlen
        lda #$2f
        sta dpath,x
        ldy #0
-       inx
        beq p_long
        lda gm_name,y
        sta dpath,x
        iny
        cpy gm_nlen
        bne -
        inx
        beq p_long
        stx dlen
        clc
        rts
p_long:
        jmp toolong
pop_s:
        ldx slen
-       dex
        lda spath,x
        cmp #$2f
        bne -
        stx slen
        rts
pop_d:
        ldx dlen
-       dex
        lda dpath,x
        cmp #$2f
        bne -
        stx dlen
        rts

; ---- progress ----------------------------------------------------------------------
.include "gemdesk-progress.inc"
progress_text:                  ; "Copying N/M" or "Moving N/M" into gm_abuf
        lda #0
        sta gm_alen
        lda #<s_copying
        ldx #>s_copying
        ldy choice
        cpy #2
        bne +
        lda #<s_moving
        ldx #>s_moving
+       jsr gm_astr
        lda item_no
        jsr pt_number
        lda #$2f                ; /
        jsr gm_aput
        lda total
        jsr pt_number
        lda #0
        jmp gm_aput
pt_number:
        sta gm_num
        lda #0
        sta gm_num+1
        jmp gm_anum

acknowledged:                   ; Z set when N_FACTUAL = size
        lda N_FACTUAL
        cmp size
        bne +
        lda N_FACTUAL+1
        cmp size+1
+       rts
stash:
        ldx #0
-       lda N_BUFFER,x
        sta data,x
        lda N_BUFFER+256,x
        sta data+256,x
        inx
        bne -
        rts
advance:                        ; X = 0 copied, 4 compared: += size
        clc
        lda counts,x
        adc size
        sta counts,x
        lda counts+1,x
        adc size+1
        sta counts+1,x
        bcc +
        inc counts+2,x
        bne +
        inc counts+3,x
+       rts
suffix: .byte 46,80,82,71   ; .PRG
s_copy: .byte 91,50,93,91,67,111,112,121,32,0   ; [2][Copy 
s_to: .byte 124,116,111,32,0   ; |to 
s_choice: .byte 63,93,91,67,111,112,121,124,77,111,118,101,124,67,97,110,99,101,108,93,0   ; ?][Copy|Move|Cancel]
s_exists: .byte 32,97,108,114,101,97,100,121,124,101,120,105,115,116,115,32,111,110,32,0   ;  already|exists on 
s_stopped: .byte 91,49,93,91,67,111,112,121,32,115,116,111,112,112,101,100,46,124,0   ; [1][Copy stopped.|
s_part: .byte 32,109,97,121,32,104,111,108,100,124,112,97,114,116,32,111,102,32,0   ;  may hold|part of 
s_badname: .byte 91,49,93,91,84,104,105,115,32,110,97,109,101,32,100,111,101,115,32,110,111,116,32,102
        .byte 105,116,124,97,32,100,114,105,118,101,58,32,49,54,32,99,104,97,114,97,99,116,101,114
        .byte 115,44,124,110,111,32,42,32,63,32,44,32,61,32,58,32,64,32,111,114,32,113,117,111
        .byte 116,101,46,93,91,79,75,93,0   ; [1][This name does not fit|a drive: 16 characters,|no * ? , = : @ or quote.][OK]
s_empty: .byte 91,49,93,91,65,32,100,114,105,118,101,32,99,97,110,110,111,116,32,104,111,108,100,124
        .byte 97,110,32,101,109,112,116,121,32,102,105,108,101,46,93,91,79,75,93,0   ; [1][A drive cannot hold|an empty file.][OK]
s_mismatch: .byte 91,51,93,91,84,104,101,32,99,111,112,121,32,100,111,101,115,32,110,111,116,32,109,97
        .byte 116,99,104,46,124,84,104,101,32,111,114,105,103,105,110,97,108,32,105,115,32,107,101,112
        .byte 116,46,93,91,79,75,93,0   ; [3][The copy does not match.|The original is kept.][OK]
s_ask_head: .byte 91,50,93,91,0   ; [2][
s_conflict: .byte 46,93,91,82,101,112,108,97,99,101,124,75,101,101,112,32,98,111,116,104,124,83,107,105,112,93,0   ; .][Replace|Keep both|Skip]
s_itself: .byte 91,49,93,91,65,32,102,111,108,100,101,114,32,99,97,110,110,111,116,32,98,101,124,99,111,112,105,101,100,32,105,110,116,111,32,105,116,115,101,108,102,46,93,91,79,75,93,0   ; [1][A folder cannot be|copied into itself.][OK]
s_copying: .byte 67,111,112,121,105,110,103,32,0   ; Copying 
s_moving: .byte 77,111,118,105,110,103,32,0   ; Moving 
depth: .byte 0
index: .byte 0                  ; an entry's position in the folder at depth
k: .byte 0
eattr: .byte 0
tstack: .fill TDEPTH,0
item_no: .byte 0
total: .byte 0
dslot: .byte 0
failed_slot: .byte 0
ddev: .byte 0
choice: .byte 0
stop: .byte 0
created: .byte 0
skipped: .byte 0                ; a name conflict was skipped in this row
keep: .byte 0                   ; Keep both: the suffix number in use, or 0
ext_at: .byte 0
base_end: .byte 0
leaf_at: .byte 0
leaf_left: .byte 0
phase: .byte 0
error: .byte 0
dos: .byte 0
counts: .fill 8,0               ; copied, then compared (LE32 each)
data = gm_sortbuf               ; the chunk: no listing is sorted while copying
.bend
