; Kestrel 128 native C128 kernel and memory workspace. GPL v3 or later, see LICENSE.
; BASIC 7 entry; never switches the machine into C64 mode.
.include "api.inc"
.weak
NATIVE_DESKTOP_BOOT = 0
NATIVE_BOOT_FORMAT = 0
.endweak
        .cerror NATIVE_BOOT_FORMAT < 0 || NATIVE_BOOT_FORMAT > 2, "invalid native boot geometry"
* = $1c01
        .word basic_end
        .word 10
        .byte $9e
        .text " 7184"
        .byte 0
basic_end:
        .word 0
* = $1c10
        jmp native_start
        .text "kes128"
        .byte 1
* = N_ALLOC
        jmp heap_alloc
        jmp heap_free
        jmp heap_read
        jmp heap_write
        jmp heap_fill
        jmp heap_stats
        jmp heap_release
        jmp heap_reserve
        jmp app_launch
        jmp native_keyin
        jmp app_exit
        jmp fs_open
        jmp fs_read
        jmp fs_write
        jmp fs_close
        jmp fs_release
        jmp fs_dirpage
        jmp app_replace
        jmp app_workspace
        jmp field_edit
        jmp field_draw
        jmp module_load
        jmp module_call
        jmp module_close
        jmp display_show
        jmp display_close
        jmp ultimate_query
        jmp ultimate_command
; SYS enters with BASIC's map, where the staging addresses are BASIC ROM:
; select the native map here, below $4000, before the boot code runs.
native_start:
        cld
        bit $d505
        bvc native_mode
        rts                     ; refuse C64 mode without changing its map
native_mode:
        lda #$0e                ; bank 0 RAM below $c000, system ROM and I/O
        sta $ff00
        jmp native_boot
native_resume:
        jsr heap_stats
.if NATIVE_DESKTOP_BOOT
        bcs native_fail
        jmp native_browser
.else
        bcc native_resume_draw
.endif
native_fail:
        sta ui_status
native_resume_draw:
        jmp native_draw         ; the memory workspace lives in the system section
native_calculator:
        lda N_BOOTFORMAT
        sta N_APPFORMAT
        lda ui_system_device
        sta N_DEVICE
        ldx #3
native_calc_name:
        lda ui_calc_name,x
        sta N_APPNAME,x
        dex
        bpl native_calc_name
        lda #4
        sta N_NAMELEN
        jsr app_launch
        bcs native_calc_result
        lda N_EXITCODE
native_calc_result:
        sta ui_status
        jmp native_draw
native_browser:
        lda N_BOOTFORMAT
        sta N_APPFORMAT
        lda ui_system_device
        sta N_DEVICE
        ldx #5
        ldy #5
        lda N_DOCRETURN
        beq +
        ldy #10
        dex
+       txa
        clc
        adc #1
        sta N_NAMELEN
        lda #0
        sta N_DOCREQUEST
native_browser_name:
        lda ui_browser_name,y
        sta N_APPNAME,x
        dey
        dex
        bpl native_browser_name
        lda N_DOCRETURN
        sta N_DOCRESUME
        eor #1                  ; Files returns to the Desktop; Desktop to workspace
        sta ui_browser_stage
        lda #0
        sta N_DOCRETURN
native_dispatch:
        jsr app_launch
        bcc native_dispatch_return
        sta N_BROWSERERROR
        ldx ui_browser_stage
        bne native_browser_result
        ldx N_APPSTATE
        bne native_browser_result
        beq native_browser
native_dispatch_return:
        lda N_ACTION
        cmp #1
        beq native_dispatch_next
        cmp #2
        beq native_dispatch_done
        lda N_EXITCODE
        sta N_BROWSERERROR
        ldx ui_browser_stage
        beq native_browser
        bne native_browser_result
native_dispatch_next:
        lda #0
        sta ui_browser_stage
        beq native_dispatch
native_dispatch_done:
        lda #0
        sta N_DOCREQUEST
        sta N_DOCRETURN
        beq native_browser_result
native_browser_result:
        jmp native_calc_result

.include "apps.inc"
.include "files.inc"
.include "module-cache.inc"
.include "ultimate-directory.inc"
        ; The scan callback must remain below BASIC ROM ($4000), since ROM
        ; SCNKEY invokes it with mapping $00 as well as the native $0e map.
native_keycheck:
        php
        sei
        cpy #88                 ; 0..87 are keys; 88 is the null sentinel
        bcc native_keycheck_valid
        inc native_key_rejects   ; retain rejected activity for diagnostics
        bne +
        inc native_key_rejects+1
+
        plp
        lda #$7f                ; same column cleanup as ROM SCNRTS
        sta $dc00
        rts
native_keycheck_valid:
        plp
        jmp (native_keycheck_saved)
native_keycheck_end:
.include "field-view.inc"
ui_browser_name: .text "browsefiles"
ui_system_device: .byte 0
ui_browser_stage: .byte 0
ui_status = N_RESULT
.include "display-gate.inc"
native_code_end:
        .cerror * > $3800, "native kernel overlaps allocation tables: ", *
