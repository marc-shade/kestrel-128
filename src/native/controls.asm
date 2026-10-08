; Native Ultimate controls. GPL v3.
; Device access uses the shared, bounded query and command services.
.include "api.inc"
NK_SAVED_BUFFER=$5400
GFX_TEXT_STORAGE=$5ac0
PM_KEYS_OWNED=1               ; retain keyboard ownership across the picker
* = N_APPBASE
uc_image:
        .text "napp"
        .byte 1,1,12,0
        .word uc_end-uc_image
        .byte (uc_end-uc_image+255+48)/256,0
        .word uc_entry-uc_image
        .word 0
        .text "ultimate",0
        .fill N_APPBASE+32-*,0
uc_entry:
        cld
        jsr ug_workspace
        bcc +
        jmp N_EXIT
+       jsr ud_init
        lda #0
        sta uc_page
        sta uc_interface
        lda #4
        sta uc_target
        jsr ug_init
uc_refresh:
        jsr ug_cleanup
        bcc +
        jsr ug_cleanup_failed
        jmp cloop
+       lda #0
        sta ug_notice
        sta N_READY
        sta uc_valid
        sta uc_error
        sta uc_count
        lda uc_page
        beq uc_info
        cmp #1
        beq uc_drives
        cmp #2
        beq uc_network
        jmp uc_clock
uc_info:
        lda #N_U_HARDWARE
        jsr uc_query
        sta uc_model_error
        lda uc_length+1
        bne uc_model_long
        lda uc_length
        cmp #65
        bcc +
uc_model_long:
        lda #64
+       sta uc_model_length
        ldx #63
-       lda uc_data,x
        sta uc_model,x
        dex
        bpl -
        lda uc_target
        sta N_UARG
        lda #N_U_IDENTIFY
        jsr uc_query
        jmp uc_render
uc_drives:
        jsr ud_probe
        jmp uc_render
uc_network:
        lda #N_U_INTERFACES
        jsr uc_query
        bcs uc_render
        lda uc_length+1
        bne uc_bad_reply
        lda uc_length
        cmp #1
        bne uc_bad_reply
        lda uc_data
        sta uc_count
        beq uc_render
        cmp uc_interface
        bcc uc_interface_reset
        bne +
uc_interface_reset:
        lda #0
        sta uc_interface
+       lda uc_interface
        sta N_UARG
        lda #N_U_IP
        jsr uc_query
        bcs uc_render
        lda uc_length+1
        bne uc_bad_reply
        lda uc_length
        cmp #12
        bne uc_bad_reply
        lda #1
        sta uc_valid
        bne uc_render
uc_clock:
        lda #N_U_TIME
        jsr uc_query
        bcs uc_render
        jsr uc_parse_time
        jmp uc_render
uc_bad_reply:
        lda #N_CORRUPT
        sta uc_error
uc_render:
        jsr ug_update
        jsr uc_draw_both
cloop:
        lda #1
        sta N_READY
uc_get_key:
        jsr N_KEYIN
        bne uc_key_ready
        jsr ug_mouse
        beq cloop
uc_key_ready:
        ldx #0
        stx N_READY
        ldx vd_phase
        beq +
        ldx vd_fault
        beq +
        cmp #27
        beq uc_exit
        jmp cloop
+
        jsr ug_key
        bcs cloop
        cmp #27
        beq uc_exit
        cmp #$9d
        beq uc_previous
        cmp #$1d
        beq uc_next
        and #$df
        cmp #$52
        beq uc_retry
        cmp #$49
        beq uc_info_key
        cmp #$44
        beq uc_drives_key
        cmp #$4e
        beq uc_network_key
        cmp #$54
        bne cloop
        lda #3
        bne uc_page_key
uc_info_key:
        lda #0
        beq uc_page_key
uc_drives_key:
        lda #1
        bne uc_page_key
uc_network_key:
        lda #2
uc_page_key:
        sta uc_page
        sta ui_selected
        jmp uc_refresh
uc_exit:
        jsr ug_exit
        jmp cloop
uc_retry:
        lda vd_phase
        bne uc_refresh
        lda #0
        sta ug_vdc_attempted
        jmp uc_refresh
uc_previous:
        lda uc_page
        beq uc_target_previous
        cmp #2
        bne cloop
        lda uc_count
        beq cloop
        lda uc_interface
        bne +
        lda uc_count
+       sec
        sbc #1
        sta uc_interface
        jmp uc_refresh
uc_target_previous:
        dec uc_target
        bne uc_refresh
        lda #15
        sta uc_target
        jmp uc_refresh
