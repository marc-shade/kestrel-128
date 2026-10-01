; Export oldest-first history to a new SEQ file, then reopen and compare bytes.
save_begin:
        jsr save_close_file
        bcc *+5
        jmp save_failed_closed
        lda history_count
        bne save_prompt
        lda #4
        sta save_status
        jmp save_redraw
save_prompt:
        lda #0
        sta save_length
        sta save_name
        sta save_status
        sta N_UIKEY
        jsr save_field_edit
        bcs save_input_error
        lda #1
        sta save_mode
save_redraw:
        jsr c_show
        jmp cloop
save_key:
        cmp #27
        beq save_cancel
        cmp #13
        bne *+5
        jmp save_enter
        sta N_UIKEY
        jsr save_field_edit
        bcs save_input_error
        lda N_UIFLAGS
        beq save_key_done
        jmp save_redraw
save_input_error:
        lda #0
        sta save_mode
        lda #6
        sta save_status
        jmp save_redraw
save_field_edit:
        jsr save_field_pointer
        jmp N_FEDIT
save_field_pointer:
        lda #<save_field
        sta N_UIPTR
        lda #>save_field
        sta N_UIPTR+1
        rts
save_cancel:
        lda #0
        sta save_mode
        jmp save_redraw
save_key_done:
        jmp cloop
save_enter:
        lda save_length
        beq save_key_done
        lda #0
        sta save_mode
        sta save_size
        sta save_row
        ; 32 records, at most five text bytes and CR per record (192 total).
save_collect:
        jsr history_select
        sec
        lda history_head
        sbc history_count
        clc
        adc save_row
        and #31
        jsr history_offset
        jsr N_READ
        bcc *+5
        jmp history_failure
        ldx #0
        ldy save_size
save_collect_text:
        lda N_BUFFER,x
        cmp #$20
        beq save_collect_line
        sta save_data,y
        iny
        inx
        cpx #5
        bne save_collect_text
save_collect_line:
        lda #13
        sta save_data,y
        iny
        sty save_size
        inc save_row
        lda save_row
        cmp history_count
        bne save_collect
        lda owner
        sta N_FOWNER
        lda N_DEVICE
        sta N_FDEVICE
        lda #0
        sta N_FTYPE
        lda N_APPFORMAT
        sta N_FFORMAT
        cmp #3
        beq save_usb_name
        lda save_length
        sta N_FNAMELEN
        ldx #15
save_filename:
        lda save_name,x
        sta N_FNAME,x
        dex
        bpl save_filename
        jmp save_create
save_usb_name:
        lda save_prefix
        beq save_path_long
        clc
        adc save_length
        bcs save_path_long
        sta N_FNAMELEN
        ldx #0
save_usb_prefix:
        lda save_path,x
        sta N_UPATH,x
        inx
        cpx save_prefix
        bne save_usb_prefix
        ldy #0
save_usb_leaf:
        lda save_name,y
        sta N_UPATH,x
        inx
        iny
        cpy save_length
        bne save_usb_leaf
save_create:
        lda #1
        sta N_FMODE
        jsr save_open_file
        bcc save_created
        lda #2
        sta save_status
        lda N_FDOS
        cmp #63
        beq save_file_exists
        lda N_APPFORMAT
        cmp #3
        bne save_rejected
        ldx #0
save_exists_text:
        lda save_exists_status,x
        cmp N_USTATUS,x
        bne save_rejected
        cmp #0
        beq save_file_exists
        inx
        bne save_exists_text
save_file_exists:
        lda #3
        sta save_status
save_rejected:
        jsr save_close_file
        bcc *+5
        jmp save_failed_closed
        jmp save_redraw
save_path_long:
        lda #5
        sta save_status
        jmp save_redraw
save_created:
        ldx #0
