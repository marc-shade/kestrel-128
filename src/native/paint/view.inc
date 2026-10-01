; Owned 256x144 viewport into the full banked image. View origin is in cells.
; Drawing only copies document bytes into presentation; pointer/UI are separate.
pa_view_open:
        lda pa_handle
        bne pa_view_initialize
        lda N_CURRENT
        sta N_OWNER
        lda #0
        sta N_BANK
        lda #$c0
        sta N_PAGE
        lda #36
        sta N_PAGES
        jsr N_RESERVE
        bcs pa_view_failed
        ldx #3
-       lda N_HANDLE,x
        sta pa_handle,x
        dex
        bpl -
pa_view_initialize:
        jsr pa_select_view
        lda #0
        sta N_OFFSET
        sta N_OFFSET+1
        sta N_COUNT
        lda #2
        sta N_COUNT+1
-       lda #0
        ldx N_OFFSET+1
        cpx #32
        bcc +
        lda #$16
+       sta N_VALUE
        jsr N_FILL
        bcs pa_view_failed
        inc N_OFFSET+1
        inc N_OFFSET+1
        lda N_OFFSET+1
        cmp #36
        bne -
        jsr pa_draw
        bcs pa_view_failed
        jsr pa_select_view
        jsr N_VSHOW
        bcs pa_view_failed
        lda #1
        sta pa_bitmap
        jsr pm_install
        bcc pa_view_return
pa_view_failed:
        sta pa_view_error
        jsr pa_view_close
        bcs pa_view_return
        lda pa_handle
        beq pa_view_return
        jsr pa_select_view
        jsr N_FREE
        bcs pa_view_return
        lda #0
        sta pa_handle
pa_view_return:
        rts
pa_view_close:
        jsr vd_close
        bcs pa_view_return
pa_surface_close:
        jsr pm_close
        jsr N_VCLOSE
        lda #0
        sta pa_bitmap
        clc
        rts
pa_select_view:
        lda N_CURRENT
        sta N_OWNER
        ldx #3
-       lda pa_handle,x
        sta N_HANDLE,x
        dex
        bpl -
        rts

; X=row, Y=column, pa_address returns an offset within a logical surface.
pa_bitmap_address:
        tya
        asl
        asl
        asl
        sta pa_address
        lda #0
        rol
        sta pa_high
        lda pa_address
        clc
        adc pd_bitmap_lo,x
        sta pa_address
        lda pa_high
        adc pd_bitmap_hi,x
        sta pa_address+1
        rts
pa_color_address:
        tya
        clc
        adc pd_color_lo,x
        sta pa_address
        lda #$20
        adc pd_color_hi,x
        sta pa_address+1
        rts
pa_source_address:
        lda pa_address
        sta pa_source
        lda pa_address+1
        sta pa_source+1
        rts
pa_destination_address:
        lda pa_address
        sta pa_destination
        lda pa_address+1
        sta pa_destination+1
        rts
pa_transfer:
        ldx #0
        jsr pd_select
        lda pa_source
        sta N_OFFSET
        lda pa_source+1
        sta N_OFFSET+1
        lda pa_count
        sta N_COUNT
        lda pa_count+1
        sta N_COUNT+1
        jsr N_READ
        bcs pa_transfer_done
        jsr pa_select_view
        lda pa_destination
        sta N_OFFSET
        lda pa_destination+1
        sta N_OFFSET+1
        jsr N_WRITE
pa_transfer_done:
        rts

pa_blit:
        jsr pa_vdc_full
        lda #0
        sta pa_row
pa_blit_row:
        lda pa_row
        clc
        adc pa_view_y
        tax
        ldy pa_view_x
        jsr pa_bitmap_address
        jsr pa_source_address
        lda pa_row
        clc
        adc #4
        tax
        ldy #1
        jsr pa_bitmap_address
        jsr pa_destination_address
        lda #0
        sta pa_count
        lda #1
        sta pa_count+1
        jsr pa_transfer
        bcs pa_transfer_done
        lda pa_row
        clc
        adc pa_view_y
        tax
        ldy pa_view_x
        jsr pa_color_address
        jsr pa_source_address
        lda pa_row
        clc
        adc #4
        tax
        ldy #1
        jsr pa_color_address
        jsr pa_destination_address
        lda #32
        sta pa_count
        lda #0
        sta pa_count+1
        jsr pa_transfer
        bcs pa_transfer_done
        inc pa_row
        lda pa_row
        cmp #18
        bne pa_blit_row
        lda #0
        clc
        rts

; Update one changed image cell if visible. pa_cell_x/y are document cells.
pa_cell:
        lda pa_cell_x
        sec
        sbc pa_view_x
        bcc pa_cell_hidden
        cmp #32
        bcs pa_cell_hidden
        clc
        adc #1
        sta pa_local_x
        lda pa_cell_y
        sec
        sbc pa_view_y
        bcc pa_cell_hidden
        cmp #18
        bcs pa_cell_hidden
        clc
        adc #4
        sta pa_local_y
        tax
        lda #1
        sta vm_rows,x
        sta vm_pending
        ldx pa_cell_y
        ldy pa_cell_x
        jsr pa_bitmap_address
        jsr pa_source_address
        ldx pa_local_y
        ldy pa_local_x
        jsr pa_bitmap_address
        jsr pa_destination_address
        lda #8
        sta pa_count
        lda #0
        sta pa_count+1
        jsr pa_transfer
        bcs pa_transfer_done
        ldx pa_cell_y
        ldy pa_cell_x
        jsr pa_color_address
        jsr pa_source_address
        ldx pa_local_y
        ldy pa_local_x
        jsr pa_color_address
        jsr pa_destination_address
        lda #1
        sta pa_count
        jmp pa_transfer
pa_cell_hidden:
        lda #0
        clc
        rts

pa_handle: .fill 4,0
pa_bitmap: .byte 0
pa_view_error: .byte 0
pa_view_x: .byte 0
pa_view_y: .byte 0
pa_row: .byte 0
pa_address: .word 0
pa_high: .byte 0
pa_source: .word 0
pa_destination: .word 0
pa_count: .word 0
pa_cell_x: .byte 0
pa_cell_y: .byte 0
pa_local_x: .byte 0
pa_local_y: .byte 0
