; Ultimate folder creation, rename and delete in the Files presentation
; module, ABI 1.11. Modes: 1 create, 2 search (find-name.inc), 3 rename,
; 4 delete. The modal call keeps this module resident. It never loads another
; module or leaves the application before returning through N_MCALL. The
; browser owns any retained cursor; close it before submitting a serialized
; absolute path. Rename and delete start from the selected entry's raw name.
fr_rename:
        lda #3
        .byte $2c               ; BIT abs: skip the next two-byte load
fr_delete:
        lda #4
        .byte $2c
fm_begin:
        lda #1
        ldx N_BROWSERFMT
        cpx #3
        bne fv_no_key
        ldx b_busy
        bne fv_no_key
        cmp #3
        bcc +
        ldx N_BROWSERNAME_LEN   ; the field holds 1-127 bytes
        beq fv_no_key
        bmi fv_no_key
+       sta fm_active
        ldx #0
        stx fm_sent
        stx fm_result
        stx fm_error
        stx fm_dos
        stx fm_status
        stx fm_length
        stx fm_state+1          ; caret and viewport from an earlier dialog
        stx fm_state+5          ; would exceed a shorter or empty new name
        stx fm_state+6
        stx fn_valid
        stx N_UIKEY
        cmp #3
        bcc fm_opened
-       lda N_BROWSERNAME,x
        sta fm_name,x
        inx
        cpx N_BROWSERNAME_LEN
        bne -
        stx fm_length
        lda #5                  ; Ctrl-E: the field service places the caret
        sta N_UIKEY
fm_opened:
        jsr fm_field
fm_draw:
        jsr fv_update
        jsr fg_vdc_sync
        jsr fm_console
fm_loop:
        lda #1
        sta N_READY
        jsr N_KEYIN
        sta fg_key
        lda #0
        sta N_READY
        lda vd_phase
        beq fm_input
        lda vd_fault
        beq fm_input
        ; The outer Files guard cannot be called inside N_MCALL: it may
        ; request a module notice. Draw it directly and freeze actions here.
        jsr fv_paused_notice
        lda fg_key
        cmp #27
        bne fm_loop
        jsr vd_close
        bcs fm_loop
        jmp fm_leave
fm_input:
        jsr fv_input
        cmp #0
        beq fm_pointer
        cmp #27
        beq fm_leave
        cmp #14
        beq fm_draw
        cmp #13
        bne +
        ldx fm_active
        cpx #2
        bne fm_create
        jmp fn_search
+
        ldx fm_sent
        bne fm_loop
        sta N_UIKEY
        jsr fm_field
        lda #0
        ldx fm_active
        cpx #2
        bne +
        sta fm_error
        sta fm_dos
        sta fm_status
        lda #7
+       sta fm_result
        jmp fm_draw
fm_pointer:
        jsr fg_vdc_sync
        jmp fm_loop
fm_leave:
        lda #0
        sta fm_active
        lda fm_sent
        beq +
        lda #$52                ; rescan only after returning from N_MCALL
        clc
        rts
+       jmp fv_redraw_key
fm_field:
        lda #<fm_state
        sta N_UIPTR
        lda #>fm_state
        sta N_UIPTR+1
        jmp N_FEDIT

fm_enabled:
        cpx #0
        beq fv_enabled_yes
        cpx #27
        beq fv_enabled_yes
        lda fg_searching
        ora fm_sent
        bne fv_enabled_no
        cpx #25
        beq fv_enabled_yes
        cpx #26
        beq fv_enabled_yes
        jmp fv_enabled_no

fm_create:
        lda fm_sent
        bne fm_loop
        jsr fg_vdc_sync
        lda vd_phase
        beq +
        lda vd_fault
        bne fm_loop
+
        jsr fm_path_build
        sta fm_result
        bcs fm_draw
        jsr bu_close_cursor
        bcc +
        lda #6
        sta fm_result
        jsr fm_diagnostics
        jsr fm_lock
        jmp fm_draw
