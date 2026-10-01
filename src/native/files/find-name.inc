; Filename search shares the Files modal field and its resident graphics module.
; IEC searches the complete cached root. Ultimate fills the inactive page and
; publishes it only after a complete match page; wrap is bounded to one restart.
fn_begin:
        lda b_busy
        bne fv_no_key
        lda #2
        sta fm_active
        lda #0
        sta fm_sent
        sta fm_error
        sta fm_dos
        sta fm_status
        sta N_UIKEY
        ldx fn_valid
        bne +
        sta fm_length
+       lda #1
        sta fn_valid
        lda #7
        sta fm_result
        jsr fm_field
        jmp fm_draw

fn_search:
        lda fm_length
        beq fn_empty
        bmi fn_empty
        lda b_error
        sta fn_old_error
        lda #0
        sta fm_error
        sta fm_dos
        sta fm_status
        sta fn_wrapped
        lda #1
        sta fg_searching
        lda #255
        sta fv_drawn_view
        lda #27
        sta ui_selected
        lda #9
        sta fm_result
        jsr fv_update
        jsr fg_vdc_sync
        jsr fm_console
        lda vd_phase
        beq +
        lda vd_fault
        bne fn_cancel
+       lda N_BROWSERFMT
        cmp #3
        bne fn_iec
        ldx #3
-       lda N_BROWSERPOS,x
        sta fn_origin,x
        dex
        bpl -
        jsr bu_candidate_current
        ldx #3
-       lda fn_origin,x
        sta bu_target,x
        dex
        bpl -
        lda bu_target
        and #$f8
        sta bu_target
        lda #2
        sta bu_search
        jsr bu_scan
        lda #0
        sta bu_search
        lda b_error
        bne fn_failure
        lda bu_found
        bne fn_found
        beq fn_not_found
fn_empty:
        lda #12
        sta fm_result
        jmp fm_draw

fn_iec:
        lda b_error
        bne fn_failure
        ldx #1
-       lda b_selected,x
        sta fn_at,x
        lda b_total,x
        sta fn_remaining,x
        dex
        bpl -
        lda b_total
        ora b_total+1
        beq fn_not_found
fn_iec_next:
        jsr fn_poll
        bcs fn_cancel
        inc fn_at
        bne +
        inc fn_at+1
+       lda fn_at
        cmp b_total
        lda fn_at+1
        sbc b_total+1
        bcc +
        lda #0
        sta fn_at
        sta fn_at+1
+       ldx #1
-       lda fn_at,x
        sta b_index,x
        dex
        bpl -
        jsr b_cache_select
        jsr N_READ
        bcs fn_failure
        ldx #16
-       lda N_BUFFER+1,x
        cmp #$a0
        bne +
        dex
        bne -
+       stx fn_name_length
        lda #<N_BUFFER+2
        sta fn_load+1
        jsr fn_match
        bcc fn_iec_found
        lda fn_remaining
        bne +
        dec fn_remaining+1
+       dec fn_remaining
        lda fn_remaining
        ora fn_remaining+1
        bne fn_iec_next
fn_not_found:
        lda #8
        bne fn_result
fn_iec_found:
        ldx #1
-       lda fn_at,x
        sta b_selected,x
        dex
        bpl -
fn_found:
        lda #0
        sta fg_searching
        jmp fm_leave
fn_cancel:
        lda #$24
fn_failure:
        sta fn_failure_code
        cmp #$24
        beq +
        lda fn_failure_code
        sta fm_error
        lda #11
        bne fn_result
+       lda #10
fn_result:
        sta fm_result
        lda fn_old_error
        sta b_error
        lda #0
        sta fg_searching
        lda #255
        sta fv_drawn_view
        lda #25
        sta ui_selected
        jmp fm_draw

