; Read-only CBM directory/chain extent check. D64, D71 and root D81 only.
; U1 reads drive buffers; no BAM, sector or directory writes are issued.
; A temporary channel is closed before opening the actual sequential stream.
fs_metadata:
        lda #FS_META
        ldx f_device
        ldy #10
        jsr $ffba
        lda #1
        ldx #<f_mname
        ldy #>f_mname
        jsr $ffbd
        jsr $ffc0
        bcs fs_meta_open_error
        jsr fs_serial
        bcs fs_meta_close
        jsr fs_drive_status
        bcs fs_meta_close
        jsr fs_extent
        jmp fs_meta_close
fs_meta_open_error:
        jsr fs_io_error
fs_meta_close:
        jsr $ffcc
        lda #FS_META
        jsr $ffc3
        jsr fs_serial
        bcc fs_meta_status
        inc f_uncertain
fs_meta_status:
        jsr fs_drive_status
        bcc fs_meta_return
        inc f_uncertain
fs_meta_return:
        lda f_result
        cmp #1
        rts

fs_extent:
        lda N_DPAGE
        sta f_dskip
        ldx N_FFORMAT
        lda f_mdir,x
        sta f_mtrack
        lda f_mfirst,x
        sta f_msector
        lda f_mdirs,x
        sta f_mlimit
fs_directory:
        lda #0                 ; read all 256 directory bytes
        sta f_mcount
        jsr fs_block
        bcc *+3
        rts
        lda N_FMODE
        cmp #2
        bne fs_directory_search
        lda f_dskip
        beq fs_directory_page
        dec f_dskip
        jmp fs_directory_follow
fs_directory_search:
        lda #0
        sta f_mentry
fs_directory_entry:
        ldx f_mentry
        lda N_BUFFER+2,x
        and #$bf               ; allow the locked bit, require closed SEQ/PRG/USR
        sec
        sbc #$81
        cmp N_FTYPE
        bne fs_directory_next
        ldy #0
fs_directory_name:
        lda #$a0
        cpy N_FNAMELEN
        bcs fs_directory_pad
        lda N_FNAME,y
fs_directory_pad:
        cmp N_BUFFER+5,x
        bne fs_directory_next
        inx
        iny
        cpy #16
        bne fs_directory_name
        jmp fs_extent_found
fs_directory_next:
        clc
        lda f_mentry
        adc #32
        sta f_mentry
        bne fs_directory_entry
fs_directory_follow:
        lda N_BUFFER
        beq fs_extent_missing
        ldx N_FFORMAT
        cmp f_mdir,x
        bne fs_extent_bad
        lda N_BUFFER+1
        cmp f_mfirst,x
        bcc fs_extent_bad
        sta f_msector
        dec f_mlimit
        bne fs_directory
        beq fs_extent_bad
fs_extent_missing:
        lda N_FMODE
        cmp #2
        beq fs_directory_empty
        lda #62
        sta N_FDOS
        lda #N_IOERROR
        jmp fs_error
fs_extent_bad:
        lda #N_CORRUPT
        jmp fs_error
fs_directory_empty:
        clc
        rts
fs_directory_page:
        ; Validate the next link before publishing a page ordinal. Repeated
        ; links cannot make an unbounded iterator: ordinals only increase.
        lda N_BUFFER
        beq fs_directory_normalize
        ldx N_FFORMAT
        cmp f_mdir,x
        bne fs_extent_bad
        lda f_mlimit
        cmp #1
        beq fs_extent_bad
        lda N_BUFFER+1
        cmp f_mfirst,x
        bcc fs_extent_bad
        lda f_mdirs,x
        clc
        adc f_mfirst,x
        cmp N_BUFFER+1
        beq fs_extent_bad
        bcc fs_extent_bad
        lda N_DPAGE
        clc
        adc #1
        sta N_DNEXT
fs_directory_normalize:
        lda #0
        sta f_mentry
fs_directory_record:
        ldx f_mentry
        lda N_BUFFER+2,x
        pha
        and #7
        sta N_BUFFER,x
        pla
        and #$c0
        sta N_BUFFER+1,x
        ldy #16
fs_directory_name_copy:
        lda N_BUFFER+5,x
        sta N_BUFFER+2,x
        inx
        dey
        bne fs_directory_name_copy
        ldx f_mentry
        lda N_BUFFER+30,x
        sta N_BUFFER+18,x
        lda N_BUFFER+31,x
        sta N_BUFFER+19,x
        txa
        clc
        adc #32
        sta f_mentry
        bne fs_directory_record
        lda #8
        sta N_DCOUNT
        clc
        rts
fs_extent_found:
        ldx f_mentry
        lda N_BUFFER+3,x
        sta f_mtrack
        lda N_BUFFER+4,x
        sta f_msector
        lda N_BUFFER+30,x
        sta f_mblocks
        lda N_BUFFER+31,x
        sta f_mblocks+1
        ldx N_FFORMAT
        lda f_mmaxlo,x
        cmp f_mblocks
        lda f_mmaxhi,x
        sbc f_mblocks+1
        bcc fs_extent_chain_bad
        bcs fs_extent_chain