uc_next:
        lda uc_page
        beq uc_target_next
        cmp #2
        bne cloop
        lda uc_count
        beq cloop
        lda uc_interface
        clc
        adc #1
        cmp uc_count
        bcc +
        lda #0
+       sta uc_interface
        jmp uc_refresh
uc_target_next:
        inc uc_target
        lda uc_target
        cmp #16
        bcc uc_refresh
        lda #1
        sta uc_target
        jmp uc_refresh

; Retain the complete first reply, including an error prefix. Display routines
; use its exact length and never interpret a failed response as fresh data.
uc_query:
        sta N_UOP
        lda N_CURRENT
        sta N_FOWNER
        jsr N_UQUERY
uc_query_result:
        sta uc_error
        lda N_FDOS
        sta uc_dos
        lda N_FSTATUS
        sta uc_transport
        lda N_FACTUAL
        sta uc_length
        lda N_FACTUAL+1
        sta uc_length+1
        ldx #0
-       lda N_BUFFER,x
        sta uc_data,x
        lda N_BUFFER+256,x
        sta uc_data+256,x
        inx
        bne -
        ldx #31
-       lda N_USTATUS,x
        sta uc_status,x
        dex
        bpl -
        lda uc_error
        cmp #1
        rts

; Full count/length agreement, or the documented observed count=4/length=7
; short form. The latter is explicitly partial; it cannot enable mutations.
uc_parse_drives:
        lda #0
        sta uc_partial
        lda uc_length+1
        bne uc_parse_bad
        lda uc_length
        beq uc_parse_bad
        lda uc_data
        cmp #5
        bcs uc_parse_bad
        sta uc_count
        asl
        clc
        adc uc_count
        adc #1
        cmp uc_length
        beq uc_drive_records
        lda uc_count
        cmp #4
        bne uc_parse_bad
        lda uc_length
        cmp #7
        bne uc_parse_bad
        lda #1
        sta uc_partial
        lda #2
        sta uc_count
uc_drive_records:
        ldx #0
        ldy #0
-       cpx uc_count
        beq uc_parse_valid
        lda uc_data+2,y
        cmp #31
        bcs uc_parse_bad
        lda uc_data+3,y
        cmp #2
        bcs uc_parse_bad
        iny
        iny
        iny
        inx
        bne -
uc_parse_valid:
        lda #1
        sta uc_valid
        rts
uc_parse_bad:
        lda #N_CORRUPT
        sta uc_error
        rts

; DOS GET_TIME supplies exactly YYYY/MM/DD HH:MM:SS. Validate calendar and
; clock fields before presenting the snapshot as the cartridge's RTC time.
uc_parse_time:
        lda uc_length+1
        bne uc_parse_bad
        lda uc_length
        cmp #19
        bne uc_parse_bad
        ldx #18
-       lda uc_time_pattern,x
        beq uc_time_digit
        cmp uc_data,x
        bne uc_parse_bad
        beq uc_time_next
uc_time_digit:
        lda uc_data,x
        cmp #$30
        bcc uc_parse_bad
        cmp #$3a
        bcs uc_parse_bad
uc_time_next:
        dex
        bpl -
        ldx #5
        jsr uc_pair
        beq uc_parse_bad
        cmp #13
        bcs uc_parse_bad
        tax
        lda uc_month_days-1,x
        sta uc_days
        cpx #2
        bne uc_time_day
        ldx #2
        jsr uc_pair
        and #3
        bne uc_time_day
        lda uc_data+2
        cmp #$30
        bne uc_leap_day
        lda uc_data+3
        cmp #$30
        bne uc_leap_day
        ldx #0
        jsr uc_pair
        and #3
        bne uc_time_day
uc_leap_day:
        inc uc_days
uc_time_day:
        ldx #8
        jsr uc_pair
        beq uc_parse_bad
        cmp uc_days
        bcc +
        bne uc_parse_bad
+       ldx #11
        jsr uc_pair
        cmp #24
        bcs uc_parse_bad
        ldx #14
        jsr uc_pair
        cmp #60
        bcs uc_parse_bad
        ldx #17
        jsr uc_pair
        cmp #60
        bcs uc_parse_bad
        jmp uc_parse_valid
uc_pair:
        lda uc_data,x
        and #15
        asl
        sta uc_number
        asl
        asl
        clc
        adc uc_number
        sta uc_number
        lda uc_data+1,x
        and #15
        clc
        adc uc_number
        rts

uc_draw_both:
        lda ug_bitmap
        sta uc_screen
-       lda uc_screen
        beq +
        lda vd_phase
        bne uc_draw_both_done
+       lda $d7
        rol
        lda #0
        rol
        cmp uc_screen
        beq +
        jsr $ff5f