* = NPAGES0
        .fill 512,0
* = N_BUFFER
        .fill 512,0
* = NHANDLES
        .fill 256,0
* = N_OWNER
        .fill $100,0            ; includes the session clipboard; reset on native boot
* = N_BROWSERNAME
        .fill 256,0
* = N_SOURCEPATH
        .fill 256,0
        .cerror * > $4000, "native system must remain below allocatable RAM"
native_metadata_end:
* = N_SERVICEBASE
native_service_start:
.include "ultimate.inc"
.include "module-context.inc"
native_module_context_end:
.include "display-restore.inc"
native_service_end:
        .cerror * > N_SERVICELIMIT, "native Ultimate service exceeds reserved RAM"
* = N_RELOCBASE
native_low_image:
        .logical N_LOWBASE
native_low_start:
.include "heap.inc"
.include "fields.inc"
.include "module-gate.inc"
native_module_gate_end:
.include "display-close.inc"
        .cerror * > N_NMIGATE, "low kernel overlaps NMI mapping bridge"
        .fill N_NMIGATE-*,0
native_nmi_gate:
        lda #$0e                ; ROM NMI entry selected system map $00
        sta $ff00               ; expose native app RAM; retain KERNAL/I/O
        jmp (N_NMIPTR)           ; ROM $ff33 restores the interrupted mapping
native_nmi_gate_end:
native_heap_epoch:              ; N_HEAPEPOCH, bumped by every heap page-owner change
        .word 0
        .cerror native_heap_epoch != N_HEAPEPOCH, "N_HEAPEPOCH moved"
native_low_end:
        .fill (-*) & $ff,0
native_low_padded_end:
        .cerror * > N_LOWLIMIT, "resident low kernel overlaps the BASIC entry"
native_low_pages = (native_low_padded_end-native_low_start)/256
        .cerror native_low_pages < 1, "empty resident low section"
        .here
native_boot_image:
.include "kernel-boot.inc"
native_boot_end:
; System section: C128 RAM at $0c00..$0fff that only the KERNAL's RS-232
; buffers (device 2, never opened here) and BASIC sprite definitions use.
; Bank-0 RAM below $4000, so it runs under the native map like main code.
native_sys_image:
        .logical N_SYSBASE
native_sys_start:
native_draw:
        jsr ui_redraw
native_loop:
        lda #1
        sta N_READY
        jsr native_keyin        ; native KERNAL GETIN ($034a/$d0 buffer)
        beq native_loop
native_key_counted:
        ldx #0
        stx N_READY
        and #$7f
        and #$df
        cmp #$11                ; '1' with bit 5 removed
        beq native_bank_zero
        cmp #$12                ; '2'
        beq native_bank_one
        cmp #$41
        beq native_allocate
        cmp #$46
        beq native_free
        cmp #$57
        bne *+5
        jmp native_write
        cmp #$56
        bne *+5
        jmp native_verify
        cmp #$43
        bne *+5
        jmp native_calculator
        cmp #$42
        bne *+5
        jmp native_browser
        jmp native_draw
native_bank_zero:
native_bank_one:
native_bank:
        sec
        sbc #$11                ; masked '1'/'2' -> bank 0/1
        sta ui_bank
        jmp native_draw
native_allocate:
        jsr ui_get_handle
        lda N_HANDLE
        bne native_draw
        lda #16
        sta N_OWNER
        lda #32
        sta N_PAGES
        lda ui_bank
        sta N_BANK
        bne native_allocate_auto
        lda #$df                ; top 32 managed pages keep document RAM contiguous
        sta N_PAGE
        jsr heap_reserve
        jmp native_allocate_done
native_allocate_auto:
        jsr heap_alloc
native_allocate_done:
        bcc *+5
        jmp native_fail
        jsr ui_keep_handle
        lda #0
        sta ui_status
        jmp native_draw
native_free:
        jsr ui_get_handle
        jsr heap_free
        bcc *+5
        jmp native_fail
        lda #0
        sta N_HANDLE
        sta N_HANDLE+1
        sta N_HANDLE+2
        sta N_HANDLE+3
        jsr ui_keep_handle
        lda #0
        sta ui_status
        jmp native_draw
native_write:
        lda #1
        sta ui_test_operation
        jsr ui_pattern_test
        sta ui_status
        jmp native_draw
native_verify:
        lda #0
        sta ui_test_operation
        jsr ui_pattern_test
        sta ui_status
        jmp native_draw

ui_get_handle:
        lda #16
        sta N_OWNER
        lda ui_bank
        asl
        asl
        tax
        ldy #0
ui_get_handle_loop:
        lda ui_handles,x
        sta N_HANDLE,y
        inx
        iny
        cpy #4
        bne ui_get_handle_loop
        rts
ui_keep_handle:
        lda ui_bank
        asl
        asl
        tax
        ldy #0
ui_keep_handle_loop:
        lda N_HANDLE,y
        sta ui_handles,x
        inx
        iny
        cpy #4
        bne ui_keep_handle_loop
        rts