fs_extent_chain_bad:
        jmp fs_extent_bad
fs_extent_chain:
        lda f_mblocks
        ora f_mblocks+1
        beq fs_extent_chain_bad
        lda f_mblocks
        bne fs_extent_decrement
        dec f_mblocks+1
fs_extent_decrement:
        dec f_mblocks
        lda f_mtrack
        ldx N_FFORMAT
        cmp f_mdir,x
        beq fs_extent_chain_bad
        cpx #1
        bne fs_extent_read
        cmp #53                ; second-side D71 BAM track
        beq fs_extent_chain_bad
fs_extent_read:
        lda #2                 ; only the next link is needed for the extent
        sta f_mcount
        jsr fs_block
        bcc *+3
        rts
        lda N_BUFFER
        sta f_mtrack
        lda N_BUFFER+1
        sta f_msector
        lda f_mtrack
        beq fs_extent_last
        lda #254
        jsr fs_extent_add
        jmp fs_extent_chain
fs_extent_last:
        lda f_mblocks
        ora f_mblocks+1
        beq *+5
        jmp fs_extent_bad
        lda f_msector
        bne *+5
        jmp fs_extent_bad
        sec
        sbc #1
        jsr fs_extent_add
        ldx f_slot
        lda #8
        sta NFILES+3,x
        lda NFILES+13,x
        ora NFILES+14,x
        ora NFILES+15,x
        bne fs_extent_done
        inc NFILES+3,x          ; an empty file returns EOF without CHRIN
fs_extent_done:
        clc
        rts
fs_extent_add:
        ldx f_slot
        clc
        adc NFILES+13,x
        sta NFILES+13,x
        bcc fs_extent_added
        inc NFILES+14,x
        bne fs_extent_added
        inc NFILES+15,x
fs_extent_added:
        rts

; Validate geometry before U1. f_mcount=0 means 256, otherwise a prefix.
fs_block:
        ldx N_FFORMAT
        lda f_mtrack
        bne *+5
        jmp fs_block_bad
        cmp f_mtracks,x
        bcc *+5
        jmp fs_block_bad
        cpx #2
        beq fs_block_40
        cmp #36
        bcc fs_block_side
        sbc #35
fs_block_side:
        ldy #21
        cmp #18
        bcc fs_block_sectors
        dey
        dey
        cmp #25
        bcc fs_block_sectors
        dey
        cmp #31
        bcc fs_block_sectors
        dey
        bne fs_block_sectors
fs_block_40:
        ldy #40
fs_block_sectors:
        tya
        cmp f_msector
        bne *+5
        jmp fs_block_bad
        bcs *+5
        jmp fs_block_bad
        lda f_mtrack
        ldx #8
        jsr fs_block_decimal
        lda f_msector
        ldx #11
        jsr fs_block_decimal
        jsr $ffcc
        ldx f_clfn
        jsr $ffc9
        bcs fs_block_io_error
        lda #0
        sta f_mindex
fs_block_command:
        ldx f_mindex
        lda f_mcommand,x
        jsr $ffd2
        jsr fs_serial
        bcs fs_block_return
        inc f_mindex
        lda f_mindex
        cmp #13
        bne fs_block_command
        jsr $ffcc
        jsr fs_serial
        bcs fs_block_return
        jsr fs_drive_status
        bcs fs_block_return
        ldx #FS_META
        jsr $ffc6
        bcs fs_block_io_error
        lda #0
        sta f_mindex
fs_block_read:
        jsr $ffcf
        sta f_byte
        jsr fs_serial
        bcs fs_block_return
        ldx f_mindex
        lda f_byte
        sta N_BUFFER,x
        inc f_mindex
        beq fs_block_complete
        lda f_raw
        and #$40
        bne fs_block_bad
        lda f_mindex
        cmp f_mcount
        bne fs_block_read
fs_block_complete:
        jsr $ffcc
        clc
fs_block_return:
        rts
fs_block_io_error:
        jmp fs_io_error
fs_block_bad:
        jmp fs_extent_bad
fs_block_decimal:
        ldy #$30
fs_block_tens:
        cmp #10
        bcc fs_block_units
        sbc #10
        iny
        bne fs_block_tens
fs_block_units:
        pha
        tya
        sta f_mcommand,x
        pla
        ora #$30
        sta f_mcommand+1,x
        rts

f_mname: .text "#"
f_mcommand: .text "u1:10 0 00 00"
f_mdir: .byte 18,18,40
f_mfirst: .byte 1,1,3
f_mdirs: .byte 18,18,37
f_mtracks: .byte 36,71,81
f_mmaxlo: .byte <683,<1366,<3200
f_mmaxhi: .byte >683,>1366,>3200
f_mtrack: .byte 0
f_msector: .byte 0
f_mlimit: .byte 0
f_mcount: .byte 0
f_mentry: .byte 0
f_mblocks: .word 0
f_mindex: .byte 0
f_dskip: .byte 0