+       jsr uc_draw
        inc uc_screen
        lda uc_screen
        cmp #2
        bne -
uc_draw_both_done:
        rts
uc_draw:
        lda ug_collect
        bne uc_draw_body
        lda #$93
        jsr uc_emit
        lda ug_mode
        beq +
        cmp #2
        bne uc_drive_dialog
        lda #<ut_heading
        ldx #>ut_heading
        jsr uc_puts
        jsr ut_body
        jmp uc_draw_end
uc_drive_dialog:
        lda #<ug_confirm_heading
        ldx #>ug_confirm_heading
        jsr uc_puts
        jsr ug_confirm_body
        jmp uc_draw_end
+
        lda #<uc_title
        ldx #>uc_title
        jsr uc_puts
uc_draw_body:
        lda uc_page
        bne uc_draw_not_info
        jsr uc_draw_info
        jmp uc_draw_end
uc_draw_not_info:
        cmp #1
        bne uc_draw_not_drives
        jsr uc_draw_drives
        jmp uc_draw_end
uc_draw_not_drives:
        cmp #2
        bne uc_draw_clock
        jsr uc_draw_network
        jmp uc_draw_end
uc_draw_clock:
        lda #<uc_clock_title
        ldx #>uc_clock_title
        jsr uc_puts
        lda uc_error
        bne uc_draw_failed
        jsr uc_data_text
        lda #<uc_clock_hint
        ldx #>uc_clock_hint
        jsr uc_puts
uc_draw_end:
        lda ug_collect
        bne +
        jmp ug_console_footer
+       rts
uc_draw_failed:
        jsr uc_show_error
        jmp uc_draw_end
uc_draw_info:
        lda #<uc_hardware_title
        ldx #>uc_hardware_title
        jsr uc_puts
        lda uc_model_error
        beq +
        lda #<uc_unavailable
        ldx #>uc_unavailable
        jsr uc_puts
        jmp uc_draw_identity
+       lda #<uc_model
        ldx #>uc_model
        jsr uc_text_source
        lda uc_model_length
        sta uc_text_left
        lda #36
        ldx ug_collect
        beq +
        lda #33                 ; reserve three cells for a clipped model suffix
+
        sta uc_text_limit
        jsr uc_text
uc_draw_identity:
        lda #<uc_target_title
        ldx #>uc_target_title
        jsr uc_puts
        lda uc_target
        jsr uc_decimal
        jsr uc_newline
        lda uc_error
        bne uc_show_error
        jmp uc_data_text
uc_draw_drives:
        lda #<uc_drives_title
        ldx #>uc_drives_title
        jsr uc_puts
        lda uc_error
        bne uc_show_error
        lda uc_count
        bne +
        lda #<uc_no_drives
        ldx #>uc_no_drives
        jmp uc_puts
+       lda uc_partial
        beq +
        lda #<uc_partial_title
        ldx #>uc_partial_title
        jsr uc_puts
+       lda #0
        sta uc_index
        sta uc_record
uc_draw_drive:
        lda #<uc_slot_title
        ldx #>uc_slot_title
        jsr uc_puts
        lda uc_index
        clc
        adc #1
        jsr uc_decimal
        lda #<uc_type_title
        ldx #>uc_type_title
        jsr uc_puts
        ldx uc_record
        lda ud_records,x
        jsr uc_hex
        lda #<uc_iec_title
        ldx #>uc_iec_title
        jsr uc_puts
        ldx uc_record
        lda ud_records+1,x
        jsr uc_decimal
        lda #<uc_off
        ldx #>uc_off
        ldy uc_record
        pha
        lda ud_records+2,y
        bne +
        pla
        jmp uc_draw_power
+       pla
        lda #<uc_on
        ldx #>uc_on
uc_draw_power:
        jsr uc_puts
        inc uc_index
        lda uc_record
        clc
        adc #3
        sta uc_record
        lda uc_index
        cmp uc_count
        bne uc_draw_drive
        lda #<uc_drive_types
        ldx #>uc_drive_types
        jmp uc_puts
uc_draw_network:
        lda #<uc_network_title
        ldx #>uc_network_title
        jsr uc_puts
        lda uc_count
        jsr uc_decimal
        jsr uc_newline
        lda uc_error
        bne uc_show_error
        lda uc_count
        bne +
        lda #<uc_no_interfaces
        ldx #>uc_no_interfaces
        jmp uc_puts
+       lda #<uc_interface_title
        ldx #>uc_interface_title
        jsr uc_puts
        lda uc_interface
        jsr uc_decimal
        jsr uc_newline
        lda #0
        sta uc_index
        sta uc_record