+       jsr fm_lock             ; one submission per dialog, including errors
        ldx fm_active
        lda fm_opcodes-1,x      ; CREATE_DIR, RENAME_FILE or DELETE_FILE
        jsr fm_command
        bcs fm_command_failed
        lda N_FACTUAL
        ora N_FACTUAL+1
        bne fm_unknown
        lda #8
        jsr fm_command          ; FILE_STAT of the created, renamed or deleted path
        ror fm_match            ; bit 7: the metadata request failed
        ldx fm_active
        cpx #4
        bne fm_present
        bit fm_match
        bpl fm_unknown          ; delete: only DOS 82 FILE NOT FOUND proves removal
        lda N_FACTUAL           ; ...with an empty reply; data means malformed
        ora N_FACTUAL+1
        bne fm_unknown
        lda N_FSTATUS
        bne fm_unknown
        lda N_FDOS
        cmp #82
        bne fm_unknown
        lda #3
        bne fm_result_ready
fm_present:
        bit fm_match
        bmi fm_unknown
        lda N_FACTUAL+1
        bne fm_unknown
        lda N_FACTUAL
        cmp #13                 ; size/date/time/ext/attributes plus a name
        bcc fm_unknown
        cmp #76                 ; reference DOS returns at most 63 name bytes
        bcs fm_unknown
        lda N_BUFFER+11
        and #$18
        cpx #1
        bne +
        eor #$10                ; create: exactly a directory
        bne fm_unknown
+       and #$08                ; rename: any file or folder, never a label
        bne fm_unknown
        lda fm_length
        cmp #64
        bcc +
        lda #63
+       sta fm_match_length
        clc
        adc #12
        cmp N_FACTUAL
        bne fm_unknown
        ldx #0
-       lda fm_name,x
        jsr fm_fold
        sta fm_match
        lda N_BUFFER+12,x
        jsr fm_fold
        cmp fm_match
        bne fm_unknown
        inx
        cpx fm_match_length
        bne -
        lda #3
        bne fm_result_ready
fm_command_failed:
        lda #4
        ldx N_FSTATUS
        beq fm_result_ready
fm_unknown:
        lda #5
fm_result_ready:
        sta fm_result
        jsr fm_diagnostics
        jmp fm_draw
fm_lock:
        lda #1
        sta fm_sent
        lda #255
        sta fv_drawn_view
        lda #27
        sta ui_selected
        rts
fm_fold:
        cmp #$61
        bcc +
        cmp #$7b
        bcs +
        and #$df
+       rts
fm_diagnostics:
        lda N_FERROR
        sta fm_error
        lda N_FDOS
        sta fm_dos
        ldx #31
-       lda N_USTATUS,x
        sta fm_status,x
        dex
        bpl -
        lda #0
        sta fm_status+31
        rts

; No CWD mutation or file-handle commands. CREATE_DIR is exclusive in the
; reference FileManager. FILE_STAT needs an explicit NUL: its firmware handler
; passes the command body directly to fstat, unlike CREATE_DIR's terminator.
; RENAME_FILE sends "old NUL new", both absolute; the firmware refuses an
; existing target and moves between filesystems, so no data is replaced.
fm_command:
        sta N_BUFFER+1
        lda N_CURRENT
        sta N_FOWNER
        lda N_BROWSERDEV
        sta N_BUFFER
        lda #0
        sta N_FCOUNT+1
        tax
        lda N_BUFFER+1
        cmp #$0a
        bne fm_new_path
-       lda fm_path,x           ; parent prefix, trailing slash included
        sta N_BUFFER+2,x
        inx
        cpx fm_component
        bne -
        ldy #0
-       lda N_BROWSERNAME,y
        sta N_BUFFER+2,x
        inx
        iny
        cpy N_BROWSERNAME_LEN
        bne -
        lda #0
        sta N_BUFFER+2,x
        inx                     ; old path is at most 254 bytes: X <= 255
fm_new_path:
        stx N_FCOUNT
        txa
        clc
        adc #<(N_BUFFER+2)
        sta fm_store+1
        lda #>(N_BUFFER+2)
        adc #0
        sta fm_store+2
        ldy #0
-       lda fm_path,y
fm_store:
        sta $ffff,y
        iny
        cpy fm_path_length
        bne -
        tya
        clc
        adc N_FCOUNT
        sta N_FCOUNT
        bcc +
        inc N_FCOUNT+1
