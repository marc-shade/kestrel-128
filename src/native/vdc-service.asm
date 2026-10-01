; Shared, retained bank-1 VDC service. The bank-0 parent owns input and VIC UI.
.include "api.inc"
BK_BASE=$6000
RU_BANKED=1
RU_INCLUDE_RESIZE=1
vs_arena_close=bm_display_close
VM_INCLUDE_COMMON=0
VM_INCLUDE_DIRTY=0
VD_DESKTOP_COMMON=0
VD_USE_STATUS_SURFACE=1
vd_initial_bitmap=bv_initial_bitmap
vd_initial_attributes=bv_initial_attributes
vm_surface_read=bv_read
vs_native_alloc=bv_alloc
vs_native_read=bv_read
vs_native_write=bv_write
vs_native_free=bv_free
* = BK_BASE
bv_image:
        .text "nbk1"
        .byte 1,1,12,0
        .word bv_end-bv_image
        .byte (bv_end-bv_image+255)/256,1
        .word bv_entry-bv_image,0
        ldx #$0e
        jmp $02ab
        .byte 0
        .word 0
        .fill 8,0
bv_entry:
        cmp #15
        bcs bh_entry
        cmp #6
        bcs bm_entry
        cmp #5
        beq bv_status
        cmp #4
        beq bv_close
        cmp #1
        bcc bv_empty
        cmp #4
        bcs bv_argument
        sta bv_operation
        lda N_BUFFER
        cmp #2
        bcs bv_argument
        lda N_BUFFER+5
        cmp #7
        bcs bv_argument
        lda N_BUFFER+9
        cmp #2
        bcs bv_argument
        cmp #1
        bne bv_check_y
        lda N_BUFFER+8
        cmp #64
        bcs bv_argument
bv_check_y:
        lda N_BUFFER+10
        cmp #200
        bcs bv_argument
        lda bv_operation
        cmp #1
        bne +
        lda vd_phase
        ora ru_probe_live
        bne bv_argument
        lda ru_active
        beq +
        lda bm_lease
        beq bv_argument
+
        lda N_BUFFER
        sta bv_mode
        ldx #3
-       lda N_BUFFER+1,x
        sta bv_surface,x
        dex
        bpl -
+       lda N_BUFFER+5
        sta gd_selected
        lda N_BUFFER+6
        sta gd_launch_error
        lda N_BUFFER+7
        and #1
        sta pm_seen
        ldx #2
-       lda N_BUFFER+8,x
        sta pm_x,x
        dex
        bpl -
        lda bv_operation
        cmp #1
        beq bv_open
        cmp #3
        beq bv_pointer
        lda bv_mode
        beq +
        jmp vd_select
+
        ldx #24
        lda #0
        sta vm_pending
-       lda N_BUFFER+11,x
        sta vm_rows,x
        ora vm_pending
        sta vm_pending
        dex
        bpl -
        jmp vm_present
bv_pointer:
        jsr vd_poll
        bcs bv_return
        jmp vd_success
bv_return:
        rts
bv_open:
        jmp vd_open
bv_close:
        jmp vd_close
bv_empty:
        lda vd_phase
        ora ru_active
        ora ru_probe_live
        ora bm_lease
        ora bm_pending
        ora bh_live
        bne bv_argument
        jmp vd_success
bv_argument:
        lda #N_BADARG
        sec
        rts
bv_status:
        ldx #6
-       lda vd_phase,x
        sta N_BUFFER,x
        dex
        bpl -
        ldx #3
-       lda vd_handle,x
        sta N_BUFFER+7,x
        lda vd_pointer_visible,x
        sta N_BUFFER+25,x
        dex
        bpl -
        ldx #13
-       lda vd_saved,x
        sta N_BUFFER+11,x
        dex
        bpl -
        lda vs_reu
        sta N_BUFFER+29
        ldx #7
-       lda vs_token,x
        sta N_BUFFER+30,x
        dex
        bpl -
        lda ru_active
        sta N_BUFFER+38
        lda ru_probe_live
        sta N_BUFFER+39
        lda vm_pending
        sta N_BUFFER+40
        jmp vd_success
bv_initial_bitmap:
        lda bv_mode
        bne +
        jmp vm_initial
+       jmp vd_unpack
bv_initial_attributes:
        lda bv_mode
        beq +
        jmp vd_render_selection
+       jmp vd_success
vm_select_surface:
        lda N_CURRENT
        sta N_OWNER
        ldx #3
-       lda bv_surface,x
        sta N_HANDLE,x
        dex
        bpl -
        rts

; VIC status glyphs already exist at x=8,y=176 in the owned surface.
; Preserve native VDC eight-pixel glyph widths without another 760-byte font.
vd_status_surface:
        jsr vm_select_surface
        lda #<7040
        sta N_OFFSET
        lda #>7040
        sta N_OFFSET+1
        lda #184
        sta N_COUNT
        lda #0
        sta N_COUNT+1
        jsr bv_read
        bcc +
        jmp vd_fail
+       lda vd_row
        clc
        adc #8
        tay
        ldx #0
-       lda N_BUFFER,y
        sta N_BUFFER+4,x
        tya
        clc
        adc #8
        tay
        inx
        cpx #22
        bne -
        ; Packing proceeds left to right, below all unread source glyphs.
        ; Clear only after all glyphs have been extracted from the input row.
        lda #0
        ldx #79
-       sta N_BUFFER,x
        dex
        cpx #25
        bne -
        ldx #3
-       sta N_BUFFER,x
        dex
        bpl -
        rts
bv_alloc:
        lda #0
        jmp bk_native
bv_free:
        lda #1
        jmp bk_native
bv_read:
        lda #2
        jmp bk_native
bv_write:
        lda #3
        jmp bk_native
bv_mode: .byte 0
bv_operation: .byte 0
bv_surface: .fill 4,0
pm_seen: .byte 0
pm_x: .word 0
pm_y: .byte 0
gd_selected: .byte 0
gd_launch_error: .byte 0
gd_card_rows: .byte 5,7,9,11,13,15,17
pm_tops: .byte 40,56,72,88,104,120,136
gfx_rows:
 .for row=0, row<25, row+=1
        .word row*320
 .endfor
.include "banked-client.inc"
.include "shared-memory-service.inc"
.include "history-service.inc"
.include "graphics/vdc-reu.inc"
.include "graphics/vdc-mirror.inc"
.include "desktop/vdc.inc"
.include "graphics/vdc-lifetime.inc"
.include "graphics/vdc-pointer.inc"
.include "graphics/vdc-state.inc"
.include "graphics/vdc-pointer-shape.inc"
bv_end:
.cerror bv_end>$c000, "bank-1 VDC service exceeds its executable region"
