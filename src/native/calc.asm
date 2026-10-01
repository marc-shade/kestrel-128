; Native Kestrel calculator with an owner-managed bank-1 history, GPL v3.
.include "api.inc"
.weak
NATIVE_CALC_GRAPHICS=0
.endweak
* = N_APPBASE
app_image:
        .text "napp"
 .if NATIVE_CALC_GRAPHICS
        .byte 1,1,8,0          ; owned bitmap presentation
 .else
        .byte 1,1,6,0          ; shared focused fields use ABI 1.6
 .endif
        .word calc_end-app_image
 .if NATIVE_CALC_GRAPHICS
        .byte (calc_end-app_image+255)/256,0
 .else
        .byte 16,0             ; 4 KiB code/data, zero-filled before loading
 .endif
        .word calc_entry-app_image
        .word 0                ; build-native.py seals CRC16 over the image
        .text "calculator",0
        .fill N_APPBASE+32-*,0
calc_entry:
        cld
        lda N_CURRENT
        sta owner
        sta N_OWNER
        lda #2
        sta N_PAGES
        lda #1
        sta N_BANK
        jsr N_ALLOC
        bcc calc_history_allocated
        rts                    ; launch reports app return code, cleans its slot
calc_history_allocated:
        ldx #3
calc_keep_handle:
        lda N_HANDLE,x
        sta history_handle,x
        dex
        bpl calc_keep_handle
        lda #0
        sta history_count
        sta history_head
        sta history_view
        sta history_pending
        sta save_mode
        sta save_status
        jsr save_source
 .if NATIVE_CALC_GRAPHICS
        tsx
        stx cg_stack
        lda #0
        sta cg_exit_error
        jsr cg_begin
 .endif
        jmp c_clear
cloop:
        lda #1
        sta N_READY
        jsr N_KEYIN
 .if NATIVE_CALC_GRAPHICS
        bne cg_have_key
        jsr cg_mouse
        beq cloop
cg_have_key:
 .else
        beq cloop
 .endif
        ldx #0
        stx N_READY
 .if NATIVE_CALC_GRAPHICS
        ldx cg_exit_error
        beq +
        cmp #27
        beq calc_exit
        jmp cloop
+
        jsr cg_key
        bcs cloop
 .endif
        ldx save_mode
        beq *+5
        jmp save_key
        cmp #$1b
        beq calc_exit
        cmp #$43
        beq calc_clear
        cmp #$63
        beq calc_clear
        cmp #$4e
        beq calc_older
        cmp #$6e
        beq calc_older
        cmp #$42
        beq calc_newer
        cmp #$62
        beq calc_newer
        cmp #$53
        bne *+5
        jmp save_begin
        cmp #$73
        bne *+5
        jmp save_begin
        ldx c_err
        bne cloop              ; ESC and history remain available during errors
        cmp #$14
        bne *+5
        jmp c_del
        cmp #13
        beq calc_equal
        cmp #$3d
        beq calc_equal
        cmp #$2b
        beq calc_plus
        cmp #$2d
        beq calc_minus
        cmp #$2a
        beq calc_times
        cmp #$2f
        beq calc_divide
        cmp #$30
        bcc cloop
        cmp #$3a
        bcs cloop
        jmp c_dig
calc_clear:
        jmp c_clear
calc_equal:
        lda #1
        sta history_pending
        jmp c_eq
calc_plus:
        lda #1
        jmp c_op
calc_minus:
        lda #2
        jmp c_op
calc_times:
        lda #3
        jmp c_op
calc_divide:
        lda #4
        jmp c_op
calc_exit:
 .if NATIVE_CALC_GRAPHICS
        jsr vd_close
        bcc +
        ldx cg_stack          ; history failures may arrive with nested app frames
        txs
        jsr cg_status
        jmp cloop
+
        jsr pm_close
        lda cg_exit_error
 .else
        lda #0
 .endif
        jmp N_EXIT             ; one-way exit drops app frames, releases all owners
calc_older:
        clc
        lda history_view
        adc #8
        cmp history_count
        bcc *+5
        jmp cloop
        sta history_view
        jsr c_show
        jmp cloop
calc_newer:
        lda history_view
        bne *+5
        jmp cloop
        sec
        sbc #8
        sta history_view
        jsr c_show
        jmp cloop

.include "calc-engine.inc"

c_show:
        lda c_elen
        bne calc_show_entry
        lda c_fresh
        beq calc_show_entry
        lda c_acc
        sta c_tmp
        lda c_acc+1
        sta c_tmp+1
        jmp calc_format
calc_show_entry:
        lda c_ent
        sta c_tmp
        lda c_ent+1
        sta c_tmp+1
calc_format:
        lda c_err
        beq calc_number
        ldx #0
        cmp #1
        bne calc_overflow
calc_divzero_text:
        lda text_divzero,x
        sta dispbuf,x
        inx
        cmp #0
        bne calc_divzero_text
        beq calc_formatted