+       lda N_BUFFER+1
        cmp #8
        bne +
        lda #0
        sta N_BUFFER+2,y        ; FILE_STAT always starts at offset zero
        inc N_FCOUNT
        bne +
        inc N_FCOUNT+1
+       jmp N_UCOMMAND

fm_path_build:
        lda N_BROWSERDEV
        cmp #1
        bcc fm_invalid
        cmp #3
        bcs fm_invalid
        lda fm_length
        beq fm_invalid
        bmi fm_invalid          ; firmware creation components hold 127 bytes
        tax
        lda fm_name-1,x
        cmp #32                 ; FAT strips trailing spaces/periods
        beq fm_invalid
        cmp #46
        beq fm_invalid
        ldx #0
fm_name_check:
        lda fm_name,x
        cmp #32
        bcc fm_invalid
        cmp #127
        bcs fm_invalid
        ldy #8
-       cmp fm_forbidden,y
        beq fm_invalid
        dey
        bpl -
        inx
        cpx fm_length
        bne fm_name_check
        lda N_BROWSERLEN
        beq fm_invalid
        tax
        lda N_BROWSERPATH
        cmp #$2f
        bne fm_invalid
        ldy #0
        sty fm_component
fm_parent:
        lda N_BROWSERPATH,y
        beq fm_invalid
        cmp #$5c
        beq fm_invalid
        cmp #$2f
        bne +
        ldx #0
        stx fm_component
        beq ++
+       inc fm_component
        ldx fm_component
        bmi fm_invalid
+
        sta fm_path,y
        iny
        cpy N_BROWSERLEN
        bne fm_parent
        lda fm_path-1,y
        cmp #$2f
        beq +
        lda #$2f
        sta fm_path,y
        iny
        beq fm_too_long
+       sty fm_component        ; parent prefix length for RENAME_FILE
        tya
        clc
        adc fm_length
        bcs fm_too_long
        sta fm_path_length
        ldx #0
-       lda fm_name,x
        sta fm_path,y
        iny
        inx
        cpx fm_length
        bne -
        lda fm_active
        cmp #3
        bne +
        lda fm_component        ; old path + NUL + new path must fit 510 bytes
        clc
        adc N_BROWSERNAME_LEN
        bcs fm_too_long
        cmp #255
        bcs fm_too_long
+       lda #0
        clc
        rts
fm_invalid:
        lda #1
        sec
        rts
fm_too_long:
        lda #2
        sec
        rts

fm_collect:
        lda fm_active
        cmp #2
        bne +
        jmp fn_collect
+       clc
        adc #6                  ; views 7 create, 9 rename, 10 delete
        sta fv_view
        lda #<fm_prompt
        ldx #>fm_prompt
        jsr b_puts
        inc fv_row
        lda #0
        sta fv_column
fm_collect_path:
        lda N_BROWSERLEN
        sec
        sbc #37
        bcs +
        lda #0
+       tax
-       lda N_BROWSERPATH,x
        jsr fv_emit
        inx
        cpx N_BROWSERLEN
        bne -
        inc fv_row
        lda #0
        sta fv_column
        lda #<fv_dos_caption
        ldx #>fv_dos_caption
        jsr b_puts
        lda N_BROWSERDEV
        ldx #0
        jsr b_number
fm_collect_field:
        lda #7
        sta fv_row
        lda #0
        sta fv_column
        lda #38
        sta N_UIWIDTH
        lda #<fm_state
        sta N_UIPTR
        lda #>fm_state
        sta N_UIPTR+1
        jsr fv_field
        lda #9
        sta fv_row
        lda #0
        sta fv_column
        ldx fm_result
        lda fm_active
        cmp #3
        bcc fm_message          ; rename/delete: results 0, 3 and 4 name their action
        cpx #5
        bcs fm_message
        txa
        beq +
        cmp #3
        bcc fm_message
        sbc #3                  ; 3 -> 0, 4 -> 1; carry stays set (+1 below)
+       adc #13                 ; 0 -> 13 ready, 3 -> 14 checked, 4 -> 15 failed
        tax