; Called before directory reads, so input/display services may use N_BUFFER.
; Back, X and Escape cancel. Other typing does not become a later file action.
fn_poll:
        jsr N_KEYIN
        sta fg_key
        jsr fv_input
        cmp #27
        beq fn_poll_cancel
        cmp #14
        bne +
        jsr fv_update
        jsr fm_console
+       jsr fg_vdc_sync
        lda vd_phase
        beq +
        lda vd_fault
        bne fn_poll_cancel
+       clc
        rts
fn_poll_cancel:
        sec
        rts

fn_ultimate_match:
        lda bu_found
        bne fn_match_done
        lda fn_wrapped
        bne fn_eligible
        clc
        lda bu_target
        adc bu_new_count
        sta fn_at
        ldx #1
        ldy #3
-       lda bu_target,x
        adc #0
        sta fn_at,x
        inx
        dey
        bne -
        ldx #3
-       lda fn_at,x
        cmp fn_origin,x
        bcc fn_match_done
        bne fn_eligible
        dex
        bpl -
        rts
fn_eligible:
        lda N_BUFFER+510
        sta fn_name_length
        lda #<N_BUFFER+1
        sta fn_load+1
        jsr fn_match
        bcs fn_match_done
        lda #1
        sta bu_found
        lda bu_new_count
        sta bu_target_row
fn_match_done:
        rts
fn_wrap:
        lda fn_wrapped
        bne fn_no_wrap
        inc fn_wrapped
        jsr bu_zero_target
        sta bu_new_count
        lda #2
        sta bu_search
        clc
        rts
fn_no_wrap:
        sec
        rts

; Literal substring comparison. ASCII case is folded on both backends;
; IEC also folds the PETSCII alternate alphabet. Stored bytes are untouched.
fn_match:
        lda fn_name_length
        sec
        sbc fm_length
        bcc fn_no_match
        sta fn_limit
        lda #0
        sta fn_start
fn_match_start:
        ldx fn_start
        ldy #0
fn_match_character:
fn_load:
        lda N_BUFFER+1,x
        jsr fn_fold
        sta fn_character
        lda fm_name,y
        jsr fn_fold
        cmp fn_character
        bne fn_match_next
        inx
        iny
        cpy fm_length
        bne fn_match_character
        clc
        rts
fn_match_next:
        lda fn_start
        cmp fn_limit
        beq fn_no_match
        inc fn_start
        bne fn_match_start
fn_no_match:
        sec
        rts
fn_fold:
        cmp #$c1
        bcc fm_fold
        cmp #$db
        bcs fm_fold
        pha
        lda N_BROWSERFMT
        cmp #3
        beq fn_fold_ascii
        pla
        and #$7f
        rts
fn_fold_ascii:
        pla
        jmp fm_fold

fn_collect:
        lda #8
        sta fv_view
        lda #<fn_prompt
        ldx #>fn_prompt
        jsr b_puts
        inc fv_row
        lda #0
        sta fv_column
        lda N_BROWSERFMT
        cmp #3
        bne +
        ; The folder header has the same path and DOS rows.
        jmp fm_collect_path
+       lda #<fn_snapshot
        ldx #>fn_snapshot
        jsr b_puts
        inc fv_row
        lda #0
        sta fv_column
        lda #<fn_device
        ldx #>fn_device
        jsr b_puts
        lda N_BROWSERDEV
        ldx #0
        jsr b_number
        jmp fm_collect_field

; Mutually exclusive with CREATE_DIR's joined path buffer.
fn_origin = fm_path
fn_at = fm_path+4
fn_remaining = fm_path+8
fn_wrapped = fm_path+10
fn_name_length = fm_path+11
fn_limit = fm_path+12
fn_start = fm_path+13
fn_character = fm_path+14
fn_old_error = fm_path+15
fn_failure_code = fm_path+16
fn_valid: .byte 0
fn_prompt: .text "find a filename in this directory",0
fn_snapshot: .text "current iec directory snapshot",0
fn_device: .text "device: ",0
fn_find_text: .byte 70,105,110,100,0