calc_overflow:
        lda text_overflow,x
        sta dispbuf,x
        inx
        cmp #0
        bne calc_overflow
        beq calc_formatted
calc_number:
        jsr fmt_dec
calc_formatted:
        lda history_pending
        beq calc_redraw
        jsr history_append
calc_redraw:
 .if NATIVE_CALC_GRAPHICS
        jsr cg_redraw
        lda cg_bitmap
 .else
        lda #0
 .endif
        sta screen
calc_screen:
 .if NATIVE_CALC_GRAPHICS
        lda screen
        beq +
        lda vd_phase         ; text output would overwrite active/saved VDC pixels
        bne calc_screen_done
+
 .endif
        lda $d7
        rol
        lda #0
        rol
        cmp screen
        beq calc_screen_ready
        jsr $ff5f
calc_screen_ready:
        lda #$93
        jsr $ffd2
        lda #<text_title
        ldx #>text_title
        jsr puts
        lda #<dispbuf
        ldx #>dispbuf
        jsr puts
        lda #<text_help
        ldx #>text_help
        jsr puts
        jsr history_show
        jsr save_show
        inc screen
        lda screen
        cmp #2
        bne calc_screen
calc_screen_done:
        rts

history_select:
        lda owner
        sta N_OWNER
        ldx #3
history_select_loop:
        lda history_handle,x
        sta N_HANDLE,x
        dex
        bpl history_select_loop
        lda #16
        sta N_COUNT
        lda #0
        sta N_COUNT+1
        rts
history_offset:
        asl
        asl
        asl
        asl
        sta N_OFFSET
        lda #0
        rol
        sta N_OFFSET+1
        rts
history_append:
        lda #0
        sta history_pending
        sta history_view
        jsr history_select
        ldx #15
        lda #$20
history_blank:
        sta N_BUFFER,x
        dex
        bpl history_blank
        ldx #0
history_text:
        lda dispbuf,x
        beq history_text_done
        sta N_BUFFER,x
        inx
        cpx #8
        bne history_text
history_text_done:
        lda history_head
        jsr history_offset
        jsr N_WRITE
        bcs history_failure
        inc history_head
        lda history_head
        and #31
        sta history_head
        lda history_count
        cmp #32
        beq history_appended
        inc history_count
history_appended:
        rts
history_failure:
 .if NATIVE_CALC_GRAPHICS
        sta cg_exit_error
        jmp calc_exit
 .else
        jmp N_EXIT             ; loader preserves error as the app exit code
 .endif
history_show:
        jsr history_select
        lda #0
        sta history_row
        lda history_count
        bne history_row_loop
        lda #<text_empty
        ldx #>text_empty
        jmp puts
history_row_loop:
        clc
        lda history_view
        adc history_row
        cmp history_count
        bcs history_shown
        sta history_ordinal
        sec
        lda history_head
        sbc #1
        sec
        sbc history_ordinal
        and #31
        jsr history_offset
        jsr N_READ
        bcs history_failure
        lda #0
        sta text_index
history_print:
        ldx text_index
        lda N_BUFFER,x
        jsr $ffd2
        inc text_index
        lda text_index
        cmp #16
        bne history_print
        lda #13
        jsr $ffd2
        inc history_row
        lda history_row
        cmp #8
        bne history_row_loop
history_shown:
        rts
puts:
        sta text_read+1
        stx text_read+2
text_read:
        lda $ffff
        beq text_done
        jsr $ffd2
        inc text_read+1
        bne text_read
        inc text_read+2
        jmp text_read
text_done:
        rts

text_title: .text "kestrel calculator",13,13,"result: ",0
text_help: .text 13,13,"0-9 + - * / =  del  c clear",13
           .text "esc return   s save   n/b history",13,13
           .text "history (newest first, 32 retained):",13,0
text_empty: .text "no results yet",13,0
text_divzero: .text "div/0",0
text_overflow: .text "ovf",0
owner: .byte 0
screen: .byte 0
text_index: .byte 0
history_handle: .fill 4,0
history_count: .byte 0
history_head: .byte 0
history_view: .byte 0
history_pending: .byte 0
history_row: .byte 0
history_ordinal: .byte 0
c_acc: .word 0
c_ent: .word 0
c_elen: .byte 0
c_pen: .byte 0
c_fresh: .byte 0
c_err: .byte 0
c_tmp: .word 0
c_tmp2: .byte 0
c_divs: .word 0
c_rem: .word 0
c_opkey: .byte 0
dispbuf: .fill 8,0
.include "calc-save.inc"
 .if NATIVE_CALC_GRAPHICS
.include "calc/gui.inc"
 .endif
calc_end:
 .if NATIVE_CALC_GRAPHICS
        .cerror * > N_APPBASE+$6000, "graphical calculator exceeds app slot"
 .else
        .cerror * > N_APPBASE+$1000, "calculator exceeds declared allocation"
 .endif