fm_message:
        lda fm_messages_lo,x
        pha
        lda fm_messages_hi,x
        tax
        pla
        jsr b_puts
        lda fm_error
        beq fm_collected
        inc fv_row
        lda #0
        sta fv_column
        lda #<fm_error_text
        ldx #>fm_error_text
        jsr b_puts
        lda fm_error
        jsr b_hex
        lda fm_active
        cmp #2
        beq fm_collected
        lda #<fm_dos_text
        ldx #>fm_dos_text
        jsr b_puts
        lda fm_dos
        jsr b_hex
        inc fv_row
        lda #0
        sta fv_column
        lda #<fm_status
        ldx #>fm_status
        jsr b_puts
fm_collected:
        jmp fv_collected

; A refused VDC bitmap still has the full dialog on the 80-column console.
fm_console:
        lda vd_phase
        bne fm_console_done
        lda $d7
        bmi +
        jsr $ff5f
+       lda #$93
        jsr b_usb_chrout
        lda #<fv_body
        sta fm_console_read+1
        lda #>fv_body
        sta fm_console_read+2
        lda #13
        sta fm_console_rows
fm_console_row:
        ldx #0
fm_console_read:
        lda $ffff,x
        jsr b_usb_chrout
        inx
        cpx #40
        bne fm_console_read
        lda #13
        jsr b_usb_chrout
        clc
        lda fm_console_read+1
        adc #40
        sta fm_console_read+1
        bcc +
        inc fm_console_read+2
+       dec fm_console_rows
        bne fm_console_row
        lda ui_selected
        cmp #25
        bne +
        ldy fv_caret_column
        cpy #38
        bcs +
        ldx #7
        clc
        jsr $fff0
        lda #$12
        jsr b_usb_chrout
        ldx fv_caret_column
        lda fv_body+280,x
        jsr b_usb_chrout
        lda #$92
        jsr b_usb_chrout
+
        jmp fv_footer
fm_console_done:
        rts

fm_active: .byte 0
fm_sent: .byte 0
fm_result: .byte 0
fm_error: .byte 0
fm_dos: .byte 0
fm_path_length: .byte 0
fm_component: .byte 0
fm_match: .byte 0
fm_match_length: .byte 0
fm_console_rows: .byte 0
fm_state:
fm_length: .byte 0,0,127
        .word fm_name
        .byte 0,0,0
fm_name: .fill 128,0
fm_forbidden: .byte $22,$2a,$2f,$3a,$3c,$3e,$3f,$5c,$7c
fm_prompt: .text "name in current directory",0
fm_opcodes: .byte $16,0,$0a,$09
fm_create_text: .byte 67,114,101,97,116,101,0
fm_back_text: .byte 66,97,99,107,0
fm_error_text: .text "error: ",0
fm_dos_text: .text "  dos: ",0
fm_message_0: .text "new folder; existing names are kept",0
fm_message_1: .text "use a valid name of 1-127 bytes",0
fm_message_2: .text "complete path exceeds 255 bytes",0
fm_message_3: .text "folder created and checked",0
fm_message_4: .text "create failed; back refreshes",0
fm_message_5: .text "result unknown; back refreshes",0
fm_message_6: .text "close directory failed; back retries",0
fm_message_7: .text "find part of a name; wraps at the end",0
fm_message_8: .text "no matching name in this directory",0
fm_message_9: .text "searching; back or esc cancels",0
fm_message_10: .text "search cancelled; selection kept",0
fm_message_11: .text "search failed; selection kept",0
fm_message_12: .text "enter part of a filename",0
fm_message_13: .text "edit the name; enter applies",0
fm_message_14: .text "done and checked",0
fm_message_15: .text "failed; back refreshes",0
fm_messages_lo: .byte <fm_message_0,<fm_message_1,<fm_message_2,<fm_message_3,<fm_message_4,<fm_message_5,<fm_message_6,<fm_message_7,<fm_message_8,<fm_message_9,<fm_message_10,<fm_message_11,<fm_message_12,<fm_message_13,<fm_message_14,<fm_message_15
fm_messages_hi: .byte >fm_message_0,>fm_message_1,>fm_message_2,>fm_message_3,>fm_message_4,>fm_message_5,>fm_message_6,>fm_message_7,>fm_message_8,>fm_message_9,>fm_message_10,>fm_message_11,>fm_message_12,>fm_message_13,>fm_message_14,>fm_message_15
