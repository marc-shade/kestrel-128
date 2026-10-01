; Present an owned VIC hires surface on the VDC. App supplies vm_select_surface.
; Logical 320x200 pixels become 640x200; controls retain the same coordinates.
; 64K uses RGBI cell attributes. 16K keeps light button fills by reversing ink.
; Dirty flags cover eight scanlines. No unowned read through bank-0 ROM is used.
.weak
VM_INCLUDE_COMMON=1
VM_INCLUDE_DIRTY=1
vm_surface_read=N_READ
.endweak
.if VM_INCLUDE_COMMON
.weak
vd_initial_bitmap=vm_initial
vd_initial_attributes=vd_success
.endweak
.endif
.if VM_INCLUDE_DIRTY
gfx_track_dirty=1

vm_dirty:
        lda gfx_clipped+6
        sec
        sbc #1
        ldx gfx_operation
        cpx #1
        beq +
        lsr
        lsr
        lsr
+       tax
        lda gfx_clipped+2
        ldy gfx_operation
        cpy #1
        beq +
        lsr
        lsr
        lsr
+       sta vm_first
        lda #1
        sta vm_pending
-       sta vm_rows,x
        cpx vm_first
        beq +
        dex
        jmp -
+
        rts
.endif

vm_initial:
        lda #1
        sta vm_pending
        ldx #24
-       sta vm_rows,x
        dex
        bpl -
        jmp vm_flush
vm_present:
        lda vd_fault
        bne vm_failed
        lda vd_live
        beq vm_done
        lda vm_pending
        beq vm_done
        jsr vd_gate
        jsr vd_hide_pointer
vm_flush:
        lda #0
        sta vm_row
vm_row_next:
        ldx vm_row
        lda vm_rows,x
        beq vm_row_done
        jsr vm_draw_row
        ldx vm_row
        lda #0
        sta vm_rows,x         ; commit only after the complete row and attributes
vm_row_done:
        inc vm_row
        lda vm_row
        cmp #25
        bne vm_row_next
        lda #0
        sta vm_pending
vm_done:
        clc
        rts
vm_failed:
        sec
        rts

vm_draw_row:
        jsr vm_select_surface
        ; Color offset = $2000 + row*40. Reuse the graphics row*320 table.
        lda vm_row
        asl
        tax
        lda gfx_rows,x
        sta N_OFFSET
        lda gfx_rows+1,x
        sta N_OFFSET+1
        ldx #3
-       lsr N_OFFSET+1
        ror N_OFFSET
        dex
        bne -
        lda N_OFFSET+1
        ora #$20
        sta N_OFFSET+1
        lda #40
        sta N_COUNT
        lda #0
        sta N_COUNT+1
        jsr vm_surface_read
        bcs vm_read_failed
        ldy #39
vm_color_next:
        lda N_BUFFER,y
        and #15
        tax
        lda vm_palette,x
        sta vm_background
        lda vm_light,x
        sta vm_brightness
        lda N_BUFFER,y
        lsr
        lsr
        lsr
        lsr
        tax
        lda vm_palette,x
        sta vm_foreground
        lda #0
        sta vm_reverse,y
        lda vd_color
        beq vm_mono
        lda vm_background
        asl
        asl
        asl
        asl
        ora vm_foreground
        sta vm_colors,y
        jmp vm_color_done
vm_mono:
        lda vm_light,x
        cmp vm_brightness
        bcs vm_color_done
        lda #$ff
        sta vm_reverse,y
vm_color_done:
        dey
        bpl vm_color_next
        lda vm_row
        asl
        tax
        lda gfx_rows,x
        sta N_OFFSET
        lda gfx_rows+1,x
        sta N_OFFSET+1
        lda #64
        sta N_COUNT
        lda #1
        sta N_COUNT+1
        jsr vm_surface_read
        bcc +
vm_read_failed:
        jmp vd_fail
+       lda vm_row
        asl
        asl
        asl
        ldx #0
        jsr vd_xy
        lda #0
        sta vm_line
vm_line_next:
        jsr vd_seek
        lda #>N_BUFFER
        sta vm_read+2
        lda #0
        sta vm_column
        ldy vm_line
vm_byte_next:
        ldx vm_column
vm_read:
        lda N_BUFFER,y
        eor vm_reverse,x
        pha
        lsr
        lsr
        lsr
        lsr
        tax
        lda vm_expand,x
        jsr vd_putbyte
        pla
        and #15
        tax
        lda vm_expand,x
        jsr vd_putbyte
        tya
        clc
        adc #8
        tay
        bcc +
        inc vm_read+2
+       inc vm_column
        lda vm_column
        cmp #40
        bne vm_byte_next
        jsr vd_next_row
        inc vm_line
        lda vm_line
        cmp #8
        bne vm_line_next
        lda vd_color
        beq vm_done
        ; Attributes occupy a separate 80x25 map at $8000 on 64K VDCs.
        lda vd_base
        pha
        lda #$80
        sta vd_base
        lda vm_row
        ldx #0
        jsr vd_xy
        pla
        sta vd_base
        jsr vd_seek
        ldy #0
-       lda vm_colors,y
        jsr vd_putbyte
        jsr vd_putbyte
        iny
        cpy #40
        bne -
        rts

; VIC black/white/red/cyan/purple/green/blue/yellow/orange/brown/light red/
; dark gray/gray/light green/light blue/light gray -> nearest RGBI family.
vm_palette: .byte 0,15,8,7,10,4,2,13,12,12,9,1,14,5,3,14
; Relative brightness of the mapped RGBI colors, used only for mono polarity.
vm_light: .byte 0,255,51,204,70,100,19,236,101,101,136,85,170,185,104,170
vm_expand: .byte $00,$03,$0c,$0f,$30,$33,$3c,$3f,$c0,$c3,$cc,$cf,$f0,$f3,$fc,$ff
vm_rows: .fill 25,0
vm_pending: .byte 0
vm_first: .byte 0
vm_row: .byte 0
vm_line: .byte 0
vm_column: .byte 0
vm_background: .byte 0
vm_foreground: .byte 0
vm_brightness: .byte 0
vm_colors: .fill 40,0
vm_reverse: .fill 40,0
.if VM_INCLUDE_COMMON
.include "vdc-lifetime.inc"
.include "vdc-pointer.inc"
.include "vdc-state.inc"
.include "vdc-pointer-shape.inc"
.endif