save_copy:
        lda save_data,x
        sta N_BUFFER,x
        inx
        cpx save_size
        bne save_copy
        lda save_size
        sta N_FCOUNT
        lda #0
        sta N_FCOUNT+1
        jsr N_FWRITE
        bcc *+5
        jmp save_failed
        jsr save_close_file
        bcc *+5
        jmp save_failed
        lda #0
        sta N_FMODE
        jsr save_open_file
        bcc *+5
        jmp save_failed
        lda #0
        sta N_FCOUNT
        lda #2
        sta N_FCOUNT+1
        jsr N_FREAD
        bcc *+5
        jmp save_failed
        lda N_FACTUAL+1
        bne save_failed
        lda N_FACTUAL
        cmp save_size
        bne save_failed
        lda N_FEOF
        cmp #1
        bne save_failed
        ldx #0
save_compare:
        lda save_data,x
        cmp N_BUFFER,x
        bne save_failed
        inx
        cpx save_size
        bne save_compare
        jsr save_close_file
        bcc *+5
        jmp save_failed
        lda #0
        sta save_open
        lda #1
        sta save_status
        jmp save_redraw
save_failed:
        jsr save_close_file      ; only checked CLOSE may retry; retain failure
save_failed_closed:
        lda #2
        sta save_status
        jmp save_redraw

; Snapshot the launch directory before any application file call changes UPATH.
save_source:
        lda #0
        sta save_prefix
        lda N_APPFORMAT
        cmp #3
        bne save_source_done
        ldx #0
save_source_byte:
        lda N_UPATH,x
        sta save_path,x
        cmp #$2f
        bne +
        txa
        clc
        adc #1
        sta save_prefix
+       inx
        cpx N_NAMELEN
        bne save_source_byte
save_source_done:
        rts
save_open_file:
        lda #0
        sta N_FHANDLE
        jsr N_FOPEN
        php
        pha
        lda N_FHANDLE
        sta save_open           ; rejected Ultimate OPEN still requires CLOSE
        pla
        plp
        rts
save_close_file:
        lda save_open
        beq save_closed
        jsr N_FCLOSE
        bcs save_close_done
        lda #0
        sta save_open
save_closed:
        clc
save_close_done:
        rts

save_show:
        lda save_mode
        beq save_show_status
        lda #<save_prompt_text
        ldx #>save_prompt_text
        ldy N_APPFORMAT
        cpy #3
        bne +
        lda #<save_usb_text
        ldx #>save_usb_text
+
        jsr puts
        jsr save_field_pointer
        lda #19
        sta N_UIWIDTH
        jsr N_FDRAW
        lda #<save_controls
        ldx #>save_controls
        jmp puts
save_show_status:
        ldx save_status
        beq save_show_done
        dex
        lda save_messages_lo,x
        pha
        lda save_messages_hi,x
        tax
        pla
        jmp puts
save_show_done:
        rts
save_prompt_text: .text 13,"save as (seq file on iec disk)",13,"name: ",0
save_usb_text: .text 13,"save as (beside usb app)",13,"name: ",0
save_controls: .text 13,"enter save   esc cancel",0
save_ok: .text 13,"history saved and verified",0
save_error_text: .text 13,"disk error; file may be partial",0
save_exists: .text 13,"file exists - choose another name",0
save_empty: .text 13,"no results to save",0
save_long_path: .text 13,"path too long; shorten name",0
save_input_text: .text 13,"input unavailable; esc returns",0
save_exists_status: .text "file exists",0
save_messages_lo: .byte <save_ok,<save_error_text,<save_exists,<save_empty,<save_long_path,<save_input_text
save_messages_hi: .byte >save_ok,>save_error_text,>save_exists,>save_empty,>save_long_path,>save_input_text
save_mode: .byte 0
save_status: .byte 0
save_field:
save_length: .byte 0
save_cursor: .byte 0
        .byte 16
        .word save_name
save_views: .fill 2,0
        .byte 3
save_size: .byte 0
save_row: .byte 0
save_open: .byte 0
save_name: .fill 17,0
save_data: .fill 192,0
save_prefix: .byte 0
save_path: .fill 256,0