; The workspace consumes the same public allocator/transfer services as apps.
; Its two independent 8 KiB blocks retain different full-byte patterns.
ui_pattern_test:
        jsr ui_get_handle
        lda #0
        sta N_OFFSET
        sta N_OFFSET+1
        sta N_COUNT
        lda #2
        sta N_COUNT+1
ui_pattern_block:
        lda ui_test_operation
        bne ui_prepare_pattern
        jsr heap_read
        bcs ui_pattern_done
ui_prepare_pattern:
        ldy #0
ui_pattern_byte:
        tya
        eor N_OFFSET+1
        ldx ui_bank
        beq ui_pattern_zero
        eor #$a5
ui_pattern_zero:
        ldx ui_test_operation
        beq ui_compare_pattern
ui_pattern_store:
        sta N_BUFFER,y
        eor #1
        sta N_BUFFER+256,y
        jmp ui_pattern_next
ui_compare_pattern:
ui_pattern_compare:
        cmp N_BUFFER,y
        bne ui_pattern_mismatch
        eor #1
        cmp N_BUFFER+256,y
        bne ui_pattern_mismatch
ui_pattern_next:
        iny
        bne ui_pattern_byte
        lda ui_test_operation
        beq ui_pattern_advance
        jsr heap_write
        bcs ui_pattern_done
ui_pattern_advance:
        inc N_OFFSET+1
        inc N_OFFSET+1
        lda N_OFFSET+1
        cmp #32
        bne ui_pattern_block
        lda #0
ui_pattern_done:
        rts
ui_pattern_mismatch:
        lda #$0a
        rts

; KERNAL text output is used for this native memory workspace. Repainting
; both screens exercises native screen switching and I/O after bank access.
ui_redraw:
        jsr heap_stats
        lda #0
        sta ui_screen
ui_screen_loop:
        lda $d7
        rol
        lda #0
        rol
        cmp ui_screen
        beq ui_selected_screen
        jsr $ff5f
ui_selected_screen:
        lda #$93
        jsr $ffd2
        lda #<ui_title
        ldx #>ui_title
        jsr ui_puts
        lda ui_bank
        clc
        adc #$30
        jsr $ffd2
        lda #<ui_free_title
        ldx #>ui_free_title
        jsr ui_puts
        lda N_FREE0
        jsr ui_hex
        lda #$2f
        jsr $ffd2
        lda N_FREE1
        jsr ui_hex
        lda #<ui_slots_title
        ldx #>ui_slots_title
        jsr ui_puts
        lda N_SLOTS
        jsr ui_hex
        lda #<ui_handle_title
        ldx #>ui_handle_title
        jsr ui_puts
        jsr ui_get_handle
        ldx #3
        stx ui_digit
ui_show_handle:
        ldx ui_digit
        lda N_HANDLE,x
        jsr ui_hex
        dec ui_digit
        bpl ui_show_handle
        lda #<ui_result_title
        ldx #>ui_result_title
        jsr ui_puts
        lda ui_status
        jsr ui_hex
        lda #<ui_help
        ldx #>ui_help
        jsr ui_puts
        inc ui_screen
        lda ui_screen
        cmp #2
        beq ui_screens_done
        jmp ui_screen_loop
ui_screens_done:
        rts
ui_puts:
        sta ui_text_byte+1
        stx ui_text_byte+2
ui_text_byte:
        lda $ffff
        beq ui_text_done
        jsr $ffd2
        inc ui_text_byte+1
        bne ui_text_byte
        inc ui_text_byte+2
        jmp ui_text_byte
ui_text_done:
        rts
ui_hex:
        pha
        lsr
        lsr
        lsr
        lsr
        jsr ui_nibble
        pla
        and #15
ui_nibble:
        cmp #10
        bcc ui_decimal
        clc
        adc #7
ui_decimal:
        clc
        adc #$30
        jmp $ffd2

ui_calc_name = ui_help_calc+2   ; first four bytes of "calculator"
ui_title: .text "kestrel - native memory workspace",13,13,"selected bank: ",0
ui_free_title: .text 13,"free 256-byte pages (hex) 0/1: ",0
ui_slots_title: .text 13,"free handles (hex): ",0
ui_handle_title: .text 13,"selected handle: ",0
ui_result_title: .text 13,"last result: ",0
ui_help: .text 13,13,"1/2 select bank  a allocate 8k",13
         .text "w fill  v verify  f release",13
ui_help_calc: .text "c calculator  b files and apps",13
         .text "00 ok  04 invalid handle  0a mismatch",13,13
         .text "native desktop migration in progress",0
ui_handles: .fill 8,0
ui_bank: .byte 0
ui_screen: .byte 0
ui_digit: .byte 0
ui_test_operation: .byte 0
native_sys_end:
        .cerror * > N_SYSLIMIT, "system section exceeds $0c00..$0fff"
        .here
native_load_end:
        .cerror native_load_end > N_APPBASE, "boot staging overlaps the app entry"