uc_draw_address:
        ldx uc_record
        lda uc_address_lo,x
        pha
        lda uc_address_hi,x
        tax
        pla
        jsr uc_puts
        lda #4
        sta uc_octets
-       ldx uc_index
        lda uc_data,x
        jsr uc_decimal
        inc uc_index
        dec uc_octets
        beq +
        lda #$2e
        jsr uc_emit
        jmp -
+       jsr uc_newline
        inc uc_record
        lda uc_record
        cmp #3
        bne uc_draw_address
        lda #<uc_network_hint
        ldx #>uc_network_hint
        jmp uc_puts

uc_show_error:
        lda #<uc_failed
        ldx #>uc_failed
        jsr uc_puts
        lda uc_error
        jsr uc_hex
        lda #<uc_dos_title
        ldx #>uc_dos_title
        jsr uc_puts
        lda uc_dos
        jsr uc_hex
        lda #<uc_transport_title
        ldx #>uc_transport_title
        jsr uc_puts
        lda uc_transport
        jsr uc_hex
        jsr uc_newline
        lda uc_error
        cmp #N_CORRUPT
        bne +
        lda #<uc_malformed
        ldx #>uc_malformed
        jmp uc_puts
+       lda #<uc_status
        ldx #>uc_status
        jsr uc_text_source
        lda #31
        sta uc_text_left
        sta uc_text_limit
        jmp uc_text
uc_data_text:
        lda #<uc_data
        ldx #>uc_data
        jsr uc_text_source
        lda uc_length+1
        beq +
        lda #255
        bne uc_data_length
+       lda uc_length
uc_data_length:
        sta uc_text_left
        lda #144
        sta uc_text_limit
        jmp uc_text
uc_text_source:
        sta uc_text_read+1
        stx uc_text_read+2
        rts
uc_text:
        lda #0
        sta uc_text_any
        sta uc_column
uc_text_next:
        lda uc_text_left
        beq uc_text_end
uc_text_read:
        lda $ffff
        beq uc_text_end
        ldx uc_text_limit
        beq uc_text_clipped
        jsr uc_ascii
        lda #1
        sta uc_text_any
        inc uc_text_read+1
        bne +
        inc uc_text_read+2
+       dec uc_text_left
        dec uc_text_limit
        inc uc_column
        lda uc_column
        cmp #36
        bne uc_text_next
        jsr uc_newline
        lda #0
        sta uc_column
        beq uc_text_next
uc_text_clipped:
        lda #<uc_clipped
        ldx #>uc_clipped
        jsr uc_puts
        jmp uc_newline
uc_text_end:
        lda uc_column
        bne uc_newline
        lda uc_text_any
        beq uc_newline
        rts
uc_ascii:
        cmp #32
        bcc uc_ascii_bad
        cmp #127
        bcs uc_ascii_bad
        cmp #$61
        bcc +
        cmp #$7b
        bcs +
        and #$df
+       jmp uc_emit
uc_ascii_bad:
        lda #$2e
        jmp uc_emit
uc_puts:
        sta uc_put_byte+1
        stx uc_put_byte+2
uc_put_byte:
        lda $ffff
        beq uc_put_done
        jsr uc_emit
        inc uc_put_byte+1
        bne uc_put_byte
        inc uc_put_byte+2
        bne uc_put_byte
uc_put_done:
        rts
uc_newline:
        lda #13
        jmp uc_emit
uc_hex:
        pha
        lsr
        lsr
        lsr
        lsr
        tax
        lda uc_hex_digits,x
        jsr uc_emit
        pla
        and #15
        tax
        lda uc_hex_digits,x
        jmp uc_emit
uc_decimal:
        sta uc_number
        lda #0
        sta uc_leading
        ldx #0
uc_decimal_next:
        lda #$30
        sta uc_digit
-       lda uc_number
        cmp uc_powers,x
        bcc +
        sec
        sbc uc_powers,x
        sta uc_number
        inc uc_digit
        bne -
+       stx uc_decimal_index
        lda uc_digit
        cmp #$30
        bne uc_decimal_print
        lda uc_leading
        bne uc_decimal_print
        cpx #2
        bne uc_decimal_skip
uc_decimal_print:
        lda #1
        sta uc_leading
        lda uc_digit
        jsr uc_emit
uc_decimal_skip:
        ldx uc_decimal_index
        inx
        cpx #3
        bne uc_decimal_next
        rts

uc_title: .text "ultimate ii+",13,13,"i info  d drives  n network  t clock",13,13,0
uc_footer: .text 13,"r refresh   esc desktop",13,"left/right: target or interface",13,0
uc_hardware_title: .text "hardware",13,0
uc_unavailable: .text "unavailable",13,0
uc_target_title: .text 13,"target ",0
uc_drives_title: .text "ultimate drive inventory",13,13,0
uc_partial_title: .text "partial reply: 2 of 4 records",13,13,0
uc_no_drives: .text "no drive records",13,0
uc_slot_title: .text "slot ",0
uc_type_title: .text "  type ",0
uc_iec_title: .text "  iec ",0
uc_on: .text "  on",13,0
uc_off: .text "  off",13,0
uc_drive_types: .text 13,"types: 00=1541 01=1571 02=1581",13,"other type codes shown as reported.",13,0
uc_network_title: .text "network interfaces: ",0
uc_interface_title: .text "interface ",0
uc_no_interfaces: .text "no interfaces available",13,0
uc_ip_title: .text 13,"ip:      ",0
uc_mask_title: .text "mask:    ",0
uc_gateway_title: .text "gateway: ",0
uc_address_lo: .byte <uc_ip_title,<uc_mask_title,<uc_gateway_title
uc_address_hi: .byte >uc_ip_title,>uc_mask_title,>uc_gateway_title
uc_network_hint: .text 13,"configured addresses; link untested.",13,0
uc_clock_title: .text "cartridge rtc",13,13,0
uc_clock_hint: .text "s set time  r refresh clock reading.",13,0
uc_failed: .text "unavailable: ",0
uc_dos_title: .text "  dos ",0
uc_transport_title: .text "  link ",0
uc_malformed: .text "invalid reply; r retries the query.",13,0
uc_clipped: .text "...",0
uc_hex_digits: .text "0123456789abcdef"
uc_powers: .byte 100,10,1
uc_time_pattern: .byte 0,0,0,0,$2f,0,0,$2f,0,0,$20,0,0,$3a,0,0,$3a,0,0
uc_month_days: .byte 31,28,31,30,31,30,31,31,30,31,30,31
uc_page: .byte 0
uc_target: .byte 0
uc_interface: .byte 0
uc_valid: .byte 0
uc_partial: .byte 0
uc_count: .byte 0
uc_error: .byte 0
uc_dos: .byte 0
uc_transport: .byte 0
uc_length: .word 0
uc_model_error: .byte 0
uc_model_length: .byte 0
uc_screen: .byte 0
uc_index: .byte 0
uc_record: .byte 0
uc_number: .byte 0
uc_leading: .byte 0
uc_digit: .byte 0
uc_decimal_index: .byte 0
uc_days: .byte 0
uc_octets: .byte 0
uc_text_any: .byte 0
uc_text_left: .byte 0
uc_text_limit: .byte 0
uc_column: .byte 0
uc_model=$5a20
uc_status=$5a60
uc_data=$5000
.include "controls/workspace.inc"
.include "controls/clock.inc"
.include "controls/drives.inc"
.include "controls/view.inc"
.include "controls/input.inc"
.include "controls/console.inc"
.include "controls/buttons.inc"
.include "graphics/buttons.inc"
ui_selected: .byte 0
.include "graphics/graphics-core.inc"
.include "graphics/text-core.inc"
pm_start = 60               ; clear of every control here (native_*_scene RECTS)
.include "input/pointer.inc"
drive_picker .block
FD_EMBEDDED=1
FD_GUI=1
FD_GUI_SHARED=1
FD_GUI_SURFACE=ug_handle
FD_VDC=1
FD_VDC_PHASE=vd_phase
FD_VDC_FAULT=vd_fault
FD_VDC_ROWS=vm_rows
FD_VDC_PENDING=vm_pending
FD_VDC_SYNC=ug_vdc_sync
FD_VDC_FULL=ug_vdc_full
FD_VDC_CLOSE=vd_close
B_COPY=0
FD_DIRECT_PAGES=6
FD_RETAINED_STORAGE=$5500
FD_BUFFER_BASE=$5800
FD_NAME_BUFFER=ud_name
FD_SCRATCH0=uc_data
FD_SCRATCH1=0                  ; patched only after allocating picker scratch
FD_SCRATCH2=0
FD_SCRATCH3=0
FD_SAFE_CHARACTER=ug_safe_character
.include "file-dialog.inc"
.bend
ug_picker_active=drive_picker.fd_active
ug_picker_get_key=drive_picker.b_get_key
BP_MODE=0
bp_select_surface=ug_select_view
.include "graphics/vdc-client.inc"
uc_end:
        .cerror uc_end+48>N_APPLIMIT, "Ultimate controls need the packed-startup cleanup tail"
